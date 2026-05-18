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

from app.interaction.session_context_store import get_session_context_store
from app.telegram_bot import TelegramBot


class DummyBot:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_message(self, chat_id, text):
        self.sent.append({"chat_id": chat_id, "text": text})
        return SimpleNamespace(
            chat=SimpleNamespace(id=chat_id),
            message_id=1000 + len(self.sent),
            date=datetime.now(timezone.utc),
        )


@pytest.mark.asyncio
async def test_drain_pending_proactive_outbox_to_telegram_sends_and_updates_state() -> None:
    session_id = "telegram:dm:8420019401"
    context_store = get_session_context_store()
    context_store.clear_session(session_id)

    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    dummy_bot = DummyBot()
    bot.app = SimpleNamespace(bot=dummy_bot)
    state = bot._get_runtime_state(session_id)
    state.push_proactive_outbox_event(
        {
            "schema_version": "mvp12.proactive_outbox_event.v1",
            "initiative_candidate_id": "candidate-1",
            "outbox_lane": "host_proactive_outbox",
            "outbox_status": "queued",
            "reply_text": "我刚又想到一个相关问题。",
            "text_length": 13,
            "reply_authority": "model_chat",
            "reply_origin": "proactive_followup",
            "authority_source": "runtime_v2.initiative_arbiter",
            "initiative_mode": "controlled_shadow_delivery_draft",
        }
    )
    bot._remember_session_transport_binding(session_id, 8420019401)

    result = await bot.drain_pending_proactive_outbox_to_telegram(session_id)

    assert result["status"] == "sent"
    assert len(result["sent_records"]) == 1
    assert result["sent_records"][0]["transport_source"] == "telegram"
    assert result["sent_records"][0]["last_message_id"] == 1001
    assert dummy_bot.sent == [{"chat_id": 8420019401, "text": "我刚又想到一个相关问题。"}]
    assert not state.has_pending_proactive_outbox_events()
    assert state.get_chat_state().recent_assistant_replies[-1] == "我刚又想到一个相关问题。"

    turns = context_store.get_recent_turns(session_id, limit=5)
    assert turns[-1]["role"] == "assistant"
    assert any("我刚又想到一个相关问题" in str(value) for value in turns[-1].values())


@pytest.mark.asyncio
async def test_drain_pending_proactive_outbox_to_telegram_holds_without_chat_binding() -> None:
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    bot.app = SimpleNamespace(bot=DummyBot())
    session_id = "session:test"
    state = bot._get_runtime_state(session_id)
    state.push_proactive_outbox_event(
        {
            "schema_version": "mvp12.proactive_outbox_event.v1",
            "initiative_candidate_id": "candidate-1",
            "outbox_lane": "host_proactive_outbox",
            "outbox_status": "queued",
            "reply_text": "我刚又想到一个相关问题。",
            "text_length": 13,
            "reply_authority": "model_chat",
            "reply_origin": "proactive_followup",
            "authority_source": "runtime_v2.initiative_arbiter",
        }
    )

    result = await bot.drain_pending_proactive_outbox_to_telegram(session_id)

    assert result["status"] == "held"
    assert result["reason"] == "missing_telegram_chat_id"
    assert state.has_pending_proactive_outbox_events()
