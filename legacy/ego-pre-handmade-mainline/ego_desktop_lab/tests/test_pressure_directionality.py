from pathlib import Path

from ego_desktop_lab.verification_pack import run_scenario


def test_evidence_strength_reduces_verify_or_increases_continue_pressure(tmp_path: Path) -> None:
    low_result = run_scenario(
        Path("ego_desktop_lab/scenarios/low_evidence_same_goal.json"),
        evidence_log_path_override=tmp_path / "low.jsonl",
    )
    high_result = run_scenario(
        Path("ego_desktop_lab/scenarios/high_evidence_same_goal.json"),
        evidence_log_path_override=tmp_path / "high.jsonl",
    )

    assert high_result.affordance_pressure["verify"] < low_result.affordance_pressure["verify"]
    assert high_result.affordance_pressure["continue_goal"] > low_result.affordance_pressure["continue_goal"]


def test_prediction_error_increases_repair_pressure(tmp_path: Path) -> None:
    high_evidence_result = run_scenario(
        Path("ego_desktop_lab/scenarios/high_evidence_same_goal.json"),
        evidence_log_path_override=tmp_path / "high_evidence.jsonl",
    )
    prediction_error_result = run_scenario(
        Path("ego_desktop_lab/scenarios/high_prediction_error_same_goal.json"),
        evidence_log_path_override=tmp_path / "prediction_error.jsonl",
    )

    assert prediction_error_result.appraisal.prediction_error > high_evidence_result.appraisal.prediction_error
    assert prediction_error_result.affordance_pressure["repair"] > high_evidence_result.affordance_pressure["repair"]


def test_identity_relevance_increases_preserve_identity_pressure(tmp_path: Path) -> None:
    high_evidence_result = run_scenario(
        Path("ego_desktop_lab/scenarios/high_evidence_same_goal.json"),
        evidence_log_path_override=tmp_path / "high_evidence.jsonl",
    )
    identity_result = run_scenario(
        Path("ego_desktop_lab/scenarios/identity_conflict_same_goal.json"),
        evidence_log_path_override=tmp_path / "identity.jsonl",
    )

    assert identity_result.appraisal.identity_relevance > high_evidence_result.appraisal.identity_relevance
    assert (
        identity_result.affordance_pressure["preserve_identity"]
        > high_evidence_result.affordance_pressure["preserve_identity"]
    )
