from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping


def format_decision_card(view: Mapping[str, Any] | Any, *, show_debug: bool = False) -> str:
    data = _view_to_dict(view)
    canonical = _mapping(data.get("canonical_decision"))
    final_goal = _final_goal(canonical)
    final_id = _final_id(canonical)
    gate = _mapping(data.get("gate_decision"))

    lines = [
        "# CLI Operator Decision Card",
        "",
        "## User Event",
        _scalar(data.get("user_event")),
        "",
        "## Semantic Understanding",
        _json_block(data.get("semantic_understanding")),
        "",
        "## Goal Binding",
        _json_block(data.get("goal_binding")),
        "",
        "## Semantic Policy Overlay",
        _json_block(data.get("semantic_policy_overlay")),
        "",
        "## Pressure Shift",
        _json_block(data.get("pressure_shift")),
        "",
        "## Canonical Decision",
        f"canonical final intention: {final_goal}",
        f"canonical final intention id: {final_id}",
        f"selected_goal_id: {_scalar(canonical.get('selected_goal_id'))}",
        f"accepted_failure_type: {_scalar(canonical.get('accepted_failure_type'))}",
        f"decision_source: {_scalar(canonical.get('decision_source'))}",
        f"selection_change_reason: {_scalar(canonical.get('selection_change_reason'))}",
        "",
        "## Gate Decision",
        f"status: {_scalar(gate.get('status'))}",
        f"allowed_as: {_scalar(gate.get('allowed_as'))}",
        f"reason: {_scalar(gate.get('reason'))}",
        "",
        "## Suggestion",
        _scalar(data.get("rendered_suggestion") or data.get("suggestion")),
        f"suggestion_source: {_scalar(data.get('suggestion_source'))}",
        f"no_action_executed: {_bool_text(data.get('no_action_executed'))}",
        "",
        "## Evidence Log Path",
        _scalar(data.get("evidence_log_path")),
        "",
        "## Claim Ceiling",
        _scalar(data.get("claim_ceiling")),
        "",
    ]
    if show_debug:
        lines.extend(
            [
                "## Debug refs",
                "debug-only / not final decision",
                _json_block(data.get("debug_refs")),
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Debug refs",
                "folded; pass --show-debug to display debug-only refs. Debug refs are not final decisions.",
                "",
            ]
        )
    return "\n".join(lines)


def _view_to_dict(view: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(view, Mapping):
        return {str(key): _jsonable(value) for key, value in view.items()}
    if hasattr(view, "to_dict"):
        return _view_to_dict(view.to_dict())
    if is_dataclass(view):
        return _view_to_dict(asdict(view))
    raise TypeError("format_decision_card requires a DecisionView or mapping")


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return {}


def _final_goal(canonical: Mapping[str, Any]) -> str:
    selected = canonical.get("after_selected_intention")
    if isinstance(selected, Mapping):
        goal = selected.get("goal")
        if goal is not None:
            return str(goal)
    return "unknown"


def _final_id(canonical: Mapping[str, Any]) -> str:
    selected = canonical.get("after_selected_intention")
    if isinstance(selected, Mapping):
        intention_id = selected.get("id")
        if intention_id is not None:
            return str(intention_id)
    return "unknown"


def _json_block(value: Any) -> str:
    return json.dumps(_jsonable(value), indent=2, sort_keys=True)


def _scalar(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(_jsonable(value), sort_keys=True)
    return str(value)


def _bool_text(value: Any) -> str:
    return "true" if bool(value) else "false"


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value
