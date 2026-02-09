
import json, os, time, boto3

REGION=os.getenv("AWS_REGION","us-east-1")
ENDPOINT=os.getenv("LOCALSTACK_ENDPOINT","http://localhost:4566")
BUCKET=os.getenv("UPLOAD_BUCKET","uploads")

s3=boto3.client("s3",
    region_name=REGION,
    endpoint_url=ENDPOINT,
    aws_access_key_id="test",
    aws_secret_access_key="test"
)

def resp(code, body):
    return {
        "statusCode": code,
        "headers": {
            "content-type":"application/json",
            "access-control-allow-origin":"*",
            "access-control-allow-methods":"GET,POST,OPTIONS",
            "access-control-allow-headers":"*"
        },
        "body": json.dumps(body)
    }

def handler(event, context):
    method=(event.get("requestContext",{}).get("http",{}) or {}).get("method","")
    if method=="OPTIONS":
        return resp(200,{"ok":True})

    data=json.loads(event.get("body") or "{}")
    filename=data.get("filename","upload.bin")
    ctype=data.get("contentType","application/octet-stream")

    key=f"{int(time.time())}-{filename}"

    url=s3.generate_presigned_url(
        "put_object",
        Params={"Bucket":BUCKET,"Key":key,"ContentType":ctype},
        ExpiresIn=300
    )

    return resp(200,{"uploadUrl":url,"bucket":BUCKET,"key":key})
