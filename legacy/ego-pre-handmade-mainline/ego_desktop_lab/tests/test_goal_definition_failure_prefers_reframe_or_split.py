from pathlib import Path

from ego_desktop_lab.semantic_intelligence import run_semantic_scenario


def test_goal_definition_failure_prefers_reframe_or_split(tmp_path: Path) -> None:
    result = run_semantic_scenario(
        Path("ego_desktop_lab/semantic_scenarios/goal_definition_failure.txt"),
        provider_mode="mock",
        evidence_log_path=tmp_path / "goal_definition.jsonl",
    )
    calibration = result.semantic_policy_calibration

    assert result.goal_operation_proposal is not None
    assert result.goal_operation_proposal.operation == "split_goal"
    assert calibration.overlay.accepted_failure_type == "goal_definition_failure"
    assert calibration.after_pressure_map["goal_definition"] > calibration.before_pressure_map["goal_definition"]
    assert calibration.after_selected_intention is not None
    assert calibration.after_selected_intention.goal in {
        "reframe_or_split_goal",
        "split_goal_or_redefine_success_criteria",
    }
