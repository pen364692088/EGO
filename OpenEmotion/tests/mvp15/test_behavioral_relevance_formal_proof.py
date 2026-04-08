import importlib
import os
import tempfile

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


def _make_reflection_guidance(
    *,
    source: str,
    target: str,
    target_id: str,
    intervention: bool,
) -> dict:
    return {
        "schema_version": "mvp15.mainline_guidance.v1",
        "source": source,
        "target": target,
        "target_id": target_id,
        "proposal_discipline": "proposal_only",
        "writeback_surface": "plan_and_decision_explanation_only",
        "behavioral_authority": "none",
        "reflection": {
            "summary": {
                "jobs_completed": 1 if intervention else 0,
                "pending_proposals": 2 if intervention else 0,
            },
            "latest_job": (
                {
                    "job_id": "job_step06b",
                    "reflection_type": "counterfactual",
                    "status": "completed",
                    "confidence": 0.82,
                    "proposal_count": 2,
                }
                if intervention
                else None
            ),
            "pending_proposals": 2 if intervention else 0,
        },
        "counterfactual": {
            "strategy_source": "counterfactual" if intervention else "adaptive",
            "mode": "info_seeking" if intervention else "normal",
            "risk_tolerance": 0.2 if intervention else 0.55,
            "info_seeking_weight": 0.85 if intervention else 0.35,
            "preferred_actions": ["clarify", "gather_info"] if intervention else [],
            "avoided_actions": ["novel_approach"] if intervention else [],
            "matched_counterfactual": intervention,
        },
    }


@pytest_asyncio.fixture(scope="function")
async def isolated_mvp15_behavioral_env():
    from emotiond import api, config, core, db

    test_data_dir = tempfile.mkdtemp(prefix="emotiond_mvp15_behavioral_")
    original_db_path = os.environ.get("EMOTIOND_DB_PATH")
    original_test_mode = os.environ.get("EMOTIOND_TEST_MODE")
    original_reflective_self_dir = os.environ.get("EMOTIOND_REFLECTIVE_SELF_DIR")

    os.environ["EMOTIOND_DB_PATH"] = os.path.join(test_data_dir, "test_emotiond.db")
    os.environ["EMOTIOND_REFLECTIVE_SELF_DIR"] = os.path.join(test_data_dir, "reflective_self")
    os.environ["ENABLE_MVP15_SHADOW"] = "true"
    os.environ["ENABLE_MVP15_MAINLINE_GUIDANCE"] = "true"
    os.environ["EMOTIOND_TEST_MODE"] = "true"

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

    yield api.app, core

    if original_db_path:
        os.environ["EMOTIOND_DB_PATH"] = original_db_path
    else:
        os.environ.pop("EMOTIOND_DB_PATH", None)
    if original_test_mode is not None:
        os.environ["EMOTIOND_TEST_MODE"] = original_test_mode
    else:
        os.environ.pop("EMOTIOND_TEST_MODE", None)
    if original_reflective_self_dir is not None:
        os.environ["EMOTIOND_REFLECTIVE_SELF_DIR"] = original_reflective_self_dir
    else:
        os.environ.pop("EMOTIOND_REFLECTIVE_SELF_DIR", None)


@pytest.mark.asyncio
async def test_plan_surface_proves_bounded_reflection_behavioral_relevance(
    isolated_mvp15_behavioral_env,
    monkeypatch,
):
    app, core = isolated_mvp15_behavioral_env
    transport = ASGITransport(app=app)

    def control_guidance(**kwargs):
        return _make_reflection_guidance(
            source=kwargs["source"],
            target=kwargs["target"],
            target_id=kwargs["target_id"],
            intervention=False,
        )

    def intervention_guidance(**kwargs):
        return _make_reflection_guidance(
            source=kwargs["source"],
            target=kwargs["target"],
            target_id=kwargs["target_id"],
            intervention=True,
        )

    request = {"user_id": "user_mvp15", "user_text": "help me think this through"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        monkeypatch.setattr(core, "_build_reflection_guidance", control_guidance)
        control = (await client.post("/plan", json=request)).json()

        monkeypatch.setattr(core, "_build_reflection_guidance", intervention_guidance)
        intervention = (await client.post("/plan", json=request)).json()

    assert control["tone"] == intervention["tone"]
    assert control["intent"] == intervention["intent"]
    assert control["focus_target"] == intervention["focus_target"]
    assert (
        "Prefer clarification and verification before committing to a response"
        not in control["constraints"]
    )
    assert (
        "Prefer clarification and verification before committing to a response"
        in intervention["constraints"]
    )
    assert (
        "Surface uncertainty explicitly and ask for the missing information"
        in intervention["key_points"]
    )
    assert intervention["language_guidance"]["reflection_considerations"] == [
        "Reflection guidance recommends an info-seeking posture",
        "Counterfactual guidance recommends risk-limiting safeguards",
        "Pending reflection proposals remain relevant to the current plan",
    ]
    assert intervention["language_guidance"]["reflection_proposal_discipline"] == "proposal_only"
    assert intervention["reflection_guidance"]["behavioral_authority"] == "none"


@pytest.mark.asyncio
async def test_decision_target_explanation_proves_bounded_reflection_behavioral_relevance(
    isolated_mvp15_behavioral_env,
    monkeypatch,
):
    app, core = isolated_mvp15_behavioral_env
    transport = ASGITransport(app=app)
    target_id = "thread:mvp15-step06b"

    def control_guidance(**kwargs):
        return _make_reflection_guidance(
            source=kwargs["source"],
            target=kwargs["target"],
            target_id=kwargs["target_id"],
            intervention=False,
        )

    def intervention_guidance(**kwargs):
        return _make_reflection_guidance(
            source=kwargs["source"],
            target=kwargs["target"],
            target_id=kwargs["target_id"],
            intervention=True,
        )

    request = {"user_id": "user_mvp15", "user_text": "help me think this through"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        monkeypatch.setattr(core, "_build_reflection_guidance", control_guidance)
        control = (
            await client.post(
                f"/decision/target?test_mode=true&target_id={target_id}",
                json=request,
            )
        ).json()

        monkeypatch.setattr(core, "_build_reflection_guidance", intervention_guidance)
        intervention = (
            await client.post(
                f"/decision/target?test_mode=true&target_id={target_id}",
                json=request,
            )
        ).json()

    assert control["action"] == intervention["action"]
    assert control["explanation"]["selected"] == intervention["explanation"]["selected"]
    assert "reflection_relevance" not in control["explanation"]
    assert intervention["explanation"]["reflection_relevance"] == {
        "proposal_discipline": "proposal_only",
        "behavioral_authority": "none",
        "considerations": [
            "Reflection guidance recommends an info-seeking posture",
            "Counterfactual guidance recommends risk-limiting safeguards",
            "Pending reflection proposals remain relevant to the current plan",
        ],
    }
    assert intervention["explanation"]["reflection_guidance"]["behavioral_authority"] == "none"
