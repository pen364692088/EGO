from pathlib import Path

from app.core_bus.events import BusEvent
from app.session_store import SessionLogManager


def test_session_log_appends_jsonl(tmp_path: Path):
    manager = SessionLogManager(tmp_path)
    event1 = BusEvent(session_key="telegram:1", kind="ingress", payload={"text": "hello"})
    event2 = BusEvent(session_key="telegram:1", kind="delivery", payload={"text": "world"})

    path = manager.append(event1)
    manager.append(event2)

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    tail = manager.get_log("telegram:1").tail(2)
    assert tail[0]["kind"] == "ingress"
    assert tail[1]["payload"]["text"] == "world"
