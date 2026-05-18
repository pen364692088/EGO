from __future__ import annotations

import time
from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class InitiativePriority(str, Enum):
    HOLD = "hold"
    REVIEW = "review"
    PREPARE = "prepare"
    CARRY_FORWARD = "carry_forward"
    SCHEDULE = "schedule"


class CommitmentContinuityStatus(str, Enum):
    ACTIVE = "active"
    DEFERRED = "deferred"
    BLOCKED = "blocked"
    FULFILLED = "fulfilled"
    DROPPED = "dropped"


class InitiativeProposalStatus(str, Enum):
    PROPOSED = "proposed"
    HELD = "held"
    APPROVED_FOR_REVIEW = "approved_for_review"
    OBSERVED = "observed"
    REJECTED = "rejected"


class HostProactiveCandidateStatus(str, Enum):
    PROPOSED = "proposed"
    HELD = "held"
    APPROVED_FOR_REVIEW = "approved_for_review"
    OBSERVED = "observed"
    REJECTED = "rejected"


class InitiativeState(BaseModel):
    initiative_id: str = "phase1"
    policy_mode: str = "proposal_only"
    dominant_mode: InitiativePriority = InitiativePriority.REVIEW
    initiative_pressure: float = Field(default=0.0, ge=0.0, le=1.0)
    commitment_carryover_bias: float = Field(default=0.0, ge=0.0, le=1.0)
    recent_delivery_sensitivity: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale_summary: str = ""
    source_refs: List[str] = Field(default_factory=list)
    last_updated: float = Field(default_factory=time.time)


class InitiativePriorityState(BaseModel):
    priority_id: str = "phase1"
    policy_mode: str = "proposal_only"
    selected_priority: InitiativePriority = InitiativePriority.REVIEW
    hold_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    review_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    prepare_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    carry_forward_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    schedule_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    priority_reason: str = ""
    upstream_pressure_sources: List[str] = Field(default_factory=list)
    source_refs: List[str] = Field(default_factory=list)
    last_updated: float = Field(default_factory=time.time)


class CommitmentContinuityState(BaseModel):
    continuity_id: str = "phase1"
    status: CommitmentContinuityStatus = CommitmentContinuityStatus.ACTIVE
    active_commitments_count: int = Field(default=0, ge=0)
    carried_commitment_refs: List[str] = Field(default_factory=list)
    blocked_commitment_refs: List[str] = Field(default_factory=list)
    continuity_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    carryover_summary: str = ""
    source_refs: List[str] = Field(default_factory=list)
    last_updated: float = Field(default_factory=time.time)


class InitiativeProposalCandidate(BaseModel):
    proposal_id: str
    proposal_label: str
    priority_mode: InitiativePriority
    proposed_effects: Dict[str, Any] = Field(default_factory=dict)
    justification: str
    required_gate: str
    effect_scope: str = "proposal_only"
    behavioral_authority: str = "none"
    requested_effects: List[str] = Field(default_factory=list)
    status: InitiativeProposalStatus = InitiativeProposalStatus.PROPOSED
    source_refs: List[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class HostProactiveCandidate(BaseModel):
    candidate_id: str
    candidate_label: str
    continuity_basis: str
    host_lane_hint: str = "host_proactive_outbox"
    required_gate: str = "initiative_writeback_gate"
    effect_scope: str = "proposal_only"
    behavioral_authority: str = "none"
    requested_effects: List[str] = Field(default_factory=list)
    status: HostProactiveCandidateStatus = HostProactiveCandidateStatus.PROPOSED
    source_refs: List[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class InitiativeLedgerEntry(BaseModel):
    ledger_id: str
    event_type: str
    reference_id: str
    gate_name: str
    gate_verdict: str
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
