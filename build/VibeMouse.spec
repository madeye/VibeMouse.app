# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for VibeMouse.app macOS bundle."""

import os
import sys

SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
PROJECT_DIR = os.path.dirname(SPEC_DIR)

block_cipher = None

a = Analysis(
    [os.path.join(PROJECT_DIR, "vibemouse", "macos_entry.py")],
    pathex=[],
    binaries=[],
    datas=[
        (os.path.join(PROJECT_DIR, "vibemouse", "macos", "resources"), "vibemouse/macos/resources"),
    ],
    hiddenimports=[
        # Core vibemouse modules
        "vibemouse",
        "vibemouse.app",
        "vibemouse.audio",
        "vibemouse.audio_feedback",
        "vibemouse.config",
        "vibemouse.deploy",
        "vibemouse.doctor",
        "vibemouse.sensevoice_coreml",
        "vibemouse.mouse_listener",
        "vibemouse.output",
        "vibemouse.system_integration",
        "vibemouse.transcriber",
        "vibemouse.macos",
        "vibemouse.macos.app_delegate",
        "vibemouse.macos.config_bridge",
        "vibemouse.macos.launchagent",
        "vibemouse.macos.model_downloader",
        "vibemouse.macos.permissions",
        "vibemouse.macos_entry",
        # pyobjc frameworks
        "objc",
        "AppKit",
        "Foundation",
        "Quartz",
        "ApplicationServices",
        "CoreFoundation",
        "AVFoundation",
        # Audio / input
        "sounddevice",
        "_sounddevice_data",
        "soundfile",
        # Keyboard control (used by output.py for typing/paste)
        "pynput",
        "pynput.keyboard",
        "pynput.keyboard._darwin",
        # ML / transcription
        "kaldi_native_fbank",
        "sentencepiece",
        "numpy",
        # Clipboard
        "pyperclip",
        # stdlib needed by pynput in frozen env
        "secrets",
    ],
    excludes=[
        # Linux-only
        "evdev",
        "gi",
        "PyGObject",
        # PyTorch backend (optional, not bundled)
        "torch",
        "funasr",
        # GUI/plotting libraries not needed
        "tkinter",
        "matplotlib",
        "PIL",
        "IPython",
        # Heavy transitive deps not needed at runtime
        "scipy",
        "sklearn",
        "scikit-learn",
        "coremltools",
        "librosa",
        "joblib",
        "threadpoolctl",
        "cattrs",
        "sympy",
        "tqdm",
        "pycparser",
        "modelscope",
        # Test frameworks
        "pytest",
        "_pytest",
        "unittest",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=os.path.join(PROJECT_DIR, "entitlements.plist"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="VibeMouse",
)

app = BUNDLE(
    coll,
    name="VibeMouse.app",
    icon=os.path.join(PROJECT_DIR, "vibemouse", "macos", "resources", "VibeMouse.icns"),
    bundle_identifier="com.vibemouse.app",
    info_plist={
        "LSUIElement": True,
        "LSMinimumSystemVersion": "12.0",
        "CFBundleDisplayName": "VibeMouse",
        "CFBundleName": "VibeMouse",
        "CFBundleIdentifier": "com.vibemouse.app",
        "CFBundleShortVersionString": "0.2.0",
        "CFBundleVersion": "0.2.0",
        "NSMicrophoneUsageDescription": (
            "VibeMouse needs microphone access to capture voice input "
            "for speech-to-text transcription."
        ),
        "NSHighResolutionCapable": True,
    },
)
