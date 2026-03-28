from pathlib import Path

from app.telegram_bot import create_bot_from_config
from app.config import load_config
from app.restore_runtime import PendingRestoreObservation


def test_create_bot_from_config_uses_runtime_v2_by_default(monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    load_config(validate=False)
    bot = create_bot_from_config()
    assert bot.use_runtime_v2 is True


def test_create_bot_from_config_accepts_pending_restore_observation(monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    load_config(validate=False)
    observation = PendingRestoreObservation(
        restore_id="restore_001",
        restore_status="success",
        loaded_layers=["identity"],
        degraded_mode=False,
        degradation_reason=None,
        restore_timestamp="2026-03-28T00:00:00+00:00",
    )
    bot = create_bot_from_config(pending_restore_observation=observation)
    assert bot._pending_restore_observation is observation
