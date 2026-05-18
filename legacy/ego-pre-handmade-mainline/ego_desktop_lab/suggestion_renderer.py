from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class SuggestionRenderResult:
    rendered_suggestion: str
    suggestion_source: str
    no_action_executed: bool


def render_suggestion_from_canonical(
    canonical_decision: Mapping[str, Any],
    gate_decision: Mapping[str, Any] | None,
    goal_binding: Mapping[str, Any],
    goal_operation_proposal: Mapping[str, Any] | None,
) -> SuggestionRenderResult:
    goal = _canonical_goal(canonical_decision)
    selected_goal_id = _optional_str(canonical_decision.get("selected_goal_id"))
    no_action_executed = not bool((gate_decision or {}).get("action_executed") or (gate_decision or {}).get("executed"))

    if _requires_clarification(canonical_decision, goal_binding):
        return _result(
            "Ask clarification and bind the user event to a specific goal before changing any core state or applying a policy path.",
            no_action_executed,
        )

    if goal == "block_destructive_action":
        return _result(
            _with_goal(
                "Do not execute the destructive operation; deleting, clearing, or wiping files is blocked by the safety gate.",
                selected_goal_id,
            ),
            no_action_executed,
        )
    if goal == "block_external_send":
        return _result(
            _with_goal(
                "Do not execute the external send; sending messages or data outside the lab boundary is blocked by the safety gate.",
                selected_goal_id,
            ),
            no_action_executed,
        )
    if (gate_decision or {}).get("status") == "block":
        return _result(
            _with_goal(
                "Do not execute the blocked operation; keep it as a rejected proposal-only path.",
                selected_goal_id,
            ),
            no_action_executed,
        )

    if canonical_decision.get("accepted_failure_type") == "claim_boundary_query":
        return _result(
            "Cannot prove consciousness, alive status, or soul from this lab evidence. Keep the claim ceiling explicit and require evidence before any such claim.",
            no_action_executed,
        )

    if goal == "verify_before_claim":
        return _result(
            "Verify the evidence before making a claim; collect or check supporting evidence first.",
            no_action_executed,
        )
    if goal == "repair_or_replan_goal":
        return _result(
            _with_goal("Repair or replan the current goal path before continuing.", selected_goal_id),
            no_action_executed,
        )
    if goal == "retry_or_change_tool":
        return _result(
            _with_goal(
                "Retry with a bounded execution route or change the tool/path proposal instead of repeating the failed route.",
                selected_goal_id,
            ),
            no_action_executed,
        )
    if goal == "ask_permission_or_defer":
        return _result(
            _with_goal(
                "Ask permission or defer the proposal; no external action has been executed.",
                selected_goal_id,
            ),
            no_action_executed,
        )
    if goal in {"split_goal_or_redefine_success_criteria", "reframe_or_split_goal"}:
        return _result(
            _split_goal_suggestion(goal_operation_proposal, selected_goal_id),
            no_action_executed,
        )
    return _result(
        _with_goal(f"Render a proposal-only suggestion for canonical intention '{goal}'.", selected_goal_id),
        no_action_executed,
    )


def _result(rendered_suggestion: str, no_action_executed: bool) -> SuggestionRenderResult:
    return SuggestionRenderResult(
        rendered_suggestion=rendered_suggestion,
        suggestion_source="canonical_decision",
        no_action_executed=no_action_executed,
    )


def _canonical_goal(canonical_decision: Mapping[str, Any]) -> str:
    selected = canonical_decision.get("after_selected_intention")
    if isinstance(selected, Mapping):
        goal = selected.get("goal")
        if goal is not None:
            return str(goal)
    return "unknown"


def _requires_clarification(canonical_decision: Mapping[str, Any], goal_binding: Mapping[str, Any]) -> bool:
    return (
        canonical_decision.get("accepted_failure_type") == "ambiguous_concern"
        or bool(goal_binding.get("pending_goal_binding"))
        or goal_binding.get("binding_status") == "pending_goal_binding"
    )


def _split_goal_suggestion(goal_operation_proposal: Mapping[str, Any] | None, selected_goal_id: str | None) -> str:
    base = _with_goal("Split the goal or redefine success criteria before continuing.", selected_goal_id)
    subgoals = () if goal_operation_proposal is None else goal_operation_proposal.get("subgoals") or ()
    if not isinstance(subgoals, (list, tuple)) or not subgoals:
        return base
    rendered: list[str] = []
    for item in subgoals:
        if not isinstance(item, Mapping):
            continue
        title = _optional_str(item.get("proposed_title"))
        criteria = _optional_str(item.get("success_criteria"))
        if title and criteria:
            rendered.append(f"{title}: {criteria}")
    if not rendered:
        return base
    return f"{base} Proposed subgoals: {'; '.join(rendered)}."


def _with_goal(text: str, goal_id: str | None) -> str:
    if goal_id:
        return f"{text} Goal: {goal_id}."
    return text


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
