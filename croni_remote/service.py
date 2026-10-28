"""Safe orchestration between MCP tools, policy and the phone worker."""

from __future__ import annotations

import asyncio
from typing import Any

from .policy import CallPolicy
from .worker import PhoneWorker

MAX_SPOKEN_CHARACTERS = 500


class GatewayError(RuntimeError):
    """A deliberately non-sensitive error safe to return through MCP."""


def _spoken_line(value: str, *, required: bool) -> str:
    if not isinstance(value, str):
        raise GatewayError("spoken text must be a string")
    text = value.strip()
    if required and not text:
        raise GatewayError("spoken text cannot be empty")
    if len(text) > MAX_SPOKEN_CHARACTERS:
        raise GatewayError(f"spoken text must be at most {MAX_SPOKEN_CHARACTERS} characters")
    if any(ord(char) < 32 and char not in "\n\t" for char in text):
        raise GatewayError("spoken text contains unsupported control characters")
    return text


def _call_finished(result: str) -> bool:
    markers = ("[CALL ENDED]", "[NO ANSWER]", "[NO ACTIVE CALL]", "[LINE BUSY]")
    return any(marker in result for marker in markers)


class CallGateway:
    """Serialize public operations and enforce policy around the upstream engine."""

    def __init__(self, policy: CallPolicy, worker: PhoneWorker):
        self.policy = policy
        self.worker = worker
        self._lock = asyncio.Lock()
        self._stop = asyncio.Event()

    async def _phone(self, method: str, *args: Any) -> str:
        try:
            return await self.worker.call(method, *args)
        except Exception:
            raise GatewayError("the phone engine could not complete the request") from None

    async def call_start(self, opening_line: str) -> dict[str, Any]:
        line = _spoken_line(opening_line, required=True)
        async with self._lock:
            if self.policy.status()["active"]:
                return {"ok": False, "status": "busy", "message": "a call is already active"}

            decision = self.policy.check_start()
            if not decision.allowed:
                return {"ok": False, "status": "blocked", "message": decision.reason}

            self.policy.record_attempt()
            try:
                result = await self._phone("call_start", line)
            except GatewayError:
                self.policy.record_end()
                raise
            if _call_finished(result):
                self.policy.record_end()
            return {"ok": True, "status": "completed" if _call_finished(result) else "active", "message": result}

    async def converse(self, text: str) -> dict[str, Any]:
        line = _spoken_line(text, required=True)
        async with self._lock:
            if not self.policy.status()["active"]:
                return {"ok": False, "status": "inactive", "message": "there is no active call"}
            if self.policy.maximum_duration_reached():
                await self._phone("call_end", "")
                self.policy.record_end()
                return {"ok": False, "status": "ended", "message": "maximum call duration reached"}

            result = await self._phone("converse", line)
            if _call_finished(result):
                self.policy.record_end()
            return {"ok": True, "status": "completed" if _call_finished(result) else "active", "message": result}

    async def call_end(self, closing_line: str = "") -> dict[str, Any]:
        line = _spoken_line(closing_line, required=False)
        async with self._lock:
            try:
                result = await self._phone("call_end", line)
            finally:
                self.policy.record_end()
            return {"ok": True, "status": "ended", "message": result}

    async def call_status(self) -> dict[str, Any]:
        async with self._lock:
            state = self.policy.status()
            engine = await self._phone("call_status")
            if state["active"] and ("no call" in engine.lower() or "connected=false" in engine.lower()):
                self.policy.record_end()
                state = self.policy.status()
            return {"ok": True, "policy": state, "engine": engine}

    async def watchdog(self, poll_seconds: float = 5.0) -> None:
        """End an abandoned call even when no later MCP request arrives."""
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=poll_seconds)
            except TimeoutError:
                pass
            if self._stop.is_set():
                break
            if self.policy.status()["active"] and self.policy.maximum_duration_reached():
                try:
                    await self.call_end("通话时间到了，我们下次再聊。")
                except GatewayError:
                    self.policy.record_end()

    def stop(self) -> None:
        self._stop.set()
