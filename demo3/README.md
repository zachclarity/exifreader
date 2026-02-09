# LocalStack File Upload (Lambda Function URL + S3 presign)

## Run
```bash
docker compose up -d
```

Open:
- http://localhost:8080

LocalStack edge:
- http://localhost:4566

## What happens
1) LocalStack init script creates S3 bucket `uploads`
2) Creates Lambda `presign-upload`
3) Creates Lambda Function URL (no auth) and writes it into `web/config.json`
4) Browser calls the Function URL to get a presigned PUT URL
5) Browser uploads the file directly to S3 in LocalStack

## Verify upload (optional)
```bash
docker exec -it $(docker ps -qf name=localstack) awslocal s3 ls s3://uploads
```

## Notes
- If your environment prevents the init script from writing `web/config.json`, just copy the FunctionUrl printed in logs:
```bash
docker logs -f $(docker ps -qf name=localstack) | grep "Function URL"
```
Then paste it into `web/config.json` and refresh the page.
