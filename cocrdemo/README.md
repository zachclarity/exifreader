# LocalStack OCR Ultimate (Docker-only)

## Features added
- **Real Tesseract OCR** via Java 21 Lambda container image (`lambda-image/`)
- **S3 pipeline before OCR**: Lambda stores uploaded bytes into S3 and returns `s3Bucket/s3Key`
- **Verification test images**: `test-images/*.png`
- **OCR accuracy benchmarking** (CER/WER + timings): `docker compose --profile bench up benchmark`
- **LocalStack image-lambda quirks handled**: init script *tries image lambda first* then auto-falls back to ZIP if unsupported.

## Quick start
```bash
docker compose up --build
```
Open:
- Frontend: http://localhost:8080
- LocalStack: http://localhost:4566

## Benchmark
```bash
docker compose --profile bench up --build benchmark
```

## About LocalStack container image Lambdas
LocalStack’s official docs indicate container-image Lambda via ECR is a Pro feature in some setups.
If your LocalStack build doesn’t support image Lambdas, this project automatically falls back to ZIP mode.
You can also force ZIP mode by setting `USE_IMAGE_LAMBDA=0` in `docker-compose.yml`.

## Cold start tips
- Increase memory for faster Java startup (image mode uses 2048MB; zip uses 1024MB).
- `JAVA_TOOL_OPTIONS` is set for quicker startup: TieredStopAtLevel=1 + SerialGC.
