from pathlib import Path

from ego_desktop_lab.learning import run_learning_cycle
from ego_desktop_lab.outcome import OutcomeRecord
from ego_desktop_lab.verification_pack import load_scenario


def _priority(result: object, goal: str) -> float:
    for intention in result.generated_intentions:  # type: ignore[attr-defined]
        if intention.goal == goal:
            return intention.priority
    return -999.0


def test_continue_failure_increases_repair_priority(tmp_path: Path) -> None:
    scenario = load_scenario(Path("ego_desktop_lab/scenarios/high_evidence_same_goal.json"))
    outcome = OutcomeRecord(
        scenario_id=scenario.name,
        selected_intention_id="intention:001:continue_or_verify_unfinished_goal",
        selected_plan_id="continue_or_verify_unfinished_goal",
        expected_effect="continue goal without repair",
        actual_effect="continue_failure",
        success_score=0.10,
        user_feedback="continuation failed and needs repair",
        prediction_error=0.90,
        evidence_refs=("test:continue_failure",),
    )

    result = run_learning_cycle(
        scenario.state,
        scenario.belief_state,
        outcome,
        evidence_log_path=tmp_path / "learning.jsonl",
        timestamp=scenario.timestamp,
    )

    assert result.before_result.selected_intention is not None
    assert result.before_result.selected_intention.goal == "continue_or_verify_unfinished_goal"
    assert result.next_result.appraisal.prediction_error > result.before_result.appraisal.prediction_error
    assert result.next_result.affordance_pressure["repair"] > result.before_result.affordance_pressure["repair"]
    assert _priority(result.next_result, "repair_or_replan_goal") > _priority(
        result.before_result,
        "repair_or_replan_goal",
    )
    assert result.next_result.selected_intention is not None
    assert result.next_result.selected_intention.goal == "repair_or_replan_goal"
