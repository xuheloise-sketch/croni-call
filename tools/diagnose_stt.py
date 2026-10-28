#!/usr/bin/env python3
"""Check cloud STT without placing a phone call or exposing credentials."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import urllib.error


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
        "/etc/croni-call/voice.env",
    )).expanduser()
    _load_env(config)

    from voice_agent import USE_GROQ, _groq_transcribe, _rm, _tts_to_wav

    print(f"[diagnostic] cloud STT configured: {USE_GROQ}", flush=True)
    if not USE_GROQ:
        print("[diagnostic] VOICE_STT_KEY was not loaded", flush=True)
        return 2

    wav = ""
    try:
        print("[diagnostic] generating a local Chinese speech sample", flush=True)
        wav = _tts_to_wav("你好，Yolie，这是语音识别测试。")
        print("[diagnostic] sending the sample to Groq", flush=True)
        text = _groq_transcribe(wav).strip()
        print(f"[diagnostic] transcript: {text!r}", flush=True)
        if text:
            print("[diagnostic] CLOUD_STT_OK", flush=True)
            return 0
        print("[diagnostic] Groq returned an empty transcript", flush=True)
        return 3
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", "replace").strip()
        except Exception:
            detail = ""
        print(f"[diagnostic] Groq HTTP error: {exc.code}", flush=True)
        if detail:
            print(f"[diagnostic] response: {detail[:800]}", flush=True)
        return 4
    except urllib.error.URLError as exc:
        print(f"[diagnostic] network error: {type(exc.reason).__name__}", flush=True)
        return 5
    except Exception as exc:
        print(f"[diagnostic] error: {type(exc).__name__}: {str(exc)[:160]}", flush=True)
        return 6
    finally:
        if wav:
            _rm(wav)


if __name__ == "__main__":
    raise SystemExit(main())
