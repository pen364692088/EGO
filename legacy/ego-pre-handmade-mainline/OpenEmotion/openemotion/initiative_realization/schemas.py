from __future__ import annotations

import time
from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class RealizationMode(str, Enum):
    HOLD = "hold"
    REVIEW = "review"
    PREPARE = "prepare"
    MEDIATE = "mediate"
    FULFILL = "fulfill"


class CommitmentFulfillmentStatus(str, Enum):
    ACTIVE = "active"
    HELD = "held"
    READY = "ready"
    BLOCKED = "blocked"
    FULFILLED = "fulfilled"
    FAILED = "failed"


class RealizationProposalStatus(str, Enum):
    PROPOSED = "proposed"
    HELD = "held"
    APPROVED_FOR_REVIEW = "approved_for_review"
    OBSERVED = "observed"
    REJECTED = "rejected"


class ControlledDeliveryCandidateStatus(str, Enum):
    PROPOSED = "proposed"
    HELD = "held"
    APPROVED_FOR_REVIEW = "approved_for_review"
    OBSERVED = "observed"
    REJECTED = "rejected"


class RealizationState(BaseModel):
    realization_id: str = "phase1"
    policy_mode: str = "proposal_only"
    dominant_mode: RealizationMode = RealizationMode.REVIEW
    realization_pressure: float = Field(default=0.0, ge=0.0, le=1.0)
    fulfillment_readiness: float = Field(default=0.0, ge=0.0, le=1.0)
    hold_bias: float = Field(default=0.0, ge=0.0, le=1.0)
    failure_recovery_bias: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale_summary: str = ""
    source_refs: List[str] = Field(default_factory=list)
    last_updated: float = Field(default_factory=time.time)


class DeliveryReadinessState(BaseModel):
    readiness_id: str = "phase1"
    policy_mode: str = "proposal_only"
    selected_lane: RealizationMode = RealizationMode.REVIEW
    hold_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    review_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    prepare_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    mediate_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    fulfill_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    lane_reason: str = ""
    host_lane_hints: List[str] = Field(default_factory=list)
    source_refs: List[str] = Field(default_factory=list)
    last_updated: float = Field(default_factory=time.time)


class CommitmentFulfillmentState(BaseModel):
    fulfillment_id: str = "phase1"
    status: CommitmentFulfillmentStatus = CommitmentFulfillmentStatus.ACTIVE
    active_commitments_count: int = Field(default=0, ge=0)
    ready_commitments_count: int = Field(default=0, ge=0)
    realized_commitment_refs: List[str] = Field(default_factory=list)
    blocked_commitment_refs: List[str] = Field(default_factory=list)
    continuity_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    fulfillment_summary: str = ""
    source_refs: List[str] = Field(default_factory=list)
    last_updated: float = Field(default_factory=time.time)


class InitiativeRealizationCandidate(BaseModel):
    candidate_id: str
    candidate_label: str
    selected_mode: RealizationMode
    proposed_effects: Dict[str, Any] = Field(default_factory=dict)
    justification: str
    required_gate: str
    effect_scope: str = "proposal_only"
    behavioral_authority: str = "none"
    requested_effects: List[str] = Field(default_factory=list)
    status: RealizationProposalStatus = RealizationProposalStatus.PROPOSED
    source_refs: List[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class ControlledDeliveryCandidate(BaseModel):
    candidate_id: str
    candidate_label: str
    readiness_basis: str
    host_lane_hint: str = "host_proactive_outbox"
    delivery_readiness: float = Field(default=0.0, ge=0.0, le=1.0)
    required_gate: str = "initiative_realization_writeback_gate"
    effect_scope: str = "proposal_only"
    behavioral_authority: str = "none"
    requested_effects: List[str] = Field(default_factory=list)
    status: ControlledDeliveryCandidateStatus = ControlledDeliveryCandidateStatus.PROPOSED
    source_refs: List[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class RealizationLedgerEntry(BaseModel):
    ledger_id: str
    event_type: str
    reference_id: str
    gate_name: str
    gate_verdict: str
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
