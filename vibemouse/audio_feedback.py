"""Audible notification tones for recording start/stop."""

from __future__ import annotations

import numpy as np
import sounddevice as sd

_SAMPLE_RATE = 44100


def _play_tone(freq: float, duration: float, volume: float = 0.3) -> None:
    """Generate a sine wave with fade envelope and play it non-blocking."""
    try:
        t = np.linspace(0, duration, int(_SAMPLE_RATE * duration), endpoint=False, dtype=np.float32)
        wave = volume * np.sin(2 * np.pi * freq * t)

        # Short fade in/out to avoid click artifacts
        fade_samples = min(int(_SAMPLE_RATE * 0.01), len(t) // 4)
        if fade_samples > 0:
            fade_in = np.linspace(0, 1, fade_samples, dtype=np.float32)
            fade_out = np.linspace(1, 0, fade_samples, dtype=np.float32)
            wave[:fade_samples] *= fade_in
            wave[-fade_samples:] *= fade_out

        sd.play(wave, samplerate=_SAMPLE_RATE, blocking=False)
    except Exception:
        pass


def play_start_tone() -> None:
    """Short high-pitched bip for recording start."""
    _play_tone(880, 0.1)


def play_stop_tone() -> None:
    """Short lower-pitched boop for recording stop."""
    _play_tone(440, 0.12)
