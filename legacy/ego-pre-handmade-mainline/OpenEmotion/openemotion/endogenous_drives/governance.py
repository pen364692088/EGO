from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from .state import DriveState, FORMAL_OWNER_SCHEMA_VERSION


class DriveGovernanceVerdict(BaseModel):
    accepted: bool = True
    violations: List[str] = Field(default_factory=list)


def validate_drive_state(state: DriveState) -> DriveGovernanceVerdict:
    violations: List[str] = []
    if state.schema_version != FORMAL_OWNER_SCHEMA_VERSION:
        violations.append("invalid_schema_version")
    if state.get_total_drive_pressure() > 5.0:
        violations.append("excessive_drive_pressure")
    if state.get_total_homeostatic_deviation() > 2.0:
        violations.append("excessive_homeostatic_deviation")
    for drive_id, drive in state.active_drives.items():
        if drive.drive_id != drive_id:
            violations.append(f"drive_id_mismatch:{drive_id}")
        for effect_key, effect_value in drive.candidate_effects.items():
            if not -1.0 <= effect_value <= 1.0:
                violations.append(f"candidate_effect_out_of_range:{drive_id}:{effect_key}")
    for debt_id, debt in state.maintenance_debt.items():
        if debt.debt_id != debt_id:
            violations.append(f"debt_id_mismatch:{debt_id}")
    return DriveGovernanceVerdict(accepted=not violations, violations=violations)
