# This Dockerfile is used by the init script to build the Lambda zip.
# It installs Tesseract, Poppler, and Python deps into a Lambda-compatible layer.
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libgl1 \
    zip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install Python dependencies into /build/package
COPY requirements.txt .
RUN pip install --no-cache-dir -t /build/package -r requirements.txt

# Copy handler
COPY handler.py /build/package/handler.py

# Create deployment zip
WORKDIR /build/package
RUN zip -r9 /build/lambda.zip .
