from __future__ import annotations

from typing import Any, Dict, Optional

from openemotion.initiative_self import (
    REQUIRED_WRITEBACK_GATE,
    RUNTIME_LOCAL_PROJECTION_FIELD,
    RUNTIME_LOCAL_PROJECTION_SEMANTICS,
)
from openemotion.proto_self.schemas import ResponseTendency
from openemotion.proto_self_v2.selfhood_integration_context import (
    extract_runtime_selfhood_integration_context,
)


PROJECTION_FIELD = "runtime_summary.initiative_self_context"
HOST_HINT_FIELD = "runtime_summary.initiative_context"
CONTRACT_VERSION = "mvp20.initiative_contract.v1"
PROJECTION_SEMANTICS = RUNTIME_LOCAL_PROJECTION_SEMANTICS

BOUNDED_CONTEXT_FIELDS = (
    "schema_version",
    "owner_revision",
    "last_revision_id",
    "dominant_mode",
    "initiative_pressure",
    "commitment_carryover_bias",
    "recent_delivery_sensitivity",
    "selected_priority",
    "active_commitments_count",
    "blocked_commitments_count",
    "continuity_confidence",
    "has_initiative_proposal_candidate",
    "has_host_proactive_candidate",
)

HOST_HINT_FIELDS = (
    "source",
    "initiative_trigger",
    "continuity_ref",
    "pending_commitment_refs",
    "blocked_commitment_refs",
    "reserve_level",
    "recent_delivery_status",
    "delivery_failure",
    "idle_seconds",
    "host_lane_hint",
    "promotion_budget",
)

ALLOWED_PROMOTION_LEVELS = {"shadow_only", "review_only", "controlled_axis"}
FAILURE_STATUSES = {"failed", "blocked", "timeout", "error"}


def _clamp(value: Any, lower: float = 0.0, upper: float = 1.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = lower
    return max(lower, min(upper, numeric))


def extract_runtime_initiative_self_context(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    raw = dict((runtime_summary or {}).get("initiative_self_context") or {})
    if not raw:
        return {}
    return {key: raw[key] for key in BOUNDED_CONTEXT_FIELDS if key in raw}


def extract_runtime_initiative_context(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    raw = dict((runtime_summary or {}).get("initiative_context") or {})
    if not raw:
        return {}
    return {key: raw[key] for key in HOST_HINT_FIELDS if key in raw}


def summarize_runtime_initiative_context(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    runtime = dict(runtime_summary or {})
    context = extract_runtime_initiative_self_context(runtime)
    host_context = extract_runtime_initiative_context(runtime)
    selfhood_context = extract_runtime_selfhood_integration_context(runtime)
    recent_delivery_outcome = dict(runtime.get("recent_delivery_outcome") or {})
    resource_budget_hint = dict(runtime.get("resource_budget_hint") or {})
    idle_window = dict(runtime.get("idle_window") or {})
    recent_delivery_status = str(
        host_context.get("recent_delivery_status")
        or recent_delivery_outcome.get("status")
        or ("failed" if recent_delivery_outcome.get("success") is False else "")
    )
    reserve_level = str(host_context.get("reserve_level") or resource_budget_hint.get("reserve_level") or "")
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
        "dominant_mode": str(context.get("dominant_mode") or ""),
        "initiative_pressure": _clamp(context.get("initiative_pressure")),
        "commitment_carryover_bias": _clamp(context.get("commitment_carryover_bias")),
        "recent_delivery_sensitivity": _clamp(context.get("recent_delivery_sensitivity")),
        "selected_priority": str(context.get("selected_priority") or ""),
        "active_commitments_count": int(context.get("active_commitments_count") or 0),
        "blocked_commitments_count": int(context.get("blocked_commitments_count") or 0),
        "continuity_confidence": _clamp(context.get("continuity_confidence"), upper=1.0),
        "has_initiative_proposal_candidate": bool(context.get("has_initiative_proposal_candidate")),
        "has_host_proactive_candidate": bool(context.get("has_host_proactive_candidate")),
        "source": str(host_context.get("source") or ""),
        "initiative_trigger": str(host_context.get("initiative_trigger") or ""),
        "continuity_ref": str(host_context.get("continuity_ref") or ""),
        "pending_commitment_refs": list(host_context.get("pending_commitment_refs") or []),
        "blocked_commitment_refs": list(host_context.get("blocked_commitment_refs") or []),
        "reserve_level": reserve_level,
        "recent_delivery_status": recent_delivery_status,
        "delivery_failure": bool(host_context.get("delivery_failure"))
        or recent_delivery_status in FAILURE_STATUSES,
        "idle_seconds": float(
            host_context.get("idle_seconds")
            or idle_window.get("idle_seconds")
            or idle_window.get("duration_seconds")
            or 0.0
        ),
        "host_lane_hint": str(host_context.get("host_lane_hint") or "host_proactive_outbox"),
        "promotion_budget": str(host_context.get("promotion_budget") or "review_only"),
        "selfhood_selected_priority": str(selfhood_context.get("selected_priority") or ""),
        "selfhood_conflict_severity": str(selfhood_context.get("highest_conflict_severity") or "none"),
    }


def derive_initiative_outputs(
    runtime_summary: Dict[str, Any] | None,
    *,
    selfhood_outputs: Dict[str, Any],
) -> Dict[str, Any]:
    runtime = dict(runtime_summary or {})
    context = extract_runtime_initiative_self_context(runtime)
    host_context = extract_runtime_initiative_context(runtime)
    if not context and not host_context:
        return {
            "initiative_context": {},
            "initiative_self_delta": {},
            "initiative_proposal_candidates": [],
            "commitment_execution_snapshot": {},
            "initiative_policy_hints": {},
            "host_proactive_candidate": None,
            "initiative_audit_entries": [],
            "initiative_writeback_candidate": None,
            "policy_hint_patch": {},
            "response_tendency": None,
        }
    if not context:
        has_host_signal = any(
            (
                bool(host_context.get("continuity_ref")),
                bool(host_context.get("pending_commitment_refs") or []),
                bool(host_context.get("blocked_commitment_refs") or []),
                float(host_context.get("idle_seconds") or 0.0) >= 600.0,
                str(host_context.get("recent_delivery_status") or "").strip() in FAILURE_STATUSES,
                bool(host_context.get("delivery_failure")),
            )
        )
        if not has_host_signal:
            return {
                "initiative_context": {},
                "initiative_self_delta": {},
                "initiative_proposal_candidates": [],
                "commitment_execution_snapshot": {},
                "initiative_policy_hints": {},
                "host_proactive_candidate": None,
                "initiative_audit_entries": [],
                "initiative_writeback_candidate": None,
                "policy_hint_patch": {},
                "response_tendency": None,
            }

    context_summary = summarize_runtime_initiative_context(runtime)
    initiative_pressure = context_summary["initiative_pressure"]
    commitment_carryover_bias = context_summary["commitment_carryover_bias"]
    delivery_sensitivity = context_summary["recent_delivery_sensitivity"]
    active_commitments_count = int(context_summary["active_commitments_count"])
    blocked_commitments_count = int(context_summary["blocked_commitments_count"])
    continuity_confidence = _clamp(context_summary["continuity_confidence"])
    reserve_level = context_summary["reserve_level"] or "medium"
    recent_delivery_status = context_summary["recent_delivery_status"] or "stable"
    delivery_failure = bool(context_summary["delivery_failure"])
    idle_seconds = float(context_summary["idle_seconds"])
    host_lane_hint = str(context_summary["host_lane_hint"] or "host_proactive_outbox")
    promotion_level = str(context_summary["promotion_budget"] or "review_only")
    if promotion_level not in ALLOWED_PROMOTION_LEVELS:
        promotion_level = "review_only"

    integrated_priority = str(
        context_summary["selfhood_selected_priority"]
        or (selfhood_outputs.get("cross_axis_priority_snapshot") or {}).get("selected_priority")
        or ""
    )
    integrated_conflict = str(
        context_summary["selfhood_conflict_severity"]
        or (selfhood_outputs.get("proposal_conflict_snapshot") or {}).get("highest_conflict_severity")
        or "none"
    )
    integrated_policy_hints = dict(selfhood_outputs.get("integrated_policy_hints") or {})

    surface_reasons = []
    for reason, enabled in (
        ("initiative_pressure", initiative_pressure >= 0.55),
        ("commitment_carryover", commitment_carryover_bias >= 0.5),
        ("active_commitments", active_commitments_count > 0),
        ("blocked_commitments", blocked_commitments_count > 0),
        ("continuity_fragile", continuity_confidence < 0.65),
        ("idle_window", idle_seconds >= 600.0),
        ("low_reserve", reserve_level == "low"),
        ("delivery_failure", delivery_failure),
        ("integration_guard", integrated_priority in {"stabilize", "conserve", "guard", "review"}),
        ("integration_conflict", integrated_conflict in {"medium", "high"}),
    ):
        if enabled:
            surface_reasons.append(reason)

    should_surface = bool(surface_reasons)
    if reserve_level == "low" or delivery_failure or integrated_priority in {"stabilize", "conserve", "guard"}:
        selected_priority = "hold"
    elif blocked_commitments_count > 0 or continuity_confidence < 0.55 or integrated_priority == "review":
        selected_priority = "review"
    elif active_commitments_count > 0 and idle_seconds >= 600.0:
        selected_priority = "carry_forward"
    elif initiative_pressure >= 0.6:
        selected_priority = "prepare"
    else:
        selected_priority = str(context.get("selected_priority") or "review")

    commitment_mode = (
        "blocked"
        if blocked_commitments_count > 0 or delivery_failure
        else ("carry_forward" if active_commitments_count > 0 else "idle")
    )
    host_proactive_mode = (
        "held"
        if selected_priority in {"hold", "review"} or reserve_level == "low" or delivery_failure
        else ("candidate" if active_commitments_count > 0 and idle_seconds >= 600.0 else "none")
    )
    continuity_mode = "fragile" if continuity_confidence < 0.65 else "stable"

    commitment_execution_snapshot = {
        "contract_version": CONTRACT_VERSION,
        "owner_revision": context.get("owner_revision"),
        "last_revision_id": context.get("last_revision_id"),
        "selected_priority": selected_priority,
        "active_commitments_count": active_commitments_count,
        "blocked_commitments_count": blocked_commitments_count,
        "continuity_confidence": round(continuity_confidence, 3),
        "commitment_mode": commitment_mode,
        "reserve_level": reserve_level,
        "recent_delivery_status": recent_delivery_status,
        "idle_seconds": round(idle_seconds, 1),
        "integrated_priority": integrated_priority,
    }
    initiative_policy_hints = {
        "initiative_bias": selected_priority,
        "continuity_mode": continuity_mode,
        "commitment_mode": commitment_mode,
        "host_proactive_mode": host_proactive_mode,
        "reserve_bias": "conserve" if reserve_level == "low" else "bounded",
        "delivery_bias": "repair_review" if delivery_failure else "normal",
    }

    initiative_proposal_candidates = []
    host_proactive_candidate = None
    initiative_writeback_candidate = None
    initiative_self_delta: Dict[str, Any] = {}
    initiative_audit_entries = []
    policy_hint_patch: Dict[str, Any] = {}
    response_tendency: Optional[ResponseTendency] = None

    if should_surface:
        proposal_label = {
            "hold": "hold_initiative_under_guard",
            "review": "review_commitment_continuity",
            "prepare": "prepare_governed_followup",
            "carry_forward": "carry_forward_commitment",
            "schedule": "schedule_host_review",
        }.get(selected_priority, "review_commitment_continuity")
        initiative_proposal_candidates = [
            {
                "proposal_id": f"initiative:{selected_priority}:{context.get('owner_revision') or 0}",
                "proposal_label": proposal_label,
                "priority_mode": selected_priority,
                "proposed_effects": {
                    "initiative_bias": selected_priority,
                    "commitment_mode": commitment_mode,
                    "host_proactive_mode": host_proactive_mode,
                },
                "justification": ", ".join(surface_reasons[:4]),
                "required_gate": REQUIRED_WRITEBACK_GATE,
                "effect_scope": "proposal_only",
                "behavioral_authority": "none",
                "requested_effects": ["governed_initiative_review"],
                "promotion_level": promotion_level,
            }
        ]
        if host_proactive_mode == "candidate":
            host_proactive_candidate = {
                "candidate_id": f"host_proactive:{selected_priority}:{context.get('owner_revision') or 0}",
                "candidate_label": "governed_host_proactive_followup",
                "continuity_basis": context_summary["continuity_ref"] or commitment_mode,
                "host_lane_hint": host_lane_hint,
                "required_gate": REQUIRED_WRITEBACK_GATE,
                "proposal_discipline": "proposal_only",
                "behavioral_authority": "none",
                "requested_effects": ["governed_host_proactive_review"],
                "promotion_level": promotion_level,
            }
        initiative_writeback_candidate = {
            "source": "proto_self_v2",
            "contract_version": CONTRACT_VERSION,
            "required_gate": REQUIRED_WRITEBACK_GATE,
            "proposal_discipline": "proposal_only",
            "behavioral_authority": "none",
            "promotion_level": promotion_level,
            "selected_priority": selected_priority,
            "surface_reasons": surface_reasons,
            "owner_revision": context.get("owner_revision"),
        }
        initiative_self_delta = {
            "proposal_candidate_count": len(initiative_proposal_candidates),
            "selected_priority": selected_priority,
            "commitment_mode": commitment_mode,
            "host_proactive_mode": host_proactive_mode,
            "surface_reasons": surface_reasons,
        }
        initiative_audit_entries = [
            {
                "entry_type": "initiative_surface",
                "selected_priority": selected_priority,
                "host_proactive_mode": host_proactive_mode,
                "surface_reasons": surface_reasons,
                "integrated_priority": integrated_priority,
                "integrated_conflict": integrated_conflict,
            }
        ]
        policy_hint_patch = {
            "initiative_priority": selected_priority,
            "initiative_commitment_mode": commitment_mode,
            "initiative_host_proactive_mode": host_proactive_mode,
            "initiative_reserve_bias": initiative_policy_hints["reserve_bias"],
        }
        if integrated_policy_hints.get("integrated_priority"):
            policy_hint_patch["selfhood_integrated_priority"] = integrated_policy_hints["integrated_priority"]
        response_tendency = ResponseTendency(
            preferred_mode="defer" if selected_priority in {"hold", "review"} else "respond",
            preferred_tone="cautious" if delivery_failure or reserve_level == "low" else "supportive",
            certainty_bound="bounded",
            suggested_next_step="route initiative continuity and host-proactive followup through the governed initiative writeback path",
            ask_needed=selected_priority == "review",
        )

    return {
        "initiative_context": context_summary,
        "initiative_self_delta": initiative_self_delta,
        "initiative_proposal_candidates": initiative_proposal_candidates,
        "commitment_execution_snapshot": commitment_execution_snapshot,
        "initiative_policy_hints": initiative_policy_hints,
        "host_proactive_candidate": host_proactive_candidate,
        "initiative_audit_entries": initiative_audit_entries,
        "initiative_writeback_candidate": initiative_writeback_candidate,
        "policy_hint_patch": policy_hint_patch,
        "response_tendency": response_tendency,
    }
