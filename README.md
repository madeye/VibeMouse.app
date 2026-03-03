# VibeMouse

Mouse-side-button voice input for macOS VibeCoding.

## What This Project Does

VibeMouse binds your coding speech workflow to mouse side buttons on macOS:
- Front side button: start/stop recording
- Rear side button while idle: send Enter
- Rear side button while recording: stop recording and route transcript to OpenClaw

Core goals are low friction, stable daily use, and graceful fallback when any subsystem fails.

## Runtime Architecture

The runtime is event-driven and split by responsibility:

1. `vibemouse/main.py`
   - CLI entry (`run` / `doctor`)
2. `vibemouse/app.py`
   - Orchestrates button events, recording state, transcription workers, and final output routing
3. `vibemouse/mouse_listener.py`
   - Captures side buttons and gestures via NSEvent global monitor (Quartz/AppKit)
4. `vibemouse/audio.py`
   - Records audio to temp WAV via sounddevice
5. `vibemouse/transcriber.py`
   - SenseVoice ASR backend selection and transcription (ONNX default, optional PyTorch)
6. `vibemouse/output.py`
   - Text typing / clipboard / OpenClaw dispatch, with fallback and reason tracking
7. `vibemouse/system_integration.py`
   - macOS platform integration via Quartz CGEvent APIs, AppKit NSWorkspace, and ApplicationServices accessibility
8. `vibemouse/doctor.py`
   - Built-in diagnostics for env, OpenClaw, accessibility permissions, and audio input

## Quick Start

### Requirements

- macOS 13+ (Ventura or later)
- Python 3.10+
- Grant Accessibility permission to your terminal in System Settings > Privacy & Security > Accessibility

### Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

Default install uses ONNX for a smaller deployment footprint.

Optional backends:
- PyTorch/FunASR (GPU-capable): `pip install -e ".[pt]"`
- Intel NPU/OpenVINO: `pip install -e ".[npu]"`

### Run

```bash
vibemouse
```

## Default Mapping and State Logic

- `VIBEMOUSE_FRONT_BUTTON` default: `x1`
- `VIBEMOUSE_REAR_BUTTON` default: `x2`

State matrix:
- Idle + rear press -> Enter (`VIBEMOUSE_ENTER_MODE`)
- Recording + rear press -> stop recording + OpenClaw dispatch

If your hardware labels are reversed:

```bash
export VIBEMOUSE_FRONT_BUTTON=x2
export VIBEMOUSE_REAR_BUTTON=x1
```

## OpenClaw Integration

OpenClaw route is explicit and configurable:
- `VIBEMOUSE_OPENCLAW_COMMAND` (default `openclaw`)
- `VIBEMOUSE_OPENCLAW_AGENT` (default `main`)
- `VIBEMOUSE_OPENCLAW_TIMEOUT_S` (default `20.0`)
- `VIBEMOUSE_OPENCLAW_RETRIES` (default `0`)

Dispatch behavior:
- Fast fire-and-forget spawn to avoid blocking UI interaction
- Route result includes reason (`dispatched`, `dispatched_after_retry_*`, `spawn_error:*`, etc.)
- Clipboard fallback if command is invalid or spawn fails

Deployment tip: if you run your own local assistant setup, set
`VIBEMOUSE_OPENCLAW_AGENT` to your own assistant ID.

## Built-in Doctor

Run diagnostics:

```bash
vibemouse doctor
```

Apply safe auto-fixes first, then re-check:

```bash
vibemouse doctor --fix
```

Current checks include:
- Config load validity
- OpenClaw command resolution + agent existence
- Microphone input availability
- macOS Accessibility permission status
- pyobjc framework availability

Exit code is non-zero when any `FAIL` check exists.

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

### OpenClaw route not working

```bash
openclaw agent --agent main --message "ping" --json
vibemouse doctor
```

### No audio input

Check that your microphone is available and not muted. Run `vibemouse doctor` to verify input device detection.

## License

Source code is licensed under Apache-2.0. See `LICENSE`.

Third-party and model asset notices: `THIRD_PARTY_NOTICES.md`.
