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

import app.telegram_bot as telegram_bot_module
from app.telegram_bot import TelegramBot
from app.interaction.session_context_store import get_session_context_store


@pytest.mark.asyncio
async def test_new_command_resets_runtime_v2_session():
    bot = TelegramBot(token="test-token", use_runtime_v2=True)

    class DummyMessage:
        text = "/new"
        message_id = 21
        reply_to_message = None
        last_text = None
        async def reply_text(self, text, parse_mode=None):
            self.last_text = text

    class DummyChat:
        id = 123
        type = "private"

    class DummyUser:
        id = 456
        username = "moonlight"

    class DummyUpdate:
        message = DummyMessage()
        effective_chat = DummyChat()
        effective_user = DummyUser()

    session_key = "telegram:dm:456"
    state = bot._get_runtime_state(session_key)
    state.task_status = "running"
    state.current_goal = "修改 hello.html"
    get_session_context_store().add_turn(session_key, "user", "hello")

    await bot.handle_command(DummyUpdate(), None)
    new_state = bot._get_runtime_state(session_key)
    assert "Session Reset" in DummyUpdate.message.last_text
    assert new_state.task_status == "idle"
    assert new_state.current_goal is None
    assert get_session_context_store().get_recent_turns(session_key) == []


@pytest.mark.asyncio
async def test_status_command_returns_runtime_style_card():
    bot = TelegramBot(token="test-token", use_runtime_v2=True)

    class DummyMessage:
        text = "/status"
        message_id = 22
        reply_to_message = None
        last_text = None
        async def reply_text(self, text, parse_mode=None):
            self.last_text = text

    class DummyChat:
        id = 123
        type = "private"

    class DummyUser:
        id = 456
        username = "moonlight"

    class DummyUpdate:
        message = DummyMessage()
        effective_chat = DummyChat()
        effective_user = DummyUser()

    session_key = "telegram:dm:456"
    state = bot._get_runtime_state(session_key)
    state.task_status = "running"
    state.task_id = "task_abc123"
    state.current_goal = "连续性验证"
    state.current_step = "检查 test.html"

    await bot.handle_command(DummyUpdate(), None)
    text = DummyUpdate.message.last_text
    assert bot.runtime_v2_loop is None
    assert "EgoCore Runtime" in text
    assert "qianfan/glm-5" in text
    assert "Session ID:" in text
    assert "native\\_loop" in text
    assert "task\\_status" in text and "running" in text
    assert "loaded:" in text


@pytest.mark.asyncio
async def test_new_command_captures_real_command_ingress(monkeypatch):
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    captured = {}

    class FakeCollector:
        def start_sample(self, update):
            captured["started"] = update["message"]["text"]

        def capture_host_response_plan(self, **kwargs):
            captured["plan"] = kwargs

        def capture_outbox_record(self, record):
            captured["outbox"] = record

        def finalize_sample(self):
            captured["finalized"] = True

    class FakeHooks:
        enabled = True

        def process_ingress(self, **kwargs):
            captured["ingress"] = kwargs

    monkeypatch.setattr(telegram_bot_module, "_EVIDENCE_COLLECTOR_AVAILABLE", True)
    monkeypatch.setattr(telegram_bot_module, "get_evidence_collector", lambda: FakeCollector())
    monkeypatch.setattr(bot, "_get_native_openemotion_hooks", lambda: FakeHooks())

    class DummyMessage:
        text = "/new"
        message_id = 21
        reply_to_message = None
        date = None
        async def reply_text(self, text, parse_mode=None):
            self.last_text = text
            return type(
                "SentMessage",
                (),
                {
                    "chat": type("Chat", (), {"id": 123})(),
                    "message_id": 22,
                    "date": None,
                },
            )()

    class DummyChat:
        id = 123
        type = "private"

    class DummyUser:
        id = 456
        username = "moonlight"

    class DummyUpdate:
        update_id = 999
        message = DummyMessage()
        effective_chat = DummyChat()
        effective_user = DummyUser()

        def to_dict(self):
            return {
                "update_id": self.update_id,
                "message": {
                    "message_id": self.message.message_id,
                    "chat": {"id": self.effective_chat.id, "type": self.effective_chat.type},
                    "from": {"id": self.effective_user.id, "username": self.effective_user.username},
                    "text": self.message.text,
                },
            }

    await bot.handle_command(DummyUpdate(), None)

    assert captured["started"] == "/new"
    assert captured["ingress"]["user_input"] == "/new"
    assert captured["ingress"]["session_id"] == "telegram:dm:456"
    assert captured["plan"]["status"] == "command_result"
    assert captured["finalized"] is True


@pytest.mark.asyncio
async def test_proto_command_enables_v2_override():
    bot = TelegramBot(token="test-token", use_runtime_v2=True)

    class DummyMessage:
        text = "/proto v2 on"
        message_id = 23
        reply_to_message = None
        date = datetime.now(timezone.utc)
        last_text = None

        async def reply_text(self, text, parse_mode=None):
            self.last_text = text

    class DummyChat:
        id = 123
        type = "private"

    class DummyUser:
        id = 456
        username = "moonlight"

    class DummyUpdate:
        message = DummyMessage()
        effective_chat = DummyChat()
        effective_user = DummyUser()

    await bot.handle_command(DummyUpdate(), None)

    state = bot._get_runtime_state("telegram:dm:456")
    assert state.proto_self_version_override == "v2"
    assert "override: \\`v2\\`" in DummyUpdate.message.last_text


@pytest.mark.asyncio
async def test_proto_command_clears_override():
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    state = bot._get_runtime_state("telegram:dm:456")
    state.proto_self_version_override = "v2"

    class DummyMessage:
        text = "/proto off"
        message_id = 24
        reply_to_message = None
        date = datetime.now(timezone.utc)
        last_text = None

        async def reply_text(self, text, parse_mode=None):
            self.last_text = text

    class DummyChat:
        id = 123
        type = "private"

    class DummyUser:
        id = 456
        username = "moonlight"

    class DummyUpdate:
        message = DummyMessage()
        effective_chat = DummyChat()
        effective_user = DummyUser()

    await bot.handle_command(DummyUpdate(), None)

    assert state.proto_self_version_override is None
    assert "override: \\`default(v1)\\`" in DummyUpdate.message.last_text
