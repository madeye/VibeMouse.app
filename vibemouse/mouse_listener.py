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
        """Use a CGEventTap to intercept and consume mouse side-button events.

        Unlike NSEvent global monitors (which observe but cannot suppress
        events), a CGEventTap can swallow events before they reach other apps,
        preventing browsers from interpreting side buttons as back/forward.

        Requires Accessibility permissions.
        """
        Quartz = importlib.import_module("Quartz")

        # CGEvent constants
        kCGEventOtherMouseDown: int = 25
        kCGEventOtherMouseUp: int = 26

        # Button numbers: 2=middle, 3=back(x1), 4=forward(x2)
        cg_button_map: dict[str, int] = {"x1": 3, "x2": 4}
        front_button_num = cg_button_map[self._front_button]
        rear_button_num = cg_button_map[self._rear_button]
        consumed_buttons = {front_button_num, rear_button_num}

        def tap_callback(
            proxy: object,
            event_type: int,
            event: object,
            refcon: object,
        ) -> object:
            # If the tap is disabled by the system (e.g. timeout), re-enable it
            if event_type == Quartz.kCGEventTapDisabledByTimeout:
                Quartz.CGEventTapEnable(tap, True)
                return event

            if event_type == Quartz.kCGEventTapDisabledByUserInput:
                return event

            button: int = Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGMouseEventButtonNumber
            )
            if button not in consumed_buttons:
                return event  # pass through non-side-button events

            if event_type == kCGEventOtherMouseDown:
                if button == front_button_num:
                    self._dispatch_front_press()
                elif button == rear_button_num:
                    self._dispatch_rear_press()

            # Return None to consume the event (suppress browser back/forward)
            return None

        event_mask = (1 << kCGEventOtherMouseDown) | (1 << kCGEventOtherMouseUp)

        tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,  # active tap (can modify/suppress)
            event_mask,
            tap_callback,
            None,
        )
        if tap is None:
            raise RuntimeError(
                "Failed to create CGEventTap — check Accessibility permissions"
            )

        run_loop_source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
        run_loop = Quartz.CFRunLoopGetCurrent()
        Quartz.CFRunLoopAddSource(run_loop, run_loop_source, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(tap, True)

        try:
            while not self._stop.is_set():
                # Run the CFRunLoop briefly to process events, then check stop
                Quartz.CFRunLoopRunInMode(Quartz.kCFRunLoopDefaultMode, 0.5, False)
        finally:
            Quartz.CGEventTapEnable(tap, False)
            Quartz.CFRunLoopRemoveSource(run_loop, run_loop_source, Quartz.kCFRunLoopCommonModes)

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
