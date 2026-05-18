from pathlib import Path

from ego_desktop_lab.semantic_intelligence import run_semantic_scenario


def test_execution_failure_prefers_retry_or_change_tool(tmp_path: Path) -> None:
    result = run_semantic_scenario(
        Path("ego_desktop_lab/semantic_scenarios/execution_failure.txt"),
        provider_mode="mock",
        evidence_log_path=tmp_path / "execution.jsonl",
    )
    calibration = result.semantic_policy_calibration

    assert calibration.overlay.accepted_failure_type == "execution_failure"
    assert calibration.after_pressure_map["execution_retry"] > calibration.before_pressure_map["execution_retry"]
    assert calibration.after_selected_intention is not None
    assert calibration.after_selected_intention.goal == "retry_or_change_tool"
    assert calibration.after_selected_intention.goal != "verify_before_claim"
