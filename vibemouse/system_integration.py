from __future__ import annotations

import importlib
from typing import Protocol

from collections.abc import Mapping


_TERMINAL_CLASS_HINTS: set[str] = {
    "kitty",
    "alacritty",
    "wezterm",
    "ghostty",
    "tabby",
    "hyper",
    "warp",
    "iterm2",
    "iterm",
}

_TERMINAL_TITLE_HINTS: set[str] = {
    "terminal",
    "tmux",
    "bash",
    "zsh",
    "fish",
}


def is_terminal_window_payload(payload: Mapping[str, object]) -> bool:
    window_class = str(payload.get("class", "")).lower()
    initial_class = str(payload.get("initialClass", "")).lower()
    title = str(payload.get("title", "")).lower()

    if any(
        hint in window_class or hint in initial_class for hint in _TERMINAL_CLASS_HINTS
    ):
        return True

    return any(hint in title for hint in _TERMINAL_TITLE_HINTS)


class SystemIntegration(Protocol):
    def send_shortcut(self, *, mod: str, key: str) -> bool: ...

    def active_window(self) -> dict[str, object] | None: ...

    def cursor_position(self) -> tuple[int, int] | None: ...

    def move_cursor(self, *, x: int, y: int) -> bool: ...

    def switch_workspace(self, direction: str) -> bool: ...

    def type_text(self, text: str) -> bool | None: ...

    def is_text_input_focused(self) -> bool | None: ...

    def send_enter_via_accessibility(self) -> bool | None: ...

    def is_terminal_window_active(self) -> bool | None: ...

    def paste_shortcuts(
        self, *, terminal_active: bool
    ) -> tuple[tuple[str, str], ...]: ...


def _load_quartz() -> object | None:
    try:
        return importlib.import_module("Quartz")
    except Exception:
        return None


def _load_appkit() -> object | None:
    try:
        return importlib.import_module("AppKit")
    except Exception:
        return None


def _load_application_services() -> object | None:
    try:
        return importlib.import_module("ApplicationServices")
    except Exception:
        return None


_MACOS_KEY_CODES: dict[str, int] = {
    "V": 9,
    "C": 8,
    "X": 7,
    "A": 0,
    "Z": 6,
    "Return": 36,
    "Left": 123,
    "Right": 124,
    "Up": 126,
    "Down": 125,
    "Tab": 48,
    "Space": 49,
    "Escape": 53,
    "Insert": 114,
}

_MACOS_MODIFIER_FLAGS: dict[str, int] = {
    "CMD": 0x100000,
    "CTRL": 0x40000,
    "SHIFT": 0x20000,
    "ALT": 0x80000,
}

_MACOS_TERMINAL_BUNDLE_IDS: set[str] = {
    "com.apple.terminal",
    "com.googlecode.iterm2",
    "net.kovidgoyal.kitty",
    "io.alacritty",
    "com.github.wez.wezterm",
    "com.mitchellh.ghostty",
    "dev.warp.warp-stable",
    "org.tabby",
    "co.zeit.hyper",
}

_MACOS_TEXT_ROLES: set[str] = {
    "AXTextField",
    "AXTextArea",
    "AXComboBox",
    "AXSearchField",
    "AXWebArea",
}


class MacOSSystemIntegration:
    def __init__(self) -> None:
        self._quartz = _load_quartz()
        self._appkit = _load_appkit()
        self._ax = _load_application_services()

    def send_shortcut(self, *, mod: str, key: str) -> bool:
        quartz = self._quartz
        if quartz is None:
            return False

        key_code = _MACOS_KEY_CODES.get(key)
        if key_code is None:
            return False

        flags = 0
        for part in mod.strip().upper().split():
            flag = _MACOS_MODIFIER_FLAGS.get(part, 0)
            flags |= flag

        try:
            create_event = getattr(quartz, "CGEventCreateKeyboardEvent")
            set_flags = getattr(quartz, "CGEventSetFlags")
            post_event = getattr(quartz, "CGEventPost")
            k_hid = getattr(quartz, "kCGHIDEventTap")

            down = create_event(None, key_code, True)
            if flags:
                set_flags(down, flags)
            post_event(k_hid, down)

            up = create_event(None, key_code, False)
            if flags:
                set_flags(up, flags)
            post_event(k_hid, up)
            return True
        except Exception:
            return False

    def type_text(self, text: str) -> bool | None:
        quartz = self._quartz
        if quartz is None:
            return None

        try:
            create_event = getattr(quartz, "CGEventCreateKeyboardEvent")
            set_unicode = getattr(quartz, "CGEventKeyboardSetUnicodeString")
            post_event = getattr(quartz, "CGEventPost")
            k_hid = getattr(quartz, "kCGHIDEventTap")

            chunk_size = 20
            for i in range(0, len(text), chunk_size):
                chunk = text[i : i + chunk_size]

                down = create_event(None, 0, True)
                set_unicode(down, len(chunk), chunk)
                post_event(k_hid, down)

                up = create_event(None, 0, False)
                set_unicode(up, len(chunk), chunk)
                post_event(k_hid, up)

            return True
        except Exception:
            return False

    def active_window(self) -> dict[str, object] | None:
        appkit = self._appkit
        if appkit is None:
            return None

        try:
            ns_workspace = getattr(appkit, "NSWorkspace")
            shared = ns_workspace.sharedWorkspace()
            app = shared.frontmostApplication()
            if app is None:
                return None
            bundle_id = app.bundleIdentifier() or ""
            name = app.localizedName() or ""
            return {"class": bundle_id, "title": name}
        except Exception:
            return None

    def is_terminal_window_active(self) -> bool | None:
        payload = self.active_window()
        if payload is None:
            return None
        bundle_id = str(payload.get("class", "")).lower()
        if bundle_id in _MACOS_TERMINAL_BUNDLE_IDS:
            return True
        return is_terminal_window_payload(payload)

    def is_text_input_focused(self) -> bool | None:
        ax = self._ax
        if ax is None:
            return None

        try:
            create_system_wide = getattr(ax, "AXUIElementCreateSystemWide")
            system_wide = create_system_wide()

            # AXUIElementCopyAttributeValue returns (err, value)
            copy_attr = getattr(ax, "AXUIElementCopyAttributeValue")
            err, focused = copy_attr(system_wide, "AXFocusedUIElement", None)
            if err != 0 or focused is None:
                return False

            err, role = copy_attr(focused, "AXRole", None)
            if err != 0 or role is None:
                return False

            return str(role) in _MACOS_TEXT_ROLES
        except Exception:
            return None

    def send_enter_via_accessibility(self) -> bool | None:
        quartz = self._quartz
        if quartz is None:
            return None

        try:
            create_event = getattr(quartz, "CGEventCreateKeyboardEvent")
            post_event = getattr(quartz, "CGEventPost")
            k_hid = getattr(quartz, "kCGHIDEventTap")

            down = create_event(None, 36, True)
            post_event(k_hid, down)
            up = create_event(None, 36, False)
            post_event(k_hid, up)
            return True
        except Exception:
            return None

    def cursor_position(self) -> tuple[int, int] | None:
        quartz = self._quartz
        if quartz is None:
            return None

        try:
            create_event = getattr(quartz, "CGEventCreate")
            get_location = getattr(quartz, "CGEventGetLocation")
            event = create_event(None)
            point = get_location(event)
            return int(point.x), int(point.y)
        except Exception:
            return None

    def move_cursor(self, *, x: int, y: int) -> bool:
        quartz = self._quartz
        if quartz is None:
            return False

        try:
            warp = getattr(quartz, "CGWarpMouseCursorPosition")
            cg_point = getattr(quartz, "CGPoint")
            warp(cg_point(x, y))
            return True
        except Exception:
            return False

    def switch_workspace(self, direction: str) -> bool:
        quartz = self._quartz
        if quartz is None:
            return False

        arrow_code = 123 if direction == "left" else 124  # Left / Right arrow
        try:
            create_event = getattr(quartz, "CGEventCreateKeyboardEvent")
            set_flags = getattr(quartz, "CGEventSetFlags")
            post_event = getattr(quartz, "CGEventPost")
            k_hid = getattr(quartz, "kCGHIDEventTap")

            ctrl_flag = _MACOS_MODIFIER_FLAGS["CTRL"]
            down = create_event(None, arrow_code, True)
            set_flags(down, ctrl_flag)
            post_event(k_hid, down)

            up = create_event(None, arrow_code, False)
            set_flags(up, ctrl_flag)
            post_event(k_hid, up)
            return True
        except Exception:
            return False

    def paste_shortcuts(self, *, terminal_active: bool) -> tuple[tuple[str, str], ...]:
        if terminal_active:
            return (("CMD", "V"),)
        return (("CMD", "V"),)


def create_system_integration() -> MacOSSystemIntegration:
    return MacOSSystemIntegration()
