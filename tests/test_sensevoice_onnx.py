"""Integration test for SenseVoice ONNX transcription pipeline.

Generates a Chinese speech WAV via macOS TTS and verifies that the
self-contained ONNX pipeline transcribes it correctly.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf


def _tts_to_wav(text: str, voice: str, out_path: Path) -> None:
    """Use macOS ``say`` to synthesise *text* and save as 16 kHz mono WAV."""
    aiff_path = out_path.with_suffix(".aiff")
    subprocess.run(
        ["say", "-v", voice, "-o", str(aiff_path), text],
        check=True,
    )
    audio, sr = sf.read(str(aiff_path), dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    if sr != 16000:
        duration = len(audio) / sr
        n_samples = int(duration * 16000)
        indices = np.linspace(0, len(audio) - 1, n_samples)
        audio = np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)

    sf.write(str(out_path), audio, 16000)
    aiff_path.unlink(missing_ok=True)


_MODEL_DIR = Path(__file__).resolve().parent.parent / "vibemouse" / "models" / "SenseVoiceSmall"


@unittest.skipUnless(sys.platform == "darwin", "macOS TTS required")
@unittest.skipUnless(_MODEL_DIR.is_dir(), "SenseVoiceSmall model not present")
class TestSenseVoiceONNXChinese(unittest.TestCase):
    """Verify that the ONNX pipeline can transcribe Chinese speech."""

    def test_transcribe_chinese_tts(self) -> None:
        from vibemouse.sensevoice_onnx import SenseVoiceONNX

        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "zh_test.wav"
            _tts_to_wav("今天天气真好", "Meijia", wav_path)

            model = SenseVoiceONNX(str(_MODEL_DIR))
            result = model(str(wav_path), language="zh", textnorm="withitn")

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        text = result[0]
        self.assertIn("今天天气真好", text)
