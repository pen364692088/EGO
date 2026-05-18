from app.telegram_bot import TelegramBot


def test_run_can_start_without_manual_setup(monkeypatch):
    bot = TelegramBot(token="test-token")

    class DummyBuilder:
        def token(self, token):
            return self
        def build(self):
            app = type("App", (), {})()
            app.add_handler = lambda *a, **k: None
            app.bot = type("B", (), {})()
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

    lifecycle_calls = []

    async def fake_lifecycle(fingerprint):
        lifecycle_calls.append(fingerprint)

    monkeypatch.setattr("app.telegram_bot.Application", DummyApplication)
    monkeypatch.setattr("app.telegram_bot.CommandHandler", lambda *a, **k: object())
    monkeypatch.setattr("app.telegram_bot.MessageHandler", lambda *a, **k: object())
    monkeypatch.setattr("app.telegram_bot.filters", type("F", (), {"TEXT": DummyFilter(), "COMMAND": DummyFilter()})())
    monkeypatch.setattr(bot, "_run_polling_lifecycle", fake_lifecycle)

    bot.run()
    assert len(lifecycle_calls) == 1
    assert bot.app is not None
