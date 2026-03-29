"""
MVP14: Endogenous Drives + Self-Maintenance

Provides internal pressure sources that influence prioritization
within governed boundaries.
"""
from __future__ import annotations

from .schema import (
    DriveState,
    ActiveDrive,
    DriveType,
    HomeostaticSignal,
    MaintenanceDebt,
    RegulationTarget,
    DriveHistory,
)
from .manager import DriveManager, get_drive_manager, reset_drive_manager
from .._legacy_drives import (
    DriveType as LegacyDriveType,
    DriveLevel,
    DriveCandidate,
    Drives,
    drives_from_valence,
)

__all__ = [
    "DriveState",
    "ActiveDrive",
    "DriveType",
    "HomeostaticSignal",
    "MaintenanceDebt",
    "RegulationTarget",
    "DriveHistory",
    "DriveManager",
    "get_drive_manager",
    "reset_drive_manager",
    "LegacyDriveType",
    "DriveLevel",
    "DriveCandidate",
    "Drives",
    "drives_from_valence",
]
