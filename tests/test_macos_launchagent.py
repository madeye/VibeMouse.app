from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vibemouse.macos import launchagent


class TestLaunchAgent(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self._agents_dir = Path(self._tmp) / "Library" / "LaunchAgents"

    def _patch_dir(self):
        return patch.object(
            launchagent,
            "_LAUNCH_AGENTS_DIR",
            self._agents_dir,
        )

    def test_register_writes_plist(self) -> None:
        with self._patch_dir():
            result = launchagent.register_login_item("/Applications/VibeMouse.app")

        self.assertTrue(result.is_file())
        content = result.read_text(encoding="utf-8")
        self.assertIn("com.vibemouse.app", content)
        self.assertIn("/Applications/VibeMouse.app", content)
        self.assertIn("<key>RunAtLoad</key>", content)

    def test_unregister_removes_plist(self) -> None:
        with self._patch_dir():
            launchagent.register_login_item("/Applications/VibeMouse.app")
            self.assertTrue(launchagent.is_registered())

            removed = launchagent.unregister_login_item()
            self.assertTrue(removed)
            self.assertFalse(launchagent.is_registered())

    def test_unregister_returns_false_when_missing(self) -> None:
        with self._patch_dir():
            self.assertFalse(launchagent.unregister_login_item())

    def test_is_registered(self) -> None:
        with self._patch_dir():
            self.assertFalse(launchagent.is_registered())
            launchagent.register_login_item("/Applications/VibeMouse.app")
            self.assertTrue(launchagent.is_registered())

    def test_xml_escapes_special_chars(self) -> None:
        with self._patch_dir():
            result = launchagent.register_login_item('/Apps/Vibe & "Mouse" <App>.app')

        content = result.read_text(encoding="utf-8")
        self.assertIn("&amp;", content)
        self.assertIn("&lt;", content)
        self.assertIn("&gt;", content)
        self.assertIn("&quot;", content)


if __name__ == "__main__":
    unittest.main()
