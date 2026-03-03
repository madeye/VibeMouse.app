from __future__ import annotations

import importlib
import shlex
import subprocess
import time
from dataclasses import dataclass
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
        openclaw_command: str = "openclaw",
        openclaw_agent: str | None = None,
        openclaw_timeout_s: float = 20.0,
        openclaw_retries: int = 0,
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
        self._openclaw_command: str = openclaw_command
        self._openclaw_agent: str | None = openclaw_agent
        self._openclaw_timeout_s: float = max(0.5, openclaw_timeout_s)
        self._openclaw_retries: int = max(0, int(openclaw_retries))

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

    def send_to_openclaw(self, text: str) -> str:
        return self.send_to_openclaw_result(text).route

    def send_to_openclaw_result(self, text: str) -> "OpenClawDispatchResult":
        normalized = text.strip()
        if not normalized:
            return OpenClawDispatchResult(route="empty", reason="empty_text")

        command = self._build_openclaw_command(normalized)
        if command is None:
            pyperclip.copy(normalized)
            return OpenClawDispatchResult(route="clipboard", reason="invalid_command")

        attempts = max(1, int(getattr(self, "_openclaw_retries", 0)) + 1)
        last_reason = "spawn_error"
        for attempt in range(attempts):
            try:
                _ = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                if attempt == 0:
                    return OpenClawDispatchResult(
                        route="openclaw",
                        reason="dispatched",
                    )
                return OpenClawDispatchResult(
                    route="openclaw",
                    reason=f"dispatched_after_retry_{attempt}",
                )
            except OSError as error:
                last_reason = f"spawn_error:{error.__class__.__name__}"

        pyperclip.copy(normalized)
        return OpenClawDispatchResult(route="clipboard", reason=last_reason)

    def _build_openclaw_command(self, message: str) -> list[str] | None:
        raw_command = str(getattr(self, "_openclaw_command", "openclaw")).strip()
        if not raw_command:
            return None

        try:
            parts = shlex.split(raw_command)
        except ValueError:
            return None

        if not parts:
            return None

        command = [*parts, "agent", "--message", message, "--json"]
        agent = getattr(self, "_openclaw_agent", None)
        if isinstance(agent, str):
            normalized_agent = agent.strip()
            if normalized_agent:
                command.extend(["--agent", normalized_agent])
        return command

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


@dataclass(frozen=True)
class OpenClawDispatchResult:
    route: str
    reason: str
