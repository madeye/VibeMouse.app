#!/usr/bin/env bash
# Build VibeMouse.app using PyInstaller.
#
# Usage:
#   bash build/build_macos_app.sh
#
# Prerequisites:
#   - Python 3.10+ virtualenv activated (or will be created in .venv)
#   - macOS 12+

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

# Ensure virtualenv
if [ -z "${VIRTUAL_ENV:-}" ]; then
    if [ ! -d .venv ]; then
        echo "Creating virtualenv..."
        python3 -m venv .venv
    fi
    source .venv/bin/activate
fi

echo "Installing dependencies..."
pip install -e ".[dev,download]" --quiet

echo "Downloading model (if not already present)..."
if [ ! -d "$PROJECT_DIR/vibemouse/models/SenseVoiceSmall/SenseVoiceSmall_ANE.mlpackage" ]; then
    python "$PROJECT_DIR/scripts/download_model.py"
else
    echo "  Model already present, skipping download."
fi

echo "Building VibeMouse.app..."
pyinstaller build/VibeMouse.spec \
    --distpath "$PROJECT_DIR/dist" \
    --workpath "$PROJECT_DIR/build/pyinstaller_work" \
    --noconfirm

SIGN_IDENTITY="${VIBEMOUSE_SIGN_IDENTITY:-Apple Development: Chao Lv (345Y8TX7HZ)}"

echo "Code signing VibeMouse.app..."
codesign --deep --force --options runtime \
    --timestamp \
    --entitlements "$PROJECT_DIR/entitlements.plist" \
    --sign "$SIGN_IDENTITY" \
    "$PROJECT_DIR/dist/VibeMouse.app"

echo ""
echo "Build complete: $PROJECT_DIR/dist/VibeMouse.app"
echo ""
echo "To test:"
echo "  open dist/VibeMouse.app"
