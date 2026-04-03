from __future__ import annotations

from typing import Any, Dict, Optional

from .state import DriveState


def compute_maintenance_status(state: DriveState) -> Dict[str, Any]:
    urgent_debts = state.get_urgent_debts()
    unbalanced_signals = state.get_unbalanced_signals()
    repair_drive = state.active_drives.get("repair")
    repair_pressure = repair_drive.compute_pressure() if repair_drive else 0.0
    total_debt = state.get_total_maintenance_debt()
    should_maintain = bool(urgent_debts or len(unbalanced_signals) >= 2 or total_debt >= 0.5)
    return {
        "urgent_maintenance": len(urgent_debts),
        "homeostatic_issues": len(unbalanced_signals),
        "repair_drive_pressure": repair_pressure,
        "total_maintenance_debt": total_debt,
        "should_maintain": should_maintain,
    }


def build_self_maintenance_candidate(state: DriveState) -> Optional[Dict[str, Any]]:
    status = compute_maintenance_status(state)
    if not status["should_maintain"]:
        return None
    dominant_issue = None
    if status["urgent_maintenance"] > 0:
        dominant_issue = "maintenance_debt"
    elif status["homeostatic_issues"] > 0:
        dominant_issue = "homeostatic_deviation"
    return {
        "category": "self_maintenance",
        "dominant_issue": dominant_issue,
        "priority": min(1.0, 0.4 + status["total_maintenance_debt"] + (status["homeostatic_issues"] * 0.1)),
        "status": status,
    }
