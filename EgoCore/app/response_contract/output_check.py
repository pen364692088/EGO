from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Any, Dict, List, Optional

from app.runtime_v2.semantic_parser import build_runtime_status_reply
from app.runtime_v2.run_items import build_run_item_summary_text

from .response_plan import ResponsePlan


@dataclass(frozen=True)
class OutputCheckVerdict:
    passed: bool
    reason: str
    reply_text: str
    delivery_kind: str
    authority_source: str = "response_contract.output_check"
    applied_authority: str = "model_chat"
    reply_origin: str = "chat_mainline"
    used_host_fallback: bool = False
    is_evidence_bearing: bool = False
    used_host_verbatim: bool = False
    fidelity_mode: str = "summary"
    fidelity_gap: bool = False
    evidence_snapshot: Optional[Dict[str, Any]] = None
    intent_gate_status: str = "skipped"
    intent_gate_reason: str = ""
    intent_gate_would_block: bool = False
    intent_gate_violation_class: str = "none"
    intent_gate_violation_types: tuple[str, ...] = ()
    intent_gate_confidence: Optional[float] = None


_TERMINAL_KINDS = {"completed_verified", "completed", "blocked", "failed", "status_probe"}
_INTENT_GATE_ALLOWED_AUTHORITIES = {"model_chat"}
_INTENT_GATE_ALLOWED_REPLY_ORIGINS = {"chat_mainline"}
_COMPLETION_CLAIM_GUARD_PATTERNS = (
    re.compile(r"已(经)?(改好|修好|修复|解决|处理好|保存)", re.IGNORECASE),
    re.compile(r"问题解决了", re.IGNORECASE),
    re.compile(r"刚保存", re.IGNORECASE),
    re.compile(r"缓存问题", re.IGNORECASE),
    re.compile(r"显示延迟", re.IGNORECASE),
    re.compile(r"文件确实是刚保存的", re.IGNORECASE),
)


def apply_output_check(plan: ResponsePlan, state: Any) -> OutputCheckVerdict:
    reply_text = str(plan.reply_text or "").strip()
    delivery_kind = _normalize_delivery_kind(plan)
    applied_authority = str(getattr(plan, "reply_authority", "") or "model_chat")
    reply_origin = str((metadata := dict(getattr(plan, "metadata", None) or {})).get("reply_origin") or "chat_mainline")
    used_host_fallback = False
    is_evidence_bearing = False
    used_host_verbatim = False
    fidelity_mode = "summary"
    fidelity_gap = False
    evidence_snapshot: Optional[Dict[str, Any]] = None
    intent_gate_status = "skipped"
    intent_gate_reason = "not_applicable"
    intent_gate_would_block = False
    intent_gate_violation_class = "none"
    intent_gate_violation_types: tuple[str, ...] = ()
    intent_gate_confidence: Optional[float] = None
    used_intent_gate_fallback = False

    raw_evidence_payload = metadata.get("evidence_payload")
    if isinstance(raw_evidence_payload, dict):
        evidence_snapshot = dict(raw_evidence_payload)
        is_evidence_bearing = True
        verbatim_reply = _render_evidence_reply_text(evidence_snapshot)
        if verbatim_reply:
            evidence_body = str(evidence_snapshot.get("body") or "").strip()
            if applied_authority == "host_evidence" and evidence_body and evidence_body not in reply_text:
                reply_text = verbatim_reply
                used_host_verbatim = True
            if evidence_body and evidence_body in reply_text:
                fidelity_mode = "verbatim"
                fidelity_gap = False
            else:
                fidelity_mode = "summary"
                fidelity_gap = applied_authority == "host_evidence"
        else:
            fidelity_mode = "fallback"
            fidelity_gap = True

    if not reply_text:
        fallback = _build_fallback_reply(plan.kind, state)
        if fallback:
            reply_text = fallback
            used_host_fallback = True
            if not is_evidence_bearing:
                fidelity_mode = "fallback"

    completion_claim_guard = evaluate_completion_claim_guard(
        plan,
        state,
        reply_text=reply_text,
        delivery_kind=delivery_kind,
        applied_authority=applied_authority,
        reply_origin=reply_origin,
        is_evidence_bearing=is_evidence_bearing,
    )
    if completion_claim_guard["applied"]:
        reply_text = completion_claim_guard["reply_text"]
        applied_authority = completion_claim_guard["applied_authority"]
        used_host_fallback = True

    intent_gate_verdict = evaluate_response_intent_gate(
        plan,
        state,
        reply_text=reply_text,
        delivery_kind=delivery_kind,
        applied_authority=applied_authority,
        reply_origin=reply_origin,
        is_evidence_bearing=is_evidence_bearing,
    )
    intent_gate_status = intent_gate_verdict["status"]
    intent_gate_reason = intent_gate_verdict["reason"]
    intent_gate_would_block = intent_gate_verdict["would_block"]
    intent_gate_violation_class = intent_gate_verdict["violation_class"]
    intent_gate_violation_types = intent_gate_verdict["violation_types"]
    intent_gate_confidence = intent_gate_verdict["confidence_score"]
    if intent_gate_verdict["applied"]:
        reply_text = intent_gate_verdict["reply_text"]
        applied_authority = intent_gate_verdict["applied_authority"]
        used_intent_gate_fallback = bool(intent_gate_verdict["used_fallback"])
        used_host_fallback = used_host_fallback or used_intent_gate_fallback

    passed = bool(reply_text)
    reason = "ok"
    if completion_claim_guard["applied"]:
        reason = completion_claim_guard["reason"]
    elif used_intent_gate_fallback:
        reason = "intent_gate_fallback_applied"
    elif used_host_verbatim:
        reason = "host_verbatim_applied"
    elif used_host_fallback:
        reason = "host_fallback_applied"
    elif not passed:
        reason = "missing_reply_text"
    elif fidelity_gap:
        reason = "fidelity_gap"

    return OutputCheckVerdict(
        passed=passed,
        reason=reason,
        reply_text=reply_text,
        delivery_kind=delivery_kind,
        applied_authority=applied_authority,
        reply_origin=reply_origin,
        used_host_fallback=used_host_fallback,
        is_evidence_bearing=is_evidence_bearing,
        used_host_verbatim=used_host_verbatim,
        fidelity_mode=fidelity_mode,
        fidelity_gap=fidelity_gap,
        evidence_snapshot=evidence_snapshot,
        intent_gate_status=intent_gate_status,
        intent_gate_reason=intent_gate_reason,
        intent_gate_would_block=intent_gate_would_block,
        intent_gate_violation_class=intent_gate_violation_class,
        intent_gate_violation_types=intent_gate_violation_types,
        intent_gate_confidence=intent_gate_confidence,
    )


def _normalize_delivery_kind(plan: ResponsePlan) -> str:
    if plan.kind in {"waiting_input", "ask"}:
        return "ask"
    if plan.kind in _TERMINAL_KINDS:
        return "final"
    return plan.delivery_kind or "chat"


def _build_fallback_reply(kind: str, state: Any) -> str:
    if kind in {"completed_verified", "completed"}:
        return _build_completion_summary(state)
    if kind in {"blocked", "failed"}:
        return _build_blocked_summary(state)
    if kind in {"waiting_input", "ask"}:
        if _should_render_active_status_reply(state):
            return build_runtime_status_reply(state)
        current_step = str(getattr(state, "current_step", "") or "").strip()
        if current_step:
            return f"当前需要你确认后继续。当前步骤：{current_step}"
        return "当前需要你确认后继续。"
    return ""


def _should_render_active_status_reply(state: Any) -> bool:
    if bool(getattr(state, "waiting_for_user_input", False)):
        return False
    return str(getattr(state, "task_status", "") or "").strip() in {
        "running",
        "resumable_pause",
        "blocked",
    }


def _build_completion_summary(state: Any) -> str:
    if hasattr(state, "get_run_items"):
        run_items = list(state.get_run_items() or [])
        verified_items = [item for item in run_items if getattr(item, "status", None) == "verified"]
        if verified_items:
            lines = ["已完成这些任务："]
            for index, item in enumerate(verified_items, start=1):
                lines.append(f"{index}. {build_run_item_summary_text(item)}")
            return "\n".join(lines)
    current_goal = str(getattr(state, "current_goal", "") or "").strip()
    if current_goal:
        return f"已完成：{current_goal}"
    return "已完成。"


def _build_blocked_summary(state: Any) -> str:
    if hasattr(state, "get_run_item_status_summary"):
        summary: Dict[str, Any] = state.get_run_item_status_summary()
        completed: List[str] = list(summary.get("completed") or [])
        active = summary.get("active")
        pending: List[str] = list(summary.get("pending") or [])
        lines = ["当前任务无法继续推进。"]
        if completed:
            lines.append(f"已完成：{', '.join(completed)}。")
        if active:
            lines.append(f"当前卡住：{active}。")
        if pending:
            lines.append(f"还未开始：{', '.join(pending)}。")
        return "\n".join(lines)
    current_step = str(getattr(state, "current_step", "") or "").strip()
    if current_step:
        return f"当前任务无法继续推进。当前卡住：{current_step}。"
    return "当前任务无法继续推进。"


def _render_evidence_reply_text(snapshot: Dict[str, Any]) -> str:
    body = str(snapshot.get("body") or "").strip()
    if not body:
        return ""
    request_kind = str(snapshot.get("request_kind") or "")
    if request_kind == "directory_listing":
        return f"目录内容如下：\n{body}"
    return body


def evaluate_response_intent_gate(
    plan: ResponsePlan,
    state: Any,
    *,
    reply_text: str,
    delivery_kind: str,
    applied_authority: str,
    reply_origin: str,
    is_evidence_bearing: bool,
    enable_shadow_logging: Optional[bool] = None,
    apply_fallback: bool = True,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "applied": False,
        "used_fallback": False,
        "reply_text": reply_text,
        "applied_authority": applied_authority,
        "status": "skipped",
        "reason": "not_applicable",
        "would_block": False,
        "violation_class": "none",
        "violation_types": (),
        "confidence_score": None,
    }

    if (
        not reply_text
        or is_evidence_bearing
        or delivery_kind != "chat"
        or applied_authority not in _INTENT_GATE_ALLOWED_AUTHORITIES
        or reply_origin not in _INTENT_GATE_ALLOWED_REPLY_ORIGINS
    ):
        return result

    traffic_source, observation_source = _resolve_intent_shadow_sources(state)
    if enable_shadow_logging is None:
        enable_shadow_logging = observation_source in {"direct_real", "testbot", "replay"}
    checker = _get_intent_checker(enable_shadow_logging=enable_shadow_logging)
    if checker is None:
        result["status"] = "checker_unavailable"
        result["reason"] = "checker_unavailable"
        return result

    contract = _build_response_intent_contract(plan, state)
    try:
        verdict = checker.check_intent(
            reply_text,
            contract,
            session_id=str(getattr(state, "session_id", "") or ""),
            traffic_source=traffic_source,
            observation_source=observation_source,
        )
    except Exception as exc:
        result["status"] = "checker_error"
        result["reason"] = f"checker_error:{type(exc).__name__}"
        return result

    violation_types = tuple(
        dict.fromkeys(
            str(v.get("type") or "").strip()
            for v in verdict.to_dict().get("violations", [])
            if str(v.get("type") or "").strip()
        )
    )
    result.update(
        {
            "status": verdict.status,
            "reason": "ok" if verdict.status == "ok" else "violation_detected",
            "would_block": bool(verdict.would_block),
            "violation_class": str(verdict.violation_class or "none"),
            "violation_types": violation_types,
            "confidence_score": float(verdict.confidence_score),
        }
    )

    if verdict.status == "violation" and verdict.would_block and apply_fallback:
        fallback = _build_intent_gate_fallback(plan)
        result.update(
            {
                "applied": True,
                "used_fallback": True,
                "reply_text": fallback,
                "applied_authority": "host_degraded_fallback",
                "reason": "would_block",
            }
        )
    return result


def _build_response_intent_contract(plan: ResponsePlan, state: Any) -> Dict[str, Any]:
    metadata = dict(getattr(plan, "metadata", None) or {})
    source = _resolve_intent_contract_source(plan, state)
    intent_policy = {
        "speaker_mode": str(getattr(plan, "speaker_mode", "reflect") or "reflect"),
        "epistemic_status": str(getattr(plan, "epistemic_status", "uncertain") or "uncertain"),
        "commitment_level": str(getattr(plan, "commitment_level", "soft") or "soft"),
        "tone_bounds": dict(getattr(plan, "tone_bounds", {}) or {}),
        "allowed_claims": list(source.get("allowed_claims") or []),
        "forbidden_claims": list(source.get("forbidden_claims") or []),
        "must_include": list(getattr(plan, "must_include", ()) or ()),
        "must_not_upgrade": dict(getattr(plan, "must_not_upgrade", {}) or {}),
    }
    grounding = dict(source.get("grounding") or {})
    if not grounding:
        grounding = _build_response_grounding(state)
    return {
        "intent_policy": intent_policy,
        "grounding": grounding,
    }


def evaluate_completion_claim_guard(
    plan: ResponsePlan,
    state: Any,
    *,
    reply_text: str,
    delivery_kind: str,
    applied_authority: str,
    reply_origin: str,
    is_evidence_bearing: bool,
) -> Dict[str, Any]:
    result = {
        "applied": False,
        "reply_text": reply_text,
        "applied_authority": applied_authority,
        "reason": "not_applicable",
    }

    if (
        not reply_text
        or is_evidence_bearing
        or delivery_kind != "chat"
        or applied_authority not in _INTENT_GATE_ALLOWED_AUTHORITIES
        or reply_origin not in _INTENT_GATE_ALLOWED_REPLY_ORIGINS
    ):
        return result

    if not _has_active_continuity_context(state):
        return result
    if not _looks_like_unverified_completion_claim(reply_text):
        return result

    result.update(
        {
            "applied": True,
            "reply_text": _build_completion_claim_guard_fallback(state),
            "applied_authority": "host_degraded_fallback",
            "reason": "completion_claim_guard_applied",
        }
    )
    return result


def _resolve_intent_contract_source(plan: ResponsePlan, state: Any) -> Dict[str, Any]:
    metadata = dict(getattr(plan, "metadata", None) or {})
    source = metadata.get("intent_contract_source")
    if isinstance(source, dict):
        return {
            "authority_source": str(source.get("authority_source") or "response_contract.intent_contract_source"),
            "source_status": str(source.get("source_status") or "explicit_metadata"),
            "allowed_claims": list(source.get("allowed_claims") or []),
            "forbidden_claims": list(source.get("forbidden_claims") or []),
            "grounding": dict(source.get("grounding") or {}),
            "grounding_source": str(source.get("grounding_source") or ""),
        }

    return {
        "authority_source": "response_contract.output_check.legacy_metadata_fallback",
        "source_status": "legacy_metadata_fallback",
        "allowed_claims": list(metadata.get("allowed_claims") or []),
        "forbidden_claims": list(metadata.get("forbidden_claims") or []),
        "grounding": dict(metadata.get("grounding") or _build_response_grounding(state)),
        "grounding_source": "legacy_metadata",
    }


def _build_response_grounding(state: Any) -> Dict[str, Any]:
    if state is None:
        return {}
    ingress_context = dict(getattr(state, "ingress_context", None) or {})
    grounding = dict(ingress_context.get("response_grounding") or {})
    if grounding:
        return grounding
    return {}


def _has_active_continuity_context(state: Any) -> bool:
    if state is None:
        return False
    ingress_context = dict(getattr(state, "ingress_context", None) or {})
    if str(ingress_context.get("runtime_action") or "").strip() != "chat":
        return False
    recent_result_context = dict(getattr(state, "recent_delivered_result_context", None) or {})
    active_task_summary = {}
    if hasattr(state, "build_active_task_summary"):
        try:
            active_task_summary = dict(state.build_active_task_summary() or {})
        except Exception:
            active_task_summary = {}
    return bool(recent_result_context or active_task_summary or getattr(state, "current_goal", None))


def _looks_like_unverified_completion_claim(reply_text: str) -> bool:
    normalized = str(reply_text or "").strip()
    if not normalized:
        return False
    return any(pattern.search(normalized) for pattern in _COMPLETION_CLAIM_GUARD_PATTERNS)


def _build_completion_claim_guard_fallback(state: Any) -> str:
    recent_result_context = dict(getattr(state, "recent_delivered_result_context", None) or {})
    target_name = str(recent_result_context.get("target_name") or "").strip()
    if target_name:
        return f"我还没实际改动并重新验证 {target_name}。要我现在继续检查并处理吗？"
    current_goal = str(getattr(state, "current_goal", "") or "").strip()
    if current_goal:
        return f"我还没实际执行并验证“{current_goal}”这一步。要我继续处理吗？"
    return "我还没实际执行并重新验证这一步。要我继续处理吗？"


def _build_intent_gate_fallback(plan: ResponsePlan) -> str:
    metadata = dict(getattr(plan, "metadata", None) or {})
    conversation_act = str(metadata.get("conversation_act") or metadata.get("chat_act") or "").strip()
    if conversation_act == "presence_check":
        return "在，我在。"
    if conversation_act == "tone_feedback":
        return "收到，换一种说法。"
    if conversation_act == "social_keepalive":
        return "我在听。"
    if conversation_act == "task_bridge_request":
        return "可以，你直接说想做什么。"
    if conversation_act == "light_chitchat":
        return "我在听。"
    return "我换个更稳妥的说法。"


def _resolve_intent_shadow_sources(state: Any) -> tuple[str, str]:
    session_id = str(getattr(state, "session_id", "") or "").strip()
    ingress_context = dict(getattr(state, "ingress_context", None) or {})
    observation_source = str(ingress_context.get("observation_source") or "").strip()
    traffic_source = str(ingress_context.get("traffic_source") or "").strip()

    if not observation_source:
        if session_id.startswith("telegram:"):
            observation_source = "direct_real"
        elif os.environ.get("PYTEST_CURRENT_TEST"):
            observation_source = "pytest"
        else:
            observation_source = "unknown"

    if not traffic_source:
        if observation_source == "direct_real":
            traffic_source = "real"
        elif observation_source in {"pytest", "testbot"}:
            traffic_source = "synthetic"
        elif observation_source == "replay":
            traffic_source = "replay"
        else:
            traffic_source = "unknown"

    return traffic_source, observation_source


def _get_intent_checker(*, enable_shadow_logging: bool = False):
    try:
        from emotiond.response_intent_checker import ResponseIntentChecker
    except Exception:
        return None
    return ResponseIntentChecker(enable_shadow_logging=enable_shadow_logging)
