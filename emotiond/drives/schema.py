"""
MVP14 T01: Endogenous Drive Schema

Structural representation of internal drives, homeostatic signals,
and maintenance debt.
"""
import time
import hashlib
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class DriveType(str, Enum):
    """Types of endogenous drives."""
    STABILITY = "stability"
    COHERENCE = "coherence"
    COMPLETION = "completion"
    VERIFICATION = "verification"
    REPAIR = "repair"
    EXPLORATION = "exploration"
    CONSERVATION = "conservation"


class ActiveDrive(BaseModel):
    """
    A single active internal drive.
    
    Drives represent internal pressures that influence prioritization.
    """
    drive_id: str = Field(..., description="Unique drive identifier")
    drive_type: DriveType = Field(..., description="Type of drive")
    intensity: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Current intensity [0, 1]"
    )
    source: str = Field(
        default="internal",
        description="Source of this drive"
    )
    persistence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="How persistent this drive is"
    )
    last_updated: float = Field(default_factory=time.time)
    linked_tensions: List[str] = Field(
        default_factory=list,
        description="Tension types linked to this drive"
    )
    candidate_bias: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
        description="Bias applied to candidate scoring"
    )
    
    def compute_pressure(self) -> float:
        """Compute effective pressure (intensity * persistence)."""
        return self.intensity * self.persistence


class HomeostaticSignal(BaseModel):
    """
    Measurable deviation from desired operating balance.
    
    Homeostatic signals indicate when the system is outside
    its preferred operating range.
    """
    signal_id: str = Field(..., description="Unique signal identifier")
    category: str = Field(..., description="Signal category")
    observed_value: float = Field(..., description="Current observed value")
    desired_range_min: float = Field(default=0.0, description="Minimum desired value")
    desired_range_max: float = Field(default=1.0, description="Maximum desired value")
    deviation_level: float = Field(default=0.0, ge=0.0, description="Deviation magnitude")
    last_checked: float = Field(default_factory=time.time)
    
    def compute_deviation(self) -> float:
        """Compute deviation from desired range."""
        if self.observed_value < self.desired_range_min:
            self.deviation_level = self.desired_range_min - self.observed_value
        elif self.observed_value > self.desired_range_max:
            self.deviation_level = self.observed_value - self.desired_range_max
        else:
            self.deviation_level = 0.0
        return self.deviation_level
    
    def is_in_balance(self) -> bool:
        """Check if signal is within desired range."""
        return self.deviation_level == 0.0


class MaintenanceDebt(BaseModel):
    """
    Accumulated upkeep obligations.
    
    Maintenance debt represents tasks that the system should
    perform to maintain itself.
    """
    debt_id: str = Field(..., description="Unique debt identifier")
    category: str = Field(..., description="Debt category")
    amount: float = Field(default=0.0, ge=0.0, description="Debt amount")
    priority: float = Field(default=0.5, ge=0.0, le=1.0, description="Priority level")
    source: str = Field(default="internal", description="Source of debt")
    created_at: float = Field(default_factory=time.time)
    last_updated: float = Field(default_factory=time.time)
    
    def add_debt(self, delta: float) -> None:
        """Add to debt amount."""
        self.amount += delta
        self.last_updated = time.time()
    
    def reduce_debt(self, delta: float) -> None:
        """Reduce debt amount."""
        self.amount = max(0.0, self.amount - delta)
        self.last_updated = time.time()


class RegulationTarget(BaseModel):
    """
    Preferred operating range for a system parameter.
    """
    target_name: str = Field(..., description="Name of regulated parameter")
    desired_range_min: float = Field(default=0.3, description="Minimum desired value")
    desired_range_max: float = Field(default=0.7, description="Maximum desired value")
    observed_value: float = Field(default=0.5, description="Current observed value")
    deviation_level: float = Field(default=0.0, description="Current deviation")
    
    def update_observed(self, value: float) -> float:
        """Update observed value and compute deviation."""
        self.observed_value = value
        
        if value < self.desired_range_min:
            self.deviation_level = self.desired_range_min - value
        elif value > self.desired_range_max:
            self.deviation_level = value - self.desired_range_max
        else:
            self.deviation_level = 0.0
        
        return self.deviation_level
    
    def is_regulated(self) -> bool:
        """Check if within regulation range."""
        return self.deviation_level == 0.0


class DriveHistoryEntry(BaseModel):
    """A single drive transition entry."""
    timestamp: float = Field(default_factory=time.time)
    drive_id: str = Field(..., description="Affected drive")
    change_type: str = Field(..., description="Type of change")
    old_value: Optional[float] = Field(default=None, description="Previous value")
    new_value: Optional[float] = Field(default=None, description="New value")
    cause: str = Field(default="", description="Cause of change")
    evidence: Dict[str, Any] = Field(default_factory=dict)


class DriveHistory(BaseModel):
    """History of drive transitions."""
    entries: List[DriveHistoryEntry] = Field(default_factory=list)
    max_entries: int = Field(default=500, description="Maximum entries to retain")
    
    def record(
        self,
        drive_id: str,
        change_type: str,
        old_value: Optional[float],
        new_value: Optional[float],
        cause: str = "",
        evidence: Optional[Dict[str, Any]] = None
    ) -> DriveHistoryEntry:
        """Record a drive transition."""
        entry = DriveHistoryEntry(
            drive_id=drive_id,
            change_type=change_type,
            old_value=old_value,
            new_value=new_value,
            cause=cause,
            evidence=evidence or {}
        )
        self.entries.append(entry)
        
        # Prune if needed
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]
        
        return entry
    
    def get_recent(self, n: int = 10) -> List[DriveHistoryEntry]:
        """Get recent entries."""
        return self.entries[-n:]


class DriveState(BaseModel):
    """
    Complete drive state for MVP14.
    
    Contains all active drives, homeostatic signals, and maintenance debt.
    """
    # Active drives
    active_drives: Dict[str, ActiveDrive] = Field(default_factory=dict)
    
    # Latent (inactive but relevant) drives
    latent_drives: Dict[str, ActiveDrive] = Field(default_factory=dict)
    
    # Homeostatic signals
    homeostatic_signals: Dict[str, HomeostaticSignal] = Field(default_factory=dict)
    
    # Maintenance debt
    maintenance_debt: Dict[str, MaintenanceDebt] = Field(default_factory=dict)
    
    # Regulation targets
    regulation_targets: Dict[str, RegulationTarget] = Field(default_factory=dict)
    
    # History
    drive_history: DriveHistory = Field(default_factory=DriveHistory)
    
    # Metadata
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    version: str = Field(default="1.0.0")
    schema_version: str = Field(default="mvp14-v1")
    
    def update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = time.time()
    
    def get_total_drive_pressure(self) -> float:
        """Get total pressure from all active drives."""
        return sum(d.compute_pressure() for d in self.active_drives.values())
    
    def get_total_homeostatic_deviation(self) -> float:
        """Get total homeostatic deviation."""
        return sum(s.deviation_level for s in self.homeostatic_signals.values())
    
    def get_total_maintenance_debt(self) -> float:
        """Get total maintenance debt."""
        return sum(d.amount for d in self.maintenance_debt.values())
    
    def get_dominant_drive(self) -> Optional[ActiveDrive]:
        """Get the drive with highest intensity."""
        if not self.active_drives:
            return None
        return max(self.active_drives.values(), key=lambda d: d.intensity)
    
    def get_urgent_debts(self, threshold: float = 0.7) -> List[MaintenanceDebt]:
        """Get debts above priority threshold."""
        return [
            d for d in self.maintenance_debt.values()
            if d.priority >= threshold
        ]
    
    def get_unbalanced_signals(self) -> List[HomeostaticSignal]:
        """Get signals that are out of balance."""
        return [
            s for s in self.homeostatic_signals.values()
            if not s.is_in_balance()
        ]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of current drive state."""
        return {
            "version": self.version,
            "active_drive_count": len(self.active_drives),
            "total_drive_pressure": self.get_total_drive_pressure(),
            "dominant_drive": (
                self.get_dominant_drive().drive_type.value
                if self.get_dominant_drive() else None
            ),
            "homeostatic_deviation": self.get_total_homeostatic_deviation(),
            "unbalanced_signals": len(self.get_unbalanced_signals()),
            "total_maintenance_debt": self.get_total_maintenance_debt(),
            "urgent_debts": len(self.get_urgent_debts()),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
