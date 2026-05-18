from __future__ import annotations

from dataclasses import dataclass

from ego_desktop_lab.drives import DEFAULT_DRIVE, Drive
from ego_desktop_lab.motivation import DEFAULT_MOTIVATION, MotivationState
from ego_desktop_lab.policy import (
    INTENTION_SPECS,
    TENSION_PRIMARY_GOAL,
    calculate_pressure_priority,
    calculate_priority,
)
from ego_desktop_lab.pressure import DEFAULT_PRESSURE, MotivationPressure
from ego_desktop_lab.tension import Tension


@dataclass(frozen=True)
class Intention:
    id: str
    goal: str
    reason: str
    source_tension: Tension
    priority: float
    risk: float
    cost: float
    proposed_action: str
    affordance: str
    goal_id: str | None = None
    goal_description: str | None = None


def generate_intentions(
    tensions: tuple[Tension, ...],
    drive: Drive | MotivationState | MotivationPressure = DEFAULT_PRESSURE,
) -> tuple[Intention, ...]:
    intentions: list[Intention] = []
    has_uncertainty_tension = any(tension.type == "high_uncertainty" for tension in tensions)

    for index, tension in enumerate(tensions, start=1):
        goals = [TENSION_PRIMARY_GOAL[tension.type]]
        if isinstance(drive, MotivationPressure) and tension.type == "unfinished_goal":
            if (
                not has_uncertainty_tension
                and drive.pressure_on_affordance("verify") >= drive.pressure_on_affordance("continue_goal")
            ):
                goals.append("verify_before_claim")
            if drive.pressure_on_affordance("repair") >= 0.55:
                goals.append("repair_or_replan_goal")

        for goal in goals:
            intentions.append(_build_intention(len(intentions) + 1, tension, goal, drive))

    return tuple(intentions)


def select_intention(intentions: tuple[Intention, ...]) -> Intention | None:
    if not intentions:
        return None
    ordered = sorted(
        enumerate(intentions),
        key=lambda item: (-item[1].priority, item[0], item[1].id),
    )
    return ordered[0][1]


def _build_intention(
    index: int,
    tension: Tension,
    goal: str,
    drive: Drive | MotivationState | MotivationPressure,
) -> Intention:
    spec = INTENTION_SPECS[goal]
    drive_name = str(spec["drive"])
    affordance = str(spec["affordance"])
    expected_value = float(spec["expected_value"])
    risk = float(spec["risk"])
    cost = float(spec["cost"])
    if isinstance(drive, MotivationPressure):
        priority = calculate_pressure_priority(
            affordance_pressure=drive.pressure_on_affordance(affordance),
            tension_severity=tension.severity,
            expected_value=expected_value,
            risk=risk,
            cost=cost,
        )
    else:
        priority = calculate_priority(
            drive_weight=drive.weight_for(drive_name),
            tension_severity=tension.severity,
            expected_value=expected_value,
            risk=risk,
            cost=cost,
        )
    return Intention(
        id=f"intention:{index:03d}:{goal}",
        goal=goal,
        reason=str(spec["reason"]),
        source_tension=tension,
        priority=priority,
        risk=risk,
        cost=cost,
        proposed_action=str(spec["proposed_action"]),
        affordance=affordance,
        goal_id=tension.goal_id,
        goal_description=tension.goal_description,
    )
