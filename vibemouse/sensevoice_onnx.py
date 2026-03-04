"""Self-contained SenseVoice ONNX inference.

Replaces the ``funasr_onnx`` package with a minimal pipeline that depends
only on ``onnxruntime``, ``soundfile``, ``kaldi_native_fbank``,
``sentencepiece``, and ``numpy``.

Pipeline: WAV → fbank → LFR + CMVN → ONNX session → CTC decode → text
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import onnxruntime as ort
import sentencepiece as spm
import soundfile as sf
from kaldi_native_fbank import FbankOptions, FrameExtractionOptions, MelBanksOptions, OnlineFbank


_LANG_IDS: dict[str, int] = {
    "auto": 0,
    "zh": 3,
    "en": 4,
    "yue": 7,
    "ja": 11,
    "ko": 12,
    "nospeech": 13,
}

_TEXTNORM_IDS: dict[str, int] = {
    "withitn": 14,
    "woitn": 15,
}

# Regex to strip SenseVoice language/event tags like <|zh|>, <|HAPPY|>, etc.
_TAG_RE = re.compile(r"<\|[^|]+\|>")


class SenseVoiceONNX:
    """Self-contained SenseVoice-Small ONNX inference engine."""

    def __init__(self, model_dir: str | Path) -> None:
        model_dir = Path(model_dir)

        # ONNX session — prefer quantized model
        onnx_path = model_dir / "model_quant.onnx"
        if not onnx_path.exists():
            onnx_path = model_dir / "model.onnx"
        if not onnx_path.exists():
            raise FileNotFoundError(f"No ONNX model found in {model_dir}")

        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 4

        self._session = ort.InferenceSession(str(onnx_path), sess_options=opts)

        # Token vocabulary
        tokens_path = model_dir / "tokens.json"
        with open(tokens_path, encoding="utf-8") as f:
            token_list: list[str] = json.load(f)
        self._id2token: dict[int, str] = {i: t for i, t in enumerate(token_list)}

        # SentencePiece for detokenization
        bpe_path = model_dir / "chn_jpn_yue_eng_ko_spectok.bpe.model"
        self._sp = spm.SentencePieceProcessor()
        self._sp.Load(str(bpe_path))

        # CMVN stats
        means, vars_ = _parse_cmvn(model_dir / "am.mvn")
        self._cmvn_means = means  # shape (560,)
        self._cmvn_vars = vars_   # shape (560,)

        # LFR params from config.yaml
        self._lfr_m = 7
        self._lfr_n = 6

    def __call__(
        self,
        wav_path: str,
        *,
        language: str = "auto",
        textnorm: str = "withitn",
    ) -> list[str]:
        """Transcribe a WAV file.

        Returns a list with a single transcription string (matching the
        funasr_onnx interface).
        """
        # 1. Load audio
        audio, sr = sf.read(wav_path, dtype="float32")
        if sr != 16000:
            raise ValueError(f"Expected 16kHz audio, got {sr}Hz")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        # 2. Extract fbank features
        feats = _extract_fbank(audio, sample_rate=16000, n_mels=80)

        # 3. LFR (low frame rate) — stack + subsample
        feats = _apply_lfr(feats, self._lfr_m, self._lfr_n)

        # 4. CMVN normalization
        feats = (feats + self._cmvn_means) * self._cmvn_vars

        # 5. ONNX inference
        speech = feats[np.newaxis, :, :].astype(np.float32)
        speech_lengths = np.array([feats.shape[0]], dtype=np.int32)

        lang_id = _LANG_IDS.get(language, 0)
        norm_id = _TEXTNORM_IDS.get(textnorm, 14)

        language_arr = np.array([lang_id], dtype=np.int32)
        textnorm_arr = np.array([norm_id], dtype=np.int32)

        outputs = self._session.run(
            None,
            {
                "speech": speech,
                "speech_lengths": speech_lengths,
                "language": language_arr,
                "textnorm": textnorm_arr,
            },
        )
        logits = outputs[0]  # (1, T, vocab)

        # 6. CTC decode
        token_ids = _ctc_greedy_decode(logits[0])

        # 7. Token → text
        text = self._decode_tokens(token_ids)
        return [text]

    def _decode_tokens(self, token_ids: list[int]) -> str:
        """Map CTC output IDs to text via sentencepiece."""
        pieces: list[str] = []
        for tid in token_ids:
            tok = self._id2token.get(tid, "")
            if tok:
                pieces.append(tok)

        raw = self._sp.decode_pieces(pieces)
        # Strip SenseVoice special tags like <|zh|>, <|EMO_UNKNOWN|>, etc.
        return _TAG_RE.sub("", raw).strip()


def _extract_fbank(
    audio: np.ndarray,
    sample_rate: int = 16000,
    n_mels: int = 80,
) -> np.ndarray:
    """Extract log-Mel filterbank features using kaldi_native_fbank."""
    frame_opts = FrameExtractionOptions()
    frame_opts.samp_freq = sample_rate
    frame_opts.frame_length_ms = 25.0
    frame_opts.frame_shift_ms = 10.0
    frame_opts.dither = 0.0
    frame_opts.window_type = "hamming"
    frame_opts.snip_edges = True

    mel_opts = MelBanksOptions()
    mel_opts.num_bins = n_mels

    opts = FbankOptions()
    opts.frame_opts = frame_opts
    opts.mel_opts = mel_opts
    opts.energy_floor = 0.0

    fbank = OnlineFbank(opts)
    # Scale to int16 range — SenseVoice was trained with waveform * (1 << 15)
    fbank.accept_waveform(sample_rate, (audio * (1 << 15)).tolist())
    fbank.input_finished()

    n_frames = fbank.num_frames_ready
    feats = np.empty((n_frames, n_mels), dtype=np.float32)
    for i in range(n_frames):
        feats[i] = fbank.get_frame(i)

    return feats


def _apply_lfr(feats: np.ndarray, lfr_m: int, lfr_n: int) -> np.ndarray:
    """Stack ``lfr_m`` consecutive frames, subsample every ``lfr_n`` frames."""
    T, D = feats.shape
    T_lfr = int(np.ceil(T / lfr_n))

    # Left-pad by repeating the first frame (matches FunASR reference)
    left_pad = (lfr_m - 1) // 2
    if left_pad > 0:
        feats = np.vstack((np.tile(feats[0], (left_pad, 1)), feats))
        T = feats.shape[0]

    # Right-pad by repeating the last frame
    right_pad = T_lfr * lfr_n + lfr_m - 1 - left_pad - T
    if right_pad > 0:
        feats = np.vstack((feats, np.tile(feats[-1], (right_pad, 1))))
        T = feats.shape[0]

    lfr_feats = np.empty((T_lfr, lfr_m * D), dtype=np.float32)
    for i in range(T_lfr):
        start = i * lfr_n
        lfr_feats[i] = feats[start : start + lfr_m].reshape(-1)

    return lfr_feats


def _parse_cmvn(mvn_path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Parse the Kaldi-style am.mvn file for AddShift (means) and Rescale (vars)."""
    text = mvn_path.read_text()
    means = _parse_vector(text, "AddShift")
    vars_ = _parse_vector(text, "Rescale")
    return means, vars_


def _parse_vector(text: str, section_name: str) -> np.ndarray:
    """Extract the float vector from a named section in am.mvn."""
    idx = text.index(f"<{section_name}>")
    bracket_start = text.index("[", idx)
    bracket_end = text.index("]", bracket_start)
    values_str = text[bracket_start + 1 : bracket_end].split()
    return np.array([float(v) for v in values_str], dtype=np.float32)


def _ctc_greedy_decode(logits: np.ndarray) -> list[int]:
    """Greedy CTC decode: argmax → unique_consecutive → remove blank (0)."""
    ids = np.argmax(logits, axis=-1)  # (T,)

    # unique_consecutive
    mask = np.empty(ids.shape[0], dtype=bool)
    mask[0] = True
    mask[1:] = ids[1:] != ids[:-1]
    ids = ids[mask]

    # Remove blank_id=0
    return [int(x) for x in ids if x != 0]
