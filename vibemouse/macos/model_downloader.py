"""First-launch model downloader with splash screen UI."""

from __future__ import annotations

import os
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

import objc
from AppKit import (
    NSAlert,
    NSAlertFirstButtonReturn,
    NSApplication,
    NSBackingStoreBuffered,
    NSFont,
    NSMakeRect,
    NSProgressIndicator,
    NSProgressIndicatorBarStyle,
    NSTextField,
    NSWindow,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskTitled,
)
from Foundation import NSLog, NSObject

_CHUNK_SIZE = 8192

_ONNX_FILES = [
    "model_quant.onnx",
    "am.mvn",
    "config.yaml",
    "configuration.json",
    "tokens.json",
]

_TOKENIZER_FILE = "chn_jpn_yue_eng_ko_spectok.bpe.model"

_HF_ONNX_BASE = "https://huggingface.co/lovegaoshi/SenseVoiceSmall-onnx/resolve/main"
_MS_ONNX_BASE = "https://modelscope.cn/models/iic/SenseVoiceSmall-onnx/resolve/master"
_HF_TOK_BASE = "https://huggingface.co/FunAudioLLM/SenseVoiceSmall/resolve/main"
_MS_TOK_BASE = "https://modelscope.cn/models/iic/SenseVoiceSmall/resolve/master"


def model_cache_dir() -> Path:
    """Return the on-disk cache directory for the ONNX model."""
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / "VibeMouse"
        / "models"
        / "iic_SenseVoiceSmall-onnx"
    )


def is_model_cached() -> bool:
    """Check whether the ONNX model has already been downloaded."""
    return (model_cache_dir() / "model_quant.onnx").exists()


def _download_file(
    filename: str,
    dest_dir: Path,
    primary_base: str,
    fallback_base: str,
    progress_cb: Callable[[str, int, int], None] | None = None,
) -> None:
    """Download a single file with primary/fallback URL and atomic write."""
    dest = dest_dir / filename
    if dest.exists():
        return

    tmp = dest_dir / f"{filename}.tmp"
    urls = [f"{primary_base}/{filename}", f"{fallback_base}/{filename}"]

    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "VibeMouse/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                with open(tmp, "wb") as f:
                    while True:
                        chunk = resp.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb:
                            progress_cb(filename, downloaded, total)
            tmp.rename(dest)
            return
        except (urllib.error.URLError, OSError) as exc:
            NSLog(f"VibeMouse: download failed from {url}: {exc}")
            if tmp.exists():
                tmp.unlink()
            continue

    raise RuntimeError(f"Failed to download {filename} from all sources")


def download_model(
    progress_cb: Callable[[str, int, int, int, int], None] | None = None,
) -> Path:
    """Download all model files to the cache directory.

    progress_cb(filename, bytes_downloaded, bytes_total, file_index, file_count)
    """
    dest_dir = model_cache_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)

    all_files = _ONNX_FILES + [_TOKENIZER_FILE]

    for idx, filename in enumerate(all_files):
        if filename == _TOKENIZER_FILE:
            primary, fallback = _HF_TOK_BASE, _MS_TOK_BASE
        else:
            primary, fallback = _HF_ONNX_BASE, _MS_ONNX_BASE

        def _file_progress(fn: str, dl: int, total: int, i: int = idx, n: int = len(all_files)) -> None:
            if progress_cb:
                progress_cb(fn, dl, total, i, n)

        _download_file(filename, dest_dir, primary, fallback, _file_progress)

    return dest_dir


class ModelDownloadSplashController(NSObject):  # type: ignore[misc]
    """Splash window that downloads the speech model on first launch."""

    def initWithCallback_(self, callback: Callable[[], None]) -> ModelDownloadSplashController:
        self = objc.super(ModelDownloadSplashController, self).init()
        if self is None:
            return None  # type: ignore[return-value]
        self._callback = callback
        self._window: NSWindow | None = None
        self._progress_bar: NSProgressIndicator | None = None
        self._status_label: NSTextField | None = None
        return self

    def show(self) -> None:
        """Build and display the splash window, start background download."""
        w, h = 400, 180
        style = NSWindowStyleMaskTitled | NSWindowStyleMaskClosable
        self._window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, w, h), style, NSBackingStoreBuffered, False
        )
        self._window.setTitle_("VibeMouse")
        self._window.center()
        self._window.setLevel_(3)  # NSFloatingWindowLevel
        content = self._window.contentView()

        # Title label
        title = NSTextField.labelWithString_("Downloading speech model...")
        title.setFont_(NSFont.boldSystemFontOfSize_(14))
        title.setFrame_(NSMakeRect(20, h - 50, w - 40, 24))
        content.addSubview_(title)

        # Progress bar
        self._progress_bar = NSProgressIndicator.alloc().initWithFrame_(
            NSMakeRect(20, h - 90, w - 40, 20)
        )
        self._progress_bar.setStyle_(NSProgressIndicatorBarStyle)
        self._progress_bar.setIndeterminate_(False)
        self._progress_bar.setMinValue_(0)
        self._progress_bar.setMaxValue_(100)
        self._progress_bar.setDoubleValue_(0)
        content.addSubview_(self._progress_bar)

        # Status label
        self._status_label = NSTextField.labelWithString_("Preparing...")
        self._status_label.setFont_(NSFont.systemFontOfSize_(11))
        self._status_label.setFrame_(NSMakeRect(20, h - 120, w - 40, 18))
        content.addSubview_(self._status_label)

        self._window.makeKeyAndOrderFront_(None)

        # Start download on background thread
        t = threading.Thread(target=self._download_thread, daemon=True)
        t.start()

    def _download_thread(self) -> None:
        try:
            download_model(progress_cb=self._on_progress)
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                self._onDownloadComplete_, None, False
            )
        except Exception as exc:
            NSLog(f"VibeMouse: model download error: {exc}")
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                self._onDownloadError_, str(exc), False
            )

    def _on_progress(self, filename: str, downloaded: int, total: int, file_idx: int, file_count: int) -> None:
        mb_dl = downloaded / (1024 * 1024)
        if total > 0:
            file_frac = downloaded / total
        else:
            file_frac = 0
        overall = ((file_idx + file_frac) / file_count) * 100
        status = f"{filename}  ({mb_dl:.1f} MB)"
        info = {"progress": overall, "status": status}
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            self._updateUI_, info, False
        )

    @objc.typedSelector(b"v@:@")
    def _updateUI_(self, info: object) -> None:
        if self._progress_bar and isinstance(info, dict):
            self._progress_bar.setDoubleValue_(info.get("progress", 0))
        if self._status_label and isinstance(info, dict):
            self._status_label.setStringValue_(info.get("status", ""))

    @objc.typedSelector(b"v@:@")
    def _onDownloadComplete_(self, _: object) -> None:
        if self._window:
            self._window.close()
            self._window = None
        self._callback()

    @objc.typedSelector(b"v@:@")
    def _onDownloadError_(self, error_msg: object) -> None:
        if self._window:
            self._window.close()
            self._window = None

        alert = NSAlert.alloc().init()
        alert.setMessageText_("Model Download Failed")
        alert.setInformativeText_(f"Could not download the speech model:\n\n{error_msg}")
        alert.addButtonWithTitle_("Retry")
        alert.addButtonWithTitle_("Quit")
        result = alert.runModal()

        if result == NSAlertFirstButtonReturn:
            self.show()
        else:
            NSApplication.sharedApplication().terminate_(None)
