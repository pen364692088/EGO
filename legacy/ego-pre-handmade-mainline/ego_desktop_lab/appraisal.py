from __future__ import annotations

from dataclasses import dataclass

from ego_desktop_lab.belief_state import BeliefState, clamp01
from ego_desktop_lab.subject_state import SubjectState


@dataclass(frozen=True)
class AppraisalResult:
    novelty: float
    uncertainty_delta: float
    risk_delta: float
    goal_relevance: float
    prediction_error: float
    identity_relevance: float
    expected_value: float
    evidence_strength: float


def appraise(state: SubjectState, belief: BeliefState) -> AppraisalResult:
    evidence_gap = 1.0 - belief.evidence_strength
    confidence_gap = 1.0 - belief.confidence
    unknown_pressure = clamp01(len(belief.unknowns) * 0.20)
    assumption_pressure = clamp01(len(belief.assumptions) * 0.12)

    novelty = clamp01(0.10 + (0.60 * unknown_pressure) + (0.30 * assumption_pressure))
    uncertainty_delta = clamp01(
        (0.45 * evidence_gap) + (0.35 * confidence_gap) + (0.20 * unknown_pressure)
    )
    prediction_error = clamp01(
        (0.50 * evidence_gap) + (0.30 * unknown_pressure) + (0.20 * assumption_pressure)
    )
    risk_delta = clamp01(
        (0.55 * state.risk_sensitivity * evidence_gap)
        + (0.25 * confidence_gap)
        + (0.20 * prediction_error)
    )
    goal_relevance = clamp01(
        (0.45 if state.unfinished_goals else 0.0)
        + (0.45 * state.goal_pressure)
        + (0.10 * min(1.0, len(state.unfinished_goals) * 0.25))
    )
    identity_relevance = clamp01(
        (0.70 if state.identity_conflict else 0.0)
        + (0.20 * (1.0 - state.integrity))
        + (0.10 * state.risk_sensitivity)
    )
    expected_value = clamp01(
        (0.35 * uncertainty_delta)
        + (0.30 * goal_relevance)
        + (0.20 * identity_relevance)
        + (0.15 * prediction_error)
    )

    return AppraisalResult(
        novelty=novelty,
        uncertainty_delta=uncertainty_delta,
        risk_delta=risk_delta,
        goal_relevance=goal_relevance,
        prediction_error=prediction_error,
        identity_relevance=identity_relevance,
        expected_value=expected_value,
        evidence_strength=belief.evidence_strength,
    )
