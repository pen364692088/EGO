from __future__ import annotations

import time
from enum import Enum
from typing import Dict, List

from pydantic import BaseModel, Field


class DriveType(str, Enum):
    STABILITY = "stability"
    COHERENCE = "coherence"
    COMPLETION = "completion"
    VERIFICATION = "verification"
    REPAIR = "repair"
    EXPLORATION = "exploration"
    CONSERVATION = "conservation"


class ActiveDrive(BaseModel):
    drive_id: str = Field(..., description="Unique drive identifier")
    drive_type: DriveType = Field(..., description="Type of drive")
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    source: str = Field(default="internal")
    persistence: float = Field(default=0.5, ge=0.0, le=1.0)
    last_updated: float = Field(default_factory=time.time)
    linked_tensions: List[str] = Field(default_factory=list)
    candidate_bias: float = Field(default=0.0, ge=-1.0, le=1.0)
    candidate_effects: Dict[str, float] = Field(default_factory=dict)

    def compute_pressure(self) -> float:
        return self.intensity * self.persistence


class HomeostaticSignal(BaseModel):
    signal_id: str
    category: str
    observed_value: float
    desired_range_min: float = 0.0
    desired_range_max: float = 1.0
    deviation_level: float = Field(default=0.0, ge=0.0)
    last_checked: float = Field(default_factory=time.time)

    def compute_deviation(self) -> float:
        if self.observed_value < self.desired_range_min:
            self.deviation_level = self.desired_range_min - self.observed_value
        elif self.observed_value > self.desired_range_max:
            self.deviation_level = self.observed_value - self.desired_range_max
        else:
            self.deviation_level = 0.0
        return self.deviation_level

    def is_in_balance(self) -> bool:
        return self.deviation_level == 0.0


class MaintenanceDebt(BaseModel):
    debt_id: str
    category: str
    amount: float = Field(default=0.0, ge=0.0)
    priority: float = Field(default=0.5, ge=0.0, le=1.0)
    source: str = Field(default="internal")
    created_at: float = Field(default_factory=time.time)
    last_updated: float = Field(default_factory=time.time)

    def add_debt(self, delta: float) -> None:
        self.amount += delta
        self.last_updated = time.time()

    def reduce_debt(self, delta: float) -> None:
        self.amount = max(0.0, self.amount - delta)
        self.last_updated = time.time()


class RegulationTarget(BaseModel):
    target_name: str
    desired_range_min: float = 0.3
    desired_range_max: float = 0.7
    observed_value: float = 0.5
    deviation_level: float = 0.0

    def update_observed(self, value: float) -> float:
        self.observed_value = value
        if value < self.desired_range_min:
            self.deviation_level = self.desired_range_min - value
        elif value > self.desired_range_max:
            self.deviation_level = value - self.desired_range_max
        else:
            self.deviation_level = 0.0
        return self.deviation_level

    def is_regulated(self) -> bool:
        return self.deviation_level == 0.0
