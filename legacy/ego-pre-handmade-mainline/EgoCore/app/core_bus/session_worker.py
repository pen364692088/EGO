from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Awaitable, Callable, Dict, Optional

from .events import BusEvent
from .message_bus import MessageBus, get_message_bus

logger = logging.getLogger(__name__)

SessionHandler = Callable[[BusEvent], Awaitable[None]]


class SessionWorkerPool:
    def __init__(self, bus: Optional[MessageBus] = None) -> None:
        self.bus = bus or get_message_bus()
        self._queues: Dict[str, asyncio.Queue[BusEvent]] = {}
        self._tasks: Dict[str, asyncio.Task[None]] = {}
        self._handlers: list[SessionHandler] = []
        self._started = False

    def register_handler(self, handler: SessionHandler) -> None:
        self._handlers.append(handler)

    def start(self) -> None:
        if self._started:
            return
        self.bus.subscribe(self.enqueue)
        self._started = True

    async def enqueue(self, event: BusEvent) -> None:
        queue = self._queues.setdefault(event.session_key, asyncio.Queue())
        await queue.put(event)
        task = self._tasks.get(event.session_key)
        if task is None or task.done():
            self._tasks[event.session_key] = asyncio.create_task(self._run_session(event.session_key))

    async def _run_session(self, session_key: str) -> None:
        queue = self._queues[session_key]
        while not queue.empty():
            event = await queue.get()
            for handler in list(self._handlers):
                try:
                    await handler(event)
                except Exception:
                    logger.exception("session_worker handler failed session=%s kind=%s", session_key, event.kind)
            queue.task_done()


_session_worker_pool: Optional[SessionWorkerPool] = None


def get_session_worker_pool() -> SessionWorkerPool:
    global _session_worker_pool
    if _session_worker_pool is None:
        _session_worker_pool = SessionWorkerPool()
    return _session_worker_pool
