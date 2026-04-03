from __future__ import annotations

import copy
import time
from typing import Any, Dict, Optional, Tuple

from .schemas import ActiveDrive, DriveType, HomeostaticSignal, MaintenanceDebt, RegulationTarget
from .state import DriveState

DEFAULT_DRIVES = (
    (DriveType.STABILITY, 0.75, "System stability maintenance"),
    (DriveType.COHERENCE, 0.25, "Internal consistency maintenance"),
    (DriveType.COMPLETION, 0.5, "Goal completion pressure"),
    (DriveType.VERIFICATION, 0.75, "State verification drive"),
    (DriveType.REPAIR, 0.15, "Self-repair drive"),
    (DriveType.EXPLORATION, 0.4, "Capability exploration drive"),
    (DriveType.CONSERVATION, 0.3, "Resource conservation drive"),
)

DEFAULT_SIGNALS = (
    ("identity_stability", 0.8, 0.6, 1.0),
    ("continuity_quality", 0.7, 0.5, 1.0),
    ("maintenance_balance", 0.5, 0.3, 0.7),
    ("tension_resolution", 0.4, 0.2, 0.6),
)

DEFAULT_TARGETS = (
    ("drive_pressure", 0.2, 0.8),
    ("homeostatic_deviation", 0.0, 0.3),
    ("maintenance_debt", 0.0, 0.5),
)


def clone_state(state: DriveState) -> DriveState:
    return state.model_copy(deep=True)


def refresh_priority_snapshot(state: DriveState) -> DriveState:
    dominant = state.get_dominant_drive()
    state.priority_snapshot = {
        "dominant_drive": dominant.drive_type.value if dominant else None,
        "total_drive_pressure": state.get_total_drive_pressure(),
        "maintenance_pressure": state.get_total_maintenance_debt(),
        "homeostatic_deviation": state.get_total_homeostatic_deviation(),
        "bias_terms": {
            drive_id: drive.compute_pressure()
            for drive_id, drive in sorted(state.active_drives.items())
        },
    }
    return state


def seed_default_state() -> DriveState:
    state = DriveState()
    for drive_type, intensity, source in DEFAULT_DRIVES:
        state.active_drives[drive_type.value] = ActiveDrive(
            drive_id=drive_type.value,
            drive_type=drive_type,
            intensity=intensity,
            source=source,
        )
    for name, value, min_val, max_val in DEFAULT_SIGNALS:
        signal = HomeostaticSignal(
            signal_id=name,
            category="system_health",
            observed_value=value,
            desired_range_min=min_val,
            desired_range_max=max_val,
        )
        signal.compute_deviation()
        state.homeostatic_signals[name] = signal
    for name, min_val, max_val in DEFAULT_TARGETS:
        state.regulation_targets[name] = RegulationTarget(
            target_name=name,
            desired_range_min=min_val,
            desired_range_max=max_val,
        )
    refresh_priority_snapshot(state)
    return state


def update_drive(
    state: DriveState,
    drive_type: DriveType,
    intensity_delta: float,
    *,
    cause: str = "",
    evidence: Optional[Dict[str, Any]] = None,
) -> DriveState:
    next_state = clone_state(state)
    drive_id = drive_type.value
    if drive_id not in next_state.active_drives:
        next_state.active_drives[drive_id] = ActiveDrive(
            drive_id=drive_id,
            drive_type=drive_type,
            intensity=min(1.0, max(0.0, 0.3 + intensity_delta)),
            source=cause or "internal",
        )
        next_state.drive_history.record(drive_id, "activation", None, next_state.active_drives[drive_id].intensity, cause, evidence)
    else:
        drive = next_state.active_drives[drive_id]
        old_intensity = drive.intensity
        drive.intensity = min(1.0, max(0.0, drive.intensity + intensity_delta))
        drive.last_updated = time.time()
        next_state.drive_history.record(drive_id, "intensity_update", old_intensity, drive.intensity, cause, evidence)
    next_state.update_timestamp()
    return refresh_priority_snapshot(next_state)


def apply_decay(state: DriveState, *, decay_rate: float = 0.01, deactivation_threshold: float = 0.1) -> DriveState:
    next_state = clone_state(state)
    move_to_latent = []
    for drive_id, drive in next_state.active_drives.items():
        old_intensity = drive.intensity
        drive.intensity = max(0.0, drive.intensity - decay_rate)
        drive.last_updated = time.time()
        if drive.intensity < deactivation_threshold:
            move_to_latent.append(drive_id)
        elif drive.intensity != old_intensity:
            next_state.drive_history.record(drive_id, "decay", old_intensity, drive.intensity, "automatic_decay")
    for drive_id in move_to_latent:
        next_state.latent_drives[drive_id] = next_state.active_drives.pop(drive_id)
    next_state.update_timestamp()
    return refresh_priority_snapshot(next_state)


def update_homeostatic_signal(state: DriveState, signal_id: str, observed_value: float) -> DriveState:
    next_state = clone_state(state)
    if signal_id not in next_state.homeostatic_signals:
        next_state.homeostatic_signals[signal_id] = HomeostaticSignal(
            signal_id=signal_id,
            category="custom",
            observed_value=observed_value,
        )
    signal = next_state.homeostatic_signals[signal_id]
    signal.observed_value = observed_value
    deviation = signal.compute_deviation()
    signal.last_checked = time.time()
    next_state.update_timestamp()
    next_state = refresh_priority_snapshot(next_state)
    if deviation > 0.1:
        next_state = update_drive(
            next_state,
            DriveType.STABILITY,
            deviation * 0.5,
            cause=f"homeostatic_deviation:{signal_id}",
        )
    return next_state


def add_maintenance_debt(
    state: DriveState,
    *,
    category: str,
    amount: float,
    priority: float = 0.5,
    source: str = "",
) -> Tuple[DriveState, MaintenanceDebt]:
    next_state = clone_state(state)
    sequence = 1 + sum(1 for debt in next_state.maintenance_debt.values() if debt.category == category)
    debt_id = f"{category}_{sequence:03d}"
    debt = MaintenanceDebt(
        debt_id=debt_id,
        category=category,
        amount=amount,
        priority=priority,
        source=source or "internal",
    )
    next_state.maintenance_debt[debt_id] = debt
    next_state.drive_history.record(debt_id, "maintenance_debt_add", None, amount, source or category)
    next_state.update_timestamp()
    next_state = refresh_priority_snapshot(next_state)
    next_state = update_drive(next_state, DriveType.REPAIR, amount * 0.1, cause=f"maintenance_debt:{category}")
    return next_state, next_state.maintenance_debt[debt_id]


def reduce_maintenance_debt(state: DriveState, *, debt_id: str, amount: float) -> DriveState:
    next_state = clone_state(state)
    debt = next_state.maintenance_debt.get(debt_id)
    if debt is None:
        return next_state
    old_amount = debt.amount
    debt.reduce_debt(amount)
    next_state.drive_history.record(debt_id, "maintenance_debt_reduce", old_amount, debt.amount, "debt_reduction")
    if debt.amount == 0.0:
        del next_state.maintenance_debt[debt_id]
    next_state.update_timestamp()
    return refresh_priority_snapshot(next_state)


def update_regulation_target(state: DriveState, *, target_name: str, observed_value: float) -> DriveState:
    next_state = clone_state(state)
    if target_name not in next_state.regulation_targets:
        next_state.regulation_targets[target_name] = RegulationTarget(target_name=target_name)
    next_state.regulation_targets[target_name].update_observed(observed_value)
    next_state.update_timestamp()
    return refresh_priority_snapshot(next_state)
