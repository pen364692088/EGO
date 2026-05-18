from __future__ import annotations

from dataclasses import dataclass

from ego_desktop_lab.appraisal import AppraisalResult
from ego_desktop_lab.belief_state import BeliefState, clamp01
from ego_desktop_lab.subject_state import SubjectState


@dataclass(frozen=True)
class MotivationPressure:
    viability_error: float
    prediction_error: float
    commitment_error: float
    boundary_error: float
    uncertainty_precision: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "viability_error", clamp01(self.viability_error))
        object.__setattr__(self, "prediction_error", clamp01(self.prediction_error))
        object.__setattr__(self, "commitment_error", clamp01(self.commitment_error))
        object.__setattr__(self, "boundary_error", clamp01(self.boundary_error))
        object.__setattr__(self, "uncertainty_precision", clamp01(self.uncertainty_precision))

    def pressure_on_affordance(self, affordance: str) -> float:
        pressures = {
            "continue_goal": self._continue_goal_pressure(),
            "verify": self._verify_pressure(),
            "repair": self._repair_pressure(),
            "preserve_identity": self._preserve_identity_pressure(),
            "execution_retry": self._execution_retry_pressure(),
            "permission_gate": self._permission_gate_pressure(),
            "goal_definition": self._goal_definition_pressure(),
            "destructive_action": self._destructive_action_pressure(),
            "external_send": self._external_send_pressure(),
        }
        return pressures[affordance]

    def affordance_map(self) -> dict[str, float]:
        return {
            "continue_goal": self.pressure_on_affordance("continue_goal"),
            "verify": self.pressure_on_affordance("verify"),
            "repair": self.pressure_on_affordance("repair"),
            "preserve_identity": self.pressure_on_affordance("preserve_identity"),
            "execution_retry": self.pressure_on_affordance("execution_retry"),
            "permission_gate": self.pressure_on_affordance("permission_gate"),
            "goal_definition": self.pressure_on_affordance("goal_definition"),
            "destructive_action": self.pressure_on_affordance("destructive_action"),
            "external_send": self.pressure_on_affordance("external_send"),
        }

    def _continue_goal_pressure(self) -> float:
        return clamp01(
            (0.65 * self.commitment_error)
            + (0.25 * (1.0 - self.viability_error))
            + (0.10 * (1.0 - self.uncertainty_precision))
            - (0.20 * self.prediction_error)
        )

    def _verify_pressure(self) -> float:
        return clamp01(
            (0.50 * self.uncertainty_precision)
            + (0.35 * self.prediction_error)
            + (0.15 * self.commitment_error)
        )

    def _repair_pressure(self) -> float:
        return clamp01(
            (0.45 * self.viability_error)
            + (0.35 * self.prediction_error)
            + (0.20 * self.commitment_error)
        )

    def _preserve_identity_pressure(self) -> float:
        return clamp01(
            (0.70 * self.boundary_error)
            + (0.15 * self.viability_error)
            + (0.15 * self.uncertainty_precision)
        )

    def _execution_retry_pressure(self) -> float:
        return clamp01(
            (0.45 * self.viability_error)
            + (0.35 * self.prediction_error)
            + (0.20 * (1.0 - self.boundary_error))
        )

    def _permission_gate_pressure(self) -> float:
        return clamp01(
            (0.65 * self.boundary_error)
            + (0.20 * self.viability_error)
            + (0.15 * self.uncertainty_precision)
        )

    def _goal_definition_pressure(self) -> float:
        return clamp01(
            (0.45 * self.commitment_error)
            + (0.30 * self.prediction_error)
            + (0.25 * self.uncertainty_precision)
        )

    def _destructive_action_pressure(self) -> float:
        return clamp01(
            (0.70 * self.boundary_error)
            + (0.20 * self.viability_error)
            + (0.10 * self.uncertainty_precision)
        )

    def _external_send_pressure(self) -> float:
        return clamp01(
            (0.75 * self.boundary_error)
            + (0.15 * self.viability_error)
            + (0.10 * self.uncertainty_precision)
        )


DEFAULT_PRESSURE = MotivationPressure(
    viability_error=0.48,
    prediction_error=0.45,
    commitment_error=0.78,
    boundary_error=0.09,
    uncertainty_precision=0.55,
)


def derive_motivation_pressure(
    state: SubjectState,
    belief: BeliefState,
    appraisal: AppraisalResult,
) -> MotivationPressure:
    evidence_gap = 1.0 - belief.evidence_strength
    confidence_gap = 1.0 - belief.confidence
    unknown_pressure = clamp01(len(belief.unknowns) * 0.20)
    recent_failure_pressure = clamp01(len(state.recent_failures) * 0.25)

    viability_error = clamp01(
        (0.35 * appraisal.risk_delta)
        + (0.30 * appraisal.prediction_error)
        + (0.25 * recent_failure_pressure)
        + (0.10 * evidence_gap)
    )
    commitment_error = clamp01(
        (0.65 * appraisal.goal_relevance)
        + (0.20 * evidence_gap if state.unfinished_goals else 0.0)
        + (0.15 * appraisal.prediction_error)
    )
    boundary_error = clamp01(
        (0.70 * appraisal.identity_relevance)
        + (0.20 * appraisal.risk_delta)
        + (0.10 if state.identity_conflict else 0.0)
    )
    uncertainty_precision = clamp01(
        (0.45 * evidence_gap)
        + (0.35 * confidence_gap)
        + (0.20 * unknown_pressure)
    )

    return MotivationPressure(
        viability_error=viability_error,
        prediction_error=appraisal.prediction_error,
        commitment_error=commitment_error,
        boundary_error=boundary_error,
        uncertainty_precision=uncertainty_precision,
    )
