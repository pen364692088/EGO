from __future__ import annotations

import time
from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ArbitrationPriority(str, Enum):
    STABILIZE = "stabilize"
    CONSERVE = "conserve"
    GUARD = "guard"
    REVIEW = "review"
    REPAIR = "repair"
    GROW = "grow"


class ConflictSeverity(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IntegratedProposalStatus(str, Enum):
    PROPOSED = "proposed"
    HELD = "held"
    APPROVED_FOR_REVIEW = "approved_for_review"
    OBSERVED = "observed"
    REJECTED = "rejected"


class IntegrationState(BaseModel):
    integration_id: str = "phase1"
    policy_mode: str = "stability_first"
    posture: ArbitrationPriority = ArbitrationPriority.REVIEW
    dominant_pressure_axis: str = "stability"
    stability_bias: float = Field(default=0.5, ge=0.0, le=1.0)
    integration_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    active_axis_count: int = Field(default=0, ge=0, le=8)
    rationale_summary: str = "bounded_cross_axis_integration"
    source_refs: List[str] = Field(default_factory=list)
    last_updated: float = Field(default_factory=time.time)


class CrossAxisPriorityState(BaseModel):
    priority_id: str = "phase1"
    policy_mode: str = "stability_first"
    selected_priority: ArbitrationPriority = ArbitrationPriority.REVIEW
    stabilize_weight: float = Field(default=0.6, ge=0.0, le=1.0)
    conserve_weight: float = Field(default=0.55, ge=0.0, le=1.0)
    guard_weight: float = Field(default=0.55, ge=0.0, le=1.0)
    review_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    repair_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    grow_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    reflective_modifier: float = Field(default=0.1, ge=0.0, le=1.0)
    priority_reason: str = "phase1_stability_first_default"
    upstream_pressure_sources: List[str] = Field(default_factory=list)
    source_refs: List[str] = Field(default_factory=list)
    last_updated: float = Field(default_factory=time.time)


class ProposalConflictState(BaseModel):
    conflict_id: str = "phase1"
    highest_severity: ConflictSeverity = ConflictSeverity.NONE
    conflict_count: int = Field(default=0, ge=0, le=64)
    unresolved_conflict_refs: List[str] = Field(default_factory=list)
    blocked_axes: List[str] = Field(default_factory=list)
    resolution_posture: ArbitrationPriority = ArbitrationPriority.REVIEW
    source_refs: List[str] = Field(default_factory=list)
    last_updated: float = Field(default_factory=time.time)


class ArbitrationBalance(BaseModel):
    balance_id: str
    lower_pole: str
    upper_pole: str
    lower_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    upper_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    preferred_pole: str
    rationale: str = ""
    source_refs: List[str] = Field(default_factory=list)
    last_updated: float = Field(default_factory=time.time)


class IntegratedTendencyProposal(BaseModel):
    proposal_id: str
    tendency_label: str
    priority_mode: ArbitrationPriority = ArbitrationPriority.REVIEW
    policy_mode: str = "stability_first"
    proposed_effects: Dict[str, Any] = Field(default_factory=dict)
    justification: str
    required_gate: str
    effect_scope: str = "proposal_only"
    behavioral_authority: str = "none"
    requested_effects: List[str] = Field(default_factory=list)
    source_refs: List[str] = Field(default_factory=list)
    status: IntegratedProposalStatus = IntegratedProposalStatus.PROPOSED
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class AxisArbitrationHint(BaseModel):
    hint_id: str
    axis_name: str
    recommendation: str
    priority_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    guardrail_summary: str = ""
    advisory_only: bool = True
    source_refs: List[str] = Field(default_factory=list)
    last_updated: float = Field(default_factory=time.time)


class IntegrationLedgerEntry(BaseModel):
    ledger_id: str
    event_type: str
    reference_id: str
    gate_name: str
    gate_verdict: str
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
