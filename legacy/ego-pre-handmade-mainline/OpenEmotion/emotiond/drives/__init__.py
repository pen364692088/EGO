"""
Legacy drives compatibility surface.

The formal authority lives in ``openemotion.endogenous_drives``. This package
keeps the older import paths available as thin re-exports so they cannot drift
into a second implementation.
"""
from __future__ import annotations

from openemotion.endogenous_drives import (
    ActiveDrive,
    DriveHistory,
    DriveManager,
    DriveState,
    DriveType,
    EndogenousDriveOwner,
    HomeostaticSignal,
    MaintenanceDebt,
    RegulationTarget,
    get_drive_manager,
    reset_drive_manager,
)

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
    "EndogenousDriveOwner",
    "get_drive_manager",
    "reset_drive_manager",
    "LegacyDriveType",
    "DriveLevel",
    "DriveCandidate",
    "Drives",
    "drives_from_valence",
]
