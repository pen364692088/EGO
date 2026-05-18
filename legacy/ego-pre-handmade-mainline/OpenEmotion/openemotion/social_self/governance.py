from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from .schemas import (
    CommitmentState,
    GovernanceLedgerEntry,
    OtherModelState,
    RelationMemoryEntry,
    RepairState,
    SocialBoundaryState,
    TrustState,
)
from .state import (
    FORBIDDEN_REQUESTED_EFFECTS,
    FORMAL_OWNER_SCHEMA_VERSION,
    REQUIRED_WRITEBACK_GATE,
    SocialSelfState,
)


class SocialGovernanceVerdict(BaseModel):
    accepted: bool = True
    violations: List[str] = Field(default_factory=list)


def validate_social_state(state: SocialSelfState) -> SocialGovernanceVerdict:
    violations: List[str] = []

    def _coerce(value, model_cls):
        if isinstance(value, model_cls):
            return value
        return model_cls.model_validate(value)

    if state.schema_version != FORMAL_OWNER_SCHEMA_VERSION:
        violations.append("invalid_schema_version")
    if not state.identity_handle.strip():
        violations.append("missing_identity_handle")
    if len(state.relation_memory) > 256:
        violations.append("relation_memory_too_large")
    if len(state.other_model_state) > 256:
        violations.append("other_model_state_too_large")
    if len(state.trust_state) > 256:
        violations.append("trust_state_too_large")
    if len(state.commitment_state) > 256:
        violations.append("commitment_state_too_large")
    if len(state.repair_state) > 256:
        violations.append("repair_state_too_large")
    if len(state.social_boundary_state) > 256:
        violations.append("social_boundary_state_too_large")
    if len(state.governance_ledger) > 512:
        violations.append("governance_ledger_too_large")

    for counterpart_id, relation in state.relation_memory.items():
        relation = _coerce(relation, RelationMemoryEntry)
        if relation.counterpart_id != counterpart_id:
            violations.append(f"relation_counterpart_id_mismatch:{counterpart_id}")

    for counterpart_id, other_model in state.other_model_state.items():
        other_model = _coerce(other_model, OtherModelState)
        if other_model.counterpart_id != counterpart_id:
            violations.append(f"other_model_counterpart_id_mismatch:{counterpart_id}")

    for counterpart_id, trust in state.trust_state.items():
        trust = _coerce(trust, TrustState)
        if trust.counterpart_id != counterpart_id:
            violations.append(f"trust_counterpart_id_mismatch:{counterpart_id}")

    for commitment_id, commitment in state.commitment_state.items():
        commitment = _coerce(commitment, CommitmentState)
        if commitment.commitment_id != commitment_id:
            violations.append(f"commitment_id_mismatch:{commitment_id}")

    for proposal_id, proposal in state.repair_state.items():
        proposal = _coerce(proposal, RepairState)
        if proposal.proposal_id != proposal_id:
            violations.append(f"repair_proposal_id_mismatch:{proposal_id}")
        if proposal.required_gate != REQUIRED_WRITEBACK_GATE:
            violations.append(f"invalid_required_gate:{proposal_id}:{proposal.required_gate}")
        if proposal.effect_scope != "proposal_only":
            violations.append(f"invalid_effect_scope:{proposal_id}:{proposal.effect_scope}")
        if proposal.behavioral_authority != "none":
            violations.append(
                f"invalid_behavioral_authority:{proposal_id}:{proposal.behavioral_authority}"
            )
        for effect in proposal.requested_effects:
            if effect in FORBIDDEN_REQUESTED_EFFECTS:
                violations.append(f"forbidden_repair_effect:{proposal_id}:{effect}")

    for counterpart_id, boundary in state.social_boundary_state.items():
        boundary = _coerce(boundary, SocialBoundaryState)
        if boundary.counterpart_id != counterpart_id:
            violations.append(f"boundary_counterpart_id_mismatch:{counterpart_id}")

    for ledger_id, entry in state.governance_ledger.items():
        entry = _coerce(entry, GovernanceLedgerEntry)
        if entry.ledger_id != ledger_id:
            violations.append(f"governance_ledger_id_mismatch:{ledger_id}")

    return SocialGovernanceVerdict(accepted=not violations, violations=violations)
