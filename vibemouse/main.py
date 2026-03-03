from __future__ import annotations

import argparse

from vibemouse.app import VoiceMouseApp
from vibemouse.config import load_config
from vibemouse.doctor import run_doctor


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vibemouse")
    subparsers = parser.add_subparsers(dest="command")
    _ = subparsers.add_parser("run", help="run the voice-input daemon")
    doctor_parser = subparsers.add_parser("doctor", help="run environment diagnostics")
    _ = doctor_parser.add_argument(
        "--fix",
        action="store_true",
        help="apply safe auto-remediations before running checks",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    raw_command = getattr(args, "command", None)
    command = raw_command if isinstance(raw_command, str) else "run"
    if command == "doctor":
        apply_fixes_raw = getattr(args, "fix", False)
        apply_fixes = bool(apply_fixes_raw)
        return run_doctor(apply_fixes=apply_fixes)

    config = load_config()
    app = VoiceMouseApp(config)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
