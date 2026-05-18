import importlib
import os
import shutil
import tempfile

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from openemotion.self_model import SelfModelStore
from openemotion.self_model.model import create_default_self_model


@pytest_asyncio.fixture
async def behavioral_proof_env(monkeypatch, tmp_path):
    """Build an isolated emotiond API environment for Step04F proof tests."""
    from emotiond import config, db, core
    import emotiond.api as api

    test_data_dir = tempfile.mkdtemp(prefix="emotiond_mvp13_behavior_")
    original_db_path = os.environ.get("EMOTIOND_DB_PATH")
    original_test_mode = os.environ.get("EMOTIOND_TEST_MODE")

    os.environ["EMOTIOND_DB_PATH"] = os.path.join(test_data_dir, "test_emotiond.db")
    os.environ["EMOTIOND_TEST_MODE"] = "1"

    config = importlib.reload(config)
    db = importlib.reload(db)
    core = importlib.reload(core)
    api = importlib.reload(api)

    core.emotion_state.valence = 0.0
    core.emotion_state.arousal = 0.3
    core.emotion_state.subjective_time = 0
    core.emotion_state.prediction_error = 0.0
    core.emotion_state.anger = 0.0
    core.emotion_state.sadness = 0.0
    core.emotion_state.anxiety = 0.0
    core.emotion_state.joy = 0.0
    core.emotion_state.loneliness = 0.0
    core.emotion_state.social_safety = 0.6
    core.emotion_state.energy = 0.7
    core.relationship_manager.relationships = {}
    core.relationship_manager.last_actions = {}
    core._predictions = {}
    core._target_predictions = {}

    await db.init_db()
    await core.load_initial_state()

    # Fix base scores so that only the formal owner intervention changes the
    # decision outcome on the same real mainline endpoint.
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

    store = SelfModelStore(base_dir=tmp_path / "self_model_store")

    def fake_get_auto_tune_param(name: str, default):
        if name == "self_bias_weight":
            return 1.0
        return default

    monkeypatch.setattr(core, "_formal_self_model_store", store)
    monkeypatch.setattr(core, "get_auto_tune_param", fake_get_auto_tune_param)

    yield {"api": api, "db": db, "core": core, "store": store}

    if original_db_path is not None:
        os.environ["EMOTIOND_DB_PATH"] = original_db_path
    else:
        os.environ.pop("EMOTIOND_DB_PATH", None)

    if original_test_mode is not None:
        os.environ["EMOTIOND_TEST_MODE"] = original_test_mode
    else:
        os.environ.pop("EMOTIOND_TEST_MODE", None)

    shutil.rmtree(test_data_dir, ignore_errors=True)


def build_client(api_module):
    transport = ASGITransport(app=api_module.app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_formal_owner_intervention_changes_same_decision_endpoint(
    behavioral_proof_env,
):
    modules = behavioral_proof_env
    api = modules["api"]
    db = modules["db"]
    core = modules["core"]
    store = modules["store"]

    target = "mvp13_behavior_target"
    target_id = "session:mvp13_behavior_target"
    core.relationship_manager._ensure_relationship_fields(target)
    owner_model = create_default_self_model(target)

    request_payload = {
        "user_id": target,
        "user_text": "make a decision",
        "focus_target": target,
        "counterparty_id": target,
        "target_id": target_id,
        "agent_id": "agent",
    }

    async with build_client(api) as client:
        owner_model.confidence_by_domain = {
            "action:approach": 1.0,
            "action:withdraw": 0.0,
        }
        store.save(owner_model, update_source="test", trace_reference="test:formal_owner_control")
        control = await client.post(
            f"/decision/target?test_mode=true&target_id={target_id}",
            json=request_payload,
        )

        assert control.status_code == 200
        control_data = control.json()
        assert control_data["action"] == "approach"
        assert control_data["explanation"]["selected"] == "approach"
        assert control_data["explanation"]["candidates"][0]["action"] == "approach"

        owner_model.confidence_by_domain = {
            "action:approach": 0.0,
            "action:withdraw": 1.0,
        }
        store.save(owner_model, update_source="test", trace_reference="test:formal_owner_intervention")
        intervention = await client.post(
            f"/decision/target?test_mode=true&target_id={target_id}",
            json=request_payload,
        )

    assert intervention.status_code == 200
    intervention_data = intervention.json()
    assert intervention_data["action"] == "withdraw"
    assert intervention_data["explanation"]["selected"] == "withdraw"
    assert intervention_data["explanation"]["candidates"][0]["action"] == "withdraw"

    latest = await db.get_latest_decision_for_target(target)
    assert latest is not None
    assert latest["action"] == "withdraw"
    assert latest["explanation"]["selected"] == "withdraw"

    # Same target, same target_id, same endpoint, only formal-owner action
    # confidence changed.
    assert control_data["target"] == intervention_data["target"] == target
    assert control_data["target_id"] == intervention_data["target_id"] == target_id
    assert control_data["action"] != intervention_data["action"]
