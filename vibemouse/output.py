from __future__ import annotations

import importlib
import time
from typing import Protocol, cast

import pyperclip

from vibemouse.system_integration import (
    SystemIntegration,
    create_system_integration,
)


class TextOutput:
    def __init__(
        self,
        *,
        system_integration: SystemIntegration | None = None,
    ) -> None:
        try:
            keyboard_module = importlib.import_module("pynput.keyboard")
        except Exception as error:
            raise RuntimeError(
                f"Failed to load keyboard control dependencies: {error}"
            ) from error

        controller_ctor = cast(
            _ControllerCtor,
            getattr(cast(object, keyboard_module), "Controller"),
        )
        key_holder = cast(
            _KeyHolder,
            getattr(cast(object, keyboard_module), "Key"),
        )
        self._kb: _KeyboardController = controller_ctor()
        self._enter_key: object = key_holder.enter
        self._ctrl_key: object = key_holder.ctrl
        self._shift_key: object = key_holder.shift
        self._system_integration: SystemIntegration = (
            system_integration
            if system_integration is not None
            else create_system_integration()
        )

    def send_enter(self, *, mode: str = "enter") -> None:
        normalized = mode.strip().lower()
        if normalized == "none":
            return
        if normalized == "enter":
            result = self._system_integration.send_enter_via_accessibility()
            if result is True:
                return
            self._tap_key(self._enter_key)
            return
        if normalized == "ctrl_enter":
            self._tap_modified_key(self._ctrl_key, self._enter_key)
            return
        if normalized == "shift_enter":
            self._tap_modified_key(self._shift_key, self._enter_key)
            return
        raise ValueError(f"Unsupported enter mode: {mode!r}")

    def inject_or_clipboard(self, text: str, *, auto_paste: bool = False) -> str:
        normalized = text.strip()
        if not normalized:
            return "empty"

        try:
            if self._system_integration.type_text(normalized):
                return "typed"
        except Exception:
            pass

        if self._is_text_input_focused():
            self._kb.type(normalized)
            return "typed"

        pyperclip.copy(normalized)
        if auto_paste:
            try:
                self._paste_clipboard()
                return "pasted"
            except Exception:
                return "clipboard"
        return "clipboard"

    def _paste_clipboard(self) -> None:
        terminal_active = self._is_terminal_window_active()
        for mod, key in self._paste_shortcuts(terminal_active=terminal_active):
            if self._send_platform_shortcut(mod=mod, key=key):
                return

        # Final fallback: pynput Cmd+V
        self._kb.press(self._ctrl_key)
        self._kb.press("v")
        self._kb.release("v")
        self._kb.release(self._ctrl_key)

    def _tap_key(self, key: object) -> None:
        self._kb.press(key)
        time.sleep(0.012)
        self._kb.release(key)

    def _tap_modified_key(self, modifier: object, key: object) -> None:
        self._kb.press(modifier)
        self._kb.press(key)
        time.sleep(0.012)
        self._kb.release(key)
        self._kb.release(modifier)

    def _paste_shortcuts(self, *, terminal_active: bool) -> tuple[tuple[str, str], ...]:
        try:
            shortcuts = self._system_integration.paste_shortcuts(
                terminal_active=terminal_active
            )
        except Exception:
            shortcuts = ()
        if shortcuts:
            return shortcuts
        return (("CMD", "V"),)

    def _send_platform_shortcut(self, *, mod: str, key: str) -> bool:
        try:
            return bool(self._system_integration.send_shortcut(mod=mod, key=key))
        except Exception:
            return False

    def _is_terminal_window_active(self) -> bool:
        try:
            result = self._system_integration.is_terminal_window_active()
        except Exception:
            result = None
        if isinstance(result, bool):
            return result
        return False

    def _is_text_input_focused(self) -> bool:
        try:
            focused = self._system_integration.is_text_input_focused()
        except Exception:
            focused = None
        if isinstance(focused, bool):
            return focused
        return False


class _KeyboardController(Protocol):
    def press(self, key: object) -> None: ...

    def release(self, key: object) -> None: ...

    def type(self, text: str) -> None: ...


class _ControllerCtor(Protocol):
    def __call__(self) -> _KeyboardController: ...


class _KeyHolder(Protocol):
    enter: object
    ctrl: object
    shift: object
