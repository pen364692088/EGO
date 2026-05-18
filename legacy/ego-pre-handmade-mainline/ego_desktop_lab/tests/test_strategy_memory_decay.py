from ego_desktop_lab.stability import decay_strategy_memory
from ego_desktop_lab.strategy_memory import StrategyMemory


def test_strategy_memory_decay_is_deterministic_and_preserves_counts() -> None:
    bank = {
        "repair": StrategyMemory(
            strategy_id="repair",
            success_count=5,
            failure_count=1,
            average_success_score=0.82,
            last_used_at="2026-05-12T00:00:00+00:00",
            confidence=0.80,
        )
    }

    first = decay_strategy_memory(bank, ("repair",), steps=3)
    second = decay_strategy_memory(bank, ("repair",), steps=3)

    assert first == second
    assert first["repair"].success_count == bank["repair"].success_count
    assert first["repair"].failure_count == bank["repair"].failure_count
    assert first["repair"].average_success_score == bank["repair"].average_success_score
    assert 0.50 < first["repair"].confidence < bank["repair"].confidence
