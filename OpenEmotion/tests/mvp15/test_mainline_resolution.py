import importlib
import os
import tempfile

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture(scope="function")
async def isolated_mvp15_mainline_env():
    from emotiond import api, config, core, db
    from emotiond.reflection_adapter import reset_reflection_adapter

    test_data_dir = tempfile.mkdtemp(prefix="emotiond_mvp15_mainline_")
    original_db_path = os.environ.get("EMOTIOND_DB_PATH")

    os.environ["EMOTIOND_DB_PATH"] = os.path.join(test_data_dir, "test_emotiond.db")
    os.environ["ENABLE_MVP15_SHADOW"] = "true"
    os.environ["ENABLE_MVP15_MAINLINE_GUIDANCE"] = "true"

    reset_reflection_adapter()
    importlib.reload(config)
    importlib.reload(db)
    importlib.reload(core)
    importlib.reload(api)

    core.emotion_state.valence = 0.0
    core.emotion_state.arousal = 0.3
    core.emotion_state.prediction_error = 0.0
    core.emotion_state.social_safety = 0.6
    core.emotion_state.energy = 0.7
    core.emotion_state.uncertainty = 0.3
    core.relationship_manager.relationships = {}
    core.relationship_manager.last_actions = {}

    await db.init_db()
    await core.load_initial_state()

    yield api.app

    if original_db_path:
        os.environ["EMOTIOND_DB_PATH"] = original_db_path
    else:
        os.environ.pop("EMOTIOND_DB_PATH", None)
    reset_reflection_adapter()


def _assert_bounded_guidance(guidance: dict, expected_source: str, expected_target_id: str) -> None:
    assert guidance["proposal_discipline"] == "proposal_only"
    assert guidance["writeback_surface"] == "plan_and_decision_explanation_only"
    assert guidance["behavioral_authority"] == "none"
    assert guidance["source"] == expected_source
    assert guidance["target_id"] == expected_target_id
    assert "reflection" in guidance
    assert "counterfactual" in guidance
    assert "summary" in guidance["reflection"]
    assert "strategy_source" in guidance["counterfactual"]
    assert guidance["counterfactual"]["strategy_source"] in {"adaptive", "counterfactual"}


@pytest.mark.asyncio
async def test_plan_mainline_includes_reflection_guidance(isolated_mvp15_mainline_env):
    transport = ASGITransport(app=isolated_mvp15_mainline_env)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/plan",
            json={"user_id": "user_mvp15", "user_text": "help me think this through"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "reflection_guidance" in data
    _assert_bounded_guidance(
        data["reflection_guidance"],
        expected_source="core.generate_plan",
        expected_target_id="user_mvp15",
    )


@pytest.mark.asyncio
async def test_decision_target_mainline_explanation_includes_reflection_guidance(
    isolated_mvp15_mainline_env,
):
    transport = ASGITransport(app=isolated_mvp15_mainline_env)
    target_id = "thread:mvp15"
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/decision/target?test_mode=true&target_id={target_id}",
            json={"user_id": "user_mvp15", "user_text": "help me think this through"},
        )

    assert response.status_code == 200
    data = response.json()
    guidance = data["explanation"]["reflection_guidance"]
    _assert_bounded_guidance(
        guidance,
        expected_source="core.generate_explanation_v31",
        expected_target_id=target_id,
    )
