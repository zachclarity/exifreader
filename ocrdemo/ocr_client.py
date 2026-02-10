#!/usr/bin/env python3
"""
OCR CLI Client — Send images to the Lambda OCR service and get results as CSV.

Usage:
    python ocr_client.py image.png
    python ocr_client.py image1.jpg image2.png image3.tiff
    python ocr_client.py *.png
    python ocr_client.py image.png --url http://localhost:9000
    python ocr_client.py image.png --no-header
    python ocr_client.py image.png --output results.csv

Requires: pip install requests
"""

import argparse
import base64
import csv
import io
import os
import sys
import time

try:
    import requests
except ImportError:
    print("Error: 'requests' package required. Install with: pip install requests", file=sys.stderr)
    sys.exit(1)


DEFAULT_URL = "http://localhost:8080/api/ocr"
DIRECT_URL = "http://localhost:9000/2015-03-31/functions/ocr-service/invocations"


def encode_image(filepath: str) -> str:
    """Read an image file and return base64-encoded string."""
    with open(filepath, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def call_ocr(image_path: str, url: str) -> dict:
    """Send image to OCR Lambda service and return results with total round-trip time."""
    filename = os.path.basename(image_path)
    image_b64 = encode_image(image_path)
    file_size = os.path.getsize(image_path)

    payload = {"image": image_b64, "filename": filename}

    start = time.time()
    resp = requests.post(url, json=payload, timeout=60)
    total_ms = round((time.time() - start) * 1000, 2)

    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        raise RuntimeError(data["error"])

    data["total_time_ms"] = total_ms
    data["file_size_bytes"] = file_size
    return data


def main():
    parser = argparse.ArgumentParser(
        description="OCR CLI — Extract text from images via the Lambda OCR service"
    )
    parser.add_argument(
        "images",
        nargs="+",
        help="Image file(s) to process (PNG, JPG, TIFF, BMP)",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"OCR service URL (default: {DEFAULT_URL})",
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        help=f"Call Lambda container directly at {DIRECT_URL} (bypass nginx)",
    )
    parser.add_argument(
        "--no-header",
        action="store_true",
        help="Omit CSV header row",
    )
    parser.add_argument(
        "--output", "-o",
        help="Write CSV to file instead of stdout",
    )

    args = parser.parse_args()

    url = DIRECT_URL if args.direct else args.url

    # CSV setup
    fieldnames = [
        "filename",
        "file_size_bytes",
        "total_time_ms",
        "ocr_time_ms",
        "word_count",
        "char_count",
        "extracted_text",
    ]

    out = open(args.output, "w", newline="", encoding="utf-8") if args.output else sys.stdout
    writer = csv.DictWriter(out, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)

    if not args.no_header:
        writer.writeheader()

    errors = 0
    for image_path in args.images:
        if not os.path.isfile(image_path):
            print(f"Error: File not found: {image_path}", file=sys.stderr)
            errors += 1
            continue

        try:
            result = call_ocr(image_path, url)
            writer.writerow({
                "filename": result.get("filename", os.path.basename(image_path)),
                "file_size_bytes": result.get("file_size_bytes", ""),
                "total_time_ms": result.get("total_time_ms", ""),
                "ocr_time_ms": result.get("processing_time_ms", ""),
                "word_count": result.get("word_count", 0),
                "char_count": result.get("text_length", 0),
                "extracted_text": result.get("text", "").replace("\n", "\\n"),
            })
            out.flush()

            # Print progress to stderr so it doesn't mix with CSV on stdout
            print(
                f"  ✓ {os.path.basename(image_path)} — "
                f"{result['word_count']} words, "
                f"OCR {result['processing_time_ms']}ms, "
                f"Total {result['total_time_ms']}ms",
                file=sys.stderr,
            )

        except Exception as e:
            print(f"  ✗ {image_path}: {e}", file=sys.stderr)
            errors += 1

    if args.output:
        out.close()
        print(f"\nResults saved to {args.output}", file=sys.stderr)

    print(f"\nProcessed {len(args.images) - errors}/{len(args.images)} images", file=sys.stderr)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
