# 🔍 OCR Extract — PDF & Image Text Extraction

Fully containerized OCR pipeline using **LocalStack Community Edition** (no Pro features).

## Architecture

```
  ┌───────────┐   POST    ┌──────────┐   invoke   ┌──────────────────────────┐
  │  Frontend  │─────────▶│ Backend  │──────────▶│  LocalStack Lambda       │
  │  Nginx +   │◀─────────│ Flask    │◀──────────│  python3.11 container    │
  │  Tailwind  │   JSON   │ :5000    │           │  + Tesseract Layer /opt  │
  │  :8080     │          └──────────┘           └──────────────────────────┘
  └───────────┘                                     ▲
                                                    │ Layer provides:
                                              /opt/bin/tesseract
                                              /opt/bin/pdftoppm
                                              /opt/lib/*.so
                                              /opt/share/tessdata/
```

## Why Lambda Layer (not custom image)?

`LAMBDA_RUNTIME_IMAGE_MAPPING` is a **LocalStack Pro** feature.
In Community edition, Lambda runs in stock AWS runtime containers.

Our solution: a **Lambda Layer** built on Amazon Linux 2023 (same OS as
the python3.11 runtime) containing Tesseract + Poppler binaries.
The layer extracts to `/opt` in the Lambda container, and the handler
configures `PATH`, `LD_LIBRARY_PATH`, and `TESSDATA_PREFIX` to use them.

## Startup Order

```
1. layer-builder   → amazonlinux:2023 builds Tesseract layer zip
2. localstack      → starts with Docker socket mounted
3. deployer        → publishes layer, creates function, waits for Active
4. backend         → Flask API (starts only after Active confirmed)
5. frontend        → Nginx serves the upload form
```

## Quick Start

```bash
cd project
docker compose up --build
# Wait for "✓ OCR Stack Ready!" in the logs
# Open → http://localhost:8080
```

## Verify

```bash
chmod +x verify.sh && ./verify.sh
```

Checks: LocalStack health, Lambda state, layers, backend, frontend.

## Supported Files

| Type | Extensions       | Method                          |
|------|------------------|---------------------------------|
| PDF  | `.pdf`           | PyPDF2 native → fallback OCR    |
| TIFF | `.tiff`, `.tif`  | Tesseract OCR (multi-frame)     |
| PNG  | `.png`           | Tesseract OCR                   |
| JPEG | `.jpg`, `.jpeg`  | Tesseract OCR                   |

## Troubleshooting

### Check function state
```bash
aws --endpoint-url=http://localhost:4566 lambda get-function \
    --function-name ocr-extract \
    --query 'Configuration.{State:State,Layers:Layers}'
```

### Check deployer logs
```bash
docker compose logs deployer
```

### Check Lambda invocation errors
```bash
docker compose logs localstack 2>&1 | grep -i error | tail -20
```

### First invocation slow?
Normal — LocalStack pulls/starts a Lambda container on first call (~10-30s).
Subsequent calls reuse the warm container.

## Cleanup

```bash
docker compose down -v
```
