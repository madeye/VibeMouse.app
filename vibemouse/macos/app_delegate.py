"""NSApplication delegate — menu bar icon for VibeMouse daemon."""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import objc
from AppKit import (
    NSApplication,
    NSImage,
    NSMenu,
    NSMenuItem,
    NSObject,
    NSStatusBar,
    NSVariableStatusItemLength,
)
from Foundation import NSBundle, NSLog

from vibemouse.config import load_config
from vibemouse.macos.config_bridge import load_preferences_into_environ, save_preference
from vibemouse.macos.launchagent import is_registered, register_login_item, unregister_login_item
from vibemouse.macos.permissions import (
    check_accessibility,
    check_microphone,
    prompt_accessibility,
    request_microphone,
)


def _resource_path(name: str) -> Path | None:
    """Resolve a resource inside the .app bundle, or adjacent to the source."""
    bundle = NSBundle.mainBundle()
    if bundle is not None:
        resource = bundle.pathForResource_ofType_(Path(name).stem, Path(name).suffix.lstrip("."))
        if resource is not None:
            return Path(str(resource))

    source_resources = Path(__file__).parent / "resources" / name
    if source_resources.is_file():
        return source_resources
    return None


class VibemouseAppDelegate(NSObject):  # type: ignore[misc]
    def applicationDidFinishLaunching_(self, notification: object) -> None:
        del notification

        # Redirect stdout/stderr to log file so print() output is visible
        log_dir = Path(os.path.expanduser("~/Library/Logs/VibeMouse"))
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "vibemouse.log"
        try:
            fh = open(log_file, "a", buffering=1)  # line-buffered  # noqa: SIM115
            sys.stdout = fh  # type: ignore[assignment]
            sys.stderr = fh  # type: ignore[assignment]
            NSLog(f"VibeMouse: logging to {log_file}")
        except Exception as exc:
            NSLog(f"VibeMouse: failed to redirect logs: {exc}")

        self._status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength
        )
        self._set_idle_icon()
        self._build_menu()

        load_preferences_into_environ()

        acc_ok = check_accessibility()
        NSLog(f"VibeMouse: accessibility={acc_ok}")
        if not acc_ok:
            prompt_accessibility()

        mic_status = check_microphone()
        NSLog(f"VibeMouse: microphone={mic_status}")
        if mic_status == "not_determined":
            request_microphone()

        try:
            config = load_config()
            NSLog("VibeMouse: config loaded successfully")
        except Exception as exc:
            NSLog(f"VibeMouse: failed to load config: {exc}")
            return

        from vibemouse.app import VoiceMouseApp

        try:
            self._voice_app = VoiceMouseApp(
                config,
                on_status_change=self._on_status_change,
            )
            NSLog("VibeMouse: VoiceMouseApp created")
        except Exception as exc:
            NSLog(f"VibeMouse: failed to create VoiceMouseApp: {exc}")
            return

        self._daemon_thread = threading.Thread(
            target=self._run_daemon,
            daemon=True,
        )
        self._daemon_thread.start()
        NSLog("VibeMouse: daemon thread started")

    def _run_daemon(self) -> None:
        try:
            NSLog("VibeMouse: daemon thread running VoiceMouseApp.run()")
            self._voice_app.run()
            NSLog("VibeMouse: daemon thread VoiceMouseApp.run() returned")
        except Exception as exc:
            import traceback
            NSLog(f"VibeMouse daemon error: {exc}")
            NSLog(f"VibeMouse daemon traceback: {traceback.format_exc()}")

    def _on_status_change(self, is_recording: bool) -> None:
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            self.updateIcon_,
            is_recording,
            False,
        )

    @objc.typedSelector(b"v@:@")
    def updateIcon_(self, is_recording: object) -> None:
        if is_recording:
            self._set_recording_icon()
        else:
            self._set_idle_icon()

    def _set_idle_icon(self) -> None:
        icon_path = _resource_path("icon_idle.pdf")
        if icon_path is not None:
            image = NSImage.alloc().initWithContentsOfFile_(str(icon_path))
            if image is not None:
                image.setTemplate_(True)
                self._status_item.button().setImage_(image)
                return
        self._status_item.button().setTitle_("VM")

    def _set_recording_icon(self) -> None:
        icon_path = _resource_path("icon_recording.pdf")
        if icon_path is not None:
            image = NSImage.alloc().initWithContentsOfFile_(str(icon_path))
            if image is not None:
                image.setTemplate_(True)
                self._status_item.button().setImage_(image)
                return
        self._status_item.button().setTitle_("REC")

    def _build_menu(self) -> None:
        menu = NSMenu.alloc().init()

        title_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "VibeMouse", None, ""
        )
        title_item.setEnabled_(False)
        menu.addItem_(title_item)

        menu.addItem_(NSMenuItem.separatorItem())

        self._login_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Start at Login", self.toggleLoginItem_, ""
        )
        self._login_item.setState_(1 if is_registered() else 0)
        menu.addItem_(self._login_item)

        device_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Input Device", None, ""
        )
        self._device_submenu = NSMenu.alloc().init()
        self._device_submenu.setDelegate_(self)
        device_item.setSubmenu_(self._device_submenu)
        menu.addItem_(device_item)

        menu.addItem_(NSMenuItem.separatorItem())

        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit", self.doQuit_, "q"
        )
        menu.addItem_(quit_item)

        self._status_item.setMenu_(menu)

    @objc.typedSelector(b"v@:@")
    def toggleLoginItem_(self, sender: object) -> None:
        del sender
        if is_registered():
            unregister_login_item()
            self._login_item.setState_(0)
        else:
            app_path = self._resolve_app_path()
            if app_path:
                register_login_item(app_path)
                self._login_item.setState_(1)

    @objc.typedSelector(b"v@:@")
    def doQuit_(self, sender: object) -> None:
        del sender
        if hasattr(self, "_voice_app"):
            try:
                self._voice_app.shutdown()
            except Exception:
                pass
        NSApplication.sharedApplication().terminate_(self)

    def menuNeedsUpdate_(self, menu: object) -> None:
        if menu is self._device_submenu:
            self._populate_device_submenu()

    def _populate_device_submenu(self) -> None:
        menu = self._device_submenu
        menu.removeAllItems()

        current = os.environ.get("VIBEMOUSE_AUDIO_INPUT_DEVICE", "").strip()
        if current.lower() == "default":
            current = ""

        default_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "System Default", self.selectInputDevice_, ""
        )
        default_item.setRepresentedObject_("")
        default_item.setState_(1 if not current else 0)
        menu.addItem_(default_item)

        menu.addItem_(NSMenuItem.separatorItem())

        for name in self._list_input_devices():
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                name, self.selectInputDevice_, ""
            )
            item.setRepresentedObject_(name)
            item.setState_(1 if name == current else 0)
            menu.addItem_(item)

    @staticmethod
    def _list_input_devices() -> list[str]:
        try:
            import sounddevice as sd

            devices = sd.query_devices()
        except Exception:
            return []
        names: list[str] = []
        seen: set[str] = set()
        if not isinstance(devices, list):
            devices = [devices]
        for dev in devices:
            if isinstance(dev, dict) and dev.get("max_input_channels", 0) > 0:
                name = dev.get("name", "")
                if name and name not in seen:
                    seen.add(name)
                    names.append(name)
        return names

    @objc.typedSelector(b"v@:@")
    def selectInputDevice_(self, sender: object) -> None:
        device_name = sender.representedObject()
        if device_name is None:
            device_name = ""
        save_preference("VIBEMOUSE_AUDIO_INPUT_DEVICE", device_name)
        if hasattr(self, "_voice_app"):
            self._voice_app._recorder._device = device_name if device_name else None

    @staticmethod
    def _resolve_app_path() -> str | None:
        bundle = NSBundle.mainBundle()
        if bundle is not None:
            path = bundle.bundlePath()
            if path and str(path).endswith(".app"):
                return str(path)

        exe = Path(sys.executable).resolve()
        for parent in exe.parents:
            if parent.suffix == ".app":
                return str(parent)
        return None
