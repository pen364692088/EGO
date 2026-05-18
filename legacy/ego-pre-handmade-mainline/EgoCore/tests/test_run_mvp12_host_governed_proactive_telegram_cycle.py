from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

if "requests" not in sys.modules:
    sys.modules["requests"] = SimpleNamespace(
        get=lambda *args, **kwargs: None,
        post=lambda *args, **kwargs: None,
        exceptions=SimpleNamespace(
            Timeout=Exception,
            ConnectionError=Exception,
        ),
    )

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.telegram_bot import TelegramBot
from EgoCore.tools import run_mvp12_host_governed_proactive_telegram_cycle as runner_module
from EgoCore.tools.run_mvp12_host_governed_proactive_telegram_cycle import (
    run_host_governed_proactive_telegram_cycle_session,
)


class DummyBotApi:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_message(self, chat_id, text):
        self.sent.append({"chat_id": chat_id, "text": text})
        return SimpleNamespace(
            chat=SimpleNamespace(id=chat_id),
            message_id=3000 + len(self.sent),
            date=datetime.now(timezone.utc),
        )


class DummyProtoRuntime:
    def process_developmental_tick(self, **kwargs):
        return {
            "developmental_summary": {
                "background_thought_candidates": [
                    {
                        "candidate_id": "candidate-1",
                        "delivery_ready": True,
                        "draft_text": "我又回到你刚才那个点“OS 的操作员感”。",
                        "initiative_score": 0.84,
                        "source_cycle": "cycle-1",
                        "source_candidate_hash": "hash-1",
                    }
                ]
            },
            "developmental_gate": {"status": "allow"},
        }


@pytest.mark.asyncio
async def test_run_mvp12_host_governed_proactive_telegram_cycle_session_writes_artifact(tmp_path: Path) -> None:
    telegram_bot = TelegramBot(token="dummy", use_runtime_v2=True)
    telegram_bot.app = SimpleNamespace(bot=DummyBotApi())
    output_json = tmp_path / "host_governed_proactive_cycle.json"

    async def fake_runtime_session(**kwargs):
        state = telegram_bot._get_runtime_state("telegram:dm:8420019401")
        chat_state = state.get_chat_state()
        chat_state.recent_user_turns = [
            "我在想，意识的门槛其实可能比人类自以为的低很多。你怎么看？",
            "有主观能动性。",
            "我觉得是有了OS的操作员的感觉。",
        ]
        chat_state.recent_assistant_replies = [
            "这个角度有意思。",
            "那单细胞生物趋利避害算不算？",
            "这个自觉挺关键的。",
        ]
        chat_state.last_user_turn_at = 100.0
        chat_state.last_assistant_reply_at = 100.0
        chat_state.last_activity_at = 100.0
        runtime = SimpleNamespace(proto_self_runtime=DummyProtoRuntime(), _states={"telegram:dm:8420019401": state})
        return runtime, state, [{"turn_id": "turn-1"}]

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(runner_module, "run_runtime_mainline_session", fake_runtime_session)

    try:
        payload = await run_host_governed_proactive_telegram_cycle_session(
            messages=[
                "我在想，意识的门槛其实可能比人类自以为的低很多。你怎么看？",
                "有主观能动性。",
                "我觉得是有了OS的操作员的感觉。",
            ],
            session_id="telegram:dm:8420019401",
            chat_id=8420019401,
            simulated_idle_seconds=900.0,
            output_json=output_json,
            telegram_bot=telegram_bot,
        )
    finally:
        monkeypatch.undo()

    assert payload["cycle_result"]["status"] == "sent"
    assert payload["cycle_result"]["transport_result"]["status"] == "sent"
    assert output_json.exists()
    written = json.loads(output_json.read_text(encoding="utf-8"))
    assert written["cycle_result"]["transport_result"]["status"] == "sent"
    assert written["pending_proactive_outbox_events"] == []
