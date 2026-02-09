"""
Lambda handler — extracts text from PDFs and images.

The Tesseract + Poppler binaries come from a Lambda Layer
mounted at /opt. We set PATH / LD_LIBRARY_PATH / TESSDATA_PREFIX
before using them.

PDF:  PyPDF2 native text → fallback to pdf2image + Tesseract OCR.
TIFF: Pillow multi-frame + Tesseract OCR.
PNG/JPG: Tesseract OCR.
"""

import os
import sys
import json
import time
import base64
import io
import logging
import subprocess

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ── Configure paths from Lambda Layer (/opt) ──────────────
# Lambda Layers extract to /opt. Our layer has:
#   /opt/bin/tesseract, /opt/bin/pdftoppm
#   /opt/lib/*.so
#   /opt/share/tessdata/eng.traineddata

OPT_BIN = "/opt/bin"
OPT_LIB = "/opt/lib"
OPT_TESSDATA = "/opt/share/tessdata"

os.environ["PATH"] = f"{OPT_BIN}:{os.environ.get('PATH', '')}"
os.environ["LD_LIBRARY_PATH"] = f"{OPT_LIB}:{os.environ.get('LD_LIBRARY_PATH', '')}"
os.environ["TESSDATA_PREFIX"] = OPT_TESSDATA

# Verify binaries on cold start
def _check_setup():
    """Log what's available for debugging."""
    logger.info("PATH=%s", os.environ.get("PATH"))
    logger.info("LD_LIBRARY_PATH=%s", os.environ.get("LD_LIBRARY_PATH"))
    logger.info("TESSDATA_PREFIX=%s", os.environ.get("TESSDATA_PREFIX"))

    # Check tesseract
    try:
        result = subprocess.run(["tesseract", "--version"],
                                capture_output=True, text=True, timeout=5)
        logger.info("tesseract: %s", result.stdout.split("\n")[0] if result.stdout else result.stderr.split("\n")[0])
    except Exception as e:
        logger.warning("tesseract not found: %s", e)
        # List /opt contents for debugging
        for d in ["/opt", "/opt/bin", "/opt/lib", "/opt/share"]:
            if os.path.exists(d):
                logger.info("  %s: %s", d, os.listdir(d)[:10])

    # Check pdftoppm
    try:
        result = subprocess.run(["pdftoppm", "-v"],
                                capture_output=True, text=True, timeout=5)
        logger.info("pdftoppm: %s", result.stderr.split("\n")[0] if result.stderr else "ok")
    except Exception as e:
        logger.warning("pdftoppm not found: %s", e)

_check_setup()


# ── Handler ──────────────────────────────────────────────

def handler(event, context):
    t0 = time.perf_counter()

    try:
        file_data = base64.b64decode(event["file_data"])
        file_type = event.get("file_type", "pdf").lower()
        file_name = event.get("file_name", "upload")

        logger.info("Processing %s (%s, %d bytes)", file_name, file_type, len(file_data))

        if file_type == "pdf":
            text, pages = _extract_pdf(file_data)
        elif file_type in ("tiff", "tif", "png", "jpg", "jpeg"):
            text = _extract_image(file_data)
            pages = 1
        else:
            return _resp(400, error=f"Unsupported type: {file_type}")

        ms = round((time.perf_counter() - t0) * 1000)
        logger.info("Done: %d chars, %d pages, %d ms", len(text), pages, ms)
        return _resp(200, text=text.strip(), pages=pages, processing_time_ms=ms)

    except Exception as exc:
        logger.exception("Extraction failed")
        ms = round((time.perf_counter() - t0) * 1000)
        return _resp(500, error=str(exc), processing_time_ms=ms)


# ── PDF ──────────────────────────────────────────────────

def _extract_pdf(data: bytes):
    import PyPDF2
    reader = PyPDF2.PdfReader(io.BytesIO(data))
    pages = len(reader.pages)
    parts = [page.extract_text() or "" for page in reader.pages]
    combined = "\n\n".join(parts)

    if combined.strip() and len(combined.strip()) > 20:
        return combined, pages

    # Scanned PDF — OCR each page
    logger.info("No native text — OCR fallback for %d pages", pages)
    return _ocr_pdf(data), pages


def _ocr_pdf(data: bytes):
    from pdf2image import convert_from_bytes
    import pytesseract

    images = convert_from_bytes(data, dpi=300)
    parts = []
    for i, img in enumerate(images):
        logger.info("OCR page %d/%d", i + 1, len(images))
        parts.append(f"--- Page {i+1} ---\n{pytesseract.image_to_string(img, lang='eng')}")
    return "\n\n".join(parts)


# ── Image (TIFF, PNG, JPG) ───────────────────────────────

def _extract_image(data: bytes):
    from PIL import Image
    import pytesseract

    img = Image.open(io.BytesIO(data))

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

    parts = []
    for i, f in enumerate(frames):
        if f.mode not in ("RGB", "L"):
            f = f.convert("RGB")
        t = pytesseract.image_to_string(f, lang="eng")
        parts.append(f"--- Frame {i+1} ---\n{t}" if len(frames) > 1 else t)
    return "\n\n".join(parts)


# ── Response ─────────────────────────────────────────────

def _resp(code, **body):
    return {"statusCode": code, "body": json.dumps(body)}
