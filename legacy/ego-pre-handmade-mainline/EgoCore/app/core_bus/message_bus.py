from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, List, Optional

from .events import BusEvent

logger = logging.getLogger(__name__)

BusSubscriber = Callable[[BusEvent], Awaitable[None]]


class MessageBus:
    def __init__(self) -> None:
        self._subscribers: List[BusSubscriber] = []

    def subscribe(self, subscriber: BusSubscriber) -> None:
        self._subscribers.append(subscriber)

    async def publish(self, event: BusEvent) -> None:
        if not self._subscribers:
            return
        await asyncio.gather(
            *(self._deliver(subscriber, event) for subscriber in list(self._subscribers)),
            return_exceptions=True,
        )

    async def _deliver(self, subscriber: BusSubscriber, event: BusEvent) -> None:
        try:
            await subscriber(event)
        except Exception:
            logger.exception("message_bus subscriber failed event=%s kind=%s", event.event_id, event.kind)


_message_bus: Optional[MessageBus] = None


def get_message_bus() -> MessageBus:
    global _message_bus
    if _message_bus is None:
        _message_bus = MessageBus()
    return _message_bus
