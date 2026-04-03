from __future__ import annotations

from typing import Any, Dict, Optional

from .governance import validate_drive_state
from .maintenance import build_self_maintenance_candidate
from .reducers import (
    add_maintenance_debt,
    apply_decay,
    refresh_priority_snapshot,
    seed_default_state,
    update_drive,
    update_homeostatic_signal,
    update_regulation_target,
)
from .schemas import DriveType
from .state import DriveState
from .store import EndogenousDriveStore


class EndogenousDriveOwner:
    _instance: Optional["EndogenousDriveOwner"] = None

    def __init__(self, initial_state: Optional[DriveState] = None, *, store: Optional[EndogenousDriveStore] = None):
        self.state = initial_state.model_copy(deep=True) if initial_state is not None else seed_default_state()
        self.state = refresh_priority_snapshot(self.state)
        self.store = store or EndogenousDriveStore()

    @classmethod
    def get_instance(cls) -> "EndogenousDriveOwner":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def update_drive(
        self,
        drive_type: DriveType,
        intensity_delta: float,
        cause: str = "",
        evidence: Optional[Dict[str, Any]] = None,
    ):
        self.state = update_drive(self.state, drive_type, intensity_delta, cause=cause, evidence=evidence)
        return self.state.active_drives[drive_type.value]

    def accumulate(self, drive_type: DriveType, amount: float = 0.05, cause: str = ""):
        return self.update_drive(drive_type, amount, cause)

    def apply_decay(self) -> None:
        self.state = apply_decay(self.state)

    def activate_drive(self, drive_type: DriveType, intensity: float = 0.5, source: str = ""):
        drive = self.state.active_drives.get(drive_type.value)
        delta = intensity - (drive.intensity if drive else 0.0)
        return self.update_drive(drive_type, delta, source)

    def update_homeostatic_signal(self, signal_id: str, observed_value: float):
        self.state = update_homeostatic_signal(self.state, signal_id, observed_value)
        return self.state.homeostatic_signals[signal_id]

    def add_maintenance_debt(
        self,
        category: str,
        amount: float,
        priority: float = 0.5,
        source: str = "",
    ):
        self.state, debt = add_maintenance_debt(
            self.state,
            category=category,
            amount=amount,
            priority=priority,
            source=source,
        )
        return debt

    def reduce_maintenance_debt(self, debt_id: str, amount: float):
        from .reducers import reduce_maintenance_debt

        self.state = reduce_maintenance_debt(self.state, debt_id=debt_id, amount=amount)
        return self.state.maintenance_debt.get(debt_id)

    def update_regulation_target(self, target_name: str, observed_value: float):
        self.state = update_regulation_target(self.state, target_name=target_name, observed_value=observed_value)
        return self.state.regulation_targets[target_name]

    def get_drive_influence(self, drive_type: DriveType) -> float:
        drive = self.state.active_drives.get(drive_type.value)
        return drive.compute_pressure() if drive else 0.0

    def get_priority_bias(self) -> Dict[str, float]:
        bias_terms = self.state.priority_snapshot.get("bias_terms", {})
        return dict(bias_terms)

    def get_runtime_projection(self) -> Dict[str, Any]:
        return self.state.to_runtime_projection()

    def get_self_maintenance_candidate(self) -> Optional[Dict[str, Any]]:
        return build_self_maintenance_candidate(self.state)

    def check_health(self) -> Dict[str, Any]:
        summary = self.state.get_summary()
        verdict = validate_drive_state(self.state)
        issues = list(verdict.violations)
        if summary["homeostatic_deviation"] > 0.5:
            issues.append("high_homeostatic_deviation")
        if summary["urgent_debts"] > 3:
            issues.append("high_maintenance_debt")
        return {"healthy": len(issues) == 0, "issues": issues, "summary": summary}

    def persist(self, *, update_source: str, trace_reference: Optional[str] = None):
        record = self.store.save(self.state, update_source=update_source, trace_reference=trace_reference)
        persisted = self.store.load()
        if persisted is not None:
            self.state = persisted
        return record

    def apply_owner_delta(self, delta: Dict[str, Any]) -> Dict[str, Any]:
        changed_fields = set()
        for item in list(delta.get("drive_adjustments") or []):
            drive_type = item.get("drive_type")
            intensity_delta = float(item.get("intensity_delta") or 0.0)
            if drive_type and intensity_delta:
                self.update_drive(
                    DriveType(str(drive_type)),
                    intensity_delta,
                    cause=str(item.get("cause") or "proto_self_v2"),
                    evidence=dict(item.get("evidence") or {}),
                )
                changed_fields.add("active_drives")
                changed_fields.add("priority_snapshot")
        for item in list(delta.get("homeostatic_updates") or []):
            signal_id = str(item.get("signal_id") or "").strip()
            if signal_id:
                self.update_homeostatic_signal(signal_id, float(item.get("observed_value") or 0.0))
                changed_fields.add("homeostatic_signals")
                changed_fields.add("priority_snapshot")
        for item in list(delta.get("maintenance_debts") or []):
            category = str(item.get("category") or "").strip()
            amount = float(item.get("amount") or 0.0)
            if category and amount > 0.0:
                self.add_maintenance_debt(
                    category=category,
                    amount=amount,
                    priority=float(item.get("priority") or 0.5),
                    source=str(item.get("source") or "proto_self_v2"),
                )
                changed_fields.add("maintenance_debt")
                changed_fields.add("priority_snapshot")
        return {"changed_fields": sorted(changed_fields)}

    def get_state(self) -> DriveState:
        return self.state

    def get_summary(self) -> Dict[str, Any]:
        return self.state.get_summary()


DriveManager = EndogenousDriveOwner


def get_drive_manager() -> EndogenousDriveOwner:
    return EndogenousDriveOwner.get_instance()


def reset_drive_manager() -> None:
    EndogenousDriveOwner.reset()
