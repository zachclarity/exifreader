#!/usr/bin/env sh
set -eu

echo "[bootstrap] creating bucket..."
awslocal s3 mb s3://uploads >/dev/null 2>&1 || true

echo "[bootstrap] building lambda zip (python zipfile)..."
python3 - <<'PY'
import zipfile, os
src = "/opt/lambda/presign/handler.py"
out = "/tmp/presign.zip"
with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
    z.write(src, arcname="handler.py")
print("Wrote", out)
PY

echo "[bootstrap] (re)creating lambda..."
awslocal lambda delete-function --function-name presign-upload >/dev/null 2>&1 || true

awslocal lambda create-function   --function-name presign-upload   --runtime python3.11   --handler handler.handler   --zip-file fileb:///tmp/presign.zip   --role arn:aws:iam::000000000000:role/lambda-role   --environment "Variables={LOCALSTACK_ENDPOINT=http://localstack:4566,UPLOAD_BUCKET=uploads}"   >/dev/null

echo "[bootstrap] creating function url (CORS enabled)..."
awslocal lambda create-function-url-config   --function-name presign-upload   --auth-type NONE   --cors "AllowOrigins=*,AllowMethods=POST,AllowHeaders=content-type"   >/dev/null

FUNCTION_URL="$(awslocal lambda get-function-url-config --function-name presign-upload --query 'FunctionUrl' --output text)"
echo "[bootstrap] Function URL: $FUNCTION_URL"

echo "[bootstrap] writing /web/config.json for frontend..."
cat > /web/config.json <<EOF
{
  "functionUrl": "${FUNCTION_URL}"
}
EOF

echo "[bootstrap] done."
