from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vibemouse.main import main


class MainEntryTests(unittest.TestCase):
    def test_default_invocation_runs_app(self) -> None:
        app_instance = MagicMock()
        cfg = MagicMock()
        with (
            patch("vibemouse.main.load_config", return_value=cfg) as load_config,
            patch(
                "vibemouse.main.VoiceMouseApp", return_value=app_instance
            ) as app_ctor,
        ):
            rc = main()

        self.assertEqual(rc, 0)
        self.assertEqual(load_config.call_count, 1)
        self.assertEqual(app_ctor.call_count, 1)
        self.assertEqual(app_instance.run.call_count, 1)
