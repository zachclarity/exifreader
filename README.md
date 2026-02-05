# PDF Metadata & Image Extractor

Upload PDFs to extract standard metadata, custom JSON classification fields, and all embedded images.

## Project Structure (all files in one folder)

```
exifreader/
  app.py              ← Flask backend
  requirements.txt    ← Python dependencies
  Dockerfile          ← Backend container image
  docker-compose.yml  ← Orchestration
  nginx.conf          ← Reverse proxy config
  index.html          ← Frontend UI
  .dockerignore       ← Keeps build context small
  create_samples.py   ← Generate test PDFs (optional)
  samples/            ← Sample PDFs with images (optional)
```

## Quick Start (Windows / Mac / Linux)

```bash
cd exifreader
docker-compose up -d --build
```

Then open **http://localhost:8080**

To stop:

```bash
docker-compose down
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/extract` | Upload PDF, returns metadata + images |
| GET | `/api/images/:jobId/:file` | Serve single extracted image |
| GET | `/api/images/:jobId/download-all` | Download all images as .zip |
| GET | `/api/health` | Health check |

## Features

- Drag & drop PDF upload with progress bar
- Standard metadata extraction (title, author, dates, page count, etc.)
- Custom JSON fields from `/CustomFields` metadata key
  - Nested objects, arrays, booleans
  - Classification banners + sensitivity badges
  - Raw JSON toggle
- Image extraction via PyMuPDF
  - Thumbnail grid with page, dimensions, size
  - Click-to-open lightbox
  - Per-image download
  - Download All as .zip
  - Images saved to `/data/extracted/<jobId>/images/`

## Generate Sample PDFs

```bash
pip install pypdf reportlab Pillow PyMuPDF
python create_samples.py
```

## Tech Stack

- **Frontend:** HTML5, Tailwind CSS, vanilla JS
- **Backend:** Python 3.12, Flask, PyMuPDF, Gunicorn
- **Proxy:** Nginx Alpine
- **Container:** Docker Compose
