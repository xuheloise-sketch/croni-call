"""Run all pjsua2 operations on one dedicated thread.

pjsua2 has thread-affinity constraints on some platforms.  HTTP handlers may run
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
    def __init__(self) -> None:
        self._queue: queue.Queue[tuple[str, tuple[Any, ...], Future] | None] = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="croni-phone", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        import voice_mcp  # lazy: pjsua2 is available only on the VPS

        methods = {
            "call_start": voice_mcp.call_start,
            "converse": voice_mcp.converse,
            "call_end": voice_mcp.call_end,
            "call_status": voice_mcp.call_status,
        }
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
        future: Future = Future()
        self._queue.put((name, args, future))
        return await asyncio.wrap_future(future)

    def close(self) -> None:
        self._queue.put(None)
