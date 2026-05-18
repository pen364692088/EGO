import app.telegram_bot as telegram_bot_module

from app.restore_runtime import PendingRestoreObservation
from app.runtime_v2.state import RuntimeV2State
from app.telegram_bot import TelegramBot


def test_pending_restore_observation_is_single_use(monkeypatch):
    captured = {}

    class FakeCollector:
        def capture_restore_observation(self, observation):
            captured["observation"] = observation

    monkeypatch.setattr(telegram_bot_module, "_EVIDENCE_COLLECTOR_AVAILABLE", True)
    monkeypatch.setattr(telegram_bot_module, "get_evidence_collector", lambda: FakeCollector())

    bot = TelegramBot(
        token="dummy",
        use_runtime_v2=True,
        pending_restore_observation=PendingRestoreObservation(
            restore_id="restore_001",
            restore_status="success",
            loaded_layers=["identity", "self_model", "summary"],
            degraded_mode=False,
            degradation_reason=None,
            restore_timestamp="2026-03-28T00:00:00+00:00",
            injection_summary={"injected": True},
            recovery_hints_present=True,
            standing_commitments_preview=["protect continuity"],
        ),
    )
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.ingress_context = {"runtime_action": "chat"}

    first = bot._activate_pending_restore_observation(state)
    second = bot._activate_pending_restore_observation(state)

    assert first["restore_id"] == "restore_001"
    assert first["post_restore_first_turn"] is True
    assert state.ingress_context["restore_observation"]["restore_status"] == "success"
    assert captured["observation"]["restore_id"] == "restore_001"
    assert second is None
