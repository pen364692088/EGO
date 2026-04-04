from __future__ import annotations

from typing import Any, Dict, Optional

from openemotion.embodied_self import (
    REQUIRED_WRITEBACK_GATE,
    RUNTIME_LOCAL_PROJECTION_FIELD,
    RUNTIME_LOCAL_PROJECTION_SEMANTICS,
)
from openemotion.proto_self.schemas import ResponseTendency


PROJECTION_FIELD = "runtime_summary.embodied_self_context"
HOST_HINT_FIELD = "runtime_summary.environment_context"
CONTRACT_VERSION = "mvp18.embodied_contract.v1"
PROJECTION_SEMANTICS = RUNTIME_LOCAL_PROJECTION_SEMANTICS

BOUNDED_CONTEXT_FIELDS = (
    "schema_version",
    "owner_revision",
    "last_revision_id",
    "resource_slack",
    "perceived_load",
    "active_coupling_count",
    "max_resource_pressure",
    "min_resource_slack",
    "max_boundary_pressure",
    "recent_consequence_count",
    "stabilization_proposal_count",
    "self_world_guard_bias",
)

HOST_HINT_FIELDS = (
    "source",
    "action_ref",
    "coupling_event",
    "outcome_type",
    "outcome_summary",
    "resource_pressure_hint",
    "slack_hint",
    "boundary_signal",
    "boundary_pressure_hint",
    "stabilization_needed",
    "promotion_budget",
)

ALLOWED_PROMOTION_LEVELS = {"shadow_only", "review_only", "controlled_axis"}
FAILURE_OUTCOMES = {"failure", "timeout", "error", "unexpected"}


def extract_runtime_embodied_self_context(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    raw = dict((runtime_summary or {}).get("embodied_self_context") or {})
    if not raw:
        return {}
    return {key: raw[key] for key in BOUNDED_CONTEXT_FIELDS if key in raw}


def extract_runtime_environment_context(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    raw = dict((runtime_summary or {}).get("environment_context") or {})
    if not raw:
        return {}
    return {key: raw[key] for key in HOST_HINT_FIELDS if key in raw}


def summarize_runtime_embodied_self_context(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    context = extract_runtime_embodied_self_context(runtime_summary)
    host_context = extract_runtime_environment_context(runtime_summary)
    return {
        "present": bool(context or host_context),
        "contract_version": CONTRACT_VERSION,
        "projection_field": PROJECTION_FIELD,
        "host_hint_field": HOST_HINT_FIELD,
        "projection_semantics": PROJECTION_SEMANTICS,
        "runtime_local_projection_field": RUNTIME_LOCAL_PROJECTION_FIELD,
        "schema_version": context.get("schema_version"),
        "owner_revision": context.get("owner_revision"),
        "last_revision_id": context.get("last_revision_id"),
        "resource_slack": float(context.get("resource_slack") or 0.0),
        "perceived_load": float(context.get("perceived_load") or 0.0),
        "active_coupling_count": int(context.get("active_coupling_count") or 0),
        "max_resource_pressure": float(context.get("max_resource_pressure") or 0.0),
        "min_resource_slack": float(context.get("min_resource_slack") or 0.0),
        "max_boundary_pressure": float(context.get("max_boundary_pressure") or 0.0),
        "recent_consequence_count": int(context.get("recent_consequence_count") or 0),
        "stabilization_proposal_count": int(context.get("stabilization_proposal_count") or 0),
        "self_world_guard_bias": float(context.get("self_world_guard_bias") or 0.0),
        "source": str(host_context.get("source") or ""),
        "action_ref": str(host_context.get("action_ref") or ""),
        "coupling_event": str(host_context.get("coupling_event") or ""),
        "outcome_type": str(host_context.get("outcome_type") or ""),
        "outcome_summary": str(host_context.get("outcome_summary") or ""),
        "resource_pressure_hint": float(host_context.get("resource_pressure_hint") or 0.0),
        "slack_hint": float(host_context.get("slack_hint") or 0.0),
        "boundary_signal": str(host_context.get("boundary_signal") or ""),
        "boundary_pressure_hint": float(host_context.get("boundary_pressure_hint") or 0.0),
        "stabilization_needed": bool(host_context.get("stabilization_needed")),
        "promotion_budget": str(host_context.get("promotion_budget") or "review_only"),
    }


def _resolve_boundary_signal(
    *,
    boundary_signal: str,
    boundary_pressure: float,
    guard_bias: float,
) -> str:
    if boundary_signal:
        return boundary_signal
    if boundary_pressure >= 0.75 or guard_bias >= 0.75:
        return "repair_only"
    if boundary_pressure >= 0.45 or guard_bias >= 0.55:
        return "guarded"
    return "open"


def derive_embodied_outputs(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    runtime = dict(runtime_summary or {})
    context = extract_runtime_embodied_self_context(runtime)
    host_context = extract_runtime_environment_context(runtime)
    if not context and not host_context:
        return {
            "environment_context": {},
            "embodied_self_delta": {},
            "consequence_update_candidates": [],
            "resource_boundary_snapshot": {},
            "embodied_policy_hints": {},
            "repair_or_stabilize_proposal_candidates": [],
            "embodied_writeback_candidate": None,
            "policy_hint_patch": {},
            "response_tendency": None,
        }

    resource_slack = float(context.get("resource_slack") or 0.0)
    perceived_load = float(context.get("perceived_load") or 0.0)
    active_coupling_count = int(context.get("active_coupling_count") or 0)
    max_resource_pressure = max(
        float(context.get("max_resource_pressure") or 0.0),
        float(host_context.get("resource_pressure_hint") or 0.0),
    )
    min_resource_slack = float(context.get("min_resource_slack") or resource_slack)
    if "slack_hint" in host_context:
        min_resource_slack = min(min_resource_slack, float(host_context.get("slack_hint") or 0.0))
    max_boundary_pressure = max(
        float(context.get("max_boundary_pressure") or 0.0),
        float(host_context.get("boundary_pressure_hint") or 0.0),
    )
    recent_consequence_count = int(context.get("recent_consequence_count") or 0)
    stabilization_proposal_count = int(context.get("stabilization_proposal_count") or 0)
    self_world_guard_bias = float(context.get("self_world_guard_bias") or 0.0)
    action_ref = str(host_context.get("action_ref") or "")
    coupling_event = str(host_context.get("coupling_event") or "")
    outcome_type = str(host_context.get("outcome_type") or "")
    outcome_summary = str(host_context.get("outcome_summary") or "")
    stabilization_needed = bool(host_context.get("stabilization_needed")) or outcome_type in FAILURE_OUTCOMES
    promotion_level = str(host_context.get("promotion_budget") or "review_only")
    if promotion_level not in ALLOWED_PROMOTION_LEVELS:
        promotion_level = "review_only"
    boundary_signal = _resolve_boundary_signal(
        boundary_signal=str(host_context.get("boundary_signal") or ""),
        boundary_pressure=max_boundary_pressure,
        guard_bias=self_world_guard_bias,
    )

    surface_reasons = []
    for reason, enabled in (
        ("resource_pressure", max_resource_pressure >= 0.6),
        ("resource_slack_low", min_resource_slack <= 0.35),
        ("boundary_pressure", max_boundary_pressure >= 0.45),
        ("stabilization_needed", stabilization_needed),
        ("recent_consequence", recent_consequence_count > 0),
        ("stabilization_history", stabilization_proposal_count > 0),
        ("high_load", perceived_load >= 0.65),
    ):
        if enabled:
            surface_reasons.append(reason)

    should_surface = bool(surface_reasons)
    environment_context = summarize_runtime_embodied_self_context(runtime)
    resource_boundary_snapshot = {
        "contract_version": CONTRACT_VERSION,
        "owner_revision": context.get("owner_revision"),
        "last_revision_id": context.get("last_revision_id"),
        "resource_slack": round(resource_slack, 3),
        "perceived_load": round(perceived_load, 3),
        "active_coupling_count": active_coupling_count,
        "max_resource_pressure": round(max_resource_pressure, 3),
        "min_resource_slack": round(min_resource_slack, 3),
        "max_boundary_pressure": round(max_boundary_pressure, 3),
        "recent_consequence_count": recent_consequence_count,
        "stabilization_proposal_count": stabilization_proposal_count,
        "self_world_guard_bias": round(self_world_guard_bias, 3),
        "action_ref": action_ref,
        "outcome_type": outcome_type,
        "coupling_event": coupling_event,
        "boundary_signal": boundary_signal,
    }
    embodied_policy_hints = {
        "resource_bias": "conserve"
        if max_resource_pressure >= 0.6 or min_resource_slack <= 0.35
        else "normal",
        "boundary_mode": boundary_signal,
        "stabilization_bias": "elevated" if stabilization_needed else "normal",
        "consequence_mode": "repair" if outcome_type in FAILURE_OUTCOMES else "observe",
        "self_world_guard": "tight"
        if self_world_guard_bias >= 0.6 or max_boundary_pressure >= 0.6
        else "bounded",
        "action_ref": action_ref,
    }

    consequence_update_candidates = []
    repair_or_stabilize_proposal_candidates = []
    embodied_writeback_candidate = None
    embodied_self_delta: Dict[str, Any] = {}
    policy_hint_patch: Dict[str, Any] = {}
    response_tendency: Optional[ResponseTendency] = None

    if should_surface:
        candidate_suffix = action_ref or coupling_event or "unknown"
        consequence_update_candidates = [
            {
                "candidate_id": f"consequence_update:{candidate_suffix}:{context.get('owner_revision') or 0}",
                "action_ref": action_ref,
                "outcome_type": outcome_type or "observed",
                "required_gate": REQUIRED_WRITEBACK_GATE,
                "proposal_discipline": "proposal_only",
                "behavioral_authority": "none",
                "promotion_level": promotion_level,
            }
        ]
        repair_or_stabilize_proposal_candidates = [
            {
                "candidate_id": f"embodied_stabilize:{candidate_suffix}:{len(surface_reasons) or 1}",
                "reason": "repair_or_stabilize",
                "surface_reasons": surface_reasons,
                "required_gate": REQUIRED_WRITEBACK_GATE,
                "proposal_discipline": "proposal_only",
                "behavioral_authority": "none",
                "promotion_level": promotion_level,
            }
        ]
        embodied_writeback_candidate = {
            "source": "proto_self_v2",
            "contract_version": CONTRACT_VERSION,
            "action_ref": action_ref,
            "required_gate": REQUIRED_WRITEBACK_GATE,
            "proposal_discipline": "proposal_only",
            "behavioral_authority": "none",
            "promotion_level": promotion_level,
            "surface_reasons": surface_reasons,
            "owner_revision": context.get("owner_revision"),
        }
        embodied_self_delta = {
            "proposal_candidate_count": len(repair_or_stabilize_proposal_candidates),
            "action_ref": action_ref,
            "surface_reasons": surface_reasons,
            "boundary_signal": boundary_signal,
        }
        policy_hint_patch = {
            "embodied_resource_bias": embodied_policy_hints["resource_bias"],
            "embodied_boundary_bias": "cautious"
            if boundary_signal in {"guarded", "repair_only"}
            else "open",
            "embodied_stabilization_bias": embodied_policy_hints["stabilization_bias"],
        }
        response_tendency = ResponseTendency(
            preferred_mode="repair" if stabilization_needed else "respond",
            preferred_tone="cautious",
            certainty_bound="bounded",
            suggested_next_step=(
                "route consequence, resource, and self-world boundary adjustments "
                "through the governed embodied writeback path"
            ),
            ask_needed=False,
        )

    return {
        "environment_context": environment_context,
        "embodied_self_delta": embodied_self_delta,
        "consequence_update_candidates": consequence_update_candidates,
        "resource_boundary_snapshot": resource_boundary_snapshot,
        "embodied_policy_hints": embodied_policy_hints,
        "repair_or_stabilize_proposal_candidates": repair_or_stabilize_proposal_candidates,
        "embodied_writeback_candidate": embodied_writeback_candidate,
        "policy_hint_patch": policy_hint_patch,
        "response_tendency": response_tendency,
    }
