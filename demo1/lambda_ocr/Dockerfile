FROM python:3.12-slim

# Install tesseract OCR
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng && \
    rm -rf /var/lib/apt/lists/*

# Install the AWS Lambda Runtime Interface Client
RUN pip install --no-cache-dir awslambdaric

WORKDIR /app
COPY handler.py .

# awslambdaric makes this container Lambda-compatible
ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["handler.handler"]
