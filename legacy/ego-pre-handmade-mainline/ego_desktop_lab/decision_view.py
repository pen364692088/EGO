from __future__ import annotations

import json
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Mapping

from ego_desktop_lab.suggestion_renderer import render_suggestion_from_canonical


CLAIM_CEILING = "lab-only decision-view contract proof"


@dataclass(frozen=True)
class DecisionView:
    user_event: str | None
    semantic_understanding: dict[str, Any]
    goal_binding: dict[str, Any]
    goal_operation_proposal: dict[str, Any] | None
    semantic_policy_overlay: dict[str, Any] | None
    pressure_shift: dict[str, Any]
    canonical_decision: dict[str, Any]
    gate_decision: dict[str, Any] | None
    suggestion: str | None
    rendered_suggestion: str
    suggestion_source: str
    no_action_executed: bool
    evidence_log_path: str
    claim_ceiling: str
    debug_refs: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_decision_view_from_evidence_record(
    record: Mapping[str, Any] | Any,
    evidence_log_path: Path | str,
) -> DecisionView:
    data = _record_to_dict(record)
    canonical_decision = _required_dict(data, "canonical_decision")
    semantic_proposal = _optional_dict(
        data.get("executive_semantic_proposal")
        or data.get("semantic_proposal")
        or data.get("semantic_policy_overlay")
    )
    goal_binding = {
        "binding_status": semantic_proposal.get("binding_status") if semantic_proposal else None,
        "related_goal_id": semantic_proposal.get("related_goal_id") if semantic_proposal else None,
        "selected_goal_id": canonical_decision.get("selected_goal_id"),
        "pending_goal_binding": bool(data.get("pending_goal_binding")),
    }
    goal_operation_proposal = _optional_dict(data.get("goal_operation_proposal"))
    gate_decision = _optional_dict(data.get("canonical_gate_decision") or data.get("gate_decision"))
    rendered = render_suggestion_from_canonical(
        canonical_decision,
        gate_decision,
        goal_binding,
        goal_operation_proposal,
    )
    before_pressure = _optional_float_map(data.get("before_pressure_map"))
    after_pressure = _optional_float_map(data.get("after_pressure_map"))
    return DecisionView(
        user_event=_optional_str(data.get("semantic_scenario_text")),
        semantic_understanding={
            "accepted_failure_type": data.get("accepted_failure_type")
            or canonical_decision.get("accepted_failure_type"),
            "semantic_proposal": semantic_proposal,
            "validation_results": _jsonable(data.get("executive_validation_results")),
            "rejected_proposals": _jsonable(data.get("executive_rejected_proposals")),
        },
        goal_binding=goal_binding,
        goal_operation_proposal=goal_operation_proposal,
        semantic_policy_overlay=_optional_dict(data.get("semantic_policy_overlay")),
        pressure_shift={
            "before": before_pressure,
            "after": after_pressure,
            "delta": _pressure_delta(before_pressure, after_pressure),
        },
        canonical_decision=canonical_decision,
        gate_decision=gate_decision,
        suggestion=rendered.rendered_suggestion,
        rendered_suggestion=rendered.rendered_suggestion,
        suggestion_source=rendered.suggestion_source,
        no_action_executed=rendered.no_action_executed,
        evidence_log_path=str(evidence_log_path),
        claim_ceiling=CLAIM_CEILING,
        debug_refs=_build_debug_refs(data),
    )


def build_decision_view_from_semantic_result(result: Any) -> DecisionView:
    return build_decision_view_from_evidence_record(result.evidence_record.to_dict(), result.evidence_log_path)


def build_decision_view_contract_report(output_path: Path) -> Path:
    from ego_desktop_lab.semantic_intelligence import (
        DEFAULT_SEMANTIC_TIMESTAMP,
        SEMANTIC_SCENARIO_DIR,
        run_semantic_scenario,
    )

    evidence_path = Path("temp/ego_desktop_lab/decision_view_v5a_pre/report.jsonl")
    scenario_paths = tuple(sorted(SEMANTIC_SCENARIO_DIR.glob("*.txt")))
    views = tuple(
        build_decision_view_from_semantic_result(
            run_semantic_scenario(
                path,
                provider_mode="mock",
                evidence_log_path=evidence_path,
                timestamp=DEFAULT_SEMANTIC_TIMESTAMP,
            )
        )
        for path in scenario_paths
    )
    no_llm_view = build_decision_view_from_semantic_result(
        run_semantic_scenario(
            SEMANTIC_SCENARIO_DIR / "evidence_failure.txt",
            provider_mode="none",
            evidence_log_path=evidence_path,
            timestamp="2026-05-13T00:00:01+00:00",
        )
    )

    lines = [
        "# Decision View Contract v5a-pre Report",
        "",
        f"Claim ceiling: {CLAIM_CEILING}.",
        "This report does not prove consciousness, alive status, live autonomy, runtime efficacy, user benefit, or real semantic intelligence.",
        "",
        "## Scenario Decision Views",
        "",
    ]
    for view in views:
        scenario_id = _scenario_id_from_view(view)
        lines.extend(
            [
                f"### {scenario_id}",
                "",
                "```json",
                json.dumps(view.to_dict(), indent=2, sort_keys=True),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## No-LLM Fallback",
            "",
            "```json",
            json.dumps(no_llm_view.to_dict(), indent=2, sort_keys=True),
            "```",
            "",
            f"Evidence log path: `{evidence_path}`",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def _record_to_dict(record: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(record, Mapping):
        return {str(key): _jsonable(value) for key, value in record.items()}
    if hasattr(record, "to_dict"):
        return _record_to_dict(record.to_dict())
    if is_dataclass(record):
        return _record_to_dict(asdict(record))
    raise TypeError("decision view requires an evidence record mapping or to_dict() record")


def _required_dict(data: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"DecisionView requires evidence.{key}")
    return {str(item_key): _jsonable(item_value) for item_key, item_value in value.items()}


def _optional_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        return None
    return {str(key): _jsonable(item) for key, item in value.items()}


def _optional_float_map(value: Any) -> dict[str, float]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): round(float(item), 6) for key, item in value.items()}


def _pressure_delta(before: dict[str, float], after: dict[str, float]) -> dict[str, float]:
    return {
        key: round(after.get(key, 0.0) - before.get(key, 0.0), 6)
        for key in sorted(set(before).union(after))
    }


def _build_debug_refs(data: Mapping[str, Any]) -> dict[str, Any]:
    legacy = data.get("next_core_cycle_influence") or data.get("legacy_next_core_cycle_influence_debug")
    debug_refs: dict[str, Any] = {}
    if isinstance(legacy, Mapping):
        if legacy.get("is_final_decision_source") is True:
            raise ValueError("legacy next-core-cycle influence cannot be a final decision source")
        normalized = {str(key): _jsonable(value) for key, value in legacy.items()}
        normalized["record_role"] = "legacy_debug"
        normalized["is_final_decision_source"] = False
        debug_refs["legacy_next_core_cycle_influence_debug"] = normalized
    debug_refs["raw_core_selected_intention"] = _jsonable(data.get("selected_intention"))
    debug_refs["raw_core_suggestion"] = _jsonable(data.get("suggestion"))
    debug_refs["raw_generated_intentions_count"] = len(data.get("generated_intentions") or ())
    return debug_refs


def _scenario_id_from_view(view: DecisionView) -> str:
    semantic_proposal = view.semantic_understanding.get("semantic_proposal")
    if isinstance(semantic_proposal, Mapping):
        source_event_id = semantic_proposal.get("source_event_id")
        if isinstance(source_event_id, str) and source_event_id.startswith("scenario:"):
            return source_event_id.split(":", 1)[1]
    return "unknown"


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


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
