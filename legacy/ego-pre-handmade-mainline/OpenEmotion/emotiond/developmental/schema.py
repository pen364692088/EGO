"""
MVP16: Developmental Schema

Long-horizon developmental continuity and governed growth.

WP11 / MVP16 status:
- reference-only compatibility surface
- not the formal owner schema
"""
from __future__ import annotations

import time
from typing import Dict, Any, Optional, List

from pydantic import BaseModel, Field


class DevelopmentalWritebackEvent(BaseModel):
    """Canonical host -> OpenEmotion contract for admission-grade developmental writeback."""

    source_type: str = Field(..., description="Ingress evidence source type")
    session_id: str = Field(..., description="Canonical host session identifier")
    sample_ref: str = Field(..., description="Reference to the persisted sample.json")
    ledger_ref: str = Field(..., description="Reference to the authoritative ledger.json")
    user_turn_kind: str = Field(..., description="natural_language or command")
    final_action: str = Field(..., description="Final host delivery/action kind")
    outcome_summary: str = Field(default="", description="Observed host-side outcome summary")
    proto_self_output_schema_version: str = Field(..., description="Observed OpenEmotion result schema version")
    proto_self_trace_schema_version: str = Field(..., description="Observed OpenEmotion trace schema version")
    governance_snapshot: Dict[str, Any] = Field(default_factory=dict)
    invariant_snapshot: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
    calendar_day: str = Field(default="", description="Calendar day for cross-day continuity accounting")
    sample_id: Optional[str] = Field(default=None)
    replay_ref: str = Field(default="", description="Reference to the persisted replay.json")
    trigger_ref: Optional[str] = Field(default=None, description="Optional command/sample ref that triggered this writeback")


class DevelopmentalEpisode(BaseModel):
    """A developmental episode in the system's growth."""

    episode_id: str = Field(..., description="Unique episode identifier")
    episode_type: str = Field(..., description="Type of episode")
    phase: str = Field(..., description="Developmental phase")
    description: str = Field(default="", description="Episode description")
    started_at: float = Field(default_factory=time.time)
    completed_at: Optional[float] = Field(default=None)
    achievements: List[str] = Field(default_factory=list)
    metrics_before: Dict[str, float] = Field(default_factory=dict)
    metrics_after: Dict[str, float] = Field(default_factory=dict)
    source_type: str = Field(default="", description="Evidence source type")
    session_id: str = Field(default="", description="Canonical host session identifier")
    sample_ref: str = Field(default="", description="Reference to the persisted sample.json")
    ledger_ref: str = Field(default="", description="Reference to the authoritative ledger.json")
    replay_ref: str = Field(default="", description="Reference to the persisted replay.json")
    final_action: str = Field(default="", description="Final host delivery/action kind")
    outcome_summary: str = Field(default="", description="Observed host-side outcome summary")
    proto_self_output_schema_version: str = Field(default="", description="Observed OpenEmotion result schema version")
    proto_self_trace_schema_version: str = Field(default="", description="Observed OpenEmotion trace schema version")
    real_mainline: bool = Field(default=False, description="Whether this episode comes from the real admission-grade mainline")
    governance_snapshot: Dict[str, Any] = Field(default_factory=dict)
    invariant_snapshot: Dict[str, Any] = Field(default_factory=dict)
    calendar_day: str = Field(default="", description="Calendar day for continuity accounting")


class TransitionRecord(BaseModel):
    """A record of a developmental transition."""

    transition_id: str = Field(..., description="Unique transition ID")
    from_phase: str = Field(..., description="Source phase")
    to_phase: str = Field(..., description="Target phase")
    timestamp: float = Field(default_factory=time.time)
    approved: bool = Field(default=False)
    approver: Optional[str] = Field(default=None)
    replay_hash: str = Field(default="", description="Hash for replay verification")
    transition_kind: str = Field(default="phase_change", description="Transition class")
    from_episode_ref: str = Field(default="", description="Episode ref before the transition")
    to_episode_ref: str = Field(default="", description="Episode ref after the transition")
    trigger_ref: str = Field(default="", description="Sample or command ref that triggered the transition")
    replay_ref: str = Field(default="", description="Replay artifact reference for transition audit")


class GrowthMetric(BaseModel):
    """A metric tracking developmental growth."""

    metric_name: str = Field(..., description="Metric name")
    value: float = Field(default=0.0)
    target: Optional[float] = Field(default=None)
    trend: str = Field(default="stable")
    history: List[float] = Field(default_factory=list)


class DevelopmentalTrajectory(BaseModel):
    """The developmental trajectory of the system."""

    trajectory_id: str = Field(default="main")
    episodes: List[DevelopmentalEpisode] = Field(default_factory=list)
    transitions: List[TransitionRecord] = Field(default_factory=list)
    current_phase: str = Field(default="MVP16")
    identity_preserved: bool = Field(default=True)


class DevelopmentalState(BaseModel):
    """Complete developmental state for MVP16."""

    trajectory: DevelopmentalTrajectory = Field(default_factory=DevelopmentalTrajectory)
    metrics: Dict[str, GrowthMetric] = Field(default_factory=dict)

    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    version: str = Field(default="1.0.0")
    schema_version: str = Field(default="mvp16-v2")

    def update_timestamp(self) -> None:
        self.updated_at = time.time()

    def get_long_horizon_score(self) -> float:
        if not self.metrics:
            return 1.0
        return sum(m.value for m in self.metrics.values()) / len(self.metrics)
