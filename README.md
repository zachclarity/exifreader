# PDF Metadata Extractor

A simple web app to upload PDFs and extract their metadata/EXIF information.

## Features

- Drag & drop or click to upload PDF files
- Extracts metadata including: Title, Author, Subject, Keywords, Creator, Producer, Creation Date, Modification Date, PDF Version, Page Count, File Size

## Quick Start

```bash
# Start the application
docker-compose up -d

# Open in browser
open http://localhost:8080

# Stop the application
docker-compose down
```

## Tech Stack

- HTML5 + Tailwind CSS
- PDF.js for metadata extraction
- Nginx (Alpine) for serving
- Docker Compose for orchestration
