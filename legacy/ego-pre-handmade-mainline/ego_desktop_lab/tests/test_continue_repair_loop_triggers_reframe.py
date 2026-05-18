from ego_desktop_lab.goal_progress import FailureType, GoalProgressState, update_goal_progress
from ego_desktop_lab.intention import Intention
from ego_desktop_lab.oscillation import select_with_oscillation_control
from ego_desktop_lab.outcome import OutcomeRecord
from ego_desktop_lab.tension import Tension


def test_continue_repair_loop_triggers_reframe() -> None:
    repair = _intention("repair_or_replan_goal", 0.80)
    continue_goal = _intention("continue_or_verify_unfinished_goal", 0.70)
    previous = GoalProgressState(
        goal_id="goal:loop",
        progress_score=0.20,
        stagnation_count=3,
        repair_count=1,
        consecutive_failures=3,
        last_selected_intention="continue_or_verify_unfinished_goal",
        selection_history=(
            "continue_or_verify_unfinished_goal",
            "repair_or_replan_goal",
            "continue_or_verify_unfinished_goal",
        ),
    )
    outcome = OutcomeRecord(
        scenario_id="loop",
        selected_intention_id=repair.id,
        selected_plan_id=repair.goal,
        expected_effect="repair should break loop",
        actual_effect="repair_failure",
        success_score=0.10,
        user_feedback="repair failed and no progress happened",
        prediction_error=0.90,
        evidence_refs=("test:loop",),
    )

    updated = update_goal_progress(previous, repair, outcome, FailureType.plan_failure)
    selected = select_with_oscillation_control((repair, continue_goal), updated)

    assert updated.stagnation_count > previous.stagnation_count
    assert updated.should_reframe is True
    assert selected.oscillation_detected is True
    assert selected.selected_intention is not None
    assert selected.selected_intention.goal == "reframe_or_split_goal"


def _intention(goal: str, priority: float) -> Intention:
    tension = Tension("unfinished_goal", 0.80, "test", "goal:loop", "loop goal")
    return Intention(
        id=f"intention:test:{goal}",
        goal=goal,
        reason="test",
        source_tension=tension,
        priority=priority,
        risk=0.05,
        cost=0.10,
        proposed_action="suggestion_card",
        affordance="repair" if goal == "repair_or_replan_goal" else "continue_goal",
        goal_id="goal:loop",
        goal_description="loop goal",
    )
