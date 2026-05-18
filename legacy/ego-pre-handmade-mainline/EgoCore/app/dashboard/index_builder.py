from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.dashboard.types import (
    AgencyLatestState,
    AgencyRollup,
    AgencyRunRecord,
    ContinuityObservationRecord,
    DashboardBuildSummary,
    FailureIndexRecord,
    FailuresRollup,
    GrowthSignalRecord,
    GrowthRollup,
    RunIndexRecord,
    RunsRollup,
    SemanticSummary,
)

EGO_ROOT = Path(__file__).resolve().parents[3]
REAL_TELEGRAM_DIR = EGO_ROOT / "artifacts" / "telegram_real_mainline_v1" / "real_telegram"
FAILURE_CASES_DIR = EGO_ROOT / "artifacts" / "telegram_real_mainline_v1" / "failure_cases"
DASHBOARD_DIR = EGO_ROOT / "artifacts" / "telegram_real_mainline_v1" / "dashboard_v1"
OBSERVATION_DIR = EGO_ROOT / "artifacts" / "mvs_e5_observation"
VALIDATION_DOC = EGO_ROOT / "docs" / "TELEGRAM_REAL_MAINLINE_VALIDATION_V1.md"

RUNS_FILE = "runs.jsonl"
CONTINUITY_FILE = "continuity_observation.jsonl"
GROWTH_FILE = "growth_signals.jsonl"
FAILURES_FILE = "failures.jsonl"
AGENCY_RUNS_FILE = "agency_runs.jsonl"
AGENCY_ROLLUP_FILE = "agency_rollup.json"
RUNS_ROLLUP_FILE = "runs_rollup.json"
GROWTH_ROLLUP_FILE = "growth_rollup.json"
FAILURES_ROLLUP_FILE = "failures_rollup.json"
GAP_SUMMARY_FILE = "gap_summary.json"
BUILD_META_FILE = "build_meta.json"

REAL_CAPTURE_STATUS_DOC = "REAL_MAINLINE_CAPTURE_STATUS.md"
CONTINUITY_LEDGER_DOC = "CONTINUITY_OBSERVATION_LEDGER.md"
PLASTICITY_REFLECTION_DOC = "PLASTICITY_REFLECTION_EVIDENCE.md"
GAP_SUMMARY_DOC = "GAP_SUMMARY.md"
DATA_SCHEMA_DOC = "DATA_SCHEMA.md"
README_DOC = "README.md"

SAMPLE_ID_RE = re.compile(r"sample_\d{8}_\d{6}_[0-9a-f]{8}")
DASHBOARD_SCHEMA_VERSION = 2

_FIXTURE_SESSION_IDS = {"telegram:dm:456"}
_FIXTURE_CHAT_USER_PAIRS = {(123, 456)}
_FIXTURE_USERNAMES = {"moonlight", "mo*******", "tester"}


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_optional_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    return _load_json(path)


def _load_raw_update(sample_dir: Path, ledger: Dict[str, Any]) -> Dict[str, Any]:
    raw_update = (ledger.get("inputs") or {}).get("raw_update")
    if isinstance(raw_update, dict) and raw_update:
        return raw_update
    return _load_optional_json(sample_dir / "raw_update.json") or {}


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(EGO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _coerce_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y", "on"}:
            return True
        if lowered in {"false", "0", "no", "n", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return None


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _first_defined(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _deep_get(data: Dict[str, Any], *paths: str) -> Any:
    for path in paths:
        current: Any = data
        found = True
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current.get(part)
            else:
                found = False
                break
        if found:
            return current
    return None


def _coerce_int(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _classify_sample_scope(sample_dir: Path, ledger: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    ids = ledger.get("ids") or {}
    for key in ("session_id", "thread_id"):
        value = ids.get(key)
        if value in _FIXTURE_SESSION_IDS:
            return "fixture_like", f"fixture_{key}"

    raw_update = _load_raw_update(sample_dir, ledger)
    message = raw_update.get("message") or {}
    chat_id = _coerce_int(_deep_get(message, "chat.id"))
    user_id = _coerce_int(_deep_get(message, "from.id"))
    username = str(_deep_get(message, "from.username") or "").strip().lower()

    if chat_id is not None and user_id is not None and (chat_id, user_id) in _FIXTURE_CHAT_USER_PAIRS:
        return "fixture_like", "fixture_transport_ids"
    if chat_id is not None and chat_id == 123 and username in _FIXTURE_USERNAMES:
        return "fixture_like", "fixture_transport_username"
    return "real_user", None


def _normalize_action_name(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("action_type", "type", "name"):
            action_type = value.get(key)
            if action_type:
                return str(action_type)
    return "unknown"


def _normalize_action_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_normalize_action_name(item) for item in value]
    return [_normalize_action_name(value)]


def _collapse_focus_goal(value: Any) -> Optional[str]:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        current_focus = value.get("current_focus")
        if current_focus:
            return str(current_focus)
        pending_commitment = value.get("pending_commitment")
        if pending_commitment:
            return str(pending_commitment)
    return None


def _normalize_code_list(values: Iterable[Optional[str]]) -> List[str]:
    deduped: List[str] = []
    for value in values:
        if not value:
            continue
        text = str(value)
        if text not in deduped:
            deduped.append(text)
    return deduped


def _semantic(
    *,
    intent_code: str = "unknown",
    host_posture_code: str = "not_applicable",
    result_state_code: str = "not_executed",
    growth_motion_code: str = "unknown",
    evidence_state_code: str = "partial",
    why_codes: Optional[Iterable[Optional[str]]] = None,
    headline_code: str = "unknown",
) -> SemanticSummary:
    return SemanticSummary(
        intent_code=intent_code,
        host_posture_code=host_posture_code,
        result_state_code=result_state_code,
        growth_motion_code=growth_motion_code,
        evidence_state_code=evidence_state_code,
        why_codes=_normalize_code_list(why_codes or []),
        headline_code=headline_code,
    )


def _freshness_seconds(timestamp: Optional[str]) -> Optional[float]:
    sample_dt = _parse_timestamp(timestamp)
    if sample_dt is None:
        return None
    return max((datetime.now(timezone.utc) - sample_dt).total_seconds(), 0.0)


def _counter_to_dict(values: Iterable[Optional[str]], *, default_label: str = "unknown") -> Dict[str, int]:
    counter: Counter[str] = Counter()
    for value in values:
        counter.update([str(value or default_label)])
    return dict(counter)


def _top_items(counter: Counter[str], *, limit: int = 8) -> List[Dict[str, Any]]:
    return [{"label": label, "count": count} for label, count in counter.most_common(limit)]


def _summarize_evidence_state(
    *,
    bundle_complete: bool = False,
    host_only: bool = False,
    trace_completeness: bool = True,
    gap_types: Optional[List[str]] = None,
    evidence_source: Optional[str] = None,
) -> str:
    gaps = gap_types or []
    if host_only:
        return "host_only"
    if "replay_mismatch" in gaps:
        return "replay_gap"
    if not trace_completeness or "collector_timing_gap" in gaps:
        return "trace_gap"
    if bundle_complete and (evidence_source in {None, "ledger_events", "ledger_trace"}):
        return "complete"
    return "partial"


def _candidate_intent(candidate_actions: List[str], focus_goal: Optional[str], suppression_reason: Optional[str]) -> str:
    joined = " ".join(candidate_actions).lower()
    focus = (focus_goal or "").lower()
    if any(token in joined for token in ("repair", "retry", "fix")) or "repair" in focus:
        return "repair"
    if any(token in joined for token in ("continue", "resume", "follow")) or "continue" in focus:
        return "continue"
    if any(token in joined for token in ("inspect", "browse", "read", "observe", "file")) or any(
        token in focus for token in ("inspect", "observe", "browse", "read", "monitor")
    ):
        return "observe"
    if suppression_reason in {"confirm_pending", "active_task"}:
        return "wait"
    if suppression_reason == "urge_below_threshold":
        return "calm"
    return "unknown"


def _host_posture(governor_status: Optional[str], *, requires_approval: bool, final_host_action: Optional[str], why_codes: Iterable[str]) -> str:
    status = str(governor_status or "").lower()
    reasons = set(why_codes)
    if status in {"blocked", "rejected", "denied"} or "safety_block" in reasons:
        return "blocked"
    if requires_approval or status in {"approval_required", "approval_needed", "needs_approval"}:
        return "approval_needed"
    if final_host_action or status in {"approved", "executed", "exec_result"}:
        return "allowed"
    return "not_applicable"


def _result_state(final_host_action: Optional[str], exec_result_type: Optional[str], writeback_applied: bool) -> str:
    status = str(exec_result_type or "").lower()
    if writeback_applied:
        return "written_back"
    if status in {"success", "ok", "completed"}:
        return "executed_success"
    if status and status not in {"none", "unknown", "null"}:
        return "executed_failure"
    if final_host_action and final_host_action != "none":
        return "executed_success"
    return "not_executed"


def _agency_headline(
    *,
    intent_code: str,
    host_posture_code: str,
    result_state_code: str,
    final_host_action: Optional[str],
    candidate_actions: List[str],
) -> str:
    if result_state_code == "written_back":
        return "changed_after_result"
    if result_state_code == "executed_success" or final_host_action:
        return "action_completed"
    if host_posture_code == "blocked":
        return "blocked_by_host"
    if host_posture_code == "approval_needed":
        return "waiting_for_host"
    if intent_code == "observe":
        return "wants_to_inspect"
    if intent_code == "continue":
        return "trying_to_continue"
    if intent_code == "repair":
        return "trying_to_repair"
    if candidate_actions:
        return "intent_detected"
    if intent_code == "calm":
        return "quiet_state"
    return "waiting_for_signal"


def _run_headline(bundle_complete: bool, host_only: bool, gap_types: List[str], oe_available: bool) -> str:
    if host_only:
        return "host_only_turn"
    if "replay_mismatch" in gap_types:
        return "replay_not_aligned"
    if "collector_timing_gap" in gap_types or "response_plan_missing" in gap_types or "audit_artifact_missing" in gap_types:
        return "evidence_missing"
    if bundle_complete and oe_available:
        return "mainline_connected"
    return "partial_evidence"


def _growth_headline(growth_motion_code: str, reflection_trigger: Optional[str], focus_goal: Optional[str]) -> str:
    if growth_motion_code == "repairing":
        return "repairing_after_failure"
    if growth_motion_code == "focus_shift":
        return "shifting_focus"
    if growth_motion_code == "identity_shift":
        return "identity_shift_detected"
    if growth_motion_code == "reflecting" or reflection_trigger:
        return "reflecting_on_result"
    if focus_goal:
        return "holding_current_focus"
    return "steady_growth"


def _failure_headline(cause_type: str, actual: Optional[str], expected: Optional[str]) -> str:
    haystack = f"{cause_type} {actual or ''} {expected or ''}".lower()
    if "replay" in haystack:
        return "replay_not_aligned"
    if "contract" in haystack or "schema" in haystack:
        return "contract_chain_broken"
    if "bundle" in haystack or "missing" in haystack or "gap" in haystack:
        return "evidence_missing"
    return "runtime_failure_detected"


def _iter_proto_event_payloads(ledger: Dict[str, Any]) -> List[Dict[str, Any]]:
    payloads: List[Dict[str, Any]] = []
    openemotion = ledger.get("openemotion") or {}
    for item in openemotion.get("events") or []:
        payload = item.get("payload")
        if isinstance(payload, dict) and payload.get("subject_profile"):
            payloads.append(payload)
    return payloads


def _select_primary_agency_payload(payloads: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for payload in payloads:
        if payload.get("candidate_actions"):
            return payload
    for payload in payloads:
        if payload.get("subject_profile"):
            return payload
    return None


def _select_feedback_payload(payloads: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for payload in reversed(payloads):
        if payload.get("exec_result") or payload.get("executed_action"):
            return payload
    return None


def _derive_idle_eligible(payload: Dict[str, Any], urge_score: Optional[float], candidate_actions: List[str]) -> bool:
    direct = _coerce_bool(payload.get("idle_eligible"))
    if direct is not None:
        return direct
    perceived = payload.get("perceived") or {}
    event_type = perceived.get("event_type")
    if event_type == "exec_result":
        return False
    if any(
        [
            perceived.get("blocked"),
            perceived.get("active_task"),
            perceived.get("confirm_pending"),
        ]
    ):
        return False
    if candidate_actions:
        return True
    return bool(urge_score and urge_score > 0.0)


def _derive_suppression_reason(
    payload: Dict[str, Any],
    *,
    candidate_generated: bool,
    urge_score: Optional[float],
) -> Optional[str]:
    explicit = payload.get("suppression_reason")
    if explicit:
        return str(explicit)
    if candidate_generated:
        return None
    perceived = payload.get("perceived") or {}
    if perceived.get("event_type") == "exec_result":
        return "exec_result_pass"
    if perceived.get("blocked"):
        return "blocked_by_safety_context"
    if perceived.get("active_task"):
        return "active_task"
    if perceived.get("confirm_pending"):
        return "confirm_pending"
    if not perceived.get("resolved_target_path") and not perceived.get("pending_commitment"):
        return "no_affordance"
    if urge_score is not None and urge_score <= 0.0:
        return "urge_below_threshold"
    return "unknown"


def _pick_agency_candidate_payload(sample_dir: Path, ledger: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], str]:
    payloads = _iter_proto_event_payloads(ledger)
    primary = _select_primary_agency_payload(payloads)
    if primary is not None:
        return primary, "ledger_events"

    trace_payload = (ledger.get("openemotion") or {}).get("trace_payload") or {}
    result_payload = (ledger.get("openemotion") or {}).get("result") or {}
    if trace_payload.get("subject_profile") == "seed_v0_2" or result_payload.get("subject_profile") == "seed_v0_2":
        merged = {}
        merged.update(trace_payload)
        merged.update(result_payload)
        return merged, "ledger_trace"

    sample_payload = _load_optional_json(sample_dir / "sample.json") or {}
    sample_result = sample_payload.get("openemotion_result") or {}
    sample_trace = sample_result.get("trace_payload") or sample_payload.get("openemotion_trace") or {}
    if sample_trace.get("subject_profile") == "seed_v0_2" or sample_result.get("subject_profile") == "seed_v0_2":
        merged = {}
        merged.update(sample_trace)
        merged.update(sample_result)
        return merged, "sample_mirror"

    return None, "missing"


def _build_agency_record(
    sample_dir: Path,
    run_record: RunIndexRecord,
) -> Tuple[Optional[AgencyRunRecord], Optional[str]]:
    if run_record.host_only:
        return None, "host_only"
    if not run_record.oe_available:
        return None, "oe_unavailable"

    ledger = _load_optional_json(sample_dir / "ledger.json") or {}
    primary_payload, evidence_source = _pick_agency_candidate_payload(sample_dir, ledger)
    if primary_payload is None:
        return None, "missing_agency_trace"

    subject_profile = primary_payload.get("subject_profile") or "unknown"
    if subject_profile != "seed_v0_2":
        return None, "non_seed_profile"

    feedback_payload = _select_feedback_payload(_iter_proto_event_payloads(ledger)) or primary_payload
    policy_hint = primary_payload.get("policy_hint") or {}
    governor_hint = feedback_payload.get("governor_hint") or primary_payload.get("governor_hint") or {}
    candidate_actions = _normalize_action_list(primary_payload.get("candidate_actions"))
    top_candidate_urge = None
    raw_candidates = primary_payload.get("candidate_actions")
    if isinstance(raw_candidates, list) and raw_candidates:
        top_candidate_urge = raw_candidates[0].get("urge_score")
    urge_score = _coerce_float(
        _first_defined(
            primary_payload.get("urge_score"),
            _deep_get(policy_hint, "urge_score"),
            _deep_get(primary_payload, "top_candidate_action.urge_score"),
            top_candidate_urge,
        )
    )
    candidate_generated = _coerce_bool(primary_payload.get("candidate_generated"))
    candidate_generated = bool(candidate_actions) if candidate_generated is None else candidate_generated
    idle_check = bool(_coerce_bool(primary_payload.get("idle_check")))
    idle_eligible = _derive_idle_eligible(primary_payload, urge_score, candidate_actions)
    suppression_reason = _derive_suppression_reason(
        feedback_payload or primary_payload,
        candidate_generated=candidate_generated,
        urge_score=urge_score,
    )
    selected_action = governor_hint.get("selected_action") or {}
    executed_action = feedback_payload.get("executed_action") or {}
    exec_result = feedback_payload.get("exec_result") or {}
    seed_state_snapshot = feedback_payload.get("seed_state_snapshot") or primary_payload.get("seed_state_snapshot") or {}
    focus_goal = _collapse_focus_goal(seed_state_snapshot.get("focus_goal"))
    identity_light_hash = (
        primary_payload.get("identity_light_hash")
        or _deep_get(primary_payload, "seed_state_snapshot.identity_light_hash")
        or _deep_get(primary_payload, "legacy_trace_payload.identity_light_hash")
        or "unknown"
    )
    final_host_action = _normalize_action_name(executed_action) if executed_action else _normalize_action_name(selected_action) if selected_action else None
    exec_result_type = (
        exec_result.get("status")
        or exec_result.get("result_type")
        or exec_result.get("outcome_type")
        or ("none" if not exec_result else "unknown")
    )
    direct_execution_violation = bool(_coerce_bool(primary_payload.get("direct_execution_violation")))
    trace_completeness = bool(
        _coerce_bool(primary_payload.get("trace_completeness"))
        if primary_payload.get("trace_completeness") is not None
        else subject_profile
        and governor_hint.get("status")
        and seed_state_snapshot
    )
    why_codes = _normalize_code_list(
        [
            suppression_reason,
            "approval_required" if (
                policy_hint.get("requires_approval")
                or governor_hint.get("requires_approval")
                or selected_action.get("requires_approval")
            ) else None,
            "safety_block" if suppression_reason == "blocked_by_safety_context" else None,
        ]
    )
    intent_code = _candidate_intent(candidate_actions, focus_goal, suppression_reason)
    host_posture_code = _host_posture(
        governor_hint.get("status"),
        requires_approval=bool(
            policy_hint.get("requires_approval")
            or governor_hint.get("requires_approval")
            or selected_action.get("requires_approval")
        ),
        final_host_action=final_host_action,
        why_codes=why_codes,
    )
    result_state_code = _result_state(final_host_action, str(exec_result_type) if exec_result_type is not None else None, bool(exec_result) and bool(seed_state_snapshot))
    growth_motion_code = "repairing" if any(action.startswith("repair") for action in candidate_actions) else "steady" if bool(seed_state_snapshot) else "unknown"
    evidence_state_code = _summarize_evidence_state(
        bundle_complete=run_record.bundle_complete,
        trace_completeness=trace_completeness,
        gap_types=run_record.gap_types,
        evidence_source=evidence_source,
    )

    record = AgencyRunRecord(
        sample_id=run_record.sample_id,
        timestamp=run_record.timestamp,
        session_id=run_record.session_id,
        subject_profile=subject_profile,
        idle_check=idle_check,
        idle_eligible=idle_eligible,
        urge_score=urge_score,
        candidate_generated=candidate_generated,
        candidate_actions=candidate_actions,
        suppression_reason=suppression_reason,
        governor_status=governor_hint.get("status"),
        requires_approval=bool(
            policy_hint.get("requires_approval")
            or governor_hint.get("requires_approval")
            or selected_action.get("requires_approval")
        ),
        final_host_action=final_host_action,
        exec_result_type=str(exec_result_type) if exec_result_type is not None else None,
        writeback_applied=bool(exec_result) and bool(seed_state_snapshot),
        focus_goal=focus_goal,
        identity_light_hash=identity_light_hash,
        revision_counter=int(seed_state_snapshot.get("revision_counter") or 0),
        trace_completeness=trace_completeness,
        evidence_source=evidence_source,
        direct_execution_violation=direct_execution_violation,
        semantic=_semantic(
            intent_code=intent_code,
            host_posture_code=host_posture_code,
            result_state_code=result_state_code,
            growth_motion_code=growth_motion_code,
            evidence_state_code=evidence_state_code,
            why_codes=why_codes,
            headline_code=_agency_headline(
                intent_code=intent_code,
                host_posture_code=host_posture_code,
                result_state_code=result_state_code,
                final_host_action=final_host_action,
                candidate_actions=candidate_actions,
            ),
        ),
    )
    return record, None


def _build_agency_rollup(
    records: List[AgencyRunRecord],
    *,
    excluded_counts: Dict[str, int],
) -> AgencyRollup:
    generated_at = datetime.now(timezone.utc).isoformat()
    if not records:
        return AgencyRollup(
            generated_at=generated_at,
            last_sample_timestamp=None,
            freshness_seconds=None,
            profile_scope=["seed_v0_2"],
            summary={
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
            latest_state=None,
            funnel={
                "idle_eligible_count": 0,
                "candidate_generated_count": 0,
                "governor_approved_count": 0,
                "host_action_count": 0,
                "writeback_count": 0,
            },
            trends=[],
            distributions={
                "candidate_actions": {},
                "governor_status": {},
                "final_host_action": {},
                "suppression_reason": {},
            },
            recent_turns=[],
            excluded_counts=excluded_counts,
            semantic_summary={
                "intent": {},
                "host_posture": {},
                "result_state": {},
                "growth_motion": {},
                "evidence_state": {},
                "headline": {},
            },
            headline_code="unknown",
            story_cards=[],
        )

    ordered = sorted(records, key=lambda item: item.timestamp)
    latest = ordered[-1]
    urge_values = [item.urge_score for item in ordered if item.urge_score is not None]
    identity_switch_count = sum(
        1
        for previous, current in zip(ordered, ordered[1:])
        if previous.identity_light_hash != current.identity_light_hash
    )
    focus_change_count = sum(
        1
        for previous, current in zip(ordered, ordered[1:])
        if previous.focus_goal != current.focus_goal
    )
    governor_counter: Counter[str] = Counter()
    final_action_counter: Counter[str] = Counter()
    suppression_counter: Counter[str] = Counter()
    candidate_counter: Counter[str] = Counter()
    for item in ordered:
        governor_counter.update([item.governor_status or "unknown"])
        final_action_counter.update([item.final_host_action or "none"])
        suppression_counter.update([item.suppression_reason or "none"])
        candidate_counter.update(item.candidate_actions or ["none"])

    last_sample_dt = _parse_timestamp(latest.timestamp)
    freshness_seconds = None
    if last_sample_dt is not None:
        freshness_seconds = max((datetime.now(timezone.utc) - last_sample_dt).total_seconds(), 0.0)

    semantic_summary = {
        "intent": _counter_to_dict((item.semantic.intent_code if item.semantic else "unknown" for item in ordered)),
        "host_posture": _counter_to_dict((item.semantic.host_posture_code if item.semantic else "not_applicable" for item in ordered)),
        "result_state": _counter_to_dict((item.semantic.result_state_code if item.semantic else "not_executed" for item in ordered)),
        "growth_motion": _counter_to_dict((item.semantic.growth_motion_code if item.semantic else "unknown" for item in ordered)),
        "evidence_state": _counter_to_dict((item.semantic.evidence_state_code if item.semantic else "partial" for item in ordered)),
        "headline": _counter_to_dict((item.semantic.headline_code if item.semantic else "unknown" for item in ordered)),
    }

    return AgencyRollup(
        generated_at=generated_at,
        last_sample_timestamp=latest.timestamp,
        freshness_seconds=freshness_seconds,
        profile_scope=sorted({item.subject_profile for item in ordered}),
        summary={
            "turn_count": len(ordered),
            "idle_check_count": sum(1 for item in ordered if item.idle_check),
            "idle_eligible_rate": sum(1 for item in ordered if item.idle_eligible) / len(ordered),
            "candidate_generated_rate": sum(1 for item in ordered if item.candidate_generated) / len(ordered),
            "exec_result_writeback_rate": sum(1 for item in ordered if item.writeback_applied) / len(ordered),
            "trace_completeness_rate": sum(1 for item in ordered if item.trace_completeness) / len(ordered),
            "direct_execution_violations": sum(1 for item in ordered if item.direct_execution_violation),
            "mean_urge": round(sum(urge_values) / len(urge_values), 4) if urge_values else None,
            "identity_switch_count": identity_switch_count,
            "focus_change_count": focus_change_count,
        },
        latest_state=AgencyLatestState(
            sample_id=latest.sample_id,
            timestamp=latest.timestamp,
            subject_profile=latest.subject_profile,
            session_id=latest.session_id,
            focus_goal=latest.focus_goal,
            urge_score=latest.urge_score,
            candidate_actions=latest.candidate_actions,
            governor_status=latest.governor_status,
            final_host_action=latest.final_host_action,
            exec_result_type=latest.exec_result_type,
            writeback_applied=latest.writeback_applied,
            revision_counter=latest.revision_counter,
            trace_completeness=latest.trace_completeness,
            semantic=latest.semantic,
        ),
        funnel={
            "idle_eligible_count": sum(1 for item in ordered if item.idle_eligible),
            "candidate_generated_count": sum(1 for item in ordered if item.candidate_generated),
            "governor_approved_count": sum(1 for item in ordered if item.governor_status == "approved"),
            "host_action_count": sum(1 for item in ordered if item.final_host_action and item.final_host_action != "none"),
            "writeback_count": sum(1 for item in ordered if item.writeback_applied),
        },
        trends=[
            {
                "sample_id": item.sample_id,
                "timestamp": item.timestamp,
                "urge_score": item.urge_score,
                "idle_eligible": item.idle_eligible,
                "candidate_generated": item.candidate_generated,
                "writeback_applied": item.writeback_applied,
                "revision_counter": item.revision_counter,
            }
            for item in ordered[-50:]
        ],
        distributions={
            "candidate_actions": dict(candidate_counter),
            "governor_status": dict(governor_counter),
            "final_host_action": dict(final_action_counter),
            "suppression_reason": dict(suppression_counter),
        },
        recent_turns=[
            {
                "sample_id": item.sample_id,
                "timestamp": item.timestamp,
                "urge_score": item.urge_score,
                "candidate_actions": item.candidate_actions,
                "governor_status": item.governor_status,
                "final_host_action": item.final_host_action,
                "exec_result_type": item.exec_result_type,
                "focus_goal": item.focus_goal,
                "trace_completeness": item.trace_completeness,
                "semantic": item.semantic.to_dict() if item.semantic else None,
            }
            for item in reversed(ordered[-12:])
        ],
        excluded_counts=excluded_counts,
        semantic_summary=semantic_summary,
        headline_code=latest.semantic.headline_code if latest.semantic else "unknown",
        story_cards=[
            {
                "slot": "intent",
                "code": latest.semantic.intent_code if latest.semantic else "unknown",
                "value": latest.candidate_actions,
            },
            {
                "slot": "host",
                "code": latest.semantic.host_posture_code if latest.semantic else "not_applicable",
                "value": latest.governor_status,
            },
            {
                "slot": "result",
                "code": latest.semantic.result_state_code if latest.semantic else "not_executed",
                "value": latest.exec_result_type,
            },
            {
                "slot": "growth",
                "code": latest.semantic.growth_motion_code if latest.semantic else "unknown",
                "value": latest.revision_counter,
            },
        ],
    )


def _build_runs_rollup(
    run_records: List[RunIndexRecord],
    continuity_records: List[ContinuityObservationRecord],
) -> RunsRollup:
    generated_at = datetime.now(timezone.utc).isoformat()
    latest = run_records[-1] if run_records else None
    gap_counter: Counter[str] = Counter()
    for item in run_records:
        gap_counter.update(item.gap_types)

    return RunsRollup(
        generated_at=generated_at,
        last_sample_timestamp=latest.timestamp if latest else None,
        freshness_seconds=_freshness_seconds(latest.timestamp if latest else None),
        headline_code=latest.semantic.headline_code if latest and latest.semantic else "unknown",
        summary={
            "turn_count": len(run_records),
            "complete_bundle_count": sum(1 for item in run_records if item.bundle_complete),
            "complete_bundle_rate": (sum(1 for item in run_records if item.bundle_complete) / len(run_records)) if run_records else 0.0,
            "oe_available_rate": (sum(1 for item in run_records if item.oe_available) / len(run_records)) if run_records else 0.0,
            "host_only_rate": (sum(1 for item in run_records if item.host_only) / len(run_records)) if run_records else 0.0,
            "latest_bundle_complete": bool(latest.bundle_complete) if latest else False,
            "latest_oe_available": bool(latest.oe_available) if latest else False,
        },
        charts={
            "bundle_trend": [
                {
                    "sample_id": item.sample_id,
                    "timestamp": item.timestamp,
                    "bundle_complete": item.bundle_complete,
                    "oe_available": item.oe_available,
                    "host_only": item.host_only,
                    "gap_count": len(item.gap_types),
                    "semantic": item.semantic.to_dict() if item.semantic else None,
                }
                for item in run_records[-50:]
            ],
            "oe_state_distribution": {
                "complete": sum(1 for item in run_records if item.bundle_complete),
                "partial": sum(1 for item in run_records if not item.bundle_complete and not item.host_only),
                "host_only": sum(1 for item in run_records if item.host_only),
            },
            "gap_type_distribution": dict(gap_counter),
            "continuity_status": {item.scenario: item.status for item in continuity_records},
        },
        continuity=[item.to_dict() for item in continuity_records],
        recent_runs=[
            {
                "sample_id": item.sample_id,
                "timestamp": item.timestamp,
                "bundle_complete": item.bundle_complete,
                "oe_available": item.oe_available,
                "host_only": item.host_only,
                "gap_types": item.gap_types,
                "semantic": item.semantic.to_dict() if item.semantic else None,
            }
            for item in reversed(run_records[-12:])
        ],
        records=[item.to_dict() for item in run_records],
        semantic_summary={
            "headline": _counter_to_dict((item.semantic.headline_code if item.semantic else "unknown" for item in run_records)),
            "evidence_state": _counter_to_dict((item.semantic.evidence_state_code if item.semantic else "partial" for item in run_records)),
        },
    )


def _build_growth_rollup(growth_records: List[GrowthSignalRecord]) -> GrowthRollup:
    generated_at = datetime.now(timezone.utc).isoformat()
    latest = growth_records[-1] if growth_records else None
    reflection_counter: Counter[str] = Counter()
    motion_counter: Counter[str] = Counter()
    focus_seen = [item.focus_goal for item in growth_records if item.focus_goal]
    component_totals: Counter[str] = Counter()
    component_counts: Counter[str] = Counter()
    for item in growth_records:
        reflection_counter.update([item.reflection_summary.get("trigger") or "none"])
        motion_counter.update([item.semantic.growth_motion_code if item.semantic else "unknown"])
        for key, value in (item.appraisal_delta_summary or {}).items():
            number = _coerce_float(value)
            if number is None:
                continue
            component_totals.update({key: number})
            component_counts.update({key: 1})

    appraisal_means = {
        key: round(component_totals[key] / component_counts[key], 4)
        for key in component_totals
        if component_counts[key]
    }

    return GrowthRollup(
        generated_at=generated_at,
        last_sample_timestamp=latest.timestamp if latest else None,
        freshness_seconds=_freshness_seconds(latest.timestamp if latest else None),
        headline_code=latest.semantic.headline_code if latest and latest.semantic else "unknown",
        summary={
            "total_records": len(growth_records),
            "reflecting_count": sum(1 for item in growth_records if (item.semantic and item.semantic.growth_motion_code == "reflecting")),
            "repairing_count": sum(1 for item in growth_records if (item.semantic and item.semantic.growth_motion_code == "repairing")),
            "focus_shift_count": sum(1 for item in growth_records if (item.semantic and item.semantic.growth_motion_code == "focus_shift")),
            "identity_shift_count": sum(1 for item in growth_records if (item.semantic and item.semantic.growth_motion_code == "identity_shift")),
            "latest_revision_counter": latest.revision_counter if latest else 0,
        },
        charts={
            "revision_trend": [
                {
                    "sample_id": item.sample_id,
                    "timestamp": item.timestamp,
                    "revision_counter": item.revision_counter,
                    "growth_motion_code": item.semantic.growth_motion_code if item.semantic else "unknown",
                }
                for item in growth_records[-50:]
            ],
            "appraisal_component_means": appraisal_means,
            "reflection_trigger_distribution": dict(reflection_counter),
            "growth_motion_distribution": dict(motion_counter),
            "focus_timeline": [
                {
                    "sample_id": item.sample_id,
                    "timestamp": item.timestamp,
                    "focus_goal": item.focus_goal or "none",
                }
                for item in growth_records[-50:]
                if item.focus_goal
            ],
        },
        recent_growth=[
            {
                "sample_id": item.sample_id,
                "timestamp": item.timestamp,
                "focus_goal": item.focus_goal,
                "revision_counter": item.revision_counter,
                "reflection_trigger": item.reflection_summary.get("trigger"),
                "semantic": item.semantic.to_dict() if item.semantic else None,
            }
            for item in reversed(growth_records[-12:])
        ],
        records=[item.to_dict() for item in growth_records],
        semantic_summary={
            "headline": _counter_to_dict((item.semantic.headline_code if item.semantic else "unknown" for item in growth_records)),
            "growth_motion": _counter_to_dict((item.semantic.growth_motion_code if item.semantic else "unknown" for item in growth_records)),
            "focus": _counter_to_dict(focus_seen, default_label="none"),
        },
    )


def _build_failures_rollup(
    failure_records: List[FailureIndexRecord],
    gap_summary: Dict[str, Any],
) -> FailuresRollup:
    generated_at = datetime.now(timezone.utc).isoformat()
    latest = failure_records[-1] if failure_records else None
    cause_counter = Counter(item.cause_type for item in failure_records)
    severity_counter = Counter(item.severity for item in failure_records)
    retested_counter = Counter("retested" if item.retested_after_fix else "open" for item in failure_records)

    return FailuresRollup(
        generated_at=generated_at,
        last_sample_timestamp=latest.timestamp if latest else None,
        freshness_seconds=_freshness_seconds(latest.timestamp if latest else None),
        headline_code=latest.semantic.headline_code if latest and latest.semantic else "unknown",
        summary={
            "total_failures": len(failure_records),
            "unresolved_count": sum(1 for item in failure_records if not item.retested_after_fix),
            "retested_rate": (sum(1 for item in failure_records if item.retested_after_fix) / len(failure_records)) if failure_records else 0.0,
            "top_cause": cause_counter.most_common(1)[0][0] if cause_counter else "none",
            "replay_mismatch_count": int((gap_summary.get("gap_type_counts") or {}).get("replay_mismatch", 0)),
        },
        charts={
            "cause_distribution": dict(cause_counter),
            "severity_distribution": dict(severity_counter),
            "retested_distribution": dict(retested_counter),
            "top_blockers": _top_items(Counter(gap_summary.get("top_blockers") or []), limit=5),
        },
        recent_failures=[
            {
                "failure_id": item.failure_id,
                "timestamp": item.timestamp,
                "cause_type": item.cause_type,
                "severity": item.severity,
                "retested_after_fix": item.retested_after_fix,
                "semantic": item.semantic.to_dict() if item.semantic else None,
                "artifact_ref": item.artifact_ref,
            }
            for item in reversed(failure_records[-12:])
        ],
        records=[item.to_dict() for item in failure_records],
        semantic_summary={
            "headline": _counter_to_dict((item.semantic.headline_code if item.semantic else "unknown" for item in failure_records)),
            "severity": dict(severity_counter),
        },
        gap_summary=gap_summary,
    )


def _iter_sample_dirs(real_dir: Path) -> List[Path]:
    if not real_dir.exists():
        return []
    return sorted(
        path for path in real_dir.iterdir() if path.is_dir() and path.name.startswith("sample_")
    )


def _artifact_refs(sample_dir: Path) -> Dict[str, str]:
    refs: Dict[str, str] = {"sample_dir": _rel(sample_dir)}
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
        if path.exists():
            refs[name.replace(".json", "").replace(".md", "")] = _rel(path)
    return refs


def _derive_completeness(sample_dir: Path, ledger: Dict[str, Any]) -> Dict[str, bool]:
    completeness = dict((ledger.get("evidence_completeness") or {}))
    for name in [
        "raw_update",
        "normalized_event",
        "openemotion_result",
        "openemotion_trace",
        "response_plan",
        "outbox_record",
        "timeline",
        "tape",
        "replay",
    ]:
        completeness.setdefault(name, (sample_dir / f"{name}.json").exists())
    return completeness


def _is_oe_available(ledger: Dict[str, Any], completeness: Dict[str, bool]) -> bool:
    openemotion = ledger.get("openemotion") or {}
    result_payload = openemotion.get("result") or {}
    trace_payload = openemotion.get("trace_payload") or {}
    return bool(result_payload) or bool(trace_payload) or (
        completeness.get("openemotion_result", False) and completeness.get("openemotion_trace", False)
    )


def _classify_gap_types(
    completeness: Dict[str, bool],
    *,
    host_only: bool,
    response_plan: Dict[str, Any],
    replay_payload: Dict[str, Any],
    ledger_payload: Dict[str, Any],
) -> List[str]:
    gap_types: List[str] = []
    host_only_gap = _classify_host_only_gap(response_plan) if host_only else None

    if host_only:
        gap_types.append(host_only_gap)

    if not completeness.get("raw_update", False):
        gap_types.append("raw_update_missing")

    if not completeness.get("normalized_event", False):
        gap_types.append("collector_timing_gap" if not host_only else host_only_gap)

    if not completeness.get("openemotion_result", False):
        gap_types.append("collector_timing_gap" if not host_only else host_only_gap)

    if not completeness.get("openemotion_trace", False):
        gap_types.append("collector_timing_gap" if not host_only else host_only_gap)

    if not completeness.get("response_plan", False):
        gap_types.append("response_plan_missing")

    if not completeness.get("outbox_record", False):
        gap_types.append("send_record_missing")

    if not completeness.get("timeline", False) or not completeness.get("tape", False):
        gap_types.append("audit_artifact_missing")

    if not completeness.get("replay", False):
        gap_types.append("replay_missing")

    if replay_payload:
        if replay_payload.get("primary_ledger_ref") not in (None, "ledger.json"):
            gap_types.append("replay_mismatch")
        if replay_payload.get("sample_id") not in (None, ledger_payload.get("sample_id")):
            gap_types.append("replay_mismatch")
        if (
            replay_payload.get("replay_hash")
            and ledger_payload.get("replay_hash")
            and replay_payload.get("replay_hash") != ledger_payload.get("replay_hash")
        ):
            gap_types.append("replay_mismatch")

    deduped: List[str] = []
    for item in gap_types:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _classify_host_only_gap(response_plan: Dict[str, Any]) -> str:
    status = str((response_plan or {}).get("status") or "").lower()
    authority_source = str((response_plan or {}).get("authority_source") or "").lower()
    if authority_source == "profile_memory":
        return "control_plane_host_only"
    if status in {"profile_rule_registered", "profile_rule_enforced", "profile_rule_unsupported", "command_result"}:
        return "control_plane_host_only"
    return "unexpected_pre_runtime_intercept"


def _build_run_record(sample_dir: Path) -> RunIndexRecord:
    ledger = _load_optional_json(sample_dir / "ledger.json") or {}
    ids = ledger.get("ids") or {}
    openemotion = ledger.get("openemotion") or {}
    host = ledger.get("host") or {}
    response_plan = host.get("response_plan") or {}
    trace_payload = openemotion.get("trace_payload") or {}
    cycle_delta = trace_payload.get("cycle_delta") or {}
    replay_payload = _load_optional_json(sample_dir / "replay.json") or {}

    completeness = _derive_completeness(sample_dir, ledger)
    oe_available = _is_oe_available(ledger, completeness)
    host_only = bool(response_plan) and not oe_available
    sample_scope, sample_scope_reason = _classify_sample_scope(sample_dir, ledger)
    gap_types = _classify_gap_types(
        completeness,
        host_only=host_only,
        response_plan=response_plan,
        replay_payload=replay_payload,
        ledger_payload=ledger,
    )

    return RunIndexRecord(
        sample_id=ledger.get("sample_id") or sample_dir.name,
        timestamp=ledger.get("timestamp") or "",
        bundle_complete=all(completeness.values()) and not host_only,
        gap_types=gap_types,
        oe_available=oe_available,
        host_only=host_only,
        continuity_tags=[],
        repair_closure=bool(cycle_delta.get("repair_closure")),
        artifact_refs=_artifact_refs(sample_dir),
        source_type=ledger.get("source_type"),
        sample_scope=sample_scope,
        sample_scope_reason=sample_scope_reason,
        response_plan_status=response_plan.get("status"),
        closure_family_id=cycle_delta.get("closure_family_id"),
        session_id=ids.get("session_id"),
        thread_id=ids.get("thread_id"),
        outcome_signature=cycle_delta.get("outcome_signature"),
        reflection_trigger=trace_payload.get("reflection_trigger"),
    )


def _build_growth_record(sample_dir: Path, run_record: RunIndexRecord) -> Optional[GrowthSignalRecord]:
    ledger = _load_optional_json(sample_dir / "ledger.json") or {}
    openemotion = ledger.get("openemotion") or {}
    result_payload = openemotion.get("result") or {}
    trace_payload = openemotion.get("trace_payload") or {}

    if not result_payload or not trace_payload:
        return None

    cycle_delta = trace_payload.get("cycle_delta") or {}
    reflection_note = result_payload.get("reflection_note") or {}
    seed_state_snapshot = trace_payload.get("seed_state_snapshot") or {}
    return GrowthSignalRecord(
        sample_id=run_record.sample_id,
        timestamp=run_record.timestamp,
        memory_update_summary=result_payload.get("memory_update") or {},
        appraisal_delta_summary=result_payload.get("appraisal_state_delta") or {},
        reflection_summary={
            "trigger": reflection_note.get("trigger"),
            "promote_to_memory": reflection_note.get("promote_to_memory"),
            "diagnosis": reflection_note.get("diagnosis"),
            "proposed_adjustment": reflection_note.get("proposed_adjustment") or {},
        },
        response_tendency_summary=result_payload.get("response_tendency") or {},
        cycle_summary={
            "cycle_id": cycle_delta.get("cycle_id"),
            "closure_family_id": cycle_delta.get("closure_family_id"),
            "action_signature": cycle_delta.get("action_signature"),
            "outcome_signature": cycle_delta.get("outcome_signature"),
            "op": cycle_delta.get("op"),
            "repair_closure": cycle_delta.get("repair_closure"),
            "closure_consistency_score": cycle_delta.get("closure_consistency_score"),
            "reflection_trigger": trace_payload.get("reflection_trigger"),
        },
        session_id=run_record.session_id,
        thread_id=run_record.thread_id,
        closure_family_id=run_record.closure_family_id,
        focus_goal=_collapse_focus_goal(seed_state_snapshot.get("focus_goal")),
        revision_counter=int(seed_state_snapshot.get("revision_counter") or 0),
        identity_light_hash=trace_payload.get("identity_light_hash") or seed_state_snapshot.get("identity_light_hash"),
    )


def _failure_severity(cause_type: str) -> str:
    if cause_type in {"boundary_error", "authority_error", "e2e_broken"}:
        return "high"
    if cause_type in {"runtime_error", "schema_error"}:
        return "medium"
    return "low"


def _build_failure_records(failure_dir: Path = FAILURE_CASES_DIR) -> List[FailureIndexRecord]:
    if not failure_dir.exists():
        return []

    records: List[FailureIndexRecord] = []
    for path in sorted(failure_dir.glob("failure_*.json")):
        payload = _load_optional_json(path) or {}
        cause_type = payload.get("initial_cause_type") or "unknown"
        records.append(
            FailureIndexRecord(
                failure_id=payload.get("failure_id") or path.stem,
                timestamp=payload.get("timestamp") or "",
                cause_type=cause_type,
                severity=_failure_severity(cause_type),
                source="failure_case",
                artifact_ref=_rel(path),
                in_regression=bool(payload.get("in_regression")),
                retested_after_fix=bool(payload.get("retested_after_fix")),
                expected=payload.get("expected"),
                actual=payload.get("actual"),
            )
        )
    return records


def _attach_run_semantics(run_records: List[RunIndexRecord]) -> None:
    for record in run_records:
        why_codes = list(record.gap_types)
        if record.host_only:
            why_codes.append("host_only")
        evidence_state = _summarize_evidence_state(
            bundle_complete=record.bundle_complete,
            host_only=record.host_only,
            gap_types=record.gap_types,
        )
        record.semantic = _semantic(
            intent_code="wait" if record.host_only else "unknown",
            host_posture_code="not_applicable",
            result_state_code="executed_success" if record.response_plan_status == "complete" else "not_executed",
            growth_motion_code="unknown",
            evidence_state_code=evidence_state,
            why_codes=why_codes,
            headline_code=_run_headline(record.bundle_complete, record.host_only, record.gap_types, record.oe_available),
        )


def _attach_growth_semantics(growth_records: List[GrowthSignalRecord]) -> None:
    ordered = sorted(growth_records, key=lambda item: item.timestamp)
    previous_focus: Optional[str] = None
    previous_identity: Optional[str] = None
    previous_revision: Optional[int] = None
    for record in ordered:
        reflection_trigger = record.reflection_summary.get("trigger")
        repair_closure = bool(record.cycle_summary.get("repair_closure"))
        focus_shift = bool(previous_focus and record.focus_goal and previous_focus != record.focus_goal)
        identity_shift = bool(previous_identity and record.identity_light_hash and previous_identity != record.identity_light_hash)
        revision_delta = max(record.revision_counter - (previous_revision or 0), 0)

        if repair_closure:
            growth_motion_code = "repairing"
        elif identity_shift:
            growth_motion_code = "identity_shift"
        elif focus_shift:
            growth_motion_code = "focus_shift"
        elif reflection_trigger:
            growth_motion_code = "reflecting"
        else:
            growth_motion_code = "steady"

        intent_code = "repair" if repair_closure else "continue" if reflection_trigger else "observe"
        why_codes = [reflection_trigger]
        if focus_shift:
            why_codes.append("focus_change")
        if identity_shift:
            why_codes.append("identity_shift")
        if revision_delta == 0:
            why_codes.append("no_revision_delta")

        record.semantic = _semantic(
            intent_code=intent_code,
            host_posture_code="not_applicable",
            result_state_code="written_back" if record.revision_counter else "not_executed",
            growth_motion_code=growth_motion_code,
            evidence_state_code="complete",
            why_codes=why_codes,
            headline_code=_growth_headline(growth_motion_code, reflection_trigger, record.focus_goal),
        )

        previous_focus = record.focus_goal or previous_focus
        previous_identity = record.identity_light_hash or previous_identity
        previous_revision = record.revision_counter


def _attach_failure_semantics(failure_records: List[FailureIndexRecord]) -> None:
    for record in failure_records:
        evidence_state = "replay_gap" if "replay" in record.cause_type else "partial"
        why_codes = [record.cause_type]
        if not record.retested_after_fix:
            why_codes.append("retest_pending")
        if record.in_regression:
            why_codes.append("in_regression")
        record.semantic = _semantic(
            intent_code="repair",
            host_posture_code="blocked",
            result_state_code="executed_failure",
            growth_motion_code="unknown",
            evidence_state_code=evidence_state,
            why_codes=why_codes,
            headline_code=_failure_headline(record.cause_type, record.actual, record.expected),
        )


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _section_sample_ids(text: str, heading_predicate) -> List[str]:
    sample_ids: List[str] = []
    current_heading = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            current_heading = stripped.lstrip("#").strip()
            continue
        if heading_predicate(current_heading):
            sample_ids.extend(SAMPLE_ID_RE.findall(stripped))
    deduped: List[str] = []
    for sample_id in sample_ids:
        if sample_id not in deduped:
            deduped.append(sample_id)
    return deduped


def _restart_external_refs(report_text: str) -> List[str]:
    refs: List[str] = []
    for line in report_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("-") and "restart_egocore.sh --telegram" in stripped:
            refs.append(line.strip("- ").strip())
    return refs


def _build_continuity_records(observation_dir: Path = OBSERVATION_DIR) -> List[ContinuityObservationRecord]:
    sample_index_text = _read_text(observation_dir / "OBSERVATION_SAMPLE_INDEX.md")
    report_text = _read_text(observation_dir / "MVS_E5_OBSERVATION_REPORT.md")

    new_sample_ids = _section_sample_ids(
        sample_index_text,
        lambda heading: "/new" in heading,
    )
    restart_sample_ids = _section_sample_ids(
        sample_index_text,
        lambda heading: "restart continuity" in heading.lower(),
    )
    restore_sample_ids = _section_sample_ids(
        sample_index_text,
        lambda heading: "restore continuity" in heading.lower(),
    )
    restart_refs = _restart_external_refs(report_text)

    return [
        ContinuityObservationRecord(
            scenario="new",
            status="direct_real" if new_sample_ids else "missing",
            sample_ids=new_sample_ids,
            external_evidence_refs=[],
            proof_summary="多次 `/new` 直接真实样本、完整 continuity probe、显式默认规则在 `/new` 后继续命中。",
            not_proved_summary="不证明 `restore continuity`、E5 稳定成立、Developmental Self 准入通过。",
            blocker="`/new` 已成立；当前 continuity 主 blocker 已切到 `restore` 与 evidence gap。",
        ),
        ContinuityObservationRecord(
            scenario="restart",
            status="cross_evidence" if restart_sample_ids else "missing",
            sample_ids=restart_sample_ids,
            external_evidence_refs=restart_refs,
            proof_summary="真实重启日志与 post-restart 命中样本已形成跨证据链正证据。",
            not_proved_summary="仍不等于 post-restart 命中样本已成为完整单样本 E4 bundle。",
            blocker="post-restart 命中样本仍非完整单样本 E4 bundle。",
        ),
        ContinuityObservationRecord(
            scenario="restore",
            status="direct_real" if restore_sample_ids else "missing",
            sample_ids=restore_sample_ids,
            external_evidence_refs=[],
            proof_summary=(
                "显式 restore 后，首条真实用户消息已形成完整 E4 bundle，随后 continuity probe 再次命中既有默认规则。"
                if restore_sample_ids
                else "当前没有直接真实 `restore` 样本。"
            ),
            not_proved_summary=(
                "不证明 E5 稳定成立，也不等于更长窗口下 continuity 已稳定。"
                if restore_sample_ids
                else "不能证明 `restore continuity` 已成立。"
            ),
            blocker=(
                "restore 首次正式补证已完成；当前更高优先级 blocker 已切到 post-restart 样本完整度与 evidence gap。"
                if restore_sample_ids
                else "`restore` 仍是 continuity 的最高优先级缺口。"
            ),
        ),
    ]


def _attach_continuity_tags(
    run_records: List[RunIndexRecord],
    continuity_records: List[ContinuityObservationRecord],
) -> None:
    tag_map: Dict[str, List[str]] = defaultdict(list)
    for record in continuity_records:
        for sample_id in record.sample_ids:
            tag_map[sample_id].append(f"continuity:{record.scenario}")
    for run_record in run_records:
        run_record.continuity_tags = tag_map.get(run_record.sample_id, [])


def _build_gap_summary(
    run_records: List[RunIndexRecord],
    failure_records: List[FailureIndexRecord],
    continuity_records: List[ContinuityObservationRecord],
) -> Dict[str, Any]:
    gap_counter: Counter[str] = Counter()
    incomplete_samples: List[str] = []
    for run_record in run_records:
        gap_counter.update(run_record.gap_types)
        if not run_record.bundle_complete:
            incomplete_samples.append(run_record.sample_id)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_runs": len(run_records),
        "complete_runs": sum(1 for record in run_records if record.bundle_complete),
        "host_only_runs": sum(1 for record in run_records if record.host_only),
        "oe_available_runs": sum(1 for record in run_records if record.oe_available),
        "failure_case_count": len(failure_records),
        "gap_type_counts": dict(sorted(gap_counter.items())),
        "incomplete_sample_ids": incomplete_samples,
        "continuity_status": {record.scenario: record.status for record in continuity_records},
        "top_blockers": [
            "post_restart_sample_not_full_e4_bundle",
            "evidence_gap_still_present",
            "plasticity_reflection_still_weak",
        ],
    }


def _detect_plasticity_chains(growth_records: List[GrowthSignalRecord]) -> List[Dict[str, Any]]:
    by_family: Dict[str, List[GrowthSignalRecord]] = defaultdict(list)
    for record in growth_records:
        family_id = record.closure_family_id
        if family_id:
            by_family[family_id].append(record)

    chains: List[Dict[str, Any]] = []
    for family_id, records in by_family.items():
        ordered = sorted(records, key=lambda item: item.timestamp)
        for earlier, later in zip(ordered, ordered[1:]):
            earlier_outcome = earlier.cycle_summary.get("outcome_signature")
            later_outcome = later.cycle_summary.get("outcome_signature")
            if earlier_outcome in {"blocked", "failure"} and later_outcome == "success":
                if later.cycle_summary.get("repair_closure"):
                    chains.append(
                        {
                            "status": "partial_positive",
                            "sample_ids": [earlier.sample_id, later.sample_id],
                            "closure_family_id": family_id,
                            "proof_summary": "同一 closure family 从失败转为 success，且后者点亮 `repair_closure=true`。",
                            "not_proved_summary": "仍不足以单独证明跨更多回合的稳定 plasticity。",
                        }
                    )
                break
    return chains


def _detect_reflection_candidates(growth_records: List[GrowthSignalRecord]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    by_session: Dict[str, List[GrowthSignalRecord]] = defaultdict(list)
    for record in growth_records:
        if record.session_id:
            by_session[record.session_id].append(record)

    for record in sorted(growth_records, key=lambda item: item.timestamp):
        trigger = record.reflection_summary.get("trigger")
        if not trigger:
            continue
        downstream_effect = None
        for later in sorted(by_session.get(record.session_id or "", []), key=lambda item: item.timestamp):
            if later.timestamp <= record.timestamp:
                continue
            if later.response_tendency_summary != record.response_tendency_summary:
                downstream_effect = {
                    "sample_id": later.sample_id,
                    "response_tendency_summary": later.response_tendency_summary,
                }
                break
        candidates.append(
            {
                "status": "partial_positive" if downstream_effect else "partial_only",
                "sample_ids": [record.sample_id] + ([downstream_effect["sample_id"]] if downstream_effect else []),
                "trigger": trigger,
                "promote_to_memory": bool(record.reflection_summary.get("promote_to_memory")),
                "proof_summary": "存在结构化 `reflection_note`，并记录了 trigger / proposed_adjustment / promote_to_memory。",
                "not_proved_summary": (
                    "尚未看到干净、可重复的后续行为影响链。"
                    if not downstream_effect
                    else "已观察到后续 tendency 变化，但当前仍按 partial 处理。"
                ),
            }
        )
    return candidates


def _render_capture_status(
    run_records: List[RunIndexRecord],
    continuity_records: List[ContinuityObservationRecord],
    gap_summary: Dict[str, Any],
) -> str:
    return f"""# REAL_MAINLINE_CAPTURE_STATUS

- 生成时间：`{gap_summary['generated_at']}`
- 真实样本总数：`{len(run_records)}`
- 完整单样本 E4 bundle：`{gap_summary['complete_runs']}`
- host-only 样本：`{gap_summary['host_only_runs']}`
- OE 结构化结果可用样本：`{gap_summary['oe_available_runs']}`

## Continuity

| scenario | status | sample_count | blocker |
|---|---|---:|---|
{chr(10).join(f"| {record.scenario} | {record.status} | {len(record.sample_ids)} | {record.blocker} |" for record in continuity_records)}

## 当前口径

- `/new continuity`：已作为直接真实正证据入账。
- `restart continuity`：已作为跨证据链正证据入账，但仍不是完整单样本 E4 bundle。
- `restore continuity`：已作为直接真实正证据入账。
- 本文件不能证明：`E5` 稳定成立、`Developmental Self` 准入通过。
"""


def _render_continuity_ledger(records: List[ContinuityObservationRecord]) -> str:
    blocks: List[str] = ["# CONTINUITY_OBSERVATION_LEDGER", ""]
    for record in records:
        blocks.append(f"## {record.scenario}")
        blocks.append(f"- status: `{record.status}`")
        blocks.append(f"- sample_ids: {', '.join(f'`{sid}`' for sid in record.sample_ids) if record.sample_ids else '无'}")
        blocks.append(
            f"- external_evidence_refs: {', '.join(f'`{ref}`' for ref in record.external_evidence_refs) if record.external_evidence_refs else '无'}"
        )
        blocks.append(f"- what_it_proves: {record.proof_summary}")
        blocks.append(f"- what_it_does_not_prove: {record.not_proved_summary}")
        blocks.append(f"- blocker: {record.blocker}")
        blocks.append("")
    return "\n".join(blocks).rstrip() + "\n"


def _render_plasticity_reflection(
    plasticity_chains: List[Dict[str, Any]],
    reflection_candidates: List[Dict[str, Any]],
) -> str:
    lines = ["# PLASTICITY_REFLECTION_EVIDENCE", ""]
    lines.append("## Plasticity")
    if plasticity_chains:
        for item in plasticity_chains:
            lines.append(f"- status: `{item['status']}`")
            lines.append(f"- sample_ids: {', '.join(f'`{sid}`' for sid in item['sample_ids'])}")
            lines.append(f"- closure_family_id: `{item['closure_family_id']}`")
            lines.append(f"- proof: {item['proof_summary']}")
            lines.append(f"- not_proved: {item['not_proved_summary']}")
    else:
        lines.append("- 当前未发现满足“failure -> repair -> re-decision”或“repeated failure -> tendency change”的可归档链。")
    lines.append("")
    lines.append("## Reflection")
    if reflection_candidates:
        for item in reflection_candidates[:5]:
            lines.append(f"- status: `{item['status']}`")
            lines.append(f"- trigger: `{item['trigger']}`")
            lines.append(f"- promote_to_memory: `{item['promote_to_memory']}`")
            lines.append(f"- sample_ids: {', '.join(f'`{sid}`' for sid in item['sample_ids'])}")
            lines.append(f"- proof: {item['proof_summary']}")
            lines.append(f"- not_proved: {item['not_proved_summary']}")
    else:
        lines.append("- 当前未发现带结构化 `reflection_note` 的真实样本。")
    lines.append("")
    lines.append("## 结论限制")
    lines.append("- 本文件只证明当前可审计信号与候选链，不证明 plasticity 或 reflection 已稳定成立。")
    return "\n".join(lines).rstrip() + "\n"


def _render_gap_summary(gap_summary: Dict[str, Any]) -> str:
    return f"""# GAP_SUMMARY

- 生成时间：`{gap_summary['generated_at']}`
- 总样本：`{gap_summary['total_runs']}`
- 完整 bundle：`{gap_summary['complete_runs']}`
- host-only：`{gap_summary['host_only_runs']}`
- OE 可用：`{gap_summary['oe_available_runs']}`
- failure_cases：`{gap_summary['failure_case_count']}`

## Gap Types

| gap_type | count |
|---|---:|
{chr(10).join(f"| {name} | {count} |" for name, count in gap_summary['gap_type_counts'].items())}

## 当前 blocker

{chr(10).join(f"- `{item}`" for item in gap_summary['top_blockers'])}
"""


def _render_data_schema() -> str:
    return """# Dashboard Data Schema

所有 dashboard_v1 数据都来自只读派生索引，不是正式运行时状态源。

## files

- `runs.jsonl`: `RunIndexRecord`
- `continuity_observation.jsonl`: `ContinuityObservationRecord`
- `growth_signals.jsonl`: `GrowthSignalRecord`
- `failures.jsonl`: `FailureIndexRecord`
- `agency_runs.jsonl`: `AgencyRunRecord`
- `runs_rollup.json`: `RunsRollup`
- `growth_rollup.json`: `GrowthRollup`
- `failures_rollup.json`: `FailuresRollup`
- `agency_rollup.json`: `AgencyRollup`
- `gap_summary.json`: gap 统计与 blocker 汇总
- `build_meta.json`: 索引生成元信息

## authority

- 主权威输入：`artifacts/telegram_real_mainline_v1/real_telegram/*/ledger.json`
- 兼容镜像：`sample.json` 只允许用于展示，不允许反向发明 OpenEmotion 语义
- Agency causal 链：优先读 `ledger.json.openemotion.events[*].payload`，仅在缺字段时回退 `sample.json`
- continuity 观察口径：`artifacts/mvs_e5_observation/*.md`

## notes

- host-only 样本会进入 `runs.jsonl` 与 continuity 统计
- host-only 样本不会进入 `growth_signals.jsonl`
- `restore` 一旦拿到“显式 restore + 首条 post-restore 完整 bundle + continuity probe 命中”的真实链，就应升级为 `status=direct_real`
"""


def _render_readme() -> str:
    return """# Growth Dashboard v1

## 生成索引

```bash
python3 scripts/build_growth_dashboard_indexes.py
```

## 启动只读服务

```bash
cd EgoCore
PYTHONPATH=. python3 -m app.main --dashboard --host 127.0.0.1 --port 8787
```

## 页面

- `/runs`
- `/growth`
- `/failures`
- `/agency`
- `/samples/<sample_id>`

## 说明

- Dashboard v1 只读，允许轮询刷新，不反写 EgoCore / OpenEmotion 状态
- 页面层提供共享语义摘要与中英切换，但原始 artifact 仍是唯一权威证据
- 所有结论强度必须低于或等于当前 artifacts 与 observation 文档的证据强度
"""


def dashboard_source_last_modified(
    *,
    real_dir: Path = REAL_TELEGRAM_DIR,
    failure_dir: Path = FAILURE_CASES_DIR,
    observation_dir: Path = OBSERVATION_DIR,
    validation_doc: Path = VALIDATION_DOC,
) -> float:
    return _source_last_modified([real_dir, failure_dir, observation_dir, validation_doc])


def _source_last_modified(paths: Iterable[Path]) -> float:
    latest = 0.0
    for path in paths:
        if not path.exists():
            continue
        if path.is_file():
            latest = max(latest, path.stat().st_mtime)
            continue
        for child in path.rglob("*"):
            if child.is_file():
                latest = max(latest, child.stat().st_mtime)
    return latest


def build_dashboard_indexes(
    *,
    real_dir: Path = REAL_TELEGRAM_DIR,
    failure_dir: Path = FAILURE_CASES_DIR,
    observation_dir: Path = OBSERVATION_DIR,
    output_dir: Path = DASHBOARD_DIR,
    validation_doc: Path = VALIDATION_DOC,
) -> DashboardBuildSummary:
    output_dir.mkdir(parents=True, exist_ok=True)
    sample_dirs = _iter_sample_dirs(real_dir)
    run_records = [_build_run_record(sample_dir) for sample_dir in sample_dirs]
    continuity_records = _build_continuity_records(observation_dir=observation_dir)
    _attach_continuity_tags(run_records, continuity_records)
    _attach_run_semantics(run_records)
    growth_records = [
        record
        for sample_dir, run_record in zip(sample_dirs, run_records)
        for record in [_build_growth_record(sample_dir, run_record)]
        if record is not None
    ]
    _attach_growth_semantics(growth_records)
    failure_records = _build_failure_records(failure_dir=failure_dir)
    _attach_failure_semantics(failure_records)
    gap_summary = _build_gap_summary(run_records, failure_records, continuity_records)
    plasticity_chains = _detect_plasticity_chains(growth_records)
    reflection_candidates = _detect_reflection_candidates(growth_records)
    agency_records: List[AgencyRunRecord] = []
    excluded_counts: Counter[str] = Counter()
    for sample_dir, run_record in zip(sample_dirs, run_records):
        agency_record, exclusion_reason = _build_agency_record(sample_dir, run_record)
        if agency_record is not None:
            agency_records.append(agency_record)
            continue
        if exclusion_reason:
            excluded_counts.update([exclusion_reason])
    agency_rollup = _build_agency_rollup(
        agency_records,
        excluded_counts=dict(sorted(excluded_counts.items())),
    )
    runs_rollup = _build_runs_rollup(run_records, continuity_records)
    growth_rollup = _build_growth_rollup(growth_records)
    failures_rollup = _build_failures_rollup(failure_records, gap_summary)
    source_last_modified = dashboard_source_last_modified(
        real_dir=real_dir,
        failure_dir=failure_dir,
        observation_dir=observation_dir,
        validation_doc=validation_doc,
    )

    summary = DashboardBuildSummary(
        generated_at=datetime.now(timezone.utc).isoformat(),
        source_last_modified=source_last_modified,
        total_runs=len(run_records),
        complete_runs=gap_summary["complete_runs"],
        oe_available_runs=gap_summary["oe_available_runs"],
        host_only_runs=gap_summary["host_only_runs"],
        failure_cases=len(failure_records),
        dashboard_schema_version=DASHBOARD_SCHEMA_VERSION,
        real_user_runs=sum(1 for record in run_records if record.sample_scope != "fixture_like"),
        fixture_like_runs=sum(1 for record in run_records if record.sample_scope == "fixture_like"),
        continuity_status={record.scenario: record.status for record in continuity_records},
        gap_type_counts=gap_summary["gap_type_counts"],
        plasticity_chain_count=len(plasticity_chains),
        reflection_candidate_count=len(reflection_candidates),
        agency_records=len(agency_records),
        agency_profile_scope=agency_rollup.profile_scope,
    )

    _write_jsonl(output_dir / RUNS_FILE, (record.to_dict() for record in run_records))
    _write_jsonl(output_dir / CONTINUITY_FILE, (record.to_dict() for record in continuity_records))
    _write_jsonl(output_dir / GROWTH_FILE, (record.to_dict() for record in growth_records))
    _write_jsonl(output_dir / FAILURES_FILE, (record.to_dict() for record in failure_records))
    _write_jsonl(output_dir / AGENCY_RUNS_FILE, (record.to_dict() for record in agency_records))
    _write_json(output_dir / RUNS_ROLLUP_FILE, runs_rollup.to_dict())
    _write_json(output_dir / GROWTH_ROLLUP_FILE, growth_rollup.to_dict())
    _write_json(output_dir / FAILURES_ROLLUP_FILE, failures_rollup.to_dict())
    _write_json(output_dir / AGENCY_ROLLUP_FILE, agency_rollup.to_dict())
    _write_json(output_dir / GAP_SUMMARY_FILE, gap_summary)
    _write_json(output_dir / BUILD_META_FILE, summary.to_dict())

    (output_dir / REAL_CAPTURE_STATUS_DOC).write_text(
        _render_capture_status(run_records, continuity_records, gap_summary),
        encoding="utf-8",
    )
    (output_dir / CONTINUITY_LEDGER_DOC).write_text(
        _render_continuity_ledger(continuity_records),
        encoding="utf-8",
    )
    (output_dir / PLASTICITY_REFLECTION_DOC).write_text(
        _render_plasticity_reflection(plasticity_chains, reflection_candidates),
        encoding="utf-8",
    )
    (output_dir / GAP_SUMMARY_DOC).write_text(
        _render_gap_summary(gap_summary),
        encoding="utf-8",
    )
    (output_dir / DATA_SCHEMA_DOC).write_text(_render_data_schema(), encoding="utf-8")
    (output_dir / README_DOC).write_text(_render_readme(), encoding="utf-8")

    return summary


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows
