from __future__ import annotations

from typing import Any, Dict, Optional

from openemotion.proto_self.schemas import ResponseTendency
from openemotion.proto_self_v2.developmental_self_context import (
    extract_runtime_developmental_context,
    extract_runtime_developmental_self_context,
)
from openemotion.proto_self_v2.embodied_self_context import (
    extract_runtime_embodied_self_context,
    extract_runtime_environment_context,
)
from openemotion.proto_self_v2.endogenous_drive_context import (
    extract_runtime_endogenous_drive_context,
)
from openemotion.proto_self_v2.reflective_self_context import (
    extract_runtime_reflective_self_context,
)
from openemotion.proto_self_v2.self_model_context import extract_runtime_self_model_context
from openemotion.proto_self_v2.social_self_context import (
    extract_runtime_social_context,
    extract_runtime_social_self_context,
)
from openemotion.selfhood_integration import (
    REQUIRED_WRITEBACK_GATE,
    RUNTIME_LOCAL_PROJECTION_FIELD,
    RUNTIME_LOCAL_PROJECTION_SEMANTICS,
)


PROJECTION_FIELD = "runtime_summary.selfhood_integration_context"
CONTRACT_VERSION = "mvp19.selfhood_integration_contract.v1"
POLICY_MODE = "stability_first"

BOUNDED_CONTEXT_FIELDS = (
    "schema_version",
    "owner_revision",
    "last_revision_id",
    "policy_mode",
    "integration_posture",
    "integration_confidence",
    "selected_priority",
    "dominant_pressure_axis",
    "highest_conflict_severity",
    "stabilize_weight",
    "explore_weight",
    "repair_weight",
    "progress_weight",
    "social_weight",
    "boundary_weight",
    "active_hint_axes",
    "tendency_status",
)

PRIORITY_ORDER = ("stabilize", "conserve", "guard", "review", "repair", "grow")
SEVERITY_ORDER = ("none", "low", "medium", "high")


def _clamp(value: Any, lower: float = 0.0, upper: float = 1.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = lower
    return max(lower, min(upper, numeric))


def _severity_rank(level: str) -> int:
    lowered = str(level or "none").strip().lower()
    if lowered in SEVERITY_ORDER:
        return SEVERITY_ORDER.index(lowered)
    return 0


def _select_priority(weights: Dict[str, float]) -> str:
    return max(
        PRIORITY_ORDER,
        key=lambda priority: (weights.get(priority, 0.0), -PRIORITY_ORDER.index(priority)),
    )


def _resolve_self_model_confidence(context: Dict[str, Any]) -> float:
    confidence_by_domain = dict(context.get("confidence_by_domain") or {})
    values = [_clamp(value) for value in confidence_by_domain.values()]
    if not values:
        return 1.0
    return min(values)


def _upstream_axes_present(runtime_summary: Dict[str, Any]) -> list[str]:
    axes = []
    if extract_runtime_self_model_context(runtime_summary):
        axes.append("self_model")
    if extract_runtime_endogenous_drive_context(runtime_summary):
        axes.append("endogenous_drives")
    if extract_runtime_reflective_self_context(runtime_summary):
        axes.append("reflective_self")
    if extract_runtime_developmental_self_context(runtime_summary) or extract_runtime_developmental_context(
        runtime_summary
    ):
        axes.append("developmental_self")
    if extract_runtime_social_self_context(runtime_summary) or extract_runtime_social_context(runtime_summary):
        axes.append("social_self")
    if extract_runtime_embodied_self_context(runtime_summary) or extract_runtime_environment_context(
        runtime_summary
    ):
        axes.append("embodied_self")
    return axes


def extract_runtime_selfhood_integration_context(
    runtime_summary: Dict[str, Any] | None,
) -> Dict[str, Any]:
    raw = dict((runtime_summary or {}).get("selfhood_integration_context") or {})
    if not raw:
        return {}
    return {key: raw[key] for key in BOUNDED_CONTEXT_FIELDS if key in raw}


def summarize_runtime_selfhood_integration_context(
    runtime_summary: Dict[str, Any] | None,
) -> Dict[str, Any]:
    runtime = dict(runtime_summary or {})
    projection = extract_runtime_selfhood_integration_context(runtime)
    self_model_context = extract_runtime_self_model_context(runtime)
    drive_context = extract_runtime_endogenous_drive_context(runtime)
    reflective_context = extract_runtime_reflective_self_context(runtime)
    developmental_context = extract_runtime_developmental_self_context(runtime)
    developmental_host_context = extract_runtime_developmental_context(runtime)
    social_context = extract_runtime_social_self_context(runtime)
    social_host_context = extract_runtime_social_context(runtime)
    embodied_context = extract_runtime_embodied_self_context(runtime)
    environment_context = extract_runtime_environment_context(runtime)

    growth_pressure = max(
        _clamp(developmental_context.get("growth_pressure")),
        _clamp(developmental_host_context.get("growth_pressure_hint")),
    )
    social_repair_pressure = max(
        0.78 if social_host_context.get("commitment_breach") else 0.0,
        0.72 if social_host_context.get("unresolved_repair") else 0.0,
        _clamp(abs(min(float(social_host_context.get("trust_drift") or 0.0), 0.0))),
        0.7 if int(social_context.get("pending_repair_count") or 0) > 0 else 0.0,
    )
    resource_pressure = max(
        _clamp(embodied_context.get("max_resource_pressure")),
        _clamp(environment_context.get("resource_pressure_hint")),
    )
    boundary_pressure = max(
        _clamp(embodied_context.get("max_boundary_pressure")),
        _clamp(environment_context.get("boundary_pressure_hint")),
    )
    maintenance_candidate = drive_context.get("self_maintenance_candidate") or {}
    maintenance_pressure = max(
        _clamp((maintenance_candidate or {}).get("priority")),
        0.72 if (runtime.get("resource_budget_hint") or {}).get("reserve_level") == "low" else 0.0,
        _clamp((runtime.get("maintenance_context") or {}).get("debt_priority")),
    )

    return {
        "present": bool(projection),
        "contract_version": CONTRACT_VERSION,
        "projection_field": PROJECTION_FIELD,
        "projection_semantics": RUNTIME_LOCAL_PROJECTION_SEMANTICS,
        "runtime_local_projection_field": RUNTIME_LOCAL_PROJECTION_FIELD,
        "schema_version": projection.get("schema_version"),
        "projection_owner_revision": projection.get("owner_revision"),
        "projection_last_revision_id": projection.get("last_revision_id"),
        "projection_selected_priority": str(projection.get("selected_priority") or ""),
        "projection_highest_conflict_severity": str(
            projection.get("highest_conflict_severity") or "none"
        ),
        "projection_active_hint_axes": list(projection.get("active_hint_axes") or []),
        "tendency_status": str(projection.get("tendency_status") or ""),
        "upstream_axes": _upstream_axes_present(runtime),
        "upstream_axis_count": len(_upstream_axes_present(runtime)),
        "self_model_confidence_floor": round(_resolve_self_model_confidence(self_model_context), 3),
        "maintenance_pressure": round(maintenance_pressure, 3),
        "reflective_pressure": round(_clamp(reflective_context.get("reflection_pressure")), 3),
        "growth_pressure": round(growth_pressure, 3),
        "social_repair_pressure": round(social_repair_pressure, 3),
        "resource_pressure": round(resource_pressure, 3),
        "boundary_pressure": round(boundary_pressure, 3),
    }


def derive_selfhood_integration_outputs(
    runtime_summary: Dict[str, Any] | None,
    *,
    endogenous_drive_outputs: Dict[str, Any],
    reflective_outputs: Dict[str, Any],
    developmental_outputs: Dict[str, Any],
    social_outputs: Dict[str, Any],
    embodied_outputs: Dict[str, Any],
) -> Dict[str, Any]:
    runtime = dict(runtime_summary or {})
    projection = extract_runtime_selfhood_integration_context(runtime)
    self_model_context = extract_runtime_self_model_context(runtime)
    maintenance_context = dict(runtime.get("maintenance_context") or {})
    resource_budget_hint = dict(runtime.get("resource_budget_hint") or {})
    recent_delivery_outcome = dict(runtime.get("recent_delivery_outcome") or {})
    idle_window = dict(runtime.get("idle_window") or {})
    context_summary = summarize_runtime_selfhood_integration_context(runtime)

    if not context_summary["present"]:
        return {
            "selfhood_integration_context": {},
            "self_integration_delta": {},
            "cross_axis_priority_snapshot": {},
            "proposal_conflict_snapshot": {},
            "integrated_policy_hints": {},
            "integrated_tendency_proposal": None,
            "axis_arbitration_hints": {},
            "integration_audit_entries": [],
            "self_integration_writeback_candidate": None,
            "policy_hint_patch": {},
            "response_tendency": None,
        }

    self_model_confidence = _resolve_self_model_confidence(self_model_context)
    known_unknown_count = len(self_model_context.get("known_unknowns") or [])
    self_model_pressure = max(1.0 - self_model_confidence, min(1.0, known_unknown_count / 4.0))

    priority_snapshot = dict(endogenous_drive_outputs.get("priority_snapshot") or {})
    candidate_bias_terms = dict(endogenous_drive_outputs.get("candidate_bias_terms") or {})
    self_maintenance_candidate = endogenous_drive_outputs.get("self_maintenance_candidate") or {}
    maintenance_pressure = max(
        _clamp(self_maintenance_candidate.get("priority")),
        _clamp(priority_snapshot.get("maintenance_pressure")),
        _clamp((priority_snapshot.get("summary") or {}).get("maintenance_pressure")),
        0.72 if resource_budget_hint.get("reserve_level") == "low" else 0.0,
        _clamp(maintenance_context.get("debt_priority")),
        _clamp(candidate_bias_terms.get("conservation")),
    )

    resource_boundary_snapshot = dict(embodied_outputs.get("resource_boundary_snapshot") or {})
    embodied_policy_hints = dict(embodied_outputs.get("embodied_policy_hints") or {})
    embodied_resource_pressure = max(
        _clamp(resource_boundary_snapshot.get("max_resource_pressure")),
        0.72 if embodied_policy_hints.get("resource_bias") == "conserve" else 0.0,
    )
    embodied_boundary_pressure = max(
        _clamp(resource_boundary_snapshot.get("max_boundary_pressure")),
        0.74 if embodied_policy_hints.get("boundary_mode") in {"guarded", "repair_only"} else 0.0,
    )

    trust_commitment_snapshot = dict(social_outputs.get("trust_commitment_snapshot") or {})
    social_policy_hints = dict(social_outputs.get("social_policy_hints") or {})
    social_repair_pressure = max(
        _clamp(candidate_bias_terms.get("repair")),
        0.78 if social_policy_hints.get("repair_bias") == "elevated" else 0.0,
        0.72 if social_policy_hints.get("commitment_guard") == "strict" else 0.0,
        _clamp(abs(min(float(trust_commitment_snapshot.get("trust_drift") or 0.0), 0.0))),
        0.68 if int(trust_commitment_snapshot.get("pending_repair_count") or 0) > 0 else 0.0,
    )

    developmental_snapshot = dict(developmental_outputs.get("developmental_continuity_snapshot") or {})
    developmental_priority_hints = dict(developmental_outputs.get("developmental_priority_hints") or {})
    growth_pressure = max(
        _clamp(developmental_snapshot.get("growth_pressure")),
        0.76 if developmental_priority_hints.get("growth_priority") == "elevated" else 0.0,
    )
    continuity_gap = _clamp(developmental_snapshot.get("continuity_gap"))

    confidence_adjustment_hints = dict(reflective_outputs.get("confidence_adjustment_hints") or {})
    maintenance_priority_hints = dict(reflective_outputs.get("maintenance_priority_hints") or {})
    reflective_modifier = max(
        _clamp(confidence_adjustment_hints.get("pressure")) * 0.2,
        0.18 if maintenance_priority_hints.get("reflection_followup_priority") == "elevated" else 0.0,
        0.14 if reflective_outputs.get("revision_proposal_candidates") else 0.0,
    )
    reflective_pressure = _clamp(context_summary["reflective_pressure"])

    delivery_failed = recent_delivery_outcome.get("success") is False or recent_delivery_outcome.get(
        "status"
    ) in {"failed", "blocked"}
    replay_inconsistency = bool(maintenance_context.get("replay_inconsistency"))
    low_self_confidence = self_model_confidence < 0.55 or known_unknown_count >= 3
    stability_pressure_active = (
        low_self_confidence
        or maintenance_pressure >= 0.6
        or embodied_resource_pressure >= 0.6
        or embodied_boundary_pressure >= 0.45
        or delivery_failed
        or replay_inconsistency
    )

    weights = {
        "stabilize": 0.32,
        "conserve": 0.3,
        "guard": 0.28,
        "review": 0.26,
        "repair": 0.22,
        "grow": 0.18,
    }
    weights["stabilize"] += self_model_pressure * 0.32
    weights["review"] += self_model_pressure * 0.28
    weights["conserve"] += maintenance_pressure * 0.34
    weights["stabilize"] += maintenance_pressure * 0.16
    weights["conserve"] += embodied_resource_pressure * 0.28
    weights["guard"] += embodied_resource_pressure * 0.1
    weights["guard"] += embodied_boundary_pressure * 0.4
    weights["stabilize"] += embodied_boundary_pressure * 0.12
    weights["repair"] += social_repair_pressure * 0.42
    weights["review"] += social_repair_pressure * 0.08
    growth_multiplier = 0.12 if stability_pressure_active else 0.38
    weights["grow"] += growth_pressure * growth_multiplier
    weights["review"] += reflective_modifier + (reflective_pressure * 0.1)
    if continuity_gap >= 0.25:
        weights["review"] += continuity_gap * 0.18
        weights["grow"] += continuity_gap * 0.05
    if delivery_failed:
        weights["review"] += 0.14
        weights["conserve"] += 0.08
    if replay_inconsistency:
        weights["review"] += 0.16
        weights["stabilize"] += 0.06
    if projection:
        weights["review"] += 0.04
        if str(projection.get("selected_priority") or "") in {"stabilize", "conserve", "guard", "review"}:
            weights["stabilize"] += 0.03
        if _severity_rank(str(projection.get("highest_conflict_severity") or "none")) >= 2:
            weights["review"] += 0.06

    bounded_weights = {priority: round(_clamp(value), 3) for priority, value in weights.items()}
    selected_priority = _select_priority(bounded_weights)

    axis_scores = {
        "self_model": round(self_model_pressure, 3),
        "endogenous_drives": round(max(maintenance_pressure, _clamp(candidate_bias_terms.get("repair"))), 3),
        "reflective_self": round(max(reflective_modifier, reflective_pressure), 3),
        "developmental_self": round(max(growth_pressure, continuity_gap), 3),
        "social_self": round(social_repair_pressure, 3),
        "embodied_self": round(max(embodied_resource_pressure, embodied_boundary_pressure), 3),
    }
    active_axes = [axis for axis in _upstream_axes_present(runtime) if axis_scores.get(axis, 0.0) > 0.0]
    dominant_pressure_axis = max(axis_scores, key=axis_scores.get)

    conflicts = []
    blocked_axes = set()
    if growth_pressure >= 0.7 and stability_pressure_active:
        conflicts.append("growth_vs_stability")
        blocked_axes.add("developmental_self")
    if social_repair_pressure >= 0.55 and embodied_boundary_pressure >= 0.45:
        conflicts.append("social_vs_boundary")
        blocked_axes.add("social_self")
    if social_repair_pressure >= 0.6 and maintenance_pressure >= 0.6:
        conflicts.append("repair_vs_conserve")
        blocked_axes.add("social_self")
    if reflective_modifier >= 0.16 and growth_pressure >= 0.7:
        conflicts.append("review_vs_growth")
    projection_selected_priority = str(projection.get("selected_priority") or "")
    if projection_selected_priority and projection_selected_priority != selected_priority:
        conflicts.append("projection_priority_drift")

    conflict_count = len(conflicts)
    highest_conflict_severity = "none"
    if conflict_count == 1:
        highest_conflict_severity = "low"
    elif conflict_count == 2:
        highest_conflict_severity = "medium"
    elif conflict_count >= 3:
        highest_conflict_severity = "high"
    if max(axis_scores.values()) >= 0.8 and conflict_count >= 2:
        highest_conflict_severity = "high"

    source_refs = []
    if low_self_confidence:
        source_refs.append("wp8:self_model_low_confidence")
    if maintenance_pressure >= 0.6:
        source_refs.append("wp9:self_maintenance_pressure")
    if reflective_modifier > 0.0:
        source_refs.append("wp10:reflective_modifier")
    if growth_pressure >= 0.6:
        source_refs.append("wp11:developmental_growth_pressure")
    if social_repair_pressure >= 0.55:
        source_refs.append("wp12:social_repair_pressure")
    if max(embodied_resource_pressure, embodied_boundary_pressure) >= 0.45:
        source_refs.append("wp13:embodied_pressure")
    if projection:
        source_refs.append("wp14:selfhood_projection")
    if replay_inconsistency:
        source_refs.append("host:maintenance_context")
    if delivery_failed:
        source_refs.append("host:recent_delivery_outcome")

    stable_priority = selected_priority in {"stabilize", "conserve", "guard", "review"}
    stability_bias = (
        bounded_weights["stabilize"]
        + bounded_weights["conserve"]
        + bounded_weights["guard"]
        + bounded_weights["review"]
    ) / max(sum(bounded_weights.values()), 1e-6)
    integration_confidence = _clamp(
        0.82
        - (0.08 * conflict_count)
        - (0.18 * max(0.0, 0.55 - self_model_confidence))
        - (0.06 if delivery_failed else 0.0)
        - (0.05 if replay_inconsistency else 0.0)
        + (0.04 if projection else 0.0)
    )
    priority_reason = {
        "stabilize": "phase1 stability-first favors stabilization while confidence or maintenance pressure remains active",
        "conserve": "phase1 stability-first favors reserve protection before broader cross-axis movement",
        "guard": "phase1 stability-first favors boundary protection before social or growth expansion",
        "review": "phase1 stability-first holds proposals in review while conflicts or uncertainty remain active",
        "repair": "repair pressure outranks growth once stability-first guardrails remain bounded",
        "grow": "growth pressure is allowed only after stability, repair, and boundary pressures remain bounded",
    }[selected_priority]

    cross_axis_priority_snapshot = {
        "contract_version": CONTRACT_VERSION,
        "policy_mode": POLICY_MODE,
        "selected_priority": selected_priority,
        "stabilize_weight": bounded_weights["stabilize"],
        "conserve_weight": bounded_weights["conserve"],
        "guard_weight": bounded_weights["guard"],
        "review_weight": bounded_weights["review"],
        "repair_weight": bounded_weights["repair"],
        "grow_weight": bounded_weights["grow"],
        "reflective_modifier": round(_clamp(reflective_modifier), 3),
        "priority_reason": priority_reason,
        "upstream_pressure_sources": source_refs,
        "active_axes": active_axes,
    }

    proposal_conflict_snapshot = {
        "contract_version": CONTRACT_VERSION,
        "policy_mode": POLICY_MODE,
        "highest_severity": highest_conflict_severity,
        "conflict_count": conflict_count,
        "unresolved_conflict_refs": [f"conflict:{conflict}" for conflict in conflicts],
        "blocked_axes": sorted(blocked_axes),
        "resolution_posture": "review" if conflict_count else selected_priority,
        "source_refs": source_refs,
    }

    integrated_policy_hints = {
        "contract_version": CONTRACT_VERSION,
        "policy_mode": POLICY_MODE,
        "selected_priority": selected_priority,
        "integration_posture": selected_priority if stable_priority else "review",
        "dominant_pressure_axis": dominant_pressure_axis,
        "stability_bias": round(_clamp(stability_bias), 3),
        "conflict_severity": highest_conflict_severity,
        "active_axes": active_axes,
        "required_gate": REQUIRED_WRITEBACK_GATE,
        "behavioral_authority": "none",
        "proposal_only": True,
    }

    axis_arbitration_hints = {}
    for axis_name in _upstream_axes_present(runtime):
        score = axis_scores.get(axis_name, 0.0)
        if score <= 0.0:
            continue
        recommendation = {
            "self_model": "hold broad growth until confidence and known-unknown pressure return to bounded levels",
            "endogenous_drives": "route maintenance and reserve protection through governed integration review before expansion",
            "reflective_self": "treat reflective revisions as bounded modifiers rather than direct authority upgrades",
            "developmental_self": "allow growth proposals only when continuity gaps remain bounded under review",
            "social_self": "prioritize repair proposals without directly mutating social owner state",
            "embodied_self": "guard boundary and conserve resources before broader coupling or growth",
        }[axis_name]
        axis_arbitration_hints[axis_name] = {
            "hint_id": f"axis_hint:{axis_name}:{selected_priority}",
            "axis_name": axis_name,
            "recommendation": recommendation,
            "priority_weight": round(_clamp(score), 3),
            "guardrail_summary": "advisory_only_no_upstream_owner_mutation",
            "advisory_only": True,
            "source_refs": source_refs,
        }

    integration_audit_entries = [
        {
            "kind": "integration_priority_selected",
            "selected_priority": selected_priority,
            "dominant_pressure_axis": dominant_pressure_axis,
            "source_refs": source_refs,
        }
    ]
    for conflict in conflicts:
        integration_audit_entries.append(
            {
                "kind": "proposal_conflict",
                "conflict_ref": f"conflict:{conflict}",
                "severity": highest_conflict_severity,
            }
        )
    if idle_window:
        integration_audit_entries.append(
            {
                "kind": "idle_window_observed",
                "idle_seconds": idle_window.get("idle_seconds"),
            }
        )

    self_integration_delta = {
        "contract_version": CONTRACT_VERSION,
        "active_axis_count": len(active_axes),
        "selected_priority": selected_priority,
        "dominant_pressure_axis": dominant_pressure_axis,
        "integration_confidence": round(integration_confidence, 3),
        "stability_bias": round(_clamp(stability_bias), 3),
        "surface_reasons": source_refs,
    }

    integrated_tendency_proposal = {
        "proposal_id": (
            f"self_integration:{selected_priority}:"
            f"{projection.get('owner_revision') or 0}:{len(source_refs) or 1}"
        ),
        "tendency_label": f"{selected_priority}_first_integration",
        "priority_mode": selected_priority,
        "policy_mode": POLICY_MODE,
        "proposed_effects": {
            "self_integration_delta": self_integration_delta,
            "cross_axis_priority_snapshot": cross_axis_priority_snapshot,
            "proposal_conflict_snapshot": proposal_conflict_snapshot,
            "integrated_policy_hints": integrated_policy_hints,
        },
        "justification": priority_reason,
        "required_gate": REQUIRED_WRITEBACK_GATE,
        "proposal_discipline": "proposal_only",
        "effect_scope": "proposal_only",
        "behavioral_authority": "none",
        "requested_effects": [],
        "source_refs": source_refs,
        "status": "proposed",
    }

    self_integration_writeback_candidate = {
        "source": "proto_self_v2",
        "contract_version": CONTRACT_VERSION,
        "required_gate": REQUIRED_WRITEBACK_GATE,
        "proposal_discipline": "proposal_only",
        "behavioral_authority": "none",
        "selected_priority": selected_priority,
        "dominant_pressure_axis": dominant_pressure_axis,
        "conflict_severity": highest_conflict_severity,
        "active_axes": active_axes,
        "owner_revision": projection.get("owner_revision"),
    }

    preferred_mode = "respond"
    if selected_priority in {"stabilize", "conserve", "guard", "repair"}:
        preferred_mode = "repair"
    elif selected_priority == "review":
        preferred_mode = "defer"
    response_tendency = ResponseTendency(
        preferred_mode=preferred_mode,
        preferred_tone="cautious",
        certainty_bound="bounded",
        suggested_next_step=(
            "route cross-axis integration through the governed self_integration_writeback_gate "
            "before any broader action or owner writeback"
        ),
        ask_needed=False,
    )

    selfhood_integration_context = {
        **context_summary,
        "selected_priority": selected_priority,
        "dominant_pressure_axis": dominant_pressure_axis,
        "integration_confidence": round(integration_confidence, 3),
        "highest_conflict_severity": highest_conflict_severity,
        "active_axes": active_axes,
        "source_refs": source_refs,
    }

    policy_hint_patch = {
        "self_integration_priority": selected_priority,
        "self_integration_conflict_severity": highest_conflict_severity,
        "self_integration_required_gate": REQUIRED_WRITEBACK_GATE,
        "self_integration_active_axes": active_axes,
    }

    return {
        "selfhood_integration_context": selfhood_integration_context,
        "self_integration_delta": self_integration_delta,
        "cross_axis_priority_snapshot": cross_axis_priority_snapshot,
        "proposal_conflict_snapshot": proposal_conflict_snapshot,
        "integrated_policy_hints": integrated_policy_hints,
        "integrated_tendency_proposal": integrated_tendency_proposal,
        "axis_arbitration_hints": axis_arbitration_hints,
        "integration_audit_entries": integration_audit_entries,
        "self_integration_writeback_candidate": self_integration_writeback_candidate,
        "policy_hint_patch": policy_hint_patch,
        "response_tendency": response_tendency,
    }
