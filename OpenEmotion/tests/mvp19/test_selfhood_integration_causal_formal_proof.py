from __future__ import annotations

from typing import Any, Dict

from openemotion.proto_self_v2.kernel import process_update_packet
from openemotion.proto_self_v2.schemas import UpdateEventV2, UpdatePacketV2
from openemotion.proto_self_v2.state import ProtoSelfStateV2


def _packet(
    *,
    event_id: str,
    runtime_summary: dict | None = None,
    raw_text: str = "continue",
) -> UpdatePacketV2:
    return UpdatePacketV2(
        event_id=event_id,
        timestamp="2026-04-04T17:00:00",
        event=UpdateEventV2(
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="cross axis integration",
            raw_text=raw_text,
        ),
        conversation_summary={"session_id": "session:mvp19:causal", "turn_id": event_id},
        task_summary={"pending_tasks": 0, "blocked_tasks": 0},
        runtime_summary={
            "runtime": "runtime_v2",
            "state_scope": "agent_global",
            **(runtime_summary or {}),
        },
        safety_context={"risk_level": "low"},
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


def _reflective_context(*, pressure: float, unresolved_items: int) -> dict:
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
        "boundary_caution_max": 0.52 if repair_pressure else 0.28,
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
    reflective_pressure: float = 0.18,
    reflective_pending: int = 0,
    known_unknowns: int = 1,
    reserve_level: str = "medium",
    delivery_status: str = "sent",
    projection_priority: str = "review",
    projection_conflict: str = "none",
    note_suffix: str = "",
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
            known_unknowns=known_unknowns,
        ),
        "endogenous_drive_context": _drive_context(
            maintenance_priority=maintenance_priority,
            repair_bias=0.74 if social_repair else 0.18,
        ),
        "reflective_self_context": _reflective_context(
            pressure=reflective_pressure,
            unresolved_items=reflective_pending,
        ),
        "developmental_self_context": developmental_owner,
        "developmental_context": developmental_host,
        "social_self_context": social_owner,
        "social_context": {**social_host, "narrative_note": f"social{note_suffix}"},
        "embodied_self_context": embodied_owner,
        "environment_context": {**environment_host, "outcome_comment": f"embodied{note_suffix}"},
        "maintenance_context": {
            "replay_inconsistency": delivery_status in {"failed", "blocked"},
            "maintenance_debt_increment": 0.2 if delivery_status in {"failed", "blocked"} else 0.0,
            "debt_priority": 0.76 if reserve_level == "low" else 0.24,
            "continuity_signal": 0.64,
            "operator_note": f"maintenance{note_suffix}",
        },
        "resource_budget_hint": {
            "reserve_level": reserve_level,
            "reserve_ratio": 0.18 if reserve_level == "low" else 0.61,
        },
        "recent_delivery_outcome": {
            "status": delivery_status,
            "success": delivery_status not in {"failed", "blocked"},
        },
        "idle_window": {"idle_seconds": 920.0, "observation_note": f"idle{note_suffix}"},
    }


def _run(packet: UpdatePacketV2):
    return process_update_packet(ProtoSelfStateV2.empty(), packet)


def _structural_snapshot(output: Any) -> Dict[str, Any]:
    return {
        "selected_priority": output.cross_axis_priority_snapshot,
        "conflict": output.proposal_conflict_snapshot,
        "policy_hints": output.integrated_policy_hints,
        "delta": output.self_integration_delta,
        "policy_hint": output.policy_hint,
        "response_tendency": output.response_tendency.to_dict() if output.response_tendency else None,
        "writeback": output.self_integration_writeback_candidate,
    }


def test_low_self_confidence_and_high_embodied_pressure_override_growth_priority():
    control = _run(
        _packet(
            event_id="evt_mvp19_causal_001_control",
            runtime_summary=_runtime_summary(
                self_confidence=0.9,
                maintenance_priority=0.15,
                growth_pressure=0.86,
                continuity_gap=0.08,
                social_repair=False,
                embodied_resource_pressure=0.12,
                embodied_boundary_pressure=0.12,
                reserve_level="medium",
                delivery_status="sent",
                projection_priority="grow",
            ),
        )
    )
    intervention = _run(
        _packet(
            event_id="evt_mvp19_causal_001_intervention",
            runtime_summary=_runtime_summary(
                self_confidence=0.42,
                known_unknowns=4,
                maintenance_priority=0.82,
                growth_pressure=0.86,
                continuity_gap=0.3,
                social_repair=False,
                embodied_resource_pressure=0.82,
                embodied_boundary_pressure=0.78,
                reflective_pressure=0.82,
                reflective_pending=2,
                reserve_level="low",
                delivery_status="failed",
            ),
        )
    )

    assert control.cross_axis_priority_snapshot["selected_priority"] == "grow"
    assert control.proposal_conflict_snapshot["blocked_axes"] == []
    assert intervention.cross_axis_priority_snapshot["selected_priority"] == "review"
    assert intervention.proposal_conflict_snapshot["highest_severity"] == "high"
    assert intervention.proposal_conflict_snapshot["blocked_axes"] == ["developmental_self"]
    assert "wp8:self_model_low_confidence" in intervention.self_integration_delta["surface_reasons"]
    assert "wp13:embodied_pressure" in intervention.self_integration_delta["surface_reasons"]
    assert intervention.policy_hint["embodied_resource_bias"] == "conserve"
    assert intervention.policy_hint["embodied_boundary_bias"] == "cautious"
    assert intervention.response_tendency is not None
    assert intervention.response_tendency.preferred_mode == "defer"
    assert intervention.self_integration_writeback_candidate["behavioral_authority"] == "none"


def test_high_maintenance_and_reflective_pressure_shift_weighting_to_review():
    control = _run(
        _packet(
            event_id="evt_mvp19_causal_002_control",
            runtime_summary=_runtime_summary(
                self_confidence=0.78,
                maintenance_priority=0.22,
                growth_pressure=0.34,
                continuity_gap=0.08,
                social_repair=False,
                embodied_resource_pressure=0.16,
                embodied_boundary_pressure=0.14,
                reflective_pressure=0.18,
                reflective_pending=0,
                reserve_level="medium",
                delivery_status="sent",
                projection_priority="review",
            ),
        )
    )
    intervention = _run(
        _packet(
            event_id="evt_mvp19_causal_002_intervention",
            runtime_summary=_runtime_summary(
                self_confidence=0.78,
                maintenance_priority=0.85,
                growth_pressure=0.34,
                continuity_gap=0.08,
                social_repair=False,
                embodied_resource_pressure=0.16,
                embodied_boundary_pressure=0.14,
                reflective_pressure=0.82,
                reflective_pending=2,
                reserve_level="low",
                delivery_status="sent",
                projection_priority="review",
            ),
        )
    )

    assert control.cross_axis_priority_snapshot["selected_priority"] == "stabilize"
    assert control.policy_hint.get("reflection_bias") is None
    assert intervention.cross_axis_priority_snapshot["selected_priority"] == "review"
    assert intervention.policy_hint["reflection_bias"] == "elevated"
    assert intervention.policy_hint["uncertainty_bias"] == "elevated"
    assert "wp9:self_maintenance_pressure" in intervention.self_integration_delta["surface_reasons"]
    assert "wp10:reflective_modifier" in intervention.self_integration_delta["surface_reasons"]
    assert intervention.response_tendency is not None
    assert intervention.response_tendency.preferred_mode == "defer"
    assert intervention.self_integration_writeback_candidate["behavioral_authority"] == "none"


def test_social_repair_breach_surfaces_repair_priority_when_stability_is_bounded():
    control = _run(
        _packet(
            event_id="evt_mvp19_causal_003_control",
            runtime_summary=_runtime_summary(
                self_confidence=0.83,
                maintenance_priority=0.18,
                growth_pressure=0.3,
                continuity_gap=0.1,
                social_repair=False,
                embodied_resource_pressure=0.18,
                embodied_boundary_pressure=0.2,
                reserve_level="medium",
                delivery_status="sent",
                projection_priority="review",
            ),
        )
    )
    intervention = _run(
        _packet(
            event_id="evt_mvp19_causal_003_intervention",
            runtime_summary=_runtime_summary(
                self_confidence=0.83,
                maintenance_priority=0.18,
                growth_pressure=0.3,
                continuity_gap=0.1,
                social_repair=True,
                embodied_resource_pressure=0.18,
                embodied_boundary_pressure=0.2,
                reserve_level="medium",
                delivery_status="sent",
                projection_priority="review",
            ),
        )
    )

    assert control.cross_axis_priority_snapshot["selected_priority"] == "stabilize"
    assert "wp12:social_repair_pressure" not in control.self_integration_delta["surface_reasons"]
    assert intervention.cross_axis_priority_snapshot["selected_priority"] == "repair"
    assert intervention.integrated_policy_hints["dominant_pressure_axis"] == "social_self"
    assert "wp12:social_repair_pressure" in intervention.self_integration_delta["surface_reasons"]
    assert intervention.policy_hint["social_repair_bias"] == "elevated"
    assert intervention.policy_hint["social_commitment_guard"] == "strict"
    assert intervention.self_integration_writeback_candidate["behavioral_authority"] == "none"


def test_boundary_guard_blocks_social_repair_when_conflict_intensifies():
    control = _run(
        _packet(
            event_id="evt_mvp19_causal_004_control",
            runtime_summary=_runtime_summary(
                self_confidence=0.83,
                maintenance_priority=0.18,
                growth_pressure=0.3,
                continuity_gap=0.1,
                social_repair=True,
                embodied_resource_pressure=0.18,
                embodied_boundary_pressure=0.2,
                reserve_level="medium",
                delivery_status="sent",
                projection_priority="review",
            ),
        )
    )
    intervention = _run(
        _packet(
            event_id="evt_mvp19_causal_004_intervention",
            runtime_summary=_runtime_summary(
                self_confidence=0.83,
                maintenance_priority=0.18,
                growth_pressure=0.3,
                continuity_gap=0.1,
                social_repair=True,
                embodied_resource_pressure=0.18,
                embodied_boundary_pressure=0.82,
                reserve_level="medium",
                delivery_status="sent",
                projection_priority="review",
            ),
        )
    )

    assert control.cross_axis_priority_snapshot["selected_priority"] == "repair"
    assert control.proposal_conflict_snapshot["blocked_axes"] == []
    assert intervention.cross_axis_priority_snapshot["selected_priority"] == "guard"
    assert intervention.proposal_conflict_snapshot["highest_severity"] == "high"
    assert intervention.proposal_conflict_snapshot["blocked_axes"] == ["social_self"]
    assert "conflict:social_vs_boundary" in intervention.proposal_conflict_snapshot["unresolved_conflict_refs"]
    assert intervention.policy_hint["embodied_boundary_bias"] == "cautious"
    assert intervention.self_integration_writeback_candidate["behavioral_authority"] == "none"


def test_text_only_runtime_notes_do_not_change_structural_arbitration_outputs():
    control = _run(
        _packet(
            event_id="evt_mvp19_causal_005_control",
            runtime_summary=_runtime_summary(
                self_confidence=0.78,
                maintenance_priority=0.22,
                growth_pressure=0.34,
                continuity_gap=0.08,
                social_repair=False,
                embodied_resource_pressure=0.16,
                embodied_boundary_pressure=0.14,
                reserve_level="medium",
                delivery_status="sent",
                projection_priority="review",
                note_suffix=":alpha",
            ),
            raw_text="continue baseline",
        )
    )
    intervention = _run(
        _packet(
            event_id="evt_mvp19_causal_005_intervention",
            runtime_summary=_runtime_summary(
                self_confidence=0.78,
                maintenance_priority=0.22,
                growth_pressure=0.34,
                continuity_gap=0.08,
                social_repair=False,
                embodied_resource_pressure=0.16,
                embodied_boundary_pressure=0.14,
                reserve_level="medium",
                delivery_status="sent",
                projection_priority="review",
                note_suffix=":beta",
            ),
            raw_text="continue wording-only change",
        )
    )

    assert _structural_snapshot(control) == _structural_snapshot(intervention)
    assert control.self_integration_writeback_candidate is not None
    assert intervention.self_integration_writeback_candidate is not None
    assert control.self_integration_writeback_candidate["behavioral_authority"] == "none"
    assert intervention.self_integration_writeback_candidate["behavioral_authority"] == "none"
