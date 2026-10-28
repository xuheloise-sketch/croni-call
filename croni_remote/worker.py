"""Run all pjsua2 operations on one dedicated thread.

pjsua2 has thread-affinity constraints on some platforms. HTTP handlers may run
concurrently, so they submit work to this single serialized worker rather than
calling the upstream module from arbitrary request threads.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import Future
import queue
import threading
from typing import Any


class PhoneWorker:
    def __init__(self, startup_timeout: float = 15.0) -> None:
        self._queue: queue.Queue[tuple[str, tuple[Any, ...], Future] | None] = queue.Queue()
        self._ready = threading.Event()
        self._startup_error: BaseException | None = None
        self._thread = threading.Thread(target=self._run, name="croni-phone", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=startup_timeout):
            raise RuntimeError("phone worker startup timed out")
        if self._startup_error is not None:
            raise RuntimeError("phone worker failed to initialize") from self._startup_error

    def _run(self) -> None:
        try:
            import voice_mcp  # lazy: pjsua2 is available only on the VPS
        except BaseException as exc:
            self._startup_error = exc
            self._ready.set()
            return

        methods = {
            "call_start": voice_mcp.call_start,
            "converse": voice_mcp.converse,
            "call_end": voice_mcp.call_end,
            "call_status": voice_mcp.call_status,
        }
        self._ready.set()
        while True:
            item = self._queue.get()
            if item is None:
                return
            name, args, future = item
            if future.set_running_or_notify_cancel():
                try:
                    future.set_result(methods[name](*args))
                except BaseException as exc:
                    future.set_exception(exc)

    async def call(self, name: str, *args: Any) -> str:
        if self._startup_error is not None or not self._thread.is_alive():
            raise RuntimeError("phone worker is unavailable")
        future: Future = Future()
        self._queue.put((name, args, future))
        return await asyncio.wrap_future(future)

    def close(self) -> None:
        if self._thread.is_alive():
            self._queue.put(None)
