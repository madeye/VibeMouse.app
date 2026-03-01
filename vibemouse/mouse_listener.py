from __future__ import annotations

import importlib
import threading
import time
from collections.abc import Callable
from typing import Protocol, cast


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
                self._run_evdev()
                return
            except Exception as evdev_error:
                try:
                    self._run_pynput()
                    return
                except Exception as pynput_error:
                    summary = (
                        "Mouse listener backends unavailable "
                        + f"(evdev: {evdev_error}; pynput: {pynput_error}). Retrying..."
                    )
                    if summary != last_error_summary:
                        print(summary)
                        last_error_summary = summary
                    if self._stop.wait(1.0):
                        return

    def _run_evdev(self) -> None:
        import select

        try:
            evdev_module = importlib.import_module("evdev")
        except Exception as error:
            raise RuntimeError("evdev is not available") from error

        input_device_ctor = cast(_InputDeviceCtor, getattr(evdev_module, "InputDevice"))
        ecodes = cast(_Ecodes, getattr(evdev_module, "ecodes"))
        list_devices = cast(_ListDevicesFn, getattr(evdev_module, "list_devices"))

        side_codes = {
            "x1": ecodes.BTN_SIDE,
            "x2": ecodes.BTN_EXTRA,
        }
        front_code = side_codes[self._front_button]
        rear_code = side_codes[self._rear_button]

        devices: list[_EvdevDevice] = []
        for path in list_devices():
            try:
                dev = input_device_ctor(path)
            except Exception:
                continue
            try:
                caps = dev.capabilities()
                key_cap = caps.get(ecodes.EV_KEY, [])
                if front_code not in key_cap and rear_code not in key_cap:
                    dev.close()
                    continue

                btn_mouse = getattr(ecodes, "BTN_MOUSE", None)
                has_pointer_button = ecodes.BTN_LEFT in key_cap or (
                    isinstance(btn_mouse, int) and btn_mouse in key_cap
                )
                if not has_pointer_button:
                    dev.close()
                    continue

                devices.append(dev)
            except Exception:
                dev.close()

        if not devices:
            raise RuntimeError("No input device with side-button capability found")

        try:
            fd_map: dict[int, _EvdevDevice] = {dev.fd: dev for dev in devices}
            while not self._stop.is_set():
                ready, _, _ = select.select(list(fd_map.keys()), [], [], 0.2)
                for fd in ready:
                    dev = fd_map[fd]
                    for event in dev.read():
                        if event.type != ecodes.EV_KEY or event.value != 1:
                            continue
                        if event.code == front_code:
                            self._dispatch_front_press()
                        elif event.code == rear_code:
                            self._dispatch_rear_press()
        finally:
            for dev in devices:
                dev.close()

    def _run_pynput(self) -> None:
        try:
            mouse_module = importlib.import_module("pynput.mouse")
        except Exception as error:
            raise RuntimeError("pynput.mouse is not available") from error

        listener_ctor = cast(_MouseListenerCtor, getattr(mouse_module, "Listener"))

        button_map = {
            "x1": {"x1", "x_button1", "button8"},
            "x2": {"x2", "x_button2", "button9"},
        }

        front_candidates = button_map[self._front_button]
        rear_candidates = button_map[self._rear_button]

        def on_click(_x: int, _y: int, button: object, pressed: bool) -> None:
            if not pressed:
                return
            btn_name = str(button).lower().split(".")[-1]
            if btn_name in front_candidates:
                self._dispatch_front_press()
            elif btn_name in rear_candidates:
                self._dispatch_rear_press()

        listener = listener_ctor(on_click=on_click)
        listener.start()
        try:
            while not self._stop.is_set():
                time.sleep(0.2)
        finally:
            listener.stop()

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


class _EvdevEvent(Protocol):
    type: int
    value: int
    code: int


class _EvdevDevice(Protocol):
    fd: int

    def read(self) -> list[_EvdevEvent]: ...

    def capabilities(self) -> dict[int, list[int]]: ...

    def close(self) -> None: ...


class _InputDeviceCtor(Protocol):
    def __call__(self, path: str) -> _EvdevDevice: ...


class _ListDevicesFn(Protocol):
    def __call__(self) -> list[str]: ...


class _Ecodes(Protocol):
    BTN_SIDE: int
    BTN_EXTRA: int
    BTN_LEFT: int
    EV_KEY: int


class _MouseListener(Protocol):
    def start(self) -> None: ...

    def stop(self) -> None: ...


class _MouseListenerCtor(Protocol):
    def __call__(
        self,
        *,
        on_click: Callable[[int, int, object, bool], None],
    ) -> _MouseListener: ...
