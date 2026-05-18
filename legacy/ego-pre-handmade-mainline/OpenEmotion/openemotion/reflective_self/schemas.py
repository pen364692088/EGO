from __future__ import annotations

import time
from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ReflectionTargetType(str, Enum):
    STATE = "state"
    BEHAVIOR = "behavior"
    DECISION = "decision"
    TRAJECTORY = "trajectory"
    MAINTENANCE = "maintenance"
    SELF_MODEL = "self_model"
    DRIVE_STATE = "drive_state"


class ReflectionQueueItem(BaseModel):
    reflection_id: str
    target_type: ReflectionTargetType
    target_reference: str
    priority: float = Field(default=0.5, ge=0.0, le=1.0)
    trigger_source: str = "internal"
    created_at: float = Field(default_factory=time.time)
    status: str = "pending"
    started_at: float | None = None
    completed_at: float | None = None
    resolution_note: str | None = None
    evidence_refs: List[str] = Field(default_factory=list)
    requested_effects: List[str] = Field(default_factory=list)


class ReflectionTarget(BaseModel):
    target_id: str
    target_type: ReflectionTargetType
    reference: str
    salience: float = Field(default=0.5, ge=0.0, le=1.0)
    reason: str = ""
    evidence_refs: List[str] = Field(default_factory=list)
    last_seen_at: float = Field(default_factory=time.time)


class DiagnosisRecord(BaseModel):
    diagnosis_id: str
    analyzed_target: str
    detected_pattern: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    supporting_evidence: List[str] = Field(default_factory=list)
    suggested_action: str | None = None
    status: str = "identified"
    created_at: float = Field(default_factory=time.time)


class CounterfactualRecord(BaseModel):
    counterfactual_id: str
    baseline_reference: str
    alternative_path: str
    expected_difference: Dict[str, Any] = Field(default_factory=dict)
    evidence_basis: List[str] = Field(default_factory=list)
    uncertainty_level: float = Field(default=0.5, ge=0.0, le=1.0)
    truth_status: str = "counterfactual_uncertain"
    created_at: float = Field(default_factory=time.time)


class RevisionProposal(BaseModel):
    proposal_id: str
    target_layer: str
    proposed_change: Dict[str, Any] = Field(default_factory=dict)
    justification: str
    reversibility: str = "reversible"
    required_gate: str
    effect_scope: str = "proposal_only"
    requested_effects: List[str] = Field(default_factory=list)
    status: str = "proposed"
    gate_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class UnresolvedReflectionItem(BaseModel):
    item_id: str
    summary: str
    linked_record_id: str | None = None
    severity: float = Field(default=0.5, ge=0.0, le=1.0)
    follow_up_required: bool = True
    created_at: float = Field(default_factory=time.time)
