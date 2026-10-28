#!/usr/bin/env bash
set -euo pipefail

CONF="${RINGRINGRING_CONF:-/etc/croni-call/voice.env}"
PREFIX="${RINGRINGRING_HOME:-/opt/croni-call}"
SRC="/opt/whisper.cpp"
TAG="v1.9.5"
MODEL_DIR="$PREFIX/models"
MODEL="$MODEL_DIR/ggml-small-q5_1.bin"
MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small-q5_1.bin"
MODEL_SHA256="ae85e4a935d7a567bd102fe55afc16bb595bdb618e11b2fc7591bc08120411bb"

[ "$(id -u)" -eq 0 ] || { echo "run this installer as root" >&2; exit 1; }
[ -f "$CONF" ] || { echo "configuration file not found: $CONF" >&2; exit 1; }

echo "[croni-call] Installing build tools"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends build-essential cmake git curl ca-certificates

echo "[croni-call] Building whisper.cpp $TAG (this can take several minutes)"
rm -rf "$SRC"
git clone --depth 1 --branch "$TAG" https://github.com/ggml-org/whisper.cpp.git "$SRC"
cmake -S "$SRC" -B "$SRC/build" \
  -DCMAKE_BUILD_TYPE=Release \
  -DWHISPER_BUILD_TESTS=OFF \
  -DWHISPER_BUILD_EXAMPLES=ON \
  -DWHISPER_BUILD_SERVER=ON
cmake --build "$SRC/build" --config Release --target whisper-cli whisper-server -j2
install -m 0755 "$SRC/build/bin/whisper-cli" /usr/local/bin/whisper-cli
install -m 0755 "$SRC/build/bin/whisper-server" /usr/local/bin/whisper-server

mkdir -p "$MODEL_DIR"
if [ ! -f "$MODEL" ] || ! echo "$MODEL_SHA256  $MODEL" | sha256sum -c - >/dev/null 2>&1; then
  echo "[croni-call] Downloading the multilingual speech model (about 190 MB)"
  tmp_model="$MODEL.part"
  rm -f "$tmp_model"
  curl -fL --retry 3 --connect-timeout 15 "$MODEL_URL" -o "$tmp_model"
  echo "$MODEL_SHA256  $tmp_model" | sha256sum -c -
  mv "$tmp_model" "$MODEL"
fi
chmod 0644 "$MODEL"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
grep -Ev '^(VOICE_STT_(KEY|URL|MODEL)|GROQ_API_KEY|VOICE_GROQ_|WHISPER_(BIN|MODEL|SERVER_BIN|SERVER_MODEL|SERVER_IDLE_SEC))=' "$CONF" > "$tmp" || true
{
  cat "$tmp"
  printf '%s\n' "WHISPER_BIN=/usr/local/bin/whisper-cli"
  printf '%s\n' "WHISPER_MODEL=$MODEL"
  printf '%s\n' "WHISPER_SERVER_BIN=/usr/local/bin/whisper-server"
  printf '%s\n' "WHISPER_SERVER_MODEL=$MODEL"
  printf '%s\n' "WHISPER_SERVER_IDLE_SEC=120"
  printf '%s\n' "VOICE_STT_LANG=zh"
  printf '%s\n' "VOICE_START_TIMEOUT=7"
} > "$CONF"
chmod 0600 "$CONF"

echo "[croni-call] Local multilingual Whisper is installed."
echo "[croni-call] The unused Groq key was removed from the VPS configuration."
