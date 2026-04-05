from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from .schemas import (
    CommitmentContinuityState,
    HostProactiveCandidate,
    InitiativeLedgerEntry,
    InitiativePriorityState,
    InitiativeProposalCandidate,
    InitiativeState,
)
from .state import (
    FIXED_POLICY_MODE,
    FORBIDDEN_REQUESTED_EFFECTS,
    FORMAL_OWNER_SCHEMA_VERSION,
    REQUIRED_WRITEBACK_GATE,
    InitiativeSelfState,
)


class InitiativeGovernanceVerdict(BaseModel):
    accepted: bool = True
    violations: List[str] = Field(default_factory=list)


def validate_initiative_state(state: InitiativeSelfState) -> InitiativeGovernanceVerdict:
    violations: List[str] = []

    def _coerce(value, model_cls):
        if isinstance(value, model_cls):
            return value
        return model_cls.model_validate(value)

    if state.schema_version != FORMAL_OWNER_SCHEMA_VERSION:
        violations.append("invalid_schema_version")
    if not state.identity_handle.strip():
        violations.append("missing_identity_handle")
    if len(state.initiative_ledger) > 512:
        violations.append("initiative_ledger_too_large")

    initiative_state = _coerce(state.initiative_state, InitiativeState)
    if initiative_state.initiative_id != "phase1":
        violations.append("invalid_initiative_state_id")
    if initiative_state.policy_mode != FIXED_POLICY_MODE:
        violations.append(f"invalid_initiative_policy_mode:{initiative_state.policy_mode}")

    priority_state = _coerce(state.initiative_priority_state, InitiativePriorityState)
    if priority_state.priority_id != "phase1":
        violations.append("invalid_initiative_priority_id")
    if priority_state.policy_mode != FIXED_POLICY_MODE:
        violations.append(f"invalid_priority_policy_mode:{priority_state.policy_mode}")

    continuity_state = _coerce(state.commitment_continuity_state, CommitmentContinuityState)
    if continuity_state.continuity_id != "phase1":
        violations.append("invalid_commitment_continuity_id")
    if continuity_state.active_commitments_count < len(continuity_state.blocked_commitment_refs):
        violations.append("blocked_commitments_exceed_active_commitments")

    if state.initiative_proposal_candidate is not None:
        proposal = _coerce(state.initiative_proposal_candidate, InitiativeProposalCandidate)
        if proposal.required_gate != REQUIRED_WRITEBACK_GATE:
            violations.append(f"invalid_required_gate:{proposal.proposal_id}:{proposal.required_gate}")
        if proposal.effect_scope != "proposal_only":
            violations.append(f"invalid_effect_scope:{proposal.proposal_id}:{proposal.effect_scope}")
        if proposal.behavioral_authority != "none":
            violations.append(
                f"invalid_behavioral_authority:{proposal.proposal_id}:{proposal.behavioral_authority}"
            )
        for effect in proposal.requested_effects:
            if effect in FORBIDDEN_REQUESTED_EFFECTS:
                violations.append(f"forbidden_initiative_effect:{proposal.proposal_id}:{effect}")

    if state.host_proactive_candidate is not None:
        candidate = _coerce(state.host_proactive_candidate, HostProactiveCandidate)
        if candidate.required_gate != REQUIRED_WRITEBACK_GATE:
            violations.append(f"invalid_host_candidate_gate:{candidate.candidate_id}:{candidate.required_gate}")
        if candidate.effect_scope != "proposal_only":
            violations.append(
                f"invalid_host_candidate_scope:{candidate.candidate_id}:{candidate.effect_scope}"
            )
        if candidate.behavioral_authority != "none":
            violations.append(
                f"invalid_host_candidate_authority:{candidate.candidate_id}:{candidate.behavioral_authority}"
            )
        for effect in candidate.requested_effects:
            if effect in FORBIDDEN_REQUESTED_EFFECTS:
                violations.append(f"forbidden_host_candidate_effect:{candidate.candidate_id}:{effect}")

    for ledger_id, entry in state.initiative_ledger.items():
        entry = _coerce(entry, InitiativeLedgerEntry)
        if entry.ledger_id != ledger_id:
            violations.append(f"initiative_ledger_id_mismatch:{ledger_id}")

    return InitiativeGovernanceVerdict(accepted=not violations, violations=violations)
