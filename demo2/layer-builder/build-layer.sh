#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  Builds a Lambda Layer zip containing:
#    - tesseract binary + shared libs + eng.traineddata
#    - pdftoppm (poppler-utils) binary + shared libs
#
#  Uses Amazon Linux 2023 (same as Lambda python3.11 runtime)
#  so all binaries are ABI-compatible.
#
#  Output: /out/layer.zip  (mounted volume)
# ─────────────────────────────────────────────────────────────
set -euo pipefail

echo "╔══════════════════════════════════════════════╗"
echo "║  Building Tesseract Lambda Layer             ║"
echo "╚══════════════════════════════════════════════╝"

# ── Install Tesseract + Poppler from AL2023 repos ──
echo "→ Installing tesseract + poppler-utils..."
dnf install -y \
    tesseract \
    tesseract-langpack-eng \
    poppler-utils \
    zip \
    findutils \
    > /dev/null 2>&1

echo "  tesseract: $(tesseract --version 2>&1 | head -1)"
echo "  pdftoppm:  $(pdftoppm -v 2>&1 | head -1 || echo ok)"

# ── Create layer directory structure ──
# Lambda layers extract to /opt, so we mirror that layout:
#   /opt/bin/          ← binaries
#   /opt/lib/          ← shared libraries
#   /opt/share/tessdata/ ← OCR training data
LAYER_DIR="/tmp/layer"
mkdir -p "${LAYER_DIR}/bin" "${LAYER_DIR}/lib" "${LAYER_DIR}/share/tessdata"

# ── Copy binaries ──
echo "→ Copying binaries..."
cp "$(which tesseract)" "${LAYER_DIR}/bin/"
cp "$(which pdftoppm)"  "${LAYER_DIR}/bin/"

# ── Copy tessdata (eng) ──
echo "→ Copying tessdata..."
TESSDATA_SRC=$(find /usr/share -name "eng.traineddata" 2>/dev/null | head -1)
if [ -z "$TESSDATA_SRC" ]; then
    echo "  ✗ eng.traineddata not found!"
    find /usr/share/tesseract* -type f 2>/dev/null || true
    exit 1
fi
TESSDATA_DIR=$(dirname "$TESSDATA_SRC")
cp "${TESSDATA_DIR}/eng.traineddata" "${LAYER_DIR}/share/tessdata/"
# Copy OSD data if present (for page orientation detection)
[ -f "${TESSDATA_DIR}/osd.traineddata" ] && \
    cp "${TESSDATA_DIR}/osd.traineddata" "${LAYER_DIR}/share/tessdata/" || true
echo "  ✓ tessdata: $(ls ${LAYER_DIR}/share/tessdata/)"

# ── Copy shared libraries (resolve all dependencies) ──
echo "→ Resolving shared library dependencies..."
collect_libs() {
    local binary="$1"
    ldd "$binary" 2>/dev/null | grep "=> /" | awk '{print $3}' | sort -u
}

# Collect all unique library paths needed by our binaries
LIBS_NEEDED=$(
    {
        collect_libs "$(which tesseract)"
        collect_libs "$(which pdftoppm)"
    } | sort -u
)

# Copy libraries that are NOT already in the Lambda base image
# (Lambda base has glibc, libstdc++, etc. — we skip those)
SKIP_LIBS="linux-vdso|ld-linux|libpthread|libdl|librt|libm\.so|libc\.so|libstdc\+\+|libgcc_s"
for lib in $LIBS_NEEDED; do
    BASENAME=$(basename "$lib")
    if echo "$BASENAME" | grep -qE "$SKIP_LIBS"; then
        continue  # Skip libs already in Lambda base
    fi
    cp -L "$lib" "${LAYER_DIR}/lib/" 2>/dev/null || true
done

echo "  ✓ Libraries: $(ls ${LAYER_DIR}/lib/ | wc -l) files"
ls -1 "${LAYER_DIR}/lib/" | head -20
[ "$(ls ${LAYER_DIR}/lib/ | wc -l)" -gt 20 ] && echo "  ... and more"

# ── Create layer zip ──
echo "→ Creating layer zip..."
cd "${LAYER_DIR}"
zip -r9 /out/layer.zip . > /dev/null 2>&1
echo "  ✓ Layer zip: $(du -sh /out/layer.zip | cut -f1)"

# ── Summary ──
echo ""
echo "Layer contents:"
echo "  bin/:   $(ls bin/)"
echo "  lib/:   $(ls lib/ | wc -l) shared libraries"
echo "  share/: $(ls share/tessdata/)"
echo ""
echo "✓ Layer build complete!"
