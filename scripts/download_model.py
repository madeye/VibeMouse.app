#!/usr/bin/env python3
"""Download SenseVoice ONNX model files for offline bundling.

Downloads from ModelScope and copies the required files into
vibemouse/models/SenseVoiceSmall/ so the app works without internet.

Usage:
    python scripts/download_model.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ONNX_MODEL_ID = "iic/SenseVoiceSmall-onnx"
TOKENIZER_MODEL_ID = "iic/SenseVoiceSmall"

ONNX_FILES = [
    "model_quant.onnx",
    "am.mvn",
    "config.yaml",
    "configuration.json",
    "tokens.json",
]
TOKENIZER_FILE = "chn_jpn_yue_eng_ko_spectok.bpe.model"

TARGET_DIR = Path(__file__).resolve().parent.parent / "vibemouse" / "models" / "SenseVoiceSmall"


def download_snapshot(model_id: str) -> Path:
    try:
        from modelscope.hub.snapshot_download import snapshot_download
    except ImportError:
        print("Error: modelscope is required. Install with: pip install modelscope", file=sys.stderr)
        sys.exit(1)

    print(f"Downloading {model_id} ...")
    path = snapshot_download(model_id)
    return Path(path)


def main() -> None:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    # Download ONNX model snapshot
    onnx_dir = download_snapshot(ONNX_MODEL_ID)
    for filename in ONNX_FILES:
        src = onnx_dir / filename
        dst = TARGET_DIR / filename
        if not src.exists():
            print(f"Warning: {filename} not found in {onnx_dir}", file=sys.stderr)
            continue
        shutil.copy2(src, dst)
        size_mb = dst.stat().st_size / (1024 * 1024)
        print(f"  Copied {filename} ({size_mb:.1f} MB)")

    # Download tokenizer from the base model
    tokenizer_dir = download_snapshot(TOKENIZER_MODEL_ID)
    src = tokenizer_dir / TOKENIZER_FILE
    dst = TARGET_DIR / TOKENIZER_FILE
    if not src.exists():
        print(f"Warning: {TOKENIZER_FILE} not found in {tokenizer_dir}", file=sys.stderr)
    else:
        shutil.copy2(src, dst)
        size_kb = dst.stat().st_size / 1024
        print(f"  Copied {TOKENIZER_FILE} ({size_kb:.0f} KB)")

    # Verify
    print("\nVerifying files in", TARGET_DIR)
    all_expected = ONNX_FILES + [TOKENIZER_FILE]
    missing = [f for f in all_expected if not (TARGET_DIR / f).exists()]
    if missing:
        print(f"Missing files: {missing}", file=sys.stderr)
        sys.exit(1)

    print("All model files present. Ready for bundling.")


if __name__ == "__main__":
    main()
