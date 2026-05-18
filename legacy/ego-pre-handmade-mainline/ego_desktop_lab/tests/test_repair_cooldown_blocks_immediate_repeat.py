from ego_desktop_lab.goal_progress import GoalProgressState
from ego_desktop_lab.intention import Intention
from ego_desktop_lab.oscillation import select_with_oscillation_control
from ego_desktop_lab.tension import Tension


def test_repair_cooldown_blocks_immediate_repeat() -> None:
    repair = _intention("repair_or_replan_goal", 0.90)
    verify = _intention("verify_before_claim", 0.70)
    progress = GoalProgressState(
        goal_id="goal:cooldown",
        last_selected_intention="repair_or_replan_goal",
        consecutive_repairs=1,
    )

    selected = select_with_oscillation_control((repair, verify), progress, risk=0.10)

    assert selected.cooldown_decision.blocked_by_cooldown is True
    assert selected.cooldown_decision.suppressed_goal == "repair_or_replan_goal"
    assert selected.selected_intention == verify


def _intention(goal: str, priority: float) -> Intention:
    tension = Tension("unfinished_goal", 0.80, "test", "goal:cooldown", "cooldown goal")
    affordance = "repair" if goal == "repair_or_replan_goal" else "verify"
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
        goal_id="goal:cooldown",
        goal_description="cooldown goal",
    )
