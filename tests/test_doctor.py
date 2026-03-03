from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

from vibemouse.config import AppConfig
from vibemouse.doctor import (
    DoctorCheck,
    _apply_doctor_fixes,
    _check_macos_accessibility_permission,
    _check_macos_launchagent_state,
    _check_macos_pyobjc,
    _check_openclaw,
    _parse_openclaw_command,
    run_doctor,
)


class DoctorHelpersTests(unittest.TestCase):
    def test_parse_openclaw_command_invalid_shell_syntax(self) -> None:
        self.assertIsNone(_parse_openclaw_command('openclaw "'))

    def test_check_openclaw_reports_missing_executable(self) -> None:
        config = cast(
            AppConfig,
            cast(
                object,
                SimpleNamespace(openclaw_command="openclaw", openclaw_agent="main"),
            ),
        )
        with patch("vibemouse.doctor.shutil.which", return_value=None):
            checks = _check_openclaw(config)

        self.assertEqual(checks[0].status, "fail")
        self.assertIn("executable not found", checks[0].detail)

    def test_check_openclaw_reports_agent_exists(self) -> None:
        config = cast(
            AppConfig,
            cast(
                object,
                SimpleNamespace(openclaw_command="openclaw", openclaw_agent="main"),
            ),
        )
        with (
            patch("vibemouse.doctor.shutil.which", return_value="/usr/bin/openclaw"),
            patch(
                "vibemouse.doctor.subprocess.run",
                return_value=SimpleNamespace(
                    returncode=0,
                    stdout='[{"id": "main"}]',
                    stderr="",
                ),
            ),
        ):
            checks = _check_openclaw(config)

        self.assertEqual([check.status for check in checks], ["ok", "ok"])

    def test_audio_input_check_reports_missing_dependency(self) -> None:
        with patch(
            "vibemouse.doctor.importlib.import_module",
            side_effect=ModuleNotFoundError("sounddevice"),
        ):
            from vibemouse.doctor import _check_audio_input

            check = _check_audio_input(None)

        self.assertEqual(check.status, "fail")
        self.assertIn("cannot import sounddevice", check.detail)

    def test_audio_input_check_reports_ok_when_input_device_exists(self) -> None:
        fake_sounddevice = SimpleNamespace(
            query_devices=lambda: [{"max_input_channels": 2}],
            default=SimpleNamespace(device=(0, 1)),
            check_input_settings=lambda **kwargs: kwargs,
        )
        with patch(
            "vibemouse.doctor.importlib.import_module",
            return_value=fake_sounddevice,
        ):
            from vibemouse.doctor import _check_audio_input

            check = _check_audio_input(
                cast(
                    AppConfig,
                    cast(object, SimpleNamespace(sample_rate=16000, channels=1)),
                )
            )

        self.assertEqual(check.status, "ok")

    def test_input_permissions_ok_on_macos(self) -> None:
        from vibemouse.doctor import _check_input_device_permissions

        check = _check_input_device_permissions()

        self.assertEqual(check.status, "ok")
        self.assertIn("Quartz", check.detail)

    def test_apply_fixes_runs_macos_path(self) -> None:
        with patch("vibemouse.doctor._ensure_macos_launchagent_loaded") as mac_fix:
            _apply_doctor_fixes()

        self.assertEqual(mac_fix.call_count, 1)


class DoctorCommandTests(unittest.TestCase):
    def test_run_doctor_returns_nonzero_when_fail_exists(self) -> None:
        with (
            patch(
                "vibemouse.doctor._check_config_load",
                return_value=(
                    DoctorCheck("config", "fail", "broken"),
                    None,
                ),
            ),
            patch(
                "vibemouse.doctor._check_audio_input",
                return_value=DoctorCheck("audio", "ok", "ok"),
            ),
            patch(
                "vibemouse.doctor._check_input_device_permissions",
                return_value=DoctorCheck("input", "ok", "ok"),
            ),
            patch(
                "vibemouse.doctor._check_macos_pyobjc",
                return_value=DoctorCheck("macos-pyobjc", "ok", "ok"),
            ),
            patch(
                "vibemouse.doctor._check_macos_accessibility_permission",
                return_value=DoctorCheck("macos-accessibility", "ok", "ok"),
            ),
            patch(
                "vibemouse.doctor._check_macos_app_bundle",
                return_value=DoctorCheck("macos-app-bundle", "ok", "ok"),
            ),
            patch(
                "vibemouse.doctor._check_macos_launchagent_state",
                return_value=DoctorCheck("macos-launchagent", "ok", "ok"),
            ),
        ):
            rc = run_doctor()

        self.assertEqual(rc, 1)

    def test_run_doctor_with_fix_invokes_fix_path(self) -> None:
        with (
            patch("vibemouse.doctor._apply_doctor_fixes") as apply_fixes,
            patch(
                "vibemouse.doctor._check_config_load",
                return_value=(
                    DoctorCheck("config", "ok", "ok"),
                    cast(
                        AppConfig,
                        cast(
                            object,
                            SimpleNamespace(
                                openclaw_command="openclaw",
                                openclaw_agent="main",
                                rear_button="x2",
                                sample_rate=16000,
                                channels=1,
                            ),
                        ),
                    ),
                ),
            ),
            patch("vibemouse.doctor._check_openclaw", return_value=[]),
            patch(
                "vibemouse.doctor._check_audio_input",
                return_value=DoctorCheck("audio", "ok", "ok"),
            ),
            patch(
                "vibemouse.doctor._check_input_device_permissions",
                return_value=DoctorCheck("input", "ok", "ok"),
            ),
            patch(
                "vibemouse.doctor._check_macos_pyobjc",
                return_value=DoctorCheck("macos-pyobjc", "ok", "ok"),
            ),
            patch(
                "vibemouse.doctor._check_macos_accessibility_permission",
                return_value=DoctorCheck("macos-accessibility", "ok", "ok"),
            ),
            patch(
                "vibemouse.doctor._check_macos_app_bundle",
                return_value=DoctorCheck("macos-app-bundle", "ok", "ok"),
            ),
            patch(
                "vibemouse.doctor._check_macos_launchagent_state",
                return_value=DoctorCheck("macos-launchagent", "ok", "ok"),
            ),
        ):
            rc = run_doctor(apply_fixes=True)

        self.assertEqual(rc, 0)
        self.assertEqual(apply_fixes.call_count, 1)


class DoctorMacOSTests(unittest.TestCase):
    def test_doctor_uses_macos_checks(self) -> None:
        with (
            patch(
                "vibemouse.doctor._check_config_load",
                return_value=(DoctorCheck("config", "ok", "ok"), None),
            ),
            patch(
                "vibemouse.doctor._check_audio_input",
                return_value=DoctorCheck("audio", "ok", "ok"),
            ),
            patch(
                "vibemouse.doctor._check_input_device_permissions",
                return_value=DoctorCheck("input", "ok", "ok"),
            ),
            patch(
                "vibemouse.doctor._check_macos_pyobjc",
                return_value=DoctorCheck("macos-pyobjc", "ok", "ok"),
            ) as pyobjc_check,
            patch(
                "vibemouse.doctor._check_macos_accessibility_permission",
                return_value=DoctorCheck("macos-accessibility", "ok", "ok"),
            ) as access_check,
            patch(
                "vibemouse.doctor._check_macos_launchagent_state",
                return_value=DoctorCheck("macos-launchagent", "ok", "ok"),
            ) as agent_check,
        ):
            rc = run_doctor()

        self.assertEqual(rc, 0)
        self.assertEqual(pyobjc_check.call_count, 1)
        self.assertEqual(access_check.call_count, 1)
        self.assertEqual(agent_check.call_count, 1)

    def test_macos_accessibility_check_ok_when_trusted(self) -> None:
        fake_app_services = SimpleNamespace(AXIsProcessTrusted=lambda: True)
        with patch(
            "vibemouse.doctor.importlib.import_module",
            return_value=fake_app_services,
        ):
            check = _check_macos_accessibility_permission()

        self.assertEqual(check.status, "ok")
        self.assertIn("granted", check.detail)

    def test_macos_accessibility_check_fail_when_not_trusted(self) -> None:
        fake_app_services = SimpleNamespace(AXIsProcessTrusted=lambda: False)
        with patch(
            "vibemouse.doctor.importlib.import_module",
            return_value=fake_app_services,
        ):
            check = _check_macos_accessibility_permission()

        self.assertEqual(check.status, "fail")
        self.assertIn("not granted", check.detail)

    def test_macos_pyobjc_check_fail_when_unavailable(self) -> None:
        with patch(
            "vibemouse.doctor.importlib.import_module",
            side_effect=ModuleNotFoundError("No module named 'Quartz'"),
        ):
            check = _check_macos_pyobjc()

        self.assertEqual(check.status, "fail")
        self.assertIn("Quartz", check.detail)

    def test_macos_pyobjc_check_ok_when_available(self) -> None:
        with patch(
            "vibemouse.doctor.importlib.import_module",
            return_value=SimpleNamespace(),
        ):
            check = _check_macos_pyobjc()

        self.assertEqual(check.status, "ok")

    def test_macos_launchagent_check_warn_when_no_plist(self) -> None:
        with patch("vibemouse.doctor.Path.home", return_value=Path("/nonexistent")):
            check = _check_macos_launchagent_state()

        self.assertEqual(check.status, "warn")
        self.assertIn("plist not found", check.detail)
