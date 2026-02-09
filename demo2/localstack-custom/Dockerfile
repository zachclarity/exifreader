# Custom LocalStack with Tesseract OCR + Poppler pre-installed.
# Needed because LAMBDA_EXECUTOR=local runs Lambda code inside this container.
FROM localstack/localstack:3.4

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*
