from __future__ import annotations

from datetime import datetime

from app.openemotion_adapter.proto_self_adapter import normalize_to_kernel_event
from openemotion.proto_self import KernelOutput, ReflectionNote, ResponseTendency, serialize_kernel_output


def test_normalize_to_kernel_event_absorbs_legacy_risk_alias():
    event = normalize_to_kernel_event(
        {
            "event_id": "evt_legacy_risk",
            "timestamp": datetime.now().isoformat(),
            "actor": "user",
            "source": "telegram",
            "event_type": "user_message",
            "safety_context": {"risk": "high", "boundary_touched": True},
        }
    )

    assert event.safety_context["risk_level"] == "high"
    assert "risk" not in event.safety_context


def test_normalize_to_kernel_event_keeps_canonical_risk_level():
    event = normalize_to_kernel_event(
        {
            "event_id": "evt_canonical_risk",
            "timestamp": datetime.now().isoformat(),
            "actor": "user",
            "source": "telegram",
            "event_type": "user_message",
            "safety_context": {"risk_level": "medium"},
        }
    )

    assert event.safety_context == {"risk_level": "medium"}


def test_serialize_kernel_output_uses_full_canonical_contract():
    output = KernelOutput(
        event_id="evt_out_001",
        identity_state_delta={"identity_confidence_delta": -0.05},
        self_model_delta={"current_mode": "repair"},
        memory_update={"append_episode": True},
        relationship_update={},
        appraisal_state_delta={"caution": 0.7},
        reflection_note=ReflectionNote(
            trigger="external_failure",
            diagnosis="tool failed",
            proposed_adjustment={"mode": "repair"},
        ),
        policy_hint={"risk_bias": "high"},
        response_tendency=ResponseTendency(
            preferred_mode="ask",
            preferred_tone="cautious",
            certainty_bound="bounded",
            suggested_next_step="clarify_or_repair",
            ask_needed=True,
        ),
        confidence_meta={"identity_confidence": 0.45},
        trace_payload={"event_id": "evt_out_001"},
    )

    payload = serialize_kernel_output(output)
    assert payload["schema_version"] == "proto_self.v1"
    assert payload["event_id"] == "evt_out_001"
    assert payload["memory_update"]["append_episode"] is True
    assert payload["confidence_meta"]["identity_confidence"] == 0.45
    assert payload["response_tendency"]["preferred_mode"] == "ask"
