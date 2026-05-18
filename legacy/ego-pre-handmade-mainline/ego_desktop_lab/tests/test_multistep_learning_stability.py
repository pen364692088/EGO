from pathlib import Path

from ego_desktop_lab.stability import run_learning_sequence
from ego_desktop_lab.verification_pack import load_scenario


def test_multistep_learning_stability(tmp_path: Path) -> None:
    scenario = load_scenario(Path("ego_desktop_lab/scenarios/high_evidence_same_goal.json"))
    sequence = (
        {
            "scenario_id": "multi_step_continue_failure",
            "actual_effect": "continue_failure",
            "success_score": 0.10,
            "user_feedback": "continuation failed and needs repair",
            "prediction_error": 0.90,
        },
        {
            "scenario_id": "multi_step_repair_success",
            "actual_effect": "repair_success",
            "success_score": 0.90,
            "user_feedback": "repair worked and reduced prediction error",
            "prediction_error": 0.10,
        },
        {
            "scenario_id": "multi_step_continue_failure_again",
            "actual_effect": "continue_failure",
            "success_score": 0.20,
            "user_feedback": "continuation regressed again",
            "prediction_error": 0.80,
        },
    )

    first = run_learning_sequence(
        scenario.state,
        scenario.belief_state,
        sequence,
        evidence_log_path=tmp_path / "first.jsonl",
        timestamp=scenario.timestamp,
    )
    second = run_learning_sequence(
        scenario.state,
        scenario.belief_state,
        sequence,
        evidence_log_path=tmp_path / "second.jsonl",
        timestamp=scenario.timestamp,
    )

    assert first.final_state == second.final_state
    assert first.final_belief_state == second.final_belief_state
    assert first.final_strategy_memory == second.final_strategy_memory
    assert first.final_result.affordance_pressure == second.final_result.affordance_pressure
    assert first.final_result.selected_intention == second.final_result.selected_intention
    assert first.pressure_stability_table == second.pressure_stability_table
    assert len(first.trace) == 3
    for pressure in first.final_result.affordance_pressure.values():
        assert 0.0 < pressure < 1.0
