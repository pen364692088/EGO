"""Bounded initiative proposal primitive for EgoOperator.

This module does not schedule background work and does not send messages. It
only defines a candidate-local contract for proactive ideas that still require
operator approval before any side effect can happen.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict


INITIATIVE_PROPOSAL_SCHEMA = "ego_operator.initiative_proposal.v1"
CLAIM_CEILING = "bounded initiative proposal only; not autonomy or consciousness proof"
MAX_EXPIRY_SECONDS = 7 * 24 * 60 * 60
DEFAULT_BUDGET = {
    "max_candidates": 1,
    "max_tool_calls": 0,
    "max_runtime_seconds": 30,
    "requires_operator_approval": True,
}
ALLOWED_APPROVAL_STATES = {
    "pending_operator_approval",
    "approved",
    "rejected",
    "expired",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _bounded(text: str, max_chars: int = 800) -> str:
    clean = (text or "").strip()
    if len(clean) <= max_chars:
        return clean
    return clean[:max_chars] + "\n...[truncated]"


def normalize_initiative_budget(budget: Dict[str, Any] | None = None) -> Dict[str, Any]:
    merged = dict(DEFAULT_BUDGET)
    if budget:
        for key in DEFAULT_BUDGET:
            if key in budget:
                merged[key] = budget[key]
    merged["max_candidates"] = max(0, min(int(merged.get("max_candidates") or 0), 3))
    merged["max_tool_calls"] = max(0, min(int(merged.get("max_tool_calls") or 0), 3))
    merged["max_runtime_seconds"] = max(1, min(int(merged.get("max_runtime_seconds") or 1), 300))
    merged["requires_operator_approval"] = True
    return merged


@dataclass(frozen=True)
class InitiativeProposal:
    proposal_id: str
    reason: str
    trigger: str
    candidate_message: str
    budget: Dict[str, Any]
    expiry: str
    approval_state: str = "pending_operator_approval"
    schema_version: str = INITIATIVE_PROPOSAL_SCHEMA
    kind: str = "candidate_bounded_initiative"
    source: str = "ego_operator.primitives.initiative"
    created_at: str = field(default_factory=lambda: _iso(_utc_now()))
    claim_ceiling: str = CLAIM_CEILING
    side_effects: str = "forbidden_until_operator_approval"
    state_mutation: str = "forbidden"
    reply_decision: str = "forbidden"
    canonical_truth: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_initiative_proposal(
    *,
    proposal_id: str,
    reason: str,
    trigger: str,
    candidate_message: str,
    budget: Dict[str, Any] | None = None,
    expiry_seconds: int = 3600,
    approval_state: str = "pending_operator_approval",
    now: datetime | None = None,
) -> Dict[str, Any]:
    errors = []
    clean_reason = _bounded(reason, 500)
    clean_trigger = _bounded(trigger, 500)
    clean_message = _bounded(candidate_message, 1000)
    if not proposal_id.strip():
        errors.append("proposal_id_required")
    if not clean_reason:
        errors.append("reason_required")
    if not clean_trigger:
        errors.append("trigger_required")
    if not clean_message:
        errors.append("candidate_message_required")
    if approval_state not in ALLOWED_APPROVAL_STATES:
        errors.append(f"invalid_approval_state:{approval_state}")
    try:
        expiry_delta = int(expiry_seconds)
    except (TypeError, ValueError):
        expiry_delta = -1
    if expiry_delta <= 0 or expiry_delta > MAX_EXPIRY_SECONDS:
        errors.append("expiry_seconds_out_of_bounds")

    normalized_budget = normalize_initiative_budget(budget)
    if errors:
        return {
            "status": "blocked",
            "schema_version": INITIATIVE_PROPOSAL_SCHEMA,
            "errors": errors,
            "claim_ceiling": CLAIM_CEILING,
        }

    current = now or _utc_now()
    proposal = InitiativeProposal(
        proposal_id=proposal_id.strip(),
        reason=clean_reason,
        trigger=clean_trigger,
        candidate_message=clean_message,
        budget=normalized_budget,
        expiry=_iso(current + timedelta(seconds=expiry_delta)),
        approval_state=approval_state,
        created_at=_iso(current),
    )
    return {"status": "ok", "proposal": proposal.to_dict()}


def validate_initiative_proposal(payload: Dict[str, Any]) -> Dict[str, Any]:
    proposal = payload.get("proposal") if isinstance(payload.get("proposal"), dict) else payload
    errors = []
    if proposal.get("schema_version") != INITIATIVE_PROPOSAL_SCHEMA:
        errors.append("schema_version_mismatch")
    for key in ("proposal_id", "reason", "trigger", "candidate_message", "expiry", "approval_state"):
        if not str(proposal.get(key) or "").strip():
            errors.append(f"{key}_required")
    if proposal.get("approval_state") not in ALLOWED_APPROVAL_STATES:
        errors.append("approval_state_invalid")
    budget = proposal.get("budget") if isinstance(proposal.get("budget"), dict) else {}
    if budget.get("requires_operator_approval") is not True:
        errors.append("operator_approval_required")
    if proposal.get("side_effects") != "forbidden_until_operator_approval":
        errors.append("side_effect_boundary_missing")
    if proposal.get("state_mutation") != "forbidden" or proposal.get("reply_decision") != "forbidden":
        errors.append("proposal_must_not_mutate_or_decide_reply")
    if proposal.get("canonical_truth") is not False:
        errors.append("canonical_truth_must_be_false")
    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "claim_ceiling": CLAIM_CEILING,
    }
