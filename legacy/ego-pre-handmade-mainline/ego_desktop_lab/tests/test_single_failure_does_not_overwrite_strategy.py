from ego_desktop_lab.outcome import OutcomeRecord
from ego_desktop_lab.strategy_memory import StrategyMemory, update_strategy_memory


def test_single_failure_does_not_overwrite_strategy() -> None:
    bank = {
        "verify": StrategyMemory(
            strategy_id="verify",
            success_count=8,
            failure_count=0,
            average_success_score=0.90,
            last_used_at="2026-05-12T00:00:00+00:00",
            confidence=0.83,
        )
    }
    outcome = OutcomeRecord(
        scenario_id="single_failure",
        selected_intention_id="intention:001:verify_before_claim",
        selected_plan_id="verify_before_claim",
        expected_effect="verify safely",
        actual_effect="verify_failure",
        success_score=0.10,
        user_feedback="verification failed",
        prediction_error=0.90,
        evidence_refs=("test:single_failure",),
    )

    updated = update_strategy_memory(bank, outcome, "2026-05-12T00:01:00+00:00")
    memory = updated["verify"]

    assert memory.failure_count == 1
    assert memory.success_count == 8
    assert 0.50 < memory.average_success_score < 0.90
    assert 0.50 < memory.confidence < 0.83
    assert memory.confidence >= 0.15
