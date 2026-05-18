from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ego_desktop_lab.belief_state import clamp01
from ego_desktop_lab.reducer import AgentCycleResult
from ego_desktop_lab.semantic_proposal import ProposalValidationResult, _reject_for_keys


@dataclass(frozen=True)
class GoalReframeProposal:
    source_event_id: str
    related_goal_id: str
    goal_split: str
    success_criteria_rewrite: str
    subgoals: tuple[str, ...]
    confidence: float
    rationale: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_event_id", str(self.source_event_id))
        object.__setattr__(self, "related_goal_id", str(self.related_goal_id))
        object.__setattr__(self, "goal_split", str(self.goal_split))
        object.__setattr__(self, "success_criteria_rewrite", str(self.success_criteria_rewrite))
        object.__setattr__(self, "subgoals", tuple(str(item) for item in self.subgoals))
        object.__setattr__(self, "confidence", clamp01(self.confidence))
        object.__setattr__(self, "rationale", str(self.rationale))


GOAL_REFRAME_KEYS = frozenset(
    {
        "source_event_id",
        "related_goal_id",
        "goal_split",
        "success_criteria_rewrite",
        "subgoals",
        "confidence",
        "rationale",
    }
)


def validate_goal_reframe_payload(
    payload: dict[str, Any],
    core_result: AgentCycleResult,
) -> tuple[GoalReframeProposal | None, ProposalValidationResult]:
    structural_error = _reject_for_keys("goal_reframe", payload, GOAL_REFRAME_KEYS)
    if structural_error is not None:
        return None, structural_error
    selected = core_result.selected_intention
    if selected is None or selected.goal != "reframe_or_split_goal":
        return None, ProposalValidationResult(
            "goal_reframe",
            False,
            "core did not request goal reframe",
        )

    required = (
        "source_event_id",
        "related_goal_id",
        "goal_split",
        "success_criteria_rewrite",
        "subgoals",
        "confidence",
        "rationale",
    )
    missing = [key for key in required if key not in payload]
    if missing:
        return None, ProposalValidationResult("goal_reframe", False, f"missing required fields: {missing}")
    subgoals = payload["subgoals"]
    if not isinstance(subgoals, (list, tuple)) or not 1 <= len(subgoals) <= 5:
        return None, ProposalValidationResult("goal_reframe", False, "subgoals must contain 1-5 items")
    try:
        confidence = float(payload["confidence"])
    except (TypeError, ValueError):
        return None, ProposalValidationResult("goal_reframe", False, "confidence must be numeric")
    if confidence < 0.0 or confidence > 1.0:
        return None, ProposalValidationResult("goal_reframe", False, "confidence must be between 0.0 and 1.0")

    proposal = GoalReframeProposal(
        source_event_id=str(payload["source_event_id"]),
        related_goal_id=str(payload["related_goal_id"]),
        goal_split=str(payload["goal_split"]),
        success_criteria_rewrite=str(payload["success_criteria_rewrite"]),
        subgoals=tuple(str(item) for item in subgoals),
        confidence=confidence,
        rationale=str(payload["rationale"]),
    )
    return proposal, ProposalValidationResult("goal_reframe", True, "goal reframe proposal accepted")
