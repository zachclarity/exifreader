#!/usr/bin/env bash
set -euo pipefail

export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"

BUCKET_NAME="${OCR_BUCKET:-ocr-images}"
FUNCTION_NAME="ocr-lambda"
HANDLER="com.zactonics.ocr.OcrHandler::handleRequest"
ZIP_RUNTIME="java21"
ZIP_JAR_PATH="/opt/build-out/ocr-lambda-zip.jar"
USE_IMAGE="${USE_IMAGE_LAMBDA:-1}"
LOCAL_IMAGE_NAME="localstack-ocr-tesseract:latest"

echo "[init] Creating S3 bucket: ${BUCKET_NAME}"
awslocal s3api create-bucket --bucket "${BUCKET_NAME}" >/dev/null 2>&1 || true

deploy_zip() {
  echo "[init] Deploying ZIP Lambda fallback: ${FUNCTION_NAME}"
  for i in {1..90}; do
    [ -f "${ZIP_JAR_PATH}" ] && break
    sleep 2
  done
  if [ ! -f "${ZIP_JAR_PATH}" ]; then
    echo "[init] ERROR: ZIP JAR not found: ${ZIP_JAR_PATH}"
    exit 1
  fi

  awslocal lambda delete-function --function-name "${FUNCTION_NAME}" >/dev/null 2>&1 || true

  awslocal lambda create-function     --function-name "${FUNCTION_NAME}"     --runtime "${ZIP_RUNTIME}"     --handler "${HANDLER}"     --role "arn:aws:iam::000000000000:role/lambda-role"     --timeout 30     --memory-size 1024     --environment "Variables={OCR_BUCKET=${BUCKET_NAME},LOCALSTACK_ENDPOINT=http://localstack:4566,REAL_OCR=false}"     --zip-file "fileb://${ZIP_JAR_PATH}" >/dev/null
}

deploy_image_if_possible() {
  echo "[init] Attempting IMAGE Lambda (requires LocalStack support; ECR may be Pro-tier per docs)."
  # This tries to create a package-type Image function referencing a local docker image name.
  # If your LocalStack doesn't support image-based Lambdas, this will fail and we will fallback.
  set +e
  awslocal lambda delete-function --function-name "${FUNCTION_NAME}" >/dev/null 2>&1 || true
  awslocal lambda create-function     --function-name "${FUNCTION_NAME}"     --package-type Image     --code ImageUri="${LOCAL_IMAGE_NAME}"     --role "arn:aws:iam::000000000000:role/lambda-role"     --timeout 30     --memory-size 2048 >/tmp/create_image_lambda.out 2>&1
  local rc=$?
  set -e
  if [ $rc -ne 0 ]; then
    echo "[init] IMAGE Lambda create failed; falling back to ZIP."
    cat /tmp/create_image_lambda.out || true
    return 1
  fi
  echo "[init] IMAGE Lambda created."
  return 0
}

if [ "${USE_IMAGE}" = "1" ]; then
  if ! deploy_image_if_possible; then
    deploy_zip
  fi
else
  deploy_zip
fi

echo "[init] Creating Function URL (Auth: NONE) with CORS"
awslocal lambda delete-function-url-config --function-name "${FUNCTION_NAME}" >/dev/null 2>&1 || true

awslocal lambda create-function-url-config   --function-name "${FUNCTION_NAME}"   --auth-type NONE   --cors '{"AllowOrigins":["*"],"AllowMethods":["POST","OPTIONS"],"AllowHeaders":["*"],"MaxAge":86400}' >/dev/null

echo "[init] ✅ Ready. Frontend calls: http://localhost:4566/lambda-url/${FUNCTION_NAME}/"
