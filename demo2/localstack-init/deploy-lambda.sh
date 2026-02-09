#!/bin/bash
# ─────────────────────────────────────────────────────────
#  LocalStack init script — packages and deploys the Lambda
#  This runs automatically when LocalStack becomes healthy.
# ─────────────────────────────────────────────────────────

set -euo pipefail

FUNCTION_NAME="ocr-extract"
LAMBDA_SRC="/opt/lambda-src"
REGION="us-east-1"
ENDPOINT="http://localhost:4566"

echo "╔══════════════════════════════════════════════╗"
echo "║  Deploying OCR Lambda function...            ║"
echo "╚══════════════════════════════════════════════╝"

# ── Install build dependencies inside LocalStack ──
echo "→ Installing pip packages for Lambda..."
cd /tmp
mkdir -p lambda-package
cd lambda-package

# Copy handler
cp "${LAMBDA_SRC}/handler.py" .

# Install Python deps locally
pip install --quiet --target . \
    PyPDF2==3.0.1 \
    pytesseract==0.3.10 \
    Pillow==10.3.0 \
    pdf2image==1.17.0 2>/dev/null || true

# Create deployment zip
echo "→ Creating deployment zip..."
zip -r9 /tmp/lambda.zip . > /dev/null 2>&1

echo "→ Lambda package size: $(du -sh /tmp/lambda.zip | cut -f1)"

# ── Create IAM role ──
echo "→ Creating IAM execution role..."
awslocal iam create-role \
    --role-name lambda-ocr-role \
    --assume-role-policy-document '{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }' > /dev/null 2>&1 || true

# ── Deploy Lambda ──
echo "→ Creating Lambda function '${FUNCTION_NAME}'..."
awslocal lambda create-function \
    --function-name "${FUNCTION_NAME}" \
    --runtime python3.11 \
    --role arn:aws:iam::000000000000:role/lambda-ocr-role \
    --handler handler.handler \
    --zip-file fileb:///tmp/lambda.zip \
    --timeout 120 \
    --memory-size 1024 \
    --environment "Variables={TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata}" \
    2>/dev/null || {
        echo "→ Function exists, updating code..."
        awslocal lambda update-function-code \
            --function-name "${FUNCTION_NAME}" \
            --zip-file fileb:///tmp/lambda.zip > /dev/null 2>&1
    }

# ── Verify ──
echo "→ Verifying deployment..."
awslocal lambda get-function --function-name "${FUNCTION_NAME}" | grep -q "${FUNCTION_NAME}" && \
    echo "✓ Lambda '${FUNCTION_NAME}' deployed successfully!" || \
    echo "✗ Deployment verification failed"

# ── Warm up the function ──
echo "→ Warming up Lambda..."
awslocal lambda invoke \
    --function-name "${FUNCTION_NAME}" \
    --payload '{"file_data":"dGVzdA==","file_type":"png","file_name":"warmup.png"}' \
    /tmp/warmup-response.json > /dev/null 2>&1 || true

echo "════════════════════════════════════════════════"
echo "  ✓ OCR Stack Ready!"
echo "  Frontend:   http://localhost:8080"
echo "  Backend:    http://localhost:5000/api/health"
echo "  LocalStack: http://localhost:4566"
echo "════════════════════════════════════════════════"
