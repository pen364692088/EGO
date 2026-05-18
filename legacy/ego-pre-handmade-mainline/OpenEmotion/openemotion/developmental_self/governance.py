from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from .schemas import (
    ContinuityMarker,
    DevelopmentalIdentityAnchor,
    DevelopmentalPromotionCandidate,
    DevelopmentalProposal,
    GovernanceLedgerEntry,
)
from .state import (
    ALLOWED_PROPOSAL_STATUSES,
    ALLOWED_PROMOTION_LEVELS,
    ALLOWED_PROMOTION_STATUSES,
    FORBIDDEN_REQUESTED_EFFECTS,
    FORMAL_OWNER_SCHEMA_VERSION,
    REQUIRED_WRITEBACK_GATE,
    DevelopmentalSelfState,
)


class DevelopmentalGovernanceVerdict(BaseModel):
    accepted: bool = True
    violations: List[str] = Field(default_factory=list)


def validate_developmental_state(state: DevelopmentalSelfState) -> DevelopmentalGovernanceVerdict:
    violations: List[str] = []

    def _coerce(value, model_cls):
        if isinstance(value, model_cls):
            return value
        return model_cls.model_validate(value)

    if state.schema_version != FORMAL_OWNER_SCHEMA_VERSION:
        violations.append("invalid_schema_version")
    if not state.identity_handle.strip():
        violations.append("missing_identity_handle")
    if len(state.proposal_history) > 128:
        violations.append("proposal_history_too_large")
    if len(state.promotion_queue) > 128:
        violations.append("promotion_queue_too_large")
    if len(state.continuity_markers) > 256:
        violations.append("continuity_markers_too_large")
    if len(state.governance_ledger) > 512:
        violations.append("governance_ledger_too_large")

    anchor = _coerce(state.developmental_identity_anchor, DevelopmentalIdentityAnchor)
    if anchor.self_model_identity != state.identity_handle:
        violations.append("identity_anchor_mismatch")

    for proposal_id, proposal in state.proposal_history.items():
        proposal = _coerce(proposal, DevelopmentalProposal)
        if proposal.proposal_id != proposal_id:
            violations.append(f"proposal_id_mismatch:{proposal_id}")
        if proposal.required_gate != REQUIRED_WRITEBACK_GATE:
            violations.append(f"invalid_required_gate:{proposal_id}:{proposal.required_gate}")
        if proposal.effect_scope != "proposal_only":
            violations.append(f"invalid_effect_scope:{proposal_id}:{proposal.effect_scope}")
        if proposal.behavioral_authority != "none":
            violations.append(
                f"invalid_behavioral_authority:{proposal_id}:{proposal.behavioral_authority}"
            )
        if proposal.promotion_level.value not in ALLOWED_PROMOTION_LEVELS:
            violations.append(f"invalid_promotion_level:{proposal_id}:{proposal.promotion_level.value}")
        if proposal.status.value not in ALLOWED_PROPOSAL_STATUSES:
            violations.append(f"invalid_proposal_status:{proposal_id}:{proposal.status.value}")
        for effect in proposal.requested_effects:
            if effect in FORBIDDEN_REQUESTED_EFFECTS:
                violations.append(f"forbidden_proposal_effect:{proposal_id}:{effect}")

    for promotion_id, candidate in state.promotion_queue.items():
        candidate = _coerce(candidate, DevelopmentalPromotionCandidate)
        if candidate.promotion_id != promotion_id:
            violations.append(f"promotion_id_mismatch:{promotion_id}")
        if candidate.source_proposal_id not in state.proposal_history:
            violations.append(f"promotion_source_missing:{promotion_id}:{candidate.source_proposal_id}")
        if candidate.required_gate != REQUIRED_WRITEBACK_GATE:
            violations.append(f"invalid_promotion_gate:{promotion_id}:{candidate.required_gate}")
        if candidate.behavioral_authority != "none":
            violations.append(
                f"invalid_promotion_behavioral_authority:{promotion_id}:{candidate.behavioral_authority}"
            )
        if candidate.promotion_level.value not in ALLOWED_PROMOTION_LEVELS:
            violations.append(
                f"invalid_promotion_level_candidate:{promotion_id}:{candidate.promotion_level.value}"
            )
        if candidate.status.value not in ALLOWED_PROMOTION_STATUSES:
            violations.append(f"invalid_promotion_status:{promotion_id}:{candidate.status.value}")

    for marker_id, marker in state.continuity_markers.items():
        marker = _coerce(marker, ContinuityMarker)
        if marker.marker_id != marker_id:
            violations.append(f"marker_id_mismatch:{marker_id}")

    for ledger_id, entry in state.governance_ledger.items():
        entry = _coerce(entry, GovernanceLedgerEntry)
        if entry.ledger_id != ledger_id:
            violations.append(f"governance_ledger_id_mismatch:{ledger_id}")

    return DevelopmentalGovernanceVerdict(accepted=not violations, violations=violations)
