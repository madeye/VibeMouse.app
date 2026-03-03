from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from vibemouse.macos.config_bridge import _MACOS_DEFAULTS, load_preferences_into_environ, save_preference


class TestLoadPreferencesIntoEnviron(unittest.TestCase):
    def test_sets_macos_defaults_when_env_empty(self) -> None:
        clean_env: dict[str, str] = {}
        with patch.dict(os.environ, clean_env, clear=True):
            load_preferences_into_environ(config_path=Path("/nonexistent/config.json"))

            for key, value in _MACOS_DEFAULTS.items():
                self.assertEqual(os.environ.get(key), value, f"{key} should be set")

    def test_reads_config_json(self, tmp_path: Path | None = None) -> None:
        if tmp_path is None:
            import tempfile

            tmp_dir = tempfile.mkdtemp()
            tmp_path = Path(tmp_dir)

        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps(
                {
                    "VIBEMOUSE_LANGUAGE": "en",
                    "VIBEMOUSE_ENTER_MODE": "ctrl_enter",
                }
            ),
            encoding="utf-8",
        )

        clean_env: dict[str, str] = {}
        with patch.dict(os.environ, clean_env, clear=True):
            load_preferences_into_environ(config_path=config_file)
            self.assertEqual(os.environ.get("VIBEMOUSE_LANGUAGE"), "en")
            self.assertEqual(os.environ.get("VIBEMOUSE_ENTER_MODE"), "ctrl_enter")

    def test_does_not_override_existing_env(self) -> None:
        import tempfile

        tmp_dir = tempfile.mkdtemp()
        config_file = Path(tmp_dir) / "config.json"
        config_file.write_text(
            json.dumps({"VIBEMOUSE_AUTO_PASTE": "false"}),
            encoding="utf-8",
        )

        with patch.dict(os.environ, {"VIBEMOUSE_AUTO_PASTE": "already_set"}, clear=True):
            load_preferences_into_environ(config_path=config_file)
            self.assertEqual(os.environ["VIBEMOUSE_AUTO_PASTE"], "already_set")

    def test_ignores_non_vibemouse_keys(self) -> None:
        import tempfile

        tmp_dir = tempfile.mkdtemp()
        config_file = Path(tmp_dir) / "config.json"
        config_file.write_text(
            json.dumps({"SOME_OTHER_KEY": "value", "VIBEMOUSE_LANGUAGE": "zh"}),
            encoding="utf-8",
        )

        clean_env: dict[str, str] = {}
        with patch.dict(os.environ, clean_env, clear=True):
            load_preferences_into_environ(config_path=config_file)
            self.assertNotIn("SOME_OTHER_KEY", os.environ)
            self.assertEqual(os.environ.get("VIBEMOUSE_LANGUAGE"), "zh")

    def test_handles_missing_config_file(self) -> None:
        clean_env: dict[str, str] = {}
        with patch.dict(os.environ, clean_env, clear=True):
            load_preferences_into_environ(config_path=Path("/no/such/file.json"))
            # Should still apply defaults
            self.assertEqual(
                os.environ.get("VIBEMOUSE_AUTO_PASTE"),
                _MACOS_DEFAULTS["VIBEMOUSE_AUTO_PASTE"],
            )

    def test_handles_malformed_json(self) -> None:
        import tempfile

        tmp_dir = tempfile.mkdtemp()
        config_file = Path(tmp_dir) / "config.json"
        config_file.write_text("{bad json", encoding="utf-8")

        clean_env: dict[str, str] = {}
        with patch.dict(os.environ, clean_env, clear=True):
            load_preferences_into_environ(config_path=config_file)
            # Should still apply defaults without error
            self.assertEqual(
                os.environ.get("VIBEMOUSE_AUTO_PASTE"),
                _MACOS_DEFAULTS["VIBEMOUSE_AUTO_PASTE"],
            )


class TestSavePreference(unittest.TestCase):
    def test_creates_config_file(self) -> None:
        import tempfile

        tmp_dir = tempfile.mkdtemp()
        config_file = Path(tmp_dir) / "subdir" / "config.json"

        with patch.dict(os.environ, {}, clear=True):
            save_preference(
                "VIBEMOUSE_AUDIO_INPUT_DEVICE",
                "USB Mic",
                config_path=config_file,
            )

        self.assertTrue(config_file.is_file())
        data = json.loads(config_file.read_text(encoding="utf-8"))
        self.assertEqual(data["VIBEMOUSE_AUDIO_INPUT_DEVICE"], "USB Mic")

    def test_updates_environ(self) -> None:
        import tempfile

        tmp_dir = tempfile.mkdtemp()
        config_file = Path(tmp_dir) / "config.json"

        with patch.dict(os.environ, {}, clear=True):
            save_preference(
                "VIBEMOUSE_AUDIO_INPUT_DEVICE",
                "AirPods",
                config_path=config_file,
            )
            self.assertEqual(os.environ["VIBEMOUSE_AUDIO_INPUT_DEVICE"], "AirPods")

    def test_merges_with_existing(self) -> None:
        import tempfile

        tmp_dir = tempfile.mkdtemp()
        config_file = Path(tmp_dir) / "config.json"
        config_file.write_text(
            json.dumps({"VIBEMOUSE_LANGUAGE": "en"}),
            encoding="utf-8",
        )

        with patch.dict(os.environ, {}, clear=True):
            save_preference(
                "VIBEMOUSE_AUDIO_INPUT_DEVICE",
                "USB Mic",
                config_path=config_file,
            )

        data = json.loads(config_file.read_text(encoding="utf-8"))
        self.assertEqual(data["VIBEMOUSE_LANGUAGE"], "en")
        self.assertEqual(data["VIBEMOUSE_AUDIO_INPUT_DEVICE"], "USB Mic")

    def test_ignores_non_vibemouse_keys(self) -> None:
        import tempfile

        tmp_dir = tempfile.mkdtemp()
        config_file = Path(tmp_dir) / "config.json"

        with patch.dict(os.environ, {}, clear=True):
            save_preference(
                "SOME_OTHER_KEY",
                "value",
                config_path=config_file,
            )

        self.assertFalse(config_file.is_file())
        self.assertNotIn("SOME_OTHER_KEY", os.environ)


if __name__ == "__main__":
    unittest.main()
