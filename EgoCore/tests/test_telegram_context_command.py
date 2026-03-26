import pytest

from app.telegram_bot import TelegramBot


@pytest.mark.asyncio
async def test_context_list_command_shows_runtime_state():
    bot = TelegramBot(token="test-token", use_runtime_v2=True)

    class DummyMessage:
        text = "/context list"
        message_id = 11
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

    state = bot._get_runtime_state("telegram:dm:456")
    state.task_status = "running"
    state.current_goal = "修改 hello.html 配色"
    state.current_step = "tool:file"
    state.record("user", {"text": "hello"})

    await bot.handle_command(DummyUpdate(), None)
    assert bot.runtime_v2_loop is None
    assert "Loaded Context" in DummyUpdate.message.last_text
    assert "Runtime State" in DummyUpdate.message.last_text
    assert "task\\_status" in DummyUpdate.message.last_text
    assert "running" in DummyUpdate.message.last_text
    assert "loaded\\_prompt\\_files:" in DummyUpdate.message.last_text


def test_context_unknown_subcommand_returns_usage():
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    class DummyUpdate:
        effective_chat = type("C", (), {"id": 123, "type": "private"})()
        effective_user = type("U", (), {"id": 456, "username": "moonlight"})()
    result = bot._handle_context_command(DummyUpdate(), "show", 123, 456, "moonlight")
    assert result.success is False
    assert "用法: /context list" in result.message
