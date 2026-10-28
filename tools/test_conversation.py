#!/usr/bin/env python3
"""Place a short two-way SIP call and verify speech recognition."""

from __future__ import annotations

import os
from pathlib import Path


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

    from voice_agent import CallSession

    session = CallSession()
    try:
        print("[croni-call] starting two-way voice test", flush=True)
        session.start_lib()
        print("[croni-call] dialing the configured phone", flush=True)
        if not session.place_call():
            print("[croni-call] no answer or call setup failed", flush=True)
            return 2

        result = session.speak_interruptible(
            "Yolie，双向语音测试开始了。请对我说一句话，说完后稍微停一下。",
            listen_after=True,
            max_wait=15.0,
        )
        heard = (result.get("user") or "").strip()
        print(f"[croni-call] transcript: {heard!r}", flush=True)

        if heard:
            session.speak(f"我听见你说：{heard}")
            print("[croni-call] speech recognition succeeded", flush=True)
            return 0

        session.speak("这次没有听清。电话线路已经接通，我们再检查语音识别配置。")
        print("[croni-call] no speech was transcribed", flush=True)
        return 3
    finally:
        session.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
