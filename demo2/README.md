# 🔍 OCR Extract — PDF & Image Text Extraction Stack

A fully containerized text extraction pipeline using **Docker Compose**, **LocalStack Lambda**, and **Tesseract OCR**.

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌──────────────────────────┐
│   Frontend   │─────▶│  Backend API │─────▶│   LocalStack Lambda      │
│  Nginx +     │ POST │  Flask +     │invoke│  Python 3.11 +           │
│  Tailwind    │◀─────│  Gunicorn    │◀─────│  PyPDF2 + Tesseract OCR  │
│  :8080       │ JSON │  :5000       │      │  :4566                   │
└─────────────┘      └──────────────┘      └──────────────────────────┘
```

**Upload flow:**
1. User drops a PDF / TIFF / PNG / JPG onto the web form
2. Frontend `POST`s to `/api/extract` (proxied through Nginx)
3. Flask backend base64-encodes the file and invokes the Lambda
4. Lambda function:
   - **PDF with selectable text** → PyPDF2 native extraction
   - **Scanned PDF (image-only)** → pdf2image → Tesseract OCR per page
   - **TIFF / PNG / JPG** → Pillow + Tesseract OCR (multi-frame TIFF supported)
5. Extracted text + page count + processing time returned to the UI

## Prerequisites

- **Docker** ≥ 20.10
- **Docker Compose** ≥ 2.0

## Quick Start

```bash
# Clone and start
cd ocr-extract
docker compose up --build

# Wait for the "✓ OCR Stack Ready!" message in the logs
# Then open → http://localhost:8080
```

## Services

| Service      | Port   | Description                          |
|-------------|--------|--------------------------------------|
| `frontend`  | `8080` | Nginx serving HTML + Tailwind CSS    |
| `backend`   | `5000` | Flask API (upload → Lambda invoke)   |
| `localstack`| `4566` | LocalStack (Lambda, S3, IAM)         |

## Supported File Types

| Type | Extension       | Method                          |
|------|-----------------|---------------------------------|
| PDF  | `.pdf`          | PyPDF2 native → fallback to OCR |
| TIFF | `.tiff`, `.tif` | Tesseract OCR (multi-frame)     |
| PNG  | `.png`          | Tesseract OCR                   |
| JPEG | `.jpg`, `.jpeg` | Tesseract OCR                   |

## API Reference

### `POST /api/extract`
Upload a file for text extraction.

**Request:** `multipart/form-data` with a `file` field.

**Response:**
```json
{
  "text": "Extracted text content...",
  "pages": 3,
  "processing_time_ms": 1842
}
```

### `GET /api/health`
Health check endpoint.

## Configuration

Edit `.env` or set environment variables:

| Variable              | Default             | Description               |
|----------------------|---------------------|---------------------------|
| `AWS_DEFAULT_REGION` | `us-east-1`        | AWS region for LocalStack |
| `LAMBDA_FUNCTION_NAME` | `ocr-extract`    | Lambda function name      |

## Troubleshooting

**Lambda not deploying?**
Check LocalStack logs: `docker compose logs localstack`

**OCR returning empty text?**
Ensure the uploaded image has readable text. Very low-resolution images may produce poor results.

**Timeout on large files?**
The Lambda has a 120s timeout. For very large PDFs (50+ pages), consider splitting them first.

## Stopping

```bash
docker compose down -v   # -v removes volumes too
```
