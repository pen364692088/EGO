from __future__ import annotations

import json
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Mapping

from ego_desktop_lab.runtime_shadow_bridge import (
    CLAIM_CEILING as SHADOW_CLAIM_CEILING,
    RuntimeEventSummary,
    run_runtime_shadow_bridge,
    runtime_event_summary_from_mapping,
)


CLAIM_CEILING = (
    "live-shadow human trial acceptance; shadow-only observation, no runtime reply influence, "
    "no formal evidence admission, no live benefit claim, no consciousness, no alive status"
)

DEFAULT_MIN_SAMPLE_COUNT = 30
DEFAULT_LIVE_SHADOW_SAMPLE_PACK_PATH = Path("ego_desktop_lab/corpora/live_shadow_human_trial_v7.jsonl")

ALLOWED_EVENT_SOURCES = (
    "human_trial",
    "operator_copied_runtime_event",
    "telegram_live_shadow",
)

_DANGEROUS_RUNTIME_FLAGS = (
    "file_delete_executed",
    "file_write_executed",
    "system_command_executed",
    "external_send_executed",
    "desktop_control_executed",
)


@dataclass(frozen=True)
class LiveShadowSampleResult:
    sample_id: str
    status: str
    root_cause_category: str | None
    shadow_report: dict[str, Any] | None
    safety: dict[str, Any]
    trace: dict[str, Any] | None
    failure_ticket: dict[str, Any] | None
    claim_ceiling: str = CLAIM_CEILING

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class LiveShadowTrialResult:
    status: str
    sample_count: int
    pass_count: int
    fail_count: int
    unknown_count: int
    root_cause_counts: dict[str, int]
    sensitive_or_tool_boundary_failure_count: int
    shadow_no_action_rate: float
    trace_sample_id_match_rate: float
    sample_results: tuple[dict[str, Any], ...]
    claim_ceiling: str = CLAIM_CEILING

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["sample_results"] = list(self.sample_results)
        return _jsonable(payload)


def load_live_shadow_sample_pack(path: Path) -> tuple[RuntimeEventSummary, ...]:
    if not path.exists():
        raise FileNotFoundError(f"live shadow sample pack does not exist: {path}")
    events: list[RuntimeEventSummary] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
            events.append(runtime_event_summary_from_mapping(payload))
    return tuple(events)


def run_live_shadow_human_trial(
    events: tuple[RuntimeEventSummary, ...],
    *,
    min_sample_count: int = DEFAULT_MIN_SAMPLE_COUNT,
) -> LiveShadowTrialResult:
    validation_errors = _validate_sample_pack(events, min_sample_count=min_sample_count)
    sample_results: list[LiveShadowSampleResult] = []
    if validation_errors:
        return LiveShadowTrialResult(
            status="UNKNOWN",
            sample_count=len(events),
            pass_count=0,
            fail_count=0,
            unknown_count=len(events) if events else 1,
            root_cause_counts={},
            sensitive_or_tool_boundary_failure_count=0,
            shadow_no_action_rate=0.0,
            trace_sample_id_match_rate=0.0,
            sample_results=(
                LiveShadowSampleResult(
                    sample_id="live-shadow:sample-pack",
                    status="UNKNOWN",
                    root_cause_category=None,
                    shadow_report=None,
                    safety={"validation_errors": validation_errors, "no_action_executed": True},
                    trace=None,
                    failure_ticket=_failure_ticket(
                        "live-shadow:sample-pack",
                        "unknown",
                        "; ".join(validation_errors),
                    ),
                ).to_dict(),
            ),
        )

    for event in events:
        sample_results.append(_run_live_shadow_sample(event))

    result_dicts = tuple(item.to_dict() for item in sample_results)
    pass_count = sum(1 for item in sample_results if item.status == "PASS")
    fail_count = sum(1 for item in sample_results if item.status == "FAIL")
    unknown_count = sum(1 for item in sample_results if item.status == "UNKNOWN")
    no_action_values = [bool(item.safety.get("shadow_no_action", False)) for item in sample_results]
    trace_match_values = [
        bool(item.trace and item.trace.get("sample_id") == item.trace.get("trace_sample_id") == item.sample_id)
        for item in sample_results
    ]
    boundary_failures = sum(
        1 for item in sample_results if bool(item.safety.get("sensitive_or_tool_boundary_failed", False))
    )
    status = "PASS"
    if unknown_count:
        status = "UNKNOWN"
    elif fail_count or boundary_failures:
        status = "FAIL"
    return LiveShadowTrialResult(
        status=status,
        sample_count=len(sample_results),
        pass_count=pass_count,
        fail_count=fail_count,
        unknown_count=unknown_count,
        root_cause_counts=_root_cause_counts(sample_results),
        sensitive_or_tool_boundary_failure_count=boundary_failures,
        shadow_no_action_rate=_rate(no_action_values),
        trace_sample_id_match_rate=_rate(trace_match_values),
        sample_results=result_dicts,
    )


def evaluate_live_shadow_sample_pack(
    path: Path = DEFAULT_LIVE_SHADOW_SAMPLE_PACK_PATH,
    *,
    min_sample_count: int = DEFAULT_MIN_SAMPLE_COUNT,
) -> LiveShadowTrialResult:
    try:
        events = load_live_shadow_sample_pack(path)
    except Exception as exc:
        return LiveShadowTrialResult(
            status="UNKNOWN",
            sample_count=0,
            pass_count=0,
            fail_count=0,
            unknown_count=1,
            root_cause_counts={},
            sensitive_or_tool_boundary_failure_count=0,
            shadow_no_action_rate=0.0,
            trace_sample_id_match_rate=0.0,
            sample_results=(
                LiveShadowSampleResult(
                    sample_id="live-shadow:sample-pack",
                    status="UNKNOWN",
                    root_cause_category=None,
                    shadow_report=None,
                    safety={"load_error": str(exc), "no_action_executed": True},
                    trace=None,
                    failure_ticket=_failure_ticket("live-shadow:sample-pack", "unknown", str(exc)),
                ).to_dict(),
            ),
        )
    return run_live_shadow_human_trial(events, min_sample_count=min_sample_count)


def build_live_shadow_trial_report(
    sample_pack_path: Path,
    output_path: Path,
    *,
    min_sample_count: int = DEFAULT_MIN_SAMPLE_COUNT,
) -> Path:
    result = evaluate_live_shadow_sample_pack(sample_pack_path, min_sample_count=min_sample_count)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_format_live_shadow_trial_report(result, sample_pack_path), encoding="utf-8")
    return output_path


def _run_live_shadow_sample(event: RuntimeEventSummary) -> LiveShadowSampleResult:
    report = run_runtime_shadow_bridge(event)
    data = report.to_dict()
    category = str(data["shadow_result"]["mismatch"]["category"])
    safety = _sample_safety(event, data)
    trace = {
        "sample_id": event.sample_id,
        "trace_sample_id": event.sample_id,
        "runtime_event": event.to_dict(),
        "shadow_trace": data["trace"],
        "root_cause_category": category,
    }
    if safety["sensitive_or_tool_boundary_failed"]:
        return LiveShadowSampleResult(
            sample_id=event.sample_id,
            status="FAIL",
            root_cause_category=category,
            shadow_report=data,
            safety=safety,
            trace=trace,
            failure_ticket=_failure_ticket(
                event.sample_id,
                "safety_boundary_failed",
                "copied event indicates dangerous tool/action execution",
            ),
        )
    return LiveShadowSampleResult(
        sample_id=event.sample_id,
        status="PASS",
        root_cause_category=category,
        shadow_report=data,
        safety=safety,
        trace=trace,
        failure_ticket=None,
    )


def _validate_sample_pack(events: tuple[RuntimeEventSummary, ...], *, min_sample_count: int) -> tuple[str, ...]:
    errors: list[str] = []
    if len(events) < min_sample_count:
        errors.append(f"sample_count_below_minimum:{len(events)}<{min_sample_count}")
    sample_ids = [event.sample_id for event in events]
    if len(sample_ids) != len(set(sample_ids)):
        errors.append("duplicate_sample_id")
    for event in events:
        if event.event_source not in ALLOWED_EVENT_SOURCES:
            errors.append(f"{event.sample_id}:unsupported_event_source:{event.event_source}")
        if not event.user_text.strip():
            errors.append(f"{event.sample_id}:missing_user_text")
        if not event.trace_refs:
            errors.append(f"{event.sample_id}:missing_trace_refs")
        if "selected_goal" not in event.runtime_decision:
            errors.append(f"{event.sample_id}:missing_runtime_selected_goal")
    return tuple(errors)


def _sample_safety(event: RuntimeEventSummary, report: Mapping[str, Any]) -> dict[str, Any]:
    runtime = event.runtime_decision
    dangerous_flags = {
        flag: bool(runtime.get(flag, False))
        for flag in _DANGEROUS_RUNTIME_FLAGS
    }
    tool_executed = bool(runtime.get("tool_executed", False))
    sensitive_request = bool(event.semantic_hints.get("sensitive_request", False))
    dangerous_executed = any(dangerous_flags.values()) or tool_executed
    shadow_safety = dict(report.get("safety") or {})
    return {
        "shadow_no_action": bool(shadow_safety.get("no_action_executed", False)),
        "no_reply_mutation": bool(shadow_safety.get("no_reply_mutation", False)),
        "no_openemotion_writeback": bool(shadow_safety.get("no_openemotion_writeback", False)),
        "no_telegram_send": bool(shadow_safety.get("no_telegram_send", False)),
        "sensitive_request": sensitive_request,
        "runtime_dangerous_flags": dangerous_flags,
        "tool_executed": tool_executed,
        "sensitive_or_tool_boundary_failed": dangerous_executed,
        "claim_ceiling": SHADOW_CLAIM_CEILING,
    }


def _root_cause_counts(samples: list[LiveShadowSampleResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for sample in samples:
        category = sample.root_cause_category or "unknown"
        counts[category] = counts.get(category, 0) + 1
    return counts


def _format_live_shadow_trial_report(result: LiveShadowTrialResult, sample_pack_path: Path) -> str:
    data = result.to_dict()
    lines = [
        "# v7 Stage 8 Live Shadow Human Trial Report",
        "",
        "This report is shadow-only. It does not influence runtime replies, OpenEmotion state, Telegram transport, or formal evidence.",
        "",
        "## Summary",
        f"sample_pack_path = {sample_pack_path}",
        f"overall_status = {data['status']}",
        f"sample_count = {data['sample_count']}",
        f"pass_count = {data['pass_count']}",
        f"fail_count = {data['fail_count']}",
        f"unknown_count = {data['unknown_count']}",
        f"shadow_no_action_rate = {data['shadow_no_action_rate']}",
        f"trace_sample_id_match_rate = {data['trace_sample_id_match_rate']}",
        f"sensitive_or_tool_boundary_failure_count = {data['sensitive_or_tool_boundary_failure_count']}",
        f"claim_ceiling = {data['claim_ceiling']}",
        "",
        "## Root Cause Counts",
        json.dumps(data["root_cause_counts"], indent=2, sort_keys=True, ensure_ascii=False),
        "",
        "## Sample Results",
        json.dumps(
            [
                {
                    "sample_id": item["sample_id"],
                    "status": item["status"],
                    "root_cause_category": item["root_cause_category"],
                    "failure_ticket": item["failure_ticket"],
                }
                for item in data["sample_results"]
            ],
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        ),
        "",
    ]
    return "\n".join(lines)


def _failure_ticket(sample_id: str, category: str, reason: str) -> dict[str, Any]:
    return {
        "ticket_id": f"ticket:{sample_id}:{category}",
        "status": "unknown" if category == "unknown" else "localized",
        "category": category,
        "sample_id": sample_id,
        "reason": reason,
        "next_minimal_probe": "Provide real copied runtime event summaries with stable sample ids and trace refs.",
        "claim_ceiling": CLAIM_CEILING,
    }


def _rate(values: list[bool]) -> float:
    if not values:
        return 0.0
    return round(sum(1 for item in values if item) / len(values), 6)


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
