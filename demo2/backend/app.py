"""
Backend API — receives file uploads from the frontend,
sends them to the LocalStack Lambda function for OCR processing,
and returns the extracted text + timing info.
"""

import os
import json
import time
import base64
import logging

import boto3
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── AWS / LocalStack Config ──
LOCALSTACK_ENDPOINT = os.environ.get("LOCALSTACK_ENDPOINT", "http://localhost:4566")
LAMBDA_FUNCTION     = os.environ.get("LAMBDA_FUNCTION_NAME", "ocr-extract")
REGION              = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

ALLOWED_EXTENSIONS  = {"pdf", "tiff", "tif", "png", "jpg", "jpeg"}
MAX_FILE_SIZE       = 20 * 1024 * 1024  # 20 MB


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_lambda_client():
    return boto3.client(
        "lambda",
        endpoint_url=LOCALSTACK_ENDPOINT,
        region_name=REGION,
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


@app.route("/api/extract", methods=["POST"])
def extract_text():
    """Accept a file upload, invoke the Lambda, return extracted text."""

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"}), 400

    file_bytes = file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        return jsonify({"error": "File exceeds 20 MB limit"}), 413

    # Build Lambda payload
    encoded = base64.b64encode(file_bytes).decode("utf-8")
    extension = file.filename.rsplit(".", 1)[1].lower()
    payload = json.dumps({
        "file_data": encoded,
        "file_name": file.filename,
        "file_type": extension,
    })

    logger.info("Invoking Lambda '%s' for file '%s' (%d bytes)", LAMBDA_FUNCTION, file.filename, len(file_bytes))

    t0 = time.perf_counter()
    try:
        client = get_lambda_client()
        response = client.invoke(
            FunctionName=LAMBDA_FUNCTION,
            InvocationType="RequestResponse",
            Payload=payload,
        )

        result_payload = json.loads(response["Payload"].read().decode("utf-8"))
        elapsed_ms = round((time.perf_counter() - t0) * 1000)

        logger.info("Lambda returned in %d ms", elapsed_ms)

        # Lambda may return {"statusCode": 200, "body": "..."}
        if "body" in result_payload:
            body = json.loads(result_payload["body"]) if isinstance(result_payload["body"], str) else result_payload["body"]
        else:
            body = result_payload

        return jsonify({
            "text": body.get("text", ""),
            "pages": body.get("pages", None),
            "processing_time_ms": body.get("processing_time_ms", elapsed_ms),
        })

    except Exception as exc:
        logger.exception("Lambda invocation failed")
        return jsonify({"error": str(exc)}), 502


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
