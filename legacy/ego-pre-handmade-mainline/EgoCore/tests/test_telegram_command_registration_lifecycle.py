import pytest

from app.telegram_bot import TelegramBot


@pytest.mark.asyncio
async def test_telegram_commands_registered_during_lifecycle():
    bot = TelegramBot(token="test-token")

    class DummyBotApi:
        def __init__(self):
            self.commands = None
        async def set_my_commands(self, commands):
            self.commands = commands

    class DummyUpdater:
        def __init__(self):
            self.running = False
        async def start_polling(self, **kwargs):
            self.running = True
        async def stop(self):
            self.running = False

    class DummyApp:
        def __init__(self):
            self.bot = DummyBotApi()
            self.updater = DummyUpdater()
            self.running = False
        async def initialize(self):
            return None
        async def start(self):
            self.running = True
        async def stop(self):
            self.running = False
        async def shutdown(self):
            return None

    bot.app = DummyApp()

    async def stop_soon(_fingerprint):
        original_sleep = __import__('asyncio').sleep
        async def fake_sleep(_):
            raise KeyboardInterrupt()
        import app.telegram_bot as tg
        tg.asyncio.sleep = fake_sleep
        try:
            await TelegramBot._run_polling_lifecycle(bot, "fp")
        except KeyboardInterrupt:
            pass
        finally:
            tg.asyncio.sleep = original_sleep

    await stop_soon("fp")
    assert bot.app.bot.commands is not None
    assert any(cmd.command == "context" for cmd in bot.app.bot.commands)
    assert any(cmd.command == "prompt" for cmd in bot.app.bot.commands)
    assert any(cmd.command == "reset" for cmd in bot.app.bot.commands)
