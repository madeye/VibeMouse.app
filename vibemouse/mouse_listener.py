from __future__ import annotations

import importlib
import threading
import time
from collections.abc import Callable


ButtonCallback = Callable[[], None]


class SideButtonListener:
    def __init__(
        self,
        on_front_press: ButtonCallback,
        on_rear_press: ButtonCallback,
        front_button: str,
        rear_button: str,
        debounce_s: float = 0.15,
    ) -> None:
        self._on_front_press: ButtonCallback = on_front_press
        self._on_rear_press: ButtonCallback = on_rear_press
        self._front_button: str = front_button
        self._rear_button: str = rear_button
        self._debounce_s: float = max(0.0, debounce_s)
        self._last_front_press_monotonic: float = 0.0
        self._last_rear_press_monotonic: float = 0.0
        self._debounce_lock: threading.Lock = threading.Lock()
        self._stop: threading.Event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        last_error_summary: str | None = None
        while not self._stop.is_set():
            try:
                self._run_quartz()
                return
            except Exception as quartz_error:
                summary = (
                    f"Mouse listener backend unavailable (quartz: {quartz_error}). Retrying..."
                )
                if summary != last_error_summary:
                    print(summary)
                    last_error_summary = summary
                if self._stop.wait(1.0):
                    return

    def _run_quartz(self) -> None:
        """Use NSEvent global monitors to capture mouse side buttons on macOS.

        NSEvent.addGlobalMonitorForEventsMatchingMask:handler: hooks into the
        main thread's NSApplication run loop, so it works even though this
        method runs on a daemon thread.
        """
        try:
            AppKit = importlib.import_module("AppKit")
            NSEvent = getattr(AppKit, "NSEvent")
        except Exception as error:
            raise RuntimeError("AppKit is not available") from error

        # NSEvent button numbers: 0=left, 1=right, 2=middle, 3=back, 4=forward
        ns_button_map: dict[str, int] = {"x1": 3, "x2": 4}
        front_button_num = ns_button_map[self._front_button]
        rear_button_num = ns_button_map[self._rear_button]

        # NSEventType constants
        NS_OTHER_MOUSE_DOWN = 25
        NS_OTHER_MOUSE_UP = 26

        # NSEventMask constants
        mask: int = (1 << NS_OTHER_MOUSE_DOWN) | (1 << NS_OTHER_MOUSE_UP)

        def handler(event: object) -> None:
            event_type: int = event.type()  # type: ignore[union-attr]
            button_num: int = event.buttonNumber()  # type: ignore[union-attr]

            if event_type == NS_OTHER_MOUSE_DOWN:
                if button_num == front_button_num:
                    self._dispatch_front_press()
                elif button_num == rear_button_num:
                    self._dispatch_rear_press()

        monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            mask, handler
        )
        if monitor is None:
            raise RuntimeError(
                "Failed to create NSEvent global monitor — check Accessibility permissions"
            )

        try:
            while not self._stop.is_set():
                self._stop.wait(0.5)
        finally:
            NSEvent.removeMonitor_(monitor)

    def _dispatch_front_press(self) -> None:
        if self._should_fire_front():
            self._on_front_press()

    def _dispatch_rear_press(self) -> None:
        if self._should_fire_rear():
            self._on_rear_press()

    def _should_fire_front(self) -> bool:
        now = time.monotonic()
        with self._debounce_lock:
            if now - self._last_front_press_monotonic < self._debounce_s:
                return False
            self._last_front_press_monotonic = now
            return True

    def _should_fire_rear(self) -> bool:
        now = time.monotonic()
        with self._debounce_lock:
            if now - self._last_rear_press_monotonic < self._debounce_s:
                return False
            self._last_rear_press_monotonic = now
            return True
