from __future__ import annotations

from typing import Any, Dict, List

from .maintenance import build_self_maintenance_candidate
from .state import DriveState


def _sorted_active_drives(state: DriveState) -> List[Dict[str, Any]]:
    drives = []
    for drive_id, drive in sorted(state.active_drives.items()):
        drives.append(
            {
                "drive_id": drive_id,
                "drive_type": drive.drive_type.value,
                "intensity": drive.intensity,
                "persistence": drive.persistence,
                "candidate_bias": drive.candidate_bias,
                "pressure": drive.compute_pressure(),
            }
        )
    return drives


def _sorted_signals(state: DriveState) -> List[Dict[str, Any]]:
    signals = []
    for signal_id, signal in sorted(state.homeostatic_signals.items()):
        signals.append(
            {
                "signal_id": signal_id,
                "category": signal.category,
                "observed_value": signal.observed_value,
                "desired_range_min": signal.desired_range_min,
                "desired_range_max": signal.desired_range_max,
                "deviation_level": signal.deviation_level,
            }
        )
    return signals


def _sorted_debts(state: DriveState) -> List[Dict[str, Any]]:
    debts = []
    for debt_id, debt in sorted(state.maintenance_debt.items()):
        debts.append(
            {
                "debt_id": debt_id,
                "category": debt.category,
                "amount": debt.amount,
                "priority": debt.priority,
                "source": debt.source,
            }
        )
    return debts


def compact_endogenous_drive_context(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    state = DriveState.model_validate(snapshot)
    return {
        "schema_version": state.schema_version,
        "owner_revision": state.owner_revision,
        "last_revision_id": state.last_revision_id,
        "active_drives": _sorted_active_drives(state),
        "homeostatic_signals": _sorted_signals(state),
        "maintenance_debt": _sorted_debts(state),
        "priority_snapshot": dict(state.priority_snapshot),
        "summary": state.get_summary(),
        "self_maintenance_candidate": build_self_maintenance_candidate(state),
    }
