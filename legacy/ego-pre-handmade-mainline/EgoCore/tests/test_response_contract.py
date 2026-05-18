from app.response_contract import (
    build_direct_response_plan,
    build_runtime_result_response_plan,
    build_status_response_plan,
    evaluate_memory_claim,
)
from app.response_contract.memory_claim_gate import build_current_session_recall_grounding
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


def test_memory_claim_gate_allows_grounded_current_session_recall() -> None:
    grounding = build_current_session_recall_grounding(
        recent_user_turns=[
            "我在想，意识的门槛其实可能比人类自以为的低很多。",
            "是不是可以想成一条光谱，我们可能都在中间某个位置？",
            "还记得我吗",
        ],
        current_user_turn="还记得我吗",
    )

    verdict = evaluate_memory_claim(
        "还记得，你刚才在聊意识光谱。",
        current_session_grounding=grounding,
    )

    assert verdict.claim_detected is True
    assert verdict.allowed is True
    assert verdict.reason == "grounded_current_session_recall"


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
    assert plan.epistemic_status == "interpreted"
    assert plan.commitment_level == "soft"
    assert plan.must_not_upgrade["epistemic_upgrade"] is True
    assert "回应当前在线确认" in plan.must_include
    assert "allowed_tones" in plan.tone_bounds
    intent_contract_source = plan.metadata["intent_contract_source"]
    assert intent_contract_source["authority_source"] == "response_contract.intent_contract_source"
    assert intent_contract_source["source_status"] == "default_host_contract"
    assert intent_contract_source["grounding_source"] == "host_expression_contract"
    assert intent_contract_source["grounding"]["reply_scope"]["conversation_act"] == "presence_check"
    assert state.to_decision_prompt_context()["ingress_context"]["conversation_act"] == "presence_check"


def test_build_runtime_result_response_plan_preserves_chat_expression_metadata() -> None:
    state = RuntimeV2State(session_id="s")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
    }
    result = RuntimeV2TurnResult(
        status="chat",
        state=state,
        reply=RuntimeV2Reply(
            reply_text="我在回应你。",
            delivery_kind="chat",
            status="chat",
            metadata={
                "chat_expression_hint": {
                    "reply_mode": "normal",
                    "tone_profile": "supportive",
                    "next_step_bias": "explore",
                    "why": "conversation_act=light_chitchat",
                },
                "response_tendency_summary": {
                    "preferred_mode": "defer",
                    "preferred_tone": "cautious",
                    "suggested_next_step": "route realization proposals to controlled host-lane review",
                },
            },
        ),
    )

    plan = build_runtime_result_response_plan(result.reply, state)

    assert plan.chat_cadence_mode == "reply_now_normal"
    assert plan.metadata["chat_cadence_mode"] == "reply_now_normal"
    assert plan.metadata["chat_expression_hint"]["reply_mode"] == "normal"
    assert plan.metadata["chat_expression_hint"]["tone_profile"] == "supportive"
    assert plan.metadata["response_tendency_summary"]["preferred_mode"] == "defer"


def test_build_runtime_result_response_plan_maps_hold_reply_mode_to_hold_cadence() -> None:
    state = RuntimeV2State(session_id="s")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
    }
    result = RuntimeV2TurnResult(
        status="chat",
        state=state,
        reply=RuntimeV2Reply(
            reply_text="我刚想到一个更贴切的角度。",
            delivery_kind="chat",
            status="chat",
            metadata={
                "chat_expression_hint": {
                    "reply_mode": "hold",
                    "tone_profile": "supportive",
                    "next_step_bias": "stabilize",
                    "why": "conversation_act=light_chitchat; initiative=hold",
                },
            },
        ),
    )

    plan = build_runtime_result_response_plan(result.reply, state)

    assert plan.chat_cadence_mode == "hold_for_followup"
    assert plan.metadata["chat_cadence_mode"] == "hold_for_followup"


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


def test_build_runtime_result_response_plan_allows_grounded_same_session_recall() -> None:
    state = RuntimeV2State(session_id="s")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
    }
    state.last_user_turn = "还记得我吗"
    chat_state = state.get_chat_state()
    chat_state.recent_user_turns = [
        "我在想，意识的门槛其实可能比人类自以为的低很多。",
        "是不是可以想成一条光谱，我们可能都在中间某个位置？",
        "还记得我吗",
    ]
    result = RuntimeV2TurnResult(
        status="chat",
        state=state,
        reply=RuntimeV2Reply(
            reply_text="还记得，你刚才在聊意识光谱。",
            delivery_kind="chat",
            status="chat",
        ),
    )

    plan = build_runtime_result_response_plan(result.reply, state)

    assert plan.memory_claim_verdict is not None
    assert plan.memory_claim_verdict.allowed is True
    assert plan.memory_claim_verdict.reason == "grounded_current_session_recall"
    assert plan.reply_authority == "model_chat"
    assert plan.reply_text == "还记得，你刚才在聊意识光谱。"


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


def test_build_direct_response_plan_normalizes_intent_contract_source_inputs() -> None:
    state = RuntimeV2State(session_id="s")
    plan = build_direct_response_plan(
        "嗯，我在。",
        kind="chat",
        delivery_kind="chat",
        authority_source="test",
        reply_authority="model_chat",
        metadata={
            "conversation_act": "presence_check",
            "allowed_claims": ["当前在线"],
            "forbidden_claims": ["不要声称 joy 上升"],
            "grounding": {"affect_summary": {"joy": 0.0}},
        },
        state=state,
    )

    source = plan.metadata["intent_contract_source"]

    assert source["source_status"] == "normalized_metadata_inputs"
    assert source["allowed_claims"] == [{"claim": "当前在线", "source": "response_plan.metadata"}]
    assert source["forbidden_claims"] == [
        {
            "pattern": "不要声称 joy 上升",
            "reason": "explicit_forbidden_claim",
            "severity": "ERROR",
        }
    ]
    assert source["grounding"] == {"affect_summary": {"joy": 0.0}}
    assert source["grounding_source"] == "metadata.grounding"
