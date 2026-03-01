from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


def _read_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _read_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError as error:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from error


def _read_button(name: str, default: str) -> str:
    value = os.getenv(name, default).strip().lower()
    if value not in {"x1", "x2"}:
        raise ValueError(f"{name} must be either 'x1' or 'x2', got {value!r}")
    return value


def _require_positive(name: str, value: int) -> int:
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer, got {value}")
    return value


def _require_non_negative(name: str, value: int) -> int:
    if value < 0:
        raise ValueError(f"{name} must be a non-negative integer, got {value}")
    return value


def _read_choice(name: str, default: str, allowed: set[str]) -> str:
    value = os.getenv(name, default).strip().lower()
    if value not in allowed:
        options = ", ".join(sorted(allowed))
        raise ValueError(f"{name} must be one of: {options}; got {value!r}")
    return value


@dataclass(frozen=True)
class AppConfig:
    sample_rate: int
    channels: int
    dtype: str
    transcriber_backend: str
    model_name: str
    device: str
    language: str
    use_itn: bool
    enable_vad: bool
    vad_max_single_segment_ms: int
    merge_vad: bool
    merge_length_s: int
    fallback_to_cpu: bool
    button_debounce_ms: int
    enter_mode: str
    auto_paste: bool
    trust_remote_code: bool
    front_button: str
    rear_button: str
    temp_dir: Path


def load_config() -> AppConfig:
    temp_dir = Path(
        os.getenv("VIBEMOUSE_TEMP_DIR", str(Path(tempfile.gettempdir()) / "vibemouse"))
    )

    sample_rate = _require_positive(
        "VIBEMOUSE_SAMPLE_RATE", _read_int("VIBEMOUSE_SAMPLE_RATE", 16000)
    )
    channels = _require_positive(
        "VIBEMOUSE_CHANNELS", _read_int("VIBEMOUSE_CHANNELS", 1)
    )
    vad_max_segment_ms = _require_positive(
        "VIBEMOUSE_VAD_MAX_SEGMENT_MS", _read_int("VIBEMOUSE_VAD_MAX_SEGMENT_MS", 30000)
    )
    merge_length_s = _require_positive(
        "VIBEMOUSE_MERGE_LENGTH_S", _read_int("VIBEMOUSE_MERGE_LENGTH_S", 15)
    )
    front_button = _read_button("VIBEMOUSE_FRONT_BUTTON", "x1")
    rear_button = _read_button("VIBEMOUSE_REAR_BUTTON", "x2")
    if front_button == rear_button:
        raise ValueError("VIBEMOUSE_FRONT_BUTTON and VIBEMOUSE_REAR_BUTTON must differ")
    button_debounce_ms = _require_non_negative(
        "VIBEMOUSE_BUTTON_DEBOUNCE_MS",
        _read_int("VIBEMOUSE_BUTTON_DEBOUNCE_MS", 150),
    )
    enter_mode = _read_choice(
        "VIBEMOUSE_ENTER_MODE",
        "enter",
        {"enter", "ctrl_enter", "shift_enter", "none"},
    )

    return AppConfig(
        sample_rate=sample_rate,
        channels=channels,
        dtype=os.getenv("VIBEMOUSE_DTYPE", "float32"),
        transcriber_backend=os.getenv("VIBEMOUSE_BACKEND", "auto").strip().lower(),
        model_name=os.getenv("VIBEMOUSE_MODEL", "iic/SenseVoiceSmall"),
        device=os.getenv("VIBEMOUSE_DEVICE", "cpu"),
        language=os.getenv("VIBEMOUSE_LANGUAGE", "auto"),
        use_itn=_read_bool("VIBEMOUSE_USE_ITN", True),
        enable_vad=_read_bool("VIBEMOUSE_ENABLE_VAD", True),
        vad_max_single_segment_ms=vad_max_segment_ms,
        merge_vad=_read_bool("VIBEMOUSE_MERGE_VAD", True),
        merge_length_s=merge_length_s,
        fallback_to_cpu=_read_bool("VIBEMOUSE_FALLBACK_CPU", True),
        button_debounce_ms=button_debounce_ms,
        enter_mode=enter_mode,
        auto_paste=_read_bool("VIBEMOUSE_AUTO_PASTE", False),
        trust_remote_code=_read_bool("VIBEMOUSE_TRUST_REMOTE_CODE", False),
        front_button=front_button,
        rear_button=rear_button,
        temp_dir=temp_dir,
    )
