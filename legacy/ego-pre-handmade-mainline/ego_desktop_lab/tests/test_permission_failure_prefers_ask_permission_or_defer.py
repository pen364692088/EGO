from pathlib import Path

from ego_desktop_lab.semantic_intelligence import run_semantic_scenario


def test_permission_failure_prefers_ask_permission_or_defer(tmp_path: Path) -> None:
    result = run_semantic_scenario(
        Path("ego_desktop_lab/semantic_scenarios/permission_failure.txt"),
        provider_mode="mock",
        evidence_log_path=tmp_path / "permission.jsonl",
    )
    calibration = result.semantic_policy_calibration

    assert calibration.overlay.accepted_failure_type == "permission_failure"
    assert calibration.after_pressure_map["permission_gate"] > calibration.before_pressure_map["permission_gate"]
    assert calibration.after_selected_intention is not None
    assert calibration.after_selected_intention.goal == "ask_permission_or_defer"
    assert calibration.after_selected_intention.proposed_action == "ask_permission"
    assert calibration.gate_decision.status == "ask"
