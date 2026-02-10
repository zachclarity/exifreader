# OCR Extract — Image & PDF OCR Service

## Quick Start

```bash
cd ocr-app
docker compose up --build
```

Open **http://localhost:8080** — ready in ~10 seconds.

## Architecture

```
                    ┌──────────────────────────────────┐
                    │       Lambda Service :9000        │
  Browser ──nginx──▶│                                  │
                    │  /api/ocr ──▶ ocr-service        │
                    │               Image → Tesseract   │
                    │                                  │
                    │  /api/pdf-ocr ──▶ pdf-ocr        │
                    │               PDF → Extract Images│
                    │                   → Tesseract OCR │
                    └──────────────────────────────────┘

PDF Pipeline: PDF → PyMuPDF renders pages as images → Tesseract OCR per image → Text
```

## Services

| Endpoint | Function | Pipeline |
|----------|----------|----------|
| `/api/ocr` | `ocr-service` | Image → Tesseract → Text |
| `/api/pdf-ocr` | `pdf-ocr` | PDF → Extract Images → Tesseract → Text |
| `/api/pdf` | `pdf-extract` | PDF → Direct text extraction (no OCR) |

## Timing Tracked

- **Round-trip**: Client-side total (network + processing)
- **Pipeline**: Server-side total
- **Image Extract**: Time to render PDF pages as images (per page)
- **OCR**: Tesseract processing time (per page)
- **Per-page breakdown**: Individual extract + OCR times

## CLI Client

```bash
pip install requests

python ocr_client.py image.png              # Image OCR
python ocr_client.py document.pdf           # PDF → Image → OCR
python ocr_client.py *.png *.pdf -o out.csv # Batch to CSV
```
