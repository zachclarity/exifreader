#!/bin/bash
# ─────────────────────────────────────────────────────────
#  LocalStack ready.d init script
#  Deploys the pre-built Lambda zip from the builder volume
# ─────────────────────────────────────────────────────────
set -euo pipefail

FUNCTION_NAME="ocr-extract"
ZIP_PATH="/opt/lambda-zip/lambda.zip"
ROLE_ARN="arn:aws:iam::000000000000:role/lambda-ocr-role"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  Deploying OCR Lambda function...            ║"
echo "╚══════════════════════════════════════════════╝"

# ── Wait for zip ──
echo "→ Waiting for Lambda zip..."
for i in $(seq 1 60); do
    [ -f "${ZIP_PATH}" ] && break
    sleep 1
done

if [ ! -f "${ZIP_PATH}" ]; then
    echo "✗ FATAL: ${ZIP_PATH} not found after 60s"
    exit 1
fi
echo "  ✓ Found zip: $(ls -lh ${ZIP_PATH} | awk '{print $5}')"

# ── Verify Tesseract (pre-installed in custom image) ──
echo "→ Tesseract: $(tesseract --version 2>&1 | head -1)"
echo "→ pdftoppm:  $(pdftoppm -v 2>&1 | head -1 || echo 'installed')"

# ── Create IAM role ──
echo "→ Creating IAM role..."
awslocal iam create-role \
    --role-name lambda-ocr-role \
    --assume-role-policy-document '{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }' 2>/dev/null || echo "  (role exists)"

# ── Delete old function if exists ──
awslocal lambda delete-function \
    --function-name "${FUNCTION_NAME}" 2>/dev/null || true

# ── Create Lambda ──
echo "→ Creating Lambda '${FUNCTION_NAME}'..."
awslocal lambda create-function \
    --function-name "${FUNCTION_NAME}" \
    --runtime python3.11 \
    --role "${ROLE_ARN}" \
    --handler handler.handler \
    --zip-file "fileb://${ZIP_PATH}" \
    --timeout 120 \
    --memory-size 1024

echo ""
echo "→ Verifying..."
awslocal lambda list-functions \
    --query 'Functions[].{Name:FunctionName,Runtime:Runtime,State:State}' \
    --output table

echo ""
echo "════════════════════════════════════════════════"
echo "  ✓ OCR Stack Ready!"
echo "  Frontend:   http://localhost:8080"
echo "  Backend:    http://localhost:5000/api/health"
echo "  LocalStack: http://localhost:4566"
echo "════════════════════════════════════════════════"
