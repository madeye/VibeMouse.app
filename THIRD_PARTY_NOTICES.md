# Third-Party Notices

This document summarizes third-party components used by VibeMouse and their
declared licenses.

Last reviewed: 2026-03-01.

## 1) Project License

VibeMouse source code is licensed under Apache-2.0. See `LICENSE`.

## 2) Direct Python Dependencies

The following are direct runtime dependencies declared in `pyproject.toml`.

| Package | Declared License | Upstream |
|---|---|---|
| `numpy` | BSD-3-Clause | https://numpy.org |
| `sounddevice` | MIT | https://python-sounddevice.readthedocs.io/ |
| `soundfile` | BSD-3-Clause | https://github.com/bastibe/python-soundfile |
| `pynput` | LGPL-3.0 (or later) | https://github.com/moses-palmer/pynput |
| `evdev` | BSD-3-Clause | https://github.com/gvalkov/python-evdev |
| `PyGObject` | LGPL-2.1 (or later) | https://pygobject.gnome.org |
| `pyperclip` | BSD | https://github.com/asweigart/pyperclip |
| `funasr` | MIT | https://github.com/modelscope/FunASR |
| `funasr-onnx` | MIT | https://pypi.org/project/funasr-onnx/ |
| `onnxruntime` | MIT | https://github.com/microsoft/onnxruntime |
| `openvino` | Apache-2.0 | https://github.com/openvinotoolkit/openvino |
| `modelscope` | Apache-2.0 | https://github.com/modelscope/modelscope |

Notes:

- `pynput` and `PyGObject` are LGPL-licensed. If you redistribute packaged
  binaries, ensure LGPL obligations are satisfied (license notice, relinking
  conditions where applicable, and source availability requirements for the
  LGPL-covered components).
- Transitive dependencies are not exhaustively listed here. They remain subject
  to their own licenses.

## 3) Model Assets and Weights

VibeMouse defaults to model IDs:

- `iic/SenseVoiceSmall`
- `iic/SenseVoiceSmall-onnx`

At review time, ModelScope API metadata reports both model IDs as
`Apache License 2.0`.

References:

- https://www.modelscope.cn/api/v1/models/iic/SenseVoiceSmall
- https://www.modelscope.cn/api/v1/models/iic/SenseVoiceSmall-onnx

Important caveat:

- The FunASR repository also contains a model-specific `MODEL_LICENSE` with
  additional terms for "FunASR Software" weights:
  https://raw.githubusercontent.com/modelscope/FunASR/main/MODEL_LICENSE
- If you switch to other model IDs, mirror-hosted weights, or bundled model
  artifacts, re-verify the exact model license/terms before redistribution.

## 4) Attribution and Compliance Guidance

When distributing VibeMouse (source or binaries):

1. Keep `LICENSE` and this notice file.
2. Preserve upstream copyright and license notices for bundled components.
3. Re-check model card licenses when changing model IDs or revisions.
4. Do not assume all speech models under the same ecosystem share identical
   license terms.
