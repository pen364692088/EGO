import importlib
import os
import shutil
import tempfile

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


def _set_drive_intensity(manager, drive_type, target_intensity: float, cause: str) -> None:
    drive = manager.state.active_drives[drive_type.value]
    manager.update_drive(drive_type, float(target_intensity) - float(drive.intensity), cause=cause)


def _configure_control_state(manager, drive_type) -> None:
    _set_drive_intensity(manager, drive_type.COMPLETION, 0.95, "step05c_control")
    _set_drive_intensity(manager, drive_type.EXPLORATION, 0.85, "step05c_control")
    _set_drive_intensity(manager, drive_type.CONSERVATION, 0.05, "step05c_control")
    _set_drive_intensity(manager, drive_type.VERIFICATION, 0.05, "step05c_control")
    _set_drive_intensity(manager, drive_type.STABILITY, 0.10, "step05c_control")
    _set_drive_intensity(manager, drive_type.REPAIR, 0.05, "step05c_control")
    _set_drive_intensity(manager, drive_type.COHERENCE, 0.10, "step05c_control")


def _configure_intervention_state(manager, drive_type) -> None:
    _set_drive_intensity(manager, drive_type.COMPLETION, 0.05, "step05c_intervention")
    _set_drive_intensity(manager, drive_type.EXPLORATION, 0.05, "step05c_intervention")
    _set_drive_intensity(manager, drive_type.CONSERVATION, 0.95, "step05c_intervention")
    _set_drive_intensity(manager, drive_type.VERIFICATION, 0.90, "step05c_intervention")
    _set_drive_intensity(manager, drive_type.STABILITY, 0.85, "step05c_intervention")
    _set_drive_intensity(manager, drive_type.REPAIR, 0.35, "step05c_intervention")
    _set_drive_intensity(manager, drive_type.COHERENCE, 0.60, "step05c_intervention")


def build_client(api_module):
    transport = ASGITransport(app=api_module.app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest_asyncio.fixture
async def drive_behavioral_proof_env(monkeypatch):
    """Build an isolated emotiond API environment for Step05C proof tests."""
    from emotiond import config, db, core, drive_adapter
    from emotiond.drives import manager as drive_manager_module
    import emotiond.api as api

    test_data_dir = tempfile.mkdtemp(prefix="emotiond_mvp14_behavior_")
    original_db_path = os.environ.get("EMOTIOND_DB_PATH")
    original_test_mode = os.environ.get("EMOTIOND_TEST_MODE")

    os.environ["EMOTIOND_DB_PATH"] = os.path.join(test_data_dir, "test_emotiond.db")
    os.environ["EMOTIOND_TEST_MODE"] = "1"

    config = importlib.reload(config)
    db = importlib.reload(db)
    drive_manager_module = importlib.reload(drive_manager_module)
    drive_adapter = importlib.reload(drive_adapter)
    core = importlib.reload(core)
    api = importlib.reload(api)

    drive_adapter.DriveStateAdapter.reset()
    drive_manager_module.reset_drive_manager()

    core.emotion_state.valence = 0.0
    core.emotion_state.arousal = 0.3
    core.emotion_state.subjective_time = 0
    core.emotion_state.prediction_error = 0.0
    core.emotion_state.anger = 0.0
    core.emotion_state.sadness = 0.0
    core.emotion_state.anxiety = 0.0
    core.emotion_state.joy = 0.0
    core.emotion_state.loneliness = 0.0
    core.emotion_state.regulation_budget = 1.0
    core.emotion_state.social_safety = 0.6
    core.emotion_state.energy = 0.7
    core.relationship_manager.relationships = {}
    core.relationship_manager.last_actions = {}
    core._predictions = {
        action: {
            "social_safety_delta": 0.0,
            "energy_delta": 0.0,
            "prediction_error_sum": 0.0,
            "prediction_count": 0,
        }
        for action in core.ACTION_SPACE
    }
    core._target_predictions = {}

    await db.init_db()
    await core.load_initial_state()

    adapter = drive_adapter.get_drive_adapter(enable_dual_run=True)

    def fake_self_model_bias(action: str, target):  # noqa: ARG001
        return 0.0

    original_get_auto_tune = core.get_auto_tune_param

    def controlled_auto_tune(name: str, default):
        if name == "drive_bias_weight":
            return 1.0
        if name == "self_bias_weight":
            return 0.0
        return original_get_auto_tune(name, default)

    monkeypatch.setattr(core, "_mvp14_adapter", adapter)
    monkeypatch.setattr(core, "ENABLE_MVP14_DUAL_RUN", True)
    monkeypatch.setattr(core, "_get_owner_backed_action_bias", fake_self_model_bias)
    monkeypatch.setattr(core, "get_auto_tune_param", controlled_auto_tune)

    yield {
        "api": api,
        "db": db,
        "core": core,
        "adapter": adapter,
        "drive_manager_module": drive_manager_module,
    }

    if original_db_path is not None:
        os.environ["EMOTIOND_DB_PATH"] = original_db_path
    else:
        os.environ.pop("EMOTIOND_DB_PATH", None)

    if original_test_mode is not None:
        os.environ["EMOTIOND_TEST_MODE"] = original_test_mode
    else:
        os.environ.pop("EMOTIOND_TEST_MODE", None)

    shutil.rmtree(test_data_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_drive_behavioral_influence_on_decision_target_mainline(
    drive_behavioral_proof_env,
):
    modules = drive_behavioral_proof_env
    api = modules["api"]
    db = modules["db"]
    core = modules["core"]
    drive_manager_module = modules["drive_manager_module"]

    target = "mvp14_drive_target"
    target_id = "session:mvp14_drive_target"
    core.relationship_manager._ensure_relationship_fields(target)

    request_payload = {
        "user_id": target,
        "user_text": "make a decision",
        "focus_target": target,
        "counterparty_id": target,
        "target_id": target_id,
        "agent_id": "agent",
    }

    manager = drive_manager_module.get_drive_manager()
    drive_type = drive_manager_module.DriveType

    async with build_client(api) as client:
        _configure_control_state(manager, drive_type)
        control = await client.post(
            f"/decision/target?test_mode=true&target_id={target_id}",
            json=request_payload,
        )

        assert control.status_code == 200
        control_data = control.json()
        assert control_data["action"] == "approach"
        assert control_data["explanation"]["selected"] == "approach"
        assert control_data["explanation"]["candidates"][0]["action"] == "approach"

        _configure_intervention_state(manager, drive_type)
        intervention = await client.post(
            f"/decision/target?test_mode=true&target_id={target_id}",
            json=request_payload,
        )

    assert intervention.status_code == 200
    intervention_data = intervention.json()
    assert intervention_data["action"] in {"withdraw", "boundary"}
    assert intervention_data["explanation"]["selected"] == intervention_data["action"]
    assert intervention_data["explanation"]["candidates"][0]["action"] == intervention_data["action"]

    latest = await db.get_latest_decision_for_target(target)
    assert latest is not None
    assert latest["action"] == intervention_data["action"]
    assert latest["explanation"]["selected"] == intervention_data["action"]

    assert control_data["target"] == intervention_data["target"] == target
    assert control_data["target_id"] == intervention_data["target_id"] == target_id
    assert control_data["action"] != intervention_data["action"]
