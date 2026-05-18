from pathlib import Path

from ego_desktop_lab.semantic_intelligence import run_semantic_scenario


def test_evidence_failure_prefers_verify(tmp_path: Path) -> None:
    result = run_semantic_scenario(
        Path("ego_desktop_lab/semantic_scenarios/evidence_failure.txt"),
        provider_mode="mock",
        evidence_log_path=tmp_path / "evidence.jsonl",
    )
    calibration = result.semantic_policy_calibration

    assert calibration.overlay.accepted_failure_type == "evidence_failure"
    assert calibration.after_pressure_map["verify"] > calibration.before_pressure_map["verify"]
    assert calibration.after_pressure_map["verify"] == 1.0
    assert calibration.after_selected_intention is not None
    assert calibration.after_selected_intention.goal == "verify_before_claim"
