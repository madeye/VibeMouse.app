from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from vibemouse.config import load_config


class LoadConfigTests(unittest.TestCase):
    def test_defaults_disable_trust_remote_code(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()

        self.assertFalse(config.trust_remote_code)
        self.assertEqual(config.transcriber_backend, "funasr_onnx")
        self.assertFalse(config.auto_paste)
        self.assertEqual(config.enter_mode, "enter")
        self.assertEqual(config.button_debounce_ms, 150)
        self.assertTrue(config.prewarm_on_start)
        self.assertEqual(config.prewarm_delay_s, 0.0)
        self.assertEqual(config.status_file.name, "vibemouse-status.json")
        self.assertEqual(config.front_button, "x1")
        self.assertEqual(config.rear_button, "x2")
        self.assertEqual(config.audio_input_device, "")

    def test_trust_remote_code_can_be_enabled(self) -> None:
        with patch.dict(
            os.environ, {"VIBEMOUSE_TRUST_REMOTE_CODE": "true"}, clear=True
        ):
            config = load_config()

        self.assertTrue(config.trust_remote_code)

    def test_backend_can_be_overridden(self) -> None:
        with patch.dict(os.environ, {"VIBEMOUSE_BACKEND": "funasr"}, clear=True):
            config = load_config()

        self.assertEqual(config.transcriber_backend, "funasr")

    def test_auto_paste_can_be_enabled(self) -> None:
        with patch.dict(os.environ, {"VIBEMOUSE_AUTO_PASTE": "true"}, clear=True):
            config = load_config()

        self.assertTrue(config.auto_paste)

    def test_prewarm_on_start_can_be_disabled(self) -> None:
        with patch.dict(
            os.environ,
            {"VIBEMOUSE_PREWARM_ON_START": "false"},
            clear=True,
        ):
            config = load_config()

        self.assertFalse(config.prewarm_on_start)

    def test_prewarm_delay_can_be_configured(self) -> None:
        with patch.dict(
            os.environ,
            {"VIBEMOUSE_PREWARM_DELAY_S": "2.5"},
            clear=True,
        ):
            config = load_config()

        self.assertEqual(config.prewarm_delay_s, 2.5)

    def test_negative_prewarm_delay_is_rejected(self) -> None:
        with patch.dict(
            os.environ,
            {"VIBEMOUSE_PREWARM_DELAY_S": "-0.1"},
            clear=True,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "VIBEMOUSE_PREWARM_DELAY_S must be a non-negative float",
            ):
                _ = load_config()

    def test_status_file_can_be_overridden(self) -> None:
        with patch.dict(
            os.environ,
            {"VIBEMOUSE_STATUS_FILE": "/tmp/custom-vibemouse-status.json"},
            clear=True,
        ):
            config = load_config()

        self.assertEqual(str(config.status_file), "/tmp/custom-vibemouse-status.json")

    def test_enter_mode_can_be_configured(self) -> None:
        with patch.dict(os.environ, {"VIBEMOUSE_ENTER_MODE": "ctrl_enter"}, clear=True):
            config = load_config()

        self.assertEqual(config.enter_mode, "ctrl_enter")

    def test_enter_mode_supports_none(self) -> None:
        with patch.dict(os.environ, {"VIBEMOUSE_ENTER_MODE": "none"}, clear=True):
            config = load_config()

        self.assertEqual(config.enter_mode, "none")

    def test_invalid_enter_mode_is_rejected(self) -> None:
        with patch.dict(os.environ, {"VIBEMOUSE_ENTER_MODE": "meta_enter"}, clear=True):
            with self.assertRaisesRegex(
                ValueError, "VIBEMOUSE_ENTER_MODE must be one of"
            ):
                _ = load_config()

    def test_negative_debounce_is_rejected(self) -> None:
        with patch.dict(os.environ, {"VIBEMOUSE_BUTTON_DEBOUNCE_MS": "-1"}, clear=True):
            with self.assertRaisesRegex(
                ValueError,
                "VIBEMOUSE_BUTTON_DEBOUNCE_MS must be a non-negative integer",
            ):
                _ = load_config()

    def test_invalid_integer_reports_variable_name(self) -> None:
        with patch.dict(os.environ, {"VIBEMOUSE_SAMPLE_RATE": "abc"}, clear=True):
            with self.assertRaisesRegex(
                ValueError, "VIBEMOUSE_SAMPLE_RATE must be an integer"
            ):
                _ = load_config()

    def test_non_positive_integer_is_rejected(self) -> None:
        with patch.dict(os.environ, {"VIBEMOUSE_MERGE_LENGTH_S": "0"}, clear=True):
            with self.assertRaisesRegex(
                ValueError,
                "VIBEMOUSE_MERGE_LENGTH_S must be a positive integer",
            ):
                _ = load_config()

    def test_invalid_button_value_is_rejected(self) -> None:
        with patch.dict(os.environ, {"VIBEMOUSE_FRONT_BUTTON": "x3"}, clear=True):
            with self.assertRaisesRegex(
                ValueError,
                "VIBEMOUSE_FRONT_BUTTON must be either 'x1' or 'x2'",
            ):
                _ = load_config()

    def test_same_front_and_rear_buttons_are_rejected(self) -> None:
        with patch.dict(
            os.environ,
            {
                "VIBEMOUSE_FRONT_BUTTON": "x1",
                "VIBEMOUSE_REAR_BUTTON": "x1",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "VIBEMOUSE_FRONT_BUTTON and VIBEMOUSE_REAR_BUTTON must differ",
            ):
                _ = load_config()

    def test_audio_input_device_reads_from_env(self) -> None:
        with patch.dict(
            os.environ,
            {"VIBEMOUSE_AUDIO_INPUT_DEVICE": "USB Audio Device"},
            clear=True,
        ):
            config = load_config()

        self.assertEqual(config.audio_input_device, "USB Audio Device")

    def test_audio_input_device_normalizes_default(self) -> None:
        with patch.dict(
            os.environ,
            {"VIBEMOUSE_AUDIO_INPUT_DEVICE": "default"},
            clear=True,
        ):
            config = load_config()

        self.assertEqual(config.audio_input_device, "")

    def test_audio_input_device_normalizes_default_case_insensitive(self) -> None:
        with patch.dict(
            os.environ,
            {"VIBEMOUSE_AUDIO_INPUT_DEVICE": "Default"},
            clear=True,
        ):
            config = load_config()

        self.assertEqual(config.audio_input_device, "")
