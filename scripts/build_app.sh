#!/usr/bin/env bash
# build_app.sh — Build VibeMouse.app with embedded Python runtime.
#
# Usage:
#   ./scripts/build_app.sh            # full build (install deps + bundle)
#   ./scripts/build_app.sh --skip-deps # skip pip install, just run PyInstaller
#
# Output:  dist/VibeMouse.app
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

SKIP_DEPS=false
for arg in "$@"; do
  case "$arg" in
    --skip-deps) SKIP_DEPS=true ;;
    -h|--help)
      echo "Usage: $0 [--skip-deps]"
      echo "  --skip-deps   Skip pip install, just run PyInstaller"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 1
      ;;
  esac
done

# ---------- pre-flight checks ----------
if [[ "$(uname)" != "Darwin" ]]; then
  echo "Error: This script must be run on macOS." >&2
  exit 1
fi

if ! command -v python3 &>/dev/null; then
  echo "Error: python3 not found. Install Python 3.10+ first." >&2
  exit 1
fi

# ---------- virtualenv ----------
VENV="$ROOT/.venv"
if [[ ! -d "$VENV" ]]; then
  echo "==> Creating virtualenv at $VENV"
  python3 -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

# ---------- dependencies ----------
if [[ "$SKIP_DEPS" == false ]]; then
  echo "==> Installing dependencies"
  pip install -U pip
  pip install -e ".[dev,download]"
fi

# ---------- model ----------
MODEL_DIR="$ROOT/vibemouse/models/SenseVoiceSmall"
if [[ ! -f "$MODEL_DIR/model_quant.onnx" ]]; then
  echo "==> Downloading SenseVoice ONNX model"
  python scripts/download_model.py
fi

# ---------- build ----------
echo "==> Running PyInstaller via VibeMouse.spec"
pyinstaller --noconfirm VibeMouse.spec

# ---------- result ----------
APP="$ROOT/dist/VibeMouse.app"
if [[ -d "$APP" ]]; then
  echo ""
  echo "Build succeeded: $APP"
  echo ""
  echo "Install:"
  echo "  cp -R dist/VibeMouse.app /Applications/"
  echo ""
  echo "Run:"
  echo "  open /Applications/VibeMouse.app"
else
  echo "Error: build failed — dist/VibeMouse.app not found." >&2
  exit 1
fi
