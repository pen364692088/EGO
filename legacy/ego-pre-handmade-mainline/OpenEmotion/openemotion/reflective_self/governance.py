from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from .schemas import (
    CounterfactualRecord,
    DiagnosisRecord,
    ReflectionQueueItem,
    ReflectionTarget,
    RevisionProposal,
    UnresolvedReflectionItem,
)
from .state import (
    ALLOWED_PROPOSAL_STATUSES,
    ALLOWED_REFLECTION_STATUSES,
    FORBIDDEN_REQUESTED_EFFECTS,
    FORMAL_OWNER_SCHEMA_VERSION,
    ReflectiveSelfState,
)


class ReflectiveGovernanceVerdict(BaseModel):
    accepted: bool = True
    violations: List[str] = Field(default_factory=list)


def validate_reflective_state(state: ReflectiveSelfState) -> ReflectiveGovernanceVerdict:
    violations: List[str] = []

    def _coerce(value, model_cls):
        if isinstance(value, model_cls):
            return value
        return model_cls.model_validate(value)

    if state.schema_version != FORMAL_OWNER_SCHEMA_VERSION:
        violations.append("invalid_schema_version")
    if len(state.reflection_queue) > 128:
        violations.append("reflection_queue_too_large")
    if len(state.revision_proposals) > 128:
        violations.append("revision_proposals_too_large")

    for reflection_id, item in state.reflection_queue.items():
        item = _coerce(item, ReflectionQueueItem)
        if item.reflection_id != reflection_id:
            violations.append(f"reflection_id_mismatch:{reflection_id}")
        if item.status not in ALLOWED_REFLECTION_STATUSES:
            violations.append(f"invalid_reflection_status:{reflection_id}:{item.status}")
        for effect in item.requested_effects:
            if effect in FORBIDDEN_REQUESTED_EFFECTS:
                violations.append(f"forbidden_queue_effect:{reflection_id}:{effect}")

    for target_id, target in state.reflection_targets.items():
        target = _coerce(target, ReflectionTarget)
        if target.target_id != target_id:
            violations.append(f"target_id_mismatch:{target_id}")

    for diagnosis_id, record in state.diagnosis_records.items():
        record = _coerce(record, DiagnosisRecord)
        if record.diagnosis_id != diagnosis_id:
            violations.append(f"diagnosis_id_mismatch:{diagnosis_id}")

    for counterfactual_id, record in state.counterfactual_records.items():
        record = _coerce(record, CounterfactualRecord)
        if record.counterfactual_id != counterfactual_id:
            violations.append(f"counterfactual_id_mismatch:{counterfactual_id}")
        if record.truth_status != "counterfactual_uncertain":
            violations.append(f"invalid_counterfactual_truth_status:{counterfactual_id}")

    for proposal_id, proposal in state.revision_proposals.items():
        proposal = _coerce(proposal, RevisionProposal)
        if proposal.proposal_id != proposal_id:
            violations.append(f"proposal_id_mismatch:{proposal_id}")
        if proposal.effect_scope != "proposal_only":
            violations.append(f"invalid_effect_scope:{proposal_id}")
        if proposal.status not in ALLOWED_PROPOSAL_STATUSES:
            violations.append(f"invalid_proposal_status:{proposal_id}:{proposal.status}")
        if proposal.status == "applied":
            violations.append(f"proposal_bypassed_governance:{proposal_id}")
        if not proposal.required_gate.strip():
            violations.append(f"missing_required_gate:{proposal_id}")
        for effect in proposal.requested_effects:
            if effect in FORBIDDEN_REQUESTED_EFFECTS:
                violations.append(f"forbidden_proposal_effect:{proposal_id}:{effect}")

    for item_id, item in state.unresolved_reflection_items.items():
        item = _coerce(item, UnresolvedReflectionItem)
        if item.item_id != item_id:
            violations.append(f"unresolved_item_id_mismatch:{item_id}")

    return ReflectiveGovernanceVerdict(accepted=not violations, violations=violations)
