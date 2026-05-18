from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .history import DriveHistory
from .schemas import ActiveDrive, HomeostaticSignal, MaintenanceDebt, RegulationTarget

FORMAL_OWNER_SCHEMA_VERSION = "mvp14-owner-v1"

PHASE1_AUTHORITATIVE_FIELDS = (
    "schema_version",
    "active_drives",
    "latent_drives",
    "homeostatic_signals",
    "maintenance_debt",
    "regulation_targets",
    "drive_history",
    "priority_snapshot",
    "created_at",
    "updated_at",
    "owner_revision",
    "last_revision_id",
)

RUNTIME_LOCAL_PROJECTION_FIELD = "proto_self_v2.state.endogenous_drives"
RUNTIME_LOCAL_PROJECTION_SEMANTICS = "runtime-local bounded projection of formal endogenous drive owner state"


class EndogenousDriveState(BaseModel):
    active_drives: Dict[str, ActiveDrive] = Field(default_factory=dict)
    latent_drives: Dict[str, ActiveDrive] = Field(default_factory=dict)
    homeostatic_signals: Dict[str, HomeostaticSignal] = Field(default_factory=dict)
    maintenance_debt: Dict[str, MaintenanceDebt] = Field(default_factory=dict)
    regulation_targets: Dict[str, RegulationTarget] = Field(default_factory=dict)
    drive_history: DriveHistory = Field(default_factory=DriveHistory)
    priority_snapshot: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    version: str = "1.0.0"
    schema_version: str = FORMAL_OWNER_SCHEMA_VERSION
    owner_revision: int = 0
    last_revision_id: Optional[str] = None

    def update_timestamp(self) -> None:
        self.updated_at = time.time()

    def get_total_drive_pressure(self) -> float:
        return sum(d.compute_pressure() for d in self.active_drives.values())

    def get_total_homeostatic_deviation(self) -> float:
        return sum(signal.deviation_level for signal in self.homeostatic_signals.values())

    def get_total_maintenance_debt(self) -> float:
        return sum(debt.amount for debt in self.maintenance_debt.values())

    def get_dominant_drive(self) -> Optional[ActiveDrive]:
        if not self.active_drives:
            return None
        return max(self.active_drives.values(), key=lambda drive: drive.intensity)

    def get_urgent_debts(self, threshold: float = 0.7) -> List[MaintenanceDebt]:
        return [debt for debt in self.maintenance_debt.values() if debt.priority >= threshold]

    def get_unbalanced_signals(self) -> List[HomeostaticSignal]:
        return [signal for signal in self.homeostatic_signals.values() if not signal.is_in_balance()]

    def get_summary(self) -> Dict[str, Any]:
        dominant = self.get_dominant_drive()
        return {
            "version": self.version,
            "schema_version": self.schema_version,
            "active_drive_count": len(self.active_drives),
            "total_drive_pressure": self.get_total_drive_pressure(),
            "dominant_drive": dominant.drive_type.value if dominant else None,
            "homeostatic_deviation": self.get_total_homeostatic_deviation(),
            "unbalanced_signals": len(self.get_unbalanced_signals()),
            "total_maintenance_debt": self.get_total_maintenance_debt(),
            "urgent_debts": len(self.get_urgent_debts()),
            "owner_revision": self.owner_revision,
            "last_revision_id": self.last_revision_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_runtime_projection(self) -> Dict[str, Any]:
        dominant = self.get_dominant_drive()
        return {
            "owner_revision": self.owner_revision,
            "dominant_drive": dominant.drive_type.value if dominant else None,
            "total_drive_pressure": self.get_total_drive_pressure(),
            "homeostatic_deviation": self.get_total_homeostatic_deviation(),
            "maintenance_pressure": self.get_total_maintenance_debt(),
            "priority_snapshot": dict(self.priority_snapshot),
        }


DriveState = EndogenousDriveState
