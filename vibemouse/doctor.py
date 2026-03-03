from __future__ import annotations

import importlib
import json
import shlex
import shutil
import subprocess
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from vibemouse.config import AppConfig, load_config


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    detail: str


def run_doctor(*, apply_fixes: bool = False) -> int:
    if apply_fixes:
        _apply_doctor_fixes()

    checks: list[DoctorCheck] = []

    config_check, config = _check_config_load()
    checks.append(config_check)

    if config is not None:
        checks.extend(_check_openclaw(config))

    checks.append(_check_audio_input(config))
    checks.append(_check_input_device_permissions())
    checks.append(_check_macos_pyobjc())
    checks.append(_check_macos_accessibility_permission())
    checks.append(_check_macos_app_bundle())
    checks.append(_check_macos_launchagent_state())

    _print_checks(checks)

    fail_count = sum(1 for check in checks if check.status == "fail")
    warn_count = sum(1 for check in checks if check.status == "warn")
    print(f"Doctor summary: {len(checks)} checks, {fail_count} fail, {warn_count} warn")
    return 1 if fail_count else 0


def _apply_doctor_fixes() -> None:
    _ensure_macos_launchagent_loaded()


def _check_config_load() -> tuple[DoctorCheck, AppConfig | None]:
    try:
        config = load_config()
    except Exception as error:
        return (
            DoctorCheck(
                name="config",
                status="fail",
                detail=f"failed to load config: {error}",
            ),
            None,
        )

    return (
        DoctorCheck(
            name="config",
            status="ok",
            detail=(
                "loaded "
                + f"front={config.front_button}, rear={config.rear_button}, "
                + f"openclaw_agent={config.openclaw_agent or 'none'}"
            ),
        ),
        config,
    )


def _check_openclaw(config: AppConfig) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []

    command_parts = _parse_openclaw_command(config.openclaw_command)
    if command_parts is None:
        checks.append(
            DoctorCheck(
                name="openclaw-command",
                status="fail",
                detail="invalid VIBEMOUSE_OPENCLAW_COMMAND shell syntax",
            )
        )
        return checks

    executable = command_parts[0]
    resolved = shutil.which(executable)
    if resolved is None:
        checks.append(
            DoctorCheck(
                name="openclaw-command",
                status="fail",
                detail=f"executable not found in PATH: {executable}",
            )
        )
        return checks

    checks.append(
        DoctorCheck(
            name="openclaw-command",
            status="ok",
            detail=f"resolved executable: {resolved}",
        )
    )

    configured_agent = config.openclaw_agent
    if not configured_agent:
        checks.append(
            DoctorCheck(
                name="openclaw-agent",
                status="warn",
                detail="no agent configured; set VIBEMOUSE_OPENCLAW_AGENT",
            )
        )
        return checks

    probe_cmd = [*command_parts, "agents", "list", "--json"]
    try:
        probe = subprocess.run(
            probe_cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=8.0,
        )
    except subprocess.TimeoutExpired:
        checks.append(
            DoctorCheck(
                name="openclaw-agent",
                status="warn",
                detail="timed out while probing available agents",
            )
        )
        return checks
    except OSError as error:
        checks.append(
            DoctorCheck(
                name="openclaw-agent",
                status="warn",
                detail=f"failed to run agent probe: {error}",
            )
        )
        return checks

    if probe.returncode != 0:
        stderr = probe.stderr.strip()
        checks.append(
            DoctorCheck(
                name="openclaw-agent",
                status="warn",
                detail=(
                    "agent probe failed"
                    if not stderr
                    else f"agent probe failed: {stderr}"
                ),
            )
        )
        return checks

    try:
        payload = json.loads(probe.stdout)
    except json.JSONDecodeError:
        checks.append(
            DoctorCheck(
                name="openclaw-agent",
                status="warn",
                detail="agent probe returned invalid JSON",
            )
        )
        return checks

    if not isinstance(payload, list):
        checks.append(
            DoctorCheck(
                name="openclaw-agent",
                status="warn",
                detail="agent probe returned unexpected payload shape",
            )
        )
        return checks

    available_agents = {
        str(entry.get("id", "")).strip() for entry in payload if isinstance(entry, dict)
    }
    if configured_agent in available_agents:
        checks.append(
            DoctorCheck(
                name="openclaw-agent",
                status="ok",
                detail=f"configured agent exists: {configured_agent}",
            )
        )
    else:
        sample = ", ".join(sorted(agent for agent in available_agents if agent)[:5])
        checks.append(
            DoctorCheck(
                name="openclaw-agent",
                status="warn",
                detail=(
                    f"configured agent not found: {configured_agent}; "
                    + (f"available: {sample}" if sample else "no agents listed")
                ),
            )
        )

    return checks


def _check_audio_input(config: AppConfig | None) -> DoctorCheck:
    try:
        sounddevice = importlib.import_module("sounddevice")
    except Exception as error:
        return DoctorCheck(
            name="audio-input",
            status="fail",
            detail=f"cannot import sounddevice: {error}",
        )

    query_devices = getattr(sounddevice, "query_devices", None)
    if not callable(query_devices):
        return DoctorCheck(
            name="audio-input",
            status="fail",
            detail="sounddevice.query_devices is unavailable",
        )

    try:
        devices_obj = query_devices()
    except Exception as error:
        return DoctorCheck(
            name="audio-input",
            status="fail",
            detail=f"failed to query audio devices: {error}",
        )

    device_entries = _coerce_device_entries(devices_obj)
    if device_entries is None:
        return DoctorCheck(
            name="audio-input",
            status="warn",
            detail="unexpected audio device payload shape",
        )

    input_devices: list[Mapping[str, object]] = []
    for item in device_entries:
        max_inputs = _to_float(item.get("max_input_channels", 0.0))
        if max_inputs > 0:
            input_devices.append(item)
    if not input_devices:
        return DoctorCheck(
            name="audio-input",
            status="fail",
            detail="no input-capable microphone device detected",
        )

    default_index = _read_default_input_device_index(sounddevice)
    check_input_settings = getattr(sounddevice, "check_input_settings", None)
    if default_index is not None and callable(check_input_settings):
        sample_rate = float(config.sample_rate) if config is not None else 16000.0
        channels = config.channels if config is not None else 1
        try:
            _ = check_input_settings(
                device=default_index,
                channels=max(1, int(channels)),
                samplerate=sample_rate,
            )
        except Exception as error:
            return DoctorCheck(
                name="audio-input",
                status="warn",
                detail=f"default input exists but validation failed: {error}",
            )

    return DoctorCheck(
        name="audio-input",
        status="ok",
        detail=f"detected {len(input_devices)} input-capable device(s)",
    )


def _check_input_device_permissions() -> DoctorCheck:
    return DoctorCheck(
        name="input-device-permissions",
        status="ok",
        detail="macOS uses Quartz for input capture",
    )


def _read_default_input_device_index(sounddevice: object) -> int | None:
    default_obj = getattr(sounddevice, "default", None)
    if default_obj is None:
        return None

    device_attr = getattr(default_obj, "device", None)
    if not isinstance(device_attr, tuple | list) or len(device_attr) < 1:
        return None

    raw_input_index = device_attr[0]
    if not isinstance(raw_input_index, int):
        return None
    if raw_input_index < 0:
        return None
    return raw_input_index


def _coerce_device_entries(devices_obj: object) -> list[Mapping[str, object]] | None:
    if isinstance(devices_obj, list):
        return [entry for entry in devices_obj if isinstance(entry, Mapping)]

    if isinstance(devices_obj, Iterable):
        entries: list[Mapping[str, object]] = []
        for entry in devices_obj:
            if isinstance(entry, Mapping):
                entries.append(entry)
        return entries

    return None


def _to_float(value: object) -> float:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return 0.0
    return 0.0


def _check_macos_app_bundle() -> DoctorCheck:
    exe = sys.executable
    if ".app/Contents/MacOS" in exe:
        bundle_path = Path(exe).resolve()
        for parent in bundle_path.parents:
            if parent.suffix == ".app":
                return DoctorCheck(
                    name="macos-app-bundle",
                    status="ok",
                    detail=f"running from app bundle: {parent}",
                )
        return DoctorCheck(
            name="macos-app-bundle",
            status="ok",
            detail="running from app bundle",
        )
    return DoctorCheck(
        name="macos-app-bundle",
        status="info",
        detail="running in development mode (not bundled as .app)",
    )


def _check_macos_pyobjc() -> DoctorCheck:
    try:
        importlib.import_module("Quartz")
    except Exception:
        return DoctorCheck(
            name="macos-pyobjc",
            status="fail",
            detail="cannot import Quartz; install with: pip install 'vibemouse'",
        )

    try:
        importlib.import_module("AppKit")
    except Exception:
        return DoctorCheck(
            name="macos-pyobjc",
            status="fail",
            detail="cannot import AppKit; install with: pip install 'vibemouse'",
        )

    return DoctorCheck(
        name="macos-pyobjc",
        status="ok",
        detail="Quartz and AppKit available",
    )


def _check_macos_accessibility_permission() -> DoctorCheck:
    try:
        app_services = importlib.import_module("ApplicationServices")
        is_trusted = getattr(app_services, "AXIsProcessTrusted", None)
        if is_trusted is None:
            return DoctorCheck(
                name="macos-accessibility",
                status="warn",
                detail="AXIsProcessTrusted not available",
            )
        if is_trusted():
            return DoctorCheck(
                name="macos-accessibility",
                status="ok",
                detail="accessibility permission granted",
            )
        return DoctorCheck(
            name="macos-accessibility",
            status="fail",
            detail=(
                "accessibility permission not granted; "
                "enable in System Settings > Privacy & Security > Accessibility"
            ),
        )
    except Exception as error:
        return DoctorCheck(
            name="macos-accessibility",
            status="warn",
            detail=f"could not check accessibility permission: {error}",
        )


_LAUNCHAGENT_LABEL = "com.vibemouse.daemon"


def _check_macos_launchagent_state() -> DoctorCheck:
    plist_path = (
        Path.home() / "Library" / "LaunchAgents" / f"{_LAUNCHAGENT_LABEL}.plist"
    )
    if not plist_path.exists():
        return DoctorCheck(
            name="macos-launchagent",
            status="warn",
            detail=f"plist not found: {plist_path}",
        )

    probe = _run_subprocess(
        ["launchctl", "list", _LAUNCHAGENT_LABEL],
        timeout=3.0,
    )
    if probe is None:
        return DoctorCheck(
            name="macos-launchagent",
            status="warn",
            detail="could not query launchctl state",
        )

    if probe.returncode == 0:
        return DoctorCheck(
            name="macos-launchagent",
            status="ok",
            detail=f"{_LAUNCHAGENT_LABEL} is loaded",
        )

    return DoctorCheck(
        name="macos-launchagent",
        status="warn",
        detail=f"{_LAUNCHAGENT_LABEL} plist exists but is not loaded",
    )


def _ensure_macos_launchagent_loaded() -> None:
    plist_path = (
        Path.home() / "Library" / "LaunchAgents" / f"{_LAUNCHAGENT_LABEL}.plist"
    )
    if not plist_path.exists():
        return

    probe = _run_subprocess(
        ["launchctl", "list", _LAUNCHAGENT_LABEL],
        timeout=3.0,
    )
    if probe is not None and probe.returncode == 0:
        return

    _ = _run_subprocess(
        ["launchctl", "load", "-w", str(plist_path)],
        timeout=5.0,
    )


def _run_subprocess(
    cmd: list[str],
    *,
    timeout: float,
) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _parse_openclaw_command(raw: str) -> list[str] | None:
    cleaned = raw.strip()
    if not cleaned:
        return None
    try:
        parts = shlex.split(cleaned)
    except ValueError:
        return None
    if not parts:
        return None
    return parts


def _print_checks(checks: list[DoctorCheck]) -> None:
    for check in checks:
        badge = {
            "ok": "[OK]",
            "warn": "[WARN]",
            "fail": "[FAIL]",
        }.get(check.status, "[INFO]")
        print(f"{badge} {check.name}: {check.detail}")
