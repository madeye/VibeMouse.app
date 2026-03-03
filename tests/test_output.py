from __future__ import annotations

import unittest
from types import SimpleNamespace
from collections.abc import Callable
from typing import cast
from unittest.mock import patch

from vibemouse.output import TextOutput


class _FakeKeyboardController:
    def __init__(self, *, fail_on_press: bool = False) -> None:
        self.events: list[tuple[str, object]] = []
        self._fail_on_press: bool = fail_on_press

    def press(self, key: object) -> None:
        if self._fail_on_press:
            raise RuntimeError("press failed")
        self.events.append(("press", key))

    def release(self, key: object) -> None:
        self.events.append(("release", key))

    def type(self, text: str) -> None:
        self.events.append(("type", text))


class TextOutputFocusProbeTests(unittest.TestCase):
    @staticmethod
    def _make_subject() -> TextOutput:
        return object.__new__(TextOutput)

    def test_focus_probe_prefers_system_integration_result(self) -> None:
        subject = self._make_subject()
        setattr(
            subject,
            "_system_integration",
            SimpleNamespace(is_text_input_focused=lambda: True),
        )

        probe = cast(Callable[[], bool], getattr(subject, "_is_text_input_focused"))
        self.assertTrue(probe())

    def test_focus_probe_returns_false_when_integration_returns_none(self) -> None:
        subject = self._make_subject()
        setattr(
            subject,
            "_system_integration",
            SimpleNamespace(is_text_input_focused=lambda: None),
        )

        probe = cast(Callable[[], bool], getattr(subject, "_is_text_input_focused"))
        self.assertFalse(probe())


class TextOutputRoutingTests(unittest.TestCase):
    @staticmethod
    def _make_subject() -> TextOutput:
        return object.__new__(TextOutput)

    @staticmethod
    def _bind_keyboard(subject: TextOutput, keyboard: _FakeKeyboardController) -> None:
        setattr(subject, "_kb", keyboard)
        setattr(subject, "_ctrl_key", "CTRL")
        setattr(subject, "_shift_key", "SHIFT")
        setattr(subject, "_enter_key", "ENTER")
        setattr(subject, "_openclaw_command", "openclaw")
        setattr(subject, "_openclaw_agent", None)
        setattr(subject, "_openclaw_timeout_s", 20.0)
        setattr(subject, "_openclaw_retries", 0)
        setattr(
            subject,
            "_system_integration",
            SimpleNamespace(
                type_text=lambda text: None,
                send_shortcut=lambda mod, key: False,
                is_terminal_window_active=lambda: None,
                paste_shortcuts=lambda terminal_active: (),
                send_enter_via_accessibility=lambda: None,
                is_text_input_focused=lambda: None,
            ),
        )

    def test_send_to_openclaw_success_returns_openclaw(self) -> None:
        subject = self._make_subject()
        keyboard = _FakeKeyboardController()
        self._bind_keyboard(subject, keyboard)

        with patch(
            "vibemouse.output.subprocess.Popen",
            return_value=SimpleNamespace(),
        ) as popen_mock:
            route = subject.send_to_openclaw("hello")
            detail = subject.send_to_openclaw_result("hello")

        self.assertEqual(route, "openclaw")
        self.assertEqual(
            popen_mock.call_args.args[0],
            ["openclaw", "agent", "--message", "hello", "--json"],
        )
        self.assertEqual(detail.route, "openclaw")
        self.assertEqual(detail.reason, "dispatched")

    def test_send_to_openclaw_includes_agent_when_configured(self) -> None:
        subject = self._make_subject()
        keyboard = _FakeKeyboardController()
        self._bind_keyboard(subject, keyboard)
        setattr(subject, "_openclaw_agent", "ops")

        with patch(
            "vibemouse.output.subprocess.Popen",
            return_value=SimpleNamespace(),
        ) as popen_mock:
            route = subject.send_to_openclaw("hello")

        self.assertEqual(route, "openclaw")
        self.assertEqual(
            popen_mock.call_args.args[0],
            ["openclaw", "agent", "--message", "hello", "--json", "--agent", "ops"],
        )

    def test_send_to_openclaw_invalid_command_falls_back_to_clipboard(self) -> None:
        subject = self._make_subject()
        keyboard = _FakeKeyboardController()
        self._bind_keyboard(subject, keyboard)
        setattr(subject, "_openclaw_command", 'openclaw "')

        with (
            patch("vibemouse.output.pyperclip.copy") as copy_mock,
        ):
            route = subject.send_to_openclaw("hello")

        self.assertEqual(route, "clipboard")
        self.assertEqual(copy_mock.call_count, 1)

        detail = subject.send_to_openclaw_result("hello")
        self.assertEqual(detail.route, "clipboard")
        self.assertEqual(detail.reason, "invalid_command")

    def test_send_to_openclaw_spawn_error_falls_back_to_clipboard(self) -> None:
        subject = self._make_subject()
        keyboard = _FakeKeyboardController()
        self._bind_keyboard(subject, keyboard)

        with (
            patch(
                "vibemouse.output.subprocess.Popen",
                side_effect=OSError("openclaw missing"),
            ),
            patch("vibemouse.output.pyperclip.copy") as copy_mock,
        ):
            route = subject.send_to_openclaw("hello")

        self.assertEqual(route, "clipboard")
        self.assertEqual(copy_mock.call_count, 1)

    def test_send_to_openclaw_retries_once_then_succeeds(self) -> None:
        subject = self._make_subject()
        keyboard = _FakeKeyboardController()
        self._bind_keyboard(subject, keyboard)
        setattr(subject, "_openclaw_retries", 1)

        popen_side_effects = [
            OSError("temporary spawn failure"),
            SimpleNamespace(),
        ]
        with patch(
            "vibemouse.output.subprocess.Popen",
            side_effect=popen_side_effects,
        ) as popen_mock:
            detail = subject.send_to_openclaw_result("hello")

        self.assertEqual(detail.route, "openclaw")
        self.assertEqual(detail.reason, "dispatched_after_retry_1")
        self.assertEqual(popen_mock.call_count, 2)

    def test_send_to_openclaw_retries_exhausted_falls_back_to_clipboard(self) -> None:
        subject = self._make_subject()
        keyboard = _FakeKeyboardController()
        self._bind_keyboard(subject, keyboard)
        setattr(subject, "_openclaw_retries", 1)

        with (
            patch(
                "vibemouse.output.subprocess.Popen",
                side_effect=OSError("spawn failure"),
            ),
            patch("vibemouse.output.pyperclip.copy") as copy_mock,
        ):
            detail = subject.send_to_openclaw_result("hello")

        self.assertEqual(detail.route, "clipboard")
        self.assertEqual(detail.reason, "spawn_error:OSError")
        self.assertEqual(copy_mock.call_count, 1)

    @staticmethod
    def _not_focused() -> bool:
        return False

    def test_inject_prefers_native_type_text_when_available(self) -> None:
        subject = self._make_subject()
        keyboard = _FakeKeyboardController()
        self._bind_keyboard(subject, keyboard)
        setattr(
            subject,
            "_system_integration",
            SimpleNamespace(
                type_text=lambda text: True,
                send_shortcut=lambda mod, key: False,
                is_terminal_window_active=lambda: None,
                paste_shortcuts=lambda terminal_active: (),
                send_enter_via_accessibility=lambda: None,
                is_text_input_focused=lambda: None,
            ),
        )

        route = subject.inject_or_clipboard("hello world")

        self.assertEqual(route, "typed")
        # pynput keyboard should NOT have been used
        self.assertEqual(keyboard.events, [])

    def test_inject_falls_through_when_type_text_returns_none(self) -> None:
        subject = self._make_subject()
        keyboard = _FakeKeyboardController()
        self._bind_keyboard(subject, keyboard)
        setattr(subject, "_is_text_input_focused", self._not_focused)
        setattr(
            subject,
            "_system_integration",
            SimpleNamespace(
                type_text=lambda text: None,
                send_shortcut=lambda mod, key: False,
                is_terminal_window_active=lambda: None,
                paste_shortcuts=lambda terminal_active: (),
                send_enter_via_accessibility=lambda: None,
                is_text_input_focused=lambda: None,
            ),
        )

        with patch("vibemouse.output.pyperclip.copy") as copy_mock:
            route = subject.inject_or_clipboard("hello", auto_paste=False)

        self.assertEqual(route, "clipboard")
        self.assertEqual(copy_mock.call_count, 1)

    def test_inject_falls_through_when_type_text_returns_false(self) -> None:
        subject = self._make_subject()
        keyboard = _FakeKeyboardController()
        self._bind_keyboard(subject, keyboard)
        setattr(subject, "_is_text_input_focused", self._not_focused)
        setattr(
            subject,
            "_system_integration",
            SimpleNamespace(
                type_text=lambda text: False,
                send_shortcut=lambda mod, key: False,
                is_terminal_window_active=lambda: None,
                paste_shortcuts=lambda terminal_active: (),
                send_enter_via_accessibility=lambda: None,
                is_text_input_focused=lambda: None,
            ),
        )

        with patch("vibemouse.output.pyperclip.copy") as copy_mock:
            route = subject.inject_or_clipboard("hello", auto_paste=False)

        self.assertEqual(route, "clipboard")
        self.assertEqual(copy_mock.call_count, 1)

    def test_inject_falls_through_when_type_text_raises(self) -> None:
        def exploding_type_text(text: str) -> bool:
            raise RuntimeError("CGEvent exploded")

        subject = self._make_subject()
        keyboard = _FakeKeyboardController()
        self._bind_keyboard(subject, keyboard)
        setattr(subject, "_is_text_input_focused", self._not_focused)
        setattr(
            subject,
            "_system_integration",
            SimpleNamespace(
                type_text=exploding_type_text,
                send_shortcut=lambda mod, key: False,
                is_terminal_window_active=lambda: None,
                paste_shortcuts=lambda terminal_active: (),
                send_enter_via_accessibility=lambda: None,
                is_text_input_focused=lambda: None,
            ),
        )

        with patch("vibemouse.output.pyperclip.copy") as copy_mock:
            route = subject.inject_or_clipboard("hello", auto_paste=False)

        self.assertEqual(route, "clipboard")
        self.assertEqual(copy_mock.call_count, 1)

    def test_clipboard_route_without_auto_paste(self) -> None:
        subject = self._make_subject()
        keyboard = _FakeKeyboardController()
        self._bind_keyboard(subject, keyboard)
        setattr(subject, "_is_text_input_focused", self._not_focused)

        copied: list[str] = []

        def fake_copy(text: str) -> None:
            copied.append(text)

        with patch("vibemouse.output.pyperclip.copy", side_effect=fake_copy):
            route = subject.inject_or_clipboard("  hello  ", auto_paste=False)

        self.assertEqual(route, "clipboard")
        self.assertEqual(copied, ["hello"])
        self.assertEqual(keyboard.events, [])

    def test_auto_paste_route_uses_ctrl_v(self) -> None:
        subject = self._make_subject()
        keyboard = _FakeKeyboardController()
        self._bind_keyboard(subject, keyboard)
        setattr(subject, "_is_text_input_focused", self._not_focused)

        with patch("vibemouse.output.pyperclip.copy") as copy_mock:
            route = subject.inject_or_clipboard("hello", auto_paste=True)

        self.assertEqual(route, "pasted")
        self.assertEqual(copy_mock.call_count, 1)
        self.assertEqual(
            keyboard.events,
            [
                ("press", "CTRL"),
                ("press", "v"),
                ("release", "v"),
                ("release", "CTRL"),
            ],
        )

    def test_auto_paste_uses_system_shortcut_candidates_when_available(self) -> None:
        subject = self._make_subject()
        keyboard = _FakeKeyboardController()
        self._bind_keyboard(subject, keyboard)
        setattr(subject, "_is_text_input_focused", self._not_focused)
        setattr(
            subject,
            "_system_integration",
            SimpleNamespace(
                type_text=lambda text: None,
                send_shortcut=lambda mod, key: mod == "ALT" and key == "V",
                is_terminal_window_active=lambda: True,
                paste_shortcuts=lambda terminal_active: (("ALT", "V"),)
                if terminal_active
                else (),
                send_enter_via_accessibility=lambda: None,
                is_text_input_focused=lambda: None,
            ),
        )

        with patch("vibemouse.output.pyperclip.copy") as copy_mock:
            route = subject.inject_or_clipboard("hello", auto_paste=True)

        self.assertEqual(route, "pasted")
        self.assertEqual(copy_mock.call_count, 1)
        self.assertEqual(keyboard.events, [])

    def test_auto_paste_system_shortcuts_fall_back_to_keyboard(self) -> None:
        subject = self._make_subject()
        keyboard = _FakeKeyboardController()
        self._bind_keyboard(subject, keyboard)
        setattr(subject, "_is_text_input_focused", self._not_focused)
        setattr(
            subject,
            "_system_integration",
            SimpleNamespace(
                type_text=lambda text: None,
                send_shortcut=lambda mod, key: False,
                is_terminal_window_active=lambda: True,
                paste_shortcuts=lambda terminal_active: (("ALT", "V"),)
                if terminal_active
                else (),
                send_enter_via_accessibility=lambda: None,
                is_text_input_focused=lambda: None,
            ),
        )

        with patch("vibemouse.output.pyperclip.copy") as copy_mock:
            route = subject.inject_or_clipboard("hello", auto_paste=True)

        self.assertEqual(route, "pasted")
        self.assertEqual(copy_mock.call_count, 1)
        self.assertEqual(
            keyboard.events,
            [
                ("press", "CTRL"),
                ("press", "v"),
                ("release", "v"),
                ("release", "CTRL"),
            ],
        )

    def test_terminal_detection_prefers_system_integration(self) -> None:
        subject = self._make_subject()
        keyboard = _FakeKeyboardController()
        self._bind_keyboard(subject, keyboard)
        setattr(
            subject,
            "_system_integration",
            SimpleNamespace(
                send_shortcut=lambda mod, key: False,
                is_terminal_window_active=lambda: True,
                paste_shortcuts=lambda terminal_active: (),
                send_enter_via_accessibility=lambda: None,
                is_text_input_focused=lambda: None,
            ),
        )

        probe = cast(
            Callable[[], bool],
            getattr(subject, "_is_terminal_window_active"),
        )
        self.assertTrue(probe())

    def test_auto_paste_failure_falls_back_to_clipboard(self) -> None:
        subject = self._make_subject()
        keyboard = _FakeKeyboardController()
        self._bind_keyboard(subject, keyboard)
        setattr(subject, "_is_text_input_focused", self._not_focused)

        def fail_paste() -> None:
            raise RuntimeError("paste failure")

        setattr(subject, "_paste_clipboard", fail_paste)

        with patch("vibemouse.output.pyperclip.copy") as copy_mock:
            route = subject.inject_or_clipboard("hello", auto_paste=True)

        self.assertEqual(route, "clipboard")
        self.assertEqual(copy_mock.call_count, 1)

    def test_send_enter_uses_enter_mode(self) -> None:
        subject = self._make_subject()
        keyboard = _FakeKeyboardController()
        self._bind_keyboard(subject, keyboard)

        with patch("vibemouse.output.time.sleep"):
            subject.send_enter(mode="enter")

        self.assertEqual(keyboard.events, [("press", "ENTER"), ("release", "ENTER")])

    def test_send_enter_supports_none_mode(self) -> None:
        subject = self._make_subject()
        keyboard = _FakeKeyboardController()
        self._bind_keyboard(subject, keyboard)

        subject.send_enter(mode="none")

        self.assertEqual(keyboard.events, [])

    def test_send_enter_prefers_system_accessibility_when_available(self) -> None:
        subject = self._make_subject()
        keyboard = _FakeKeyboardController()
        self._bind_keyboard(subject, keyboard)
        setattr(
            subject,
            "_system_integration",
            SimpleNamespace(send_enter_via_accessibility=lambda: True),
        )

        subject.send_enter(mode="enter")

        self.assertEqual(keyboard.events, [])

    def test_send_enter_falls_back_to_pynput_when_integration_returns_none(self) -> None:
        subject = self._make_subject()
        keyboard = _FakeKeyboardController()
        self._bind_keyboard(subject, keyboard)
        setattr(
            subject,
            "_system_integration",
            SimpleNamespace(send_enter_via_accessibility=lambda: None),
        )

        with patch("vibemouse.output.time.sleep"):
            subject.send_enter(mode="enter")

        self.assertEqual(keyboard.events, [("press", "ENTER"), ("release", "ENTER")])

    def test_send_enter_supports_ctrl_enter(self) -> None:
        subject = self._make_subject()
        keyboard = _FakeKeyboardController()
        self._bind_keyboard(subject, keyboard)

        with patch("vibemouse.output.time.sleep"):
            subject.send_enter(mode="ctrl_enter")

        self.assertEqual(
            keyboard.events,
            [
                ("press", "CTRL"),
                ("press", "ENTER"),
                ("release", "ENTER"),
                ("release", "CTRL"),
            ],
        )

    def test_send_enter_supports_shift_enter(self) -> None:
        subject = self._make_subject()
        keyboard = _FakeKeyboardController()
        self._bind_keyboard(subject, keyboard)

        with patch("vibemouse.output.time.sleep"):
            subject.send_enter(mode="shift_enter")

        self.assertEqual(
            keyboard.events,
            [
                ("press", "SHIFT"),
                ("press", "ENTER"),
                ("release", "ENTER"),
                ("release", "SHIFT"),
            ],
        )

    def test_send_enter_rejects_unknown_mode(self) -> None:
        subject = self._make_subject()
        keyboard = _FakeKeyboardController()
        self._bind_keyboard(subject, keyboard)

        with self.assertRaisesRegex(ValueError, "Unsupported enter mode"):
            subject.send_enter(mode="meta_enter")
