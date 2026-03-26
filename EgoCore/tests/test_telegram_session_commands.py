import pytest

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
    state = bot._get_runtime_v2_loop().get_state(session_key)
    state.task_status = "running"
    state.current_goal = "修改 hello.html"
    get_session_context_store().add_turn(session_key, "user", "hello")

    await bot.handle_command(DummyUpdate(), None)
    new_state = bot._get_runtime_v2_loop().get_state(session_key)
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
    state = bot._get_runtime_v2_loop().get_state(session_key)
    state.task_status = "running"
    state.task_id = "task_abc123"
    state.current_goal = "连续性验证"
    state.current_step = "检查 test.html"

    await bot.handle_command(DummyUpdate(), None)
    text = DummyUpdate.message.last_text
    assert "EgoCore Runtime" in text
    assert "qianfan/glm-5" in text
    assert "Session ID:" in text
    assert "native\\_loop" in text
    assert "task\\_status" in text and "running" in text
    assert "loaded:" in text
