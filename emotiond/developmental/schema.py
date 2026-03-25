"""
MVP16: Developmental Schema

Long-horizon developmental continuity and governed growth.
"""
import time
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


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


class TransitionRecord(BaseModel):
    """A record of a developmental transition."""
    transition_id: str = Field(..., description="Unique transition ID")
    from_phase: str = Field(..., description="Source phase")
    to_phase: str = Field(..., description="Target phase")
    timestamp: float = Field(default_factory=time.time)
    approved: bool = Field(default=False)
    approver: Optional[str] = Field(default=None)
    replay_hash: str = Field(default="", description="Hash for replay verification")


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
    schema_version: str = Field(default="mvp16-v1")
    
    def update_timestamp(self) -> None:
        self.updated_at = time.time()
    
    def get_long_horizon_score(self) -> float:
        if not self.metrics:
            return 1.0
        return sum(m.value for m in self.metrics.values()) / len(self.metrics)
