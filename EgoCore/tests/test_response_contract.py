from app.response_contract import (
    build_direct_response_plan,
    build_runtime_result_response_plan,
    build_status_response_plan,
    evaluate_memory_claim,
)
from app.restore_runtime import PendingRestoreObservation
from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
from app.runtime_v2.state import RuntimeV2State


def test_memory_claim_gate_blocks_without_restore_authority() -> None:
    verdict = evaluate_memory_claim("我已经恢复成功，还记得你。")
    assert verdict.claim_detected is True
    assert verdict.allowed is False
    assert verdict.reason == "missing_restore_authority"


def test_memory_claim_gate_allows_with_restore_authority() -> None:
    observation = PendingRestoreObservation(
        restore_id="r1",
        restore_status="success",
        loaded_layers=["identity"],
        degraded_mode=False,
        degradation_reason=None,
        restore_timestamp="2026-03-31T08:00:00Z",
    )
    verdict = evaluate_memory_claim("我已经恢复成功，还记得你。", restore_observation=observation)
    assert verdict.claim_detected is True
    assert verdict.allowed is True
    assert verdict.authority_source == "restore_audit"


def test_build_status_response_plan_wraps_runtime_reply_and_verdict() -> None:
    state = RuntimeV2State(session_id="s", current_goal="整理任务", current_step="检查状态")
    observation = PendingRestoreObservation(
        restore_id="r1",
        restore_status="success",
        loaded_layers=["identity"],
        degraded_mode=False,
        degradation_reason=None,
        restore_timestamp="2026-03-31T08:00:00Z",
    )
    plan = build_status_response_plan(
        "status",
        state,
        assume_active=True,
        restore_observation=observation,
    )
    assert plan.kind == "status_probe"
    assert plan.delivery_kind == "final"
    assert "当前步骤" in plan.reply_text
    assert plan.memory_claim_verdict is not None
    assert plan.memory_claim_verdict.allowed is True


def test_build_runtime_result_response_plan_preserves_presence_conversation_act() -> None:
    state = RuntimeV2State(session_id="s")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "presence_check",
        "parser_source": "chat_default",
        "primary_intent": "chat",
    }
    result = RuntimeV2TurnResult(
        status="chat",
        state=state,
        reply=RuntimeV2Reply(
            reply_text="在的，请说。",
            delivery_kind="chat",
            status="chat",
        ),
    )

    plan = build_runtime_result_response_plan(result.reply, state)

    assert plan.reply_authority == "model_chat"
    assert plan.metadata["conversation_act"] == "presence_check"
    assert plan.metadata["reply_origin"] == "chat_mainline"
    assert plan.speaker_mode == "reflect"
    assert plan.epistemic_status == "uncertain"
    assert plan.commitment_level == "soft"
    assert plan.must_not_upgrade["epistemic_upgrade"] is True
    assert "回应当前在线确认" in plan.must_include
    assert "allowed_tones" in plan.tone_bounds
    assert state.to_decision_prompt_context()["ingress_context"]["conversation_act"] == "presence_check"


def test_build_runtime_result_response_plan_blocks_memory_claim_without_restore_authority() -> None:
    state = RuntimeV2State(session_id="s")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
    }
    result = RuntimeV2TurnResult(
        status="chat",
        state=state,
        reply=RuntimeV2Reply(
            reply_text="我还记得你。",
            delivery_kind="chat",
            status="chat",
        ),
    )

    plan = build_runtime_result_response_plan(result.reply, state)

    assert plan.memory_claim_verdict is not None
    assert plan.memory_claim_verdict.claim_detected is True
    assert plan.memory_claim_verdict.allowed is False
    assert plan.reply_authority == "host_degraded_fallback"
    assert "记得你" not in plan.reply_text
    assert plan.metadata["memory_claim_reason"] == "missing_restore_authority"


def test_build_direct_response_plan_applies_memory_claim_gate_with_restore_authority() -> None:
    state = RuntimeV2State(session_id="s")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
        "restore_observation": {
            "restore_id": "r1",
            "restore_status": "success",
            "loaded_layers": ["identity"],
            "degraded_mode": False,
            "degradation_reason": None,
            "restore_timestamp": "2026-03-31T08:00:00Z",
            "authority_source": "restore_audit",
            "injection_summary": {},
            "recovery_hints_present": False,
            "standing_commitments_preview": [],
            "post_restore_first_turn": True,
        },
    }

    plan = build_direct_response_plan(
        "我已经恢复成功，还记得你。",
        kind="chat",
        delivery_kind="chat",
        authority_source="test",
        reply_authority="model_chat",
        state=state,
    )

    assert plan.memory_claim_verdict is not None
    assert plan.memory_claim_verdict.allowed is True
    assert plan.reply_authority == "model_chat"
    assert plan.reply_text == "我已经恢复成功，还记得你。"
