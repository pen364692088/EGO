from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


HOLD = "held"
CANDIDATE_READY = "candidate_ready"
ASK = "ask"
SUGGEST = "suggest"

BLOCKING_SELFHOOD_PRIORITIES = {"guard", "conserve"}
REVIEW_SELFHOOD_PRIORITIES = {"review"}
SUPPORTED_CANDIDATE_FAMILIES = {"commitment_followup", "repair_review", "bounded_reminder", "thought_probe"}
TIMING_DELAY_WINDOW = "delay_window"
TIMING_READINESS_THRESHOLD = "readiness_threshold"
PROACTIVE_TOPIC_PERMISSION_ALLOW = "long_term_allow"
QUIET_STATE_REDUCED = "reduced"
QUIET_STATE_PAUSED = "paused"


def _clamp01(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.0
    return max(0.0, min(1.0, numeric))


def _trim_text(value: Any, *, limit: int = 280) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _ensure_terminal_punctuation(text: str) -> str:
    if not text:
        return ""
    if text.endswith(("。", "？", "！", ".", "?", "!")):
        return text
    return f"{text}。"


def _draft_text(*, family: str, mode: str, candidate: Optional[Dict[str, Any]] = None) -> str:
    candidate = dict(candidate or {})
    final_text_candidate = _trim_text(candidate.get("final_text_candidate"), limit=280)
    if final_text_candidate:
        return final_text_candidate
    draft_text = _trim_text(candidate.get("draft_text"), limit=220)
    open_question = _trim_text(candidate.get("open_question"), limit=120)
    message_shape_hint = str(candidate.get("message_shape_hint") or "short_view")
    if open_question and not open_question.endswith(("？", "?", "。", ".")):
        open_question = f"{open_question}？"
    if message_shape_hint == "question_only" and open_question:
        return open_question
    if message_shape_hint == "thought_plus_question" and draft_text and open_question:
        if open_question in draft_text:
            return draft_text
        return f"{_ensure_terminal_punctuation(draft_text)} {open_question}"
    if draft_text:
        return draft_text
    if family == "thought_probe" and open_question:
        return open_question
    return ""


def _normalize_timing_advice(candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    payload = dict(candidate.get("timing_advice") or {})
    mode = str(payload.get("timing_mode") or "").strip()
    if mode not in {TIMING_DELAY_WINDOW, TIMING_READINESS_THRESHOLD}:
        return None
    normalized = {
        "schema_version": str(payload.get("schema_version") or "subject_system_v1.timing_advice.v1"),
        "timing_mode": mode,
        "earliest_send_after_seconds": payload.get("earliest_send_after_seconds"),
        "preferred_send_after_seconds": payload.get("preferred_send_after_seconds"),
        "latest_send_after_seconds": payload.get("latest_send_after_seconds"),
        "readiness_score": payload.get("readiness_score"),
        "readiness_threshold": payload.get("readiness_threshold"),
        "timing_basis": str(payload.get("timing_basis") or "mixed"),
        "timing_confidence": _clamp01(payload.get("timing_confidence")),
    }
    return normalized


def _timing_ready_verdict(candidate: Dict[str, Any]) -> Dict[str, Any]:
    timing_advice = _normalize_timing_advice(candidate)
    if not timing_advice:
        return {
            "status": "fallback",
            "reason": "timing_advice_missing",
            "timing_advice": None,
        }

    idle_seconds = 0.0
    try:
        idle_seconds = float(candidate.get("idle_seconds") or 0.0)
    except (TypeError, ValueError):
        idle_seconds = 0.0
    earliest = timing_advice.get("earliest_send_after_seconds")
    latest = timing_advice.get("latest_send_after_seconds")

    if isinstance(latest, (int, float)) and idle_seconds > float(latest):
        return {
            "status": "expired",
            "reason": "timing_window_expired",
            "timing_advice": timing_advice,
        }
    if timing_advice["timing_mode"] == TIMING_DELAY_WINDOW:
        if isinstance(earliest, (int, float)) and idle_seconds < float(earliest):
            return {
                "status": "hold",
                "reason": "timing_window_not_open",
                "timing_advice": timing_advice,
            }
        return {
            "status": "ready",
            "reason": "timing_window_open",
            "timing_advice": timing_advice,
        }

    threshold = timing_advice.get("readiness_threshold")
    score = timing_advice.get("readiness_score")
    if isinstance(earliest, (int, float)) and idle_seconds < float(earliest):
        return {
            "status": "hold",
            "reason": "timing_window_not_open",
            "timing_advice": timing_advice,
        }
    if not isinstance(score, (int, float)) or not isinstance(threshold, (int, float)):
        return {
            "status": "fallback",
            "reason": "readiness_signal_missing",
            "timing_advice": timing_advice,
        }
    if float(score) < float(threshold):
        return {
            "status": "hold",
            "reason": "readiness_threshold_not_met",
            "timing_advice": timing_advice,
        }
    return {
        "status": "ready",
        "reason": "readiness_threshold_met",
        "timing_advice": timing_advice,
    }


@dataclass(frozen=True)
class HostProactiveDecision:
    status: str
    mode: Optional[str]
    candidate_id: str
    candidate_family: str
    reason: str
    draft_text: str
    proposal_discipline: str
    behavioral_authority: str
    timing_advice: Optional[Dict[str, Any]] = None
    timing_verdict: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "mode": self.mode,
            "candidate_id": self.candidate_id,
            "candidate_family": self.candidate_family,
            "reason": self.reason,
            "draft_text": self.draft_text,
            "proposal_discipline": self.proposal_discipline,
            "behavioral_authority": self.behavioral_authority,
            "timing_advice": dict(self.timing_advice or {}) if self.timing_advice else None,
            "timing_verdict": dict(self.timing_verdict or {}) if self.timing_verdict else None,
            "authority_source": "egocore.runtime_v2.host_proactive_candidate_arbiter",
        }


def _held(
    *,
    candidate: Dict[str, Any],
    reason: str,
) -> HostProactiveDecision:
    timing_verdict = _timing_ready_verdict(candidate)
    return HostProactiveDecision(
        status=HOLD,
        mode=None,
        candidate_id=str(candidate.get("candidate_id") or ""),
        candidate_family=str(candidate.get("candidate_family") or ""),
        reason=reason,
        draft_text="",
        proposal_discipline=str(candidate.get("proposal_discipline") or ""),
        behavioral_authority=str(candidate.get("behavioral_authority") or ""),
        timing_advice=dict(timing_verdict.get("timing_advice") or {}) if timing_verdict.get("timing_advice") else None,
        timing_verdict=timing_verdict,
    )


def _ready(
    *,
    candidate: Dict[str, Any],
    mode: str,
    reason: str,
) -> HostProactiveDecision:
    family = str(candidate.get("candidate_family") or "")
    timing_verdict = _timing_ready_verdict(candidate)
    return HostProactiveDecision(
        status=CANDIDATE_READY,
        mode=mode,
        candidate_id=str(candidate.get("candidate_id") or ""),
        candidate_family=family,
        reason=reason,
        draft_text=_draft_text(family=family, mode=mode, candidate=candidate),
        proposal_discipline=str(candidate.get("proposal_discipline") or ""),
        behavioral_authority=str(candidate.get("behavioral_authority") or ""),
        timing_advice=dict(timing_verdict.get("timing_advice") or {}) if timing_verdict.get("timing_advice") else None,
        timing_verdict=timing_verdict,
    )


def arbitrate_host_proactive_candidate(
    *,
    subject_system_v1: Dict[str, Any] | None,
    idle_eligible: bool,
    active_task_present: bool,
    runtime_guard: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    subject_payload = dict(subject_system_v1 or {})
    candidate = dict(subject_payload.get("host_proactive_candidate") or {})
    trace_payload = dict(subject_payload.get("trace_payload") or {})
    host_proactive_context = dict(trace_payload.get("host_proactive_context") or {})
    guard = dict(runtime_guard or {})

    if not candidate:
        hold_reason = str(host_proactive_context.get("thought_probe_hold_reason") or "").strip() or "missing_candidate"
        fallback_candidate = {
            "candidate_family": str(host_proactive_context.get("candidate_family") or ""),
            "topic_fingerprint": str(host_proactive_context.get("topic_fingerprint") or ""),
            "topic_cluster_ref": str(host_proactive_context.get("topic_cluster_ref") or ""),
            "topic_anchor_summary": str(host_proactive_context.get("topic_anchor_summary") or ""),
            "topic_binding_mode": str(host_proactive_context.get("topic_binding_mode") or ""),
            "topic_sendability": str(host_proactive_context.get("topic_sendability") or ""),
        }
        return _held(candidate=fallback_candidate, reason=hold_reason).to_dict()
    if not idle_eligible:
        return _held(candidate=candidate, reason="not_idle").to_dict()
    if active_task_present:
        return _held(candidate=candidate, reason="active_task_present").to_dict()

    proposal_discipline = str(candidate.get("proposal_discipline") or "")
    behavioral_authority = str(candidate.get("behavioral_authority") or "")
    if proposal_discipline != "proposal_only":
        return _held(candidate=candidate, reason="proposal_discipline_must_remain_proposal_only").to_dict()
    if behavioral_authority != "none":
        return _held(candidate=candidate, reason="behavioral_authority_must_remain_none").to_dict()
    if bool(guard.get("tool_execution_requested")):
        return _held(candidate=candidate, reason="tool_execution_not_allowed").to_dict()
    if bool(guard.get("transport_authority_requested")):
        return _held(candidate=candidate, reason="transport_authority_not_allowed").to_dict()
    if bool(guard.get("direct_reply_authority_requested")):
        return _held(candidate=candidate, reason="direct_reply_authority_not_allowed").to_dict()

    family = str(candidate.get("candidate_family") or "")
    if family not in SUPPORTED_CANDIDATE_FAMILIES:
        return _held(candidate=candidate, reason="unsupported_candidate_family").to_dict()

    selfhood_priority = str(candidate.get("selfhood_priority") or "")
    continuity_ref = str(candidate.get("continuity_ref") or "")
    continuity_confidence = _clamp01(candidate.get("continuity_confidence"))
    delivery_failure = bool(candidate.get("delivery_failure")) or bool(guard.get("delivery_failure"))
    timing_verdict = _timing_ready_verdict(candidate)
    if timing_verdict["status"] == "expired":
        return _held(candidate=candidate, reason=str(timing_verdict["reason"] or "timing_window_expired")).to_dict()
    if timing_verdict["status"] == "hold":
        return _held(candidate=candidate, reason=str(timing_verdict["reason"] or "timing_window_not_open")).to_dict()

    if family == "repair_review":
        return _ready(candidate=candidate, mode=ASK, reason="repair_review_family_requires_ask").to_dict()

    if family == "commitment_followup":
        if selfhood_priority in BLOCKING_SELFHOOD_PRIORITIES:
            return _held(candidate=candidate, reason="selfhood_priority_blocks_followup").to_dict()
        if delivery_failure:
            return _ready(candidate=candidate, mode=ASK, reason="delivery_failure_forces_repair_review_posture").to_dict()
        if selfhood_priority in REVIEW_SELFHOOD_PRIORITIES:
            return _ready(candidate=candidate, mode=ASK, reason="selfhood_priority_review_requires_ask").to_dict()
        return _ready(candidate=candidate, mode=SUGGEST, reason="stable_commitment_followup").to_dict()

    if family == "thought_probe":
        if str(candidate.get("proactive_topic_permission") or "") != PROACTIVE_TOPIC_PERMISSION_ALLOW:
            return _held(candidate=candidate, reason="proactive_topic_permission_not_allowed").to_dict()
        quiet_state = str(candidate.get("quiet_state") or "").strip()
        if quiet_state == QUIET_STATE_PAUSED:
            return _held(candidate=candidate, reason="quiet_state_paused").to_dict()
        if selfhood_priority == "conserve":
            return _held(candidate=candidate, reason="selfhood_priority_blocks_topic_outreach").to_dict()
        if delivery_failure:
            return _held(candidate=candidate, reason="delivery_failure_blocks_topic_outreach").to_dict()
        if quiet_state == QUIET_STATE_REDUCED and _clamp01(candidate.get("initiative_score")) < 0.72:
            return _held(candidate=candidate, reason="reduced_mode_requires_higher_value_candidate").to_dict()
        if not str(candidate.get("source_ref") or "").strip():
            return _held(candidate=candidate, reason="topic_source_ref_missing").to_dict()
        if not str(candidate.get("draft_text") or candidate.get("open_question") or "").strip():
            return _held(candidate=candidate, reason="topic_content_missing").to_dict()
        return _ready(candidate=candidate, mode=SUGGEST, reason="durable_thought_probe_ready").to_dict()

    if continuity_confidence < 0.65 or not continuity_ref:
        return _held(candidate=candidate, reason="continuity_not_stable_enough").to_dict()
    return _ready(candidate=candidate, mode=SUGGEST, reason="stable_bounded_reminder").to_dict()
