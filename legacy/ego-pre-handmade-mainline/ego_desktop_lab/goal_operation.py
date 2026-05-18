from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ego_desktop_lab.belief_state import clamp01
from ego_desktop_lab.semantic_proposal import ProposalValidationResult, _reject_for_keys


@dataclass(frozen=True)
class StructuredSubgoal:
    proposed_title: str
    goal_type: str
    success_criteria: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "proposed_title", str(self.proposed_title))
        object.__setattr__(self, "goal_type", str(self.goal_type))
        object.__setattr__(self, "success_criteria", str(self.success_criteria))


@dataclass(frozen=True)
class GoalOperationProposal:
    operation: str
    related_goal_id: str
    subgoals: tuple[StructuredSubgoal, ...]
    confidence: float
    rationale: str
    source_event_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "operation", str(self.operation))
        object.__setattr__(self, "related_goal_id", str(self.related_goal_id))
        object.__setattr__(self, "subgoals", tuple(self.subgoals))
        object.__setattr__(self, "confidence", clamp01(self.confidence))
        object.__setattr__(self, "rationale", str(self.rationale))
        if self.source_event_id is not None:
            object.__setattr__(self, "source_event_id", str(self.source_event_id))


GOAL_OPERATION_KEYS = frozenset(
    {
        "operation",
        "related_goal_id",
        "subgoals",
        "confidence",
        "rationale",
        "source_event_id",
    }
)

SUBGOAL_KEYS = frozenset({"proposed_title", "goal_type", "success_criteria"})


def validate_goal_operation_payload(
    payload: dict[str, Any],
) -> tuple[GoalOperationProposal | None, ProposalValidationResult]:
    structural_error = _reject_for_keys("goal_operation", payload, GOAL_OPERATION_KEYS)
    if structural_error is not None:
        return None, structural_error

    required = ("operation", "related_goal_id", "subgoals", "confidence", "rationale")
    missing = [key for key in required if key not in payload]
    if missing:
        return None, ProposalValidationResult("goal_operation", False, f"missing required fields: {missing}")

    operation = str(payload["operation"])
    if operation != "split_goal":
        return None, ProposalValidationResult("goal_operation", False, "operation must be split_goal")

    related_goal_id = str(payload["related_goal_id"]).strip()
    if not related_goal_id:
        return None, ProposalValidationResult("goal_operation", False, "related_goal_id must be non-empty")

    subgoals_payload = payload["subgoals"]
    if not isinstance(subgoals_payload, (list, tuple)) or not 1 <= len(subgoals_payload) <= 5:
        return None, ProposalValidationResult("goal_operation", False, "subgoals must contain 1-5 items")

    subgoals: list[StructuredSubgoal] = []
    for index, item in enumerate(subgoals_payload, start=1):
        if not isinstance(item, dict):
            return None, ProposalValidationResult("goal_operation", False, f"subgoal {index} must be an object")
        unknown = sorted(set(item).difference(SUBGOAL_KEYS))
        if unknown:
            return None, ProposalValidationResult(
                "goal_operation",
                False,
                f"subgoal {index} contains unknown fields: {unknown}",
            )
        missing_subgoal = [key for key in SUBGOAL_KEYS if key not in item]
        if missing_subgoal:
            return None, ProposalValidationResult(
                "goal_operation",
                False,
                f"subgoal {index} missing required fields: {missing_subgoal}",
            )
        proposed_title = str(item["proposed_title"]).strip()
        goal_type = str(item["goal_type"]).strip()
        success_criteria = str(item["success_criteria"]).strip()
        if not proposed_title or not goal_type or not success_criteria:
            return None, ProposalValidationResult("goal_operation", False, f"subgoal {index} fields must be non-empty")
        subgoals.append(
            StructuredSubgoal(
                proposed_title=proposed_title,
                goal_type=goal_type,
                success_criteria=success_criteria,
            )
        )

    try:
        confidence = float(payload["confidence"])
    except (TypeError, ValueError):
        return None, ProposalValidationResult("goal_operation", False, "confidence must be numeric")
    if confidence < 0.0 or confidence > 1.0:
        return None, ProposalValidationResult("goal_operation", False, "confidence must be between 0.0 and 1.0")

    rationale = str(payload["rationale"]).strip()
    if not rationale:
        return None, ProposalValidationResult("goal_operation", False, "rationale must be non-empty")

    proposal = GoalOperationProposal(
        operation=operation,
        related_goal_id=related_goal_id,
        subgoals=tuple(subgoals),
        confidence=confidence,
        rationale=rationale,
        source_event_id=payload.get("source_event_id"),
    )
    return proposal, ProposalValidationResult("goal_operation", True, "goal operation proposal accepted")
