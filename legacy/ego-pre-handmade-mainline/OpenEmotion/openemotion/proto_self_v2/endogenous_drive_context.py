from __future__ import annotations

from typing import Any, Dict, Optional

from openemotion.proto_self.schemas import ResponseTendency


PROJECTION_FIELD = "runtime_summary.endogenous_drive_context"
PROJECTION_SEMANTICS = "bounded runtime projection of formal endogenous drive owner state"


def extract_runtime_endogenous_drive_context(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    raw = dict((runtime_summary or {}).get("endogenous_drive_context") or {})
    if not raw:
        return {}
    return {
        "schema_version": raw.get("schema_version"),
        "owner_revision": raw.get("owner_revision"),
        "last_revision_id": raw.get("last_revision_id"),
        "active_drives": list(raw.get("active_drives") or []),
        "homeostatic_signals": list(raw.get("homeostatic_signals") or []),
        "maintenance_debt": list(raw.get("maintenance_debt") or []),
        "priority_snapshot": dict(raw.get("priority_snapshot") or {}),
        "summary": dict(raw.get("summary") or {}),
        "self_maintenance_candidate": raw.get("self_maintenance_candidate"),
    }


def summarize_runtime_endogenous_drive_context(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    context = extract_runtime_endogenous_drive_context(runtime_summary)
    return {
        "present": bool(context),
        "projection_field": PROJECTION_FIELD,
        "projection_semantics": PROJECTION_SEMANTICS,
        "schema_version": context.get("schema_version"),
        "owner_revision": context.get("owner_revision"),
        "last_revision_id": context.get("last_revision_id"),
        "active_drive_count": len(context.get("active_drives") or []),
        "signal_count": len(context.get("homeostatic_signals") or []),
        "maintenance_debt_count": len(context.get("maintenance_debt") or []),
        "dominant_drive": (context.get("priority_snapshot") or {}).get("dominant_drive"),
        "maintenance_candidate_present": bool(context.get("self_maintenance_candidate")),
    }


def derive_endogenous_drive_outputs(runtime_summary: Dict[str, Any] | None) -> Dict[str, Any]:
    runtime = dict(runtime_summary or {})
    context = extract_runtime_endogenous_drive_context(runtime)
    if not context:
        return {
            "drive_context": {},
            "endogenous_drive_delta": {},
            "drive_state_snapshot": {},
            "priority_snapshot": {},
            "candidate_bias_terms": {},
            "self_maintenance_candidate": None,
            "drive_audit_entries": [],
            "policy_hint_patch": {},
            "response_tendency": None,
        }

    priority_snapshot = dict(context.get("priority_snapshot") or {})
    bias_terms = dict(priority_snapshot.get("bias_terms") or {})
    if not bias_terms:
        for item in list(context.get("active_drives") or []):
            drive_id = str(item.get("drive_id") or "")
            if drive_id:
                bias_terms[drive_id] = float(item.get("pressure") or 0.0)

    recent_delivery = dict(runtime.get("recent_delivery_outcome") or {})
    maintenance_context = dict(runtime.get("maintenance_context") or {})
    resource_budget = dict(runtime.get("resource_budget_hint") or {})
    idle_window = dict(runtime.get("idle_window") or {})
    caution_score = max(
        float(bias_terms.get("verification") or 0.0),
        float(bias_terms.get("conservation") or 0.0),
    )
    closure_score = float(bias_terms.get("completion") or 0.0)
    repair_score = float(bias_terms.get("repair") or 0.0)

    self_maintenance_candidate = context.get("self_maintenance_candidate")
    if self_maintenance_candidate is None and resource_budget.get("reserve_level") == "low":
        self_maintenance_candidate = {
            "category": "self_maintenance",
            "dominant_issue": "reserve_protection",
            "priority": 0.72,
            "status": {
                "urgent_maintenance": 0,
                "homeostatic_issues": len(context.get("homeostatic_signals") or []),
                "total_maintenance_debt": (context.get("summary") or {}).get("total_maintenance_debt", 0.0),
                "should_maintain": True,
            },
        }

    policy_hint_patch: Dict[str, Any] = {}
    if caution_score >= 0.45 or resource_budget.get("reserve_level") == "low":
        policy_hint_patch["risk_bias"] = "high"
    if closure_score >= 0.35:
        policy_hint_patch["closure_bias"] = True
    if self_maintenance_candidate:
        policy_hint_patch["maintenance_bias"] = "elevated"

    response_tendency: Optional[ResponseTendency] = None
    if self_maintenance_candidate:
        response_tendency = ResponseTendency(
            preferred_mode="repair",
            preferred_tone="cautious" if caution_score >= 0.45 else "calm",
            certainty_bound="bounded",
            suggested_next_step="prioritize governed self-maintenance before expanding scope",
            ask_needed=False,
        )
    elif caution_score >= 0.45:
        response_tendency = ResponseTendency(
            preferred_mode="respond",
            preferred_tone="cautious",
            certainty_bound="bounded",
            suggested_next_step="reduce risk before taking the next irreversible step",
            ask_needed=False,
        )
    elif closure_score >= 0.35:
        response_tendency = ResponseTendency(
            preferred_mode="respond",
            preferred_tone="direct",
            certainty_bound="bounded",
            suggested_next_step="close the active loop before opening a new one",
            ask_needed=False,
        )

    endogenous_drive_delta: Dict[str, Any] = {}
    drive_audit_entries = []
    delivery_failed = recent_delivery.get("success") is False or recent_delivery.get("status") in {"failed", "blocked"}
    if delivery_failed:
        endogenous_drive_delta.setdefault("drive_adjustments", []).append(
            {
                "drive_type": "repair",
                "intensity_delta": 0.1,
                "cause": "recent_delivery_outcome:failure",
                "evidence": {"status": recent_delivery.get("status")},
            }
        )
        drive_audit_entries.append({"kind": "drive_adjustment", "reason": "recent_delivery_outcome:failure"})
    maintenance_debt_increment = float(maintenance_context.get("maintenance_debt_increment") or 0.0)
    if maintenance_context.get("replay_inconsistency") or maintenance_debt_increment > 0.0:
        endogenous_drive_delta.setdefault("maintenance_debts", []).append(
            {
                "category": str(maintenance_context.get("debt_category") or "replay_verification"),
                "amount": maintenance_debt_increment or 0.2,
                "priority": float(maintenance_context.get("debt_priority") or 0.8),
                "source": "maintenance_context",
            }
        )
        drive_audit_entries.append({"kind": "maintenance_debt", "reason": "maintenance_context"})
    continuity_signal = maintenance_context.get("continuity_signal")
    if continuity_signal is not None:
        endogenous_drive_delta.setdefault("homeostatic_updates", []).append(
            {
                "signal_id": "continuity_quality",
                "observed_value": float(continuity_signal),
            }
        )
        drive_audit_entries.append({"kind": "homeostatic_update", "reason": "continuity_signal"})

    drive_state_snapshot = {
        "schema_version": context.get("schema_version"),
        "owner_revision": context.get("owner_revision"),
        "last_revision_id": context.get("last_revision_id"),
        "summary": dict(context.get("summary") or {}),
        "idle_window": {"idle_seconds": idle_window.get("idle_seconds")},
    }

    return {
        "drive_context": summarize_runtime_endogenous_drive_context(runtime),
        "endogenous_drive_delta": endogenous_drive_delta,
        "drive_state_snapshot": drive_state_snapshot,
        "priority_snapshot": priority_snapshot,
        "candidate_bias_terms": bias_terms,
        "self_maintenance_candidate": self_maintenance_candidate,
        "drive_audit_entries": drive_audit_entries,
        "policy_hint_patch": policy_hint_patch,
        "response_tendency": response_tendency,
        "repair_score": repair_score,
    }
