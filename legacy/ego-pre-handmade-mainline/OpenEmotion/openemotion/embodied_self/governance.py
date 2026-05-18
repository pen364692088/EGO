from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from .schemas import (
    ActionConsequenceRecord,
    BoundaryPressureState,
    EmbodiedProposal,
    EnvironmentCouplingState,
    GovernanceLedgerEntry,
    ResourcePressureState,
)
from .state import (
    FORBIDDEN_REQUESTED_EFFECTS,
    FORMAL_OWNER_SCHEMA_VERSION,
    REQUIRED_WRITEBACK_GATE,
    EmbodiedSelfState,
)


class EmbodiedGovernanceVerdict(BaseModel):
    accepted: bool = True
    violations: List[str] = Field(default_factory=list)


def validate_embodied_state(state: EmbodiedSelfState) -> EmbodiedGovernanceVerdict:
    violations: List[str] = []

    def _coerce(value, model_cls):
        if isinstance(value, model_cls):
            return value
        return model_cls.model_validate(value)

    if state.schema_version != FORMAL_OWNER_SCHEMA_VERSION:
        violations.append("invalid_schema_version")
    if not state.identity_handle.strip():
        violations.append("missing_identity_handle")
    if len(state.environment_coupling_state) > 256:
        violations.append("environment_coupling_state_too_large")
    if len(state.resource_pressure_state) > 256:
        violations.append("resource_pressure_state_too_large")
    if len(state.boundary_pressure_state) > 256:
        violations.append("boundary_pressure_state_too_large")
    if len(state.action_consequence_memory) > 512:
        violations.append("action_consequence_memory_too_large")
    if len(state.proposal_history) > 256:
        violations.append("proposal_history_too_large")
    if len(state.governance_ledger) > 512:
        violations.append("governance_ledger_too_large")

    for coupling_id, entry in state.environment_coupling_state.items():
        entry = _coerce(entry, EnvironmentCouplingState)
        if entry.coupling_id != coupling_id:
            violations.append(f"environment_coupling_id_mismatch:{coupling_id}")

    for pressure_id, entry in state.resource_pressure_state.items():
        entry = _coerce(entry, ResourcePressureState)
        if entry.pressure_id != pressure_id:
            violations.append(f"resource_pressure_id_mismatch:{pressure_id}")

    for boundary_id, entry in state.boundary_pressure_state.items():
        entry = _coerce(entry, BoundaryPressureState)
        if entry.boundary_id != boundary_id:
            violations.append(f"boundary_pressure_id_mismatch:{boundary_id}")

    for consequence_id, entry in state.action_consequence_memory.items():
        entry = _coerce(entry, ActionConsequenceRecord)
        if entry.consequence_id != consequence_id:
            violations.append(f"action_consequence_id_mismatch:{consequence_id}")

    for proposal_id, proposal in state.proposal_history.items():
        proposal = _coerce(proposal, EmbodiedProposal)
        if proposal.proposal_id != proposal_id:
            violations.append(f"embodied_proposal_id_mismatch:{proposal_id}")
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
                violations.append(f"forbidden_embodied_effect:{proposal_id}:{effect}")

    if state.self_world_boundary_semantics.semantic_id != "self_world":
        violations.append("invalid_self_world_semantic_id")

    for ledger_id, entry in state.governance_ledger.items():
        entry = _coerce(entry, GovernanceLedgerEntry)
        if entry.ledger_id != ledger_id:
            violations.append(f"governance_ledger_id_mismatch:{ledger_id}")

    return EmbodiedGovernanceVerdict(accepted=not violations, violations=violations)
