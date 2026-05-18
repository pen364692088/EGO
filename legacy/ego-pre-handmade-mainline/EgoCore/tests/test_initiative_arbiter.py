from __future__ import annotations

from app.runtime_v2.initiative_arbiter import evaluate_proactive_followup
from app.runtime_v2.state import RuntimeV2State


def _state_with_chat() -> RuntimeV2State:
    state = RuntimeV2State(session_id="session:test")
    chat_state = state.get_chat_state()
    chat_state.recent_user_turns = ["我觉得是有了OS的操作员的感觉。"]
    chat_state.recent_assistant_replies = ["这个自觉挺关键的。"]
    return state


def test_initiative_arbiter_builds_controlled_delivery_draft() -> None:
    state = _state_with_chat()
    developmental_result = {
        "developmental_summary": {
            "gate_status": "allow",
            "background_thought_candidates": [
                {
                    "candidate_id": "cand_001",
                    "candidate_type": "self_model_hypothesis",
                    "draft_text": "我刚才一直在想你那句“有了OS的操作员的感觉”。也许那个操作员本身也是系统里跑出来的一层解释。",
                    "initiative_score": 0.82,
                    "delivery_ready": True,
                    "source_cycle": "cycle_001",
                    "source_candidate_hash": "hash_001",
                }
            ],
        },
        "developmental_gate": {"status": "allow"},
    }

    verdict = evaluate_proactive_followup(
        state=state,
        developmental_result=developmental_result,
        idle_seconds=900.0,
        controlled_mode=True,
    )

    assert verdict.status == "delivery_ready"
    assert verdict.delivery_ready is True
    assert "操作员" in verdict.draft_reply_text
    assert verdict.response_plan is not None
    assert verdict.response_plan.metadata["initiative_mode"] == "controlled_shadow_delivery_draft"


def test_initiative_arbiter_holds_when_candidate_repeats_recent_reply() -> None:
    state = _state_with_chat()
    state.get_chat_state().recent_assistant_replies.append("我后来又想了一下。")
    developmental_result = {
        "developmental_summary": {
            "gate_status": "allow",
            "background_thought_candidates": [
                {
                    "candidate_id": "cand_001",
                    "candidate_type": "interpretation",
                    "draft_text": "我后来又想了一下。",
                    "initiative_score": 0.75,
                    "delivery_ready": True,
                    "source_cycle": "cycle_001",
                    "source_candidate_hash": "hash_001",
                }
            ],
        },
        "developmental_gate": {"status": "allow"},
    }

    verdict = evaluate_proactive_followup(
        state=state,
        developmental_result=developmental_result,
        idle_seconds=900.0,
        controlled_mode=True,
    )

    assert verdict.status == "held"
    assert verdict.reason == "no_non_repetitive_candidate"


def test_initiative_arbiter_holds_when_active_task_present() -> None:
    state = _state_with_chat()
    state.task_status = "running"
    state.current_goal = "finish current task"
    developmental_result = {
        "developmental_summary": {
            "gate_status": "allow",
            "background_thought_candidates": [
                {
                    "candidate_id": "cand_001",
                    "candidate_type": "interpretation",
                    "draft_text": "我后来又想到一个问题。",
                    "initiative_score": 0.75,
                    "delivery_ready": True,
                    "source_cycle": "cycle_001",
                    "source_candidate_hash": "hash_001",
                }
            ],
        },
        "developmental_gate": {"status": "allow"},
    }

    verdict = evaluate_proactive_followup(
        state=state,
        developmental_result=developmental_result,
        idle_seconds=900.0,
        controlled_mode=True,
    )

    assert verdict.status == "held"
    assert verdict.reason == "active_task_present"
