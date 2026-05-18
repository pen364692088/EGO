from __future__ import annotations

from dataclasses import dataclass

from ego_desktop_lab.policy import UNCERTAINTY_THRESHOLD
from ego_desktop_lab.subject_state import SubjectState


@dataclass(frozen=True)
class Tension:
    type: str
    severity: float
    source: str
    goal_id: str | None = None
    goal_description: str | None = None


def detect_tensions(state: SubjectState) -> tuple[Tension, ...]:
    tensions: list[Tension] = []

    if state.unfinished_goals:
        for goal in state.unfinished_goals:
            severity = min(
                1.0,
                0.60
                + (0.10 * len(state.unfinished_goals))
                + (0.20 * state.goal_pressure)
                + (0.10 * (goal.salience - 0.50)),
            )
            tensions.append(
                Tension(
                    type="unfinished_goal",
                    severity=round(severity, 6),
                    source=f"unfinished_goals:{goal.goal_id}:{goal.description}",
                    goal_id=goal.goal_id,
                    goal_description=goal.description,
                )
            )

    if state.uncertainty > UNCERTAINTY_THRESHOLD:
        tensions.append(
            Tension(
                type="high_uncertainty",
                severity=round(state.uncertainty, 6),
                source=f"uncertainty:{state.uncertainty}",
            )
        )

    if state.identity_conflict:
        severity = max(0.90, min(1.0, state.risk_sensitivity))
        tensions.append(
            Tension(
                type="identity_conflict",
                severity=round(severity, 6),
                source="identity_conflict:true",
            )
        )

    return tuple(tensions)
