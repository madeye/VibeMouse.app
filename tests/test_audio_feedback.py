"""Tests for vibemouse.audio_feedback."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vibemouse import audio_feedback


class TestPlayStartTone(unittest.TestCase):
    @patch("vibemouse.audio_feedback.sd")
    def test_calls_sounddevice_play(self, mock_sd):
        audio_feedback.play_start_tone()
        mock_sd.play.assert_called_once()
        _args, kwargs = mock_sd.play.call_args
        self.assertEqual(kwargs["samplerate"], 44100)
        self.assertFalse(kwargs["blocking"])

    @patch("vibemouse.audio_feedback.sd")
    def test_start_tone_duration(self, mock_sd):
        audio_feedback.play_start_tone()
        wave = mock_sd.play.call_args[0][0]
        expected_samples = int(44100 * 0.1)
        self.assertEqual(len(wave), expected_samples)


class TestPlayStopTone(unittest.TestCase):
    @patch("vibemouse.audio_feedback.sd")
    def test_calls_sounddevice_play(self, mock_sd):
        audio_feedback.play_stop_tone()
        mock_sd.play.assert_called_once()
        _args, kwargs = mock_sd.play.call_args
        self.assertEqual(kwargs["samplerate"], 44100)
        self.assertFalse(kwargs["blocking"])

    @patch("vibemouse.audio_feedback.sd")
    def test_stop_tone_duration(self, mock_sd):
        audio_feedback.play_stop_tone()
        wave = mock_sd.play.call_args[0][0]
        expected_samples = int(44100 * 0.12)
        self.assertEqual(len(wave), expected_samples)


class TestSilentOnException(unittest.TestCase):
    @patch("vibemouse.audio_feedback.sd")
    def test_start_tone_silent_on_exception(self, mock_sd):
        mock_sd.play.side_effect = RuntimeError("no audio device")
        # Must not raise
        audio_feedback.play_start_tone()

    @patch("vibemouse.audio_feedback.sd")
    def test_stop_tone_silent_on_exception(self, mock_sd):
        mock_sd.play.side_effect = RuntimeError("no audio device")
        # Must not raise
        audio_feedback.play_stop_tone()


if __name__ == "__main__":
    unittest.main()
