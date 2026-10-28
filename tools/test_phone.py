#!/usr/bin/env python3
"""Place one short SIP test call without starting an MCP client.

This is deliberately one-way: it verifies SIP registration, ringing and TTS
without requiring an STT provider key.  Credentials are loaded from the same
private voice.env file used by the service and are never printed.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys


def _load_env(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(f"configuration file not found: {path}")
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    config = Path(os.environ.get(
        "RINGRINGRING_CONF",
        "~/.config/ringringring/voice.env",
    )).expanduser()
    _load_env(config)

    # Import only after configuration and pjsua2 paths are present.
    from voice_agent import CallSession

    opening = " ".join(sys.argv[1:]).strip() or "Yolie，晚上好。这里是克罗尼的第一次测试来电。"
    session = CallSession()
    try:
        print("[croni-call] starting SIP engine", flush=True)
        session.start_lib()
        print("[croni-call] dialing the configured phone", flush=True)
        if not session.place_call():
            print("[croni-call] no answer or call setup failed", file=sys.stderr)
            return 2
        session.speak(opening)
        print("[croni-call] audio delivered; ending test call", flush=True)
        session.hangup()
        return 0
    finally:
        session.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
