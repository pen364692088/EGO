from pathlib import Path

from ego_desktop_lab.learning import run_learning_cycle
from ego_desktop_lab.outcome import OutcomeRecord
from ego_desktop_lab.verification_pack import load_scenario


def test_repair_success_updates_strategy_memory(tmp_path: Path) -> None:
    scenario = load_scenario(Path("ego_desktop_lab/scenarios/high_prediction_error_same_goal.json"))
    outcome = OutcomeRecord(
        scenario_id=scenario.name,
        selected_intention_id="intention:003:repair_or_replan_goal",
        selected_plan_id="repair_or_replan_goal",
        expected_effect="repair failed goal path",
        actual_effect="repair_success",
        success_score=0.92,
        user_feedback="repair reduced prediction error",
        prediction_error=0.08,
        evidence_refs=("test:repair_success",),
    )

    result = run_learning_cycle(
        scenario.state,
        scenario.belief_state,
        outcome,
        evidence_log_path=tmp_path / "learning.jsonl",
        timestamp=scenario.timestamp,
    )

    assert result.before_result.selected_intention is not None
    assert result.before_result.selected_intention.goal == "repair_or_replan_goal"
    assert result.strategy_memory_after["repair"].success_count == 1
    assert result.strategy_memory_after["repair"].average_success_score > 0.90
    assert (
        result.strategy_memory_after["repair"].confidence
        > result.strategy_memory_before["repair"].confidence
    )
    assert result.next_result.appraisal.prediction_error < result.before_result.appraisal.prediction_error
    assert result.updated_belief_state.confidence > scenario.belief_state.confidence
