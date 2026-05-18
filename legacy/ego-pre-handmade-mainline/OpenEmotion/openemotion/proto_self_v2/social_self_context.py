from __future__ import annotations

from typing import Any, Dict, Optional

from openemotion.proto_self.schemas import ResponseTendency
from openemotion.social_self import (
    REQUIRED_WRITEBACK_GATE,
    RUNTIME_LOCAL_PROJECTION_FIELD,
    RUNTIME_LOCAL_PROJECTION_SEMANTICS,
)


PROJECTION_FIELD = "runtime_summary.social_self_context"
HOST_HINT_FIELD = "runtime_summary.social_context"
CONTRACT_VERSION = "mvp17.social_contract.v1"
PROJECTION_SEMANTICS = RUNTIME_LOCAL_PROJECTION_SEMANTICS

BOUNDED_CONTEXT_FIELDS = (
    "schema_version",
    "owner_revision",
    "last_revision_id",
    "active_relations_count",
    "trust_signal_max",
    "open_commitment_count",
    "breached_commitment_count",
    "pending_repair_count",
    "boundary_caution_max",
    "recent_counterpart_ids",
)

HOST_HINT_FIELDS = (
    "source",
    "counterpart_id",
    "relationship_event",
    "relationship_continuity",
    "trust_drift",
    "commitment_event",
    "commitment_breach",
    "repair_outcome",
    "unresolved_repair",
    "boundary_signal",
    "promotion_budget",
)

ALLOWED_PROMOTION_LEVELS = {"shadow_only", "review_only", "controlled_axis"}


def extract_runtime_social_self_context(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    raw = dict((runtime_summary or {}).get("social_self_context") or {})
    if not raw:
        return {}
    return {key: raw[key] for key in BOUNDED_CONTEXT_FIELDS if key in raw}


def extract_runtime_social_context(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    raw = dict((runtime_summary or {}).get("social_context") or {})
    if not raw:
        return {}
    return {key: raw[key] for key in HOST_HINT_FIELDS if key in raw}


def _resolve_counterpart_id(context: Dict[str, Any], host_context: Dict[str, Any]) -> str:
    if host_context.get("counterpart_id"):
        return str(host_context["counterpart_id"])
    recent_counterparts = list(context.get("recent_counterpart_ids") or [])
    if recent_counterparts:
        return str(recent_counterparts[0])
    return ""


def summarize_runtime_social_self_context(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    context = extract_runtime_social_self_context(runtime_summary)
    host_context = extract_runtime_social_context(runtime_summary)
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
        "active_relations_count": int(context.get("active_relations_count") or 0),
        "trust_signal_max": float(context.get("trust_signal_max") or 0.0),
        "open_commitment_count": int(context.get("open_commitment_count") or 0),
        "breached_commitment_count": int(context.get("breached_commitment_count") or 0),
        "pending_repair_count": int(context.get("pending_repair_count") or 0),
        "boundary_caution_max": float(context.get("boundary_caution_max") or 0.0),
        "recent_counterpart_ids": list(context.get("recent_counterpart_ids") or []),
        "source": str(host_context.get("source") or ""),
        "counterpart_id": _resolve_counterpart_id(context, host_context),
        "relationship_event": str(host_context.get("relationship_event") or ""),
        "relationship_continuity": str(host_context.get("relationship_continuity") or ""),
        "trust_drift": float(host_context.get("trust_drift") or 0.0),
        "commitment_event": str(host_context.get("commitment_event") or ""),
        "commitment_breach": bool(host_context.get("commitment_breach")),
        "repair_outcome": str(host_context.get("repair_outcome") or ""),
        "unresolved_repair": bool(host_context.get("unresolved_repair")),
        "boundary_signal": str(host_context.get("boundary_signal") or ""),
        "promotion_budget": str(host_context.get("promotion_budget") or "review_only"),
    }


def derive_social_outputs(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    runtime = dict(runtime_summary or {})
    context = extract_runtime_social_self_context(runtime)
    host_context = extract_runtime_social_context(runtime)
    if not context and not host_context:
        return {
            "social_context": {},
            "social_self_delta": {},
            "relation_update_candidates": [],
            "trust_commitment_snapshot": {},
            "social_policy_hints": {},
            "repair_proposal_candidates": [],
            "social_writeback_candidate": None,
            "policy_hint_patch": {},
            "response_tendency": None,
        }

    counterpart_id = _resolve_counterpart_id(context, host_context)
    trust_signal_max = float(context.get("trust_signal_max") or 0.0)
    open_commitment_count = int(context.get("open_commitment_count") or 0)
    breached_commitment_count = int(context.get("breached_commitment_count") or 0)
    pending_repair_count = int(context.get("pending_repair_count") or 0)
    boundary_caution_max = float(context.get("boundary_caution_max") or 0.0)
    trust_drift = float(host_context.get("trust_drift") or 0.0)
    commitment_event = str(host_context.get("commitment_event") or "")
    commitment_breach = (
        bool(host_context.get("commitment_breach"))
        or commitment_event == "breach"
        or breached_commitment_count > 0
    )
    unresolved_repair = bool(host_context.get("unresolved_repair")) or pending_repair_count > 0
    repair_outcome = str(host_context.get("repair_outcome") or "")
    relationship_continuity = str(host_context.get("relationship_continuity") or "")
    if not relationship_continuity:
        relationship_continuity = "strained" if (commitment_breach or unresolved_repair) else "stable"
    boundary_signal = str(host_context.get("boundary_signal") or "")
    if not boundary_signal:
        if boundary_caution_max >= 0.75:
            boundary_signal = "firm"
        elif boundary_caution_max >= 0.45:
            boundary_signal = "cautious"
        else:
            boundary_signal = "open"
    promotion_level = str(host_context.get("promotion_budget") or "review_only")
    if promotion_level not in ALLOWED_PROMOTION_LEVELS:
        promotion_level = "review_only"

    surface_reasons = []
    for reason, enabled in (
        ("trust_drift", trust_drift <= -0.1),
        ("commitment_breach", commitment_breach),
        ("unresolved_repair", unresolved_repair),
        ("boundary_caution", boundary_caution_max >= 0.45),
        ("repair_outcome", repair_outcome in {"failed", "blocked"}),
        ("relationship_strain", relationship_continuity in {"strained", "repairing", "paused"}),
    ):
        if enabled:
            surface_reasons.append(reason)

    should_surface = bool(surface_reasons)
    social_context = summarize_runtime_social_self_context(runtime)
    trust_commitment_snapshot = {
        "contract_version": CONTRACT_VERSION,
        "owner_revision": context.get("owner_revision"),
        "last_revision_id": context.get("last_revision_id"),
        "counterpart_id": counterpart_id,
        "active_relations_count": int(context.get("active_relations_count") or 0),
        "trust_signal_max": round(trust_signal_max, 3),
        "open_commitment_count": open_commitment_count,
        "breached_commitment_count": breached_commitment_count,
        "pending_repair_count": pending_repair_count,
        "boundary_caution_max": round(boundary_caution_max, 3),
        "relationship_continuity": relationship_continuity,
        "trust_drift": round(trust_drift, 3),
    }
    social_policy_hints = {
        "relationship_continuity": relationship_continuity,
        "trust_bias": "guarded" if trust_drift <= -0.1 else "normal",
        "commitment_guard": "strict" if commitment_breach else "normal",
        "repair_bias": "elevated" if unresolved_repair or commitment_breach else "normal",
        "boundary_mode": boundary_signal,
        "counterpart_id": counterpart_id,
    }

    relation_update_candidates = []
    repair_proposal_candidates = []
    social_writeback_candidate = None
    social_self_delta: Dict[str, Any] = {}
    policy_hint_patch: Dict[str, Any] = {}
    response_tendency: Optional[ResponseTendency] = None

    if should_surface:
        candidate_suffix = counterpart_id or "unknown"
        relation_update_candidates = [
            {
                "candidate_id": f"relation_update:{candidate_suffix}:{context.get('owner_revision') or 0}",
                "counterpart_id": counterpart_id,
                "relationship_event": str(host_context.get("relationship_event") or "social_adjustment"),
                "relationship_continuity": relationship_continuity,
                "required_gate": REQUIRED_WRITEBACK_GATE,
                "proposal_discipline": "proposal_only",
                "behavioral_authority": "none",
                "promotion_level": promotion_level,
            }
        ]
        repair_proposal_candidates = [
            {
                "candidate_id": f"repair_candidate:{candidate_suffix}:{len(surface_reasons)}",
                "counterpart_id": counterpart_id,
                "reason": "social_repair",
                "surface_reasons": surface_reasons,
                "required_gate": REQUIRED_WRITEBACK_GATE,
                "proposal_discipline": "proposal_only",
                "behavioral_authority": "none",
                "promotion_level": promotion_level,
            }
        ]
        social_writeback_candidate = {
            "source": "proto_self_v2",
            "contract_version": CONTRACT_VERSION,
            "counterpart_id": counterpart_id,
            "required_gate": REQUIRED_WRITEBACK_GATE,
            "proposal_discipline": "proposal_only",
            "behavioral_authority": "none",
            "promotion_level": promotion_level,
            "surface_reasons": surface_reasons,
            "owner_revision": context.get("owner_revision"),
        }
        social_self_delta = {
            "proposal_candidate_count": len(repair_proposal_candidates),
            "counterpart_id": counterpart_id,
            "relationship_continuity": relationship_continuity,
            "surface_reasons": surface_reasons,
        }
        policy_hint_patch = {
            "social_trust_bias": social_policy_hints["trust_bias"],
            "social_repair_bias": social_policy_hints["repair_bias"],
            "social_boundary_bias": "cautious"
            if boundary_signal in {"cautious", "firm", "repair_only"}
            else "open",
            "social_commitment_guard": social_policy_hints["commitment_guard"],
        }
        response_tendency = ResponseTendency(
            preferred_mode="repair" if (unresolved_repair or commitment_breach) else "respond",
            preferred_tone="cautious",
            certainty_bound="bounded",
            suggested_next_step="route trust, commitment, and repair adjustments through the governed social writeback path",
            ask_needed=False,
        )

    return {
        "social_context": social_context,
        "social_self_delta": social_self_delta,
        "relation_update_candidates": relation_update_candidates,
        "trust_commitment_snapshot": trust_commitment_snapshot,
        "social_policy_hints": social_policy_hints,
        "repair_proposal_candidates": repair_proposal_candidates,
        "social_writeback_candidate": social_writeback_candidate,
        "policy_hint_patch": policy_hint_patch,
        "response_tendency": response_tendency,
    }
