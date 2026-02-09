#!/bin/bash
# Deploy the OCR Lambda function using container image (Lambda v2)

echo "=== [init] Deploying OCR Lambda (container image) ==="

FUNCTION_NAME="ocr-extract-text"
IMAGE_URI="ocr-lambda:latest"
MAX_RETRIES=5

# Check if already exists
existing=$(awslocal lambda get-function --function-name "$FUNCTION_NAME" 2>&1)
if echo "$existing" | grep -q '"FunctionName"'; then
    echo "=== [init] Lambda '$FUNCTION_NAME' already exists, skipping ==="
    exit 0
fi

# Create function using container image
for i in $(seq 1 $MAX_RETRIES); do
    echo "=== [init] Attempt $i/$MAX_RETRIES ==="

    result=$(awslocal lambda create-function \
        --function-name "$FUNCTION_NAME" \
        --package-type Image \
        --code "ImageUri=$IMAGE_URI" \
        --role arn:aws:iam::000000000000:role/lambda-role \
        --timeout 60 \
        --memory-size 512 2>&1)

    if echo "$result" | grep -q '"FunctionName"'; then
        echo "=== [init] Lambda created successfully ==="

        # Wait for Active state
        for j in $(seq 1 15); do
            state=$(awslocal lambda get-function --function-name "$FUNCTION_NAME" 2>&1 | grep -o '"State": "[^"]*"' | head -1)
            echo "=== [init] State: $state ==="
            if echo "$state" | grep -q "Active"; then
                break
            fi
            sleep 3
        done

        # Smoke test
        echo "=== [init] Smoke test ==="
        awslocal lambda invoke \
            --function-name "$FUNCTION_NAME" \
            --payload '{"image_b64":"","image_ext":"png","image_name":"test"}' \
            /tmp/lambda_smoke.json 2>&1 || true
        cat /tmp/lambda_smoke.json 2>/dev/null
        echo ""
        echo "=== [init] Done ==="
        exit 0
    fi

    if echo "$result" | grep -q "ResourceConflictException\|already exist"; then
        echo "=== [init] Function already exists (race condition), done ==="
        exit 0
    fi

    echo "=== [init] Failed: $result ==="
    sleep 5
done

echo "=== [init] All retries exhausted — backend will auto-deploy ==="
exit 0
