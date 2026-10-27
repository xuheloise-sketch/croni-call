#!/bin/sh
# VOICE_TTS_CMD helper: render text with Microsoft Edge TTS (needs network, no key).
#   VOICE_TTS_CMD="/path/to/tools/edge_tts_wav.sh {text} {out}"
# Writes an MP3 and converts it to WAV at {out}; platform_compat then resamples to 16k mono.
set -e
text="$1"; out="$2"
voice="${VOICE_EDGE_VOICE:-zh-CN-YunxiNeural}"
here="$(cd "$(dirname "$0")" && pwd)"
edge="${VOICE_EDGE_TTS_BIN:-$(command -v edge-tts || echo "$here/../../venv/bin/edge-tts")}"
mp3="$(mktemp --suffix=.mp3)"
trap 'rm -f "$mp3"' EXIT
"$edge" --voice "$voice" --text "$text" --write-media "$mp3" >/dev/null 2>&1
ffmpeg -loglevel error -y -i "$mp3" -ar 16000 -ac 1 -sample_fmt s16 "$out"
