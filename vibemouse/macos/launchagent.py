"""Self-registration for macOS login startup via LaunchAgent plist."""

from __future__ import annotations

from pathlib import Path

_PLIST_NAME = "com.vibemouse.app.plist"
_LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"


def _plist_path() -> Path:
    return _LAUNCH_AGENTS_DIR / _PLIST_NAME


def is_registered() -> bool:
    """Return True if the login-item plist exists."""
    return _plist_path().is_file()


def register_login_item(app_path: str) -> Path:
    """Write a LaunchAgent plist that opens *app_path* at login.

    Returns the path to the written plist file.
    """
    plist = _plist_path()
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"'
        ' "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        "<dict>\n"
        "  <key>Label</key>\n"
        "  <string>com.vibemouse.app</string>\n"
        "  <key>ProgramArguments</key>\n"
        "  <array>\n"
        "    <string>/usr/bin/open</string>\n"
        "    <string>-a</string>\n"
        f"    <string>{_xml_escape(app_path)}</string>\n"
        "  </array>\n"
        "  <key>RunAtLoad</key>\n"
        "  <true/>\n"
        "</dict>\n"
        "</plist>\n"
    )

    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_text(content, encoding="utf-8")
    return plist


def unregister_login_item() -> bool:
    """Remove the login-item plist.  Returns True if it existed."""
    plist = _plist_path()
    if plist.is_file():
        plist.unlink()
        return True
    return False


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
