from pathlib import Path

from ego_desktop_lab.semantic_intelligence import run_semantic_scenario


def test_plan_failure_prefers_repair(tmp_path: Path) -> None:
    result = run_semantic_scenario(
        Path("ego_desktop_lab/semantic_scenarios/plan_failure.txt"),
        provider_mode="mock",
        evidence_log_path=tmp_path / "plan.jsonl",
    )
    calibration = result.semantic_policy_calibration

    assert calibration.overlay.accepted_failure_type == "plan_failure"
    assert calibration.after_pressure_map["repair"] > calibration.before_pressure_map["repair"]
    assert calibration.after_selected_intention is not None
    assert calibration.after_selected_intention.goal == "repair_or_replan_goal"
