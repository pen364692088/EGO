from __future__ import annotations

from dataclasses import asdict, dataclass

from ego_desktop_lab.belief_state import clamp01
from ego_desktop_lab.pressure import MotivationPressure


@dataclass(frozen=True)
class AffectiveDriveState:
    frustration_pressure: float = 0.0
    curiosity_pressure: float = 0.0
    caution_pressure: float = 0.0
    urgency_pressure: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "frustration_pressure", clamp01(self.frustration_pressure))
        object.__setattr__(self, "curiosity_pressure", clamp01(self.curiosity_pressure))
        object.__setattr__(self, "caution_pressure", clamp01(self.caution_pressure))
        object.__setattr__(self, "urgency_pressure", clamp01(self.urgency_pressure))

    def to_dict(self) -> dict[str, float]:
        return {key: round(float(value), 6) for key, value in asdict(self).items()}

    def pressure_bias_delta(self) -> dict[str, float]:
        """Project bounded drive state into viability pressure bias.

        The drive loop can shift option ranking inside the lab, but it cannot
        create an action, bypass a gate, or write runtime state.
        """

        return {
            "viability_error": round((0.22 * self.frustration_pressure) - (0.06 * self.urgency_pressure), 6),
            "prediction_error": round((0.18 * self.frustration_pressure) + (0.08 * self.curiosity_pressure), 6),
            "commitment_error": round((0.12 * self.urgency_pressure) + (0.04 * self.curiosity_pressure), 6),
            "boundary_error": round(0.18 * self.caution_pressure, 6),
            "uncertainty_precision": round((0.14 * self.caution_pressure) + (0.08 * self.curiosity_pressure), 6),
        }


def derive_affective_drive_state(pressure: MotivationPressure) -> AffectiveDriveState:
    return AffectiveDriveState(
        frustration_pressure=(0.55 * pressure.viability_error) + (0.45 * pressure.prediction_error),
        curiosity_pressure=(
            (0.45 * pressure.uncertainty_precision)
            + (0.35 * pressure.prediction_error)
            + (0.20 * pressure.commitment_error)
        ),
        caution_pressure=(0.65 * pressure.boundary_error) + (0.35 * pressure.uncertainty_precision),
        urgency_pressure=(0.70 * pressure.commitment_error) + (0.30 * (1.0 - pressure.viability_error)),
    )
