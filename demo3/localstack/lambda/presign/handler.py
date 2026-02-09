import json
import os
import time
import boto3

REGION = os.getenv("AWS_REGION", "us-east-1")
ENDPOINT = os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566")
BUCKET = os.getenv("UPLOAD_BUCKET", "uploads")

s3 = boto3.client(
    "s3",
    region_name=REGION,
    endpoint_url=ENDPOINT,
    aws_access_key_id="test",
    aws_secret_access_key="test",
)

def _resp(status, body):
    return {
        "statusCode": status,
        "headers": {
            "content-type": "application/json",
            "access-control-allow-origin": "*",
            "access-control-allow-methods": "GET,POST,OPTIONS",
            "access-control-allow-headers": "content-type",
        },
        "body": json.dumps(body),
    }

def handler(event, context):
    # Function URL uses event["requestContext"]["http"]["method"] for HTTP method
    method = (event.get("requestContext", {}).get("http", {}) or {}).get("method", "")
    if method == "OPTIONS":
        return _resp(200, {"ok": True})

    try:
        raw_body = event.get("body") or "{}"
        if event.get("isBase64Encoded"):
            import base64
            raw_body = base64.b64decode(raw_body).decode("utf-8")

        data = json.loads(raw_body)
        filename = (data.get("filename") or "upload.bin").strip()
        content_type = (data.get("contentType") or "application/octet-stream").strip()

        key = f"{int(time.time())}-{filename}"

        url = s3.generate_presigned_url(
            ClientMethod="put_object",
            Params={"Bucket": BUCKET, "Key": key, "ContentType": content_type},
            ExpiresIn=300,
        )

        return _resp(200, {"uploadUrl": url, "bucket": BUCKET, "key": key})
    except Exception as e:
        return _resp(500, {"error": str(e)})
