from __future__ import annotations

import unittest
from unittest.mock import patch

from vibemouse.system_integration import (
    MacOSSystemIntegration,
    _MACOS_TERMINAL_BUNDLE_IDS,
    create_system_integration,
    is_terminal_window_payload,
)


class SystemIntegrationDetectionTests(unittest.TestCase):
    def test_factory_returns_macos_integration(self) -> None:
        integration = create_system_integration()
        self.assertIsInstance(integration, MacOSSystemIntegration)


class MacOSSystemIntegrationTests(unittest.TestCase):
    def _make_integration(
        self,
        *,
        quartz: object | None = None,
        appkit: object | None = None,
        ax: object | None = None,
    ) -> MacOSSystemIntegration:
        with (
            patch("vibemouse.system_integration._load_quartz", return_value=quartz),
            patch("vibemouse.system_integration._load_appkit", return_value=appkit),
            patch("vibemouse.system_integration._load_application_services", return_value=ax),
        ):
            return MacOSSystemIntegration()

    def test_send_shortcut_posts_keyboard_event(self) -> None:
        posted: list[tuple[object, object]] = []

        class FakeQuartz:
            kCGHIDEventTap = 0

            @staticmethod
            def CGEventCreateKeyboardEvent(
                source: object, keycode: int, key_down: bool
            ) -> dict[str, object]:
                return {"keycode": keycode, "down": key_down}

            @staticmethod
            def CGEventSetFlags(event: object, flags: int) -> None:
                pass

            @staticmethod
            def CGEventPost(tap: object, event: object) -> None:
                posted.append((tap, event))

        integration = self._make_integration(quartz=FakeQuartz())
        ok = integration.send_shortcut(mod="CMD", key="V")

        self.assertTrue(ok)
        self.assertEqual(len(posted), 2)
        # Key down then key up
        self.assertTrue(posted[0][1]["down"])
        self.assertFalse(posted[1][1]["down"])

    def test_send_shortcut_returns_false_when_quartz_unavailable(self) -> None:
        integration = self._make_integration(quartz=None)
        self.assertFalse(integration.send_shortcut(mod="CMD", key="V"))

    def test_active_window_returns_bundle_info(self) -> None:
        class FakeApp:
            def bundleIdentifier(self) -> str:
                return "com.apple.terminal"

            def localizedName(self) -> str:
                return "Terminal"

        class FakeWorkspace:
            def frontmostApplication(self) -> FakeApp:
                return FakeApp()

        class FakeNSWorkspace:
            @staticmethod
            def sharedWorkspace() -> FakeWorkspace:
                return FakeWorkspace()

        class FakeAppKit:
            NSWorkspace = FakeNSWorkspace

        integration = self._make_integration(appkit=FakeAppKit())
        result = integration.active_window()

        self.assertIsNotNone(result)
        self.assertEqual(result["class"], "com.apple.terminal")
        self.assertEqual(result["title"], "Terminal")

    def test_is_terminal_active_detects_apple_terminal(self) -> None:
        integration = self._make_integration()
        with patch.object(
            integration,
            "active_window",
            return_value={"class": "com.apple.terminal", "title": "Terminal"},
        ):
            self.assertTrue(integration.is_terminal_window_active())

    def test_is_terminal_active_false_for_safari(self) -> None:
        integration = self._make_integration()
        with patch.object(
            integration,
            "active_window",
            return_value={"class": "com.apple.safari", "title": "Safari"},
        ):
            self.assertFalse(integration.is_terminal_window_active())

    def test_is_text_input_focused_returns_true_for_text_field(self) -> None:
        class FakeQuartz:
            @staticmethod
            def AXUIElementCreateSystemWide() -> object:
                return "system_wide"

            @staticmethod
            def AXUIElementCopyAttributeValue(
                element: object, attr: str, _out: object
            ) -> tuple[int, object]:
                if attr == "AXFocusedUIElement":
                    return (0, "focused_element")
                if attr == "AXRole":
                    return (0, "AXTextField")
                return (1, None)

        integration = self._make_integration(ax=FakeQuartz())
        self.assertTrue(integration.is_text_input_focused())

    def test_is_text_input_focused_returns_none_when_quartz_unavailable(self) -> None:
        integration = self._make_integration(ax=None)
        self.assertIsNone(integration.is_text_input_focused())

    def test_cursor_position_returns_coordinates(self) -> None:
        class FakePoint:
            x = 100.5
            y = 200.0

        class FakeQuartz:
            @staticmethod
            def CGEventCreate(source: object) -> object:
                return "event"

            @staticmethod
            def CGEventGetLocation(event: object) -> FakePoint:
                return FakePoint()

        integration = self._make_integration(quartz=FakeQuartz())
        result = integration.cursor_position()
        self.assertEqual(result, (100, 200))

    def test_move_cursor_calls_warp(self) -> None:
        warped: list[object] = []

        class FakeCGPoint:
            def __init__(self, x: int, y: int) -> None:
                self.x = x
                self.y = y

        class FakeQuartz:
            CGPoint = FakeCGPoint

            @staticmethod
            def CGWarpMouseCursorPosition(point: object) -> None:
                warped.append(point)

        integration = self._make_integration(quartz=FakeQuartz())
        ok = integration.move_cursor(x=50, y=75)
        self.assertTrue(ok)
        self.assertEqual(len(warped), 1)

    def test_send_enter_via_accessibility_posts_return_key(self) -> None:
        posted: list[object] = []

        class FakeQuartz:
            kCGHIDEventTap = 0

            @staticmethod
            def CGEventCreateKeyboardEvent(
                source: object, keycode: int, key_down: bool
            ) -> dict[str, object]:
                return {"keycode": keycode, "down": key_down}

            @staticmethod
            def CGEventPost(tap: object, event: object) -> None:
                posted.append(event)

        integration = self._make_integration(quartz=FakeQuartz())
        ok = integration.send_enter_via_accessibility()
        self.assertTrue(ok)
        self.assertEqual(len(posted), 2)
        self.assertEqual(posted[0]["keycode"], 36)

    def test_switch_workspace_left(self) -> None:
        posted: list[dict[str, object]] = []

        class FakeQuartz:
            kCGHIDEventTap = 0

            @staticmethod
            def CGEventCreateKeyboardEvent(
                source: object, keycode: int, key_down: bool
            ) -> dict[str, object]:
                return {"keycode": keycode, "down": key_down}

            @staticmethod
            def CGEventSetFlags(event: object, flags: int) -> None:
                pass

            @staticmethod
            def CGEventPost(tap: object, event: object) -> None:
                posted.append(event)

        integration = self._make_integration(quartz=FakeQuartz())
        ok = integration.switch_workspace("left")
        self.assertTrue(ok)
        self.assertEqual(posted[0]["keycode"], 123)  # Left arrow

    def test_type_text_posts_chunked_unicode_events(self) -> None:
        posted: list[tuple[object, object]] = []
        unicode_calls: list[tuple[object, int, str]] = []

        class FakeQuartz:
            kCGHIDEventTap = 0

            @staticmethod
            def CGEventCreateKeyboardEvent(
                source: object, keycode: int, key_down: bool
            ) -> dict[str, object]:
                return {"keycode": keycode, "down": key_down}

            @staticmethod
            def CGEventKeyboardSetUnicodeString(
                event: object, length: int, string: str
            ) -> None:
                unicode_calls.append((event, length, string))

            @staticmethod
            def CGEventPost(tap: object, event: object) -> None:
                posted.append((tap, event))

        integration = self._make_integration(quartz=FakeQuartz())
        # 25 chars -> 2 chunks: 20 + 5
        text = "A" * 20 + "B" * 5
        ok = integration.type_text(text)

        self.assertTrue(ok)
        # 2 chunks x 2 events (down + up) = 4 posts
        self.assertEqual(len(posted), 4)
        # First chunk down, first chunk up, second chunk down, second chunk up
        self.assertTrue(posted[0][1]["down"])
        self.assertFalse(posted[1][1]["down"])
        self.assertTrue(posted[2][1]["down"])
        self.assertFalse(posted[3][1]["down"])
        # Unicode strings set correctly
        self.assertEqual(len(unicode_calls), 4)
        self.assertEqual(unicode_calls[0][2], "A" * 20)
        self.assertEqual(unicode_calls[0][1], 20)
        self.assertEqual(unicode_calls[2][2], "B" * 5)
        self.assertEqual(unicode_calls[2][1], 5)

    def test_type_text_returns_none_when_quartz_unavailable(self) -> None:
        integration = self._make_integration(quartz=None)
        self.assertIsNone(integration.type_text("hello"))

    def test_type_text_returns_false_on_exception(self) -> None:
        class FakeQuartz:
            kCGHIDEventTap = 0

            @staticmethod
            def CGEventCreateKeyboardEvent(
                source: object, keycode: int, key_down: bool
            ) -> object:
                raise RuntimeError("CGEvent failed")

            @staticmethod
            def CGEventKeyboardSetUnicodeString(
                event: object, length: int, string: str
            ) -> None:
                pass

            @staticmethod
            def CGEventPost(tap: object, event: object) -> None:
                pass

        integration = self._make_integration(quartz=FakeQuartz())
        self.assertFalse(integration.type_text("hello"))

    def test_macos_paste_shortcuts_use_cmd_v(self) -> None:
        integration = MacOSSystemIntegration()
        self.assertEqual(
            integration.paste_shortcuts(terminal_active=True),
            (("CMD", "V"),),
        )
        self.assertEqual(
            integration.paste_shortcuts(terminal_active=False),
            (("CMD", "V"),),
        )

    def test_terminal_payload_detection_by_title_hint(self) -> None:
        payload = {"class": "Code", "initialClass": "Code", "title": "tmux"}
        self.assertTrue(is_terminal_window_payload(payload))

    def test_terminal_payload_detection_false_for_browser_window(self) -> None:
        payload = {
            "class": "chromium",
            "initialClass": "chromium",
            "title": "ChatGPT",
        }
        self.assertFalse(is_terminal_window_payload(payload))

    def test_terminal_bundle_ids_contain_common_terminals(self) -> None:
        self.assertIn("com.apple.terminal", _MACOS_TERMINAL_BUNDLE_IDS)
        self.assertIn("com.googlecode.iterm2", _MACOS_TERMINAL_BUNDLE_IDS)
