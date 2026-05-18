from __future__ import annotations

import time
from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class EnvironmentCouplingStatus(str, Enum):
    STABLE = "stable"
    STRAINED = "strained"
    RECOVERING = "recovering"
    DEGRADED = "degraded"


class BoundaryPressureMode(str, Enum):
    STABLE = "stable"
    GUARDED = "guarded"
    PRESSURED = "pressured"
    REPAIR_ONLY = "repair_only"


class EmbodiedProposalStatus(str, Enum):
    PROPOSED = "proposed"
    HELD = "held"
    APPROVED_FOR_REVIEW = "approved_for_review"
    OBSERVED = "observed"
    REJECTED = "rejected"


class EmbodiedState(BaseModel):
    resource_slack: float = Field(default=0.5, ge=0.0, le=1.0)
    perceived_load: float = Field(default=0.5, ge=0.0, le=1.0)
    action_readiness: float = Field(default=0.5, ge=0.0, le=1.0)
    last_action_source: str = "runtime"
    source_refs: List[str] = Field(default_factory=list)
    last_updated: float = Field(default_factory=time.time)


class EnvironmentCouplingState(BaseModel):
    coupling_id: str
    coupling_strength: float = Field(default=0.5, ge=0.0, le=1.0)
    controllability_estimate: float = Field(default=0.5, ge=0.0, le=1.0)
    recent_outcome_summary: str = ""
    status: EnvironmentCouplingStatus = EnvironmentCouplingStatus.STABLE
    source_refs: List[str] = Field(default_factory=list)
    last_updated: float = Field(default_factory=time.time)


class ResourcePressureState(BaseModel):
    pressure_id: str
    pressure_level: float = Field(default=0.0, ge=0.0, le=1.0)
    slack_level: float = Field(default=1.0, ge=0.0, le=1.0)
    recovery_bias: float = Field(default=0.0, ge=0.0, le=1.0)
    source_refs: List[str] = Field(default_factory=list)
    last_updated: float = Field(default_factory=time.time)


class BoundaryPressureState(BaseModel):
    boundary_id: str
    pressure_level: float = Field(default=0.0, ge=0.0, le=1.0)
    mode: BoundaryPressureMode = BoundaryPressureMode.STABLE
    reason: str = ""
    source_refs: List[str] = Field(default_factory=list)
    last_updated: float = Field(default_factory=time.time)


class ActionConsequenceRecord(BaseModel):
    consequence_id: str
    action_ref: str
    outcome_type: str
    consequence_summary: str
    impact_score: float = Field(default=0.0, ge=0.0, le=1.0)
    controllability_estimate: float = Field(default=0.5, ge=0.0, le=1.0)
    source_refs: List[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class SelfWorldBoundarySemantics(BaseModel):
    semantic_id: str = "self_world"
    distinction_summary: str = "bounded_self_world_boundary"
    guard_bias: float = Field(default=0.5, ge=0.0, le=1.0)
    repair_bias: float = Field(default=0.5, ge=0.0, le=1.0)
    source_refs: List[str] = Field(default_factory=list)
    last_updated: float = Field(default_factory=time.time)


class EmbodiedProposal(BaseModel):
    proposal_id: str
    target_ref: str
    issue_summary: str
    proposal_kind: str = "repair_or_stabilize"
    proposed_adjustment: Dict[str, Any] = Field(default_factory=dict)
    justification: str
    required_gate: str
    effect_scope: str = "proposal_only"
    behavioral_authority: str = "none"
    requested_effects: List[str] = Field(default_factory=list)
    status: EmbodiedProposalStatus = EmbodiedProposalStatus.PROPOSED
    source_refs: List[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class GovernanceLedgerEntry(BaseModel):
    ledger_id: str
    event_type: str
    reference_id: str
    gate_name: str
    gate_verdict: str
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
