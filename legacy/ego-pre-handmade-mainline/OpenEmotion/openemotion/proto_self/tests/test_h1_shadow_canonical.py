from __future__ import annotations

from datetime import datetime

from openemotion.proto_self import KernelEvent, ProtoSelfState
from openemotion.proto_self.h1_shadow import build_h1_shadow_key
from openemotion.proto_self.kernel import process_event


def _tool_result_event(*, event_id: str, success: bool, runtime_summary: dict | None = None) -> KernelEvent:
    return KernelEvent(
        event_id=event_id,
        timestamp=datetime.now().isoformat(),
        actor="system",
        source="runtime",
        event_type="tool_result",
        runtime_summary=runtime_summary or {},
        safety_context={"risk_level": "medium"},
        external_result={
            "success": success,
            "tool": "shell",
            "exit_code": 0 if success else 1,
            "error": None if success else "boom",
        },
    )


def _user_event(*, event_id: str, runtime_summary: dict | None = None) -> KernelEvent:
    return KernelEvent(
        event_id=event_id,
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
        user_intent="继续",
        runtime_summary=runtime_summary or {},
        safety_context={"risk_level": "low"},
    )


def test_h1_shadow_flag_off_emits_no_shadow_telemetry():
    state = ProtoSelfState.empty()

    output = process_event(
        state,
        _tool_result_event(event_id="h1-shadow-off", success=False),
    )

    assert "shadow_h1" not in output.trace_payload
    assert "shadow_h1_enabled" not in output.confidence_meta
    assert state.self_model.counterfactual_success_by_action == {}
    assert state.self_model.recent_correction_tags == {}


def test_h1_shadow_is_shadow_only_and_does_not_perturb_followup_public_behavior():
    runtime_summary = {
        "h1_canonical_shadow": {
            "enabled": True,
            "shadow_only": True,
            "allowlisted": True,
            "source": "canonical_shadow",
        }
    }
    state_on = ProtoSelfState.empty()
    state_off = ProtoSelfState.empty()

    process_event(
        state_on,
        _tool_result_event(event_id="h1-shadow-on-failure", success=False, runtime_summary=runtime_summary),
    )
    process_event(
        state_off,
        _tool_result_event(event_id="h1-shadow-off-failure", success=False),
    )

    shadow_key = build_h1_shadow_key("tool:shell")
    assert state_on.self_model.counterfactual_success_by_action[shadow_key] == 0.18
    assert state_on.self_model.recent_correction_tags[shadow_key] == 1.0
    assert state_off.self_model.counterfactual_success_by_action == {}
    assert state_off.self_model.recent_correction_tags == {}

    followup_on = process_event(
        state_on,
        _user_event(event_id="h1-shadow-followup-on", runtime_summary=runtime_summary),
    )
    followup_off = process_event(
        state_off,
        _user_event(event_id="h1-shadow-followup-off"),
    )

    assert followup_on.policy_hint == followup_off.policy_hint
    assert followup_on.response_tendency is not None
    assert followup_off.response_tendency is not None
    assert followup_on.response_tendency.to_dict() == followup_off.response_tendency.to_dict()
    assert "shadow_h1" not in followup_on.trace_payload
    assert "shadow_h1_enabled" not in followup_on.confidence_meta
    assert followup_on.policy_hint.get("shadow_counterfactual_guard") is None
    assert followup_on.response_tendency.ask_needed is False


def test_h1_shadow_trace_roundtrip_preserves_shadow_summary():
    state = ProtoSelfState.empty()
    runtime_summary = {
        "h1_canonical_shadow": {
            "enabled": True,
            "shadow_only": True,
            "allowlisted": True,
            "source": "canonical_shadow",
        }
    }

    output = process_event(
        state,
        _tool_result_event(event_id="h1-shadow-roundtrip", success=False, runtime_summary=runtime_summary),
    )

    assert output.trace_payload["shadow_h1"]["action_key"] == "tool:shell"
    assert output.trace_payload["shadow_h1"]["would_guard"] is True
    assert output.confidence_meta["shadow_h1_action_key"] == "tool:shell"


def test_h1_shadow_does_not_emit_for_user_message_negative_control():
    state = ProtoSelfState.empty()
    runtime_summary = {
        "h1_canonical_shadow": {
            "enabled": True,
            "shadow_only": True,
            "allowlisted": True,
            "source": "canonical_shadow",
        }
    }

    output = process_event(
        state,
        _user_event(event_id="h1-shadow-negative-control", runtime_summary=runtime_summary),
    )

    assert "shadow_h1" not in output.trace_payload
    assert "shadow_h1_enabled" not in output.confidence_meta
