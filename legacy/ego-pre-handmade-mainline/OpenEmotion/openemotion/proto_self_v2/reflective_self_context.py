from __future__ import annotations

from typing import Any, Dict, Optional

from openemotion.proto_self.schemas import ResponseTendency
from openemotion.reflective_self import (
    RUNTIME_LOCAL_PROJECTION_FIELD,
    RUNTIME_LOCAL_PROJECTION_SEMANTICS,
)


PROJECTION_FIELD = "runtime_summary.reflective_self_context"
PROJECTION_SEMANTICS = RUNTIME_LOCAL_PROJECTION_SEMANTICS

BOUNDED_CONTEXT_FIELDS = (
    "schema_version",
    "owner_revision",
    "last_revision_id",
    "reflection_pressure",
    "pending_reflections",
    "unresolved_items",
    "proposal_candidates",
    "top_target_ids",
)


def extract_runtime_reflective_self_context(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    raw = dict((runtime_summary or {}).get("reflective_self_context") or {})
    if not raw:
        return {}
    return {key: raw[key] for key in BOUNDED_CONTEXT_FIELDS if key in raw}


def summarize_runtime_reflective_self_context(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    context = extract_runtime_reflective_self_context(runtime_summary)
    return {
        "present": bool(context),
        "projection_field": PROJECTION_FIELD,
        "projection_semantics": PROJECTION_SEMANTICS,
        "runtime_local_projection_field": RUNTIME_LOCAL_PROJECTION_FIELD,
        "schema_version": context.get("schema_version"),
        "owner_revision": context.get("owner_revision"),
        "last_revision_id": context.get("last_revision_id"),
        "reflection_pressure": float(context.get("reflection_pressure") or 0.0),
        "pending_reflections": int(context.get("pending_reflections") or 0),
        "unresolved_items": int(context.get("unresolved_items") or 0),
        "proposal_candidates": int(context.get("proposal_candidates") or 0),
        "top_target_ids": list(context.get("top_target_ids") or []),
    }


def derive_reflective_self_outputs(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    runtime = dict(runtime_summary or {})
    context = extract_runtime_reflective_self_context(runtime)
    if not context:
        return {
            "reflection_context": {},
            "reflective_self_delta": {},
            "revision_proposal_candidates": [],
            "confidence_adjustment_hints": {},
            "maintenance_priority_hints": {},
            "reflection_writeback_candidate": None,
            "policy_hint_patch": {},
            "response_tendency": None,
        }

    reflection_pressure = float(context.get("reflection_pressure") or 0.0)
    pending_reflections = int(context.get("pending_reflections") or 0)
    unresolved_items = int(context.get("unresolved_items") or 0)
    proposal_candidates = int(context.get("proposal_candidates") or 0)
    top_target_ids = list(context.get("top_target_ids") or [])

    maintenance_context = dict(runtime.get("maintenance_context") or {})
    recent_delivery = dict(runtime.get("recent_delivery_outcome") or {})
    replay_inconsistency = bool(maintenance_context.get("replay_inconsistency"))
    delivery_failed = recent_delivery.get("success") is False or recent_delivery.get("status") in {"failed", "blocked"}

    should_surface = (
        reflection_pressure >= 0.35
        or unresolved_items > 0
        or proposal_candidates > 0
        or replay_inconsistency
        or delivery_failed
    )

    revision_proposal_candidates = []
    reflection_writeback_candidate = None
    reflective_self_delta: Dict[str, Any] = {}
    confidence_adjustment_hints: Dict[str, Any] = {}
    maintenance_priority_hints: Dict[str, Any] = {}
    policy_hint_patch: Dict[str, Any] = {}
    response_tendency: Optional[ResponseTendency] = None

    if should_surface:
        target_id = top_target_ids[0] if top_target_ids else "reflection:unresolved"
        revision_proposal_candidates = [
            {
                "candidate_id": f"reflection_candidate:{target_id}",
                "target_id": target_id,
                "reason": "reflective_pressure",
                "required_gate": "reflection_writeback_gate",
                "proposal_discipline": "proposal_only",
                "effect_scope": "proposal_only",
            }
        ]
        reflection_writeback_candidate = {
            "source": "proto_self_v2",
            "target_ids": top_target_ids[:3],
            "required_gate": "reflection_writeback_gate",
            "proposal_discipline": "proposal_only",
            "behavioral_authority": "none",
        }
        reflective_self_delta = {
            "revision_proposals": revision_proposal_candidates,
            "target_ids": top_target_ids[:3],
            "surface_reasons": [
                reason
                for reason, enabled in (
                    ("reflection_pressure", reflection_pressure >= 0.35),
                    ("unresolved_items", unresolved_items > 0),
                    ("proposal_candidates", proposal_candidates > 0),
                    ("replay_inconsistency", replay_inconsistency),
                    ("delivery_failed", delivery_failed),
                )
                if enabled
            ],
        }
        confidence_adjustment_hints = {
            "certainty_bound": "bounded",
            "reason": "reflective_pressure_present",
            "pressure": round(reflection_pressure, 3),
        }
        maintenance_priority_hints = {
            "reflection_followup_priority": "elevated" if unresolved_items > 0 or pending_reflections > 0 else "normal",
            "unresolved_items": unresolved_items,
        }
        policy_hint_patch["reflection_bias"] = "elevated"
        if unresolved_items > 0:
            policy_hint_patch["uncertainty_bias"] = "elevated"
        response_tendency = ResponseTendency(
            preferred_mode="respond",
            preferred_tone="cautious",
            certainty_bound="bounded",
            suggested_next_step="keep reflection outputs proposal-disciplined and evidence-linked",
            ask_needed=False,
        )

    return {
        "reflection_context": summarize_runtime_reflective_self_context(runtime),
        "reflective_self_delta": reflective_self_delta,
        "revision_proposal_candidates": revision_proposal_candidates,
        "confidence_adjustment_hints": confidence_adjustment_hints,
        "maintenance_priority_hints": maintenance_priority_hints,
        "reflection_writeback_candidate": reflection_writeback_candidate,
        "policy_hint_patch": policy_hint_patch,
        "response_tendency": response_tendency,
    }
