from __future__ import annotations

from typing import Any, Dict, Optional

from openemotion.initiative_realization import (
    REQUIRED_WRITEBACK_GATE,
    RUNTIME_LOCAL_PROJECTION_FIELD,
    RUNTIME_LOCAL_PROJECTION_SEMANTICS,
)
from openemotion.proto_self.schemas import ResponseTendency


PROJECTION_FIELD = "runtime_summary.initiative_realization_context"
HOST_HINT_FIELD = "runtime_summary.host_proactive_context"
CONTRACT_VERSION = "mvp21.initiative_realization_contract.v1"
PROJECTION_SEMANTICS = RUNTIME_LOCAL_PROJECTION_SEMANTICS

BOUNDED_CONTEXT_FIELDS = (
    "schema_version",
    "owner_revision",
    "last_revision_id",
    "dominant_mode",
    "realization_pressure",
    "fulfillment_readiness",
    "hold_bias",
    "failure_recovery_bias",
    "selected_lane",
    "active_commitments_count",
    "ready_commitments_count",
    "continuity_confidence",
    "has_realization_candidate",
    "has_controlled_delivery_candidate",
)

HOST_HINT_FIELDS = (
    "source",
    "host_lane_hints",
    "delivery_readiness",
    "readiness_basis",
    "host_lane_hint",
    "reserve_level_hint",
    "pending_realization_refs",
    "recent_delivery_success",
    "recent_delivery_status",
    "promotion_budget",
)

ALLOWED_PROMOTION_LEVELS = {"shadow_only", "review_only", "controlled_axis"}
FAILURE_STATUSES = {"failed", "blocked", "error", "timeout"}


def _clamp(value: Any, lower: float = 0.0, upper: float = 1.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = lower
    return max(lower, min(upper, numeric))


def _to_bool(value: Any) -> bool:
    return bool(value)


def extract_runtime_initiative_realization_context(
    runtime_summary: Dict[str, Any] | None,
) -> Dict[str, Any]:
    raw = dict((runtime_summary or {}).get("initiative_realization_context") or {})
    if not raw:
        return {}
    return {key: raw[key] for key in BOUNDED_CONTEXT_FIELDS if key in raw}


def extract_runtime_host_proactive_context(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    raw = dict((runtime_summary or {}).get("host_proactive_context") or {})
    if not raw:
        return {}
    return {key: raw[key] for key in HOST_HINT_FIELDS if key in raw}


def summarize_runtime_initiative_realization_context(
    runtime_summary: Dict[str, Any] | None,
) -> Dict[str, Any]:
    context = extract_runtime_initiative_realization_context(runtime_summary)
    host_context = extract_runtime_host_proactive_context(runtime_summary)
    maintenance_context = dict((runtime_summary or {}).get("maintenance_context") or {})
    resource_budget = dict((runtime_summary or {}).get("resource_budget_hint") or {})
    recent_delivery = dict((runtime_summary or {}).get("recent_delivery_outcome") or {})
    idle_window = dict((runtime_summary or {}).get("idle_window") or {})
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
        "selected_lane": str(context.get("selected_lane") or ""),
        "realization_pressure": _clamp(context.get("realization_pressure")),
        "fulfillment_readiness": _clamp(context.get("fulfillment_readiness")),
        "hold_bias": _clamp(context.get("hold_bias")),
        "failure_recovery_bias": _clamp(context.get("failure_recovery_bias")),
        "active_commitments_count": int(context.get("active_commitments_count") or 0),
        "ready_commitments_count": int(context.get("ready_commitments_count") or 0),
        "continuity_confidence": _clamp(context.get("continuity_confidence")),
        "has_realization_candidate": _to_bool(context.get("has_realization_candidate")),
        "has_controlled_delivery_candidate": _to_bool(context.get("has_controlled_delivery_candidate")),
        "source": str(host_context.get("source") or ""),
        "host_lane_hints": list(host_context.get("host_lane_hints") or []),
        "host_lane_hint": str(host_context.get("host_lane_hint") or ""),
        "readiness_basis": str(host_context.get("readiness_basis") or ""),
        "delivery_readiness": _clamp(host_context.get("delivery_readiness")),
        "reserve_level_hint": str(resource_budget.get("reserve_level") or host_context.get("reserve_level_hint") or ""),
        "recent_delivery_status": str(host_context.get("recent_delivery_status") or recent_delivery.get("status") or ""),
        "recent_delivery_success": _to_bool(host_context.get("recent_delivery_success", recent_delivery.get("success") or False)),
        "promotion_budget": str(host_context.get("promotion_budget") or "review_only"),
        "pending_realization_refs": list(host_context.get("pending_realization_refs") or []),
        "replay_inconsistency": _to_bool(maintenance_context.get("replay_inconsistency")),
        "idle_seconds": float(
            idle_window.get("idle_seconds")
            or maintenance_context.get("idle_seconds")
            or host_context.get("idle_seconds")
            or 0.0
        ),
    }


def derive_initiative_realization_outputs(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    runtime = dict(runtime_summary or {})
    context = extract_runtime_initiative_realization_context(runtime)
    host_context = extract_runtime_host_proactive_context(runtime)

    if not context and not host_context:
        return {
            "initiative_realization_context": {},
            "initiative_realization_delta": {},
            "commitment_fulfillment_candidates": [],
            "delivery_readiness_snapshot": {},
            "host_lane_hints": [],
            "controlled_delivery_candidate": None,
            "initiative_realization_audit_entries": [],
            "initiative_realization_writeback_candidate": None,
            "policy_hint_patch": {},
            "response_tendency": None,
        }

    if not context:
        has_host_signal = any(
            (
                bool(host_context.get("source")),
                bool(host_context.get("pending_realization_refs") or []),
                bool(host_context.get("host_lane_hint")),
                bool(host_context.get("host_lane_hints") or []),
                bool(host_context.get("readiness_basis")),
                float(host_context.get("delivery_readiness") or 0.0) > 0.0,
                float((runtime.get("idle_window") or {}).get("idle_seconds") or 0.0) >= 600.0,
                str((runtime.get("recent_delivery_outcome") or {}).get("status") or "").strip()
                in FAILURE_STATUSES,
            )
        )
        if not has_host_signal:
            return {
                "initiative_realization_context": {},
                "initiative_realization_delta": {},
                "commitment_fulfillment_candidates": [],
                "delivery_readiness_snapshot": {},
                "host_lane_hints": [],
                "controlled_delivery_candidate": None,
                "initiative_realization_audit_entries": [],
                "initiative_realization_writeback_candidate": None,
                "policy_hint_patch": {},
                "response_tendency": None,
            }

    maintenance_context = dict(runtime.get("maintenance_context") or {})
    resource_budget = dict(runtime.get("resource_budget_hint") or {})
    recent_delivery = dict(runtime.get("recent_delivery_outcome") or {})
    idle_window = dict(runtime.get("idle_window") or {})

    realization_summary = summarize_runtime_initiative_realization_context(runtime)

    dominant_mode = str(context.get("dominant_mode") or "review")
    selected_lane = str(context.get("selected_lane") or "review")
    realization_pressure = _clamp(context.get("realization_pressure"))
    fulfillment_readiness = _clamp(context.get("fulfillment_readiness"))
    hold_bias = _clamp(context.get("hold_bias"))
    failure_recovery_bias = _clamp(context.get("failure_recovery_bias"))
    continuity_confidence = _clamp(context.get("continuity_confidence"))
    active_commitments_count = int(context.get("active_commitments_count") or 0)
    ready_commitments_count = int(context.get("ready_commitments_count") or 0)
    pending_realization_refs = list(host_context.get("pending_realization_refs") or [])

    reserve_level = str(resource_budget.get("reserve_level") or host_context.get("reserve_level_hint") or "medium")
    recent_delivery_status = str(
        host_context.get("recent_delivery_status")
        or recent_delivery.get("status")
        or ""
    )
    recent_delivery_success = bool(host_context.get("recent_delivery_success") if "recent_delivery_success" in host_context else recent_delivery.get("success"))
    delivery_failure = recent_delivery_status in FAILURE_STATUSES or recent_delivery_success is False
    idle_seconds = float(idle_window.get("idle_seconds") or 0.0)
    continuation_gap = float(maintenance_context.get("continuity_gap") or 0.0)
    promotion_level = str(host_context.get("promotion_budget") or "review_only")
    if promotion_level not in ALLOWED_PROMOTION_LEVELS:
        promotion_level = "review_only"

    surface_reasons = []
    for reason, enabled in (
        ("low_realization_readiness", realization_pressure < 0.32),
        ("low_fulfillment_readiness", fulfillment_readiness < 0.35),
        ("high_hold_bias", hold_bias >= 0.62),
        ("high_failure_recovery_bias", failure_recovery_bias >= 0.58),
        ("low_continuity_confidence", continuity_confidence < 0.55),
        ("high_active_commitments", active_commitments_count > 0),
        ("low_reserve", reserve_level == "low"),
        ("delivery_failure", delivery_failure),
        ("extended_idle", idle_seconds >= 600.0),
        ("continuity_gap", continuation_gap > 0.2),
    ):
        if enabled:
            surface_reasons.append(reason)

    if context and not surface_reasons:
        should_surface = False
    elif host_context and not surface_reasons:
        should_surface = bool(host_context)
    else:
        should_surface = bool(surface_reasons)

    host_lane_hints = list(host_context.get("host_lane_hints") or [])
    host_lane_hint = str(host_context.get("host_lane_hint") or "")
    if host_lane_hint and host_lane_hint not in host_lane_hints:
        host_lane_hints.insert(0, host_lane_hint)
    if not host_lane_hints:
        host_lane_hints = ["host_proactive_outbox"]

    delivery_readiness_snapshot = {
        "contract_version": CONTRACT_VERSION,
        "owner_revision": context.get("owner_revision"),
        "last_revision_id": context.get("last_revision_id"),
        "dominant_mode": dominant_mode,
        "selected_lane": selected_lane,
        "realization_pressure": round(realization_pressure, 3),
        "fulfillment_readiness": round(fulfillment_readiness, 3),
        "hold_bias": round(hold_bias, 3),
        "failure_recovery_bias": round(failure_recovery_bias, 3),
        "continuity_confidence": round(continuity_confidence, 3),
        "active_commitments_count": active_commitments_count,
        "ready_commitments_count": ready_commitments_count,
        "has_realization_candidate": _to_bool(context.get("has_realization_candidate")),
        "has_controlled_delivery_candidate": _to_bool(context.get("has_controlled_delivery_candidate")),
        "reserve_level_hint": reserve_level,
        "recent_delivery_status": recent_delivery_status,
        "delivery_failure": delivery_failure,
    }

    commitment_fulfillment_candidates: list[Dict[str, Any]] = []
    controlled_delivery_candidate: Optional[Dict[str, Any]] = None
    initiative_realization_delta: Dict[str, Any] = {}
    audit_entries: list[Dict[str, Any]] = []
    writeback_candidate: Optional[Dict[str, Any]] = None
    policy_hint_patch: Dict[str, Any] = {}
    response_tendency: Optional[ResponseTendency] = None

    candidate_prefix = (
        str(context.get("last_revision_id") or context.get("owner_revision") or "host")
    )

    if should_surface:
        candidate_id_suffix = f"{candidate_prefix}"
        if context:
            commitment_fulfillment_candidates = [
                {
                    "candidate_id": f"commitment_fulfillment:{candidate_id_suffix}",
                    "target_mode": dominant_mode,
                    "active_commitments_count": active_commitments_count,
                    "ready_commitments_count": ready_commitments_count,
                    "continuity_confidence": round(continuity_confidence, 3),
                    "projection_gap": round(
                        abs(ready_commitments_count - active_commitments_count),
                        3,
                    ),
                    "required_gate": REQUIRED_WRITEBACK_GATE,
                    "proposal_only": True,
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "none",
                    "promotion_level": "controlled_axis" if promotion_level == "controlled_axis" else "review_only",
                    "surface_reasons": surface_reasons,
                    "source_refs": pending_realization_refs,
                }
            ]

        controlled_delivery_candidate = {
            "candidate_id": f"controlled_delivery_candidate:{candidate_id_suffix}",
            "candidate_label": "governed_controlled_delivery",
            "readiness_basis": str(host_context.get("readiness_basis") or "realization_continuity_review"),
            "delivery_readiness": _clamp(
                host_context.get("delivery_readiness", fulfillment_readiness)
            ),
            "host_lane_hint": host_lane_hints[0],
            "required_gate": REQUIRED_WRITEBACK_GATE,
            "proposal_only": True,
            "proposal_discipline": "proposal_only",
            "effect_scope": "proposal_only",
            "behavioral_authority": "none",
            "status": "proposed",
            "requested_effects": ["review_realization_lane"],
            "promotion_level": promotion_level,
            "source_refs": pending_realization_refs,
            "owner_revision": context.get("owner_revision"),
        }

        initiative_realization_delta = {
            "proposal_candidate_count": len(commitment_fulfillment_candidates) + int(controlled_delivery_candidate is not None),
            "surface_reasons": surface_reasons,
            "selected_mode": dominant_mode,
            "delivery_readiness": round(fulfillment_readiness, 3),
            "lane": selected_lane,
            "continuity_confidence": round(continuity_confidence, 3),
            "proposal_only": True,
        }
        audit_entries = [
            {
                "entry_type": "initiative_realization_contract_surface",
                "selected_lane": selected_lane,
                "dominant_mode": dominant_mode,
                "surface_reasons": surface_reasons,
                "proposal_only": True,
            }
        ]
        policy_hint_patch = {
            "initiative_realization_bias": "review_first" if selected_lane == "review" else selected_lane,
            "initiative_readiness_bias": "governed" if delivery_failure or hold_bias >= 0.62 else "normal",
            "initiative_continuity_bias": "repair" if continuity_confidence < 0.55 else "stable",
        }
        response_tendency = ResponseTendency(
            preferred_mode="defer" if selected_lane in {"hold", "review"} else "respond",
            preferred_tone="cautious" if delivery_failure or reserve_level == "low" else "supportive",
            certainty_bound="bounded",
            suggested_next_step="route realization proposals to controlled host-lane review",
            ask_needed=selected_lane in {"review", "hold"},
        )
        writeback_candidate = {
            "source": "proto_self_v2",
            "contract_version": CONTRACT_VERSION,
            "required_gate": REQUIRED_WRITEBACK_GATE,
            "proposal_only": True,
            "proposal_discipline": "proposal_only",
            "behavioral_authority": "none",
            "promotion_level": promotion_level,
            "owner_revision": context.get("owner_revision"),
            "surface_reasons": surface_reasons,
            "controlled_lane_hints": host_lane_hints,
            "source_refs": pending_realization_refs,
        }

    return {
        "initiative_realization_context": realization_summary,
        "initiative_realization_delta": initiative_realization_delta,
        "commitment_fulfillment_candidates": commitment_fulfillment_candidates,
        "delivery_readiness_snapshot": delivery_readiness_snapshot,
        "host_lane_hints": host_lane_hints,
        "controlled_delivery_candidate": controlled_delivery_candidate,
        "initiative_realization_audit_entries": audit_entries,
        "initiative_realization_writeback_candidate": writeback_candidate,
        "policy_hint_patch": policy_hint_patch,
        "response_tendency": response_tendency,
    }
