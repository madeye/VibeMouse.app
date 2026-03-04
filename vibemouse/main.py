from __future__ import annotations

from vibemouse.app import VoiceMouseApp
from vibemouse.config import load_config


def main() -> int:
    config = load_config()
    app = VoiceMouseApp(config)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
