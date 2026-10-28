"""Configuration parsing for the remote Croni Call gateway.

Secrets are read from environment variables on the VPS.  This module never logs
their values and deliberately keeps the public MCP tools free of phone-number
or SIP-address parameters.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ConfigError(ValueError):
    """Raised for an unsafe or incomplete gateway configuration."""


def _positive_int(env: dict[str, str], name: str, default: int) -> int:
    raw = env.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ConfigError(f"{name} must be greater than zero")
    return value


def _clock_time(raw: str, name: str) -> tuple[int, int] | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        hour_s, minute_s = raw.split(":", 1)
        hour, minute = int(hour_s), int(minute_s)
    except (ValueError, TypeError) as exc:
        raise ConfigError(f"{name} must use HH:MM") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ConfigError(f"{name} must use a valid 24-hour time")
    return hour, minute


@dataclass(frozen=True)
class RemoteConfig:
    resource_url: str
    auth_issuer_url: str
    bearer_token: str
    sip_callee: str
    host: str
    port: int
    timezone: ZoneInfo
    quiet_start: tuple[int, int] | None
    quiet_end: tuple[int, int] | None
    daily_call_limit: int
    minimum_retry_seconds: int
    maximum_call_seconds: int
    state_file: Path
    allowed_hosts: tuple[str, ...]
    allowed_origins: tuple[str, ...]

    @classmethod
    def from_env(cls, source: dict[str, str] | None = None) -> "RemoteConfig":
        env = dict(os.environ if source is None else source)

        resource_url = env.get("CRONI_MCP_RESOURCE_URL", "").strip()
        parsed = urlparse(resource_url)
        allow_http = env.get("CRONI_ALLOW_INSECURE_HTTP", "") == "1"
        if parsed.scheme not in ({"http", "https"} if allow_http else {"https"}) or not parsed.netloc:
            suffix = " (HTTP is allowed only with CRONI_ALLOW_INSECURE_HTTP=1)"
            raise ConfigError("CRONI_MCP_RESOURCE_URL must be an absolute HTTPS URL" + suffix)
        if not parsed.path.endswith("/mcp"):
            raise ConfigError("CRONI_MCP_RESOURCE_URL must end with /mcp")

        issuer = env.get("CRONI_AUTH_ISSUER_URL", "").strip() or resource_url.rsplit("/mcp", 1)[0]
        issuer_parsed = urlparse(issuer)
        if issuer_parsed.scheme not in ({"http", "https"} if allow_http else {"https"}) or not issuer_parsed.netloc:
            raise ConfigError("CRONI_AUTH_ISSUER_URL must be an absolute HTTPS URL")

        token = env.get("CRONI_MCP_BEARER_TOKEN", "")
        if len(token) < 32:
            raise ConfigError("CRONI_MCP_BEARER_TOKEN must contain at least 32 characters")

        callee = env.get("VOICE_SIP_CALLEE", "").strip()
        if not callee.startswith("sip:") or "@" not in callee or any(ch.isspace() for ch in callee):
            raise ConfigError("VOICE_SIP_CALLEE must be one fixed SIP address")

        tz_name = env.get("CRONI_TIMEZONE", "Asia/Shanghai").strip()
        try:
            timezone = ZoneInfo(tz_name)
        except ZoneInfoNotFoundError as exc:
            raise ConfigError(f"unknown CRONI_TIMEZONE: {tz_name}") from exc

        quiet_start = _clock_time(env.get("CRONI_QUIET_START", "23:00"), "CRONI_QUIET_START")
        quiet_end = _clock_time(env.get("CRONI_QUIET_END", "08:00"), "CRONI_QUIET_END")
        if (quiet_start is None) != (quiet_end is None):
            raise ConfigError("quiet start and end must both be set or both be blank")

        state_file = Path(env.get(
            "CRONI_POLICY_STATE_FILE",
            "~/.local/state/croni-call/policy.json",
        )).expanduser()

        hostname = parsed.hostname or "localhost"
        allowed_hosts = tuple(filter(None, (
            item.strip() for item in env.get("CRONI_ALLOWED_HOSTS", hostname).split(",")
        )))
        allowed_origins = tuple(filter(None, (
            item.strip() for item in env.get("CRONI_ALLOWED_ORIGINS", f"{parsed.scheme}://{parsed.netloc}").split(",")
        )))

        return cls(
            resource_url=resource_url,
            auth_issuer_url=issuer,
            bearer_token=token,
            sip_callee=callee,
            host=env.get("CRONI_MCP_HOST", "127.0.0.1").strip() or "127.0.0.1",
            port=_positive_int(env, "CRONI_MCP_PORT", 8765),
            timezone=timezone,
            quiet_start=quiet_start,
            quiet_end=quiet_end,
            daily_call_limit=_positive_int(env, "CRONI_DAILY_CALL_LIMIT", 3),
            minimum_retry_seconds=_positive_int(env, "CRONI_MINIMUM_RETRY_SECONDS", 300),
            maximum_call_seconds=_positive_int(env, "CRONI_MAXIMUM_CALL_SECONDS", 900),
            state_file=state_file,
            allowed_hosts=allowed_hosts,
            allowed_origins=allowed_origins,
        )
