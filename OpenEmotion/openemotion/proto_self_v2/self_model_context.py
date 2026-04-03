from __future__ import annotations

from typing import Any, Dict

from openemotion.self_model.model import (
    PHASE1_ALLOWED_PROOF_LEVERS,
    PHASE1_AUTHORITATIVE_FIELDS,
    PHASE1_LEGACY_REFERENCE_ONLY_FIELDS,
    RUNTIME_LOCAL_PROJECTION_FIELD,
    RUNTIME_LOCAL_PROJECTION_SEMANTICS,
)


def extract_runtime_self_model_context(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    raw = dict((runtime_summary or {}).get("self_model_context") or {})
    if not raw:
        return {}
    return {
        key: raw[key]
        for key in PHASE1_AUTHORITATIVE_FIELDS
        if key in raw and key not in PHASE1_LEGACY_REFERENCE_ONLY_FIELDS
    }


def summarize_runtime_self_model_context(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    context = extract_runtime_self_model_context(runtime_summary)
    return {
        "present": bool(context),
        "projection_field": RUNTIME_LOCAL_PROJECTION_FIELD,
        "projection_semantics": RUNTIME_LOCAL_PROJECTION_SEMANTICS,
        "authoritative_fields": list(context.keys()),
        "allowed_proof_levers_present": [
            key for key in PHASE1_ALLOWED_PROOF_LEVERS if key in context
        ],
        "identity_handle": context.get("identity_handle"),
        "schema_version": context.get("schema_version"),
        "owner_last_modified_at": context.get("last_modified_at"),
        "capability_count": len(context.get("capabilities") or []),
        "limitation_count": len(context.get("limitations") or []),
        "active_goals_count": len(context.get("active_goals") or []),
        "standing_commitments_count": len(context.get("standing_commitments") or []),
        "confidence_domains_count": len(context.get("confidence_by_domain") or {}),
        "known_unknowns_count": len(context.get("known_unknowns") or []),
    }
