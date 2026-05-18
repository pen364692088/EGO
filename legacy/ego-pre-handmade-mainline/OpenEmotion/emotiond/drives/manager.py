"""
Legacy drives manager compatibility surface.

This module re-exports the formal owner manager from
``openemotion.endogenous_drives`` so that older imports keep working without
preserving a second implementation.
"""

from __future__ import annotations

from openemotion.endogenous_drives import DriveManager as _FormalDriveManager
from openemotion.endogenous_drives import EndogenousDriveOwner
from openemotion.endogenous_drives import get_drive_manager as _get_drive_manager
from openemotion.endogenous_drives import reset_drive_manager as _reset_drive_manager

DriveManager = _FormalDriveManager


def get_drive_manager() -> EndogenousDriveOwner:
    return _get_drive_manager()


def reset_drive_manager() -> None:
    _reset_drive_manager()


__all__ = [
    "DriveManager",
    "EndogenousDriveOwner",
    "get_drive_manager",
    "reset_drive_manager",
]
