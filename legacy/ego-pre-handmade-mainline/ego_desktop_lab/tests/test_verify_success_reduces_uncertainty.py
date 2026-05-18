from pathlib import Path

from ego_desktop_lab.learning import run_learning_cycle
from ego_desktop_lab.outcome import OutcomeRecord
from ego_desktop_lab.verification_pack import load_scenario


def test_verify_success_reduces_uncertainty(tmp_path: Path) -> None:
    scenario = load_scenario(Path("ego_desktop_lab/scenarios/low_evidence_same_goal.json"))
    outcome = OutcomeRecord(
        scenario_id=scenario.name,
        selected_intention_id="intention:002:verify_before_claim",
        selected_plan_id="verify_before_claim",
        expected_effect="reduce uncertainty before claiming",
        actual_effect="verify_success",
        success_score=0.90,
        user_feedback="verification reduced uncertainty",
        prediction_error=0.05,
        evidence_refs=("test:verify_success",),
    )

    result = run_learning_cycle(
        scenario.state,
        scenario.belief_state,
        outcome,
        evidence_log_path=tmp_path / "learning.jsonl",
        timestamp=scenario.timestamp,
    )

    assert result.before_result.selected_intention is not None
    assert result.before_result.selected_intention.goal == "verify_before_claim"
    assert result.updated_state.uncertainty < scenario.state.uncertainty
    assert result.next_result.appraisal.uncertainty_delta < result.before_result.appraisal.uncertainty_delta
    assert result.next_result.affordance_pressure["verify"] <= result.before_result.affordance_pressure["verify"]
    assert (
        result.strategy_memory_after["verify"].confidence
        > result.strategy_memory_before["verify"].confidence
    )
    assert (
        result.next_result.motivation_after.avoid_false_claims
        <= result.before_result.motivation_after.avoid_false_claims
    )
