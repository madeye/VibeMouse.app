"""Load macOS app preferences into os.environ before config.py reads them.

Reads ``~/Library/Application Support/VibeMouse/config.json`` and injects
each ``VIBEMOUSE_*`` key via ``os.environ.setdefault`` so that environment
variables set externally always win.  Also applies sensible macOS defaults.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "VibeMouse"
_CONFIG_PATH = _APP_SUPPORT_DIR / "config.json"

_MACOS_DEFAULTS: dict[str, str] = {
    "VIBEMOUSE_AUTO_PASTE": "true",
    "VIBEMOUSE_PREWARM_ON_START": "true",
    "VIBEMOUSE_BACKEND": "funasr_onnx",
    "VIBEMOUSE_DEVICE": "cpu",
    "VIBEMOUSE_FALLBACK_CPU": "true",
}


def load_preferences_into_environ(
    *,
    config_path: Path | None = None,
) -> None:
    """Populate ``os.environ`` from *config_path* (JSON) and macOS defaults.

    Values already present in the environment are never overwritten.
    """
    path = config_path if config_path is not None else _CONFIG_PATH

    user_prefs: dict[str, str] = {}
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for key, value in raw.items():
                    str_key = str(key).strip()
                    if str_key.startswith("VIBEMOUSE_"):
                        user_prefs[str_key] = str(value)
        except (json.JSONDecodeError, OSError):
            pass

    for key, value in user_prefs.items():
        os.environ.setdefault(key, value)

    for key, value in _MACOS_DEFAULTS.items():
        os.environ.setdefault(key, value)


def save_preference(
    key: str,
    value: str,
    *,
    config_path: Path | None = None,
) -> None:
    """Persist a single ``VIBEMOUSE_*`` preference to disk and environment.

    Non-``VIBEMOUSE_`` keys are silently ignored.
    """
    key = key.strip()
    if not key.startswith("VIBEMOUSE_"):
        return

    path = config_path if config_path is not None else _CONFIG_PATH

    existing: dict[str, str] = {}
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                existing = {str(k): str(v) for k, v in raw.items()}
        except (json.JSONDecodeError, OSError):
            pass

    existing[key] = value

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    os.environ[key] = value
