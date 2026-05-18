from openemotion.proto_self_v2.kernel import process_update_packet
from openemotion.proto_self_v2.schemas import UpdateEventV2, UpdatePacketV2
from openemotion.proto_self_v2.state import ProtoSelfStateV2


def _packet(*, event_id: str, runtime_summary: dict | None = None) -> UpdatePacketV2:
    return UpdatePacketV2(
        event_id=event_id,
        timestamp="2026-04-04T05:00:00",
        event=UpdateEventV2(
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="cross axis integration",
            raw_text="继续",
        ),
        conversation_summary={"session_id": "session:test", "turn_id": "turn_001"},
        task_summary={"pending_tasks": 0, "blocked_tasks": 0},
        runtime_summary={"runtime": "runtime_v2", "state_scope": "agent_global", **(runtime_summary or {})},
        safety_context={"risk_level": "low"},
    )


def _developmental_packet(*, event_id: str, runtime_summary: dict | None = None) -> UpdatePacketV2:
    return UpdatePacketV2(
        event_id=event_id,
        timestamp="2026-04-04T05:30:00",
        event=UpdateEventV2(
            actor="system",
            source="runtime",
            event_type="developmental_tick",
            user_intent=None,
            raw_text=None,
        ),
        conversation_summary={"session_id": "session:test", "turn_id": "turn_dev"},
        task_summary={"pending_tasks": 0, "blocked_tasks": 0},
        runtime_summary={
            "runtime": "runtime_v2",
            "state_scope": "agent_global",
            "developmental_mode": "shadow_observe",
            "observation_source": "direct_real",
            "developmental_trigger": "idle",
            "idle_seconds": 900.0,
            **(runtime_summary or {}),
        },
        safety_context={"risk_level": "low"},
        intervention_context={"developmental_input": {"state_snapshot": {}, "observation_refs": []}},
    )


def _selfhood_projection(*, selected_priority: str = "review", conflict: str = "medium") -> dict:
    return {
        "schema_version": "mvp19-owner-v1",
        "owner_revision": 3,
        "last_revision_id": "integration_rev_000003",
        "policy_mode": "stability_first",
        "integration_posture": selected_priority,
        "integration_confidence": 0.61,
        "selected_priority": selected_priority,
        "dominant_pressure_axis": "embodied_self",
        "highest_conflict_severity": conflict,
        "stabilize_weight": 0.66,
        "explore_weight": 0.34,
        "repair_weight": 0.58,
        "progress_weight": 0.42,
        "social_weight": 0.44,
        "boundary_weight": 0.56,
        "active_hint_axes": ["self_model", "embodied_self"],
        "tendency_status": "proposed",
        "direct_owner_state": {"should": "not_pass"},
    }


def _self_model_context(*, confidence: float, known_unknowns: int = 1) -> dict:
    return {
        "schema_version": "1.0.0",
        "identity_handle": "openemotion",
        "capabilities": [{"capability_id": "c1"}],
        "limitations": [{"limitation_id": "l1"}],
        "active_goals": [{"goal_id": "g1"}],
        "standing_commitments": [{"commitment_id": "sc1"}],
        "tool_authority_boundary": {"forbidden_tools": ["transport"]},
        "dependency_map": {"internal_modules": [{"name": "proto_self_v2"}]},
        "confidence_by_domain": {
            "identity": confidence,
            "planning": min(0.95, confidence + 0.08),
        },
        "known_unknowns": [{"id": f"unknown_{idx}"} for idx in range(known_unknowns)],
        "created_at": "2026-04-04T00:00:00Z",
        "last_modified_at": "2026-04-04T04:00:00Z",
        "modification_audit_trail": [],
        "active_tensions": ["legacy_should_not_pass"],
    }


def _drive_context(*, maintenance_priority: float, repair_bias: float = 0.18) -> dict:
    return {
        "schema_version": "mvp14-owner-v1",
        "owner_revision": 7,
        "last_revision_id": "drive_rev_000007",
        "active_drives": [
            {"drive_id": "conservation", "pressure": maintenance_priority},
            {"drive_id": "repair", "pressure": repair_bias},
        ],
        "homeostatic_signals": [{"signal_id": "continuity", "value": 0.62}],
        "maintenance_debt": [{"category": "resource", "amount": maintenance_priority}],
        "priority_snapshot": {
            "dominant_drive": "conservation",
            "bias_terms": {"conservation": maintenance_priority, "repair": repair_bias},
        },
        "summary": {"total_maintenance_debt": maintenance_priority},
        "self_maintenance_candidate": {
            "category": "self_maintenance",
            "priority": maintenance_priority,
            "status": {"should_maintain": maintenance_priority >= 0.6},
        },
    }


def _reflective_context(*, pressure: float = 0.24, unresolved_items: int = 1) -> dict:
    return {
        "schema_version": "mvp15-owner-v1",
        "owner_revision": 5,
        "last_revision_id": "reflective_rev_000005",
        "reflection_pressure": pressure,
        "pending_reflections": unresolved_items,
        "unresolved_items": unresolved_items,
        "proposal_candidates": 1 if pressure >= 0.3 else 0,
        "top_target_ids": ["target:reflection"],
    }


def _developmental_context(*, growth_pressure: float, continuity_gap: float) -> tuple[dict, dict]:
    owner_context = {
        "schema_version": "mvp16-owner-v1",
        "owner_revision": 4,
        "last_revision_id": "developmental_rev_000004",
        "continuity_score": round(1.0 - continuity_gap, 3),
        "growth_pressure": growth_pressure,
        "stagnation_signal": 0.22,
        "identity_preservation_confidence": 0.88,
        "developmental_risk_index": 0.26,
        "trajectory_summary": {"current_arc": "bounded_growth"},
        "promotion_queue_size": 1 if growth_pressure >= 0.7 else 0,
        "recent_proposal_count": 1 if growth_pressure >= 0.7 else 0,
    }
    host_context = {
        "source": "runtime_v2",
        "continuity_gap": continuity_gap,
        "growth_pressure_hint": growth_pressure,
        "stagnation_signal_hint": 0.2,
        "identity_guard": "strict",
        "replay_debt": 0.0,
        "promotion_budget": "controlled_axis",
        "drift_markers": [],
    }
    return owner_context, host_context


def _social_context(*, repair_pressure: bool) -> tuple[dict, dict]:
    owner_context = {
        "schema_version": "mvp17-owner-v1",
        "owner_revision": 4,
        "last_revision_id": "social_rev_000004",
        "active_relations_count": 2,
        "trust_signal_max": 0.72,
        "open_commitment_count": 1,
        "breached_commitment_count": 1 if repair_pressure else 0,
        "pending_repair_count": 1 if repair_pressure else 0,
        "boundary_caution_max": 0.28 if not repair_pressure else 0.52,
        "recent_counterpart_ids": ["telegram:8420019401"],
    }
    host_context = {
        "source": "runtime_v2",
        "counterpart_id": "telegram:8420019401",
        "relationship_event": "commitment_breach" if repair_pressure else "stable_followup",
        "relationship_continuity": "strained" if repair_pressure else "stable",
        "trust_drift": -0.24 if repair_pressure else -0.02,
        "commitment_event": "breach" if repair_pressure else "none",
        "commitment_breach": repair_pressure,
        "repair_outcome": "pending" if repair_pressure else "resolved",
        "unresolved_repair": repair_pressure,
        "boundary_signal": "cautious" if repair_pressure else "open",
        "promotion_budget": "review_only",
    }
    return owner_context, host_context


def _embodied_context(*, resource_pressure: float, boundary_pressure: float) -> tuple[dict, dict]:
    owner_context = {
        "schema_version": "mvp18-owner-v1",
        "owner_revision": 5,
        "last_revision_id": "embodied_rev_000005",
        "resource_slack": round(max(0.0, 1.0 - resource_pressure), 3),
        "perceived_load": resource_pressure,
        "active_coupling_count": 2,
        "max_resource_pressure": resource_pressure,
        "min_resource_slack": round(max(0.0, 1.0 - resource_pressure - 0.08), 3),
        "max_boundary_pressure": boundary_pressure,
        "recent_consequence_count": 1 if resource_pressure >= 0.6 else 0,
        "stabilization_proposal_count": 1 if boundary_pressure >= 0.45 else 0,
        "self_world_guard_bias": boundary_pressure,
    }
    host_context = {
        "source": "runtime_v2",
        "action_ref": "delivery:telegram:turn_001",
        "coupling_event": "delivery_feedback",
        "outcome_type": "failure" if resource_pressure >= 0.6 else "success",
        "outcome_summary": "delivery timeout" if resource_pressure >= 0.6 else "delivery stable",
        "resource_pressure_hint": resource_pressure,
        "slack_hint": round(max(0.0, 1.0 - resource_pressure - 0.1), 3),
        "boundary_signal": "guarded" if boundary_pressure >= 0.45 else "open",
        "boundary_pressure_hint": boundary_pressure,
        "stabilization_needed": resource_pressure >= 0.6 or boundary_pressure >= 0.45,
        "promotion_budget": "controlled_axis",
    }
    return owner_context, host_context


def _runtime_summary(
    *,
    self_confidence: float,
    maintenance_priority: float,
    growth_pressure: float,
    continuity_gap: float,
    social_repair: bool,
    embodied_resource_pressure: float,
    embodied_boundary_pressure: float,
    reserve_level: str = "medium",
    delivery_status: str = "sent",
    projection_priority: str = "review",
    projection_conflict: str = "medium",
) -> dict:
    developmental_owner, developmental_host = _developmental_context(
        growth_pressure=growth_pressure,
        continuity_gap=continuity_gap,
    )
    social_owner, social_host = _social_context(repair_pressure=social_repair)
    embodied_owner, environment_host = _embodied_context(
        resource_pressure=embodied_resource_pressure,
        boundary_pressure=embodied_boundary_pressure,
    )
    return {
        "selfhood_integration_context": _selfhood_projection(
            selected_priority=projection_priority,
            conflict=projection_conflict,
        ),
        "self_model_context": _self_model_context(
            confidence=self_confidence,
            known_unknowns=3 if self_confidence < 0.55 else 1,
        ),
        "endogenous_drive_context": _drive_context(
            maintenance_priority=maintenance_priority,
            repair_bias=0.74 if social_repair else 0.18,
        ),
        "reflective_self_context": _reflective_context(
            pressure=0.41 if self_confidence < 0.55 else 0.18,
            unresolved_items=1 if self_confidence < 0.55 else 0,
        ),
        "developmental_self_context": developmental_owner,
        "developmental_context": developmental_host,
        "social_self_context": social_owner,
        "social_context": social_host,
        "embodied_self_context": embodied_owner,
        "environment_context": environment_host,
        "maintenance_context": {
            "replay_inconsistency": delivery_status in {"failed", "blocked"},
            "maintenance_debt_increment": 0.2 if delivery_status in {"failed", "blocked"} else 0.0,
            "debt_priority": 0.76 if reserve_level == "low" else 0.24,
            "continuity_signal": 0.64,
        },
        "resource_budget_hint": {
            "reserve_level": reserve_level,
            "reserve_ratio": 0.18 if reserve_level == "low" else 0.61,
        },
        "recent_delivery_outcome": {
            "status": delivery_status,
            "success": delivery_status not in {"failed", "blocked"},
        },
        "idle_window": {"idle_seconds": 920.0},
    }


def test_runtime_selfhood_integration_context_is_reflected_in_trace_summary():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_selfhood_ctx_001",
        runtime_summary=_runtime_summary(
            self_confidence=0.43,
            maintenance_priority=0.81,
            growth_pressure=0.82,
            continuity_gap=0.34,
            social_repair=True,
            embodied_resource_pressure=0.76,
            embodied_boundary_pressure=0.83,
            reserve_level="low",
            delivery_status="failed",
        ),
    )

    output = process_update_packet(state, packet)

    summary = output.trace_payload["constraint_summary"]["selfhood_integration_context"]
    assert summary["present"] is True
    assert summary["contract_version"] == "mvp19.selfhood_integration_contract.v1"
    assert summary["projection_field"] == "runtime_summary.selfhood_integration_context"
    assert summary["runtime_local_projection_field"] == "proto_self_v2.state.selfhood_integration"
    assert summary["projection_owner_revision"] == 3
    assert summary["upstream_axis_count"] == 6
    assert output.confidence_meta["selfhood_integration_context_present"] is True
    assert output.confidence_meta["selfhood_integration_owner_revision"] == 3
    assert output.trace_payload["retrieval_summary"]["selfhood_integration_context_present"] is True


def test_runtime_selfhood_integration_emits_stability_first_proposal_only_outputs():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_selfhood_ctx_002",
        runtime_summary=_runtime_summary(
            self_confidence=0.43,
            maintenance_priority=0.81,
            growth_pressure=0.82,
            continuity_gap=0.34,
            social_repair=True,
            embodied_resource_pressure=0.76,
            embodied_boundary_pressure=0.83,
            reserve_level="low",
            delivery_status="failed",
        ),
    )

    output = process_update_packet(state, packet)

    assert output.cross_axis_priority_snapshot["selected_priority"] in {
        "stabilize",
        "conserve",
        "guard",
        "review",
    }
    assert output.self_integration_writeback_candidate is not None
    assert output.self_integration_writeback_candidate["proposal_discipline"] == "proposal_only"
    assert output.self_integration_writeback_candidate["behavioral_authority"] == "none"
    assert output.self_integration_writeback_candidate["required_gate"] == "self_integration_writeback_gate"
    assert output.integrated_tendency_proposal is not None
    assert output.integrated_tendency_proposal["effect_scope"] == "proposal_only"
    assert output.integrated_tendency_proposal["behavioral_authority"] == "none"
    assert output.integrated_tendency_proposal["required_gate"] == "self_integration_writeback_gate"
    assert output.proposal_conflict_snapshot["highest_severity"] in {"medium", "high"}
    assert output.policy_hint["self_integration_required_gate"] == "self_integration_writeback_gate"
    assert (
        output.trace_payload["selfhood_integration_context"]["selected_priority"]
        == output.cross_axis_priority_snapshot["selected_priority"]
    )


def test_runtime_selfhood_integration_does_not_promote_second_truth_source_fields():
    state = ProtoSelfStateV2.empty()
    runtime_summary = _runtime_summary(
        self_confidence=0.52,
        maintenance_priority=0.62,
        growth_pressure=0.66,
        continuity_gap=0.28,
        social_repair=True,
        embodied_resource_pressure=0.58,
        embodied_boundary_pressure=0.51,
        reserve_level="low",
        delivery_status="blocked",
    )
    packet = _packet(event_id="evt_selfhood_ctx_003", runtime_summary=runtime_summary)

    output = process_update_packet(state, packet)

    assert "direct_owner_state" not in output.trace_payload["selfhood_integration_context"]
    assert "active_tensions" not in output.trace_payload["constraint_summary"]["self_model_context"]
    assert "axis_arbitration_hints" not in output.trace_payload["selfhood_integration_context"]
    assert output.axis_arbitration_hints["self_model"]["advisory_only"] is True
    assert output.axis_arbitration_hints["embodied_self"]["guardrail_summary"] == (
        "advisory_only_no_upstream_owner_mutation"
    )


def test_social_repair_priority_surfaces_when_stability_pressure_is_bounded():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_selfhood_ctx_004",
        runtime_summary=_runtime_summary(
            self_confidence=0.82,
            maintenance_priority=0.18,
            growth_pressure=0.32,
            continuity_gap=0.12,
            social_repair=True,
            embodied_resource_pressure=0.18,
            embodied_boundary_pressure=0.2,
            reserve_level="medium",
            delivery_status="sent",
        ),
    )

    output = process_update_packet(state, packet)

    assert output.cross_axis_priority_snapshot["selected_priority"] == "repair"
    assert output.integrated_policy_hints["selected_priority"] == "repair"
    assert output.axis_arbitration_hints["social_self"]["advisory_only"] is True


def test_growth_priority_surfaces_when_other_axes_are_calm():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_selfhood_ctx_005",
        runtime_summary=_runtime_summary(
            self_confidence=0.88,
            maintenance_priority=0.16,
            growth_pressure=0.84,
            continuity_gap=0.08,
            social_repair=False,
            embodied_resource_pressure=0.12,
            embodied_boundary_pressure=0.14,
            reserve_level="medium",
            delivery_status="sent",
            projection_priority="grow",
            projection_conflict="none",
        ),
    )

    output = process_update_packet(state, packet)

    assert output.cross_axis_priority_snapshot["selected_priority"] == "grow"
    assert output.integrated_tendency_proposal["priority_mode"] == "grow"
    assert output.proposal_conflict_snapshot["conflict_count"] == 0


def test_developmental_tick_keeps_selfhood_outputs_proposal_only():
    state = ProtoSelfStateV2.empty()
    packet = _developmental_packet(
        event_id="evt_selfhood_ctx_dev_001",
        runtime_summary=_runtime_summary(
            self_confidence=0.43,
            maintenance_priority=0.81,
            growth_pressure=0.82,
            continuity_gap=0.34,
            social_repair=True,
            embodied_resource_pressure=0.76,
            embodied_boundary_pressure=0.83,
            reserve_level="low",
            delivery_status="failed",
        ),
    )

    output = process_update_packet(state, packet)

    assert output.self_integration_writeback_candidate is not None
    assert output.self_integration_writeback_candidate["proposal_discipline"] == "proposal_only"
    assert output.self_integration_writeback_candidate["behavioral_authority"] == "none"
    assert output.trace_payload["selfhood_integration_context"]["highest_conflict_severity"] in {
        "medium",
        "high",
    }
