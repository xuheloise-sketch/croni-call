"""Persistent call-safety policy: quiet hours, rate limits and call duration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Callable

from .config import RemoteConfig


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str = ""


class CallPolicy:
    def __init__(self, config: RemoteConfig, now: Callable[[], datetime] | None = None):
        self.config = config
        self._now = now or (lambda: datetime.now(config.timezone))
        self._lock = threading.RLock()

    def _read(self) -> dict:
        try:
            data = json.loads(self.config.state_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _write(self, data: dict) -> None:
        path = self.config.state_file
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix="policy-", dir=path.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, separators=(",", ":"), sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
            os.chmod(path, 0o600)
        finally:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass

    def _in_quiet_hours(self, now: datetime) -> bool:
        start, end = self.config.quiet_start, self.config.quiet_end
        if start is None or end is None or start == end:
            return False
        current = (now.hour, now.minute)
        if start < end:
            return start <= current < end
        return current >= start or current < end

    def check_start(self) -> PolicyDecision:
        with self._lock:
            now = self._now().astimezone(self.config.timezone)
            if self._in_quiet_hours(now):
                return PolicyDecision(False, "quiet hours are active")

            state = self._read()
            today = now.date().isoformat()
            count = int(state.get("count", 0)) if state.get("date") == today else 0
            if count >= self.config.daily_call_limit:
                return PolicyDecision(False, "daily call limit reached")

            last = state.get("last_attempt")
            if last:
                try:
                    elapsed = (now - datetime.fromisoformat(last).astimezone(self.config.timezone)).total_seconds()
                except ValueError:
                    elapsed = self.config.minimum_retry_seconds
                if elapsed < self.config.minimum_retry_seconds:
                    wait = int(self.config.minimum_retry_seconds - elapsed)
                    return PolicyDecision(False, f"retry interval active; wait {wait} seconds")
            return PolicyDecision(True)

    def record_attempt(self) -> None:
        with self._lock:
            now = self._now().astimezone(self.config.timezone)
            state = self._read()
            today = now.date().isoformat()
            count = int(state.get("count", 0)) if state.get("date") == today else 0
            state.update({
                "date": today,
                "count": count + 1,
                "last_attempt": now.isoformat(),
                "call_started": now.isoformat(),
                "active": True,
            })
            self._write(state)

    def record_end(self) -> None:
        with self._lock:
            state = self._read()
            state["active"] = False
            state.pop("call_started", None)
            self._write(state)

    def maximum_duration_reached(self) -> bool:
        with self._lock:
            state = self._read()
            started = state.get("call_started")
            if not state.get("active") or not started:
                return False
            try:
                start = datetime.fromisoformat(started)
            except ValueError:
                return True
            now = self._now().astimezone(self.config.timezone)
            return (now - start.astimezone(self.config.timezone)).total_seconds() >= self.config.maximum_call_seconds

    def status(self) -> dict[str, object]:
        """Return non-sensitive operational state."""
        with self._lock:
            state = self._read()
            today = self._now().astimezone(self.config.timezone).date().isoformat()
            count = int(state.get("count", 0)) if state.get("date") == today else 0
            return {
                "active": bool(state.get("active", False)),
                "calls_today": count,
                "daily_limit": self.config.daily_call_limit,
                "quiet_hours": self.config.quiet_start is not None,
            }
