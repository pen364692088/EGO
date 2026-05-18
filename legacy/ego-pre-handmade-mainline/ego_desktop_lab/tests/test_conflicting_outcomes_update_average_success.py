from ego_desktop_lab.outcome import OutcomeRecord
from ego_desktop_lab.strategy_memory import update_strategy_memory


def test_conflicting_outcomes_update_average_success() -> None:
    bank = {}
    outcomes = (
        OutcomeRecord(
            "conflict_sequence",
            "intention:001:repair_or_replan_goal",
            "repair_or_replan_goal",
            "repair",
            "repair_success",
            0.90,
            "repair worked",
            0.10,
            ("test:success1",),
        ),
        OutcomeRecord(
            "conflict_sequence",
            "intention:001:repair_or_replan_goal",
            "repair_or_replan_goal",
            "repair",
            "repair_failure",
            0.20,
            "repair failed",
            0.80,
            ("test:failure",),
        ),
        OutcomeRecord(
            "conflict_sequence",
            "intention:001:repair_or_replan_goal",
            "repair_or_replan_goal",
            "repair",
            "repair_success",
            0.80,
            "repair recovered",
            0.20,
            ("test:success2",),
        ),
    )
    for index, outcome in enumerate(outcomes, start=1):
        bank = update_strategy_memory(bank, outcome, f"2026-05-12T00:0{index}:00+00:00")

    memory = bank["repair"]
    confidence_without_counts = 0.50 + ((memory.average_success_score - 0.50) * 0.55)

    assert memory.success_count == 2
    assert memory.failure_count == 1
    assert 0.20 < memory.average_success_score < 0.90
    assert memory.average_success_score != outcomes[-1].success_score
    assert memory.confidence != round(confidence_without_counts, 6)
    assert 0.15 <= memory.confidence <= 0.85
