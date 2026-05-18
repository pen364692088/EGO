from __future__ import annotations

import sys
from datetime import datetime, timezone
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

from app.telegram_bot import TelegramBot


class DummyBotApi:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_message(self, chat_id, text):
        self.sent.append({"chat_id": chat_id, "text": text})
        return SimpleNamespace(
            chat=SimpleNamespace(id=chat_id),
            message_id=2000 + len(self.sent),
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
                        "draft_text": "我又回到你刚才那个点“OS 的操作员感”。这不像一个比喻结束了，更像它刚开始暴露谁在做选择。",
                        "initiative_score": 0.84,
                        "source_cycle": "cycle-1",
                        "source_candidate_hash": "hash-1",
                    }
                ]
            },
            "developmental_gate": {"status": "allow"},
        }


async def _build_host_governed_fixture(session_id: str):
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    bot.app = SimpleNamespace(bot=DummyBotApi())
    state = bot._get_runtime_state(session_id)
    bot.runtime_v2_loop = SimpleNamespace(proto_self_runtime=DummyProtoRuntime(), _states={session_id: state})
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
    bot._remember_session_transport_binding(session_id, 8420019401)
    return bot, state


@pytest.mark.asyncio
async def test_run_host_governed_proactive_telegram_cycle_sends_after_idle() -> None:
    session_id = "telegram:dm:8420019401"
    bot, state = await _build_host_governed_fixture(session_id)
    bot._mvp12_proactive_telegram_autodrain_enabled = True
    bot._mvp12_proactive_allowed_chat_ids = {8420019401}
    last_activity_at = state.get_chat_state().last_activity_at
    assert last_activity_at == 100.0

    result = await bot.run_host_governed_proactive_telegram_cycle(
        session_id,
        now_ts=last_activity_at + 900.0,
        live_mode=True,
        max_events=1,
        enforce_enable_policy=True,
    )

    assert result["status"] == "sent"
    assert result["enable_policy"]["status"] == "allow"
    assert result["transport_gate"]["status"] == "allow"
    assert result["transport_result"]["status"] == "sent"
    assert result["transport_result"]["sent_records"][0]["transport_source"] == "telegram"
    assert state.peek_proactive_outbox_events() == []


@pytest.mark.asyncio
async def test_run_host_governed_proactive_telegram_cycle_holds_when_transport_gate_blocks() -> None:
    session_id = "telegram:dm:8420019401"
    bot, state = await _build_host_governed_fixture(session_id)
    bot._mvp12_proactive_telegram_autodrain_enabled = True
    bot._mvp12_proactive_allowed_chat_ids = {8420019401}
    last_activity_at = state.get_chat_state().last_activity_at
    assert last_activity_at == 100.0

    result = await bot.run_host_governed_proactive_telegram_cycle(
        session_id,
        now_ts=last_activity_at + 700.0,
        live_mode=True,
        max_events=1,
        enforce_enable_policy=True,
    )

    assert result["status"] == "held"
    assert result["reason"] == "transport_gate:idle_window_too_short"
    assert result["enable_policy"]["status"] == "allow"
    assert result["transport_gate"]["reason"] == "idle_window_too_short"
    assert result["transport_result"] is None
    assert state.has_pending_proactive_outbox_events()


@pytest.mark.asyncio
async def test_run_host_governed_proactive_telegram_cycle_holds_when_enable_policy_blocks() -> None:
    session_id = "telegram:dm:8420019401"
    bot, state = await _build_host_governed_fixture(session_id)
    bot._mvp12_proactive_telegram_autodrain_enabled = True
    bot._mvp12_proactive_allowed_chat_ids = {999}
    last_activity_at = state.get_chat_state().last_activity_at
    assert last_activity_at == 100.0

    result = await bot.run_host_governed_proactive_telegram_cycle(
        session_id,
        now_ts=last_activity_at + 900.0,
        live_mode=True,
        max_events=1,
        enforce_enable_policy=True,
    )

    assert result["status"] == "held"
    assert result["reason"] == "enable_policy:chat_not_allowlisted"
    assert result["enable_policy"]["reason"] == "chat_not_allowlisted"
    assert result["transport_result"] is None
    assert not state.has_pending_proactive_outbox_events()
