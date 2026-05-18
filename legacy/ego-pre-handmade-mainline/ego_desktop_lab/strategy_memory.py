from __future__ import annotations

from dataclasses import dataclass

from ego_desktop_lab.belief_state import clamp01
from ego_desktop_lab.outcome import OutcomeRecord, strategy_id_for_goal


SUCCESS_THRESHOLD = 0.65


@dataclass(frozen=True)
class StrategyMemory:
    strategy_id: str
    success_count: int
    failure_count: int
    average_success_score: float
    last_used_at: str
    confidence: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "average_success_score", clamp01(self.average_success_score))
        object.__setattr__(self, "confidence", clamp01(self.confidence))


StrategyMemoryBank = dict[str, StrategyMemory]


def default_strategy_memory(strategy_id: str) -> StrategyMemory:
    return StrategyMemory(
        strategy_id=strategy_id,
        success_count=0,
        failure_count=0,
        average_success_score=0.0,
        last_used_at="never",
        confidence=0.50,
    )


def update_strategy_memory(
    bank: StrategyMemoryBank,
    outcome: OutcomeRecord,
    timestamp: str,
    config: object | None = None,
    feedback_conflict: bool = False,
) -> StrategyMemoryBank:
    strategy_id = strategy_id_for_goal(outcome.selected_plan_id)
    previous = bank.get(strategy_id, default_strategy_memory(strategy_id))
    previous_count = previous.success_count + previous.failure_count
    success_increment = 1 if outcome.success_score >= SUCCESS_THRESHOLD else 0
    failure_increment = 0 if success_increment else 1
    learning_rate = _config_value(config, "learning_rate", 0.35)
    if feedback_conflict:
        learning_rate *= _config_value(config, "conflict_learning_rate_multiplier", 0.35)
    if previous_count == 0:
        average_success_score = outcome.success_score
    else:
        average_success_score = (
            (previous.average_success_score * (1.0 - learning_rate))
            + (outcome.success_score * learning_rate)
        )
    success_count = previous.success_count + success_increment
    failure_count = previous.failure_count + failure_increment
    total_count = success_count + failure_count
    count_balance = (success_count - failure_count) / (total_count + 2)
    evidence_weight = min(0.08, total_count * 0.01)
    evidence_sign = 1.0 if average_success_score >= 0.50 else -1.0
    confidence = (
        _config_value(config, "baseline_confidence", 0.50)
        + ((average_success_score - 0.50) * 0.55)
        + (count_balance * 0.12)
        + (evidence_weight * evidence_sign)
    )
    confidence = _clamp_confidence(confidence, config)
    updated = StrategyMemory(
        strategy_id=strategy_id,
        success_count=success_count,
        failure_count=failure_count,
        average_success_score=average_success_score,
        last_used_at=timestamp,
        confidence=confidence,
    )
    return {**bank, strategy_id: updated}


def _config_value(config: object | None, name: str, default: float) -> float:
    return float(getattr(config, name, default))


def _clamp_confidence(value: float, config: object | None) -> float:
    lower = _config_value(config, "confidence_min", 0.15)
    upper = _config_value(config, "confidence_max", 0.85)
    return round(max(lower, min(upper, value)), 6)
