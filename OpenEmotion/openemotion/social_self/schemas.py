from __future__ import annotations

import time
from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class RelationshipContinuityStatus(str, Enum):
    ACTIVE = "active"
    STRAINED = "strained"
    REPAIRING = "repairing"
    PAUSED = "paused"


class CommitmentStatus(str, Enum):
    OPEN = "open"
    HELD = "held"
    FULFILLED = "fulfilled"
    BREACHED = "breached"
    REPAIRED = "repaired"


class RepairProposalStatus(str, Enum):
    PROPOSED = "proposed"
    HELD = "held"
    APPROVED_FOR_REVIEW = "approved_for_review"
    OBSERVED = "observed"
    REJECTED = "rejected"


class BoundaryMode(str, Enum):
    OPEN = "open"
    CAUTIOUS = "cautious"
    FIRM = "firm"
    REPAIR_ONLY = "repair_only"


class RelationMemoryEntry(BaseModel):
    counterpart_id: str
    relationship_summary: str
    interaction_role: str = "user"
    continuity_status: RelationshipContinuityStatus = RelationshipContinuityStatus.ACTIVE
    source_refs: List[str] = Field(default_factory=list)
    last_updated: float = Field(default_factory=time.time)


class OtherModelState(BaseModel):
    counterpart_id: str
    inferred_preferences: Dict[str, Any] = Field(default_factory=dict)
    inferred_constraints: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source_refs: List[str] = Field(default_factory=list)
    last_updated: float = Field(default_factory=time.time)


class TrustState(BaseModel):
    counterpart_id: str
    trust_level: float = Field(default=0.5, ge=0.0, le=1.0)
    trust_delta: float = Field(default=0.0, ge=-1.0, le=1.0)
    trust_basis: List[str] = Field(default_factory=list)
    last_updated: float = Field(default_factory=time.time)


class CommitmentState(BaseModel):
    commitment_id: str
    counterpart_id: str
    summary: str
    status: CommitmentStatus = CommitmentStatus.OPEN
    due_hint: str | None = None
    source_refs: List[str] = Field(default_factory=list)
    last_updated: float = Field(default_factory=time.time)


class RepairState(BaseModel):
    proposal_id: str
    counterpart_id: str
    issue_summary: str
    proposed_adjustment: Dict[str, Any] = Field(default_factory=dict)
    justification: str
    required_gate: str
    effect_scope: str = "proposal_only"
    behavioral_authority: str = "none"
    requested_effects: List[str] = Field(default_factory=list)
    status: RepairProposalStatus = RepairProposalStatus.PROPOSED
    source_refs: List[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class SocialBoundaryState(BaseModel):
    counterpart_id: str
    caution_level: float = Field(default=0.5, ge=0.0, le=1.0)
    boundary_mode: BoundaryMode = BoundaryMode.CAUTIOUS
    reason: str = ""
    source_refs: List[str] = Field(default_factory=list)
    last_updated: float = Field(default_factory=time.time)


class GovernanceLedgerEntry(BaseModel):
    ledger_id: str
    event_type: str
    reference_id: str
    gate_name: str
    gate_verdict: str
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
