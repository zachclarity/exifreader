#!/bin/bash
# ──────────────────────────────────────────────────────────────
#  Deployer: publishes Lambda Layer (Tesseract+Poppler), then
#  creates the Lambda function with that layer attached.
#  Waits for Active state before exiting.
# ──────────────────────────────────────────────────────────────
set -euo pipefail

FUNCTION_NAME="ocr-extract"
LAYER_NAME="tesseract-layer"
LAYER_ZIP="/layers/layer.zip"
ENDPOINT="http://localstack:4566"
REGION="us-east-1"
ROLE_ARN="arn:aws:iam::000000000000:role/lambda-ocr-role"

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=$REGION

# Shorthand
awsl() { aws --endpoint-url="$ENDPOINT" --region "$REGION" "$@"; }

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  OCR Lambda Deployer                             ║"
echo "╚══════════════════════════════════════════════════╝"

# ── 1. Wait for layer.zip from the builder ──
echo "→ [1/7] Waiting for Tesseract layer zip..."
for i in $(seq 1 120); do
    [ -f "$LAYER_ZIP" ] && break
    [ "$i" -eq 120 ] && { echo "✗ layer.zip not found after 120s"; exit 1; }
    sleep 1
done
echo "  ✓ Found: $(du -sh $LAYER_ZIP | cut -f1)"

# ── 2. Build function zip ──
echo "→ [2/7] Building function zip..."
mkdir -p /tmp/fn-pkg
pip install --quiet --no-cache-dir -t /tmp/fn-pkg \
    PyPDF2==3.0.1 \
    pytesseract==0.3.10 \
    Pillow==10.3.0 \
    pdf2image==1.17.0
cp /src/handler.py /tmp/fn-pkg/
cd /tmp/fn-pkg
zip -r9 /tmp/function.zip . > /dev/null 2>&1
echo "  ✓ Function zip: $(du -sh /tmp/function.zip | cut -f1)"

# ── 3. Wait for LocalStack Lambda service ──
echo "→ [3/7] Waiting for LocalStack Lambda service..."
for i in $(seq 1 60); do
    HEALTH=$(curl -sf "$ENDPOINT/_localstack/health" 2>/dev/null || echo "{}")
    STATUS=$(echo "$HEALTH" | python3 -c "
import sys,json
try: print(json.load(sys.stdin).get('services',{}).get('lambda','unavailable'))
except: print('unavailable')
" 2>/dev/null)
    if [ "$STATUS" = "running" ] || [ "$STATUS" = "available" ]; then
        echo "  ✓ Lambda service: $STATUS"
        break
    fi
    echo "  ... lambda service=$STATUS (attempt $i/60)"
    [ "$i" -eq 60 ] && { echo "⚠ Timeout but continuing..."; }
    sleep 2
done

# ── 4. Create IAM role ──
echo "→ [4/7] Creating IAM role..."
awsl iam create-role \
    --role-name lambda-ocr-role \
    --assume-role-policy-document '{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }' > /dev/null 2>&1 || echo "  (exists)"

# ── 5. Publish Lambda Layer ──
echo "→ [5/7] Publishing Lambda Layer '${LAYER_NAME}'..."
LAYER_RESULT=$(awsl lambda publish-layer-version \
    --layer-name "$LAYER_NAME" \
    --description "Tesseract OCR + Poppler binaries for Amazon Linux 2023" \
    --zip-file "fileb://${LAYER_ZIP}" \
    --compatible-runtimes python3.11 \
    --output json)

LAYER_ARN=$(echo "$LAYER_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['LayerVersionArn'])")
echo "  ✓ Layer ARN: ${LAYER_ARN}"

# ── 6. Deploy Lambda function ──
echo "→ [6/7] Deploying Lambda function '${FUNCTION_NAME}'..."

# Clean up any old version
awsl lambda delete-function --function-name "$FUNCTION_NAME" 2>/dev/null || true
sleep 2

awsl lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --runtime python3.11 \
    --role "$ROLE_ARN" \
    --handler handler.handler \
    --zip-file fileb:///tmp/function.zip \
    --timeout 120 \
    --memory-size 1024 \
    --layers "$LAYER_ARN" \
    --environment "Variables={TESSDATA_PREFIX=/opt/share/tessdata,PATH=/opt/bin:/var/lang/bin:/usr/local/bin:/usr/bin:/bin,LD_LIBRARY_PATH=/opt/lib:/var/lang/lib:/lib64:/usr/lib64}" \
    --output json | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f\"  FunctionName: {d.get('FunctionName')}\")
print(f\"  State:        {d.get('State','N/A')}\")
print(f\"  Layers:       {[l['Arn'] for l in d.get('Layers',[])]}\")
"

# ── 7. Wait for Active ──
echo "→ [7/7] Waiting for Active state..."
for i in $(seq 1 90); do
    STATE=$(awsl lambda get-function \
        --function-name "$FUNCTION_NAME" \
        --query 'Configuration.State' \
        --output text 2>/dev/null || echo "NOT_FOUND")

    if [ "$STATE" = "Active" ]; then
        echo "  ✓ Function is Active!"
        break
    fi
    if [ "$STATE" = "Failed" ]; then
        REASON=$(awsl lambda get-function \
            --function-name "$FUNCTION_NAME" \
            --query 'Configuration.StateReasonCode' \
            --output text 2>/dev/null || echo "unknown")
        echo "  ✗ FAILED: $REASON"
        exit 1
    fi
    echo "  State=$STATE (attempt $i/90)"
    [ "$i" -eq 90 ] && { echo "✗ Timed out"; exit 1; }
    sleep 2
done

# ── List all resources ──
echo ""
echo "→ Functions:"
awsl lambda list-functions \
    --query 'Functions[].{Name:FunctionName,State:State,Runtime:Runtime}' \
    --output table 2>/dev/null || \
awsl lambda list-functions --output json

echo ""
echo "→ Layers:"
awsl lambda list-layers --output table 2>/dev/null || \
awsl lambda list-layers --output json

# ── Test invocation ──
echo ""
echo "→ Test invocation (small PNG payload)..."
INVOKE_RESULT=$(awsl lambda invoke \
    --function-name "$FUNCTION_NAME" \
    --payload '{"file_data":"dGVzdA==","file_type":"png","file_name":"test.png"}' \
    --cli-binary-format raw-in-base64-out \
    /tmp/test-out.json 2>&1) || true
echo "  $INVOKE_RESULT"
echo "  Response: $(cat /tmp/test-out.json 2>/dev/null | head -c 300)"

echo ""
echo "════════════════════════════════════════════════════"
echo "  ✓ OCR Stack Ready!"
echo ""
echo "  Frontend:   http://localhost:8080"
echo "  Backend:    http://localhost:5000/api/health"
echo "  LocalStack: http://localhost:4566"
echo "════════════════════════════════════════════════════"
