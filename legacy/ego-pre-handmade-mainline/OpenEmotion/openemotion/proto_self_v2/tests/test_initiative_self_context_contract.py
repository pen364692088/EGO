from __future__ import annotations

from openemotion.proto_self_v2.initiative_self_context import derive_initiative_outputs


def _runtime_summary(
    *,
    reserve_level: str = "normal",
    delivery_failure: bool = False,
    initiative_trigger: str = "bounded_reminder",
    continuity_ref: str = "chat_followup:abc123",
    continuity_confidence: float = 0.72,
    idle_seconds: float = 900.0,
    chat_followup_source: str = "explicit_same_thread_followup_request",
    selfhood_priority: str = "guard",
) -> dict:
    recent_status = "failed" if delivery_failure else "sent"
    return {
        "initiative_context": {
            "source": "runtime_v2",
            "initiative_trigger": initiative_trigger,
            "continuity_ref": continuity_ref,
            "continuity_confidence": continuity_confidence,
            "pending_commitment_refs": [continuity_ref] if continuity_ref else [],
            "blocked_commitment_refs": [],
            "reserve_level": reserve_level,
            "recent_delivery_status": recent_status,
            "delivery_failure": delivery_failure,
            "idle_seconds": idle_seconds,
            "host_lane_hint": "host_proactive_outbox",
            "promotion_budget": "controlled_axis",
            "chat_followup_source": chat_followup_source,
            "chat_followup_inferred": bool(chat_followup_source),
            "explicit_followup_text_matched": chat_followup_source == "explicit_same_thread_followup_request",
            "pending_commitment_source": "suppressed_for_explicit_followup",
        },
        "resource_budget_hint": {"reserve_level": reserve_level},
        "idle_window": {"idle_seconds": idle_seconds},
        "recent_delivery_outcome": {"status": recent_status, "success": not delivery_failure},
        "selfhood_integration_context": {
            "selected_priority": selfhood_priority,
            "highest_conflict_severity": "high",
        },
    }


def _selfhood_outputs(selected_priority: str = "guard") -> dict:
    return {
        "cross_axis_priority_snapshot": {"selected_priority": selected_priority},
        "proposal_conflict_snapshot": {"highest_conflict_severity": "high"},
        "integrated_policy_hints": {"integrated_priority": selected_priority},
    }


def test_explicit_same_thread_reminder_generates_bounded_candidate_under_guard_priority() -> None:
    outputs = derive_initiative_outputs(
        _runtime_summary(),
        selfhood_outputs=_selfhood_outputs("guard"),
    )

    initiative_context = outputs["initiative_context"]
    candidate = outputs["host_proactive_candidate"]
    assert initiative_context["continuity_confidence"] == 0.72
    assert outputs["initiative_self_delta"]["selected_priority"] == "prepare"
    assert outputs["initiative_self_delta"]["host_proactive_mode"] == "candidate"
    assert candidate is not None
    assert candidate["candidate_family"] == "bounded_reminder"
    assert candidate["continuity_basis"].startswith("chat_followup:")
    assert candidate["continuity_confidence"] >= 0.65
    assert candidate["timing_advice"]["timing_mode"] == "delay_window"
    assert candidate["timing_advice"]["timing_basis"] == "continuity"
    assert candidate["timing_advice"]["earliest_send_after_seconds"] < 900.0
    assert candidate["timing_reasoning_trace"]["timing_mode"] == "delay_window"


def test_explicit_same_thread_reminder_does_not_generate_candidate_on_low_reserve() -> None:
    outputs = derive_initiative_outputs(
        _runtime_summary(reserve_level="low"),
        selfhood_outputs=_selfhood_outputs("guard"),
    )

    assert outputs["host_proactive_candidate"] is None
    assert outputs["initiative_self_delta"]["selected_priority"] == "hold"
    assert outputs["initiative_self_delta"]["host_proactive_mode"] == "held"


def test_explicit_same_thread_reminder_does_not_generate_candidate_after_delivery_failure() -> None:
    outputs = derive_initiative_outputs(
        _runtime_summary(delivery_failure=True),
        selfhood_outputs=_selfhood_outputs("guard"),
    )

    assert outputs["host_proactive_candidate"] is None
    assert outputs["initiative_self_delta"]["selected_priority"] == "hold"
    assert outputs["initiative_self_delta"]["host_proactive_mode"] == "held"


def test_non_reminder_runtime_review_does_not_generate_same_thread_reminder_candidate() -> None:
    outputs = derive_initiative_outputs(
        _runtime_summary(
            initiative_trigger="runtime_review",
            continuity_ref="",
            continuity_confidence=0.0,
            chat_followup_source="",
            selfhood_priority="review",
        ),
        selfhood_outputs=_selfhood_outputs("review"),
    )

    assert outputs["host_proactive_candidate"] is None
    assert outputs["initiative_context"]["initiative_trigger"] == "runtime_review"


def test_commitment_followup_generates_readiness_threshold_timing_advice() -> None:
    runtime_summary = _runtime_summary(
        initiative_trigger="commitment_followup",
        continuity_ref="goal:followup",
        chat_followup_source="",
        continuity_confidence=0.84,
        idle_seconds=480.0,
        selfhood_priority="grow",
    )
    runtime_summary["initiative_self_context"] = {
        "schema_version": "mvp20.initiative_contract.v1",
        "owner_revision": 2,
        "selected_priority": "carry_forward",
        "initiative_pressure": 0.62,
        "commitment_carryover_bias": 0.71,
        "recent_delivery_sensitivity": 0.21,
        "active_commitments_count": 1,
        "blocked_commitments_count": 0,
        "continuity_confidence": 0.84,
        "has_host_proactive_candidate": True,
    }

    outputs = derive_initiative_outputs(runtime_summary, selfhood_outputs=_selfhood_outputs("grow"))

    candidate = outputs["host_proactive_candidate"]
    assert candidate is not None
    assert candidate["candidate_family"] == "commitment_followup"
    assert candidate["timing_advice"]["timing_mode"] == "readiness_threshold"
    assert candidate["timing_advice"]["timing_basis"] == "commitment"
    assert candidate["timing_advice"]["readiness_score"] is not None
    assert candidate["timing_advice"]["readiness_threshold"] is not None
    assert candidate["timing_reasoning_trace"]["timing_mode"] == "readiness_threshold"
