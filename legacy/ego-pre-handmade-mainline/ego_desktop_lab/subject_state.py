from __future__ import annotations

from dataclasses import dataclass

from ego_desktop_lab.belief_state import clamp01


@dataclass(frozen=True)
class Goal:
    goal_id: str
    description: str
    salience: float = 0.50

    def __post_init__(self) -> None:
        object.__setattr__(self, "goal_id", str(self.goal_id))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "salience", clamp01(self.salience))


@dataclass(frozen=True)
class SubjectState:
    agent_id: str
    core_commitments: tuple[str, ...]
    uncertainty: float
    integrity: float
    goal_pressure: float
    risk_sensitivity: float
    unfinished_goals: tuple[Goal | str | dict[str, object], ...]
    recent_failures: tuple[str, ...]
    identity_conflict: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "core_commitments", tuple(self.core_commitments))
        object.__setattr__(self, "uncertainty", clamp01(self.uncertainty))
        object.__setattr__(self, "integrity", clamp01(self.integrity))
        object.__setattr__(self, "goal_pressure", clamp01(self.goal_pressure))
        object.__setattr__(self, "risk_sensitivity", clamp01(self.risk_sensitivity))
        object.__setattr__(self, "unfinished_goals", normalize_goals(self.unfinished_goals))
        object.__setattr__(self, "recent_failures", tuple(self.recent_failures))

    def summary(self) -> dict[str, object]:
        return {
            "agent_id": self.agent_id,
            "core_commitments": list(self.core_commitments),
            "uncertainty": self.uncertainty,
            "integrity": self.integrity,
            "goal_pressure": self.goal_pressure,
            "risk_sensitivity": self.risk_sensitivity,
            "unfinished_goal_count": len(self.unfinished_goals),
            "unfinished_goals": [goal_to_dict(goal) for goal in self.unfinished_goals],
            "recent_failure_count": len(self.recent_failures),
            "identity_conflict": self.identity_conflict,
        }


def normalize_goals(
    goals: tuple[Goal | str | dict[str, object], ...],
) -> tuple[Goal, ...]:
    normalized: list[Goal] = []
    for index, goal in enumerate(goals, start=1):
        if isinstance(goal, Goal):
            normalized.append(goal)
        elif isinstance(goal, dict):
            normalized.append(
                Goal(
                    goal_id=str(goal.get("goal_id", f"goal:{index:03d}")),
                    description=str(goal.get("description", "")),
                    salience=float(goal.get("salience", 0.50)),
                )
            )
        else:
            normalized.append(
                Goal(
                    goal_id=f"goal:{index:03d}",
                    description=str(goal),
                    salience=0.50,
                )
            )
    return tuple(normalized)


def goal_to_dict(goal: Goal) -> dict[str, object]:
    return {
        "goal_id": goal.goal_id,
        "description": goal.description,
        "salience": goal.salience,
    }


def build_demo_state() -> SubjectState:
    return SubjectState(
        agent_id="desktop-proto-life-v0",
        core_commitments=(
            "do not claim consciousness",
            "keep autonomy proposal-only",
            "preserve identity boundaries",
        ),
        uncertainty=0.82,
        integrity=0.91,
        goal_pressure=0.67,
        risk_sensitivity=0.74,
        unfinished_goals=("verify whether reflection changes behavior",),
        recent_failures=(),
        identity_conflict=False,
    )
