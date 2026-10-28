#!/usr/bin/env python3
"""Distinguish Groq account/network denial from speech-model permissions."""

from __future__ import annotations

import json
import os
from pathlib import Path
import urllib.error
import urllib.request


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
    key = os.environ.get("VOICE_STT_KEY", "").strip() or os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        print("[access] no Groq key loaded")
        return 2

    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/models",
        headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "User-Agent": "croni-call-diagnostic/1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
        ids = {item.get("id") for item in payload.get("data", [])}
        print("[access] models endpoint: 200")
        print(f"[access] whisper-large-v3-turbo available: {'whisper-large-v3-turbo' in ids}")
        print("[access] GROQ_ACCOUNT_AND_NETWORK_OK")
        return 0
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", "replace").strip()
        except Exception:
            detail = ""
        server = exc.headers.get("server", "")
        ray = exc.headers.get("cf-ray", "")
        print(f"[access] models endpoint HTTP: {exc.code}")
        print(f"[access] server: {server or '(not supplied)'}")
        if ray:
            print(f"[access] edge trace: {ray}")
        print(f"[access] response body: {detail[:800] if detail else '(empty)'}")
        return 3
    except urllib.error.URLError as exc:
        print(f"[access] network error: {type(exc.reason).__name__}")
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
