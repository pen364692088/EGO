#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from openemotion.proto_self_v2.kernel import process_update_packet
from openemotion.proto_self_v2.schemas import UpdateEventV2, UpdatePacketV2
from openemotion.proto_self_v2.state import ProtoSelfStateV2


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_ROOT = ROOT / "OpenEmotion" / "artifacts" / "mvp19"


def _git_commit_short() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _packet(
    *,
    event_id: str,
    runtime_summary: dict | None = None,
    raw_text: str = "continue",
) -> UpdatePacketV2:
    return UpdatePacketV2(
        event_id=event_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
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


def _pair_results() -> List[Dict[str, Any]]:
    pairs: List[Dict[str, Any]] = []

    control = _run(
        _packet(
            event_id="pair1_control",
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
            event_id="pair1_intervention",
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
    pairs.append(
        {
            "pair_id": "stability_first_overrides_growth_under_low_confidence_and_embodied_pressure",
            "passed": control.cross_axis_priority_snapshot.get("selected_priority") == "grow"
            and control.proposal_conflict_snapshot.get("blocked_axes") == []
            and intervention.cross_axis_priority_snapshot.get("selected_priority") == "review"
            and intervention.proposal_conflict_snapshot.get("blocked_axes") == ["developmental_self"]
            and "wp8:self_model_low_confidence" in intervention.self_integration_delta.get("surface_reasons", [])
            and "wp13:embodied_pressure" in intervention.self_integration_delta.get("surface_reasons", [])
            and intervention.policy_hint.get("embodied_resource_bias") == "conserve"
            and intervention.policy_hint.get("embodied_boundary_bias") == "cautious"
            and intervention.response_tendency is not None
            and intervention.response_tendency.preferred_mode == "defer"
            and intervention.self_integration_writeback_candidate is not None
            and intervention.self_integration_writeback_candidate.get("behavioral_authority") == "none",
            "metric": {
                "control_selected_priority": control.cross_axis_priority_snapshot.get("selected_priority"),
                "intervention_selected_priority": intervention.cross_axis_priority_snapshot.get(
                    "selected_priority"
                ),
                "intervention_blocked_axes": intervention.proposal_conflict_snapshot.get("blocked_axes"),
                "intervention_surface_reasons": intervention.self_integration_delta.get(
                    "surface_reasons", []
                ),
            },
        }
    )

    control = _run(
        _packet(
            event_id="pair2_control",
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
            event_id="pair2_intervention",
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
    pairs.append(
        {
            "pair_id": "maintenance_and_reflective_pressure_shift_to_review",
            "passed": control.cross_axis_priority_snapshot.get("selected_priority") == "stabilize"
            and control.policy_hint.get("reflection_bias") is None
            and intervention.cross_axis_priority_snapshot.get("selected_priority") == "review"
            and intervention.policy_hint.get("reflection_bias") == "elevated"
            and intervention.policy_hint.get("uncertainty_bias") == "elevated"
            and "wp9:self_maintenance_pressure" in intervention.self_integration_delta.get(
                "surface_reasons", []
            )
            and "wp10:reflective_modifier" in intervention.self_integration_delta.get(
                "surface_reasons", []
            )
            and intervention.response_tendency is not None
            and intervention.response_tendency.preferred_mode == "defer"
            and intervention.self_integration_writeback_candidate is not None
            and intervention.self_integration_writeback_candidate.get("behavioral_authority") == "none",
            "metric": {
                "control_selected_priority": control.cross_axis_priority_snapshot.get("selected_priority"),
                "intervention_selected_priority": intervention.cross_axis_priority_snapshot.get(
                    "selected_priority"
                ),
                "control_reflection_bias": control.policy_hint.get("reflection_bias"),
                "intervention_reflection_bias": intervention.policy_hint.get("reflection_bias"),
                "intervention_surface_reasons": intervention.self_integration_delta.get(
                    "surface_reasons", []
                ),
            },
        }
    )

    control = _run(
        _packet(
            event_id="pair3_control",
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
            event_id="pair3_intervention",
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
    pairs.append(
        {
            "pair_id": "social_repair_breach_surfaces_repair_priority",
            "passed": control.cross_axis_priority_snapshot.get("selected_priority") == "stabilize"
            and "wp12:social_repair_pressure" not in control.self_integration_delta.get(
                "surface_reasons", []
            )
            and intervention.cross_axis_priority_snapshot.get("selected_priority") == "repair"
            and intervention.integrated_policy_hints.get("dominant_pressure_axis") == "social_self"
            and "wp12:social_repair_pressure" in intervention.self_integration_delta.get(
                "surface_reasons", []
            )
            and intervention.policy_hint.get("social_repair_bias") == "elevated"
            and intervention.policy_hint.get("social_commitment_guard") == "strict"
            and intervention.self_integration_writeback_candidate is not None
            and intervention.self_integration_writeback_candidate.get("behavioral_authority") == "none",
            "metric": {
                "control_selected_priority": control.cross_axis_priority_snapshot.get("selected_priority"),
                "intervention_selected_priority": intervention.cross_axis_priority_snapshot.get(
                    "selected_priority"
                ),
                "intervention_dominant_axis": intervention.integrated_policy_hints.get(
                    "dominant_pressure_axis"
                ),
                "intervention_surface_reasons": intervention.self_integration_delta.get(
                    "surface_reasons", []
                ),
            },
        }
    )

    control = _run(
        _packet(
            event_id="pair4_control",
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
            event_id="pair4_intervention",
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
    pairs.append(
        {
            "pair_id": "boundary_guard_blocks_social_repair_when_conflicted",
            "passed": control.cross_axis_priority_snapshot.get("selected_priority") == "repair"
            and control.proposal_conflict_snapshot.get("blocked_axes") == []
            and intervention.cross_axis_priority_snapshot.get("selected_priority") == "guard"
            and intervention.proposal_conflict_snapshot.get("highest_severity") == "high"
            and intervention.proposal_conflict_snapshot.get("blocked_axes") == ["social_self"]
            and "conflict:social_vs_boundary"
            in intervention.proposal_conflict_snapshot.get("unresolved_conflict_refs", [])
            and intervention.policy_hint.get("embodied_boundary_bias") == "cautious"
            and intervention.self_integration_writeback_candidate is not None
            and intervention.self_integration_writeback_candidate.get("behavioral_authority") == "none",
            "metric": {
                "control_selected_priority": control.cross_axis_priority_snapshot.get("selected_priority"),
                "intervention_selected_priority": intervention.cross_axis_priority_snapshot.get(
                    "selected_priority"
                ),
                "intervention_blocked_axes": intervention.proposal_conflict_snapshot.get("blocked_axes"),
                "intervention_conflicts": intervention.proposal_conflict_snapshot.get(
                    "unresolved_conflict_refs", []
                ),
            },
        }
    )

    control = _run(
        _packet(
            event_id="pair5_control",
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
            event_id="pair5_intervention",
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
    pairs.append(
        {
            "pair_id": "text_only_runtime_notes_do_not_change_structural_outputs",
            "passed": _structural_snapshot(control) == _structural_snapshot(intervention),
            "metric": {
                "control_selected_priority": control.cross_axis_priority_snapshot.get("selected_priority"),
                "intervention_selected_priority": intervention.cross_axis_priority_snapshot.get(
                    "selected_priority"
                ),
                "control_policy_hint": control.policy_hint,
                "intervention_policy_hint": intervention.policy_hint,
            },
        }
    )

    return pairs


def _write_artifacts(report: Dict[str, Any]) -> None:
    ARTIFACTS_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS_ROOT / "mvp19_causal_validation_current.json"
    md_path = ARTIFACTS_ROOT / "mvp19_causal_validation_current.md"

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    lines = [
        "# MVP19 Causal Validation",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- git_commit_short: `{report['git_commit_short']}`",
        f"- status: `{report['status']}`",
        f"- verification_level: `{report['verification_level']}`",
        f"- evidence_level: `{report['evidence_level']}`",
        f"- pair_count: `{report['pair_count']}`",
        f"- passed_count: `{report['passed_count']}`",
        "",
        "## Pairs",
        "",
    ]
    for pair in report["pairs"]:
        verdict = "pass" if pair["passed"] else "fail"
        lines.append(f"- `{pair['pair_id']}`: `{verdict}` {json.dumps(pair['metric'], ensure_ascii=True)}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    pairs = _pair_results()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit_short": _git_commit_short(),
        "status": "pass" if all(pair["passed"] for pair in pairs) else "fail",
        "verification_level": "V3",
        "evidence_level": "E3",
        "pair_count": len(pairs),
        "passed_count": sum(1 for pair in pairs if pair["passed"]),
        "pairs": pairs,
    }
    _write_artifacts(report)
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
