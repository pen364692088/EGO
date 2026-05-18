from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ego_desktop_lab.belief_state import clamp01
from ego_desktop_lab.intention import Intention
from ego_desktop_lab.outcome import OutcomeRecord


class FailureType(str, Enum):
    evidence_failure = "evidence_failure"
    plan_failure = "plan_failure"
    execution_failure = "execution_failure"
    goal_definition_failure = "goal_definition_failure"
    permission_failure = "permission_failure"
    environment_failure = "environment_failure"


@dataclass(frozen=True)
class GoalProgressState:
    goal_id: str
    progress_score: float = 0.0
    stagnation_count: int = 0
    repair_count: int = 0
    consecutive_failures: int = 0
    consecutive_repairs: int = 0
    last_selected_intention: str | None = None
    last_successful_strategy: str | None = None
    last_failed_strategy: str | None = None
    should_reframe: bool = False
    should_split: bool = False
    should_pause: bool = False
    selection_history: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "goal_id", str(self.goal_id))
        object.__setattr__(self, "progress_score", clamp01(self.progress_score))
        object.__setattr__(self, "stagnation_count", max(0, int(self.stagnation_count)))
        object.__setattr__(self, "repair_count", max(0, int(self.repair_count)))
        object.__setattr__(self, "consecutive_failures", max(0, int(self.consecutive_failures)))
        object.__setattr__(self, "consecutive_repairs", max(0, int(self.consecutive_repairs)))
        object.__setattr__(self, "selection_history", tuple(self.selection_history)[-4:])


def normalize_failure_type(failure_type: FailureType | str | None) -> FailureType | None:
    if failure_type is None:
        return None
    if isinstance(failure_type, FailureType):
        return failure_type
    return FailureType(str(failure_type))


def update_goal_progress(
    previous: GoalProgressState,
    selected_intention: Intention,
    outcome: OutcomeRecord | None = None,
    failure_type: FailureType | str | None = None,
) -> GoalProgressState:
    normalized_failure = normalize_failure_type(failure_type)
    goal = selected_intention.goal
    strategy = _strategy_for_intention(goal)
    progress_signal = _has_progress_signal(outcome)
    success = outcome is not None and outcome.success_score >= 0.65
    progress_increment = _progress_increment(outcome) if progress_signal else 0.0
    next_progress_score = clamp01(previous.progress_score + progress_increment)
    progress_improved = next_progress_score > previous.progress_score
    failed_or_stalled = not progress_improved and _counts_as_stagnating(goal, outcome)

    stagnation_count = previous.stagnation_count + 1 if failed_or_stalled else 0
    consecutive_failures = previous.consecutive_failures + 1 if failed_or_stalled else 0
    repair_selected = goal == "repair_or_replan_goal"
    repair_count = previous.repair_count + 1 if repair_selected else previous.repair_count
    consecutive_repairs = previous.consecutive_repairs + 1 if repair_selected else 0

    history = (*previous.selection_history, goal)[-4:]
    oscillation_pattern = history == (
        "continue_or_verify_unfinished_goal",
        "repair_or_replan_goal",
        "continue_or_verify_unfinished_goal",
        "repair_or_replan_goal",
    )
    repeated_repair_without_progress = repair_count >= 2 and repair_selected and not progress_improved

    last_successful_strategy = previous.last_successful_strategy
    last_failed_strategy = previous.last_failed_strategy
    if success and progress_improved:
        last_successful_strategy = strategy
        last_failed_strategy = previous.last_failed_strategy
    elif failed_or_stalled:
        last_failed_strategy = strategy

    should_pause = previous.should_pause or consecutive_failures >= 3 or normalized_failure in (
        FailureType.permission_failure,
        FailureType.environment_failure,
    )

    return GoalProgressState(
        goal_id=previous.goal_id or str(selected_intention.goal_id or "goal:unknown"),
        progress_score=next_progress_score,
        stagnation_count=stagnation_count,
        repair_count=repair_count,
        consecutive_failures=consecutive_failures,
        consecutive_repairs=consecutive_repairs,
        last_selected_intention=goal,
        last_successful_strategy=last_successful_strategy,
        last_failed_strategy=last_failed_strategy,
        should_reframe=previous.should_reframe
        or oscillation_pattern
        or normalized_failure == FailureType.goal_definition_failure,
        should_split=previous.should_split or repeated_repair_without_progress,
        should_pause=should_pause,
        selection_history=history,
    )


def _strategy_for_intention(goal: str) -> str:
    if goal == "continue_or_verify_unfinished_goal":
        return "continue_goal"
    if goal in {
        "repair_or_replan_goal",
        "reframe_or_split_goal",
        "split_goal_or_redefine_success_criteria",
        "retry_or_change_tool",
    }:
        return "repair"
    if goal == "verify_before_claim":
        return "verify"
    if goal in {"preserve_identity_boundary", "ask_permission_or_defer"}:
        return "preserve_identity"
    return goal


def _has_progress_signal(outcome: OutcomeRecord | None) -> bool:
    if outcome is None or outcome.success_score < 0.65:
        return False
    effect = outcome.actual_effect.lower()
    feedback = outcome.user_feedback.lower()
    tokens = (
        "success",
        "succeeded",
        "progress",
        "improved",
        "resolved",
        "completed",
        "protected",
        "reduced",
    )
    return any(token in effect or token in feedback for token in tokens)


def _progress_increment(outcome: OutcomeRecord | None) -> float:
    if outcome is None:
        return 0.0
    return round(0.10 + (0.25 * outcome.success_score), 6)


def _counts_as_stagnating(goal: str, outcome: OutcomeRecord | None) -> bool:
    if goal not in {"continue_or_verify_unfinished_goal", "repair_or_replan_goal"}:
        return outcome is not None and outcome.success_score < 0.40
    if outcome is None:
        return True
    return outcome.success_score < 0.65 or not _has_progress_signal(outcome)
