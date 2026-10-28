#!/usr/bin/env bash
# Interactive first-stage installer for a fresh Ubuntu 22.04 x86_64 VPS.
# Installs the phone core, writes secrets only on the VPS, and creates a one-way
# test-call command. It does not expose any network service.
set -euo pipefail

REPO_URL="${CRONI_REPO_URL:-https://github.com/xuheloise-sketch/croni-call.git}"
REPO_BRANCH="${CRONI_REPO_BRANCH:-croni-vps-stage-a}"
CHECKOUT="${CRONI_CHECKOUT:-/opt/croni-call-src}"
PREFIX="${RINGRINGRING_HOME:-/opt/croni-call}"
CONF="${RINGRINGRING_CONF:-/etc/croni-call/voice.env}"
PJS_URL="https://github.com/yanyan1115/ringringring/releases/download/v0.1.0/pjsua2-2.17-linux-x86_64-cp311.tar.gz"
PJS_SHA256="a5a25f65af77a35b7c12ca6ee4f1b3c145007959564dd281f3699dfd0bc4300b"

say() { printf '\n[croni-call] %s\n' "$*"; }
die() { printf '\n[croni-call] ERROR: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run this installer as root"
[ "$(uname -m)" = "x86_64" ] || die "this installer requires x86_64"
. /etc/os-release
[ "${ID:-}" = "ubuntu" ] && [ "${VERSION_ID:-}" = "22.04" ] \
  || die "this installer currently supports Ubuntu 22.04 only"

say "Installing Ubuntu packages and Python 3.11"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -q --no-install-recommends \
  ca-certificates curl git gnupg software-properties-common \
  libssl3 libasound2 libopus0 libuuid1 ffmpeg >/dev/null
if ! command -v python3.11 >/dev/null 2>&1; then
  add-apt-repository -y ppa:deadsnakes/ppa >/dev/null
  apt-get update -qq
fi
apt-get install -y -q --no-install-recommends python3.11 python3.11-venv >/dev/null

say "Fetching Croni Call source"
if [ -d "$CHECKOUT/.git" ]; then
  git -C "$CHECKOUT" fetch --depth 1 origin "$REPO_BRANCH"
  git -C "$CHECKOUT" checkout -f FETCH_HEAD
else
  rm -rf "$CHECKOUT"
  git clone --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" "$CHECKOUT"
fi

say "Downloading and verifying the prebuilt SIP runtime"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
curl -fsSL "$PJS_URL" -o "$tmp/pjsua2.tar.gz"
printf '%s  %s\n' "$PJS_SHA256" "$tmp/pjsua2.tar.gz" | sha256sum -c - >/dev/null \
  || die "pjsua2 checksum mismatch"
printf '%s  %s\n' "$PJS_SHA256" "$(basename "$PJS_URL")" > "$tmp/pjsua2.tar.gz.sha256"

say "Installing the phone core"
RINGRINGRING_HOME="$PREFIX" RINGRINGRING_CONF="$CONF" PYTHON_BIN=python3.11 \
  bash "$CHECKOUT/plugin-native/bin/install.sh" \
    --pjsua2 "$tmp/pjsua2.tar.gz" --src "$CHECKOUT"
install -m 0755 "$CHECKOUT/tools/test_phone.py" "$PREFIX/app/test_phone.py"

printf '\nThe following values stay only on this VPS. Nothing is uploaded.\n'
read -r -p 'AI Linphone username (without sip: or domain): ' sip_user
[ -n "$sip_user" ] || die "AI Linphone username is required"
read -r -s -p 'AI Linphone password: ' sip_pass; printf '\n'
[ -n "$sip_pass" ] || die "AI Linphone password is required"
read -r -p 'Phone Linphone username (without sip: or domain): ' callee_user
[ -n "$callee_user" ] || die "phone Linphone username is required"
read -r -p 'Caller display name [Croni]: ' display_name
display_name="${display_name:-Croni}"

install -d -m 0700 "$(dirname "$CONF")"
umask 077
cat > "$CONF" <<EOF
VOICE_SIP_ID=sip:${sip_user}@sip.linphone.org
VOICE_SIP_USER=${sip_user}
VOICE_SIP_PASS=${sip_pass}
VOICE_SIP_CALLEE=sip:${callee_user}@sip.linphone.org
VOICE_DISPLAY_NAME=${display_name}
VOICE_STT_LANG=zh
VOICE_EDGE_VOICE=zh-CN-YunxiNeural
VOICE_TTS=edge
VOICE_STUN=stun.linphone.org:3478
VOICE_NULL_AUDIO=1
VOICE_END_SILENCE=1.0
EOF
chmod 0600 "$CONF"

cat > /usr/local/bin/croni-call-test <<EOF
#!/usr/bin/env bash
set -euo pipefail
export RINGRINGRING_CONF="$CONF"
export PYTHONPATH="$PREFIX/pjsua2/python:$PREFIX/app"
export LD_LIBRARY_PATH="$PREFIX/pjsua2/lib"
export PATH="$PREFIX/venv/bin:\$PATH"
exec "$PREFIX/venv/bin/python" "$PREFIX/app/test_phone.py" "\$@"
EOF
chmod 0755 /usr/local/bin/croni-call-test

say "Installation complete"
printf '%s\n' 'Run: croni-call-test'
printf '%s\n' 'Your iPhone should ring. Answer it and listen for the test line.'

