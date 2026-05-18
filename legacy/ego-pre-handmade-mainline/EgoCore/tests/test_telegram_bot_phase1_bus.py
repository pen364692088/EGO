import pytest

from app.telegram_bot import TelegramBot


@pytest.mark.asyncio
async def test_telegram_bot_phase1_bus_writes_session_log(tmp_path):
    bot = TelegramBot(token="dummy", use_runtime_v2=False)
    bot._session_log_manager.root = tmp_path

    await bot._publish_phase1_event(
        session_key="telegram:dm:42",
        kind="telegram_ingress",
        payload={"text_preview": "hello"},
        trace_id="trace-1",
        message_id=7,
    )

    log_path = bot._session_log_manager.get_log("telegram:dm:42").path
    contents = log_path.read_text(encoding="utf-8")
    assert "telegram_ingress" in contents
    assert "trace-1" in contents
