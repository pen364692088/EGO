import pytest

from app.telegram_bot import TelegramBot


@pytest.mark.asyncio
async def test_runtime_v2_keeps_priority_over_compat_paths(monkeypatch):
    bot = TelegramBot(token="test-token", use_runtime_v2=True, use_new_runtime=True)

    class DummyMessage:
        text = "你好"
        message_id = 1
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

    class DummyBot:
        async def send_chat_action(self, chat_id, action):
            return None

    bot.app = type("A", (), {"bot": DummyBot()})()

    async def fake_v2(*args, **kwargs):
        await DummyUpdate.message.reply_text("v2")

    async def should_not_run(*args, **kwargs):
        raise AssertionError("compatibility path should not run when runtime_v2 is enabled")

    monkeypatch.setattr(bot, "_handle_with_runtime_v2", fake_v2)
    monkeypatch.setattr(bot, "_handle_with_new_runtime", should_not_run)
    monkeypatch.setattr(bot, "_handle_with_legacy_router", should_not_run)

    await bot.handle_message(DummyUpdate(), None)
    assert DummyUpdate.message.last_text == "v2"


def test_legacy_paths_start_unlogged():
    bot = TelegramBot(token="test-token", use_runtime_v2=False, use_new_runtime=True)
    assert bot._legacy_runtime_notice_logged is False
