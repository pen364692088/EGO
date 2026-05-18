from __future__ import annotations

from dataclasses import dataclass

from ego_desktop_lab.belief_state import clamp01


GOAL_STRATEGY_MAP: dict[str, str] = {
    "verify_before_claim": "verify",
    "continue_or_verify_unfinished_goal": "continue_goal",
    "repair_or_replan_goal": "repair",
    "preserve_identity_boundary": "preserve_identity",
    "reframe_or_split_goal": "repair",
    "split_goal_or_redefine_success_criteria": "repair",
    "ask_permission_or_defer": "preserve_identity",
    "retry_or_change_tool": "repair",
}


@dataclass(frozen=True)
class OutcomeRecord:
    scenario_id: str
    selected_intention_id: str
    selected_plan_id: str
    expected_effect: str
    actual_effect: str
    success_score: float
    user_feedback: str
    prediction_error: float
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "success_score", clamp01(self.success_score))
        object.__setattr__(self, "prediction_error", clamp01(self.prediction_error))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


def strategy_id_for_goal(goal: str) -> str:
    return GOAL_STRATEGY_MAP[goal]
