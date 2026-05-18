from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .model import (
    FORMAL_OWNER_SCHEMA_VERSION,
    PHASE1_AUTHORITATIVE_FIELDS,
    PHASE1_LEGACY_REFERENCE_ONLY_FIELDS,
    SelfModel,
)
from .store import SelfModelRevisionRecord, SelfModelStore


ALLOW_WRITEBACK = "allow_writeback"
HOLD_FOR_REVIEW = "hold_for_review"
REJECT = "reject"
ROLLBACK_TO_LAST_STABLE = "rollback_to_last_stable"

ALLOWED_UPDATE_MODES = (
    "append_observation",
    "revise_tendency",
    "resolve_tension",
    "promote_to_stable_trait",
    "mark_for_review",
    "rollback_revision",
)

WRITABLE_AUTHORITATIVE_FIELDS = tuple(
    field_name
    for field_name in PHASE1_AUTHORITATIVE_FIELDS
    if field_name
    not in {
        "schema_version",
        "identity_handle",
        "created_at",
        "last_modified_at",
        "modification_audit_trail",
    }
)

HARD_INVARIANT_FIELDS = (
    "identity_handle",
    "schema_version",
    "tool_authority_boundary",
    "created_at",
)

STABLE_DEFAULT_FIELDS = (
    "capabilities",
    "limitations",
    "standing_commitments",
    "dependency_map",
)

EVOLVABLE_FIELDS = (
    "active_goals",
    "confidence_by_domain",
    "known_unknowns",
)

_CONFIDENCE_RANK = {
    "low": 0,
    "bounded": 1,
    "medium": 1,
    "stable": 2,
    "high": 2,
    "critical": 3,
}


@dataclass(frozen=True)
class InvariantViolation:
    field_path: str
    invariant_class: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_path": self.field_path,
            "invariant_class": self.invariant_class,
            "message": self.message,
        }


@dataclass(frozen=True)
class SelfModelUpdateRequest:
    delta: Dict[str, Any]
    update_mode: str
    update_source: str
    trace_reference: str
    confidence_class: str
    supporting_evidence: List[str]
    candidate_id: Optional[str] = None


@dataclass(frozen=True)
class DriftAssessment:
    drift_detected: bool
    drift_level: str
    recommended_verdict: str
    changed_fields: List[str]
    stable_default_changes: List[str]
    evolvable_changes: List[str]
    revision_oscillation_rate: float
    unsupported_identity_claim_rate: float
    continuity_break_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "drift_detected": self.drift_detected,
            "drift_level": self.drift_level,
            "recommended_verdict": self.recommended_verdict,
            "changed_fields": list(self.changed_fields),
            "stable_default_changes": list(self.stable_default_changes),
            "evolvable_changes": list(self.evolvable_changes),
            "revision_oscillation_rate": self.revision_oscillation_rate,
            "unsupported_identity_claim_rate": self.unsupported_identity_claim_rate,
            "continuity_break_count": self.continuity_break_count,
        }


@dataclass(frozen=True)
class SelfModelUpdateDecision:
    gate_verdict: str
    accepted: bool
    changed_fields: List[str]
    before_snapshot: Dict[str, Any]
    after_snapshot: Dict[str, Any]
    invariant_violations: List[InvariantViolation]
    drift_assessment: DriftAssessment
    request: SelfModelUpdateRequest

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_verdict": self.gate_verdict,
            "accepted": self.accepted,
            "changed_fields": list(self.changed_fields),
            "before_snapshot": dict(self.before_snapshot),
            "after_snapshot": dict(self.after_snapshot),
            "invariant_violations": [item.to_dict() for item in self.invariant_violations],
            "drift_assessment": self.drift_assessment.to_dict(),
            "request": {
                "delta": dict(self.request.delta),
                "update_mode": self.request.update_mode,
                "update_source": self.request.update_source,
                "trace_reference": self.request.trace_reference,
                "confidence_class": self.request.confidence_class,
                "supporting_evidence": list(self.request.supporting_evidence),
                "candidate_id": self.request.candidate_id,
            },
        }


@dataclass(frozen=True)
class SelfModelWritebackResult:
    decision: SelfModelUpdateDecision
    revision: Optional[SelfModelRevisionRecord]
    stable_snapshot_mutated: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.to_dict(),
            "revision": self.revision.to_dict() if self.revision else None,
            "stable_snapshot_mutated": self.stable_snapshot_mutated,
        }


def _snapshot(model_or_snapshot: SelfModel | Dict[str, Any] | None) -> Dict[str, Any]:
    if model_or_snapshot is None:
        return {}
    if isinstance(model_or_snapshot, SelfModel):
        return model_or_snapshot.to_dict()
    return dict(model_or_snapshot)


def _deep_merge(base: Any, patch: Any) -> Any:
    if isinstance(base, dict) and isinstance(patch, dict):
        merged = dict(base)
        for key, value in patch.items():
            merged[key] = _deep_merge(base.get(key), value)
        return merged
    return patch


def _top_level_changed_fields(before_snapshot: Dict[str, Any], after_snapshot: Dict[str, Any]) -> List[str]:
    changed: List[str] = []
    for field_name in sorted(set(before_snapshot.keys()) | set(after_snapshot.keys())):
        if before_snapshot.get(field_name) != after_snapshot.get(field_name):
            changed.append(field_name)
    return changed


def _normalize_confidence_class(confidence_class: str) -> str:
    normalized = (confidence_class or "").strip().lower()
    if normalized not in _CONFIDENCE_RANK:
        return "low"
    return normalized


def _confidence_rank(confidence_class: str) -> int:
    return _CONFIDENCE_RANK[_normalize_confidence_class(confidence_class)]


def _is_governance_revision(request: SelfModelUpdateRequest) -> bool:
    return request.update_mode == "rollback_revision" or request.update_source.startswith("governance_")


def _extract_tool_boundary(snapshot: Dict[str, Any]) -> Dict[str, List[str]]:
    boundary = dict(snapshot.get("tool_authority_boundary") or {})
    return {
        "current_allowed_tools": list(boundary.get("current_allowed_tools") or []),
        "restricted_tools": list(boundary.get("restricted_tools") or []),
        "forbidden_tools": list(boundary.get("forbidden_tools") or []),
    }


def check_identity_invariants(
    before_model: SelfModel | Dict[str, Any] | None,
    after_model: SelfModel | Dict[str, Any],
    *,
    request: Optional[SelfModelUpdateRequest] = None,
) -> List[InvariantViolation]:
    before_snapshot = _snapshot(before_model)
    after_snapshot = _snapshot(after_model)
    violations: List[InvariantViolation] = []

    for legacy_field in PHASE1_LEGACY_REFERENCE_ONLY_FIELDS:
        if legacy_field in after_snapshot:
            violations.append(
                InvariantViolation(
                    field_path=legacy_field,
                    invariant_class="hard",
                    message="legacy reference-only fields may not enter the formal owner snapshot",
                )
            )

    for field_name in PHASE1_AUTHORITATIVE_FIELDS:
        if field_name not in after_snapshot:
            violations.append(
                InvariantViolation(
                    field_path=field_name,
                    invariant_class="hard",
                    message="formal owner snapshot is missing an authoritative field",
                )
            )

    if after_snapshot.get("schema_version") != FORMAL_OWNER_SCHEMA_VERSION:
        violations.append(
            InvariantViolation(
                field_path="schema_version",
                invariant_class="hard",
                message="schema_version must stay on the formal owner schema version",
            )
        )

    if before_snapshot:
        if after_snapshot.get("identity_handle") != before_snapshot.get("identity_handle"):
            violations.append(
                InvariantViolation(
                    field_path="identity_handle",
                    invariant_class="hard",
                    message="identity_handle may not change during governed writeback",
                )
            )
        if after_snapshot.get("created_at") != before_snapshot.get("created_at"):
            violations.append(
                InvariantViolation(
                    field_path="created_at",
                    invariant_class="hard",
                    message="created_at is immutable once the owner snapshot exists",
                )
            )

        before_boundary = _extract_tool_boundary(before_snapshot)
        after_boundary = _extract_tool_boundary(after_snapshot)
        if before_boundary != after_boundary and not (request and _is_governance_revision(request)):
            violations.append(
                InvariantViolation(
                    field_path="tool_authority_boundary",
                    invariant_class="hard",
                    message="tool authority boundary may not change without governance-approved revision",
                )
            )

    return violations


def assess_drift(
    before_model: SelfModel | Dict[str, Any] | None,
    after_model: SelfModel | Dict[str, Any],
    *,
    request: SelfModelUpdateRequest,
    revisions: Optional[Sequence[SelfModelRevisionRecord]] = None,
) -> DriftAssessment:
    before_snapshot = _snapshot(before_model)
    after_snapshot = _snapshot(after_model)
    changed_fields = _top_level_changed_fields(before_snapshot, after_snapshot)
    stable_default_changes = [field_name for field_name in changed_fields if field_name in STABLE_DEFAULT_FIELDS]
    evolvable_changes = [field_name for field_name in changed_fields if field_name in EVOLVABLE_FIELDS]
    confidence_rank = _confidence_rank(request.confidence_class)

    recent_revisions = list(revisions or [])[-3:]
    repeated_field_count = 0
    if len(recent_revisions) >= 2 and changed_fields:
        recent_tops: List[set[str]] = []
        for revision in recent_revisions:
            top_fields = {
                str(item.get("field_path", "")).split(".", 1)[0]
                for item in revision.diff
                if item.get("field_path")
            }
            recent_tops.append(top_fields)
        repeated_field_count = sum(
            1
            for field_name in changed_fields
            if sum(1 for top_fields in recent_tops if field_name in top_fields) >= 2
        )
    revision_oscillation_rate = (
        repeated_field_count / len(changed_fields) if changed_fields else 0.0
    )

    continuity_break_count = 0
    if before_snapshot and after_snapshot.get("identity_handle") != before_snapshot.get("identity_handle"):
        continuity_break_count += 1

    unsupported_identity_claim_rate = 0.0
    if stable_default_changes and confidence_rank < _CONFIDENCE_RANK["high"]:
        unsupported_identity_claim_rate = 1.0
    elif not request.supporting_evidence and changed_fields:
        unsupported_identity_claim_rate = 1.0

    recommended_verdict = ALLOW_WRITEBACK
    drift_level = "none"

    if continuity_break_count > 0 or revision_oscillation_rate >= 1.0:
        recommended_verdict = ROLLBACK_TO_LAST_STABLE
        drift_level = "high"
    elif unsupported_identity_claim_rate > 0 or (len(stable_default_changes) > 1 and confidence_rank < _CONFIDENCE_RANK["high"]):
        recommended_verdict = HOLD_FOR_REVIEW
        drift_level = "medium"
    elif changed_fields:
        drift_level = "low"

    return DriftAssessment(
        drift_detected=recommended_verdict != ALLOW_WRITEBACK,
        drift_level=drift_level,
        recommended_verdict=recommended_verdict,
        changed_fields=changed_fields,
        stable_default_changes=stable_default_changes,
        evolvable_changes=evolvable_changes,
        revision_oscillation_rate=revision_oscillation_rate,
        unsupported_identity_claim_rate=unsupported_identity_claim_rate,
        continuity_break_count=continuity_break_count,
    )


def evaluate_update_request(
    before_model: SelfModel | Dict[str, Any],
    *,
    request: SelfModelUpdateRequest,
    revisions: Optional[Sequence[SelfModelRevisionRecord]] = None,
) -> SelfModelUpdateDecision:
    before_snapshot = _snapshot(before_model)
    changed_fields = sorted(request.delta.keys())
    after_snapshot = _deep_merge(before_snapshot, request.delta)

    violations: List[InvariantViolation] = []
    if not request.trace_reference:
        violations.append(
            InvariantViolation(
                field_path="trace_reference",
                invariant_class="hard",
                message="trace_reference is required for governed writeback",
            )
        )
    if not request.update_source:
        violations.append(
            InvariantViolation(
                field_path="update_source",
                invariant_class="hard",
                message="update_source is required for governed writeback",
            )
        )
    if request.update_mode not in ALLOWED_UPDATE_MODES:
        violations.append(
            InvariantViolation(
                field_path="update_mode",
                invariant_class="hard",
                message="update_mode must be one of the governed writeback modes",
            )
        )
    for field_name in changed_fields:
        if field_name in PHASE1_LEGACY_REFERENCE_ONLY_FIELDS:
            violations.append(
                InvariantViolation(
                    field_path=field_name,
                    invariant_class="hard",
                    message="legacy-only fields may not be written into the formal owner store",
                )
            )
        elif field_name not in WRITABLE_AUTHORITATIVE_FIELDS:
            violations.append(
                InvariantViolation(
                    field_path=field_name,
                    invariant_class="hard",
                    message="field is outside the writable formal owner contract",
                )
            )

    violations.extend(check_identity_invariants(before_snapshot, after_snapshot, request=request))
    drift = assess_drift(before_snapshot, after_snapshot, request=request, revisions=revisions)

    gate_verdict = REJECT if violations else drift.recommended_verdict
    accepted = gate_verdict == ALLOW_WRITEBACK
    return SelfModelUpdateDecision(
        gate_verdict=gate_verdict,
        accepted=accepted,
        changed_fields=changed_fields,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        invariant_violations=violations,
        drift_assessment=drift,
        request=request,
    )


def apply_governed_writeback(
    *,
    store: SelfModelStore,
    current_model: SelfModel,
    request: SelfModelUpdateRequest,
    revisions: Optional[Sequence[SelfModelRevisionRecord]] = None,
) -> SelfModelWritebackResult:
    decision = evaluate_update_request(current_model, request=request, revisions=revisions)
    if not decision.accepted:
        return SelfModelWritebackResult(
            decision=decision,
            revision=None,
            stable_snapshot_mutated=False,
        )

    updated_model = SelfModel.from_dict(decision.after_snapshot)
    revision = store.save(
        updated_model,
        update_source=request.update_source,
        trace_reference=request.trace_reference,
        confidence_class=request.confidence_class,
        gate_verdict=decision.gate_verdict,
        changed_fields=decision.changed_fields,
        reason=request.update_mode,
    )
    return SelfModelWritebackResult(
        decision=decision,
        revision=revision,
        stable_snapshot_mutated=True,
    )
