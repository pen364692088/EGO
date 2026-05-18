from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from .schemas import (
    CommitmentFulfillmentState,
    ControlledDeliveryCandidate,
    DeliveryReadinessState,
    InitiativeRealizationCandidate,
    RealizationLedgerEntry,
    RealizationState,
)
from .state import (
    FIXED_POLICY_MODE,
    FORBIDDEN_REQUESTED_EFFECTS,
    FORMAL_OWNER_SCHEMA_VERSION,
    REQUIRED_WRITEBACK_GATE,
    InitiativeRealizationState,
)


class RealizationGovernanceVerdict(BaseModel):
    accepted: bool = True
    violations: List[str] = Field(default_factory=list)


def validate_realization_state(state: InitiativeRealizationState) -> RealizationGovernanceVerdict:
    violations: List[str] = []

    def _coerce(value, model_cls):
        if isinstance(value, model_cls):
            return value
        return model_cls.model_validate(value)

    if state.schema_version != FORMAL_OWNER_SCHEMA_VERSION:
        violations.append("invalid_schema_version")
    if not state.identity_handle.strip():
        violations.append("missing_identity_handle")
    if len(state.realization_ledger) > 512:
        violations.append("realization_ledger_too_large")

    realization_state = _coerce(state.realization_state, RealizationState)
    if realization_state.realization_id != "phase1":
        violations.append("invalid_realization_state_id")
    if realization_state.policy_mode != FIXED_POLICY_MODE:
        violations.append(f"invalid_realization_policy_mode:{realization_state.policy_mode}")

    readiness_state = _coerce(state.delivery_readiness_state, DeliveryReadinessState)
    if readiness_state.readiness_id != "phase1":
        violations.append("invalid_delivery_readiness_id")
    if readiness_state.policy_mode != FIXED_POLICY_MODE:
        violations.append(f"invalid_delivery_policy_mode:{readiness_state.policy_mode}")

    fulfillment_state = _coerce(state.commitment_fulfillment_state, CommitmentFulfillmentState)
    if fulfillment_state.fulfillment_id != "phase1":
        violations.append("invalid_commitment_fulfillment_id")
    if fulfillment_state.ready_commitments_count > fulfillment_state.active_commitments_count:
        violations.append("ready_commitments_exceed_active_commitments")

    if state.initiative_realization_candidate is not None:
        candidate = _coerce(state.initiative_realization_candidate, InitiativeRealizationCandidate)
        if candidate.required_gate != REQUIRED_WRITEBACK_GATE:
            violations.append(f"invalid_required_gate:{candidate.candidate_id}:{candidate.required_gate}")
        if candidate.effect_scope != "proposal_only":
            violations.append(f"invalid_effect_scope:{candidate.candidate_id}:{candidate.effect_scope}")
        if candidate.behavioral_authority != "none":
            violations.append(
                f"invalid_behavioral_authority:{candidate.candidate_id}:{candidate.behavioral_authority}"
            )
        for effect in candidate.requested_effects:
            if effect in FORBIDDEN_REQUESTED_EFFECTS:
                violations.append(f"forbidden_realization_effect:{candidate.candidate_id}:{effect}")

    if state.controlled_delivery_candidate is not None:
        candidate = _coerce(state.controlled_delivery_candidate, ControlledDeliveryCandidate)
        if candidate.required_gate != REQUIRED_WRITEBACK_GATE:
            violations.append(f"invalid_delivery_candidate_gate:{candidate.candidate_id}:{candidate.required_gate}")
        if candidate.effect_scope != "proposal_only":
            violations.append(
                f"invalid_delivery_candidate_scope:{candidate.candidate_id}:{candidate.effect_scope}"
            )
        if candidate.behavioral_authority != "none":
            violations.append(
                f"invalid_delivery_candidate_authority:{candidate.candidate_id}:{candidate.behavioral_authority}"
            )
        for effect in candidate.requested_effects:
            if effect in FORBIDDEN_REQUESTED_EFFECTS:
                violations.append(f"forbidden_delivery_candidate_effect:{candidate.candidate_id}:{effect}")

    for ledger_id, entry in state.realization_ledger.items():
        entry = _coerce(entry, RealizationLedgerEntry)
        if entry.ledger_id != ledger_id:
            violations.append(f"realization_ledger_id_mismatch:{ledger_id}")

    return RealizationGovernanceVerdict(accepted=not violations, violations=violations)
