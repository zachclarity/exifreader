# OCR Lambda System — Complete Tutorial

A full line-by-line walkthrough of three AWS Lambda handlers (Python) and the Java 21 CLI client that invokes them. Every import, every method, every line explained.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Part 1 — Python Lambda Handlers](#2-part-1--python-lambda-handlers)
    - [handler.py — Image OCR](#21-handlerpy--image-ocr)
    - [pdf_handler.py — PDF Text Extraction](#22-pdf_handlerpy--pdf-text-extraction)
    - [pdf_ocr_handler.py — PDF OCR Pipeline](#23-pdf_ocr_handlerpy--pdf-ocr-pipeline)
    - [How the Three Handlers Relate](#24-how-the-three-handlers-relate)
3. [Part 2 — Java 21 CLI Client](#3-part-2--java-21-cli-client)
    - [Project Structure and Maven Build](#31-project-structure-and-maven-build)
    - [pom.xml — Maven Configuration](#32-pomxml--maven-configuration)
    - [OcrRequest.java — Sealed Request Model](#33-ocrrequestjava--sealed-request-model)
    - [OcrResponse.java — Response Records](#34-ocrresponsejava--response-records)
    - [FileUtils.java — File I/O Utilities](#35-fileutilsjava--file-io-utilities)
    - [OutputFormatter.java — Display Formatting](#36-outputformatterjava--display-formatting)
    - [LambdaInvoker.java — AWS Lambda Service](#37-lambdainvokerjava--aws-lambda-service)
    - [OcrCli.java — CLI Entry Point](#38-ocrclijava--cli-entry-point)
4. [Running Against LocalStack](#4-running-against-localstack)
5. [Running the Tests](#5-running-the-tests)

---

## 1. Architecture Overview

The system has two layers: Python functions running in AWS Lambda, and a Java CLI that calls them.

```
┌───────────────────────────────────────────────────────────────────┐
│                      Java 21 CLI Client                          │
│  ┌──────────┐  ┌───────────┐  ┌──────────────┐  ┌────────────┐  │
│  │ OcrCli   │→ │FileUtils  │→ │LambdaInvoker │→ │OutputFormat│  │
│  │ (picocli)│  │(base64 I/O│  │(AWS SDK v2)  │  │(JSON/text) │  │
│  └──────────┘  └───────────┘  └──────┬───────┘  └────────────┘  │
└──────────────────────────────────────┼───────────────────────────┘
                                       │ AWS SDK invoke()
                    ┌──────────────────┼──────────────────┐
                    │           AWS Lambda / LocalStack     │
                    │                  │                    │
                    │    ┌─────────────┼─────────────┐     │
                    │    ▼             ▼             ▼     │
                    │ handler.py  pdf_handler.py  pdf_ocr  │
                    │ (Tesseract) (PyMuPDF text) (both)    │
                    └─────────────────────────────────────┘
```

**Data flow for every request:**

1. CLI reads a file from disk, base64-encodes it
2. CLI builds a JSON payload matching the Lambda's expected format
3. AWS SDK sends the payload to the correct Lambda function
4. Lambda decodes base64 → writes temp file → processes → returns JSON
5. CLI deserializes JSON into a typed record and formats for display

---

## 2. Part 1 — Python Lambda Handlers

### 2.1 handler.py — Image OCR

This handler receives a base64-encoded image, writes it to disk, and runs Tesseract OCR on it.

#### Imports (Lines 1–6)

```python
import json          # Line 1: Parse JSON when request arrives via API Gateway
import base64        # Line 2: Decode the base64-encoded image from the client
import time          # Line 3: Measure OCR processing duration in milliseconds
import subprocess    # Line 4: Execute the Tesseract OCR binary as a child process
import tempfile      # Line 5: Create temporary files (Tesseract reads from disk, not memory)
import os            # Line 6: Delete temp files and extract file extensions
```

**Why these specific imports:** Tesseract is a C++ binary that reads files from disk — it doesn't have a Python API. So the pipeline is: decode bytes → write to temp file → call Tesseract via subprocess → read stdout → delete temp file. Every import supports one step of that pipeline.

#### Function Signature (Line 9)

```python
def lambda_handler(event, context):
```

- `event` — A Python dict containing the request. Its structure depends on how the Lambda is invoked (directly or through API Gateway).
- `context` — An AWS `LambdaContext` object with runtime metadata (function name, memory limit, remaining time). We don't use it here, but Lambda requires it in the signature.

The name `lambda_handler` is the conventional default. In AWS, you configure this as `handler.lambda_handler` (filename.function).

#### Input Parsing (Lines 13–20)

```python
# Line 13: Check if this came through API Gateway (has "body" and "httpMethod")
if "body" in event and "httpMethod" in event:
    # Line 14: Get the body string (API Gateway wraps the real payload here)
    body = event.get("body", "")
    # Lines 15-16: API Gateway sometimes base64-encodes the body for binary payloads
    if event.get("isBase64Encoded", False):
        body = base64.b64decode(body).decode("utf-8")
    # Line 17: Parse the JSON string into a Python dict
    payload = json.loads(body) if isinstance(body, str) else body
else:
    # Line 19: Direct invocation — the event IS the payload already
    payload = event
```

**Why two formats:** This is a common Lambda pattern. API Gateway wraps the client's JSON inside its own envelope (`{"body": "...", "httpMethod": "POST", ...}`). Direct invocation (from another Lambda, or from our Java client) sends the payload directly. By handling both, the same function works behind an API and in direct testing.

**The `isBase64Encoded` flag:** When API Gateway receives binary data, it base64-encodes the body and sets this flag. We decode it back to a UTF-8 string before JSON parsing.

#### Extracting Image Data (Lines 22–26)

```python
# Line 22: Pull the base64-encoded image string from the payload
image_data = payload.get("image", "")
# Line 23: Get the filename (used for temp file extension and response metadata)
filename = payload.get("filename", "unknown")

# Lines 25-26: Early return if no image was provided
if not image_data:
    return {"error": "No image data provided"}
```

- `payload.get("image", "")` — Uses `.get()` with a default to avoid `KeyError` if the key is missing.
- The error return is a plain dict. Lambda serializes it to JSON automatically. No HTTP status codes here — that's API Gateway's job.

#### Stripping Data URL Prefix (Lines 28–30)

```python
# Lines 29-30: Remove "data:image/png;base64," prefix if present
if "," in image_data:
    image_data = image_data.split(",", 1)[1]
```

- Browsers encode files as data URLs: `data:image/png;base64,iVBORw0KGgo...`
- `split(",", 1)` splits on the **first** comma only. The `1` limits it to one split, producing a list of two elements. `[1]` takes everything after the comma.
- This is defensive — the actual base64 data uses `A-Za-z0-9+/=` characters (no commas), but limiting the split to 1 is still safer.

#### Decoding and Writing to Disk (Lines 32–37)

```python
# Line 33: Convert base64 string → raw bytes
image_bytes = base64.b64decode(image_data)

# Line 36: Extract file extension from filename, default to ".png"
suffix = os.path.splitext(filename)[1] or ".png"
# Lines 37-39: Create temp file with that extension
with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
    tmp.write(image_bytes)       # Write decoded bytes to disk
    tmp_path = tmp.name          # Save the path for Tesseract
```

- `os.path.splitext("photo.jpg")` returns `("photo", ".jpg")`. The `[1]` gets `.jpg`. The `or ".png"` handles cases where there's no extension.
- `delete=False` is **crucial**. Without it, Python deletes the temp file when the `with` block exits — but Tesseract needs to read it after. We'll delete it manually later.
- `tmp.name` is the full filesystem path, like `/tmp/tmp8x3k2f9d.jpg`.

#### Running Tesseract (Lines 41–50)

```python
# Line 42: Record the start time
start_time = time.time()

# Lines 44-49: Execute Tesseract as a subprocess
result = subprocess.run(
    ["tesseract", tmp_path, "stdout", "--oem", "1", "--psm", "3"],
    capture_output=True,   # Capture both stdout and stderr
    text=True,             # Return strings, not bytes
    timeout=30             # Kill after 30 seconds
)

# Line 51: Calculate elapsed time in milliseconds
elapsed_ms = round((time.time() - start_time) * 1000, 2)
```

Breaking down the Tesseract command arguments:

| Argument | Meaning |
|----------|---------|
| `tesseract` | The Tesseract binary |
| `tmp_path` | Input image file path |
| `stdout` | Special keyword: write OCR output to stdout (not a file) |
| `--oem 1` | OCR Engine Mode 1 = LSTM neural network only (most accurate) |
| `--psm 3` | Page Segmentation Mode 3 = fully automatic segmentation (good default) |

The `subprocess.run` parameters:

| Parameter | Purpose |
|-----------|---------|
| `capture_output=True` | Pipes stdout and stderr back to Python (equivalent to `stdout=PIPE, stderr=PIPE`) |
| `text=True` | Decodes output as UTF-8 strings instead of raw bytes |
| `timeout=30` | Raises `subprocess.TimeoutExpired` after 30 seconds. Prevents Lambda from hitting its own timeout without returning a response |

#### Cleanup and Response (Lines 53–67)

```python
# Line 54: Delete the temp file immediately (Lambda has limited /tmp space: 512 MB)
os.unlink(tmp_path)

# Line 56: Get the extracted text, removing leading/trailing whitespace
extracted_text = result.stdout.strip()

# Lines 58-62: Only report error if Tesseract failed AND produced no text
if result.returncode != 0 and not extracted_text:
    return {
        "error": "Tesseract OCR failed: " + result.stderr.strip(),
        "processing_time_ms": elapsed_ms
    }

# Lines 64-70: Success response with text and metadata
return {
    "text": extracted_text,
    "processing_time_ms": elapsed_ms,
    "filename": filename,
    "text_length": len(extracted_text),
    "word_count": len(extracted_text.split()) if extracted_text else 0
}
```

- `os.unlink()` deletes the file. Called before the return to ensure cleanup even if we return early on error.
- **Why check both `returncode` and `extracted_text`:** Sometimes Tesseract exits with a non-zero return code but still produces partial text (e.g., it recognized some characters but had warnings). That partial text is still useful, so we only error out if there's truly nothing.
- `extracted_text.split()` splits on any whitespace. `len()` of the resulting list gives word count. The `if extracted_text else 0` guard prevents `"".split()` returning `['']` (which has length 1, not 0).

---

### 2.2 pdf_handler.py — PDF Text Extraction

This handler extracts **embedded** text from digital PDFs using PyMuPDF. It does not OCR — it reads the text layer directly. This is much faster than OCR and works perfectly on PDFs created from word processors, web pages, or any digital source.

#### Imports (Lines 1–6)

```python
import base64     # Line 1: Decode the base64-encoded PDF from the client
import os         # Line 2: Delete temp files after processing
import tempfile   # Line 3: Create temp files (PyMuPDF needs a file path)
import time       # Line 4: Track processing time per page and overall

import fitz       # Line 6: PyMuPDF — the PDF processing library
```

- `fitz` is the Python binding for MuPDF, a lightweight PDF rendering library. The import name `fitz` is a historical artifact from the library's origins — it's actually `PyMuPDF`. You install it with `pip install PyMuPDF` but import it as `fitz`.

#### Function Signature (Line 9)

```python
def pdf_handler(event, context):
```

Named `pdf_handler` instead of `lambda_handler` — each handler uses a descriptive name. In AWS you'd configure this as `pdf_handler.pdf_handler`. Note this handler **does not** support the API Gateway proxy format (unlike `handler.py`). It expects direct invocation only.

#### Input Parsing (Lines 13–16)

```python
# Line 13: No API Gateway support — event IS the payload
payload = event
# Line 14: Get the base64-encoded PDF data
pdf_data = payload.get("pdf", "")
# Line 15: Get filename with a sensible default
filename = payload.get("filename", "unknown.pdf")
```

- The key is `"pdf"` (not `"image"`) — each handler expects its own input field.
- Default filename includes `.pdf` extension since we know the type.

#### Decoding and Opening (Lines 21–30)

```python
# Line 22: Decode base64 → raw PDF bytes
pdf_bytes = base64.b64decode(pdf_data)

# Lines 25-27: Write to a temp file
with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
    tmp.write(pdf_bytes)
    tmp_path = tmp.name

# Line 30: Start the overall timer
total_start = time.time()

# Line 32: Open the PDF with PyMuPDF
doc = fitz.open(tmp_path)
# Line 33: Get page count — fitz.Document supports len()
page_count = len(doc)
```

- `fitz.open()` reads the entire PDF into memory and parses its structure. It needs a file path (or a bytes buffer), hence the temp file.
- `len(doc)` returns the number of pages. PyMuPDF implements `__len__` on its Document class.

#### Per-Page Extraction Loop (Lines 35–54)

```python
# Lines 35-38: Initialize accumulators
pages = []              # Per-page result dicts for the response
full_text_parts = []    # Collected text strings to join at the end
total_word_count = 0    # Running total across all pages
total_char_count = 0    # Running total across all pages

# Line 40: Iterate over pages — fitz.Document is iterable
for i, page in enumerate(doc):
    # Line 41: Time each page individually
    page_start = time.time()
    # Line 42: Extract plain text from this page
    text = page.get_text("text").strip()
    # Line 43: Calculate this page's extraction time
    page_ms = round((time.time() - page_start) * 1000, 2)

    # Lines 45-48: Compute per-page stats
    word_count = len(text.split()) if text else 0
    char_count = len(text)
    total_word_count += word_count
    total_char_count += char_count
    # Line 49: Save text for final concatenation
    full_text_parts.append(text)

    # Lines 51-57: Build the per-page result dict
    pages.append({
        "page": i + 1,              # 1-indexed page numbers (human-readable)
        "text": text,
        "word_count": word_count,
        "char_count": char_count,
        "extraction_time_ms": page_ms,
    })
```

- `page.get_text("text")` extracts the text layer from the PDF page. The `"text"` argument specifies plain text output. Other options: `"html"` (HTML with formatting), `"dict"` (structured dict with position info), `"blocks"` (text blocks with coordinates).
- Per-page timing helps identify complex pages that take longer — useful for debugging production performance.
- `i + 1` because `enumerate` starts at 0 but humans expect pages starting at 1.

#### Cleanup and Response (Lines 56–74)

```python
# Line 57: Close the document to free memory
doc.close()

# Line 59: Total wall-clock time for the entire extraction
total_ms = round((time.time() - total_start) * 1000, 2)

# Line 62: Delete the temp file
os.unlink(tmp_path)

# Line 64: Join all pages with double newline for clear separation
full_text = "\n\n".join(full_text_parts)

# Lines 66-74: Return everything
return {
    "text": full_text,
    "filename": filename,
    "page_count": page_count,
    "total_word_count": total_word_count,
    "total_char_count": total_char_count,
    "processing_time_ms": total_ms,
    "file_size_bytes": len(pdf_bytes),     # Original PDF size (before base64)
    "pages": pages,                         # Per-page breakdown
}
```

- `doc.close()` is important — PyMuPDF holds file handles and memory. Without closing, you'd leak resources (especially in a Lambda that may be reused).
- `"\n\n".join()` puts two newlines between pages, making the output readable.
- `len(pdf_bytes)` gives the actual PDF size, not the base64 size (base64 is ~33% larger).

---

### 2.3 pdf_ocr_handler.py — PDF OCR Pipeline

The most complex handler. It combines both previous approaches: PyMuPDF renders PDF pages to images, then Tesseract OCRs each image. This is for **scanned** PDFs where pages are images with no text layer.

#### Pipeline Flow

```
PDF bytes → temp file → PyMuPDF opens
    → For each page:
        1. Render page to PNG image (PyMuPDF)
        2. Write PNG to temp file
        3. Run Tesseract OCR on PNG
        4. Collect text, delete temp PNG
    → Join all page texts
    → Return with detailed timing
```

#### Helper: `run_tesseract()` (Lines 20–31)

```python
def run_tesseract(image_path: str) -> tuple[str, float]:
```

- Type hints: Takes a file path string, returns a tuple of (extracted text, elapsed milliseconds).
- `tuple[str, float]` is Python 3.9+ built-in generic syntax.

```python
    # Line 22: Record start time
    start = time.time()
    # Lines 23-28: Run Tesseract (same args as handler.py)
    result = subprocess.run(
        ["tesseract", image_path, "stdout", "--oem", "1", "--psm", "3"],
        capture_output=True,
        text=True,
        timeout=60,    # 60s timeout (larger than handler.py's 30s)
    )
    # Line 29: Calculate elapsed time
    elapsed_ms = round((time.time() - start) * 1000, 2)
    # Line 30: Strip whitespace from output
    text = result.stdout.strip()

    # Lines 32-33: Unlike handler.py, this RAISES an exception on failure
    if result.returncode != 0 and not text:
        raise RuntimeError(f"Tesseract failed: {result.stderr.strip()}")

    # Line 35: Return both text and timing
    return text, elapsed_ms
```

**Key differences from handler.py:**
1. **60-second timeout** instead of 30 — PDF pages rendered at 300 DPI produce large images.
2. **Raises RuntimeError** instead of returning an error dict — the calling function (`pdf_ocr_handler`) catches it and wraps it in the response format.
3. **Extracted as a helper** for clarity and testability — you can unit-test OCR logic independently.

#### Helper: `extract_page_image()` (Lines 38–44)

```python
def extract_page_image(page, dpi: int = 300) -> tuple[bytes, float]:
```

Renders a PDF page to a PNG image in memory.

```python
    # Line 40: Record start time
    start = time.time()
    # Line 41: Create a scaling matrix — PDFs use 72 points per inch
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    # Line 42: Render the page to a pixel buffer at the given resolution
    pix = page.get_pixmap(matrix=mat)
    # Line 43: Encode the pixel buffer as PNG bytes
    png_bytes = pix.tobytes("png")
    # Line 44: Calculate elapsed time
    elapsed_ms = round((time.time() - start) * 1000, 2)
    # Line 45: Return the image bytes and timing
    return png_bytes, elapsed_ms
```

**The DPI math explained:**
- PDFs define coordinates in "points" where 1 point = 1/72 of an inch.
- `fitz.Matrix(scale_x, scale_y)` creates a transformation matrix that scales the rendering.
- At 300 DPI: `300 / 72 = 4.167`. Each point becomes ~4.17 pixels.
- A standard US Letter page (8.5 × 11 inches) at 300 DPI becomes 2550 × 3300 pixels.
- Higher DPI = better OCR accuracy but larger images and slower processing.

| DPI | Scale | Letter Page Size | Use Case |
|-----|-------|-----------------|----------|
| 150 | 2.08x | 1275 × 1650 | Fast preview, low quality |
| 300 | 4.17x | 2550 × 3300 | Standard OCR (good default) |
| 600 | 8.33x | 5100 × 6600 | High-quality OCR for fine print |

#### Main Function: Page Processing Loop (Lines 73–106)

```python
for i, page in enumerate(doc):
    # Line 75: Time the entire page (render + OCR)
    page_start = time.time()

    # Step 1: Render page to image
    # Line 78: Get PNG bytes and render timing
    png_bytes, extract_ms = extract_page_image(page, dpi)
    # Line 79: Add to running total
    total_extract_ms += extract_ms

    # Step 2: Write image to disk for Tesseract
    # Lines 82-84: Create temp PNG file
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as img_tmp:
        img_tmp.write(png_bytes)
        img_path = img_tmp.name

    # Step 3: OCR the rendered image
    # Line 87: Run Tesseract and get text + timing
    text, ocr_ms = run_tesseract(img_path)
    # Line 88: Add to running total
    total_ocr_ms += ocr_ms

    # Step 4: Clean up
    # Line 91: Delete temp image immediately (conserve /tmp space)
    os.unlink(img_path)

    # Line 93: Total wall-clock time for this page
    page_total_ms = round((time.time() - page_start) * 1000, 2)
```

**Why a temp file per page instead of keeping all in memory:** Lambda has limited memory (128 MB to 10 GB, configurable). A single page at 300 DPI is ~25 MB as an uncompressed PNG. On a 100-page PDF that would be 2.5 GB in memory. Creating and deleting per-page keeps peak memory to just one page image.

#### Timing Breakdown in Response (Lines 115–121)

```python
"timing": {
    "pipeline_ms": pipeline_ms,                                             # Total wall-clock time
    "total_image_extract_ms": round(total_extract_ms, 2),                  # Sum of all render times
    "total_ocr_ms": round(total_ocr_ms, 2),                               # Sum of all OCR times
    "avg_extract_per_page_ms": round(total_extract_ms / max(page_count, 1), 2),  # Average render per page
    "avg_ocr_per_page_ms": round(total_ocr_ms / max(page_count, 1), 2),         # Average OCR per page
},
```

- `max(page_count, 1)` prevents division by zero if a PDF somehow has zero pages.
- `pipeline_ms` will be slightly larger than `total_image_extract_ms + total_ocr_ms` because it includes overhead (temp file I/O, loop iteration, etc.).
- These averages help you estimate processing time for larger documents: a 100-page PDF at 350ms/page OCR ≈ 35 seconds total.

---

### 2.4 How the Three Handlers Relate

| Feature | handler.py | pdf_handler.py | pdf_ocr_handler.py |
|---|---|---|---|
| **Input** | Base64 image | Base64 PDF | Base64 PDF |
| **Input key** | `"image"` | `"pdf"` | `"pdf"` |
| **Method** | Tesseract OCR | PyMuPDF text extraction | PyMuPDF render + Tesseract |
| **Use case** | Photos, screenshots | Digital/native PDFs | Scanned PDFs |
| **Speed** | Fast (single image) | Very fast (no OCR) | Slow (render + OCR × pages) |
| **Dependencies** | Tesseract | PyMuPDF | Both |
| **API Gateway** | Yes | No | No |

---

## 3. Part 2 — Java 21 CLI Client

The Java client is a command-line tool that reads files from disk, base64-encodes them, invokes the correct Lambda function via the AWS SDK, and formats the results. It uses several Java 21 features throughout.

### 3.1 Project Structure and Maven Build

```
ocr-client/
├── pom.xml                                    # Maven build config
├── src/
│   ├── main/java/com/ocr/
│   │   ├── client/
│   │   │   ├── OcrCli.java                   # CLI entry point (picocli)
│   │   │   └── LambdaInvoker.java            # AWS Lambda invocation
│   │   ├── model/
│   │   │   ├── OcrRequest.java               # Sealed interface + request records
│   │   │   └── OcrResponse.java              # Response records
│   │   └── util/
│   │       ├── FileUtils.java                # File reading, base64, type detection
│   │       └── OutputFormatter.java          # JSON / text / summary output
│   └── test/java/com/ocr/
│       ├── FileUtilsTest.java                # 10 tests
│       ├── ModelAndPayloadTest.java          # 11 tests
│       └── OutputFormatterTest.java          # 8 tests
```

**Why this package layout:**
- `model/` — Pure data. No dependencies on AWS or CLI frameworks. Can be reused in a library.
- `client/` — Depends on AWS SDK and picocli. Orchestrates the workflow.
- `util/` — Shared utilities with no domain-specific coupling.

---

### 3.2 pom.xml — Maven Configuration

#### Project Coordinates (Lines 8–11)

```xml
<groupId>com.ocr</groupId>           <!-- Organization identifier -->
<artifactId>ocr-client</artifactId>  <!-- Project name (becomes the JAR filename) -->
<version>1.0.0</version>             <!-- Semantic version -->
<packaging>jar</packaging>           <!-- Output type: JAR file -->
```

#### Properties (Lines 15–29)

```xml
<properties>
    <maven.compiler.source>21</maven.compiler.source>   <!-- Java source level -->
    <maven.compiler.target>21</maven.compiler.target>   <!-- Bytecode target level -->
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>

    <!-- Centralized dependency versions -->
    <aws.sdk.version>2.25.60</aws.sdk.version>    <!-- AWS SDK for Java v2 -->
    <picocli.version>4.7.6</picocli.version>       <!-- CLI argument parser -->
    <gson.version>2.11.0</gson.version>             <!-- JSON serializer -->
    <slf4j.version>2.0.13</slf4j.version>           <!-- Logging (AWS SDK needs it) -->
    <junit.version>5.10.3</junit.version>            <!-- Unit testing -->

    <!-- Used by both maven-jar-plugin and maven-shade-plugin -->
    <main.class>com.ocr.client.OcrCli</main.class>
</properties>
```

**Why `<properties>`:** Defining versions once here means every `<dependency>` references `${aws.sdk.version}` etc. When you upgrade, you change one line.

#### AWS SDK BOM (Lines 32–42)

```xml
<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>software.amazon.awssdk</groupId>
            <artifactId>bom</artifactId>         <!-- Bill of Materials -->
            <version>${aws.sdk.version}</version>
            <type>pom</type>
            <scope>import</scope>                 <!-- Import all version declarations -->
        </dependency>
    </dependencies>
</dependencyManagement>
```

A **BOM (Bill of Materials)** is a Maven POM that declares compatible versions for a group of related libraries. Importing the AWS SDK BOM means you don't specify versions for individual AWS modules — they all come from the BOM and are guaranteed compatible.

#### Key Dependencies

| Dependency | Purpose | Why needed |
|---|---|---|
| `software.amazon.awssdk:lambda` | Lambda client for invoke API | Core functionality — calls Lambda |
| `software.amazon.awssdk:auth` | Credential providers | Finds AWS keys (env vars, files, roles) |
| `info.picocli:picocli` | CLI argument parsing | Parses `--region`, `--output`, subcommands |
| `com.google.code.gson:gson` | JSON serialization/deserialization | Builds Lambda payloads, parses responses |
| `org.slf4j:slf4j-simple` | Logging implementation | AWS SDK requires SLF4J; `simple` outputs to stderr |
| `org.junit.jupiter:junit-jupiter` | JUnit 5 testing | Unit tests with `@Test`, `@ParameterizedTest` |

#### Maven Shade Plugin (Lines 113–148)

```xml
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-shade-plugin</artifactId>
    <version>3.6.0</version>
    ...
</plugin>
```

The Shade plugin creates a **fat JAR** (also called uber JAR) containing all dependencies in a single file. This is essential because the Lambda client needs 30+ JARs (AWS SDK, HTTP client, Jackson, Netty, etc.). Without shading, you'd need to ship and manage the entire dependency tree.

Key configuration:

- **`ManifestResourceTransformer`** — Sets `Main-Class` in `MANIFEST.MF` so `java -jar` works.
- **`ServicesResourceTransformer`** — Merges `META-INF/services` files. **Critical for AWS SDK** — without this, the SDK can't discover HTTP client implementations and credential providers at runtime.
- **Signature exclusion filters** — Removes `*.SF`, `*.DSA`, `*.RSA` files from dependencies. Signed JARs break when repackaged; removing their signatures prevents `SecurityException` at runtime.
- **`module-info.class` exclusion** — Removes Java 9+ module descriptors that conflict in a fat JAR.

---

### 3.3 OcrRequest.java — Sealed Request Model

This file defines the three request types using Java 21 sealed interfaces and records.

#### The Sealed Interface (Line 10)

```java
public sealed interface OcrRequest {
```

**`sealed`** means only classes declared in this file can implement `OcrRequest`. The compiler knows exactly three implementations exist, which enables **exhaustive switch expressions** — you don't need a `default` case, and the compiler warns if you forget one.

#### ImageOcr Record (Line 13)

```java
record ImageOcr(String image, String filename) implements OcrRequest {}
```

**`record`** is Java 21's concise immutable data class. This single line generates:
- Private final fields: `image`, `filename`
- A canonical constructor: `new ImageOcr("base64...", "photo.png")`
- Accessor methods: `image()`, `filename()` (note: no `get` prefix)
- `equals()`, `hashCode()`, `toString()` implementations
- The class is implicitly `final`

This replaces ~40 lines of traditional Java boilerplate.

#### PdfExtract Record (Line 16)

```java
record PdfExtract(String pdf, String filename) implements OcrRequest {}
```

Same pattern — `pdf` instead of `image` because the Lambda expects a different JSON key.

#### PdfOcr Record with Overloaded Constructor (Lines 19–23)

```java
record PdfOcr(String pdf, String filename, int dpi) implements OcrRequest {
    public PdfOcr(String pdf, String filename) {
        this(pdf, filename, 300);   // Default DPI of 300
    }
}
```

Records can have additional constructors that delegate to the canonical one via `this(...)`. This provides a convenient two-argument constructor while the canonical constructor keeps DPI configurable.

#### How Sealed + Records Enable Pattern Matching

```java
// In LambdaInvoker.invokeRaw():
return switch (request) {
    case OcrRequest.ImageOcr img   -> invoke(imageOcrFunction, buildImagePayload(img));
    case OcrRequest.PdfExtract pdf -> invoke(pdfExtractFunction, buildPdfExtractPayload(pdf));
    case OcrRequest.PdfOcr ocr     -> invoke(pdfOcrFunction, buildPdfOcrPayload(ocr));
};
// No default needed — compiler guarantees all cases covered
```

If you add a fourth record to `OcrRequest`, every switch that matches on it will fail to compile until updated. This is compile-time safety that prevents bugs.

---

### 3.4 OcrResponse.java — Response Records

This file defines the Java types that map to each Lambda's JSON response.

#### Class Structure (Lines 10–12)

```java
public final class OcrResponse {
    private OcrResponse() {}    // Private constructor — this class is just a namespace
```

- `final` — Cannot be subclassed.
- Private constructor — Cannot be instantiated. This class exists only to hold nested record definitions, acting as a namespace (like a C++ namespace or Python module).

#### ImageOcrResult Record (Lines 28–37)

```java
public record ImageOcrResult(
        String text,
        String filename,
        @SerializedName("text_length") int textLength,
        @SerializedName("word_count") int wordCount,
        @SerializedName("processing_time_ms") double processingTimeMs,
        String error
) {
    public boolean isSuccess() { return error == null; }
}
```

**`@SerializedName`** bridges naming conventions. Python's `handler.py` returns `"word_count"` (snake_case) but Java convention is `wordCount` (camelCase). Gson uses `@SerializedName` to map between them during deserialization.

**`isSuccess()` method**: Records can have methods. This provides a clean API: `if (result.isSuccess())` instead of `if (result.error() == null)`.

#### Nested Record: TimingBreakdown (Lines 83–89)

```java
public record TimingBreakdown(
        @SerializedName("pipeline_ms") double pipelineMs,
        @SerializedName("total_image_extract_ms") double totalImageExtractMs,
        @SerializedName("total_ocr_ms") double totalOcrMs,
        @SerializedName("avg_extract_per_page_ms") double avgExtractPerPageMs,
        @SerializedName("avg_ocr_per_page_ms") double avgOcrPerPageMs
) {}
```

This maps to the nested `"timing"` object in `pdf_ocr_handler.py`'s response. Gson handles nested deserialization automatically — when it sees `"timing": {...}`, it creates a `TimingBreakdown` record from the inner JSON.

#### PdfOcrResult with Nested Types (Lines 94–107)

```java
public record PdfOcrResult(
        ...
        TimingBreakdown timing,                    // Nested record
        ...
        List<OcrPageResult> pages,                 // List of nested records
        String error
) {
    public boolean isSuccess() { return error == null; }
}
```

Gson deserializes the `"pages"` JSON array into a `List<OcrPageResult>` automatically. Each JSON object in the array becomes an `OcrPageResult` record.

---

### 3.5 FileUtils.java — File I/O Utilities

#### Class Design (Lines 12–14)

```java
public final class FileUtils {
    private FileUtils() {}    // Utility class — all methods are static
```

Same pattern as `OcrResponse` — `final` + private constructor makes this a pure utility class.

#### Extension Sets (Lines 16–20)

```java
private static final Set<String> IMAGE_EXTENSIONS = Set.of(
        ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif", ".webp"
);
private static final Set<String> PDF_EXTENSIONS = Set.of(".pdf");
```

- `Set.of()` creates an **immutable** set (Java 9+). This is important — the set is a static final constant that should never change.
- Using a `Set` gives O(1) lookup instead of iterating a list.

#### FileType Enum (Line 23)

```java
public enum FileType { IMAGE, PDF, UNKNOWN }
```

Used in the CLI's `scan` command to decide which Lambda to invoke.

#### detectType Method (Lines 28–37)

```java
public static FileType detectType(Path file) {
    // Line 29: Get filename in lowercase for case-insensitive matching
    String name = file.getFileName().toString().toLowerCase();
    // Line 30: Find the last dot (handles "archive.tar.gz" correctly)
    int dot = name.lastIndexOf('.');
    // Line 31: No dot means no extension
    if (dot < 0) return FileType.UNKNOWN;

    // Line 33: Extract ".pdf" or ".png" etc.
    String ext = name.substring(dot);
    // Lines 34-35: Check against known extensions
    if (IMAGE_EXTENSIONS.contains(ext)) return FileType.IMAGE;
    if (PDF_EXTENSIONS.contains(ext))   return FileType.PDF;
    // Line 36: Anything else is unknown
    return FileType.UNKNOWN;
}
```

- `lastIndexOf('.')` handles edge cases like `my.file.name.pdf` — it correctly gets `.pdf`.
- `toLowerCase()` makes matching case-insensitive: `REPORT.PDF` → `report.pdf` → `.pdf` → `PDF`.

#### readAsBase64 Method (Lines 45–59)

```java
public static String readAsBase64(Path file, int maxSizeMb) throws IOException {
    // Line 46: Get file size in bytes
    long sizeBytes = Files.size(file);
    // Line 47: Convert MB limit to bytes
    long maxBytes = (long) maxSizeMb * 1024 * 1024;

    // Lines 49-54: Reject oversized files with a descriptive message
    if (sizeBytes > maxBytes) {
        throw new IllegalArgumentException(
                "File %s is %.1f MB, exceeds %d MB limit".formatted(
                        file.getFileName(), sizeBytes / (1024.0 * 1024.0), maxSizeMb
                )
        );
    }

    // Line 57: Read entire file into byte array
    byte[] bytes = Files.readAllBytes(file);
    // Line 58: Encode to base64 string for JSON transport
    return Base64.getEncoder().encodeToString(bytes);
}
```

- **Size check before reading:** `Files.size()` uses filesystem metadata (no I/O). This prevents loading a 500 MB file into memory just to reject it.
- `String.formatted()` is the Java 15+ instance method equivalent of `String.format()`.
- `Base64.getEncoder()` uses standard RFC 4648 encoding — the same encoding Python's `base64.b64decode()` expects.

#### formatSize Method (Lines 71–75)

```java
public static String formatSize(long bytes) {
    if (bytes < 1024) return bytes + " B";                             // 0-1023 → "512 B"
    if (bytes < 1024 * 1024) return "%.1f KB".formatted(bytes / 1024.0);  // 1 KB - 1 MB
    return "%.1f MB".formatted(bytes / (1024.0 * 1024.0));                 // 1 MB+
}
```

Used in CLI status messages: `Sending report.pdf (2.4 MB) to PDF text extraction Lambda...`

---

### 3.6 OutputFormatter.java — Display Formatting

Formats Lambda responses for three output modes.

#### Mode Enum (Line 23)

```java
public enum Mode { JSON, TEXT, SUMMARY }
```

- `JSON` — Pretty-printed raw Lambda response.
- `TEXT` — Extracted text only (for piping: `ocr-client scan f.pdf -o text | wc -w`).
- `SUMMARY` — Human-readable box with stats, timing, and text.

#### Image OCR Print Method (Lines 29–49)

```java
public static void print(ImageOcrResult result, Mode mode, PrintStream out) {
    switch (mode) {
        // Line 31: Serialize the record to pretty JSON using Gson
        case JSON    -> out.println(GSON.toJson(result));
        // Line 32: Text mode — just the text, or "ERROR:" prefix on failure
        case TEXT    -> out.println(result.isSuccess() ? result.text() : "ERROR: " + result.error());
        // Lines 33-47: Summary mode — formatted box with stats
        case SUMMARY -> {
            if (!result.isSuccess()) {
                out.println("❌ Error: " + result.error());
                return;
            }
            out.println("─".repeat(60));               // Unicode box-drawing line
            out.println("  Image OCR Result");
            out.println("─".repeat(60));
            out.printf("  File:       %s%n", result.filename());
            out.printf("  Words:      %,d%n", result.wordCount());  // %,d adds thousands separators
            out.printf("  Characters: %,d%n", result.textLength());
            out.printf("  Time:       %.0f ms%n", result.processingTimeMs());
            out.println("─".repeat(60));
            out.println(result.text());
        }
    }
}
```

- **Switch expression with arrows** (`->`) — Java 21 enhanced switch. No `break` needed, no fall-through.
- **Block case** (`case SUMMARY -> { ... }`) — Uses braces when more than one statement is needed.
- `"─".repeat(60)` — Repeats the Unicode box-drawing character 60 times for a visual separator.
- `%,d` format — Adds locale-specific thousands separators: `1,247` instead of `1247`.
- **Method overloading** — Three `print()` methods with different first parameters (`ImageOcrResult`, `PdfExtractResult`, `PdfOcrResult`). Java dispatches to the right one based on the argument type.

#### PDF OCR Summary (Lines 91–133)

The PDF OCR print method includes the timing breakdown:

```java
if (result.timing() != null) {
    var t = result.timing();         // var infers TimingBreakdown
    out.println();
    out.println("  Timing breakdown:");
    out.printf("    Total pipeline:    %,.0f ms%n", t.pipelineMs());
    out.printf("    Image rendering:   %,.0f ms (avg %.0f ms/page)%n",
            t.totalImageExtractMs(), t.avgExtractPerPageMs());
    out.printf("    OCR processing:    %,.0f ms (avg %.0f ms/page)%n",
            t.totalOcrMs(), t.avgOcrPerPageMs());
}
```

- `var t = result.timing()` — Java 10+ local variable type inference. The compiler infers `TimingBreakdown`.
- The null check guards against responses where `timing` might not be present.

---

### 3.7 LambdaInvoker.java — AWS Lambda Service

The core service that actually calls AWS Lambda.

#### Class Declaration (Line 24)

```java
public class LambdaInvoker implements AutoCloseable {
```

`AutoCloseable` enables the `try-with-resources` pattern: `try (var invoker = ...) { ... }`. When the block exits, `close()` is called automatically, which closes the underlying HTTP connections.

#### Fields (Lines 26–33)

```java
private static final Gson GSON = new GsonBuilder()
        .setPrettyPrinting()
        .create();

private final LambdaClient lambda;          // AWS SDK Lambda client
private final String imageOcrFunction;      // Lambda function name for image OCR
private final String pdfExtractFunction;    // Lambda function name for PDF extraction
private final String pdfOcrFunction;        // Lambda function name for PDF OCR
```

- `GSON` is `static final` — shared across all instances, thread-safe.
- `LambdaClient` is the AWS SDK v2 client. It manages HTTP connections, signing, retries.
- The three function name strings identify which Lambda to invoke.

#### Simple Constructor (Lines 41–46)

```java
public LambdaInvoker(String region,
                     String imageOcrFunction,
                     String pdfExtractFunction,
                     String pdfOcrFunction) {
    this(region, null, imageOcrFunction, pdfExtractFunction, pdfOcrFunction);
}
```

Delegates to the full constructor with `endpointOverride = null`. This is the constructor used in production against real AWS.

#### Full Constructor with Endpoint Override (Lines 55–72)

```java
public LambdaInvoker(String region,
                     String endpointOverride,
                     String imageOcrFunction,
                     String pdfExtractFunction,
                     String pdfOcrFunction) {
    // Line 60: Start building the Lambda client
    var builder = LambdaClient.builder()
            // Line 61: Set the AWS region (e.g., "us-east-1")
            .region(Region.of(region))
            // Line 62: Use the default credential chain (env vars → files → IAM roles)
            .credentialsProvider(DefaultCredentialsProvider.create());

    // Lines 64-66: If a custom endpoint is provided, override the default AWS endpoint
    if (endpointOverride != null && !endpointOverride.isBlank()) {
        builder.endpointOverride(java.net.URI.create(endpointOverride));
    }

    // Line 68: Build the immutable client
    this.lambda = builder.build();
    this.imageOcrFunction = imageOcrFunction;
    this.pdfExtractFunction = pdfExtractFunction;
    this.pdfOcrFunction = pdfOcrFunction;
}
```

**`DefaultCredentialsProvider.create()`** searches for credentials in this order:
1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
2. System properties
3. `~/.aws/credentials` file
4. EC2/ECS instance metadata
5. SSO token cache

**`endpointOverride`** — Replaces the normal `https://lambda.us-east-1.amazonaws.com` with a custom URL like `http://localhost:7878` for LocalStack. The `isBlank()` check handles empty strings from picocli defaults.

#### Test Constructor (Lines 74–83)

```java
LambdaInvoker(LambdaClient lambda, ...) {
    this.lambda = lambda;       // Accept a pre-built (or mocked) client
    ...
}
```

Package-private (no `public` modifier). Used by unit tests to inject a mock `LambdaClient`.

#### Pattern Matching Dispatch — invokeRaw (Lines 95–101)

```java
public String invokeRaw(OcrRequest request) {
    return switch (request) {
        case OcrRequest.ImageOcr img   -> invoke(imageOcrFunction, buildImagePayload(img));
        case OcrRequest.PdfExtract pdf -> invoke(pdfExtractFunction, buildPdfExtractPayload(pdf));
        case OcrRequest.PdfOcr ocr     -> invoke(pdfOcrFunction, buildPdfOcrPayload(ocr));
    };
}
```

This is the heart of the sealed interface + pattern matching design:

1. `switch (request)` — Pattern matches on the sealed type.
2. `case OcrRequest.ImageOcr img` — Checks if the request is an `ImageOcr`, and binds it to `img` as the correct type. No casting needed.
3. Each case calls `invoke()` with the appropriate function name and payload.
4. **No `default` needed** — Because `OcrRequest` is sealed with exactly three implementations, the compiler verifies all cases are covered. If you add a fourth record, this switch won't compile until updated.

#### Typed Invoke Methods (Lines 103–117)

```java
public ImageOcrResult invokeImageOcr(OcrRequest.ImageOcr request) {
    // Line 105: Call Lambda and get raw JSON string
    String json = invoke(imageOcrFunction, buildImagePayload(request));
    // Line 106: Deserialize JSON → typed record
    return GSON.fromJson(json, ImageOcrResult.class);
}
```

`GSON.fromJson()` maps JSON fields to record components using `@SerializedName` annotations. It handles nested objects (`TimingBreakdown`), lists (`List<PageResult>`), and null fields automatically.

#### Payload Builders (Lines 123–143)

```java
public static String buildImagePayload(OcrRequest.ImageOcr req) {
    // Line 124: Create a mutable JSON object
    var obj = new JsonObject();
    // Line 125: Add "image" key matching handler.py's expected field
    obj.addProperty("image", req.image());
    // Line 126: Add "filename" key
    obj.addProperty("filename", req.filename());
    // Line 127: Serialize to JSON string
    return GSON.toJson(obj);
}
```

**Why `JsonObject` instead of serializing the record directly:** The Lambda expects specific JSON keys like `"image"` and `"pdf"` that don't match the record's accessor names. `JsonObject` gives explicit control over the JSON structure.

The PDF OCR builder adds the `dpi` field:

```java
public static String buildPdfOcrPayload(OcrRequest.PdfOcr req) {
    var obj = new JsonObject();
    obj.addProperty("pdf", req.pdf());
    obj.addProperty("filename", req.filename());
    obj.addProperty("dpi", req.dpi());       // Extra field for OCR resolution
    return GSON.toJson(obj);
}
```

#### Core Lambda Invocation (Lines 149–168)

```java
private String invoke(String functionName, String payload) {
    // Lines 150-153: Build the invoke request
    InvokeRequest invokeReq = InvokeRequest.builder()
            .functionName(functionName)                                    // Lambda name or ARN
            .payload(SdkBytes.fromString(payload, StandardCharsets.UTF_8)) // JSON as bytes
            .build();

    // Line 155: Synchronously invoke the Lambda
    InvokeResponse response = lambda.invoke(invokeReq);

    // Lines 157-165: Check for Lambda-level errors
    if (response.functionError() != null && !response.functionError().isEmpty()) {
        throw new LambdaInvocationException(
                "Lambda function error (%s): %s".formatted(
                        response.functionError(),       // "Handled" or "Unhandled"
                        response.payload().asUtf8String() // Error details
                )
        );
    }

    // Line 167: Extract the response payload as a UTF-8 string
    return response.payload().asUtf8String();
}
```

**Two levels of errors:**
1. **Lambda-level errors** (`functionError()`) — The Lambda runtime itself failed (out of memory, timeout, uncaught exception). We throw a `LambdaInvocationException`.
2. **Application-level errors** — The Lambda ran fine but returned `{"error": "No image data"}`. These are in the payload and handled by the caller (checking `result.isSuccess()`).

`SdkBytes.fromString()` converts the JSON string to bytes for the wire. Lambda always exchanges payloads as byte buffers.

---

### 3.8 OcrCli.java — CLI Entry Point

The CLI uses picocli to define subcommands, options, and argument parsing.

#### Root Command (Lines 36–47)

```java
@Command(
        name = "ocr-client",                         // Binary name in help text
        description = "CLI client for OCR Lambda functions",
        version = "ocr-client 1.0.0",                // Shown with --version
        mixinStandardHelpOptions = true,              // Adds --help and --version
        subcommands = {                               // Register the four subcommands
                OcrCli.ScanCommand.class,
                OcrCli.ImageCommand.class,
                OcrCli.PdfExtractCommand.class,
                OcrCli.PdfOcrCommand.class,
        }
)
public class OcrCli implements Runnable {
```

`mixinStandardHelpOptions = true` adds `--help` and `--version` flags automatically. `Runnable` is used because the root command just prints usage (no actual logic).

#### Default Action (Lines 50–56)

```java
@Spec
Model.CommandSpec spec;    // picocli injects the command spec here

@Override
public void run() {
    spec.commandLine().usage(System.out);    // Print help when no subcommand given
}
```

If you type `ocr-client` with no subcommand, it prints the help text.

#### main Method (Lines 58–61)

```java
public static void main(String[] args) {
    // Line 59: Create the CLI, parse args, execute the matched subcommand
    int exitCode = new CommandLine(new OcrCli()).execute(args);
    // Line 60: Exit with the subcommand's return code (0=success, 1=error)
    System.exit(exitCode);
}
```

`CommandLine.execute()` does everything: parses arguments, validates types, invokes the matched subcommand's `call()` method, and returns its exit code.

#### SharedOptions Mixin (Lines 67–102)

```java
static class SharedOptions {
    @Option(names = {"-r", "--region"},
            description = "AWS region (default: ${DEFAULT-VALUE})",
            defaultValue = "${OCR_AWS_REGION:-us-east-1}")     // Env var with fallback
    String region;

    @Option(names = {"-e", "--endpoint"},
            description = "Custom endpoint URL (e.g. http://localhost:7878 for LocalStack)",
            defaultValue = "${OCR_ENDPOINT:-}")                // Empty default = no override
    String endpoint;
    ...
```

**`defaultValue = "${OCR_AWS_REGION:-us-east-1}"`:** Picocli variable interpolation. It checks environment variable `OCR_AWS_REGION` first; if unset, falls back to `us-east-1`. The `:-` syntax is borrowed from shell parameter expansion.

**`@Mixin`:** This class isn't a command itself — it's mixed into every subcommand so they share the same flags without duplication.

```java
    LambdaInvoker buildInvoker() {
        return new LambdaInvoker(region, endpoint, imageFn, pdfFn, pdfOcrFn);
    }
```

Factory method that creates a `LambdaInvoker` wired with whatever options the user provided.

#### Scan Command — Auto-Detection (Lines 108–142)

```java
@Command(name = "scan", description = "Auto-detect file type and call the right Lambda")
static class ScanCommand implements Callable<Integer> {

    @Parameters(index = "0", description = "File to process (image or PDF)")
    Path file;          // picocli automatically converts string args to Path

    @Mixin
    SharedOptions opts; // Pull in all shared flags

    @Option(names = {"--force-ocr"}, description = "Force PDF OCR pipeline even for digital PDFs")
    boolean forceOcr;

    @Override
    public Integer call() throws Exception {
        validateFile(file);

        FileType type = FileUtils.detectType(file);

        // Pattern matching switch on the enum
        return switch (type) {
            case IMAGE   -> processImage(file, opts);
            case PDF     -> forceOcr
                    ? processPdfOcr(file, dpi, opts)    // Force OCR pipeline
                    : processPdfExtract(file, opts);    // Default: text extraction
            case UNKNOWN -> {
                System.err.println("Unsupported file type: " + file.getFileName());
                System.err.println("Supported: PNG, JPG, TIFF, BMP, GIF, WEBP, PDF");
                yield 1;    // "yield" returns a value from a block case in switch expression
            }
        };
    }
}
```

**`Callable<Integer>`** instead of `Runnable` — The `call()` method returns an exit code. `0` = success, `1` = error. picocli propagates this to `System.exit()`.

**`yield 1`** — Inside a block case (`case UNKNOWN -> { ... }`), `yield` is used instead of `return` to provide the switch expression's value. `return` would exit the entire method, but `yield` only provides the value for the expression.

#### Shared Processing Logic (Lines 211–260)

```java
private static int processImage(Path file, SharedOptions opts) throws IOException {
    // Line 212: Read file and base64-encode it
    String b64 = FileUtils.readAsBase64(file, opts.maxSizeMb);
    // Line 213: Get just the filename (not the full path)
    String filename = file.getFileName().toString();

    // Lines 215-216: Status message to stderr (stdout reserved for output)
    System.err.printf("Sending %s (%s) to image OCR Lambda...%n",
            filename, FileUtils.formatSize(Files.size(file)));

    // Lines 218-225: Create invoker, call Lambda, format output
    try (var invoker = opts.buildInvoker()) {       // AutoCloseable — closes on exit
        var request = new OcrRequest.ImageOcr(b64, filename);
        ImageOcrResult result = invoker.invokeImageOcr(request);

        OutputFormatter.print(result, opts.outputMode, System.out);
        maybeSave(result.text(), opts.saveTo);
        return result.isSuccess() ? 0 : 1;          // Exit code
    }
}
```

**`System.err` vs `System.out`:** Status messages go to `stderr`, actual output goes to `stdout`. This lets users pipe output: `ocr-client scan f.pdf -o text | wc -w` — the word count only sees the text, not the "Sending..." message.

**`try (var invoker = ...)`** — Try-with-resources. When the block exits (normally or via exception), `invoker.close()` is called, which closes the HTTP connections to AWS.

#### File Validation (Lines 266–279)

```java
private static void validateFile(Path file) {
    if (!Files.exists(file)) {
        throw new ParameterException(
                new CommandLine(new OcrCli()),
                "File not found: " + file
        );
    }
    if (!Files.isRegularFile(file)) {
        throw new ParameterException(
                new CommandLine(new OcrCli()),
                "Not a regular file: " + file
        );
    }
}
```

`ParameterException` is picocli's way of reporting input errors. It prints the error message plus the usage help.

---

## 4. Running Against LocalStack

#### With Flags

```bash
# Image OCR
java -jar target/ocr-client-1.0.0.jar image receipt.png \
  -e http://localhost:7878 -r us-east-1

# PDF text extraction
java -jar target/ocr-client-1.0.0.jar pdf-extract report.pdf \
  -e http://localhost:7878

# PDF OCR at high resolution
java -jar target/ocr-client-1.0.0.jar pdf-ocr scanned.pdf \
  -e http://localhost:7878 --dpi 600

# Auto-detect with JSON output
java -jar target/ocr-client-1.0.0.jar scan invoice.pdf \
  -e http://localhost:7878 -o json
```

#### With Environment Variables (set once)

```bash
export OCR_ENDPOINT=http://localhost:7878
export OCR_AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export OCR_IMAGE_FUNCTION=ocr-image
export OCR_PDF_FUNCTION=ocr-pdf
export OCR_PDF_OCR_FUNCTION=ocr-pdf-ocr

# Now just:
java -jar target/ocr-client-1.0.0.jar scan invoice.pdf
java -jar target/ocr-client-1.0.0.jar image photo.jpg -o text
java -jar target/ocr-client-1.0.0.jar pdf-ocr scanned.pdf --dpi 600 -s output.txt
```

---

## 5. Running the Tests

### Python Tests (43 tests)

```bash
pip install pytest pymupdf
pytest -v
```

All external dependencies (Tesseract, file I/O) are mocked — no system tools required.

### Java Tests (29 tests)

```bash
mvn test
```

Tests cover: file type detection, base64 encoding, size limits, JSON serialization, payload building, response deserialization, and output formatting. No AWS credentials needed — payload builders and formatters are tested in isolation.

# OCR Lambda Client — Java 21 CLI

A command-line client for invoking the OCR Lambda functions (`handler.py`, `pdf_handler.py`, `pdf_ocr_handler.py`) via the AWS SDK for Java v2.

Built with Java 21 features: sealed interfaces, records, pattern matching switch expressions, and text blocks.

---

## Prerequisites

- **Java 21+** (verify with `java --version`)
- **Maven 3.9+** (verify with `mvn --version`)
- **AWS credentials** configured — via `~/.aws/credentials`, environment variables, IAM role, or SSO
- **Deployed Lambda functions** — the three Python handlers deployed to AWS Lambda

## Build

```bash
# Compile, test, and build fat JAR
mvn clean package

# Skip tests if needed
mvn clean package -DskipTests

# The fat JAR is at target/ocr-client-1.0.0.jar
```

Create an alias for convenience:

```bash
alias ocr-client='java -jar target/ocr-client-1.0.0.jar'
```

## Quick Start

```bash
# Auto-detect file type (image → Tesseract, PDF → text extraction)
ocr-client scan invoice.pdf

# OCR a scanned PDF (render pages to images, then Tesseract)
ocr-client pdf-ocr scanned-document.pdf

# OCR an image
ocr-client image receipt.jpg

# Extract text from a digital PDF
ocr-client pdf-extract report.pdf
```

## Commands

### `scan` — Auto-detect and process

Inspects the file extension and routes to the appropriate Lambda:

```bash
# Digital PDF → pdf_handler.py
ocr-client scan report.pdf

# Scanned PDF → pdf_ocr_handler.py (with --force-ocr)
ocr-client scan scanned.pdf --force-ocr --dpi 600

# Image → handler.py
ocr-client scan photo.png
```

### `image` — Image OCR

Calls `handler.py` → Tesseract OCR:

```bash
ocr-client image screenshot.png
ocr-client image receipt.jpg --output json
ocr-client image whiteboard.tiff --save-to notes.txt
```

### `pdf-extract` — Digital PDF text extraction

Calls `pdf_handler.py` → PyMuPDF text layer extraction:

```bash
ocr-client pdf-extract annual-report.pdf
ocr-client pdf-extract contract.pdf --output text --save-to contract.txt
```

### `pdf-ocr` — Scanned PDF OCR pipeline

Calls `pdf_ocr_handler.py` → PyMuPDF render + Tesseract per page:

```bash
ocr-client pdf-ocr old-scan.pdf
ocr-client pdf-ocr fax.pdf --dpi 600 --output summary
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `-o, --output` | Output format: `summary`, `text`, `json` | `summary` |
| `-s, --save-to FILE` | Save extracted text to a file | — |
| `-r, --region` | AWS region | `us-east-1` |
| `--image-fn` | Image OCR Lambda function name | `ocr-image` |
| `--pdf-fn` | PDF extract Lambda function name | `ocr-pdf` |
| `--pdf-ocr-fn` | PDF OCR Lambda function name | `ocr-pdf-ocr` |
| `--dpi` | Render DPI for PDF OCR | `300` |
| `--max-size` | Max input file size in MB | `10` |
| `--force-ocr` | Force OCR pipeline for PDFs (scan command) | `false` |

## Environment Variables

All Lambda function names and the AWS region can be configured via environment variables:

```bash
export OCR_AWS_REGION=eu-west-1
export OCR_IMAGE_FUNCTION=my-image-ocr
export OCR_PDF_FUNCTION=my-pdf-extract
export OCR_PDF_OCR_FUNCTION=my-pdf-ocr
```

## Output Formats

### `--output summary` (default)

Human-readable with stats and timing:

```
────────────────────────────────────────────────────────────
  PDF OCR Pipeline Result
────────────────────────────────────────────────────────────
  File:       scan.pdf
  Pages:      3
  DPI:        300
  Words:      1,247
  Characters: 7,891
  PDF size:   1.2 MB

  Timing breakdown:
    Total pipeline:    4,520 ms
    Image rendering:   1,200 ms (avg 400 ms/page)
    OCR processing:    3,100 ms (avg 1033 ms/page)
────────────────────────────────────────────────────────────

── Page 1 (412 words | render 380 ms | OCR 1050 ms) ──
[extracted text here...]
```

### `--output text`

Raw extracted text only (ideal for piping):

```bash
ocr-client scan report.pdf --output text | wc -w
ocr-client image receipt.jpg --output text | grep "Total"
```

### `--output json`

Full Lambda response as pretty-printed JSON:

```bash
ocr-client scan doc.pdf --output json | jq '.page_count'
```

## Project Structure

```
ocr-client/
├── pom.xml                               # Maven build with shade plugin
├── src/
│   ├── main/java/com/ocr/
│   │   ├── client/
│   │   │   ├── OcrCli.java              # picocli CLI with subcommands
│   │   │   └── LambdaInvoker.java       # AWS Lambda invocation service
│   │   ├── model/
│   │   │   ├── OcrRequest.java          # Sealed interface + request records
│   │   │   └── OcrResponse.java         # Response records with @SerializedName
│   │   └── util/
│   │       ├── FileUtils.java           # File I/O, base64, type detection
│   │       └── OutputFormatter.java     # JSON / text / summary formatting
│   └── test/java/com/ocr/
│       ├── FileUtilsTest.java
│       ├── ModelAndPayloadTest.java
│       └── OutputFormatterTest.java
```

## Java 21 Features Used

| Feature | Where |
|---------|-------|
| **Sealed interfaces** | `OcrRequest` — exhaustive type hierarchy for the 3 request kinds |
| **Records** | All request/response models — immutable data carriers with auto-generated methods |
| **Pattern matching switch** | `LambdaInvoker.invokeRaw()`, `ScanCommand.call()` — exhaustive dispatch |
| **Switch expressions** | Throughout — concise control flow returning values |
| **Text blocks** | Test JSON literals — multi-line strings with `"""` |
| **`String.formatted()`** | All string formatting — instance method alternative to `String.format()` |
| **`var` local inference** | Used throughout for readability |

## Running Tests

```bash
mvn test
```

## Troubleshooting

**"No credential provider" error**: Ensure AWS credentials are configured. The client uses `DefaultCredentialsProvider` which checks (in order): environment variables, system properties, `~/.aws/credentials`, EC2/ECS instance roles, SSO.

**"Function not found" error**: Verify the Lambda function names match your deployment. Use `--image-fn`, `--pdf-fn`, `--pdf-ocr-fn` flags or environment variables to override.

**Timeout on large PDFs**: Lambda has a 15-minute max timeout. For very large PDFs via `pdf-ocr`, consider reducing DPI (`--dpi 150`) or splitting the PDF first.
