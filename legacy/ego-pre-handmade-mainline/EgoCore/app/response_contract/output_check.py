from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Any, Dict, List, Optional

from app.runtime_v2.topic_anchor import build_topic_anchor_variants
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
    anti_template_status: str = "skipped"
    anti_template_reason: str = ""
    fallback_origin: str = "none"


_TERMINAL_KINDS = {"completed_verified", "completed", "blocked", "failed", "status_probe"}
_INTENT_GATE_ALLOWED_AUTHORITIES = {"model_chat"}
_INTENT_GATE_ALLOWED_REPLY_ORIGINS = {"chat_mainline"}
_ANTI_TEMPLATE_ALLOWED_AUTHORITIES = {"model_chat"}
_ANTI_TEMPLATE_ALLOWED_REPLY_ORIGINS = {"chat_mainline", "subject_system_v1_proactive"}
_ANTI_TEMPLATE_GENERIC_PATTERNS = (
    "你想聊什么",
    "你先起头",
    "你接着起个头",
    "还是由我直接起个头",
    "最近有没有碰到",
    "想顺手吐槽",
    "随便聊聊",
    "目前没在忙具体任务",
    "你想听听我对什么话题的看法",
)
_ANTI_TEMPLATE_PROACTIVE_TEMPLATE_PATTERNS = (
    "I can surface a bounded reminder to preserve continuity here if you want.",
    "There may be a continuity reminder worth surfacing. Do you want me to bring it up?",
    "I can follow up on the open commitment with a bounded next step if you want.",
    "There is an open commitment thread here. Do you want me to surface the next bounded follow-up?",
    "I may need to review a blocked or failed commitment before moving further. Want me to surface that review first?",
    "我刚想到一个相关切口。你想继续展开吗？",
    "轻轻接回来",
    "现在继续吗",
    "你想现在继续展开吗",
    "我想补一个轻提醒",
    "你想先看这个切口吗",
)
_COMPLETION_CLAIM_GUARD_PATTERNS = (
    re.compile(r"已(经)?(改好|修好|修复|解决|处理好|保存)", re.IGNORECASE),
    re.compile(r"改好啦", re.IGNORECASE),
    re.compile(r"已经换好了", re.IGNORECASE),
    re.compile(r"问题解决了", re.IGNORECASE),
    re.compile(r"刚保存", re.IGNORECASE),
    re.compile(r"缓存问题", re.IGNORECASE),
    re.compile(r"显示延迟", re.IGNORECASE),
    re.compile(r"文件确实是刚保存的", re.IGNORECASE),
    re.compile(r"重新打开.*看看", re.IGNORECASE),
    re.compile(r"强制刷新", re.IGNORECASE),
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
    anti_template_status = "skipped"
    anti_template_reason = "not_applicable"
    fallback_origin = str(metadata.get("fallback_origin") or "none").strip() or "none"
    used_intent_gate_fallback = False
    used_anti_template_fallback = False

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
        if used_intent_gate_fallback:
            fallback_origin = "degraded_only"

    anti_template_verdict = evaluate_anti_template_gate(
        plan,
        state,
        reply_text=reply_text,
        delivery_kind=delivery_kind,
        applied_authority=applied_authority,
        reply_origin=reply_origin,
        is_evidence_bearing=is_evidence_bearing,
        apply_fallback=True,
    )
    anti_template_status = anti_template_verdict["status"]
    anti_template_reason = anti_template_verdict["reason"]
    if anti_template_verdict["applied"]:
        reply_text = anti_template_verdict["reply_text"]
        applied_authority = anti_template_verdict["applied_authority"]
        used_anti_template_fallback = bool(anti_template_verdict["used_fallback"])
        used_host_fallback = used_host_fallback or used_anti_template_fallback
        if used_anti_template_fallback:
            fallback_origin = "degraded_only"

    passed = bool(reply_text)
    reason = "ok"
    if completion_claim_guard["applied"]:
        reason = completion_claim_guard["reason"]
    elif used_intent_gate_fallback:
        reason = "intent_gate_fallback_applied"
    elif used_anti_template_fallback:
        reason = "anti_template_fallback_applied"
    elif intent_gate_status == "violation":
        reason = "intent_gate_violation_logged"
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
        anti_template_status=anti_template_status,
        anti_template_reason=anti_template_reason,
        fallback_origin=fallback_origin,
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


def evaluate_anti_template_gate(
    plan: ResponsePlan,
    state: Any,
    *,
    reply_text: str,
    delivery_kind: str,
    applied_authority: str,
    reply_origin: str,
    is_evidence_bearing: bool,
    apply_fallback: bool = True,
) -> Dict[str, Any]:
    result = {
        "applied": False,
        "used_fallback": False,
        "reply_text": reply_text,
        "applied_authority": applied_authority,
        "status": "skipped",
        "reason": "not_applicable",
    }
    metadata = dict(getattr(plan, "metadata", None) or {})
    fallback_origin = str(metadata.get("fallback_origin") or "none").strip() or "none"
    if (
        not reply_text
        or is_evidence_bearing
        or delivery_kind != "chat"
        or applied_authority not in _ANTI_TEMPLATE_ALLOWED_AUTHORITIES
        or reply_origin not in _ANTI_TEMPLATE_ALLOWED_REPLY_ORIGINS
        or fallback_origin == "degraded_only"
    ):
        return result

    conversation_act = str(metadata.get("conversation_act") or metadata.get("chat_act") or "").strip()
    if conversation_act in {"presence_check", "tone_feedback", "social_keepalive"}:
        return result

    context = _extract_contract_context(plan, state)
    normalized = str(reply_text or "").strip().lower()
    banned_patterns = list(_ANTI_TEMPLATE_GENERIC_PATTERNS)
    if reply_origin == "subject_system_v1_proactive":
        banned_patterns.extend(_ANTI_TEMPLATE_PROACTIVE_TEMPLATE_PATTERNS)
    banned_patterns.extend(context.get("banned_patterns") or [])
    violation_reason = ""
    if any(pattern.lower() in normalized for pattern in banned_patterns):
        violation_reason = "generic_or_template_phrase_detected"
    elif reply_origin == "subject_system_v1_proactive":
        violation_reason = _proactive_specificity_violation_reason(reply_text, metadata)
    elif conversation_act == "solicited_view":
        question_count = _count_explicit_questions(reply_text)
        if not _has_declarative_viewpoint(reply_text):
            violation_reason = "solicited_view_missing_viewpoint"
        elif question_count < 1:
            violation_reason = "solicited_view_missing_followup_question"
        elif question_count > 1:
            violation_reason = "solicited_view_too_many_questions"
        else:
            required_anchor_tokens = [
                str(token).strip().lower()
                for token in (context.get("required_anchor_tokens") or [])
                if str(token).strip()
            ]
            if required_anchor_tokens and not any(token in normalized for token in required_anchor_tokens):
                violation_reason = "solicited_view_missing_topic_anchor"

    if not violation_reason:
        result["status"] = "ok"
        result["reason"] = "ok"
        return result

    result["status"] = "violation"
    result["reason"] = violation_reason
    if not apply_fallback:
        return result

    if conversation_act == "solicited_view":
        fallback = _build_solicited_view_fallback(plan, state)
    elif reply_origin == "subject_system_v1_proactive":
        result.update(
            {
                "applied": True,
                "used_fallback": False,
                "reply_text": "",
                "applied_authority": "host_guard",
            }
        )
        return result
    else:
        fallback = _build_intent_gate_fallback(plan)
    result.update(
        {
            "applied": True,
            "used_fallback": True,
            "reply_text": fallback,
            "applied_authority": "host_degraded_fallback",
        }
    )
    return result


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
    if str(ingress_context.get("runtime_action") or "").strip() not in {"chat", "return_runtime_status", "execute_task"}:
        return False
    pending_result_continuation = dict(getattr(state, "pending_result_continuation", None) or {})
    if pending_result_continuation:
        return True
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
    pending_result_continuation = dict(getattr(state, "pending_result_continuation", None) or {})
    if pending_result_continuation:
        target_name = str(pending_result_continuation.get("target_name") or "").strip()
        requested_mode = str(pending_result_continuation.get("requested_mode") or "analyze").strip() or "analyze"
        status = str(pending_result_continuation.get("status") or "pending").strip() or "pending"
        if requested_mode == "write" or status == "running":
            if target_name:
                return f"我还没完成这次对 {target_name} 的修改并验证结果。"
            return "我还没完成这次修改并验证结果。"
        if target_name:
            return f"我还在检查 {target_name} 这个改动点，还没实际改完并重新验证。"
        return "我还在检查这个改动点，还没实际改完并重新验证。"

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
    if conversation_act == "solicited_view":
        return _build_solicited_view_fallback(plan)
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


def _extract_contract_context(plan: ResponsePlan, state: Any) -> Dict[str, Any]:
    metadata = dict(getattr(plan, "metadata", None) or {})
    ingress_context = dict(getattr(state, "ingress_context", None) or {}) if state is not None else {}
    chat_output_contract = metadata.get("chat_output_contract")
    if not isinstance(chat_output_contract, dict):
        chat_output_contract = ingress_context.get("chat_output_contract") or {}
    chat_output_contract = dict(chat_output_contract or {})
    topic_anchor_summary = str(
        metadata.get("solicited_view_topic_anchor")
        or chat_output_contract.get("topic_anchor_summary")
        or ingress_context.get("solicited_view_topic_anchor")
        or metadata.get("topic_summary")
        or ""
    ).strip()
    required_anchor_tokens = [
        str(token).strip()
        for token in (
            metadata.get("required_anchor_tokens")
            or chat_output_contract.get("required_anchor_tokens")
            or []
        )
        if str(token).strip()
    ]
    banned_patterns = [
        str(pattern).strip()
        for pattern in (
            metadata.get("anti_template_banned_patterns")
            or chat_output_contract.get("banned_patterns")
            or []
        )
        if str(pattern).strip()
    ]
    return {
        "topic_anchor_summary": topic_anchor_summary,
        "required_anchor_tokens": required_anchor_tokens,
        "banned_patterns": banned_patterns,
    }


def _count_explicit_questions(text: str) -> int:
    body = str(text or "").strip()
    if not body:
        return 0
    count = body.count("?") + body.count("？")
    if count:
        return count
    segments = [segment.strip() for segment in re.split(r"[。.!！\n]+", body) if segment.strip()]
    return sum(
        1
        for segment in segments
        if segment.endswith(("吗", "呢", "么"))
        or segment.startswith(("为什么", "怎么", "如何", "是否"))
    )


def _has_declarative_viewpoint(text: str) -> bool:
    body = str(text or "").strip()
    if not body:
        return False
    if any(
        marker in body
        for marker in (
            "我觉得",
            "我倾向于",
            "我更倾向",
            "我的看法",
            "我会把重点放在",
            "关键在于",
            "更像是",
            "需要",
            "应该",
            "如果沿着",
        )
    ):
        return True
    segments = [segment.strip() for segment in re.split(r"[。.!！?\n？]+", body) if segment.strip()]
    for segment in segments:
        if segment.endswith(("吗", "呢", "么")):
            continue
        if len(segment) >= 12:
            return True
    return False


def _proactive_specificity_violation_reason(reply_text: str, metadata: Dict[str, Any]) -> str:
    def _normalize(value: str) -> str:
        return "".join(str(value or "").strip().lower().split())

    def _topic_anchor_bound(body: str, anchor: str) -> bool:
        normalized_body = _normalize(body)
        for variant in build_topic_anchor_variants(anchor, limit=120):
            if _normalize(variant) in normalized_body:
                return True
        normalized_anchor = _normalize(anchor)
        if any("a" <= char.lower() <= "z" for char in normalized_anchor):
            tokens = [
                token
                for token in anchor.lower().replace("?", " ").replace("？", " ").split()
                if len(token) >= 2
            ]
            if tokens and any(token in body.lower() for token in tokens):
                return True
        stop_fragments = {"你觉得", "怎么做", "是什么", "为什么", "有没有", "什么想法", "告诉我"}
        for size in (4, 3):
            for index in range(0, max(0, len(normalized_anchor) - size + 1)):
                fragment = normalized_anchor[index : index + size]
                if fragment in stop_fragments:
                    continue
                if fragment in normalized_body:
                    return True
        return False

    normalized = str(reply_text or "").strip()
    if not normalized:
        return "proactive_missing_specificity"
    if _count_explicit_questions(normalized) > 1:
        return "proactive_too_many_questions"

    topic_summary = str(metadata.get("topic_summary") or "").strip()
    topic_anchor_summary = str(metadata.get("topic_anchor_summary") or "").strip()
    topic_sendability = str(metadata.get("topic_sendability") or "").strip()
    source_draft_text = str(metadata.get("source_draft_text") or "").strip()
    open_question = str(metadata.get("open_question") or "").strip()
    message_shape_hint = str(metadata.get("message_shape_hint") or "").strip()
    candidate_family = str(metadata.get("candidate_family") or "").strip()

    if candidate_family == "thought_probe":
        if topic_sendability == "meta_only":
            return "proactive_missing_specificity"
        if not source_draft_text and not topic_summary and not open_question:
            return "proactive_missing_specificity"
        if message_shape_hint == "question_only" and not open_question:
            return "proactive_missing_specificity"
        if topic_anchor_summary and not _topic_anchor_bound(normalized, topic_anchor_summary):
            return "proactive_missing_specificity"
        if not topic_anchor_summary and not topic_summary and not source_draft_text:
            return "proactive_missing_specificity"
    elif len(normalized) < 12:
        return "proactive_missing_specificity"
    return ""


def _build_solicited_view_fallback(plan: ResponsePlan, state: Any | None = None) -> str:
    metadata = dict(getattr(plan, "metadata", None) or {})
    context = _extract_contract_context(plan, state)
    anchor = str(
        metadata.get("solicited_view_topic_anchor")
        or context.get("topic_anchor_summary")
        or metadata.get("topic_summary")
        or ""
    ).strip()
    if anchor:
        return (
            f"如果沿着“{anchor}”继续看，我更倾向于把重点放在可持续闭环和可验证边界上，"
            "而不是一次性追求最终状态。你更想先拆核心机制，还是先看现实约束？"
        )
    return "如果沿着刚才这个话题继续看，我更倾向于先抓住最关键的约束，再往下推演。你更想先看原理，还是先看落地路径？"


def _build_proactive_anti_template_fallback(plan: ResponsePlan) -> str:
    return ""


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
