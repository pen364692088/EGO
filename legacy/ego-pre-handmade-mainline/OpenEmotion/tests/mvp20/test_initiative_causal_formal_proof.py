from openemotion.proto_self_v2.kernel import process_update_packet
from openemotion.proto_self_v2.schemas import UpdateEventV2, UpdatePacketV2
from openemotion.proto_self_v2.state import ProtoSelfStateV2


def _packet(*, event_id: str, runtime_summary: dict | None = None, raw_text: str = "continue") -> UpdatePacketV2:
    return UpdatePacketV2(
        event_id=event_id,
        timestamp="2026-04-04T20:00:00",
        event=UpdateEventV2(
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="initiative_continuity",
            raw_text=raw_text,
        ),
        conversation_summary={"session_id": "session:mvp20:causal", "turn_id": event_id},
        task_summary={"pending_tasks": 0, "blocked_tasks": 0},
        runtime_summary={
            "runtime": "runtime_v2",
            "state_scope": "agent_global",
            **(runtime_summary or {}),
        },
        safety_context={"risk_level": "low"},
    )


def _initiative_owner_projection(
    *,
    owner_revision: int,
    initiative_pressure: float = 0.22,
    commitment_carryover_bias: float = 0.24,
    recent_delivery_sensitivity: float = 0.28,
    selected_priority: str = "review",
    active_commitments_count: int = 0,
    blocked_commitments_count: int = 0,
    continuity_confidence: float = 0.82,
) -> dict:
    return {
        "schema_version": "mvp20-owner-v1",
        "owner_revision": owner_revision,
        "last_revision_id": f"initiative_rev_{owner_revision:06d}",
        "dominant_mode": selected_priority,
        "initiative_pressure": initiative_pressure,
        "commitment_carryover_bias": commitment_carryover_bias,
        "recent_delivery_sensitivity": recent_delivery_sensitivity,
        "selected_priority": selected_priority,
        "active_commitments_count": active_commitments_count,
        "blocked_commitments_count": blocked_commitments_count,
        "continuity_confidence": continuity_confidence,
        "has_initiative_proposal_candidate": initiative_pressure >= 0.55
        or commitment_carryover_bias >= 0.5
        or active_commitments_count > 0
        or blocked_commitments_count > 0,
        "has_host_proactive_candidate": False,
    }


def _initiative_context(
    *,
    initiative_trigger: str = "bounded_followup",
    continuity_ref: str = "commitment:followup:001",
    reserve_level: str = "medium",
    delivery_status: str = "sent",
    idle_seconds: float = 1200.0,
    blocked_refs: list[str] | None = None,
    pending_refs: list[str] | None = None,
    promotion_budget: str = "controlled_axis",
) -> dict:
    delivery_failure = delivery_status in {"failed", "blocked", "timeout", "error"}
    return {
        "source": "runtime_v2",
        "initiative_trigger": initiative_trigger,
        "continuity_ref": continuity_ref,
        "pending_commitment_refs": list(pending_refs or ([] if continuity_ref == "" else [continuity_ref])),
        "blocked_commitment_refs": list(blocked_refs or []),
        "reserve_level": reserve_level,
        "recent_delivery_status": delivery_status,
        "delivery_failure": delivery_failure,
        "idle_seconds": idle_seconds,
        "host_lane_hint": "host_proactive_outbox",
        "promotion_budget": promotion_budget,
    }


def _selfhood_integration_context(
    *,
    selected_priority: str = "grow",
    conflict: str = "low",
) -> dict:
    return {
        "schema_version": "mvp19-owner-v1",
        "owner_revision": 3,
        "last_revision_id": "integration_rev_000003",
        "policy_mode": "stability_first",
        "integration_posture": selected_priority,
        "integration_confidence": 0.69,
        "selected_priority": selected_priority,
        "dominant_pressure_axis": "initiative_self",
        "highest_conflict_severity": conflict,
        "stabilize_weight": 0.34,
        "explore_weight": 0.66,
        "repair_weight": 0.41,
        "progress_weight": 0.59,
        "social_weight": 0.38,
        "boundary_weight": 0.29,
        "active_hint_axes": ["initiative_self", "social_self"],
        "tendency_status": "proposed",
    }


def _runtime_summary(
    *,
    owner_revision: int,
    initiative_pressure: float = 0.22,
    commitment_carryover_bias: float = 0.24,
    active_commitments_count: int = 0,
    blocked_commitments_count: int = 0,
    continuity_confidence: float = 0.82,
    reserve_level: str = "medium",
    delivery_status: str = "sent",
    idle_seconds: float = 1200.0,
    selfhood_priority: str = "grow",
    selfhood_conflict: str = "low",
    initiative_trigger: str = "bounded_followup",
    continuity_ref: str = "commitment:followup:001",
) -> dict:
    return {
        "initiative_self_context": _initiative_owner_projection(
            owner_revision=owner_revision,
            initiative_pressure=initiative_pressure,
            commitment_carryover_bias=commitment_carryover_bias,
            selected_priority="review",
            active_commitments_count=active_commitments_count,
            blocked_commitments_count=blocked_commitments_count,
            continuity_confidence=continuity_confidence,
        ),
        "initiative_context": _initiative_context(
            initiative_trigger=initiative_trigger,
            continuity_ref=continuity_ref,
            reserve_level=reserve_level,
            delivery_status=delivery_status,
            idle_seconds=idle_seconds,
            blocked_refs=(["commitment:blocked:001"] if blocked_commitments_count > 0 else []),
            pending_refs=([] if active_commitments_count == 0 and continuity_ref else [continuity_ref]),
        ),
        "selfhood_integration_context": _selfhood_integration_context(
            selected_priority=selfhood_priority,
            conflict=selfhood_conflict,
        ),
        "resource_budget_hint": {"reserve_level": reserve_level},
        "recent_delivery_outcome": {
            "status": delivery_status,
            "success": delivery_status not in {"failed", "blocked", "timeout", "error"},
        },
        "idle_window": {"idle_seconds": idle_seconds},
    }


def _run(runtime_summary: dict, *, event_id: str, raw_text: str = "continue"):
    return process_update_packet(
        ProtoSelfStateV2.empty(),
        _packet(event_id=event_id, runtime_summary=runtime_summary, raw_text=raw_text),
    )


def test_initiative_carryover_changes_bounded_followup_weighting():
    control = _run(
        _runtime_summary(
            owner_revision=1,
            active_commitments_count=0,
            initiative_pressure=0.22,
            commitment_carryover_bias=0.24,
            idle_seconds=90.0,
        ),
        event_id="evt_mvp20_causal_001_control",
    )
    intervention = _run(
        _runtime_summary(
            owner_revision=2,
            active_commitments_count=2,
            initiative_pressure=0.74,
            commitment_carryover_bias=0.83,
            idle_seconds=1800.0,
        ),
        event_id="evt_mvp20_causal_001_intervention",
    )

    assert control.initiative_self_delta == {}
    assert control.initiative_proposal_candidates == []
    assert control.policy_hint.get("initiative_priority") is None
    assert control.host_proactive_candidate is None
    assert intervention.initiative_proposal_candidates
    assert intervention.initiative_self_delta["selected_priority"] == "carry_forward"
    assert intervention.policy_hint["initiative_priority"] == "carry_forward"
    assert intervention.policy_hint["initiative_host_proactive_mode"] == "candidate"
    assert intervention.host_proactive_candidate is not None
    assert intervention.host_proactive_candidate["proposal_discipline"] == "proposal_only"
    assert intervention.host_proactive_candidate["behavioral_authority"] == "none"
    assert intervention.response_tendency is not None
    assert intervention.response_tendency.preferred_mode == "respond"


def test_delivery_failure_holds_initiative_under_guard():
    control = _run(
        _runtime_summary(
            owner_revision=3,
            active_commitments_count=2,
            initiative_pressure=0.74,
            commitment_carryover_bias=0.83,
            idle_seconds=1800.0,
            delivery_status="sent",
        ),
        event_id="evt_mvp20_causal_002_control",
    )
    intervention = _run(
        _runtime_summary(
            owner_revision=4,
            active_commitments_count=2,
            initiative_pressure=0.74,
            commitment_carryover_bias=0.83,
            idle_seconds=1800.0,
            delivery_status="blocked",
        ),
        event_id="evt_mvp20_causal_002_intervention",
    )

    assert control.policy_hint["initiative_priority"] == "carry_forward"
    assert control.policy_hint["initiative_host_proactive_mode"] == "candidate"
    assert control.host_proactive_candidate is not None
    assert intervention.initiative_proposal_candidates
    assert intervention.initiative_self_delta["selected_priority"] == "hold"
    assert intervention.policy_hint["initiative_priority"] == "hold"
    assert intervention.policy_hint["initiative_host_proactive_mode"] == "held"
    assert intervention.initiative_policy_hints["delivery_bias"] == "repair_review"
    assert intervention.host_proactive_candidate is None
    assert intervention.initiative_writeback_candidate is not None
    assert intervention.initiative_writeback_candidate["behavioral_authority"] == "none"
    assert intervention.response_tendency is not None
    assert intervention.response_tendency.preferred_mode == "defer"


def test_continuity_fragility_forces_review_bias():
    control = _run(
        _runtime_summary(
            owner_revision=5,
            active_commitments_count=1,
            initiative_pressure=0.62,
            commitment_carryover_bias=0.72,
            continuity_confidence=0.81,
            idle_seconds=1600.0,
        ),
        event_id="evt_mvp20_causal_003_control",
    )
    intervention = _run(
        _runtime_summary(
            owner_revision=6,
            active_commitments_count=1,
            initiative_pressure=0.62,
            commitment_carryover_bias=0.72,
            continuity_confidence=0.42,
            idle_seconds=1600.0,
        ),
        event_id="evt_mvp20_causal_003_intervention",
    )

    assert control.initiative_self_delta["selected_priority"] == "carry_forward"
    assert control.policy_hint["initiative_priority"] == "carry_forward"
    assert control.host_proactive_candidate is not None
    assert intervention.initiative_proposal_candidates
    assert intervention.initiative_self_delta["selected_priority"] == "review"
    assert intervention.initiative_policy_hints["continuity_mode"] == "fragile"
    assert intervention.policy_hint["initiative_priority"] == "review"
    assert intervention.policy_hint["initiative_host_proactive_mode"] == "held"
    assert intervention.host_proactive_candidate is None
    assert intervention.response_tendency is not None
    assert intervention.response_tendency.ask_needed is True


def test_selfhood_guard_overrides_initiative_growth_bias():
    control = _run(
        _runtime_summary(
            owner_revision=7,
            active_commitments_count=1,
            initiative_pressure=0.66,
            commitment_carryover_bias=0.77,
            idle_seconds=1500.0,
            selfhood_priority="grow",
            selfhood_conflict="low",
        ),
        event_id="evt_mvp20_causal_004_control",
    )
    intervention = _run(
        _runtime_summary(
            owner_revision=8,
            active_commitments_count=1,
            initiative_pressure=0.66,
            commitment_carryover_bias=0.77,
            idle_seconds=1500.0,
            selfhood_priority="guard",
            selfhood_conflict="high",
        ),
        event_id="evt_mvp20_causal_004_intervention",
    )

    assert control.initiative_self_delta["selected_priority"] == "carry_forward"
    assert control.policy_hint["initiative_priority"] == "carry_forward"
    assert control.host_proactive_candidate is not None
    assert intervention.initiative_proposal_candidates
    assert "integration_guard" in intervention.initiative_self_delta["surface_reasons"]
    assert "integration_conflict" in intervention.initiative_self_delta["surface_reasons"]
    assert intervention.initiative_self_delta["selected_priority"] == "hold"
    assert intervention.policy_hint["initiative_priority"] == "hold"
    assert intervention.host_proactive_candidate is None
    assert intervention.response_tendency is not None
    assert intervention.response_tendency.preferred_mode == "defer"


def test_text_only_trigger_change_has_no_structural_effect():
    control = _run(
        _runtime_summary(
            owner_revision=9,
            active_commitments_count=1,
            initiative_pressure=0.66,
            commitment_carryover_bias=0.77,
            idle_seconds=1500.0,
            initiative_trigger="bounded_followup",
            continuity_ref="commitment:followup:stable",
        ),
        event_id="evt_mvp20_causal_005_control",
        raw_text="continue with the same bounded followup",
    )
    intervention = _run(
        _runtime_summary(
            owner_revision=9,
            active_commitments_count=1,
            initiative_pressure=0.66,
            commitment_carryover_bias=0.77,
            idle_seconds=1500.0,
            initiative_trigger="same metrics, reworded trigger",
            continuity_ref="commitment:followup:stable",
        ),
        event_id="evt_mvp20_causal_005_intervention",
        raw_text="same bounded state, just phrased differently",
    )

    assert control.initiative_self_delta == intervention.initiative_self_delta
    assert control.commitment_execution_snapshot == intervention.commitment_execution_snapshot
    assert control.initiative_policy_hints == intervention.initiative_policy_hints
    assert control.policy_hint == intervention.policy_hint
    assert control.initiative_proposal_candidates == intervention.initiative_proposal_candidates
    assert control.host_proactive_candidate == intervention.host_proactive_candidate
    assert control.initiative_writeback_candidate == intervention.initiative_writeback_candidate
    assert control.response_tendency is not None
    assert intervention.response_tendency is not None
    assert control.response_tendency.to_dict() == intervention.response_tendency.to_dict()
