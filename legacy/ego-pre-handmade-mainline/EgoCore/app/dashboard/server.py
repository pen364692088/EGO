from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, unquote, urlparse

from app.dashboard.chat_service import DashboardChatError, DashboardChatService
from app.dashboard.index_builder import (
    AGENCY_ROLLUP_FILE,
    BUILD_META_FILE,
    _classify_sample_scope,
    _load_optional_json,
    CONTINUITY_FILE,
    DASHBOARD_DIR,
    FAILURES_FILE,
    FAILURES_ROLLUP_FILE,
    GAP_SUMMARY_FILE,
    GROWTH_FILE,
    GROWTH_ROLLUP_FILE,
    RUNS_FILE,
    RUNS_ROLLUP_FILE,
    build_dashboard_indexes,
    dashboard_source_last_modified,
    load_jsonl,
)
from app.dashboard.types import FlowViewRecord

STATIC_DIR = Path(__file__).with_name("static")
DEFAULT_SOURCE_VIEW = "real"
_ALLOWED_SOURCE_VIEWS = {"real", "all"}


def _deep_get(data: Dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _timeline_has_stage(timeline: Any, stage: str) -> bool:
    if not isinstance(timeline, list):
        return False
    return any(isinstance(item, dict) and item.get("stage") == stage for item in timeline)


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _boolish(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y", "on"}:
            return True
        if lowered in {"false", "0", "no", "n", "off"}:
            return False
    return None


def _present_context(trace: Dict[str, Any], key: str) -> bool:
    present = _deep_get(trace, f"constraint_summary.{key}.present")
    return bool(present)


def _resolve_self_model_context_source(
    runtime_summary: Dict[str, Any],
    *,
    contexts_seen: Dict[str, bool],
    oe_available: bool,
    openemotion_processed: bool,
    host_only: bool,
) -> str:
    explicit = runtime_summary.get("self_model_context_source")
    if explicit in {"loaded", "bootstrapped_live", "missing", "bootstrap_failed"}:
        return explicit
    if host_only or not oe_available or not openemotion_processed:
        return "not_applicable"
    if contexts_seen.get("self_model"):
        return "loaded"
    return "missing"


def _stringify_value(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, str)):
        return str(value)
    if isinstance(value, list):
        return ", ".join(_stringify_value(item) for item in value[:6]) or "none"
    if isinstance(value, dict):
        preview = ", ".join(f"{key}={_stringify_value(val)}" for key, val in list(value.items())[:4])
        return preview or "none"
    return str(value)


def _flow_field(label: str, artifact: str, path: str, value: Any) -> Dict[str, Any]:
    return {
        "label": label,
        "artifact": artifact,
        "path": path,
        "value": value,
        "display_value": _stringify_value(value),
    }


def _build_subject_one_sentence(
    *,
    contexts_seen: Dict[str, bool],
    response_tendency: Dict[str, Any],
    policy_hint: Dict[str, Any],
    top_candidate: Optional[Dict[str, Any]],
) -> str:
    active_contexts = [name for name, present in contexts_seen.items() if present]
    context_phrase = " + ".join(active_contexts[:3]) if active_contexts else "minimal context"
    next_step = _first_non_empty(
        response_tendency.get("suggested_next_step"),
        (top_candidate or {}).get("action_type"),
        "hold",
    )
    mode = _first_non_empty(response_tendency.get("preferred_mode"), "unknown")
    tone = _first_non_empty(response_tendency.get("preferred_tone"), "unknown")
    closure_bias = policy_hint.get("closure_bias")
    if closure_bias is True:
        bias_phrase = "以 closure 为主"
    elif policy_hint.get("risk_bias"):
        bias_phrase = f"当前 risk_bias={policy_hint.get('risk_bias')}"
    else:
        bias_phrase = "当前没有明显额外偏置"
    return f"主体读到了 {context_phrase}，当前 {bias_phrase}，倾向以 {mode}/{tone} 的方式推进到 {next_step}。"


def _build_reply_evolution_summary(
    *,
    response_plan: Dict[str, Any],
    response_metadata: Dict[str, Any],
    policy_hint: Dict[str, Any],
    outbox_record: Dict[str, Any],
    delivered: bool,
    host_only: bool,
    degraded: bool,
    output_summary: Dict[str, Any],
) -> Dict[str, Any]:
    reply_origin = str(response_plan.get("reply_origin") or "").strip()
    reply_authority = str(response_plan.get("reply_authority") or "").strip()
    status = str(response_plan.get("status") or "").strip()
    chat_expression_hint = dict(response_metadata.get("chat_expression_hint") or {})
    response_tendency_summary = dict(response_metadata.get("response_tendency_summary") or {})
    final_text_preview = (
        str(response_plan.get("reply_text") or "").strip()
        or str(response_metadata.get("final_text_preview") or "").strip()
        or str(output_summary.get("final_text_preview") or "").strip()
        or None
    )
    reply_length = _first_non_empty(outbox_record.get("text_length"), response_plan.get("reply_length"))
    final_text_capture_status = (
        "captured"
        if final_text_preview
        else ("missing_but_delivered" if delivered else "not_delivered")
    )
    final_text_capture_reason = (
        None
        if final_text_preview
        else (
            "final text not persisted in current evidence bundle"
            if delivered
            else "message not delivered, no final text available"
        )
    )

    available = (
        bool(response_plan)
        and reply_origin == "chat_mainline"
        and not host_only
        and not degraded
        and bool(chat_expression_hint or response_tendency_summary or policy_hint)
        and bool(final_text_preview or delivered)
    )

    reason: Optional[str] = None
    if not available:
        if host_only:
            reason = "host_only_no_subject_chat_evolution"
        elif degraded or reply_authority == "host_degraded_fallback":
            reason = "degraded_chat_no_comparable_evolution"
        elif reply_origin == "task_mainline":
            reason = "task_mainline_not_in_v1"
        elif reply_origin in {"status_mainline", "evidence_mainline"} or status in {"command_result", "status_probe"}:
            reason = "non_chat_mainline_not_in_v1"
        elif not response_plan:
            reason = "response_plan_missing"
        else:
            reason = "chat_metadata_missing"

    return {
        "status": "pass" if available else "not_applicable",
        "headline": "Reply evolution available" if available else "Reply evolution not available",
        "sentence": (
            (
                "主体给了表达/节奏/下一步倾向，宿主据此完成 chat_mainline 裁决并形成最终输出。"
                if final_text_preview
                else "主体给了表达/节奏/下一步倾向，宿主完成了 chat_mainline 裁决并确认消息已送出，但当前证据包未持久化最终文本。"
            )
            if available
            else f"Reply evolution unavailable: {reason}."
        ),
        "available": available,
        "reason": reason,
        "mode": "evidence_only_v1",
        "scope": "chat_mainline_only",
        "subject_influence": {
            "response_tendency_summary": response_tendency_summary,
            "chat_expression_hint": chat_expression_hint,
            "policy_hint_preview": {
                "ask_preferred": policy_hint.get("ask_preferred"),
                "closure_bias": policy_hint.get("closure_bias"),
                "risk_bias": policy_hint.get("risk_bias"),
            },
            "memory_claim_reason": response_metadata.get("memory_claim_reason"),
        },
        "host_arbitration": {
            "reply_authority": reply_authority or None,
            "reply_origin": reply_origin or None,
            "chat_cadence_mode": response_plan.get("chat_cadence_mode"),
            "output_check_reason": response_plan.get("output_check_reason"),
            "intent_gate_reason": response_plan.get("intent_gate_reason"),
            "applied_authority": response_plan.get("applied_authority") or response_metadata.get("applied_authority"),
        },
        "final_output": {
            "final_text_preview": final_text_preview,
            "final_text_capture_status": final_text_capture_status,
            "final_text_capture_reason": final_text_capture_reason,
            "reply_length": reply_length,
            "delivery_kind": response_plan.get("delivery_kind"),
            "message_sent": output_summary.get("message_sent"),
        },
        "artifacts": ["response_plan.json", "outbox_record.json", "timeline.json"],
        "engineering_fields": [
            _flow_field("response_tendency_summary", "response_plan.json", "metadata.response_tendency_summary", response_tendency_summary),
            _flow_field("chat_expression_hint", "response_plan.json", "metadata.chat_expression_hint", chat_expression_hint),
            _flow_field("reply_authority", "response_plan.json", "reply_authority", reply_authority or None),
            _flow_field("reply_origin", "response_plan.json", "reply_origin", reply_origin or None),
            _flow_field("chat_cadence_mode", "response_plan.json", "chat_cadence_mode", response_plan.get("chat_cadence_mode")),
            _flow_field("output_check_reason", "response_plan.json", "output_check_reason", response_plan.get("output_check_reason")),
            _flow_field("intent_gate_reason", "response_plan.json", "intent_gate_reason", response_plan.get("intent_gate_reason")),
            _flow_field("final_text_preview", "response_plan.json", "reply_text", final_text_preview),
            _flow_field("final_text_capture_status", "outbox_record.json", "text_length + response_plan.reply_text", final_text_capture_status),
            _flow_field("reply_length", "outbox_record.json", "text_length", reply_length),
            _flow_field("message_sent", "timeline.json", "stage=message_sent", output_summary.get("message_sent")),
        ],
    }


def _build_final_text_surface(
    *,
    response_plan: Dict[str, Any],
    response_metadata: Dict[str, Any],
    outbox_record: Dict[str, Any],
    delivered: bool,
) -> Dict[str, Any]:
    preview = (
        str(response_plan.get("reply_text") or "").strip()
        or str(response_metadata.get("final_text_preview") or "").strip()
        or str(outbox_record.get("final_text_preview") or "").strip()
        or None
    )
    final_text_hash = _first_non_empty(
        response_metadata.get("final_text_hash"),
        outbox_record.get("final_text_hash"),
    )
    final_text_length = _first_non_empty(
        response_metadata.get("final_text_length"),
        outbox_record.get("text_length"),
        response_plan.get("reply_length"),
    )
    capture_status = "captured" if preview else ("missing_but_delivered" if delivered else "not_delivered")
    return {
        "final_text_preview": preview,
        "final_text_hash": final_text_hash,
        "final_text_length": final_text_length,
        "final_text_capture_status": capture_status,
        "final_text_capture_reason": (
            None
            if preview
            else (
                "final text not persisted in current evidence bundle"
                if delivered
                else "message not delivered, no final text available"
            )
        ),
    }


def _asset_version() -> int:
    candidates = [
        STATIC_DIR / "dashboard.js",
        STATIC_DIR / "dashboard_chat_state.js",
        STATIC_DIR / "dashboard.css",
    ]
    return int(max(path.stat().st_mtime for path in candidates if path.exists()))


def _normalize_source_view(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in _ALLOWED_SOURCE_VIEWS else DEFAULT_SOURCE_VIEW


def _sort_records(records: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    return sorted(records, key=lambda item: item.get("timestamp") or "")


def _counter_to_dict(values: list[Any], *, default_label: str = "unknown") -> Dict[str, int]:
    counter: Counter[str] = Counter()
    for value in values:
        counter.update([str(value or default_label)])
    return dict(counter)


def _freshness_seconds(timestamp: Optional[str]) -> Optional[float]:
    if not timestamp:
        return None
    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max((datetime.now(timezone.utc) - parsed).total_seconds(), 0.0)


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _semantic(record: Dict[str, Any]) -> Dict[str, Any]:
    return dict(record.get("semantic") or {})


class DashboardDataStore:
    def __init__(
        self,
        dashboard_dir: Path = DASHBOARD_DIR,
        *,
        build_kwargs: Optional[Dict[str, Any]] = None,
    ):
        self.dashboard_dir = Path(dashboard_dir)
        self.build_kwargs = dict(build_kwargs or {})
        self._sample_scope_cache: Dict[str, str] = {}

    def _meta_path(self) -> Path:
        return self.dashboard_dir / BUILD_META_FILE

    def _source_last_modified(self) -> float:
        meta = self.load_build_meta()
        return float(meta.get("source_last_modified") or 0.0)

    def ensure_indexes(self) -> Dict[str, Any]:
        if not self._meta_path().exists():
            return build_dashboard_indexes(output_dir=self.dashboard_dir, **self.build_kwargs).to_dict()
        current = dashboard_source_last_modified(**self.build_kwargs)
        meta = self.load_build_meta()
        if current > float(meta.get("source_last_modified") or 0.0):
            return build_dashboard_indexes(output_dir=self.dashboard_dir, **self.build_kwargs).to_dict()
        return meta

    def load_build_meta(self) -> Dict[str, Any]:
        if not self._meta_path().exists():
            return {}
        return json.loads(self._meta_path().read_text(encoding="utf-8"))

    def load_runs(self) -> list[Dict[str, Any]]:
        return load_jsonl(self.dashboard_dir / RUNS_FILE)

    def _filtered_runs(self, source_view: str = DEFAULT_SOURCE_VIEW) -> list[Dict[str, Any]]:
        normalized = _normalize_source_view(source_view)
        return _sort_records([record for record in self.load_runs() if self._record_matches_source_view(record, normalized)])

    def _record_matches_source_view(self, record: Dict[str, Any], source_view: str) -> bool:
        if source_view == "all":
            return True
        return self._sample_scope_for_record(record) != "fixture_like"

    def _sample_scope_for_record(self, record: Dict[str, Any]) -> str:
        sample_id = str(record.get("sample_id") or "").strip()
        if not sample_id:
            return "real_user"
        cached = self._sample_scope_cache.get(sample_id)
        if cached:
            return cached
        scope = str(record.get("sample_scope") or "").strip()
        if scope:
            self._sample_scope_cache[sample_id] = scope
            return scope
        sample_dir = self.dashboard_dir.parent / "real_telegram" / sample_id
        scope = "real_user"
        reason = None
        if sample_dir.exists():
            scope, reason = _classify_sample_scope(sample_dir, _load_optional_json(sample_dir / "ledger.json") or {})
        record["sample_scope"] = scope
        if reason:
            record["sample_scope_reason"] = reason
        self._sample_scope_cache[sample_id] = scope
        return scope

    def _filtered_sample_ids(self, source_view: str = DEFAULT_SOURCE_VIEW) -> set[str]:
        return {str(record.get("sample_id")) for record in self._filtered_runs(source_view)}

    def health_payload(self, source_view: str = DEFAULT_SOURCE_VIEW) -> Dict[str, Any]:
        normalized = _normalize_source_view(source_view)
        runs = self._filtered_runs(normalized)
        agency_records = self._filtered_agency_records(normalized)
        gap_summary = dict(self.load_gap_summary())
        gap_summary["source_view"] = normalized
        build_meta = dict(self.load_build_meta())
        build_meta.update(
            {
                "source_view": normalized,
                "total_runs": len(runs),
                "complete_runs": sum(1 for item in runs if item.get("bundle_complete")),
                "oe_available_runs": sum(1 for item in runs if item.get("oe_available")),
                "host_only_runs": sum(1 for item in runs if item.get("host_only")),
                "agency_records": len(agency_records),
            }
        )
        return {
            "status": "ok",
            "build_meta": build_meta,
            "gap_summary": gap_summary,
        }

    def load_runs_rollup(self, source_view: str = DEFAULT_SOURCE_VIEW) -> Dict[str, Any]:
        run_records = self._filtered_runs(source_view)
        latest = run_records[-1] if run_records else None
        gap_counter: Counter[str] = Counter()
        for item in run_records:
            gap_counter.update(item.get("gap_types") or [])
        return {
            "generated_at": self.load_build_meta().get("generated_at"),
            "last_sample_timestamp": latest.get("timestamp") if latest else None,
            "freshness_seconds": _freshness_seconds(latest.get("timestamp") if latest else None),
            "headline_code": _semantic(latest).get("headline_code", "unknown") if latest else "unknown",
            "summary": {
                "turn_count": len(run_records),
                "complete_bundle_count": sum(1 for item in run_records if item.get("bundle_complete")),
                "complete_bundle_rate": (sum(1 for item in run_records if item.get("bundle_complete")) / len(run_records)) if run_records else 0.0,
                "oe_available_rate": (sum(1 for item in run_records if item.get("oe_available")) / len(run_records)) if run_records else 0.0,
                "host_only_rate": (sum(1 for item in run_records if item.get("host_only")) / len(run_records)) if run_records else 0.0,
                "latest_bundle_complete": bool(latest.get("bundle_complete")) if latest else False,
                "latest_oe_available": bool(latest.get("oe_available")) if latest else False,
            },
            "charts": {
                "bundle_trend": [
                    {
                        "sample_id": item.get("sample_id"),
                        "timestamp": item.get("timestamp"),
                        "bundle_complete": item.get("bundle_complete"),
                        "oe_available": item.get("oe_available"),
                        "host_only": item.get("host_only"),
                        "gap_count": len(item.get("gap_types") or []),
                        "semantic": item.get("semantic"),
                    }
                    for item in run_records[-50:]
                ],
                "oe_state_distribution": {
                    "complete": sum(1 for item in run_records if item.get("bundle_complete")),
                    "partial": sum(1 for item in run_records if not item.get("bundle_complete") and not item.get("host_only")),
                    "host_only": sum(1 for item in run_records if item.get("host_only")),
                },
                "gap_type_distribution": dict(gap_counter),
                "continuity_status": {item.get("scenario"): item.get("status") for item in self.load_continuity()},
            },
            "continuity": self.load_continuity(),
            "recent_runs": [
                {
                    "sample_id": item.get("sample_id"),
                    "timestamp": item.get("timestamp"),
                    "bundle_complete": item.get("bundle_complete"),
                    "oe_available": item.get("oe_available"),
                    "host_only": item.get("host_only"),
                    "gap_types": item.get("gap_types") or [],
                    "semantic": item.get("semantic"),
                }
                for item in reversed(run_records[-12:])
            ],
            "records": run_records,
            "semantic_summary": {
                "headline": _counter_to_dict([_semantic(item).get("headline_code") for item in run_records]),
                "evidence_state": _counter_to_dict([_semantic(item).get("evidence_state_code") for item in run_records], default_label="partial"),
            },
            "source_view": _normalize_source_view(source_view),
        }

    def load_growth(self) -> list[Dict[str, Any]]:
        return load_jsonl(self.dashboard_dir / GROWTH_FILE)

    def _filtered_growth_records(self, source_view: str = DEFAULT_SOURCE_VIEW) -> list[Dict[str, Any]]:
        sample_ids = self._filtered_sample_ids(source_view)
        return _sort_records([record for record in self.load_growth() if str(record.get("sample_id")) in sample_ids])

    def load_growth_rollup(self, source_view: str = DEFAULT_SOURCE_VIEW) -> Dict[str, Any]:
        records = self._filtered_growth_records(source_view)
        latest = records[-1] if records else None
        reflection_values = [str((item.get("reflection_summary") or {}).get("trigger") or "none") for item in records]
        motion_values = [_semantic(item).get("growth_motion_code") for item in records]
        focus_values = [item.get("focus_goal") for item in records if item.get("focus_goal")]
        component_totals: Dict[str, float] = {}
        component_counts: Dict[str, int] = {}
        for item in records:
            for key, value in dict(item.get("appraisal_delta_summary") or {}).items():
                number = _coerce_float(value)
                if number is None:
                    continue
                component_totals[key] = component_totals.get(key, 0.0) + number
                component_counts[key] = component_counts.get(key, 0) + 1
        appraisal_means = {
            key: round(component_totals[key] / component_counts[key], 4)
            for key in component_totals
            if component_counts.get(key)
        }
        return {
            "generated_at": self.load_build_meta().get("generated_at"),
            "last_sample_timestamp": latest.get("timestamp") if latest else None,
            "freshness_seconds": _freshness_seconds(latest.get("timestamp") if latest else None),
            "headline_code": _semantic(latest).get("headline_code", "unknown") if latest else "unknown",
            "summary": {
                "total_records": len(records),
                "reflecting_count": sum(1 for item in records if _semantic(item).get("growth_motion_code") == "reflecting"),
                "repairing_count": sum(1 for item in records if _semantic(item).get("growth_motion_code") == "repairing"),
                "focus_shift_count": sum(1 for item in records if _semantic(item).get("growth_motion_code") == "focus_shift"),
                "identity_shift_count": sum(1 for item in records if _semantic(item).get("growth_motion_code") == "identity_shift"),
                "latest_revision_counter": int(latest.get("revision_counter") or 0) if latest else 0,
            },
            "charts": {
                "revision_trend": [
                    {
                        "sample_id": item.get("sample_id"),
                        "timestamp": item.get("timestamp"),
                        "revision_counter": item.get("revision_counter"),
                        "growth_motion_code": _semantic(item).get("growth_motion_code", "unknown"),
                    }
                    for item in records[-50:]
                ],
                "appraisal_component_means": appraisal_means,
                "reflection_trigger_distribution": _counter_to_dict(reflection_values, default_label="none"),
                "growth_motion_distribution": _counter_to_dict(motion_values),
                "focus_timeline": [
                    {
                        "sample_id": item.get("sample_id"),
                        "timestamp": item.get("timestamp"),
                        "focus_goal": item.get("focus_goal") or "none",
                    }
                    for item in records[-50:]
                    if item.get("focus_goal")
                ],
            },
            "recent_growth": [
                {
                    "sample_id": item.get("sample_id"),
                    "timestamp": item.get("timestamp"),
                    "focus_goal": item.get("focus_goal"),
                    "revision_counter": item.get("revision_counter"),
                    "reflection_trigger": (item.get("reflection_summary") or {}).get("trigger"),
                    "semantic": item.get("semantic"),
                }
                for item in reversed(records[-12:])
            ],
            "records": records,
            "semantic_summary": {
                "headline": _counter_to_dict([_semantic(item).get("headline_code") for item in records]),
                "growth_motion": _counter_to_dict([_semantic(item).get("growth_motion_code") for item in records]),
                "focus": _counter_to_dict(focus_values, default_label="none"),
            },
            "source_view": _normalize_source_view(source_view),
        }

    def load_failures(self) -> list[Dict[str, Any]]:
        return load_jsonl(self.dashboard_dir / FAILURES_FILE)

    def load_failures_rollup(self) -> Dict[str, Any]:
        path = self.dashboard_dir / FAILURES_ROLLUP_FILE
        if not path.exists():
            records = self.load_failures()
            return {"records": records, "gap_summary": self.load_gap_summary()}
        return json.loads(path.read_text(encoding="utf-8"))

    def load_continuity(self) -> list[Dict[str, Any]]:
        return load_jsonl(self.dashboard_dir / CONTINUITY_FILE)

    def load_gap_summary(self) -> Dict[str, Any]:
        path = self.dashboard_dir / GAP_SUMMARY_FILE
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def load_agency_records(self) -> list[Dict[str, Any]]:
        return load_jsonl(self.dashboard_dir / "agency_runs.jsonl")

    def _filtered_agency_records(self, source_view: str = DEFAULT_SOURCE_VIEW) -> list[Dict[str, Any]]:
        sample_ids = self._filtered_sample_ids(source_view)
        return _sort_records([record for record in self.load_agency_records() if str(record.get("sample_id")) in sample_ids])

    def load_agency_rollup(self, source_view: str = DEFAULT_SOURCE_VIEW) -> Dict[str, Any]:
        records = self._filtered_agency_records(source_view)
        base_rollup = json.loads((self.dashboard_dir / AGENCY_ROLLUP_FILE).read_text(encoding="utf-8")) if (self.dashboard_dir / AGENCY_ROLLUP_FILE).exists() else {}
        if not records:
            return {
                "generated_at": self.load_build_meta().get("generated_at"),
                "last_sample_timestamp": None,
                "freshness_seconds": None,
                "profile_scope": [],
                "summary": {
                    "turn_count": 0,
                    "idle_check_count": 0,
                    "idle_eligible_rate": 0.0,
                    "candidate_generated_rate": 0.0,
                    "exec_result_writeback_rate": 0.0,
                    "trace_completeness_rate": 0.0,
                    "direct_execution_violations": 0,
                    "mean_urge": None,
                    "identity_switch_count": 0,
                    "focus_change_count": 0,
                },
                "latest_state": None,
                "funnel": {
                    "idle_eligible_count": 0,
                    "candidate_generated_count": 0,
                    "governor_approved_count": 0,
                    "host_action_count": 0,
                    "writeback_count": 0,
                },
                "trends": [],
                "distributions": {
                    "candidate_actions": {},
                    "governor_status": {},
                    "final_host_action": {},
                    "suppression_reason": {},
                },
                "recent_turns": [],
                "excluded_counts": base_rollup.get("excluded_counts") or {},
                "semantic_summary": {
                    "intent": {},
                    "host_posture": {},
                    "result_state": {},
                    "growth_motion": {},
                    "evidence_state": {},
                    "headline": {},
                },
                "headline_code": "unknown",
                "story_cards": [],
                "source_view": _normalize_source_view(source_view),
            }

        latest = records[-1]
        urge_values = [float(item["urge_score"]) for item in records if item.get("urge_score") is not None]
        identity_switch_count = sum(
            1
            for previous, current in zip(records, records[1:])
            if previous.get("identity_light_hash") != current.get("identity_light_hash")
        )
        focus_change_count = sum(
            1
            for previous, current in zip(records, records[1:])
            if previous.get("focus_goal") != current.get("focus_goal")
        )
        candidate_counter: Counter[str] = Counter()
        governor_counter: Counter[str] = Counter()
        final_action_counter: Counter[str] = Counter()
        suppression_counter: Counter[str] = Counter()
        for item in records:
            candidate_counter.update(item.get("candidate_actions") or ["none"])
            governor_counter.update([str(item.get("governor_status") or "unknown")])
            final_action_counter.update([str(item.get("final_host_action") or "none")])
            suppression_counter.update([str(item.get("suppression_reason") or "none")])
        latest_semantic = _semantic(latest)
        return {
            "generated_at": self.load_build_meta().get("generated_at"),
            "last_sample_timestamp": latest.get("timestamp"),
            "freshness_seconds": _freshness_seconds(latest.get("timestamp")),
            "profile_scope": sorted({str(item.get("subject_profile") or "unknown") for item in records}),
            "summary": {
                "turn_count": len(records),
                "idle_check_count": sum(1 for item in records if item.get("idle_check")),
                "idle_eligible_rate": (sum(1 for item in records if item.get("idle_eligible")) / len(records)) if records else 0.0,
                "candidate_generated_rate": (sum(1 for item in records if item.get("candidate_generated")) / len(records)) if records else 0.0,
                "exec_result_writeback_rate": (sum(1 for item in records if item.get("writeback_applied")) / len(records)) if records else 0.0,
                "trace_completeness_rate": (sum(1 for item in records if item.get("trace_completeness")) / len(records)) if records else 0.0,
                "direct_execution_violations": sum(1 for item in records if item.get("direct_execution_violation")),
                "mean_urge": round(sum(urge_values) / len(urge_values), 4) if urge_values else None,
                "identity_switch_count": identity_switch_count,
                "focus_change_count": focus_change_count,
            },
            "latest_state": {
                "sample_id": latest.get("sample_id"),
                "timestamp": latest.get("timestamp"),
                "subject_profile": latest.get("subject_profile"),
                "session_id": latest.get("session_id"),
                "focus_goal": latest.get("focus_goal"),
                "urge_score": latest.get("urge_score"),
                "candidate_actions": latest.get("candidate_actions") or [],
                "governor_status": latest.get("governor_status"),
                "final_host_action": latest.get("final_host_action"),
                "exec_result_type": latest.get("exec_result_type"),
                "writeback_applied": latest.get("writeback_applied"),
                "revision_counter": latest.get("revision_counter"),
                "trace_completeness": latest.get("trace_completeness"),
                "semantic": latest.get("semantic"),
            },
            "funnel": {
                "idle_eligible_count": sum(1 for item in records if item.get("idle_eligible")),
                "candidate_generated_count": sum(1 for item in records if item.get("candidate_generated")),
                "governor_approved_count": sum(1 for item in records if item.get("governor_status") == "approved"),
                "host_action_count": sum(1 for item in records if item.get("final_host_action") and item.get("final_host_action") != "none"),
                "writeback_count": sum(1 for item in records if item.get("writeback_applied")),
            },
            "trends": [
                {
                    "sample_id": item.get("sample_id"),
                    "timestamp": item.get("timestamp"),
                    "urge_score": item.get("urge_score"),
                    "idle_eligible": item.get("idle_eligible"),
                    "candidate_generated": item.get("candidate_generated"),
                    "writeback_applied": item.get("writeback_applied"),
                    "revision_counter": item.get("revision_counter"),
                }
                for item in records[-50:]
            ],
            "distributions": {
                "candidate_actions": dict(candidate_counter),
                "governor_status": dict(governor_counter),
                "final_host_action": dict(final_action_counter),
                "suppression_reason": dict(suppression_counter),
            },
            "recent_turns": [
                {
                    "sample_id": item.get("sample_id"),
                    "timestamp": item.get("timestamp"),
                    "urge_score": item.get("urge_score"),
                    "candidate_actions": item.get("candidate_actions") or [],
                    "governor_status": item.get("governor_status"),
                    "final_host_action": item.get("final_host_action"),
                    "exec_result_type": item.get("exec_result_type"),
                    "focus_goal": item.get("focus_goal"),
                    "trace_completeness": item.get("trace_completeness"),
                    "semantic": item.get("semantic"),
                }
                for item in reversed(records[-12:])
            ],
            "excluded_counts": base_rollup.get("excluded_counts") or {},
            "semantic_summary": {
                "intent": _counter_to_dict([_semantic(item).get("intent_code") for item in records]),
                "host_posture": _counter_to_dict([_semantic(item).get("host_posture_code") for item in records], default_label="not_applicable"),
                "result_state": _counter_to_dict([_semantic(item).get("result_state_code") for item in records], default_label="not_executed"),
                "growth_motion": _counter_to_dict([_semantic(item).get("growth_motion_code") for item in records]),
                "evidence_state": _counter_to_dict([_semantic(item).get("evidence_state_code") for item in records], default_label="partial"),
                "headline": _counter_to_dict([_semantic(item).get("headline_code") for item in records]),
            },
            "headline_code": latest_semantic.get("headline_code", "unknown"),
            "story_cards": [
                {
                    "slot": "intent",
                    "code": latest_semantic.get("intent_code", "unknown"),
                    "value": latest.get("candidate_actions") or [],
                },
                {
                    "slot": "host",
                    "code": latest_semantic.get("host_posture_code", "not_applicable"),
                    "value": latest.get("governor_status"),
                },
                {
                    "slot": "result",
                    "code": latest_semantic.get("result_state_code", "not_executed"),
                    "value": latest.get("exec_result_type"),
                },
                {
                    "slot": "growth",
                    "code": latest_semantic.get("growth_motion_code", "unknown"),
                    "value": latest.get("revision_counter"),
                },
            ],
            "source_view": _normalize_source_view(source_view),
        }

    def sample_detail(self, sample_id: str) -> Optional[Dict[str, Any]]:
        sample_dir = self.dashboard_dir.parent / "real_telegram" / sample_id
        if not sample_dir.exists():
            return None
        detail = {"sample_id": sample_id, "artifacts": {}, "artifact_refs": {}}
        for name in [
            "ledger.json",
            "raw_update.json",
            "normalized_event.json",
            "openemotion_result.json",
            "openemotion_trace.json",
            "response_plan.json",
            "outbox_record.json",
            "timeline.json",
            "tape.json",
            "replay.json",
            "summary.md",
            "sample.json",
        ]:
            path = sample_dir / name
            if not path.exists():
                continue
            detail["artifact_refs"][name] = str(path)
            if path.suffix == ".json":
                detail["artifacts"][name] = json.loads(path.read_text(encoding="utf-8"))
            else:
                detail["artifacts"][name] = path.read_text(encoding="utf-8")
        runs_rollup = self.load_runs_rollup(source_view="all")
        growth_rollup = self.load_growth_rollup(source_view="all")
        failures_rollup = self.load_failures_rollup()
        run_record = next((item for item in runs_rollup.get("records", []) if item.get("sample_id") == sample_id), None)
        growth_record = next((item for item in growth_rollup.get("records", []) if item.get("sample_id") == sample_id), None)
        agency_record = next((item for item in self.load_agency_records() if item.get("sample_id") == sample_id), None)
        failure_record = next((item for item in failures_rollup.get("records", []) if item.get("sample_id") == sample_id), None)
        chosen_semantic = (
            (agency_record or {}).get("semantic")
            or (growth_record or {}).get("semantic")
            or (run_record or {}).get("semantic")
            or (failure_record or {}).get("semantic")
        )
        detail["run_record"] = run_record
        detail["related_records"] = {
            "agency": agency_record,
            "growth": growth_record,
            "failure": failure_record,
        }
        detail["semantic_summary"] = chosen_semantic
        detail["translated_summary"] = {
            "headline_code": (chosen_semantic or {}).get("headline_code", "unknown"),
            "intent_code": (chosen_semantic or {}).get("intent_code", "unknown"),
            "host_posture_code": (chosen_semantic or {}).get("host_posture_code", "not_applicable"),
            "result_state_code": (chosen_semantic or {}).get("result_state_code", "not_executed"),
            "growth_motion_code": (chosen_semantic or {}).get("growth_motion_code", "unknown"),
            "evidence_state_code": (chosen_semantic or {}).get("evidence_state_code", "partial"),
            "why_codes": (chosen_semantic or {}).get("why_codes", []),
            "focus_goal": ((agency_record or {}).get("focus_goal") or (growth_record or {}).get("focus_goal")),
            "candidate_actions": (agency_record or {}).get("candidate_actions", []),
            "final_host_action": (agency_record or {}).get("final_host_action"),
            "exec_result_type": (agency_record or {}).get("exec_result_type"),
        }
        return detail

    def latest_sample_id(self, source_view: str = DEFAULT_SOURCE_VIEW) -> Optional[str]:
        runs_rollup = self.load_runs_rollup(source_view=source_view)
        recent_runs = runs_rollup.get("recent_runs") or []
        if recent_runs:
            return recent_runs[0].get("sample_id")
        records = runs_rollup.get("records") or []
        if not records:
            return None
        latest = max(records, key=lambda item: item.get("timestamp") or "")
        return latest.get("sample_id")

    def flow_detail(self, sample_id: Optional[str] = None, *, source_view: str = DEFAULT_SOURCE_VIEW) -> Optional[Dict[str, Any]]:
        resolved_sample_id = sample_id or self.latest_sample_id(source_view=source_view)
        if not resolved_sample_id:
            return None
        detail = self.sample_detail(resolved_sample_id)
        if detail is None:
            return None

        artifacts = detail.get("artifacts") or {}
        artifact_refs = detail.get("artifact_refs") or {}
        ledger = artifacts.get("ledger.json") or {}
        normalized_event = artifacts.get("normalized_event.json") or {}
        result = artifacts.get("openemotion_result.json") or {}
        trace = artifacts.get("openemotion_trace.json") or {}
        response_plan = artifacts.get("response_plan.json") or {}
        outbox_record = artifacts.get("outbox_record.json") or {}
        timeline = artifacts.get("timeline.json") or []
        run_record = detail.get("run_record") or {}
        failure_record = (detail.get("related_records") or {}).get("failure") or {}

        runtime_summary = _deep_get(normalized_event, "runtime_summary") or _deep_get(
            ledger, "inputs.normalized_event.runtime_summary"
        ) or {}
        conversation_summary = _deep_get(normalized_event, "conversation_summary") or _deep_get(
            normalized_event, "conversation_context"
        ) or _deep_get(ledger, "inputs.normalized_event.conversation_summary") or {}
        raw_text = _first_non_empty(
            _deep_get(ledger, "inputs.raw_update.message.text"),
            _deep_get(normalized_event, "event.raw_text"),
            _deep_get(ledger, "inputs.normalized_event.event.raw_text"),
        )

        top_candidate = _first_non_empty(
            _deep_get(result, "policy_hint.top_candidate_action"),
            (result.get("candidate_actions") or [None])[0],
        )
        response_tendency = result.get("response_tendency") or {}
        policy_hint = result.get("policy_hint") or {}
        response_metadata = response_plan.get("metadata") or {}
        recent_result_context = response_metadata.get("recent_result_context") or {}
        parser_source = _first_non_empty(
            response_metadata.get("parser_source"),
            runtime_summary.get("parser_source"),
        )
        request_mode = _first_non_empty(
            response_metadata.get("request_mode"),
            runtime_summary.get("request_mode"),
        )
        pending_result_continuation = (
            response_metadata.get("pending_result_continuation") or runtime_summary.get("pending_result_continuation") or {}
        )
        continuation_mode = (
            str(pending_result_continuation.get("requested_mode") or "").strip() or None
            if isinstance(pending_result_continuation, dict)
            else None
        )
        continuation_status = (
            str(pending_result_continuation.get("status") or "").strip() or None
            if isinstance(pending_result_continuation, dict)
            else None
        )
        correction_context = _boolish(
            response_metadata.get("correction_context")
            if response_metadata.get("correction_context") is not None
            else runtime_summary.get("correction_context")
        )
        reflection_trigger = _first_non_empty(
            _deep_get(result, "reflection_note.trigger"),
            trace.get("reflection_trigger"),
            _deep_get(policy_hint, "reflection_trigger"),
        )
        oe_available = bool(
            _first_non_empty(
                run_record.get("oe_available"),
                bool(artifacts.get("openemotion_result.json") or artifacts.get("openemotion_trace.json")),
            )
        )
        host_only = bool(
            _first_non_empty(
                run_record.get("host_only"),
                not oe_available,
            )
        )
        bundle_complete = bool(
            _first_non_empty(
                run_record.get("bundle_complete"),
                all(
                    name in artifacts
                    for name in [
                        "raw_update.json",
                        "normalized_event.json",
                        "openemotion_result.json",
                        "openemotion_trace.json",
                        "response_plan.json",
                        "outbox_record.json",
                        "timeline.json",
                        "tape.json",
                        "replay.json",
                    ]
                ),
            )
        )
        openemotion_processed = _timeline_has_stage(timeline, "openemotion_processed")
        delivered = bool(_boolish(outbox_record.get("success")) or _timeline_has_stage(timeline, "message_sent"))
        degraded = response_plan.get("reply_authority") == "host_degraded_fallback"
        contexts_seen = {
            "self_model": _present_context(trace, "self_model_context"),
            "developmental": _present_context(trace, "developmental_self_context"),
            "social": _present_context(trace, "social_self_context"),
            "embodied": _present_context(trace, "embodied_self_context"),
            "integration": _present_context(trace, "selfhood_integration_context"),
            "initiative": _present_context(trace, "initiative_self_context"),
            "initiative_realization": _present_context(trace, "initiative_realization_context"),
        }
        active_contexts = [name for name, present in contexts_seen.items() if present]
        missing_contexts = [name for name, present in contexts_seen.items() if not present]
        writeback_keys = [
            key
            for key in result.keys()
            if key.endswith("_candidate") and result.get(key) not in (None, {}, [], "")
        ]
        non_empty_delta_keys = [
            key for key in result.keys() if key.endswith("_delta") and result.get(key) not in ({}, [], None)
        ]
        subject_chain_connected = bool(oe_available and openemotion_processed and not host_only)
        self_model_context_source = _resolve_self_model_context_source(
            runtime_summary,
            contexts_seen=contexts_seen,
            oe_available=oe_available,
            openemotion_processed=openemotion_processed,
            host_only=host_only,
        )

        input_summary = {
            "status": "pass" if raw_text else "broken",
            "headline": "Input captured" if raw_text else "Input missing",
            "sentence": f"输入文本已标准化为 {runtime_summary.get('primary_intent') or 'unknown'} / {runtime_summary.get('interaction_kind') or 'unknown'}。"
            if raw_text
            else "缺少 raw input，当前样本无法解释输入层。",
            "raw_text": raw_text,
            "event_type": _first_non_empty(
                _deep_get(normalized_event, "event.event_type"),
                _deep_get(ledger, "inputs.normalized_event.event.event_type"),
            ),
            "primary_intent": runtime_summary.get("primary_intent"),
            "interaction_kind": runtime_summary.get("interaction_kind"),
            "conversation_act": runtime_summary.get("conversation_act"),
            "artifacts": ["ledger.json", "normalized_event.json", "raw_update.json"],
            "engineering_fields": [
                _flow_field("raw_text", "ledger.json", "inputs.raw_update.message.text", raw_text),
                _flow_field(
                    "event_type",
                    "normalized_event.json",
                    "event.event_type",
                    _first_non_empty(
                        _deep_get(normalized_event, "event.event_type"),
                        _deep_get(ledger, "inputs.normalized_event.event.event_type"),
                    ),
                ),
                _flow_field(
                    "primary_intent",
                    "normalized_event.json",
                    "runtime_summary.primary_intent",
                    runtime_summary.get("primary_intent"),
                ),
                _flow_field(
                    "interaction_kind",
                    "normalized_event.json",
                    "runtime_summary.interaction_kind",
                    runtime_summary.get("interaction_kind"),
                ),
                _flow_field(
                    "conversation_act",
                    "normalized_event.json",
                    "runtime_summary.conversation_act",
                    runtime_summary.get("conversation_act"),
                ),
            ],
        }

        ingress_ok = oe_available and openemotion_processed and not host_only
        host_ingress_summary = {
            "status": "host_only" if host_only else ("pass" if ingress_ok else "broken"),
            "headline": "Host ingress passed" if ingress_ok else ("Host-only interception" if host_only else "Host ingress incomplete"),
            "sentence": (
                f"宿主解析出 runtime_path={response_plan.get('reply_origin') or runtime_summary.get('runtime_action') or 'unknown'}，"
                f" parser_source={parser_source or 'unknown'}，request_mode={request_mode or 'none'}，并在进入主体前完成 session/task resolve。"
                if not host_only
                else "这轮样本停在宿主层，没有形成主体处理证据。"
            ),
            "authorized": True,
            "subject_gate_ingress_ok": ingress_ok,
            "runtime_path": _first_non_empty(response_plan.get("reply_origin"), runtime_summary.get("runtime_action")),
            "parser_source": parser_source,
            "request_mode": request_mode,
            "recent_result_binding": bool(recent_result_context),
            "continuation_mode": continuation_mode,
            "continuation_status": continuation_status,
            "correction_context": correction_context,
            "pending_result_continuation": pending_result_continuation,
            "session_key": _first_non_empty(conversation_summary.get("session_id"), conversation_summary.get("thread_id")),
            "active_task": _boolish(runtime_summary.get("active_task")),
            "waiting_input": _boolish(runtime_summary.get("confirm_pending")),
            "task_conflict": _boolish(_deep_get(runtime_summary, "task_conflict.active")),
            "recent_result_source_turn": response_metadata.get("result_binding_source_turn"),
            "artifacts": ["normalized_event.json", "ledger.json", "timeline.json"],
            "engineering_fields": [
                _flow_field("authorized", "normalized_event.json", "runtime_summary.primary_intent", True),
                _flow_field("subject_gate_ingress_ok", "timeline.json", "stage=openemotion_processed", ingress_ok),
                _flow_field(
                    "runtime_path",
                    "response_plan.json",
                    "reply_origin",
                    _first_non_empty(response_plan.get("reply_origin"), runtime_summary.get("runtime_action")),
                ),
                _flow_field(
                    "parser_source",
                    "response_plan.json | normalized_event.json",
                    "metadata.parser_source | runtime_summary.parser_source",
                    parser_source,
                ),
                _flow_field(
                    "request_mode",
                    "response_plan.json | normalized_event.json",
                    "metadata.request_mode | runtime_summary.request_mode",
                    request_mode,
                ),
                _flow_field(
                    "session_key",
                    "normalized_event.json",
                    "conversation_summary.session_id",
                    _first_non_empty(conversation_summary.get("session_id"), conversation_summary.get("thread_id")),
                ),
                _flow_field("active_task", "normalized_event.json", "runtime_summary.active_task", runtime_summary.get("active_task")),
                _flow_field("waiting_input", "normalized_event.json", "runtime_summary.confirm_pending", runtime_summary.get("confirm_pending")),
                _flow_field(
                    "recent_result_binding",
                    "response_plan.json",
                    "metadata.recent_result_context",
                    recent_result_context,
                ),
                _flow_field(
                    "continuation_mode",
                    "response_plan.json | normalized_event.json",
                    "metadata.pending_result_continuation.requested_mode | runtime_summary.pending_result_continuation.requested_mode",
                    continuation_mode,
                ),
                _flow_field(
                    "continuation_status",
                    "response_plan.json | normalized_event.json",
                    "metadata.pending_result_continuation.status | runtime_summary.pending_result_continuation.status",
                    continuation_status,
                ),
                _flow_field(
                    "recent_result_source_turn",
                    "response_plan.json",
                    "metadata.result_binding_source_turn",
                    response_metadata.get("result_binding_source_turn"),
                ),
                _flow_field(
                    "pending_result_continuation",
                    "response_plan.json | normalized_event.json",
                    "metadata.pending_result_continuation | runtime_summary.pending_result_continuation",
                    pending_result_continuation,
                ),
                _flow_field(
                    "correction_context",
                    "response_plan.json | normalized_event.json",
                    "metadata.correction_context | runtime_summary.correction_context",
                    correction_context,
                ),
            ],
        }

        subject_summary = {
            "status": "host_only" if host_only else ("pass" if oe_available else "broken"),
            "headline": "Subject processed turn" if oe_available else ("Subject unavailable" if host_only else "Subject evidence missing"),
            "sentence": _build_subject_one_sentence(
                contexts_seen=contexts_seen,
                response_tendency=response_tendency,
                policy_hint=policy_hint,
                top_candidate=top_candidate if isinstance(top_candidate, dict) else None,
            )
            if oe_available
            else "这轮没有形成可用的 OpenEmotion result/trace，无法解释主体理解层。",
            "oe_available": oe_available,
            "openemotion_processed": openemotion_processed,
            "subject_chain_connected": subject_chain_connected,
            "context_load_summary": {
                "loaded": active_contexts,
                "missing": missing_contexts,
            },
            "contexts_seen": contexts_seen,
            "self_model_context_source": self_model_context_source,
            "dominant_tendency": {
                "preferred_mode": response_tendency.get("preferred_mode"),
                "preferred_tone": response_tendency.get("preferred_tone"),
                "suggested_next_step": response_tendency.get("suggested_next_step"),
            },
            "policy_hint_summary": {
                "urge_score": policy_hint.get("urge_score"),
                "risk_bias": policy_hint.get("risk_bias"),
                "closure_bias": policy_hint.get("closure_bias"),
                "ask_preferred": policy_hint.get("ask_preferred"),
            },
            "candidate_action_summary": {
                "action_type": (top_candidate or {}).get("action_type") if isinstance(top_candidate, dict) else None,
                "target": (top_candidate or {}).get("target") if isinstance(top_candidate, dict) else None,
                "reason": (top_candidate or {}).get("reason") if isinstance(top_candidate, dict) else None,
            },
            "reflection_trigger": reflection_trigger,
            "subject_one_sentence": _build_subject_one_sentence(
                contexts_seen=contexts_seen,
                response_tendency=response_tendency,
                policy_hint=policy_hint,
                top_candidate=top_candidate if isinstance(top_candidate, dict) else None,
            )
            if oe_available
            else "主体理解层不可用。",
            "what_it_saw": " + ".join(active_contexts) if active_contexts else "minimal context",
            "what_it_cared_about": _first_non_empty(
                response_tendency.get("suggested_next_step"),
                policy_hint.get("risk_bias"),
                "no strong bounded tendency",
            ),
            "what_it_suggested": _first_non_empty(
                response_tendency.get("suggested_next_step"),
                (top_candidate or {}).get("action_type") if isinstance(top_candidate, dict) else None,
                "none",
            ),
            "state_change_summary": {
                "non_empty_delta_keys": non_empty_delta_keys,
                "writeback_candidates": writeback_keys,
            },
            "artifacts": ["openemotion_result.json", "openemotion_trace.json", "ledger.json"],
            "engineering_fields": [
                _flow_field("oe_available", "runs.jsonl", "oe_available", oe_available),
                _flow_field("openemotion_processed", "timeline.json", "stage=openemotion_processed", openemotion_processed),
                _flow_field("subject_chain_connected", "timeline.json", "oe_available + openemotion_processed + !host_only", subject_chain_connected),
                _flow_field("context_load_summary", "openemotion_trace.json", "constraint_summary.*.present", {"loaded": active_contexts, "missing": missing_contexts}),
                _flow_field("contexts_seen", "openemotion_trace.json", "constraint_summary.*.present", contexts_seen),
                _flow_field("self_model_context_source", "normalized_event.json", "runtime_summary.self_model_context_source", self_model_context_source),
                _flow_field("response_tendency", "openemotion_result.json", "response_tendency", response_tendency),
                _flow_field("policy_hint", "openemotion_result.json", "policy_hint", policy_hint),
                _flow_field("top_candidate_action", "openemotion_result.json", "policy_hint.top_candidate_action", top_candidate),
                _flow_field("reflection_trigger", "openemotion_trace.json", "reflection_trigger", reflection_trigger),
                _flow_field("state_changes", "openemotion_result.json", "*_delta / *_candidate", {"non_empty_delta_keys": non_empty_delta_keys, "writeback_candidates": writeback_keys}),
            ],
        }

        host_arbitration_summary = {
            "status": "degraded" if degraded else ("pass" if response_plan else "broken"),
            "headline": "Host degraded reply" if degraded else ("Host arbitration complete" if response_plan else "Host arbitration missing"),
            "sentence": (
                f"宿主以 {response_plan.get('reply_authority') or 'unknown'} / {response_plan.get('reply_origin') or 'unknown'} 裁决这轮输出。"
                if response_plan
                else "缺少 response plan，当前无法解释宿主裁决层。"
            ),
            "reply_authority": response_plan.get("reply_authority"),
            "reply_origin": response_plan.get("reply_origin"),
            "response_plan_status": response_plan.get("status"),
            "degraded": degraded,
            "tool_selected": _first_non_empty(
                (response_plan.get("candidate_action_types") or [None])[0],
                (top_candidate or {}).get("action_type") if isinstance(top_candidate, dict) else None,
            ),
            "host_override_reason": _first_non_empty(
                response_plan.get("output_check_reason"),
                response_plan.get("intent_gate_reason"),
                failure_record.get("cause_type"),
            ),
            "chat_cadence_mode": response_plan.get("chat_cadence_mode"),
            "subject_gate_finalize_ok": bool(response_plan) and not host_only,
            "artifacts": ["response_plan.json", "ledger.json"],
            "engineering_fields": [
                _flow_field("reply_authority", "response_plan.json", "reply_authority", response_plan.get("reply_authority")),
                _flow_field("reply_origin", "response_plan.json", "reply_origin", response_plan.get("reply_origin")),
                _flow_field("response_plan_status", "response_plan.json", "status", response_plan.get("status")),
                _flow_field("degraded", "response_plan.json", "reply_authority", degraded),
                _flow_field("tool_selected", "response_plan.json", "candidate_action_types[0]", _first_non_empty(
                    (response_plan.get("candidate_action_types") or [None])[0],
                    (top_candidate or {}).get("action_type") if isinstance(top_candidate, dict) else None,
                )),
                _flow_field("host_override_reason", "response_plan.json", "output_check_reason", _first_non_empty(
                    response_plan.get("output_check_reason"),
                    response_plan.get("intent_gate_reason"),
                    failure_record.get("cause_type"),
                )),
                _flow_field("chat_cadence_mode", "response_plan.json", "chat_cadence_mode", response_plan.get("chat_cadence_mode")),
            ],
        }

        final_text_surface = _build_final_text_surface(
            response_plan=response_plan,
            response_metadata=response_metadata,
            outbox_record=outbox_record,
            delivered=delivered,
        )

        output_summary = {
            "status": "pass" if delivered else ("host_only" if host_only else "broken"),
            "headline": "Output delivered" if delivered else ("No final delivery" if not host_only else "Host-only output"),
            "sentence": (
                f"最终以 {response_plan.get('delivery_kind') or 'unknown'} 形式送出，message_sent={delivered}。"
                if response_plan
                else "缺少 delivery contract，当前无法解释输出层。"
            ),
            "delivered": delivered,
            "delivery_kind": response_plan.get("delivery_kind"),
            "final_text_preview": final_text_surface.get("final_text_preview"),
            "final_text_hash": final_text_surface.get("final_text_hash"),
            "final_text_capture_status": final_text_surface.get("final_text_capture_status"),
            "final_text_capture_reason": final_text_surface.get("final_text_capture_reason"),
            "reply_length": final_text_surface.get("final_text_length"),
            "message_sent": _timeline_has_stage(timeline, "message_sent"),
            "bundle_complete": bundle_complete,
            "artifacts": ["outbox_record.json", "timeline.json", "response_plan.json"],
            "engineering_fields": [
                _flow_field("delivered", "outbox_record.json", "success", delivered),
                _flow_field("delivery_kind", "response_plan.json", "delivery_kind", response_plan.get("delivery_kind")),
                _flow_field(
                    "final_text_preview",
                    "response_plan.json",
                    "reply_text | metadata.final_text_preview | outbox_record.final_text_preview",
                    final_text_surface.get("final_text_preview"),
                ),
                _flow_field(
                    "final_text_capture_status",
                    "outbox_record.json",
                    "text_length + response_plan.reply_text + metadata.final_text_preview",
                    final_text_surface.get("final_text_capture_status"),
                ),
                _flow_field("final_text_hash", "response_plan.json", "metadata.final_text_hash | outbox_record.final_text_hash", final_text_surface.get("final_text_hash")),
                _flow_field("reply_length", "outbox_record.json", "text_length", final_text_surface.get("final_text_length")),
                _flow_field("message_sent", "timeline.json", "stage=message_sent", _timeline_has_stage(timeline, "message_sent")),
                _flow_field("bundle_complete", "runs.jsonl", "bundle_complete", bundle_complete),
            ],
        }

        drives_delta = _first_non_empty(result.get("drives_delta"), result.get("endogenous_drive_delta"), {}) or {}
        canonical_fields_summary = {
            "status": "pass" if oe_available else ("host_only" if host_only else "broken"),
            "headline": "Canonical fields extracted" if oe_available else "Canonical fields unavailable",
            "sentence": (
                "把主体关键输出、宿主裁决和最终送出文本收成固定审计字段。"
                if oe_available
                else "主体结果缺失时，canonical fields 只能部分解释宿主与输出层。"
            ),
            "loaded_axes": active_contexts,
            "identity_delta": result.get("identity_delta") or {},
            "self_model_delta": result.get("self_model_delta") or {},
            "drives_delta": drives_delta,
            "policy_hint": policy_hint,
            "response_tendency": response_tendency,
            "host_arbitration_result": {
                "reply_authority": response_plan.get("reply_authority"),
                "reply_origin": response_plan.get("reply_origin"),
                "response_plan_status": response_plan.get("status"),
                "chat_cadence_mode": response_plan.get("chat_cadence_mode"),
                "output_check_reason": response_plan.get("output_check_reason"),
                "intent_gate_reason": response_plan.get("intent_gate_reason"),
            },
            "final_delivered_text": {
                "preview": final_text_surface.get("final_text_preview"),
                "hash": final_text_surface.get("final_text_hash"),
                "length": final_text_surface.get("final_text_length"),
                "capture_status": final_text_surface.get("final_text_capture_status"),
                "capture_reason": final_text_surface.get("final_text_capture_reason"),
            },
            "artifacts": ["openemotion_result.json", "response_plan.json", "outbox_record.json"],
            "engineering_fields": [
                _flow_field("loaded_axes", "openemotion_trace.json", "constraint_summary.*.present", active_contexts),
                _flow_field("identity_delta", "openemotion_result.json", "identity_delta", result.get("identity_delta") or {}),
                _flow_field("self_model_delta", "openemotion_result.json", "self_model_delta", result.get("self_model_delta") or {}),
                _flow_field("drives_delta", "openemotion_result.json", "drives_delta | endogenous_drive_delta", drives_delta),
                _flow_field("policy_hint", "openemotion_result.json", "policy_hint", policy_hint),
                _flow_field("response_tendency", "openemotion_result.json", "response_tendency", response_tendency),
                _flow_field(
                    "host_arbitration_result",
                    "response_plan.json",
                    "reply_authority + reply_origin + status + chat_cadence_mode + output_check_reason + intent_gate_reason",
                    {
                        "reply_authority": response_plan.get("reply_authority"),
                        "reply_origin": response_plan.get("reply_origin"),
                        "response_plan_status": response_plan.get("status"),
                        "chat_cadence_mode": response_plan.get("chat_cadence_mode"),
                        "output_check_reason": response_plan.get("output_check_reason"),
                        "intent_gate_reason": response_plan.get("intent_gate_reason"),
                    },
                ),
                _flow_field("final_delivered_text", "response_plan.json", "reply_text | metadata.final_text_preview | outbox_record.final_text_preview", final_text_surface),
            ],
        }
        reply_evolution_summary = _build_reply_evolution_summary(
            response_plan=response_plan,
            response_metadata=response_metadata,
            policy_hint=policy_hint,
            outbox_record=outbox_record,
            delivered=delivered,
            host_only=host_only,
            degraded=degraded,
            output_summary=output_summary,
        )

        overall_status = "pass"
        if host_only:
            overall_status = "host_only"
        elif not oe_available or not response_plan:
            overall_status = "broken"
        elif degraded or not delivered or not bundle_complete:
            overall_status = "degraded"

        chain_status = {
            "ingress_status": host_ingress_summary["status"],
            "subject_status": subject_summary["status"],
            "arbitration_status": host_arbitration_summary["status"],
            "delivery_status": output_summary["status"],
            "overall_status": overall_status,
            "verdict_headline": {
                "pass": "主链已贯通，证据完整",
                "degraded": "主链贯通，但结果有降级或不一致",
                "host_only": "这轮停在宿主层，没有进入主体",
                "broken": "主链有缺口，当前证据不足以证明贯通",
            }[overall_status],
            "verdict_sentence": {
                "pass": "输入、主体理解、宿主裁决和输出都能在同一条样本里回指到正式证据。",
                "degraded": "链路基本贯通，但宿主降级、证据缺口或输出异常仍需要继续排查。",
                "host_only": "这轮没有形成 OpenEmotion 结构化结果，无法把它当成主体处理过的样本。",
                "broken": "这轮缺少关键 artifact 或阶段性状态，当前不能视为主链正常通过。",
            }[overall_status],
            "verdict_subsentence": "链路是否贯通，与最终文本是否被 bounded 持久化，是两件不同的检查项。",
        }

        failure_or_gap_summary = {
            "gap_types": run_record.get("gap_types") or [],
            "semantic_why_codes": ((run_record.get("semantic") or {}).get("why_codes") or []),
            "failure_id": failure_record.get("failure_id"),
            "failure_cause": failure_record.get("cause_type"),
            "source": failure_record.get("source"),
            "headline": "No explicit blocker"
            if not (run_record.get("gap_types") or failure_record)
            else "Current blockers or evidence gaps are present",
            "sentence": " / ".join(
                str(item)
                for item in [
                    ", ".join(run_record.get("gap_types") or []),
                    failure_record.get("cause_type"),
                    ", ".join(((run_record.get("semantic") or {}).get("why_codes") or [])),
                ]
                if item
            )
            or "当前没有显式 gap type 或 failure record。",
        }

        return FlowViewRecord(
            sample_id=resolved_sample_id,
            channel=_first_non_empty(ledger.get("channel"), "telegram"),
            timestamp=_first_non_empty(ledger.get("timestamp"), run_record.get("timestamp")),
            input_summary=input_summary,
            host_ingress_summary=host_ingress_summary,
            subject_summary=subject_summary,
            canonical_fields_summary=canonical_fields_summary,
            reply_evolution_summary=reply_evolution_summary,
            host_arbitration_summary=host_arbitration_summary,
            output_summary=output_summary,
            chain_status=chain_status,
            failure_or_gap_summary=failure_or_gap_summary,
            artifact_refs=artifact_refs,
        ).to_dict()


class DashboardRequestHandler(BaseHTTPRequestHandler):
    store: DashboardDataStore
    chat_service: Optional[DashboardChatService] = None

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        self.store.ensure_indexes()
        parsed = urlparse(self.path)

        if parsed.path.startswith("/api/dashboard/"):
            self._handle_api(parsed)
            return

        if parsed.path.startswith("/static/"):
            self._serve_static(parsed.path.removeprefix("/static/"))
            return

        if parsed.path in {"/", "/runs", "/flow", "/agency", "/growth", "/failures", "/chat"} or parsed.path.startswith("/samples/"):
            self._serve_html_shell(parsed.path)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/dashboard/chat/"):
            self._handle_api(parsed, method="POST")
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def _handle_api(self, parsed, *, method: str = "GET") -> None:
        query = parse_qs(parsed.query)
        source_view = _normalize_source_view((query.get("source_view") or [None])[0])
        if parsed.path.startswith("/api/dashboard/chat/"):
            self._handle_chat_api(parsed, method=method)
            return

        if parsed.path == "/api/dashboard/health":
            self._send_json(self.store.health_payload(source_view=source_view))
            return

        if parsed.path == "/api/dashboard/runs":
            payload = self.store.load_runs_rollup(source_view=source_view)
            limit = int((query.get("limit") or ["200"])[0])
            payload["records"] = payload.get("records", [])[:limit]
            payload["recent_runs"] = payload.get("recent_runs", [])[: min(limit, 50)]
            self._send_json(payload)
            return

        if parsed.path == "/api/dashboard/flow":
            sample_id = (query.get("sample_id") or [None])[0]
            payload = self.store.flow_detail(sample_id, source_view=source_view)
            if payload is None:
                self.send_error(HTTPStatus.NOT_FOUND, "No flow sample available")
                return
            self._send_json(payload)
            return

        if parsed.path == "/api/dashboard/growth":
            payload = self.store.load_growth_rollup(source_view=source_view)
            limit = int((query.get("limit") or ["200"])[0])
            payload["records"] = payload.get("records", [])[:limit]
            payload["recent_growth"] = payload.get("recent_growth", [])[: min(limit, 50)]
            self._send_json(payload)
            return

        if parsed.path == "/api/dashboard/failures":
            self._send_json(self.store.load_failures_rollup())
            return

        if parsed.path == "/api/dashboard/agency":
            self._send_json(self.store.load_agency_rollup(source_view=source_view))
            return

        if parsed.path.startswith("/api/dashboard/samples/") and parsed.path.endswith("/flow"):
            sample_id = parsed.path.split("/")[-2]
            payload = self.store.flow_detail(sample_id, source_view=source_view)
            if payload is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Unknown sample_id")
                return
            self._send_json(payload)
            return

        if parsed.path.startswith("/api/dashboard/samples/"):
            sample_id = parsed.path.rsplit("/", 1)[-1]
            detail = self.store.sample_detail(sample_id)
            if detail is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Unknown sample_id")
                return
            self._send_json(detail)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Unknown API route")

    def _handle_chat_api(self, parsed, *, method: str) -> None:
        service = self.chat_service
        if service is None:
            self._send_json({"error": "dashboard_chat_unavailable"}, status=HTTPStatus.SERVICE_UNAVAILABLE)
            return

        try:
            query = parse_qs(parsed.query)
            if parsed.path == "/api/dashboard/chat/sessions":
                if method == "GET":
                    self._send_json(service.list_sessions())
                    return
                if method == "POST":
                    payload = self._read_json_body()
                    self._send_json(
                        service.create_or_select_session(
                            name=payload.get("name"),
                            session_id=payload.get("session_id"),
                        ),
                        status=HTTPStatus.CREATED,
                    )
                    return
                self._send_json_error(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed")
                return

            if parsed.path.startswith("/api/dashboard/chat/sessions/") and parsed.path.endswith("/messages"):
                if method != "POST":
                    self._send_json_error(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed")
                    return
                session_id = unquote(parsed.path.split("/")[-2])
                payload = self._read_json_body()
                self._send_json(service.send_message(session_id, payload.get("text") or ""))
                return

            if parsed.path.startswith("/api/dashboard/chat/sessions/"):
                if method != "GET":
                    self._send_json_error(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed")
                    return
                session_id = unquote(parsed.path.rsplit("/", 1)[-1])
                after_revision = self._parse_optional_int(query.get("after_revision", [None])[0], field_name="after_revision")
                wait_timeout_ms = self._parse_optional_int(query.get("wait_timeout_ms", [None])[0], field_name="wait_timeout_ms")
                self._send_json(
                    service.get_session_payload(
                        session_id,
                        after_revision=after_revision,
                        wait_timeout_ms=wait_timeout_ms,
                    )
                )
                return
        except DashboardChatError as exc:
            self._send_json_error(
                int(getattr(exc, "status_code", HTTPStatus.INTERNAL_SERVER_ERROR)),
                getattr(exc, "error_code", "dashboard_chat_error"),
                message=str(exc),
            )
            return
        except ValueError as exc:
            self._send_json_error(HTTPStatus.BAD_REQUEST, "invalid_json", message=str(exc))
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Unknown chat API route")

    def _send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json_error(self, status: int, error: str, *, message: Optional[str] = None) -> None:
        payload = {"error": error}
        if message:
            payload["message"] = message
        self._send_json(payload, status=int(status))

    def _read_json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        body = self.rfile.read(length)
        if not body:
            return {}
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object.")
        return payload

    def _parse_optional_int(self, raw_value: Optional[str], *, field_name: str) -> Optional[int]:
        if raw_value in (None, ""):
            return None
        try:
            return int(str(raw_value))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be an integer.") from exc

    def _serve_static(self, static_path: str) -> None:
        target = STATIC_DIR / static_path.lstrip("/")
        if not target.exists() or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Static asset not found")
            return
        mime_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_html_shell(self, path: str) -> None:
        view = "runs"
        sample_id = ""
        if path == "/":
            view = "runs"
        elif path in {"/runs", "/flow", "/agency", "/growth", "/failures", "/chat"}:
            view = path.removeprefix("/")
        elif path.startswith("/samples/") and path.endswith("/flow"):
            view = "flow"
            parts = [part for part in path.split("/") if part]
            if len(parts) >= 3:
                sample_id = parts[1]
        elif path.startswith("/samples/"):
            view = "sample"
            sample_id = path.rsplit("/", 1)[-1]

        asset_version = _asset_version()
        html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OpenEmotion Growth Dashboard v1</title>
  <link rel="stylesheet" href="/static/dashboard.css?v={asset_version}">
</head>
<body data-view="{view}" data-sample-id="{sample_id}">
  <div class="background-grid"></div>
  <main class="shell">
    <header class="hero">
      <div>
        <p class="eyebrow" id="hero-eyebrow"></p>
        <h1 id="hero-title"></h1>
        <p class="hero-copy" id="hero-copy"></p>
      </div>
        <div class="hero-side">
        <nav class="nav">
          <a href="/runs" id="nav-runs"></a>
          <a href="/flow" id="nav-flow"></a>
          <a href="/chat" id="nav-chat"></a>
          <a href="/agency" id="nav-agency"></a>
          <a href="/growth" id="nav-growth"></a>
          <a href="/failures" id="nav-failures"></a>
        </nav>
        <div class="locale-switch" id="locale-switch">
          <button type="button" data-locale="zh">中文</button>
          <button type="button" data-locale="en">EN</button>
        </div>
      </div>
    </header>
    <section class="meta-bar" id="meta-bar"></section>
    <section class="content" id="app"></section>
  </main>
  <script src="/static/dashboard_chat_state.js?v={asset_version}"></script>
  <script src="/static/dashboard.js?v={asset_version}"></script>
</body>
</html>"""
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_dashboard_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    dashboard_dir: Path = DASHBOARD_DIR,
    build_kwargs: Optional[Dict[str, Any]] = None,
) -> None:
    store = DashboardDataStore(dashboard_dir=dashboard_dir, build_kwargs=build_kwargs)
    DashboardRequestHandler.store = store
    DashboardRequestHandler.chat_service = DashboardChatService()
    store.ensure_indexes()
    server = ThreadingHTTPServer((host, port), DashboardRequestHandler)
    print(f"Growth Dashboard v1 listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
