# VibeMouse

Mouse-side-button voice input for macOS VibeCoding.

## What This Project Does

VibeMouse binds your coding speech workflow to mouse side buttons on macOS:
- Front side button: start/stop recording
- Rear side button while idle: send Enter
- Rear side button while recording: stop recording and transcribe

Core goals are low friction, stable daily use, and graceful fallback when any subsystem fails.

## Runtime Architecture

The runtime is event-driven and split by responsibility:

1. `vibemouse/app.py`
   - Orchestrates button events, recording state, transcription workers, and final output routing
3. `vibemouse/mouse_listener.py`
   - Captures side buttons and gestures via NSEvent global monitor (Quartz/AppKit)
4. `vibemouse/audio.py`
   - Records audio to temp WAV via sounddevice
5. `vibemouse/transcriber.py`
   - SenseVoice ASR transcription via ONNX Runtime
6. `vibemouse/output.py`
   - Text typing / clipboard dispatch, with fallback and reason tracking
7. `vibemouse/system_integration.py`
   - macOS platform integration via Quartz CGEvent APIs, AppKit NSWorkspace, and ApplicationServices accessibility

## Quick Start

### Requirements

- macOS 13+ (Ventura or later)
- Python 3.10+
- Xcode Command Line Tools (`xcode-select --install`)

### Build VibeMouse.app

One-step build (creates venv, installs deps, downloads model, runs PyInstaller):

```bash
git clone https://github.com/anthropics/VibeMouse.app.git
cd VibeMouse.app
./scripts/build_app.sh
```

Or step by step:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev,download]"

# Download the SenseVoice ONNX model for offline use
python scripts/download_model.py

# Build the .app bundle (uses VibeMouse.spec)
pyinstaller --noconfirm VibeMouse.spec
```

The built app is at `dist/VibeMouse.app`. The bundle includes a complete Python runtime — users do not need Python installed.

### Install

```bash
cp -R dist/VibeMouse.app /Applications/
```

### Run

Double-click **VibeMouse** in `/Applications`, or:

```bash
open /Applications/VibeMouse.app
```

VibeMouse runs as a menu-bar accessory (no Dock icon). Use the menu-bar icon to select input devices, toggle Start at Login, or quit.

### Permissions

On first launch, grant these in **System Settings > Privacy & Security**:

- **Accessibility** — required for mouse side-button capture and keyboard synthesis
- **Microphone** — required for audio recording

## Default Mapping and State Logic

- `VIBEMOUSE_FRONT_BUTTON` default: `x1`
- `VIBEMOUSE_REAR_BUTTON` default: `x2`

State matrix:
- Idle + rear press -> Enter (`VIBEMOUSE_ENTER_MODE`)
- Recording + rear press -> stop recording + transcribe

If your hardware labels are reversed:

```bash
export VIBEMOUSE_FRONT_BUTTON=x2
export VIBEMOUSE_REAR_BUTTON=x1
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `VIBEMOUSE_ENTER_MODE` | `enter` | Rear-button submit mode (`enter`, `ctrl_enter`, `shift_enter`, `none`) |
| `VIBEMOUSE_AUTO_PASTE` | `false` | Auto paste when route falls back to clipboard |
| `VIBEMOUSE_GESTURES_ENABLED` | `false` | Enable gesture recognition |
| `VIBEMOUSE_GESTURE_TRIGGER_BUTTON` | `rear` | Gesture trigger (`front`, `rear`, `right`) |
| `VIBEMOUSE_GESTURE_THRESHOLD_PX` | `120` | Gesture movement threshold |
| `VIBEMOUSE_PREWARM_ON_START` | `true` | Preload ASR on startup to reduce first-use latency |
| `VIBEMOUSE_PREWARM_DELAY_S` | `0.0` | Delay ASR prewarm after startup to improve initial responsiveness |
| `VIBEMOUSE_STATUS_FILE` | `$TMPDIR/vibemouse-status.json` | Runtime status for bars/widgets |

Full configuration source of truth: `vibemouse/config.py`.

## Troubleshooting

### Side buttons not detected

Grant Accessibility permission to your terminal app in System Settings > Privacy & Security > Accessibility, then restart the terminal.

### No audio input

Check that your microphone is available and not muted.

## License

Source code is licensed under Apache-2.0. See `LICENSE`.

Third-party and model asset notices: `THIRD_PARTY_NOTICES.md`.
