from ego_desktop_lab.goal_progress import FailureType, GoalProgressState, update_goal_progress
from ego_desktop_lab.intention import Intention
from ego_desktop_lab.oscillation import select_with_oscillation_control
from ego_desktop_lab.outcome import OutcomeRecord
from ego_desktop_lab.tension import Tension


def test_repeated_repair_triggers_goal_split() -> None:
    repair = _intention("repair_or_replan_goal", 0.85)
    verify = _intention("verify_before_claim", 0.70)
    previous = GoalProgressState(
        goal_id="goal:split",
        progress_score=0.25,
        stagnation_count=1,
        repair_count=1,
        consecutive_repairs=1,
        last_selected_intention="repair_or_replan_goal",
    )
    outcome = OutcomeRecord(
        scenario_id="split",
        selected_intention_id=repair.id,
        selected_plan_id=repair.goal,
        expected_effect="repair should improve progress",
        actual_effect="repair_failure",
        success_score=0.20,
        user_feedback="repair failed without progress",
        prediction_error=0.80,
        evidence_refs=("test:split",),
    )

    updated = update_goal_progress(previous, repair, outcome, FailureType.plan_failure)
    selected = select_with_oscillation_control((repair, verify), updated)

    assert updated.repair_count == 2
    assert updated.progress_score == previous.progress_score
    assert updated.should_split is True
    assert selected.selected_intention is not None
    assert selected.selected_intention.goal == "split_goal_or_redefine_success_criteria"


def _intention(goal: str, priority: float) -> Intention:
    tension = Tension("unfinished_goal", 0.80, "test", "goal:split", "split goal")
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
        goal_id="goal:split",
        goal_description="split goal",
    )
