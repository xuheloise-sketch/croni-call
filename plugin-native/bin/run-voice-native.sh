#!/usr/bin/env bash
# ringringring voice MCP launcher (native route, no Docker).
#
# Claude Code spawns this over stdio. Settings come from two places:
#   1. the plugin's userConfig (mapped to VOICE_* by .mcp.json), which wins when set;
#   2. ~/.config/ringringring/voice.env (KEY=VALUE lines), which fills whatever is blank.
# The file is parsed, never sourced, so nothing in it gets executed.
# Everything else (pjsua2, venv, app code) lives under $RINGRINGRING_HOME, put there
# by bin/install.sh.
set -euo pipefail

PREFIX="${RINGRINGRING_HOME:-$HOME/.local/share/ringringring}"
CONF="${RINGRINGRING_CONF:-$HOME/.config/ringringring/voice.env}"

die() { echo "[ringringring] $*" >&2; exit 1; }

# A blank value or an un-substituted ${user_config.*} placeholder counts as unset.
is_unset() { case "${1:-}" in "" | '${'*) return 0 ;; esac; return 1; }

for k in $(compgen -e | grep '^VOICE_' || true); do
  is_unset "${!k}" && unset "$k"
done

if [ -f "$CONF" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line#"${line%%[![:space:]]*}"}"
    case "$line" in "" | "#"*) continue ;; esac
    line="${line#export }"
    k="${line%%=*}"; v="${line#*=}"
    [[ "$k" =~ ^[A-Z_][A-Z0-9_]*$ ]] || continue
    [ "$k" = "$line" ] && continue
    v="${v%"${v##*[![:space:]]}"}"
    case "$v" in \"*\") v="${v:1:${#v}-2}" ;; \'*\') v="${v:1:${#v}-2}" ;; esac
    if [ -z "${!k:-}" ]; then export "$k=$v"; fi
  done < "$CONF"
fi

for k in VOICE_SIP_ID VOICE_SIP_USER VOICE_SIP_PASS; do
  [ -n "${!k:-}" ] || die "Missing $k: set it in the plugin config or in $CONF."
done

APP="$PREFIX/app"
PY="$PREFIX/venv/bin/python"
PJ="$PREFIX/pjsua2"

# First start (or plugin updated): install everything under $PREFIX by itself.
# A manual install.sh install (no .plugin-version marker) is left alone.
# All output goes to stderr: stdout is the MCP channel. Never runs apt or needs root;
# missing system packages are reported as one apt-get line by install.sh.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="https://github.com/yanyan1115/ringringring"
PJSUA2_URL="${PJSUA2_URL:-$REPO/releases/download/v0.1.0/pjsua2-2.17-linux-x86_64-cp311.tar.gz}"
VER="$(sed -n 's/^ *"version": *"\([^"]*\)".*/\1/p' "$ROOT/.claude-plugin/plugin.json" | head -1)"
installed=0
[ -x "$PY" ] && [ -f "$APP/voice_mcp.py" ] && [ -d "$PJ/python" ] && installed=1
if [ "$installed" = 0 ] || { [ -f "$PREFIX/.plugin-version" ] && [ "$(cat "$PREFIX/.plugin-version")" != "$VER" ]; }; then
  echo "[ringringring] installing v$VER to $PREFIX (first start, may take a minute)" >&2
  if [ -f "$ROOT/../voice_mcp.py" ]; then
    SRC="$(cd "$ROOT/.." && pwd)"
  else
    TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
    curl -fsSL "$REPO/archive/refs/tags/v$VER.tar.gz" | tar -xz -C "$TMP" \
      || die "could not download $REPO v$VER"
    SRC="$(find "$TMP" -mindepth 1 -maxdepth 1 -type d | head -1)"
  fi
  bash "$ROOT/bin/install.sh" --no-apt --pjsua2 "$PJSUA2_URL" --src "$SRC" >&2 \
    || die "install failed (see above). After fixing it, restart Claude Code or reconnect in /mcp."
  echo "$VER" > "$PREFIX/.plugin-version"
  [ -n "${TMP:-}" ] && rm -rf "$TMP"   # exec below skips the EXIT trap
fi

# default voice: Edge TTS in-process (engine "edge"); an explicit VOICE_TTS or
# VOICE_TTS_CMD (e.g. "$APP/tools/edge_tts_wav.sh {text} {out}") still wins
if [ -z "${VOICE_TTS_CMD:-}" ] && [ -z "${VOICE_TTS:-}" ]; then
  export VOICE_TTS=edge
fi

export PYTHONPATH="$PJ/python:$APP${PYTHONPATH:+:$PYTHONPATH}"
export LD_LIBRARY_PATH="$PJ/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PATH="$PREFIX/venv/bin:$HOME/.local/bin:$PATH"

# per-turn diagnostics (numbers only, redacted); VOICE_DIAG_FILE="" in voice.env turns it off
if [ -z "${VOICE_DIAG_FILE+x}" ]; then
  export VOICE_DIAG_FILE="${XDG_STATE_HOME:-$HOME/.local/state}/ringringring/voice.log"
fi
[ -n "$VOICE_DIAG_FILE" ] && mkdir -p -m 700 "$(dirname "$VOICE_DIAG_FILE")"

exec "$PY" "$APP/voice_mcp.py"
