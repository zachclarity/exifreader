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
from botocore.exceptions import ClientError
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
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


def wait_for_lambda(max_retries=30, interval=2):
    """Block until the Lambda function is available in LocalStack."""
    client = get_lambda_client()
    for i in range(max_retries):
        try:
            resp = client.get_function(FunctionName=LAMBDA_FUNCTION)
            state = resp.get("Configuration", {}).get("State", "Unknown")
            logger.info("Lambda '%s' state: %s", LAMBDA_FUNCTION, state)
            if state == "Active":
                return True
            # Even if state is not "Active", if we got a response it exists
            return True
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code == "ResourceNotFoundException":
                logger.info("Lambda not found yet, waiting... (%d/%d)", i + 1, max_retries)
                time.sleep(interval)
            else:
                logger.warning("Unexpected error checking Lambda: %s", e)
                time.sleep(interval)
        except Exception as e:
            logger.warning("Connection error (LocalStack may still be starting): %s", e)
            time.sleep(interval)
    return False


# ── Wait for Lambda on startup ──
with app.app_context():
    logger.info("Waiting for Lambda function '%s' to be available...", LAMBDA_FUNCTION)
    if wait_for_lambda():
        logger.info("✓ Lambda function '%s' is ready!", LAMBDA_FUNCTION)
    else:
        logger.error("✗ Lambda function '%s' not found after retries. Invocations will fail.", LAMBDA_FUNCTION)


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

    logger.info("Invoking Lambda '%s' for file '%s' (%d bytes)",
                LAMBDA_FUNCTION, file.filename, len(file_bytes))

    t0 = time.perf_counter()
    try:
        client = get_lambda_client()

        # Verify function exists before invoking
        try:
            client.get_function(FunctionName=LAMBDA_FUNCTION)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                # Try listing to help debug
                funcs = client.list_functions()
                names = [f["FunctionName"] for f in funcs.get("Functions", [])]
                logger.error("Lambda '%s' not found. Available functions: %s", LAMBDA_FUNCTION, names)
                return jsonify({
                    "error": f"Lambda function '{LAMBDA_FUNCTION}' not found in LocalStack. "
                             f"Available: {names}. Check LocalStack logs."
                }), 503
            raise

        response = client.invoke(
            FunctionName=LAMBDA_FUNCTION,
            InvocationType="RequestResponse",
            Payload=payload,
        )

        raw_payload = response["Payload"].read().decode("utf-8")
        elapsed_ms = round((time.perf_counter() - t0) * 1000)

        logger.info("Lambda returned in %d ms (status %s)",
                     elapsed_ms, response.get("StatusCode"))

        # Check for Lambda-level errors
        if "FunctionError" in response:
            logger.error("Lambda FunctionError: %s", raw_payload)
            return jsonify({"error": f"Lambda execution error: {raw_payload}"}), 502

        result_payload = json.loads(raw_payload)

        # Lambda returns {"statusCode": 200, "body": "{...}"}
        if "body" in result_payload:
            body = json.loads(result_payload["body"]) if isinstance(result_payload["body"], str) else result_payload["body"]
        else:
            body = result_payload

        # Check for application-level errors from the handler
        if result_payload.get("statusCode", 200) >= 400:
            return jsonify({"error": body.get("error", "Extraction failed")}), 502

        return jsonify({
            "text": body.get("text", ""),
            "pages": body.get("pages", None),
            "processing_time_ms": body.get("processing_time_ms", elapsed_ms),
        })

    except ClientError as exc:
        logger.exception("AWS ClientError during Lambda invocation")
        return jsonify({"error": f"AWS error: {exc.response['Error']['Message']}"}), 502
    except Exception as exc:
        logger.exception("Lambda invocation failed")
        return jsonify({"error": str(exc)}), 502


@app.route("/api/health", methods=["GET"])
def health():
    """Health check — also reports whether Lambda is reachable."""
    try:
        client = get_lambda_client()
        client.get_function(FunctionName=LAMBDA_FUNCTION)
        lambda_ok = True
    except Exception:
        lambda_ok = False

    return jsonify({
        "status": "ok",
        "lambda_ready": lambda_ok,
        "lambda_function": LAMBDA_FUNCTION,
        "localstack_endpoint": LOCALSTACK_ENDPOINT,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
