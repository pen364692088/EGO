"""
Legacy drives schema compatibility surface.

This module is intentionally a thin re-export of the formal owner package
under ``openemotion.endogenous_drives`` so that legacy imports do not behave
like a second authority surface.
"""

from __future__ import annotations

from openemotion.endogenous_drives import (
    ActiveDrive,
    DriveHistory,
    DriveState,
    DriveType,
    HomeostaticSignal,
    MaintenanceDebt,
    RegulationTarget,
)

__all__ = [
    "DriveState",
    "ActiveDrive",
    "DriveType",
    "HomeostaticSignal",
    "MaintenanceDebt",
    "RegulationTarget",
    "DriveHistory",
]
