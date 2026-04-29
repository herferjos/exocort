#!/usr/bin/env bash
# Builds all services as standalone PyInstaller executables.
# Usage: ./build_executables.sh [output_dir]
# Default output: /Users/herferjos/Projects/exocort-app/assets/services
set -euo pipefail

SERVICES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${1:-/Users/herferjos/Projects/exocort-app/assets/services}"

mkdir -p "$OUTPUT_DIR"

build_service() {
    local service="$1"
    local spec="$2"
    echo "▶ Building $service ($spec)..."
    cd "$SERVICES_DIR/$service"
    uv run --with pyinstaller pyinstaller \
        ".pyinstaller-spec/$spec.spec" \
        --distpath "$OUTPUT_DIR" \
        --workpath ".pyinstaller-build" \
        --noconfirm
    echo "✓ $spec → $OUTPUT_DIR/$spec"
}

build_service mac_ocr       mac-ocr-service
build_service mac_asr       mac-asr-service
build_service faster_whisper faster-whisper-service
build_service llama_cpp     llama-cpp-service

echo ""
echo "Done. Executables in: $OUTPUT_DIR"
ls -lh "$OUTPUT_DIR"
