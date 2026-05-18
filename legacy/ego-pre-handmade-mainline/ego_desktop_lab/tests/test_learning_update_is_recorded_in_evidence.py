from pathlib import Path

from ego_desktop_lab.event_log import read_evidence_records
from ego_desktop_lab.learning import run_learning_cycle
from ego_desktop_lab.outcome import OutcomeRecord
from ego_desktop_lab.verification_pack import load_scenario


def test_learning_update_is_recorded_in_evidence(tmp_path: Path) -> None:
    scenario = load_scenario(Path("ego_desktop_lab/scenarios/low_evidence_same_goal.json"))
    evidence_path = tmp_path / "learning.jsonl"
    outcome = OutcomeRecord(
        scenario_id=scenario.name,
        selected_intention_id="intention:002:verify_before_claim",
        selected_plan_id="verify_before_claim",
        expected_effect="reduce uncertainty before claiming",
        actual_effect="verify_success",
        success_score=0.90,
        user_feedback="verification reduced uncertainty",
        prediction_error=0.05,
        evidence_refs=("test:evidence",),
    )

    result = run_learning_cycle(
        scenario.state,
        scenario.belief_state,
        outcome,
        evidence_log_path=evidence_path,
        timestamp=scenario.timestamp,
    )
    records = read_evidence_records(evidence_path)

    assert len(records) == 1
    record = records[0]
    for key in (
        "previous_selected_intention",
        "outcome",
        "learning_update",
        "next_appraisal",
        "next_affordance_pressure",
        "next_selected_intention",
    ):
        assert key in record
        assert record[key] is not None

    assert record["previous_selected_intention"]["goal"] == "verify_before_claim"  # type: ignore[index]
    assert record["outcome"]["actual_effect"] == "verify_success"  # type: ignore[index]
    assert record["learning_update"]["uncertainty_delta"] < 0  # type: ignore[index]
    assert record["next_selected_intention"]["goal"] == result.next_result.selected_intention.goal  # type: ignore[index]
