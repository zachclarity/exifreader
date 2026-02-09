"""
Lambda function — extracts text from PDFs and images.

PDF workflow:
  1. Try native text extraction via PyPDF2.
  2. If the PDF is scanned (no selectable text), convert to images
     with pdf2image and run Tesseract OCR on each page.

Image workflow (TIFF, PNG, JPG):
  Run Tesseract OCR directly on the image.

Returns JSON with extracted text, page count, and processing time.
"""

import os
import json
import time
import base64
import tempfile
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    t0 = time.perf_counter()

    try:
        file_data = base64.b64decode(event["file_data"])
        file_type = event.get("file_type", "pdf").lower()
        file_name = event.get("file_name", "upload")

        logger.info("Processing %s (%s, %d bytes)", file_name, file_type, len(file_data))

        if file_type == "pdf":
            text, pages = extract_from_pdf(file_data)
        elif file_type in ("tiff", "tif", "png", "jpg", "jpeg"):
            text = extract_from_image(file_data)
            pages = 1
        else:
            return _response(400, error=f"Unsupported file type: {file_type}")

        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        logger.info("Extraction done: %d chars, %d pages, %d ms", len(text), pages, elapsed_ms)

        return _response(200, text=text.strip(), pages=pages, processing_time_ms=elapsed_ms)

    except Exception as exc:
        logger.exception("Extraction failed")
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        return _response(500, error=str(exc), processing_time_ms=elapsed_ms)


# ── PDF Extraction ──────────────────────────────────────

def extract_from_pdf(file_data: bytes) -> tuple[str, int]:
    """Try native text first; fall back to OCR for scanned pages."""
    import PyPDF2
    import io

    reader = PyPDF2.PdfReader(io.BytesIO(file_data))
    pages = len(reader.pages)
    text_parts = []

    # Pass 1: native text extraction
    for page in reader.pages:
        page_text = page.extract_text() or ""
        text_parts.append(page_text)

    combined = "\n\n".join(text_parts)

    # If we got meaningful text, return it
    if combined.strip() and len(combined.strip()) > 20:
        return combined, pages

    # Pass 2: scanned PDF → OCR via Tesseract
    logger.info("Native text empty/short — falling back to OCR for %d pages", pages)
    return ocr_pdf_pages(file_data), pages


def ocr_pdf_pages(file_data: bytes) -> str:
    """Convert each PDF page to an image, then OCR with Tesseract."""
    from pdf2image import convert_from_bytes
    import pytesseract

    images = convert_from_bytes(file_data, dpi=300)
    text_parts = []

    for i, img in enumerate(images):
        logger.info("OCR page %d/%d", i + 1, len(images))
        page_text = pytesseract.image_to_string(img, lang="eng")
        text_parts.append(f"--- Page {i + 1} ---\n{page_text}")

    return "\n\n".join(text_parts)


# ── Image Extraction (TIFF, PNG, JPG) ──────────────────

def extract_from_image(file_data: bytes) -> str:
    """Run Tesseract OCR on a single image file."""
    import pytesseract
    from PIL import Image
    import io

    img = Image.open(io.BytesIO(file_data))

    # Handle multi-frame TIFF
    frames = []
    try:
        while True:
            frames.append(img.copy())
            img.seek(img.tell() + 1)
    except EOFError:
        pass

    if not frames:
        frames = [img]

    text_parts = []
    for i, frame in enumerate(frames):
        # Convert to RGB if necessary (e.g., CMYK TIFF)
        if frame.mode not in ("RGB", "L"):
            frame = frame.convert("RGB")
        page_text = pytesseract.image_to_string(frame, lang="eng")
        if len(frames) > 1:
            text_parts.append(f"--- Frame {i + 1} ---\n{page_text}")
        else:
            text_parts.append(page_text)

    return "\n\n".join(text_parts)


# ── Response Helper ─────────────────────────────────────

def _response(status_code: int, **body):
    return {
        "statusCode": status_code,
        "body": json.dumps(body),
        "headers": {"Content-Type": "application/json"},
    }
