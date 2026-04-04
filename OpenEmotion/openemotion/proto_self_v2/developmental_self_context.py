from __future__ import annotations

from typing import Any, Dict, Optional

from openemotion.developmental_self import (
    REQUIRED_WRITEBACK_GATE,
    RUNTIME_LOCAL_PROJECTION_FIELD,
    RUNTIME_LOCAL_PROJECTION_SEMANTICS,
)
from openemotion.proto_self.schemas import ResponseTendency


PROJECTION_FIELD = "runtime_summary.developmental_self_context"
HOST_HINT_FIELD = "runtime_summary.developmental_context"
PROJECTION_SEMANTICS = RUNTIME_LOCAL_PROJECTION_SEMANTICS

BOUNDED_CONTEXT_FIELDS = (
    "schema_version",
    "owner_revision",
    "last_revision_id",
    "continuity_score",
    "growth_pressure",
    "stagnation_signal",
    "identity_preservation_confidence",
    "developmental_risk_index",
    "trajectory_summary",
    "promotion_queue_size",
    "recent_proposal_count",
)

HOST_HINT_FIELDS = (
    "source",
    "continuity_gap",
    "growth_pressure_hint",
    "stagnation_signal_hint",
    "identity_guard",
    "replay_debt",
    "promotion_budget",
    "drift_markers",
)


def extract_runtime_developmental_self_context(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    raw = dict((runtime_summary or {}).get("developmental_self_context") or {})
    if not raw:
        return {}
    return {key: raw[key] for key in BOUNDED_CONTEXT_FIELDS if key in raw}


def extract_runtime_developmental_context(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    raw = dict((runtime_summary or {}).get("developmental_context") or {})
    if not raw:
        return {}
    return {key: raw[key] for key in HOST_HINT_FIELDS if key in raw}


def summarize_runtime_developmental_self_context(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    context = extract_runtime_developmental_self_context(runtime_summary)
    host_context = extract_runtime_developmental_context(runtime_summary)
    return {
        "present": bool(context),
        "projection_field": PROJECTION_FIELD,
        "projection_semantics": PROJECTION_SEMANTICS,
        "runtime_local_projection_field": RUNTIME_LOCAL_PROJECTION_FIELD,
        "host_hint_field": HOST_HINT_FIELD,
        "schema_version": context.get("schema_version"),
        "owner_revision": context.get("owner_revision"),
        "last_revision_id": context.get("last_revision_id"),
        "continuity_score": float(context.get("continuity_score") or 0.0),
        "growth_pressure": float(context.get("growth_pressure") or 0.0),
        "stagnation_signal": float(context.get("stagnation_signal") or 0.0),
        "identity_preservation_confidence": float(
            context.get("identity_preservation_confidence") or 0.0
        ),
        "developmental_risk_index": float(context.get("developmental_risk_index") or 0.0),
        "promotion_queue_size": int(context.get("promotion_queue_size") or 0),
        "recent_proposal_count": int(context.get("recent_proposal_count") or 0),
        "continuity_gap": float(host_context.get("continuity_gap") or 0.0),
        "replay_debt": float(host_context.get("replay_debt") or 0.0),
        "identity_guard": str(host_context.get("identity_guard") or ""),
        "drift_marker_count": len(host_context.get("drift_markers") or []),
    }


def derive_developmental_outputs(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    runtime = dict(runtime_summary or {})
    context = extract_runtime_developmental_self_context(runtime)
    host_context = extract_runtime_developmental_context(runtime)
    if not context and not host_context:
        return {
            "developmental_context": {},
            "developmental_self_delta": {},
            "developmental_proposal_candidates": [],
            "developmental_continuity_snapshot": {},
            "developmental_priority_hints": {},
            "developmental_audit_entries": [],
            "developmental_writeback_candidate": None,
            "policy_hint_patch": {},
            "response_tendency": None,
        }

    continuity_score = float(context.get("continuity_score") or 0.0)
    growth_pressure = max(
        float(context.get("growth_pressure") or 0.0),
        float(host_context.get("growth_pressure_hint") or 0.0),
    )
    stagnation_signal = max(
        float(context.get("stagnation_signal") or 0.0),
        float(host_context.get("stagnation_signal_hint") or 0.0),
    )
    identity_preservation_confidence = float(
        context.get("identity_preservation_confidence") or 0.0
    )
    developmental_risk_index = max(
        float(context.get("developmental_risk_index") or 0.0),
        1.0 - identity_preservation_confidence,
    )
    promotion_queue_size = int(context.get("promotion_queue_size") or 0)
    recent_proposal_count = int(context.get("recent_proposal_count") or 0)
    if "continuity_gap" in host_context:
        continuity_gap = float(host_context.get("continuity_gap") or 0.0)
    else:
        continuity_gap = max(0.0, 1.0 - continuity_score)
    replay_debt = float(host_context.get("replay_debt") or 0.0)
    identity_guard = str(host_context.get("identity_guard") or "bounded")
    promotion_budget = str(host_context.get("promotion_budget") or "shadow_only")
    trajectory_summary = dict(context.get("trajectory_summary") or {})

    developmental_context = summarize_runtime_developmental_self_context(runtime)
    developmental_continuity_snapshot = {
        "owner_revision": context.get("owner_revision"),
        "last_revision_id": context.get("last_revision_id"),
        "continuity_score": continuity_score,
        "continuity_gap": round(continuity_gap, 3),
        "growth_pressure": round(growth_pressure, 3),
        "stagnation_signal": round(stagnation_signal, 3),
        "identity_preservation_confidence": round(identity_preservation_confidence, 3),
        "developmental_risk_index": round(developmental_risk_index, 3),
        "trajectory_summary": trajectory_summary,
        "promotion_queue_size": promotion_queue_size,
        "recent_proposal_count": recent_proposal_count,
    }

    should_surface = (
        recent_proposal_count > 0
        or promotion_queue_size > 0
        or continuity_gap >= 0.2
        or stagnation_signal >= 0.35
        or replay_debt > 0.0
        or developmental_risk_index >= 0.45
    )

    developmental_priority_hints = {
        "continuity_priority": (
            "elevated" if continuity_gap >= 0.25 or replay_debt > 0.0 else "normal"
        ),
        "adaptation_mode": "guarded" if stagnation_signal >= 0.35 else "incremental",
        "identity_preservation_guard": identity_guard or "bounded",
        "promotion_budget": promotion_budget,
        "promotion_queue_size": promotion_queue_size,
        "recent_proposal_count": recent_proposal_count,
    }

    developmental_audit_entries = []
    surface_reasons = []
    for reason, enabled in (
        ("proposal_history_present", recent_proposal_count > 0),
        ("promotion_queue_present", promotion_queue_size > 0),
        ("continuity_gap", continuity_gap >= 0.2),
        ("stagnation_signal", stagnation_signal >= 0.35),
        ("replay_debt", replay_debt > 0.0),
        ("developmental_risk", developmental_risk_index >= 0.45),
    ):
        if enabled:
            surface_reasons.append(reason)
            developmental_audit_entries.append({"kind": "developmental_signal", "reason": reason})

    developmental_proposal_candidates = []
    developmental_writeback_candidate = None
    developmental_self_delta: Dict[str, Any] = {}
    policy_hint_patch: Dict[str, Any] = {}
    response_tendency: Optional[ResponseTendency] = None

    if should_surface:
        promotion_level = "review_only"
        if promotion_budget == "controlled_axis" and continuity_gap >= 0.3:
            promotion_level = "controlled_axis"
        elif promotion_budget == "shadow_only":
            promotion_level = "shadow_only"

        candidate_id = (
            f"developmental_candidate:{context.get('owner_revision') or 0}:"
            f"{len(surface_reasons) or 1}"
        )
        developmental_proposal_candidates = [
            {
                "candidate_id": candidate_id,
                "reason": "developmental_continuity",
                "surface_reasons": surface_reasons,
                "continuity_gap": round(continuity_gap, 3),
                "required_gate": REQUIRED_WRITEBACK_GATE,
                "proposal_discipline": "proposal_only",
                "behavioral_authority": "none",
                "promotion_level": promotion_level,
            }
        ]
        developmental_writeback_candidate = {
            "source": "proto_self_v2",
            "required_gate": REQUIRED_WRITEBACK_GATE,
            "proposal_discipline": "proposal_only",
            "behavioral_authority": "none",
            "promotion_level": promotion_level,
            "surface_reasons": surface_reasons,
            "owner_revision": context.get("owner_revision"),
        }
        developmental_self_delta = {
            "proposal_candidate_count": len(developmental_proposal_candidates),
            "surface_reasons": surface_reasons,
            "continuity_adjustment_hint": {
                "continuity_gap": round(continuity_gap, 3),
                "identity_guard": identity_guard or "bounded",
                "promotion_level": promotion_level,
            },
        }
        policy_hint_patch = {
            "developmental_continuity_bias": developmental_priority_hints["continuity_priority"],
            "identity_preservation_guard": developmental_priority_hints["identity_preservation_guard"],
        }
        if stagnation_signal >= 0.35:
            policy_hint_patch["developmental_adaptation_bias"] = "guarded"
        response_tendency = ResponseTendency(
            preferred_mode="respond",
            preferred_tone="cautious",
            certainty_bound="bounded",
            suggested_next_step="prefer identity-preserving adaptation proposals before broadening scope",
            ask_needed=False,
        )

    return {
        "developmental_context": developmental_context,
        "developmental_self_delta": developmental_self_delta,
        "developmental_proposal_candidates": developmental_proposal_candidates,
        "developmental_continuity_snapshot": developmental_continuity_snapshot,
        "developmental_priority_hints": developmental_priority_hints,
        "developmental_audit_entries": developmental_audit_entries,
        "developmental_writeback_candidate": developmental_writeback_candidate,
        "policy_hint_patch": policy_hint_patch,
        "response_tendency": response_tendency,
    }
