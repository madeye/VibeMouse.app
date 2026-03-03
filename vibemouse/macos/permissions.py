"""Thin wrappers around macOS permission APIs (Accessibility + Microphone)."""

from __future__ import annotations

import importlib


def check_accessibility() -> bool:
    """Return True if this process has accessibility permission."""
    try:
        app_services = importlib.import_module("ApplicationServices")
        is_trusted = getattr(app_services, "AXIsProcessTrusted", None)
        if is_trusted is None:
            return False
        return bool(is_trusted())
    except Exception:
        return False


def prompt_accessibility() -> bool:
    """Prompt the user to grant accessibility permission.

    Returns the current trust state (may still be False until the user acts).
    """
    try:
        app_services = importlib.import_module("ApplicationServices")
        trusted_with_options = getattr(
            app_services, "AXIsProcessTrustedWithOptions", None
        )
        if trusted_with_options is None:
            return check_accessibility()

        core_foundation = importlib.import_module("CoreFoundation")
        k_prompt = getattr(
            app_services,
            "kAXTrustedCheckOptionPrompt",
            None,
        )
        if k_prompt is None:
            return check_accessibility()

        cf_true = getattr(core_foundation, "kCFBooleanTrue", True)
        options = {k_prompt: cf_true}
        return bool(trusted_with_options(options))
    except Exception:
        return check_accessibility()


def check_microphone() -> str:
    """Return the microphone authorization status.

    Returns one of: ``"authorized"``, ``"denied"``, ``"not_determined"``,
    ``"restricted"``, or ``"unknown"``.
    """
    try:
        av_foundation = importlib.import_module("AVFoundation")
        av_capture = getattr(av_foundation, "AVCaptureDevice", None)
        if av_capture is None:
            return "unknown"

        media_audio = getattr(av_foundation, "AVMediaTypeAudio", None)
        if media_audio is None:
            return "unknown"

        status = av_capture.authorizationStatusForMediaType_(media_audio)
        return {0: "not_determined", 1: "restricted", 2: "denied", 3: "authorized"}.get(
            status, "unknown"
        )
    except Exception:
        return "unknown"


def request_microphone(callback: object | None = None) -> None:
    """Request microphone access asynchronously.

    *callback* is an optional callable receiving a single ``bool`` argument
    indicating whether access was granted.  If ``None``, the prompt still
    appears but no callback fires.
    """
    try:
        av_foundation = importlib.import_module("AVFoundation")
        av_capture = getattr(av_foundation, "AVCaptureDevice", None)
        media_audio = getattr(av_foundation, "AVMediaTypeAudio", None)
        if av_capture is None or media_audio is None:
            return

        if callback is not None:
            av_capture.requestAccessForMediaType_completionHandler_(
                media_audio, callback
            )
        else:
            av_capture.requestAccessForMediaType_completionHandler_(
                media_audio, lambda granted: None
            )
    except Exception:
        pass
