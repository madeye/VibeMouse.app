# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VibeMouse is a macOS mouse side-button voice input daemon. It binds speech-to-text to mouse side buttons: front button toggles recording, rear button sends Enter when idle or stops recording and transcribes when recording. ASR uses SenseVoice (ONNX-first, optional PyTorch backend). Platform integration uses Quartz/AppKit via pyobjc.

## Build & Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .                  # ONNX-only (default), includes pyobjc
pip install -e ".[pt]"            # + PyTorch/FunASR backend
pip install -e ".[npu]"           # + Intel NPU/OpenVINO
```

## Testing

```bash
python -m pytest tests/                     # all tests
python -m pytest tests/test_config.py       # single test file
python -m pytest tests/test_config.py -k test_defaults_disable_trust_remote_code  # single test
```

Tests use `unittest` with `unittest.mock`. No external test fixtures or CI-specific setup required.

## Architecture

### Event-driven runtime flow

`macos_entry.py` → `app.py (VoiceMouseApp)` → wires together all subsystems:
- **Mouse input**: `SideButtonListener` (NSEvent global monitor via Quartz/AppKit) fires `_on_front_press` / `_on_rear_press` / `_on_gesture` callbacks
- **Audio**: `AudioRecorder` captures mic to temp WAV via sounddevice
- **Transcription**: `SenseVoiceTranscriber` with lazy-loaded backend (`_FunASRONNXBackend` or `_FunASRBackend`), runs in daemon threads under `_transcribe_lock`
- **Output routing**: `TextOutput.inject_or_clipboard()` routes text to the focused app, clipboard, or paste. Falls back clipboard → typed → pasted with reason tracking

### Platform integration

`system_integration.py` defines the `SystemIntegration` protocol. `MacOSSystemIntegration` is the sole implementation, using Quartz CGEvent APIs for keyboard synthesis, AppKit NSWorkspace for active window detection, and ApplicationServices accessibility APIs for text input focus detection.

`create_system_integration()` returns a `MacOSSystemIntegration` instance.

### Configuration

All config is via environment variables (`VIBEMOUSE_*`), parsed in `config.py` into a frozen `AppConfig` dataclass. `config.py` is the source of truth for defaults and validation.

### Transcriber backend selection

`transcriber.py` supports three `VIBEMOUSE_BACKEND` values: `funasr_onnx` (default, CPU), `funasr` (PyTorch, GPU-capable), `auto` (tries ONNX first on CPU/NPU, PyTorch first on CUDA, with cross-fallback). All backends lazy-load models on first use or via prewarm.
