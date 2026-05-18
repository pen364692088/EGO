import asyncio

import pytest

from app.core_bus import BusEvent, MessageBus, SessionWorkerPool


@pytest.mark.asyncio
async def test_session_worker_preserves_per_session_order():
    bus = MessageBus()
    pool = SessionWorkerPool(bus=bus)
    seen: list[tuple[str, int]] = []

    async def record(event: BusEvent) -> None:
        await asyncio.sleep(0.01 if event.payload["index"] == 1 else 0)
        seen.append((event.session_key, event.payload["index"]))

    pool.register_handler(record)
    pool.start()

    await asyncio.gather(
        bus.publish(BusEvent(session_key="s1", kind="ingress", payload={"index": 1})),
        bus.publish(BusEvent(session_key="s1", kind="result", payload={"index": 2})),
    )
    await asyncio.sleep(0.05)

    assert seen == [("s1", 1), ("s1", 2)]
