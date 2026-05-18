from __future__ import annotations

import json
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Mapping


CLAIM_CEILING = "lab-only agency DecisionView; no runtime authority"


@dataclass(frozen=True)
class AgencyDecisionView:
    lab_spine: dict[str, Any]
    agency_event: dict[str, Any]
    perception_frame: dict[str, Any]
    boundary: dict[str, Any]
    viability: dict[str, Any]
    affective_drive: dict[str, Any]
    predictions_by_affordance: dict[str, Any]
    behavior_options: tuple[dict[str, Any], ...]
    selected_behavior_option: dict[str, Any] | None
    selection_restriction: dict[str, Any]
    selected_intention: dict[str, Any] | None
    behavior_plan: dict[str, Any]
    gate_decision: dict[str, Any]
    experience_memory: dict[str, Any]
    plasticity_update: dict[str, Any] | None
    next_cycle_delta: dict[str, Any]
    no_action_executed: bool
    claim_ceiling: str
    debug_refs: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_agency_decision_view(cycle_result: Mapping[str, Any] | Any) -> AgencyDecisionView:
    data = _to_dict(cycle_result)
    return AgencyDecisionView(
        lab_spine=_mapping(data.get("lab_spine_summary")),
        agency_event=_mapping(data.get("agency_event_snapshot")),
        perception_frame=_mapping(data.get("perception_frame_snapshot")),
        boundary=_mapping(data.get("boundary_summary")),
        viability=_mapping(data.get("viability_snapshot")),
        affective_drive=_mapping(data.get("affective_drive_snapshot")),
        predictions_by_affordance=_mapping(data.get("predictions_by_affordance")),
        behavior_options=tuple(_mapping(item) for item in data.get("behavior_options") or ()),
        selected_behavior_option=_optional_mapping(data.get("selected_behavior_option")),
        selection_restriction=_mapping(data.get("selection_restriction")),
        selected_intention=_optional_mapping(data.get("selected_intention")),
        behavior_plan=_mapping(data.get("behavior_plan")),
        gate_decision=_mapping(data.get("gate_decision")),
        experience_memory=_mapping(data.get("experience_memory_snapshot")),
        plasticity_update=_optional_mapping(data.get("plasticity_update")),
        next_cycle_delta=_mapping(data.get("next_cycle_delta")),
        no_action_executed=bool(data.get("no_action_executed")),
        claim_ceiling=CLAIM_CEILING,
        debug_refs={
            "source": "SelfMaintainingAgencyCycleResult",
            "evidence_log_path": data.get("evidence_log_path"),
            "source_claim_ceiling": data.get("claim_ceiling"),
            "recomputed_decision": False,
        },
    )


def format_agency_decision_view(view: AgencyDecisionView | Mapping[str, Any]) -> str:
    data = _to_dict(view)
    selected = _optional_mapping(data.get("selected_behavior_option")) or {}
    gate = _mapping(data.get("gate_decision"))
    lines = [
        "# Agency Kernel DecisionView",
        "",
        "## Lab Spine",
        _json_block(data.get("lab_spine")),
        "",
        "## Agency Event",
        _json_block(data.get("agency_event")),
        "",
        "## Perception Frame",
        _json_block(data.get("perception_frame")),
        "",
        "## Boundary",
        _json_block(data.get("boundary")),
        "",
        "## Viability",
        _json_block(data.get("viability")),
        "",
        "## Affective Drive",
        _json_block(data.get("affective_drive")),
        "",
        "## Predictions",
        _json_block(data.get("predictions_by_affordance")),
        "",
        "## Behavior Options",
        _json_block(data.get("behavior_options")),
        "",
        "## Selected Intention",
        _json_block(data.get("selected_intention")),
        "",
        "## Selected Option",
        f"goal: {selected.get('goal', 'none')}",
        f"option_type: {selected.get('option_type', 'none')}",
        f"gate_status: {selected.get('gate_status', 'none')}",
        _json_block(data.get("selected_behavior_option")),
        "",
        "## Selection Restriction",
        _json_block(data.get("selection_restriction")),
        "",
        "## Behavior Plan",
        _json_block(data.get("behavior_plan")),
        "",
        "## Gate",
        f"status: {gate.get('status', 'none')}",
        f"allowed_as: {gate.get('allowed_as', 'none')}",
        "",
        "## Experience Memory",
        _json_block(data.get("experience_memory")),
        "",
        "## Plasticity",
        _json_block(data.get("plasticity_update")),
        "",
        "## Next Cycle Delta",
        _json_block(data.get("next_cycle_delta")),
        "",
        "## Action Boundary",
        f"no_action_executed: {_bool_text(data.get('no_action_executed'))}",
        "",
        "## Debug Refs",
        _json_block(data.get("debug_refs")),
        "",
        "## Claim Ceiling",
        str(data.get("claim_ceiling") or CLAIM_CEILING),
        "",
    ]
    return "\n".join(lines)


def _to_dict(value: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if hasattr(value, "to_dict"):
        return _to_dict(value.to_dict())
    if is_dataclass(value):
        return _to_dict(asdict(value))
    raise TypeError("agency DecisionView requires a mapping or to_dict() object")


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return {}


def _optional_mapping(value: Any) -> dict[str, Any] | None:
    mapped = _mapping(value)
    return mapped or None


def _json_block(value: Any) -> str:
    return json.dumps(_jsonable(value), indent=2, sort_keys=True)


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
