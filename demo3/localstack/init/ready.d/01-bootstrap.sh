
#!/usr/bin/env sh
set -eu

echo "[bootstrap] create bucket"
awslocal s3 mb s3://uploads || true

echo "[bootstrap] set S3 CORS policy"
awslocal s3api put-bucket-cors --bucket uploads --cors-configuration '{
 "CORSRules":[{
   "AllowedOrigins":["*"],
   "AllowedMethods":["GET","PUT","POST","HEAD"],
   "AllowedHeaders":["*"],
   "ExposeHeaders":["ETag"]
 }]
}'

echo "[bootstrap] build lambda zip"
python3 - <<'PY'
import zipfile
z=zipfile.ZipFile("/tmp/lambda.zip","w")
z.write("/opt/lambda/presign/handler.py","handler.py")
z.close()
PY

awslocal lambda delete-function --function-name presign-upload >/dev/null 2>&1 || true

awslocal lambda create-function   --function-name presign-upload   --runtime python3.11   --handler handler.handler   --zip-file fileb:///tmp/lambda.zip   --role arn:aws:iam::000000000000:role/lambda-role   --environment "Variables={LOCALSTACK_ENDPOINT=http://localstack:4566,UPLOAD_BUCKET=uploads}"

echo "[bootstrap] create function URL with CORS"
awslocal lambda create-function-url-config   --function-name presign-upload   --auth-type NONE   --cors "AllowOrigins=*,AllowMethods=GET,POST,OPTIONS,PUT,AllowHeaders=*"

URL=$(awslocal lambda get-function-url-config --function-name presign-upload --query FunctionUrl --output text)

echo "{ \"functionUrl\": \"$URL\" }" > /web/config.json

echo "[bootstrap complete]"
