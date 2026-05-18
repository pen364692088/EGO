from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from .schemas import (
    ArbitrationBalance,
    AxisArbitrationHint,
    CrossAxisPriorityState,
    IntegratedTendencyProposal,
    IntegrationLedgerEntry,
    IntegrationState,
    ProposalConflictState,
)
from .state import (
    FIXED_POLICY_MODE,
    FORBIDDEN_REQUESTED_EFFECTS,
    FORMAL_OWNER_SCHEMA_VERSION,
    REQUIRED_WRITEBACK_GATE,
    SelfhoodIntegrationState,
)


class SelfhoodIntegrationGovernanceVerdict(BaseModel):
    accepted: bool = True
    violations: List[str] = Field(default_factory=list)


def validate_selfhood_integration_state(
    state: SelfhoodIntegrationState,
) -> SelfhoodIntegrationGovernanceVerdict:
    violations: List[str] = []

    def _coerce(value, model_cls):
        if isinstance(value, model_cls):
            return value
        return model_cls.model_validate(value)

    if state.schema_version != FORMAL_OWNER_SCHEMA_VERSION:
        violations.append("invalid_schema_version")
    if not state.identity_handle.strip():
        violations.append("missing_identity_handle")
    if len(state.axis_arbitration_hints) > 32:
        violations.append("axis_arbitration_hints_too_large")
    if len(state.integration_ledger) > 512:
        violations.append("integration_ledger_too_large")

    integration_state = _coerce(state.integration_state, IntegrationState)
    if integration_state.integration_id != "phase1":
        violations.append("invalid_integration_state_id")
    if integration_state.policy_mode != FIXED_POLICY_MODE:
        violations.append(f"invalid_integration_policy_mode:{integration_state.policy_mode}")

    priority_state = _coerce(state.cross_axis_priority_state, CrossAxisPriorityState)
    if priority_state.priority_id != "phase1":
        violations.append("invalid_cross_axis_priority_id")
    if priority_state.policy_mode != FIXED_POLICY_MODE:
        violations.append(f"invalid_priority_policy_mode:{priority_state.policy_mode}")

    conflict_state = _coerce(state.proposal_conflict_state, ProposalConflictState)
    if conflict_state.conflict_id != "phase1":
        violations.append("invalid_proposal_conflict_id")
    if conflict_state.conflict_count == 0 and conflict_state.highest_severity.value != "none":
        violations.append("conflict_severity_present_without_conflict_count")
    if conflict_state.conflict_count > 0 and conflict_state.highest_severity.value == "none":
        violations.append("conflict_count_present_without_severity")

    def _validate_balance(
        value,
        *,
        field_name: str,
        expected_id: str,
        lower_pole: str,
        upper_pole: str,
    ) -> None:
        balance = _coerce(value, ArbitrationBalance)
        if balance.balance_id != expected_id:
            violations.append(f"invalid_balance_id:{field_name}:{balance.balance_id}")
        if balance.lower_pole != lower_pole:
            violations.append(f"invalid_lower_pole:{field_name}:{balance.lower_pole}")
        if balance.upper_pole != upper_pole:
            violations.append(f"invalid_upper_pole:{field_name}:{balance.upper_pole}")
        if balance.preferred_pole not in {lower_pole, upper_pole}:
            violations.append(f"invalid_preferred_pole:{field_name}:{balance.preferred_pole}")

    _validate_balance(
        state.stabilize_explore_balance,
        field_name="stabilize_explore_balance",
        expected_id="stabilize_explore",
        lower_pole="stabilize",
        upper_pole="explore",
    )
    _validate_balance(
        state.repair_progress_balance,
        field_name="repair_progress_balance",
        expected_id="repair_progress",
        lower_pole="repair",
        upper_pole="progress",
    )
    _validate_balance(
        state.social_boundary_balance,
        field_name="social_boundary_balance",
        expected_id="social_boundary",
        lower_pole="social",
        upper_pole="boundary",
    )

    if state.integrated_tendency_proposal is not None:
        proposal = _coerce(state.integrated_tendency_proposal, IntegratedTendencyProposal)
        if proposal.policy_mode != FIXED_POLICY_MODE:
            violations.append(f"invalid_proposal_policy_mode:{proposal.policy_mode}")
        if proposal.required_gate != REQUIRED_WRITEBACK_GATE:
            violations.append(
                f"invalid_required_gate:{proposal.proposal_id}:{proposal.required_gate}"
            )
        if proposal.effect_scope != "proposal_only":
            violations.append(
                f"invalid_effect_scope:{proposal.proposal_id}:{proposal.effect_scope}"
            )
        if proposal.behavioral_authority != "none":
            violations.append(
                f"invalid_behavioral_authority:{proposal.proposal_id}:{proposal.behavioral_authority}"
            )
        for effect in proposal.requested_effects:
            if effect in FORBIDDEN_REQUESTED_EFFECTS:
                violations.append(f"forbidden_integrated_effect:{proposal.proposal_id}:{effect}")

    for axis_name, hint in state.axis_arbitration_hints.items():
        hint = _coerce(hint, AxisArbitrationHint)
        if hint.axis_name != axis_name:
            violations.append(f"axis_arbitration_hint_axis_mismatch:{axis_name}")
        if not hint.recommendation.strip():
            violations.append(f"axis_arbitration_hint_missing_recommendation:{axis_name}")
        if not hint.advisory_only:
            violations.append(f"axis_arbitration_hint_not_advisory:{axis_name}")

    for ledger_id, entry in state.integration_ledger.items():
        entry = _coerce(entry, IntegrationLedgerEntry)
        if entry.ledger_id != ledger_id:
            violations.append(f"integration_ledger_id_mismatch:{ledger_id}")

    return SelfhoodIntegrationGovernanceVerdict(
        accepted=not violations,
        violations=violations,
    )
