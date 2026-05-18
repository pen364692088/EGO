from app.telegram_bot import TelegramBot


class DummyTelegramBotApi:
    def __init__(self):
        self.commands = None

    async def set_my_commands(self, commands):
        self.commands = commands


class DummyApp:
    def __init__(self):
        self.calls = 0
        self.running = False
        self.updater = type('U', (), {'running': False})()

    def run_polling(self, **kwargs):
        self.calls += 1


def test_setup_is_idempotent(monkeypatch):
    bot = TelegramBot(token="test-token")

    built = []

    class DummyBuilder:
        def token(self, token):
            return self

        def build(self):
            app = DummyApp()
            app.add_handler = lambda *a, **k: None
            app.bot = DummyTelegramBotApi()
            built.append(app)
            return app

    class DummyApplication:
        @staticmethod
        def builder():
            return DummyBuilder()

    class DummyFilter:
        def __and__(self, other):
            return self

        def __invert__(self):
            return self

    monkeypatch.setattr("app.telegram_bot.Application", DummyApplication)
    monkeypatch.setattr("app.telegram_bot.CommandHandler", lambda *a, **k: object())
    monkeypatch.setattr("app.telegram_bot.MessageHandler", lambda *a, **k: object())
    monkeypatch.setattr("app.telegram_bot.filters", type("F", (), {"TEXT": DummyFilter(), "COMMAND": DummyFilter()})())

    bot.setup()
    first_app = bot.app
    bot.setup()

    assert bot.app is first_app
    assert len(built) == 1
    # slash commands are registered during async lifecycle, not setup()
    assert built[0].bot.commands is None


def test_run_refuses_second_start_on_same_instance(monkeypatch):
    bot = TelegramBot(token="test-token")
    bot.app = DummyApp()
    bot._setup_complete = True

    lifecycle_calls = []

    async def fake_lifecycle(fingerprint):
        lifecycle_calls.append(fingerprint)

    monkeypatch.setattr(bot, "_run_polling_lifecycle", fake_lifecycle)

    bot.run()
    assert len(lifecycle_calls) == 1
    assert bot.app.calls == 0

    try:
        bot.run()
        assert False, "expected second run() to fail"
    except RuntimeError as e:
        assert "already started" in str(e)
