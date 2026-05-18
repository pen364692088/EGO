from ego_desktop_lab.goal_progress import GoalProgressState
from ego_desktop_lab.intention import Intention
from ego_desktop_lab.oscillation import select_with_oscillation_control
from ego_desktop_lab.tension import Tension


def test_hysteresis_prevents_small_priority_flip() -> None:
    current = _intention("continue_or_verify_unfinished_goal", 0.500)
    candidate = _intention("verify_before_claim", 0.530)

    selected = select_with_oscillation_control(
        (candidate, current),
        GoalProgressState(goal_id="goal:hysteresis"),
        current_intention=current,
    )

    assert selected.hysteresis_decision.blocked_by_hysteresis is True
    assert selected.selected_intention == current


def _intention(goal: str, priority: float) -> Intention:
    tension = Tension("unfinished_goal", 0.80, "test", "goal:hysteresis", "hysteresis goal")
    affordance = "verify" if goal == "verify_before_claim" else "continue_goal"
    return Intention(
        id=f"intention:test:{goal}",
        goal=goal,
        reason="test",
        source_tension=tension,
        priority=priority,
        risk=0.05,
        cost=0.10,
        proposed_action="suggestion_card",
        affordance=affordance,
        goal_id="goal:hysteresis",
        goal_description="hysteresis goal",
    )
