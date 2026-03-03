from __future__ import annotations

import importlib
import threading
import time
from collections.abc import Callable

from vibemouse.system_integration import SystemIntegration, create_system_integration


ButtonCallback = Callable[[], None]
GestureCallback = Callable[[str], None]


class SideButtonListener:
    def __init__(
        self,
        on_front_press: ButtonCallback,
        on_rear_press: ButtonCallback,
        front_button: str,
        rear_button: str,
        debounce_s: float = 0.15,
        on_gesture: GestureCallback | None = None,
        gestures_enabled: bool = False,
        gesture_trigger_button: str = "rear",
        gesture_threshold_px: int = 120,
        gesture_restore_cursor: bool = True,
        system_integration: SystemIntegration | None = None,
    ) -> None:
        if gesture_trigger_button not in {"front", "rear", "right"}:
            raise ValueError(
                "gesture_trigger_button must be one of: front, rear, right"
            )
        self._on_front_press: ButtonCallback = on_front_press
        self._on_rear_press: ButtonCallback = on_rear_press
        self._on_gesture: GestureCallback | None = on_gesture
        self._front_button: str = front_button
        self._rear_button: str = rear_button
        self._debounce_s: float = max(0.0, debounce_s)
        self._gestures_enabled: bool = gestures_enabled
        self._gesture_trigger_button: str = gesture_trigger_button
        self._gesture_threshold_px: int = max(1, gesture_threshold_px)
        self._gesture_restore_cursor: bool = gesture_restore_cursor
        self._system_integration: SystemIntegration = (
            system_integration
            if system_integration is not None
            else create_system_integration()
        )
        self._last_front_press_monotonic: float = 0.0
        self._last_rear_press_monotonic: float = 0.0
        self._debounce_lock: threading.Lock = threading.Lock()
        self._gesture_lock: threading.Lock = threading.Lock()
        self._gesture_active: bool = False
        self._gesture_dx: int = 0
        self._gesture_dy: int = 0
        self._gesture_last_position: tuple[int, int] | None = None
        self._gesture_anchor_cursor: tuple[int, int] | None = None
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
        NS_RIGHT_MOUSE_DOWN = 3
        NS_RIGHT_MOUSE_UP = 4
        NS_MOUSE_MOVED = 5

        # NSEventMask constants
        mask: int = (1 << NS_OTHER_MOUSE_DOWN) | (1 << NS_OTHER_MOUSE_UP)
        if self._gestures_enabled:
            mask |= 1 << NS_MOUSE_MOVED
            if self._gesture_trigger_button == "right":
                mask |= (1 << NS_RIGHT_MOUSE_DOWN) | (1 << NS_RIGHT_MOUSE_UP)

        def handler(event: object) -> None:
            event_type: int = event.type()  # type: ignore[union-attr]
            button_num: int = event.buttonNumber()  # type: ignore[union-attr]

            if event_type in (NS_OTHER_MOUSE_DOWN, NS_OTHER_MOUSE_UP):
                pressed = event_type == NS_OTHER_MOUSE_DOWN

                button_label: str | None = None
                if button_num == front_button_num:
                    button_label = "front"
                elif button_num == rear_button_num:
                    button_label = "rear"

                if button_label is not None:
                    if (
                        self._gestures_enabled
                        and self._is_gesture_trigger_button(button_label)
                    ):
                        if pressed:
                            loc = event.locationInWindow()  # type: ignore[union-attr]
                            self._start_gesture_capture(
                                initial_position=(int(loc.x), int(loc.y))
                            )
                        else:
                            self._finish_gesture_capture(button_label)
                    elif pressed:
                        self._dispatch_click(button_label)

            elif event_type in (NS_RIGHT_MOUSE_DOWN, NS_RIGHT_MOUSE_UP):
                if (
                    self._gestures_enabled
                    and self._gesture_trigger_button == "right"
                ):
                    pressed = event_type == NS_RIGHT_MOUSE_DOWN
                    if pressed:
                        loc = event.locationInWindow()  # type: ignore[union-attr]
                        self._start_gesture_capture(
                            initial_position=(int(loc.x), int(loc.y))
                        )
                    else:
                        self._finish_gesture_capture("right")

            elif event_type == NS_MOUSE_MOVED and self._gestures_enabled:
                loc = event.locationInWindow()  # type: ignore[union-attr]
                self._accumulate_gesture_position(int(loc.x), int(loc.y))

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

    def _dispatch_click(self, button_label: str) -> None:
        if button_label == "front":
            self._dispatch_front_press()
            return
        if button_label == "rear":
            self._dispatch_rear_press()
            return

    def _is_gesture_trigger_button(self, button_label: str) -> bool:
        return button_label == self._gesture_trigger_button

    def _start_gesture_capture(
        self,
        *,
        initial_position: tuple[int, int] | None = None,
    ) -> None:
        with self._gesture_lock:
            self._gesture_active = True
            self._gesture_dx = 0
            self._gesture_dy = 0
            self._gesture_last_position = initial_position
            if self._gesture_restore_cursor:
                self._gesture_anchor_cursor = self._read_cursor_position()
            else:
                self._gesture_anchor_cursor = None

    def _accumulate_gesture_position(self, x: int, y: int) -> None:
        with self._gesture_lock:
            if not self._gesture_active:
                return
            if self._gesture_last_position is None:
                self._gesture_last_position = (x, y)
                return
            last_x, last_y = self._gesture_last_position
            self._gesture_dx += x - last_x
            self._gesture_dy += y - last_y
            self._gesture_last_position = (x, y)

    def _finish_gesture_capture(self, button_label: str) -> None:
        with self._gesture_lock:
            if not self._gesture_active:
                return
            dx = self._gesture_dx
            dy = self._gesture_dy
            self._gesture_active = False
            self._gesture_dx = 0
            self._gesture_dy = 0
            self._gesture_last_position = None
            anchor_cursor = self._gesture_anchor_cursor
            self._gesture_anchor_cursor = None

        direction = self._classify_gesture(dx, dy, self._gesture_threshold_px)
        if direction is None:
            self._dispatch_click(button_label)
            return
        self._dispatch_gesture(direction)
        if anchor_cursor is not None:
            self._restore_cursor_position(anchor_cursor)

    def _dispatch_gesture(self, direction: str) -> None:
        callback = self._on_gesture
        if callback is None:
            return
        callback(direction)

    def _read_cursor_position(self) -> tuple[int, int] | None:
        try:
            return self._system_integration.cursor_position()
        except Exception:
            return None

    def _restore_cursor_position(self, position: tuple[int, int]) -> None:
        x, y = position
        try:
            self._system_integration.move_cursor(x=x, y=y)
        except Exception:
            return

    @staticmethod
    def _classify_gesture(dx: int, dy: int, threshold_px: int) -> str | None:
        if max(abs(dx), abs(dy)) < threshold_px:
            return None
        if abs(dx) >= abs(dy):
            return "right" if dx > 0 else "left"
        return "down" if dy > 0 else "up"

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
