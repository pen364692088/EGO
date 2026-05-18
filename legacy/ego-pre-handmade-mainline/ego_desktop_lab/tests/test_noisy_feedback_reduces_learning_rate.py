from pathlib import Path

from ego_desktop_lab.event_log import read_evidence_records
from ego_desktop_lab.learning import derive_learning_update, run_learning_cycle
from ego_desktop_lab.outcome import OutcomeRecord
from ego_desktop_lab.verification_pack import load_scenario


def test_noisy_feedback_reduces_learning_rate(tmp_path: Path) -> None:
    scenario = load_scenario(Path("ego_desktop_lab/scenarios/low_evidence_same_goal.json"))
    normal = OutcomeRecord(
        scenario_id=scenario.name,
        selected_intention_id="intention:002:verify_before_claim",
        selected_plan_id="verify_before_claim",
        expected_effect="reduce uncertainty",
        actual_effect="verify_success",
        success_score=0.90,
        user_feedback="verification worked and reduced uncertainty",
        prediction_error=0.05,
        evidence_refs=("test:normal",),
    )
    noisy = OutcomeRecord(
        scenario_id=scenario.name,
        selected_intention_id="intention:002:verify_before_claim",
        selected_plan_id="verify_before_claim",
        expected_effect="reduce uncertainty",
        actual_effect="verify_success",
        success_score=0.90,
        user_feedback="not useful and failed",
        prediction_error=0.05,
        evidence_refs=("test:noisy",),
    )

    normal_update = derive_learning_update(normal)
    noisy_update = derive_learning_update(noisy)

    assert normal_update.feedback_conflict is False
    assert noisy_update.feedback_conflict is True
    assert noisy_update.effective_learning_rate < normal_update.effective_learning_rate
    assert abs(noisy_update.uncertainty_delta) < abs(normal_update.uncertainty_delta)
    assert abs(noisy_update.pressure_bias_delta["uncertainty_precision"]) < abs(
        normal_update.pressure_bias_delta["uncertainty_precision"]
    )

    evidence_path = tmp_path / "noisy.jsonl"
    run_learning_cycle(
        scenario.state,
        scenario.belief_state,
        noisy,
        evidence_log_path=evidence_path,
        timestamp=scenario.timestamp,
    )
    record = read_evidence_records(evidence_path)[0]
    assert record["feedback_conflict"] is True
    assert record["learning_update"]["feedback_conflict"] is True  # type: ignore[index]
