from pathlib import Path

from ego_desktop_lab.learning import run_learning_cycle
from ego_desktop_lab.outcome import OutcomeRecord
from ego_desktop_lab.verification_pack import build_priority_table, load_scenario


def test_replay_with_learning_is_deterministic(tmp_path: Path) -> None:
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
        evidence_refs=("test:deterministic",),
    )

    first = run_learning_cycle(
        scenario.state,
        scenario.belief_state,
        outcome,
        evidence_log_path=tmp_path / "first.jsonl",
        timestamp=scenario.timestamp,
    )
    second = run_learning_cycle(
        scenario.state,
        scenario.belief_state,
        outcome,
        evidence_log_path=tmp_path / "second.jsonl",
        timestamp=scenario.timestamp,
    )

    assert first.learning_update == second.learning_update
    assert first.strategy_memory_after == second.strategy_memory_after
    assert build_priority_table(first.next_result) == build_priority_table(second.next_result)
    assert first.next_result.selected_intention is not None
    assert second.next_result.selected_intention is not None
    assert first.next_result.selected_intention.goal == second.next_result.selected_intention.goal
    assert first.next_result.selected_intention.priority == second.next_result.selected_intention.priority
    assert first.next_result.gate_decision == second.next_result.gate_decision
