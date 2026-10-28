#!/usr/bin/env bash
set -euo pipefail

CONF="${RINGRINGRING_CONF:-/etc/croni-call/voice.env}"
PREFIX="${RINGRINGRING_HOME:-/opt/croni-call}"
TEST_URL="https://raw.githubusercontent.com/xuheloise-sketch/croni-call/croni-vps-stage-a/tools/test_conversation.py"

[ "$(id -u)" -eq 0 ] || { echo "run this helper as root" >&2; exit 1; }
[ -f "$CONF" ] || { echo "configuration file not found: $CONF" >&2; exit 1; }
[ -x "$PREFIX/venv/bin/python" ] || { echo "phone runtime not found under $PREFIX" >&2; exit 1; }

printf 'Paste Groq API key (input is hidden), then press Enter: ' >/dev/tty
IFS= read -r -s groq_key </dev/tty
printf '\n' >/dev/tty
[ -n "$groq_key" ] || { echo "API key cannot be empty" >&2; exit 1; }

tmp="$(mktemp)"
trap 'rm -f "$tmp"; unset groq_key' EXIT
grep -Ev '^VOICE_STT_(KEY|URL|MODEL)=' "$CONF" > "$tmp" || true
{
  cat "$tmp"
  printf 'VOICE_STT_KEY=%s\n' "$groq_key"
  printf '%s\n' 'VOICE_STT_URL=https://api.groq.com/openai/v1/audio/transcriptions'
  printf '%s\n' 'VOICE_STT_MODEL=whisper-large-v3-turbo'
} > "$CONF"
chmod 0600 "$CONF"
unset groq_key

curl -fsSL "$TEST_URL" -o "$PREFIX/app/test_conversation.py"
chmod 0755 "$PREFIX/app/test_conversation.py"

cat > /usr/local/bin/croni-call-conversation-test <<EOF
#!/usr/bin/env bash
set -euo pipefail
export RINGRINGRING_CONF="$CONF"
export PYTHONPATH="$PREFIX/pjsua2/python:$PREFIX/app"
export LD_LIBRARY_PATH="$PREFIX/pjsua2/lib"
export PATH="$PREFIX/venv/bin:\$PATH"
exec "$PREFIX/venv/bin/python" "$PREFIX/app/test_conversation.py"
EOF
chmod 0755 /usr/local/bin/croni-call-conversation-test

echo '[croni-call] Groq speech recognition is configured.'
echo '[croni-call] Run: croni-call-conversation-test'
