from __future__ import annotations

import time
from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class DevelopmentalProposalStatus(str, Enum):
    PROPOSED = "proposed"
    HELD = "held"
    APPROVED_FOR_REVIEW = "approved_for_review"
    OBSERVED = "observed"


class PromotionLevel(str, Enum):
    SHADOW_ONLY = "shadow_only"
    REVIEW_ONLY = "review_only"
    CONTROLLED_AXIS = "controlled_axis"


class PromotionStatus(str, Enum):
    QUEUED = "queued"
    HELD = "held"
    REVIEWED = "reviewed"
    REJECTED = "rejected"


class ContinuityMarkerType(str, Enum):
    IDENTITY_ANCHOR = "identity_anchor"
    CONTINUITY_GAP = "continuity_gap"
    GROWTH_SIGNAL = "growth_signal"
    STAGNATION_SIGNAL = "stagnation_signal"
    GOVERNANCE_CHECKPOINT = "governance_checkpoint"


class DevelopmentalIdentityAnchor(BaseModel):
    anchor_id: str = "identity_anchor"
    self_model_identity: str = "openemotion"
    anchor_summary: str = "bounded developmental continuity anchor"
    invariant_refs: List[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    last_confirmed_at: float = Field(default_factory=time.time)


class DevelopmentalTrajectorySummary(BaseModel):
    current_arc: str = "continuity_first"
    current_phase: str = "baseline"
    recent_shift: str = ""
    continuity_note: str = ""
    source_refs: List[str] = Field(default_factory=list)


class DevelopmentalProposal(BaseModel):
    proposal_id: str
    proposal_kind: str
    summary: str
    proposed_adjustment: Dict[str, Any] = Field(default_factory=dict)
    justification: str
    source_refs: List[str] = Field(default_factory=list)
    requested_effects: List[str] = Field(default_factory=list)
    required_gate: str = "developmental_writeback_gate"
    effect_scope: str = "proposal_only"
    behavioral_authority: str = "none"
    promotion_level: PromotionLevel = PromotionLevel.SHADOW_ONLY
    status: DevelopmentalProposalStatus = DevelopmentalProposalStatus.PROPOSED
    created_at: float = Field(default_factory=time.time)


class DevelopmentalPromotionCandidate(BaseModel):
    promotion_id: str
    source_proposal_id: str
    summary: str
    promotion_level: PromotionLevel = PromotionLevel.REVIEW_ONLY
    required_gate: str = "developmental_writeback_gate"
    behavioral_authority: str = "none"
    status: PromotionStatus = PromotionStatus.QUEUED
    created_at: float = Field(default_factory=time.time)


class ContinuityMarker(BaseModel):
    marker_id: str
    marker_type: ContinuityMarkerType
    reference: str
    continuity_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    note: str = ""
    source_refs: List[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class GovernanceLedgerEntry(BaseModel):
    ledger_id: str
    event_type: str
    reference_id: str
    gate_name: str = "developmental_writeback_gate"
    gate_verdict: str = "allow_writeback"
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
