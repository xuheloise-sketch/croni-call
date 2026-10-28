#!/usr/bin/env python3
"""Test local Whisper without placing a SIP call."""

from __future__ import annotations

import os
from pathlib import Path


def load_env(path: Path) -> None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:]
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def main() -> int:
    load_env(Path(os.environ.get("RINGRINGRING_CONF", "/etc/croni-call/voice.env")))
    from voice_agent import USE_GROQ, _rm, _transcribe_stream, _tts_to_wav

    print(f"[local-stt] cloud mode enabled: {USE_GROQ}", flush=True)
    wav = ""
    try:
        print("[local-stt] generating a Chinese sample", flush=True)
        wav = _tts_to_wav("你好，Yolie，这是本地语音识别测试。")
        print("[local-stt] loading the local model and transcribing", flush=True)
        text = _transcribe_stream(wav).strip()
        print(f"[local-stt] transcript: {text!r}", flush=True)
        if text:
            print("[local-stt] LOCAL_STT_OK", flush=True)
            return 0
        print("[local-stt] empty transcript", flush=True)
        return 3
    finally:
        if wav:
            _rm(wav)


if __name__ == "__main__":
    raise SystemExit(main())
