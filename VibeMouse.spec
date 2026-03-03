# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for VibeMouse.app.

Bundles the Python runtime, all dependencies, the ONNX model, and macOS
resources into a standalone .app that requires no pre-installed Python.

Usage:
    pyinstaller VibeMouse.spec
"""

import os
import sys
from pathlib import Path

block_cipher = None

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(SPECPATH)
VIBEMOUSE_PKG = ROOT / "vibemouse"
MODELS_DIR = VIBEMOUSE_PKG / "models"
RESOURCES_DIR = VIBEMOUSE_PKG / "macos" / "resources"

# ---------------------------------------------------------------------------
# Data files — model assets and macOS resources
# ---------------------------------------------------------------------------
datas = [
    (str(MODELS_DIR), os.path.join("vibemouse", "models")),
    (str(RESOURCES_DIR), os.path.join("vibemouse", "macos", "resources")),
]

# ---------------------------------------------------------------------------
# Hidden imports — dynamic imports that PyInstaller cannot detect
# ---------------------------------------------------------------------------
hiddenimports = [
    # pyobjc frameworks used via lazy / conditional imports
    "AppKit",
    "Foundation",
    "Quartz",
    "objc",
    "PyObjCTools",
    "PyObjCTools.AppHelper",
    "CoreFoundation",
    "AVFoundation",
    # pyobjc bridge modules
    "pyobjc",
    "pyobjc_framework_Cocoa",
    "pyobjc_framework_Quartz",
    "pyobjc_framework_AVFoundation",
    # vibemouse submodules imported at runtime
    "vibemouse.app",
    "vibemouse.audio",
    "vibemouse.audio_feedback",
    "vibemouse.config",
    "vibemouse.doctor",
    "vibemouse.mouse_listener",
    "vibemouse.output",
    "vibemouse.sensevoice_onnx",
    "vibemouse.system_integration",
    "vibemouse.transcriber",
    "vibemouse.macos",
    "vibemouse.macos.app_delegate",
    "vibemouse.macos.config_bridge",
    "vibemouse.macos.launchagent",
    "vibemouse.macos.permissions",
    # Runtime dependencies that may be imported dynamically
    "sounddevice",
    "soundfile",
    "pynput",
    "pynput.mouse",
    "pynput.keyboard",
    "pyperclip",
    "numpy",
    "onnxruntime",
    "kaldi_native_fbank",
    "sentencepiece",
    "yaml",
]

# ---------------------------------------------------------------------------
# Excludes — keep the bundle lean
# ---------------------------------------------------------------------------
excludes = [
    "tkinter",
    "matplotlib",
    "scipy",
    "pandas",
    "PIL",
    "cv2",
    "torch",
    "torchaudio",
    "torchvision",
    "funasr",
    "modelscope",
    "tensorflow",
    "openvino",
    "IPython",
    "notebook",
    "pytest",
    "setuptools",
    "pip",
    "wheel",
    "distutils",
]

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    [str(VIBEMOUSE_PKG / "macos_entry.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    cipher=block_cipher,
)

# ---------------------------------------------------------------------------
# PYZ — bytecode archive
# ---------------------------------------------------------------------------
pyz = PYZ(a.pure, cipher=block_cipher)

# ---------------------------------------------------------------------------
# EXE — the executable inside the .app
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VibeMouse",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,           # windowed app — no terminal
    target_arch=None,        # universal2 when building on appropriate SDK
)

# ---------------------------------------------------------------------------
# COLLECT — gather everything into dist/VibeMouse/
# ---------------------------------------------------------------------------
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="VibeMouse",
)

# ---------------------------------------------------------------------------
# BUNDLE — produce dist/VibeMouse.app
# ---------------------------------------------------------------------------
app = BUNDLE(
    coll,
    name="VibeMouse.app",
    icon=str(RESOURCES_DIR / "VibeMouse.icns"),
    bundle_identifier="com.vibemouse.app",
    info_plist={
        "CFBundleDisplayName": "VibeMouse",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        "LSMinimumSystemVersion": "13.0",
        "LSUIElement": True,          # menu-bar-only, no Dock icon
        "NSMicrophoneUsageDescription": (
            "VibeMouse needs microphone access to record speech for transcription."
        ),
        "NSHighResolutionCapable": True,
    },
)
