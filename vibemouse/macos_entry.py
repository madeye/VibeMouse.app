"""Entry point for the VibeMouse.app macOS bundle.

Starts an NSApplication as a menu-bar-only accessory (no Dock icon) and
delegates to ``VibemouseAppDelegate`` which wires up the daemon thread.
"""

from __future__ import annotations

import sys


def main() -> None:
    if sys.platform != "darwin":
        print("macos_entry is only supported on macOS", file=sys.stderr)
        sys.exit(1)

    from AppKit import NSApplication, NSApplicationActivationPolicyAccessory

    from vibemouse.macos.app_delegate import VibemouseAppDelegate

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    delegate = VibemouseAppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.run()


if __name__ == "__main__":
    main()
