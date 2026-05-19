from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import logging
from typing import Any, Dict, Optional

from app.response_contract.output_check import OutputCheckVerdict, apply_output_check
from app.response_contract.response_plan import ResponsePlan, build_direct_response_plan
from app.runtime_v2.proactive_identity import (
    build_proactive_outreach_epoch,
    build_sent_text_fingerprint,
    current_proactive_outreach_history,
    normalize_proactive_text,
)
from app.runtime_v2.topic_anchor import (
    build_topic_anchor_variants,
    coerce_recent_user_turn_records,
    extract_recent_substantive_topic_anchor,
    is_meta_or_control_topic_turn,
    is_non_substantive_topic_turn_record,
    is_prompt_like_view_request,
)

from .subject_system_bridge import get_canonical_subject_system_v1_context


logger = logging.getLogger(__name__)


_CANDIDATE_READY = "candidate_ready"
_META_FOLLOWUP_MARKERS = (
    "提醒我继续",
    "只发一个轻提醒",
    "不要连续发",
    "会回来继续这个话题",
    "以后可以主动找我",
    "以后可以主动来找我",
)
_PROACTIVE_TEMPLATE_BLOCK_PATTERNS = (
    "你想聊什么",
    "你先起头",
    "你接着起个头",
    "还是由我直接起个头",
    "现在继续吗",
    "你想现在继续展开吗",
    "轻轻接回来",
    "我想补一个轻提醒",
    "你想先看这个切口吗",
    "随便聊聊",
    "目前没在忙具体任务",
    "i can surface a bounded reminder to preserve continuity here if you want",
    "there may be a continuity reminder worth surfacing",
    "i can follow up on the open commitment with a bounded next step if you want",
    "there is an open commitment thread here",
    "i may need to review a blocked or failed commitment before moving further",
    "我刚想到一个相关切口",
)
_THOUGHT_PROBE_NORMAL_FLOOR_SECONDS = 20 * 60
_THOUGHT_PROBE_REDUCED_FLOOR_SECONDS = 45 * 60
_THOUGHT_PROBE_META_PHRASES = (
    "这条判断",
    "这个判断",
    "那个判断",
    "表面上的判断",
    "这个问题",
    "那个问题",
    "问题本身",
    "这个前提",
    "那个前提",
    "这条判断的前提",
)
_THOUGHT_PROBE_NONCONVERSATIONAL_META_PHRASES = (
    "表面上的判断",
    "这条判断",
    "这个判断",
    "那个判断",
    "这条判断的前提",
    "这个前提",
    "那个前提",
    "这个问题",
    "那个问题",
    "问题本身",
    "当前判断背后",
    "没有显式展开的前提",
)
_THOUGHT_PROBE_WEAK_GENERIC_TOPIC_ANCHORS = (
    "这种能力如何实现",
    "这个能力如何实现",
    "这项能力如何实现",
    "那个能力如何实现",
    "能力如何实现",
    "能力怎么实现",
    "如何实现这种能力",
    "如何实现这个能力",
    "如何实现这项能力",
    "怎么实现这种能力",
    "怎么实现这个能力",
    "怎么实现这项能力",
    "如何实现",
    "怎么实现",
    "这种能力",
    "这个能力",
    "这项能力",
)
_THOUGHT_PROBE_ABSTRACT_META_OUTREACH_PHRASES = (
    "想要可以被拆成",
    "可实现的机制",
    "不丢掉主体性",
    "系统什么时候才算",
    "什么时候才算真的",
    "真的在想要",
    "只在执行规则",
    "而不是只在执行规则",
)
_PROACTIVE_ASKBACK_PATTERNS = (
    "你想聊什么",
    "你先起头",
    "你接着起个头",
    "由你起头",
    "现在继续吗",
    "你想现在继续",
    "你想先看",
    "你想听",
    "what do you want to talk about",
    "do you want me to continue",
)


def _serialize_response_plan(plan: Optional[ResponsePlan]) -> Optional[Dict[str, Any]]:
    if plan is None:
        return None
    return {
        "kind": plan.kind,
        "delivery_kind": plan.delivery_kind,
        "authority_source": plan.authority_source,
        "reply_authority": plan.reply_authority,
        "speaker_mode": plan.speaker_mode,
        "epistemic_status": plan.epistemic_status,
        "commitment_level": plan.commitment_level,
        "metadata": dict(plan.metadata or {}),
    }


def _serialize_output_verdict(verdict: Optional[OutputCheckVerdict]) -> Optional[Dict[str, Any]]:
    if verdict is None:
        return None
    return {
        "passed": verdict.passed,
        "reason": verdict.reason,
        "reply_text": verdict.reply_text,
        "delivery_kind": verdict.delivery_kind,
        "applied_authority": verdict.applied_authority,
        "reply_origin": verdict.reply_origin,
        "intent_gate_status": verdict.intent_gate_status,
        "intent_gate_reason": verdict.intent_gate_reason,
        "anti_template_status": verdict.anti_template_status,
        "anti_template_reason": verdict.anti_template_reason,
        "fallback_origin": verdict.fallback_origin,
    }


def _active_task_present(state: Any) -> bool:
    if hasattr(state, "build_active_task_summary"):
        return bool(state.build_active_task_summary())
    return False


def _resolve_idle_seconds(state: Any, *, now_ts: Optional[float], subject_candidate: Dict[str, Any]) -> float:
    candidate_idle_seconds = subject_candidate.get("idle_seconds")
    if candidate_idle_seconds not in (None, ""):
        try:
            return round(float(candidate_idle_seconds), 3)
        except (TypeError, ValueError):
            pass
    if hasattr(state, "idle_seconds_since_chat_activity"):
        return round(float(state.idle_seconds_since_chat_activity(now_ts=now_ts)), 3)
    return 0.0


def _current_timestamp(now_ts: Optional[float]) -> float:
    return float(now_ts) if now_ts is not None else datetime.now(UTC).timestamp()


def _current_recent_user_turn_count(state: Any) -> int:
    chat_state = getattr(state, "get_chat_state", lambda: None)()
    if chat_state is None:
        return 0
    return len(list(chat_state.recent_user_turns or []))


def _current_outreach_history(state: Any) -> list[Dict[str, Any]]:
    return current_proactive_outreach_history(state)


def _current_outreach_epoch(state: Any) -> str:
    return build_proactive_outreach_epoch(state)


def _current_outreach_history_by_latest_sent(state: Any) -> list[Dict[str, Any]]:
    history = _current_outreach_history(state)
    return sorted(
        history,
        key=lambda item: str(item.get("sent_at") or ""),
    )


def _current_recent_user_turn_records(state: Any) -> list[Dict[str, Any]]:
    if state is None or not hasattr(state, "get_chat_state"):
        return []
    chat_state = state.get_chat_state()
    return coerce_recent_user_turn_records(
        getattr(chat_state, "recent_user_turn_records", None),
        getattr(chat_state, "recent_user_turns", None),
    )


def _current_latest_assistant_reply(state: Any) -> str:
    if state is None or not hasattr(state, "get_chat_state"):
        return ""
    chat_state = state.get_chat_state()
    replies = [str(turn or "").strip() for turn in list(getattr(chat_state, "recent_assistant_replies", None) or [])]
    return _trim_text(replies[-1], limit=160) if replies else ""


def _parse_iso_timestamp(value: Any) -> Optional[float]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except (TypeError, ValueError):
        return None


def _contains_proactive_template_phrase(text: str) -> bool:
    normalized = normalize_proactive_text(text)
    if not normalized:
        return False
    return any(pattern in normalized for pattern in _PROACTIVE_TEMPLATE_BLOCK_PATTERNS)


def _question_count(text: str) -> int:
    body = str(text or "").strip()
    if not body:
        return 0
    return body.count("?") + body.count("？")


def _trim_text(value: Any, *, limit: int = 180) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _sanitize_topic_anchor(value: Any) -> str:
    text = _trim_text(value, limit=120).strip()
    return text.rstrip("。！？?!,.，；;：: ").strip()


def _build_direct_continuation_from_topic(topic_anchor: str) -> str:
    return ""


def _contains_meta_reference(text: Any) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return False
    return any(token in normalized for token in _THOUGHT_PROBE_META_PHRASES)


def _marker_count(text: Any, markers: tuple[str, ...]) -> int:
    normalized = normalize_proactive_text(str(text or ""))
    if not normalized:
        return 0
    return sum(1 for marker in markers if normalize_proactive_text(marker) in normalized)


def _looks_like_weak_generic_topic_anchor(value: Any) -> bool:
    normalized = normalize_proactive_text(str(value or ""))
    if not normalized:
        return False
    normalized_markers = tuple(
        normalize_proactive_text(marker) for marker in _THOUGHT_PROBE_WEAK_GENERIC_TOPIC_ANCHORS
    )
    if normalized in normalized_markers:
        return True
    if len(normalized) <= 12 and any(marker in normalized for marker in normalized_markers):
        return True
    return "能力" in normalized and ("如何实现" in normalized or "怎么实现" in normalized) and len(normalized) <= 18


def _resolve_thought_probe_topic_anchor(state: Any, selected_candidate: Dict[str, Any]) -> str:
    candidate_anchor = _sanitize_topic_anchor(selected_candidate.get("topic_anchor_summary"))
    recent_anchor = _sanitize_topic_anchor(_recent_non_meta_topic_anchor(state))
    if candidate_anchor and _looks_like_weak_generic_topic_anchor(candidate_anchor):
        selected_candidate["raw_topic_anchor_summary"] = candidate_anchor
        selected_candidate["weak_generic_topic_anchor"] = True
        if recent_anchor and not _looks_like_weak_generic_topic_anchor(recent_anchor):
            selected_candidate["topic_anchor_summary"] = recent_anchor
            selected_candidate["effective_topic_anchor_summary"] = recent_anchor
            selected_candidate["topic_anchor_rebound_source"] = "recent_substantive_topic"
            return recent_anchor
        selected_candidate["humanization_failed"] = True
        return ""
    selected = candidate_anchor or recent_anchor or ""
    if selected:
        selected_candidate["effective_topic_anchor_summary"] = selected
    return selected


def _looks_like_nonconversational_meta_probe_text(text: Any, *, topic_anchor: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return True
    if any(token in normalized for token in _THOUGHT_PROBE_NONCONVERSATIONAL_META_PHRASES):
        return True
    anchor = _sanitize_topic_anchor(topic_anchor)
    if anchor and normalized.startswith(f"关于“{anchor}”"):
        tail = normalized.split("”，", 1)[-1]
        if any(token in tail for token in _THOUGHT_PROBE_NONCONVERSATIONAL_META_PHRASES):
            return True
    return False


def _looks_like_abstract_meta_outreach_text(text: Any, *, topic_anchor: str) -> bool:
    if _looks_like_nonconversational_meta_probe_text(text, topic_anchor=topic_anchor):
        return True
    abstract_hits = _marker_count(text, _THOUGHT_PROBE_ABSTRACT_META_OUTREACH_PHRASES)
    if abstract_hits >= 2:
        return True
    if abstract_hits and _looks_like_weak_generic_topic_anchor(topic_anchor):
        return True
    return False


def _bind_meta_reference_to_topic(text: Any, *, topic_anchor: str) -> str:
    body = _trim_text(text, limit=220)
    anchor = _sanitize_topic_anchor(topic_anchor)
    if not body or not anchor:
        return body
    rewritten = body
    replacements = (
        ("表面上的判断", f"“{anchor}”这个判断"),
        ("这条判断的前提", f"“{anchor}”这个判断背后的前提"),
        ("这条判断", f"“{anchor}”这个判断"),
        ("这个判断", f"“{anchor}”这个判断"),
        ("那个判断", f"“{anchor}”这个判断"),
        ("这个问题", f"“{anchor}”这个问题"),
        ("那个问题", f"“{anchor}”这个问题"),
        ("问题本身", f"“{anchor}”这个问题本身"),
    )
    for source, replacement in replacements:
        rewritten = rewritten.replace(source, replacement)
    if f"“{anchor}”" in rewritten or anchor in rewritten:
        return rewritten
    return f"关于“{anchor}”，{rewritten}"


def _ensure_terminal_punctuation(text: str) -> str:
    if not text:
        return ""
    if text.endswith(("。", "？", "！", ".", "?", "!")):
        return text
    return f"{text}。"


def _topic_anchor_bound_in_text(text: Any, *, topic_anchor: str) -> bool:
    body = str(text or "").strip()
    if not body:
        return False
    for variant in build_topic_anchor_variants(topic_anchor, limit=120):
        if variant in body or f"“{variant}”" in body:
            return True
    return False


def _recent_non_meta_topic_anchor(state: Any) -> Optional[str]:
    anchor = extract_recent_substantive_topic_anchor(
        _current_recent_user_turn_records(state),
        skip_turn=lambda text: is_meta_or_control_topic_turn(text, include_prompt_like=False)
        or any(marker in text for marker in _META_FOLLOWUP_MARKERS),
    )
    resolved = str(anchor.get("topic_anchor") or "").strip()
    return _trim_text(resolved, limit=80) if resolved else None


def _fallback_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _strip_to_observation(value: Any, *, limit: int = 120) -> str:
    text = _trim_text(value, limit=limit).strip()
    if not text:
        return ""
    for separator in ("？", "?", "！", "!", "。", ".", "；", ";"):
        if separator in text:
            text = text.split(separator, 1)[0].strip()
            break
    return text.rstrip("，,：:；;。！？?! ").strip()


def _build_recent_topic_conversational_fallback(
    *,
    state: Any,
    selected_candidate: Dict[str, Any],
) -> str:
    return ""


def _recent_prompt_like_turn(state: Any) -> Optional[str]:
    for record in reversed(_current_recent_user_turn_records(state)):
        text = str(record.get("text") or "").strip()
        if not text:
            continue
        if is_non_substantive_topic_turn_record(record, include_prompt_like=False):
            continue
        if is_meta_or_control_topic_turn(text, include_prompt_like=False):
            continue
        if any(marker in text for marker in _META_FOLLOWUP_MARKERS):
            continue
        if is_prompt_like_view_request(text):
            return _trim_text(text, limit=120)
    return None


def _normalize_prompt_echo(value: Any) -> str:
    return normalize_proactive_text(str(value or ""))


def _looks_like_prompt_echo(text: str, prompt_like_turn: Optional[str]) -> bool:
    normalized_text = _normalize_prompt_echo(text)
    normalized_prompt = _normalize_prompt_echo(prompt_like_turn)
    if not normalized_text or not normalized_prompt:
        return False
    return normalized_prompt in normalized_text


def _build_deterministic_thought_probe_observation(
    *,
    selected_candidate: Dict[str, Any],
    topic_anchor: str,
) -> str:
    observation_candidates = (
        _sanitize_topic_anchor(selected_candidate.get("topic_summary")),
        _trim_text(selected_candidate.get("hidden_premise"), limit=180),
        _sanitize_topic_anchor(selected_candidate.get("frame_anchor")),
        _trim_text(selected_candidate.get("source_draft_text"), limit=200),
    )
    for candidate in observation_candidates:
        text = str(candidate or "").strip()
        if not text:
            continue
        if _contains_meta_reference(text):
            continue
        if not _topic_anchor_bound_in_text(text, topic_anchor=topic_anchor):
            return f"关于“{topic_anchor}”，{text}"
        return text
    return ""


def _should_attempt_conversational_rewrite(selected_candidate: Dict[str, Any]) -> bool:
    if str(selected_candidate.get("candidate_family") or "").strip() != "thought_probe":
        return False
    if str(selected_candidate.get("topic_sendability") or "").strip() == "meta_only":
        return False
    if str(selected_candidate.get("topic_anchor_kind") or "").strip() == "prompt_like_request":
        return False
    if str(selected_candidate.get("topic_conversation_grade") or "").strip() == "meta_reflection_only":
        return True
    if _contains_meta_reference(selected_candidate.get("source_draft_text")):
        return True
    if _contains_meta_reference(selected_candidate.get("open_question")):
        return True
    return False


def _generate_conversational_thought_probe_text(
    *,
    selected_candidate: Dict[str, Any],
    topic_anchor: str,
    prompt_like_turn: Optional[str],
) -> str:
    observation_seed = _build_deterministic_thought_probe_observation(
        selected_candidate=selected_candidate,
        topic_anchor=topic_anchor,
    )
    open_question = _trim_text(selected_candidate.get("open_question"), limit=140)
    if open_question and not open_question.endswith(("？", "?", "。", ".")):
        open_question = f"{open_question}？"
    if open_question and (
        _contains_meta_reference(open_question) or _looks_like_prompt_echo(open_question, prompt_like_turn)
    ):
        open_question = ""

    system_prompt = (
        "你在做宿主治理下的中文主动消息改写。"
        "把给定 thought_probe 材料改写成 1-2 句像人说话的主动消息。"
        "必须显式贴着 topic anchor，说一个具体观察，最多一个问题。"
        "禁止复述用户的索取观点提示词，禁止提醒式口吻，禁止抽象元反思绕圈。"
        "如果无法改写成自然、具体、贴题的话，就只输出 HOLD。"
    )
    user_prompt = (
        f"topic_anchor: {topic_anchor}\n"
        f"topic_summary: {selected_candidate.get('topic_summary') or ''}\n"
        f"hidden_premise: {selected_candidate.get('hidden_premise') or ''}\n"
        f"frame_anchor: {selected_candidate.get('frame_anchor') or ''}\n"
        f"draft_text: {selected_candidate.get('source_draft_text') or ''}\n"
        f"open_question: {selected_candidate.get('open_question') or ''}\n"
        f"prompt_like_user_turn_to_avoid: {prompt_like_turn or ''}\n"
        f"preferred_shape: {selected_candidate.get('message_shape_hint') or 'thought_plus_question'}\n"
        "输出要求：只给最终中文消息，不要解释。"
    )
    try:
        from app.llm_client import get_llm_client

        response = get_llm_client().generate(
            user_prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=120,
            timeout=20,
        )
        rewritten = _trim_text((response.content or "").strip(), limit=220)
        if rewritten and rewritten.upper() != "HOLD":
            return rewritten
    except Exception as exc:
        logger.debug("thought_probe conversational rewrite fallback: %s", exc)

    if observation_seed and open_question:
        return f"{_ensure_terminal_punctuation(observation_seed)} {open_question}"
    if observation_seed:
        return observation_seed
    return ""


def _verbalize_subject_system_candidate(
    *,
    state: Any,
    selected_candidate: Dict[str, Any],
) -> str:
    return _trim_text(selected_candidate.get("final_text_candidate"), limit=280)


def _candidate_audit_text_for_rejection_reason(selected_candidate: Dict[str, Any]) -> str:
    fragments = (
        _trim_text(selected_candidate.get("source_draft_text"), limit=220),
        _trim_text(selected_candidate.get("open_question"), limit=160),
    )
    return " ".join(fragment for fragment in fragments if fragment).strip()


def _text_language_hint(text: str) -> str:
    has_cjk = any("\u4e00" <= char <= "\u9fff" for char in str(text or ""))
    has_latin = any("a" <= char.lower() <= "z" for char in str(text or ""))
    if has_cjk and has_latin:
        return "mixed"
    if has_cjk:
        return "zh"
    if has_latin:
        return "en"
    return "unknown"


def _language_mismatch(candidate_hint: Any, text: str) -> bool:
    expected = str(candidate_hint or "").strip()
    actual = _text_language_hint(text)
    if expected in {"", "unknown", "mixed"} or actual in {"unknown", "mixed"}:
        return False
    return expected != actual


def _candidate_grounding_anchor(selected_candidate: Dict[str, Any]) -> str:
    grounding = dict(selected_candidate.get("content_grounding") or {})
    return _sanitize_topic_anchor(
        selected_candidate.get("effective_topic_anchor_summary")
        or selected_candidate.get("topic_anchor_summary")
        or grounding.get("topic_anchor_summary")
        or ""
    )


def _candidate_grounding_bound(text: str, selected_candidate: Dict[str, Any], *, topic_anchor: str) -> bool:
    def _has_meaningful_overlap(body: str, anchor: str) -> bool:
        body_norm = normalize_proactive_text(body)
        anchor_norm = normalize_proactive_text(anchor)
        if not body_norm or not anchor_norm:
            return False
        if anchor_norm in body_norm:
            return True
        if any("a" <= char.lower() <= "z" for char in anchor_norm):
            tokens = [token for token in anchor.lower().replace("?", " ").replace("？", " ").split() if len(token) >= 2]
            if tokens and any(token in body.lower() for token in tokens):
                return True
        stop_fragments = {"你觉得", "怎么做", "是什么", "为什么", "有没有", "什么想法", "告诉我"}
        for size in (4, 3):
            for index in range(0, max(0, len(anchor_norm) - size + 1)):
                fragment = anchor_norm[index : index + size]
                if fragment in stop_fragments:
                    continue
                if fragment in body_norm:
                    return True
        return False

    if topic_anchor and _topic_anchor_bound_in_text(text, topic_anchor=topic_anchor):
        return True
    if topic_anchor and _has_meaningful_overlap(text, topic_anchor):
        return True
    topic_summary = _sanitize_topic_anchor(selected_candidate.get("topic_summary"))
    if topic_summary and _topic_anchor_bound_in_text(text, topic_anchor=topic_summary):
        return True
    if topic_summary and _has_meaningful_overlap(text, topic_summary):
        return True
    grounding = dict(selected_candidate.get("content_grounding") or {})
    grounded_summary = _sanitize_topic_anchor(grounding.get("topic_summary"))
    if grounded_summary and _topic_anchor_bound_in_text(text, topic_anchor=grounded_summary):
        return True
    if grounded_summary and _has_meaningful_overlap(text, grounded_summary):
        return True
    return False


def _evaluate_final_text_candidate(
    *,
    state: Any,
    selected_candidate: Dict[str, Any],
    final_text: str,
) -> Dict[str, Any]:
    result = {
        "status": "accepted",
        "reason": "accepted",
        "judge_type": "host_naturalness_judge_v1",
    }
    audit_text = final_text or _candidate_audit_text_for_rejection_reason(selected_candidate)
    if not audit_text:
        return {**result, "status": "retry_later", "reason": "final_text_candidate_missing"}
    if _contains_proactive_template_phrase(audit_text):
        return {**result, "status": "retry_later", "reason": "template_or_askback_detected"}
    normalized = normalize_proactive_text(audit_text)
    if any(normalize_proactive_text(pattern) in normalized for pattern in _PROACTIVE_ASKBACK_PATTERNS):
        return {**result, "status": "retry_later", "reason": "topic_thrown_back_to_user"}
    if _question_count(audit_text) > 1:
        return {**result, "status": "retry_later", "reason": "too_many_questions"}
    if final_text and _language_mismatch(selected_candidate.get("language_hint"), final_text):
        return {**result, "status": "retry_later", "reason": "language_mismatch"}

    family = str(selected_candidate.get("candidate_family") or "").strip()
    if family == "thought_probe":
        topic_anchor = _candidate_grounding_anchor(selected_candidate) or _sanitize_topic_anchor(
            _recent_non_meta_topic_anchor(state)
        )
        if topic_anchor and not selected_candidate.get("topic_anchor_summary"):
            selected_candidate["topic_anchor_summary"] = topic_anchor
            selected_candidate["effective_topic_anchor_summary"] = topic_anchor
        if str(selected_candidate.get("topic_anchor_kind") or "").strip() == "prompt_like_request":
            return {**result, "status": "held", "reason": "proactive_anchor_prompt_like"}
        if str(selected_candidate.get("topic_sendability") or "").strip() == "meta_only":
            return {**result, "status": "held", "reason": "proactive_meta_only_candidate"}
        if not topic_anchor:
            return {**result, "status": "held", "reason": "proactive_topic_unanchored"}
        if _looks_like_prompt_echo(audit_text, _recent_prompt_like_turn(state)):
            return {**result, "status": "held", "reason": "proactive_question_echoes_user_prompt"}
        if _looks_like_abstract_meta_outreach_text(audit_text, topic_anchor=topic_anchor):
            return {**result, "status": "held", "reason": "proactive_meta_reflection_not_conversational"}
        if not _candidate_grounding_bound(audit_text, selected_candidate, topic_anchor=topic_anchor):
            return {**result, "status": "held", "reason": "proactive_topic_unanchored"}
    elif len(normalized) < 12:
        return {**result, "status": "retry_later", "reason": "proactive_missing_specificity"}
    if not final_text:
        return {**result, "status": "retry_later", "reason": "final_text_candidate_missing"}
    return result


def _build_timing_contract(
    *,
    selected_candidate: Dict[str, Any],
    now_ts: Optional[float],
    idle_seconds: float,
) -> Optional[Dict[str, Any]]:
    timing_advice = dict(selected_candidate.get("timing_advice") or {})
    timing_mode = str(timing_advice.get("timing_mode") or "").strip()
    if not timing_mode:
        return None

    current_ts = _current_timestamp(now_ts)
    reference_ts = current_ts - max(0.0, float(idle_seconds or 0.0))

    def _absolute_iso(offset: Any) -> Optional[str]:
        try:
            offset_seconds = float(offset)
        except (TypeError, ValueError):
            return None
        if offset_seconds < 0.0:
            offset_seconds = 0.0
        return datetime.fromtimestamp(reference_ts + offset_seconds, tz=UTC).isoformat()

    contract = {
        "timing_mode": timing_mode,
        "not_before_at": _absolute_iso(timing_advice.get("earliest_send_after_seconds")),
        "preferred_at": _absolute_iso(timing_advice.get("preferred_send_after_seconds")),
        "expires_at": _absolute_iso(timing_advice.get("latest_send_after_seconds")),
        "readiness_threshold": timing_advice.get("readiness_threshold"),
        "timing_confidence": timing_advice.get("timing_confidence"),
        "timing_source": "subject_system_v1",
    }
    if timing_advice.get("readiness_score") is not None:
        contract["readiness_score"] = timing_advice.get("readiness_score")
    return contract


def _build_selected_candidate(
    *,
    subject_system_v1: Dict[str, Any],
    host_proactive_decision: Dict[str, Any],
) -> Dict[str, Any]:
    subject_candidate = dict(subject_system_v1.get("host_proactive_candidate") or {})
    trace_payload = dict(subject_system_v1.get("trace_payload") or {})
    continuity_ref = str(subject_candidate.get("continuity_ref") or "").strip()
    return {
        "candidate_id": str(
            host_proactive_decision.get("candidate_id")
            or subject_candidate.get("candidate_id")
            or ""
        ).strip(),
        "candidate_family": str(
            host_proactive_decision.get("candidate_family")
            or subject_candidate.get("candidate_family")
            or ""
        ).strip(),
        "mode": str(host_proactive_decision.get("mode") or "").strip() or None,
        "reason": str(host_proactive_decision.get("reason") or "").strip(),
        "proposal_discipline": str(
            host_proactive_decision.get("proposal_discipline")
            or subject_candidate.get("proposal_discipline")
            or ""
        ).strip(),
        "behavioral_authority": str(
            host_proactive_decision.get("behavioral_authority")
            or subject_candidate.get("behavioral_authority")
            or ""
        ).strip(),
        "continuity_ref": continuity_ref or None,
        "continuity_confidence": subject_candidate.get("continuity_confidence"),
        "source_cycle": continuity_ref or str(subject_candidate.get("candidate_id") or "").strip() or None,
        "source_candidate_hash": str(
            subject_candidate.get("source_candidate_hash")
            or trace_payload.get("update_packet_hash")
            or ""
        ).strip() or None,
        "initiative_score": subject_candidate.get("initiative_score", subject_candidate.get("continuity_confidence")),
        "delivery_ready": True,
        "timing_advice": dict(
            host_proactive_decision.get("timing_advice")
            or subject_candidate.get("timing_advice")
            or {}
        ),
        "timing_reasoning_trace": dict(subject_candidate.get("timing_reasoning_trace") or {}),
        "topic_source": str(subject_candidate.get("topic_source") or "").strip() or None,
        "topic_fingerprint": str(subject_candidate.get("topic_fingerprint") or "").strip() or None,
        "topic_cluster_ref": str(subject_candidate.get("topic_cluster_ref") or "").strip() or None,
        "topic_anchor_summary": str(subject_candidate.get("topic_anchor_summary") or "").strip() or None,
        "topic_anchor_source": str(subject_candidate.get("topic_anchor_source") or "").strip() or None,
        "topic_anchor_kind": str(subject_candidate.get("topic_anchor_kind") or "").strip() or None,
        "topic_binding_mode": str(subject_candidate.get("topic_binding_mode") or "").strip() or None,
        "topic_sendability": str(subject_candidate.get("topic_sendability") or "").strip() or None,
        "topic_conversation_grade": str(subject_candidate.get("topic_conversation_grade") or "").strip() or None,
        "raw_topic_anchor_summary": str(subject_candidate.get("raw_topic_anchor_summary") or "").strip() or None,
        "effective_topic_anchor_summary": str(subject_candidate.get("effective_topic_anchor_summary") or "").strip() or None,
        "topic_anchor_rebound_source": str(subject_candidate.get("topic_anchor_rebound_source") or "").strip() or None,
        "weak_generic_topic_anchor": subject_candidate.get("weak_generic_topic_anchor"),
        "recent_topic_fallback_allowed": subject_candidate.get("recent_topic_fallback_allowed"),
        "topic_summary": str(subject_candidate.get("topic_summary") or "").strip() or None,
        "message_shape_hint": str(subject_candidate.get("message_shape_hint") or "").strip() or None,
        "source_ref": str(subject_candidate.get("source_ref") or "").strip() or None,
        "frame_anchor": str(subject_candidate.get("frame_anchor") or "").strip() or None,
        "hidden_premise": str(subject_candidate.get("hidden_premise") or "").strip() or None,
        "source_draft_text": str(subject_candidate.get("draft_text") or "").strip() or None,
        "open_question": str(subject_candidate.get("open_question") or "").strip() or None,
        "final_text_candidate": str(subject_candidate.get("final_text_candidate") or "").strip() or None,
        "language_hint": str(subject_candidate.get("language_hint") or "").strip() or None,
        "style_intent": dict(subject_candidate.get("style_intent") or {}),
        "content_grounding": dict(subject_candidate.get("content_grounding") or {}),
        "generation_trace": dict(subject_candidate.get("generation_trace") or {}),
        "proactive_topic_permission": str(subject_candidate.get("proactive_topic_permission") or "").strip() or None,
        "quiet_state": str(subject_candidate.get("quiet_state") or "").strip() or None,
        "feedback_signal": str(subject_candidate.get("feedback_signal") or "").strip() or None,
        "outreach_reason": str(subject_candidate.get("outreach_reason") or "").strip() or None,
    }


def _normalize_selected_candidate_expression_context(
    *,
    state: Any,
    selected_candidate: Dict[str, Any],
) -> None:
    if str(selected_candidate.get("candidate_family") or "").strip() != "thought_probe":
        return
    topic_anchor = _sanitize_topic_anchor(selected_candidate.get("topic_anchor_summary"))
    effective_anchor = _sanitize_topic_anchor(selected_candidate.get("effective_topic_anchor_summary"))
    if topic_anchor and _looks_like_weak_generic_topic_anchor(topic_anchor):
        selected_candidate["raw_topic_anchor_summary"] = (
            selected_candidate.get("raw_topic_anchor_summary") or topic_anchor
        )
        selected_candidate["weak_generic_topic_anchor"] = True
        if effective_anchor and not _looks_like_weak_generic_topic_anchor(effective_anchor):
            selected_candidate["topic_anchor_summary"] = effective_anchor
            selected_candidate["effective_topic_anchor_summary"] = effective_anchor
            return
        recent_anchor = _sanitize_topic_anchor(_recent_non_meta_topic_anchor(state))
        if recent_anchor and not _looks_like_weak_generic_topic_anchor(recent_anchor):
            selected_candidate["topic_anchor_summary"] = recent_anchor
            selected_candidate["effective_topic_anchor_summary"] = recent_anchor
            selected_candidate["topic_anchor_rebound_source"] = "recent_substantive_topic"
        return
    if topic_anchor and not effective_anchor:
        selected_candidate["effective_topic_anchor_summary"] = topic_anchor


def _duplicate_topic_outreach_reason(
    state: Any,
    selected_candidate: Dict[str, Any],
    *,
    verbalized_text: str,
) -> Optional[str]:
    if str(selected_candidate.get("candidate_family") or "") != "thought_probe":
        return None
    text_fingerprint = build_sent_text_fingerprint(verbalized_text)
    topic_fingerprint = str(selected_candidate.get("topic_fingerprint") or "").strip()
    topic_cluster_ref = str(selected_candidate.get("topic_cluster_ref") or "").strip()
    for marker in _current_outreach_history(state):
        if text_fingerprint and str(marker.get("sent_text_fingerprint") or "").strip() == text_fingerprint:
            return "duplicate_verbalization_before_user_return"
        if topic_fingerprint and str(marker.get("topic_fingerprint") or "").strip() == topic_fingerprint:
            return "duplicate_topic_cluster_before_user_return"
        if topic_cluster_ref and str(marker.get("topic_cluster_ref") or "").strip() == topic_cluster_ref:
            return "duplicate_topic_cluster_before_user_return"
    return None


def _thought_probe_pacing_floor_reason(
    state: Any,
    selected_candidate: Dict[str, Any],
    *,
    now_ts: Optional[float],
) -> Optional[str]:
    if str(selected_candidate.get("candidate_family") or "") != "thought_probe":
        return None
    history = _current_outreach_history_by_latest_sent(state)
    if not history:
        return None
    quiet_state = str(selected_candidate.get("quiet_state") or "").strip()
    floor_seconds = (
        _THOUGHT_PROBE_REDUCED_FLOOR_SECONDS
        if quiet_state == "reduced"
        else _THOUGHT_PROBE_NORMAL_FLOOR_SECONDS
    )
    last_sent_at = _parse_iso_timestamp(history[-1].get("sent_at"))
    if last_sent_at is None:
        return None
    current_ts = _current_timestamp(now_ts)
    host_floor_not_before_ts = last_sent_at + float(floor_seconds)
    if current_ts < host_floor_not_before_ts:
        selected_candidate["host_pacing_floor_not_before_at"] = datetime.fromtimestamp(
            host_floor_not_before_ts,
            tz=UTC,
        ).isoformat()
        selected_candidate["host_pacing_floor_seconds"] = float(floor_seconds)
        selected_candidate["proactive_outreach_epoch"] = _current_outreach_epoch(state)
        return "proactive_pacing_floor_active"
    return None


def _proactive_expression_block_reason(
    *,
    state: Any,
    selected_candidate: Dict[str, Any],
    verbalized_text: str,
) -> Optional[str]:
    if not verbalized_text:
        return "proactive_template_or_specificity_blocked"
    if _contains_proactive_template_phrase(verbalized_text):
        return "proactive_template_or_specificity_blocked"
    if _question_count(verbalized_text) > 1:
        return "proactive_template_or_specificity_blocked"

    family = str(selected_candidate.get("candidate_family") or "").strip()
    topic_summary = str(selected_candidate.get("topic_summary") or "").strip()
    topic_anchor_summary = str(selected_candidate.get("topic_anchor_summary") or "").strip()
    topic_anchor_summary = str(selected_candidate.get("effective_topic_anchor_summary") or topic_anchor_summary).strip()
    topic_anchor_kind = str(selected_candidate.get("topic_anchor_kind") or "").strip()
    topic_sendability = str(selected_candidate.get("topic_sendability") or "").strip()
    topic_conversation_grade = str(selected_candidate.get("topic_conversation_grade") or "").strip()
    source_draft_text = str(selected_candidate.get("source_draft_text") or "").strip()
    open_question = str(selected_candidate.get("open_question") or "").strip()
    normalized = normalize_proactive_text(verbalized_text)
    if family == "thought_probe":
        if topic_anchor_kind == "prompt_like_request":
            return "proactive_anchor_prompt_like"
        if topic_sendability == "meta_only":
            return "proactive_meta_only_candidate"
        if not topic_anchor_summary:
            return "proactive_topic_unanchored"
        if selected_candidate.get("question_binding_failed"):
            return "proactive_question_not_topic_bound"
        if _looks_like_prompt_echo(verbalized_text, _recent_prompt_like_turn(state)):
            return "proactive_question_echoes_user_prompt"
        if selected_candidate.get("humanization_failed") or _looks_like_abstract_meta_outreach_text(
            verbalized_text,
            topic_anchor=topic_anchor_summary,
        ):
            return "proactive_meta_reflection_not_conversational"
        if topic_conversation_grade == "meta_reflection_only" and (
            selected_candidate.get("rewrite_failed")
            or _looks_like_nonconversational_meta_probe_text(
                verbalized_text,
                topic_anchor=topic_anchor_summary,
            )
        ):
            return "proactive_meta_reflection_not_conversational"
        if not source_draft_text and not topic_summary:
            return "proactive_template_or_specificity_blocked"
        if not source_draft_text and open_question and len(normalized) < 12:
            return "proactive_template_or_specificity_blocked"
        if not _candidate_grounding_bound(verbalized_text, selected_candidate, topic_anchor=topic_anchor_summary):
            return "proactive_topic_unanchored"
    elif len(normalized) < 12:
        return "proactive_template_or_specificity_blocked"
    return None


@dataclass(frozen=True)
class SubjectSystemV1DeliveryBridgeResult:
    status: str
    reason: str
    pending_proactive_followup: Optional[Dict[str, Any]]
    host_proactive_decision: Optional[Dict[str, Any]]
    selected_candidate: Optional[Dict[str, Any]]
    response_plan: Optional[ResponsePlan] = None
    output_verdict: Optional[OutputCheckVerdict] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "pending_proactive_followup": (
                dict(self.pending_proactive_followup or {}) if self.pending_proactive_followup else None
            ),
            "host_proactive_decision": (
                dict(self.host_proactive_decision or {}) if self.host_proactive_decision else None
            ),
            "selected_candidate": dict(self.selected_candidate or {}) if self.selected_candidate else None,
            "response_plan": _serialize_response_plan(self.response_plan),
            "output_verdict": _serialize_output_verdict(self.output_verdict),
        }


def build_pending_proactive_followup_from_subject_system_v1(
    *,
    session_id: str,
    state: Any,
    now_ts: Optional[float] = None,
    subject_system_v1: Optional[Dict[str, Any]] = None,
    host_proactive_decision: Optional[Dict[str, Any]] = None,
) -> SubjectSystemV1DeliveryBridgeResult:
    if hasattr(state, "get_pending_proactive_followup"):
        existing_pending = state.get_pending_proactive_followup()
        if existing_pending:
            return SubjectSystemV1DeliveryBridgeResult(
                status="held",
                reason="pending_followup_exists",
                pending_proactive_followup=existing_pending,
                host_proactive_decision=None,
                selected_candidate=None,
            )

    if _active_task_present(state):
        return SubjectSystemV1DeliveryBridgeResult(
            status="held",
            reason="active_task_present",
            pending_proactive_followup=None,
            host_proactive_decision=None,
            selected_candidate=None,
        )

    subject_payload = dict(subject_system_v1 or get_canonical_subject_system_v1_context(state))
    if not subject_payload:
        return SubjectSystemV1DeliveryBridgeResult(
            status="held",
            reason="subject_system_v1_missing",
            pending_proactive_followup=None,
            host_proactive_decision=None,
            selected_candidate=None,
        )

    decision_payload = dict(
        host_proactive_decision
        or dict(getattr(state, "proto_self_context", None) or {}).get("host_proactive_decision")
        or {}
    )
    if not decision_payload:
        return SubjectSystemV1DeliveryBridgeResult(
            status="held",
            reason="host_proactive_decision_missing",
            pending_proactive_followup=None,
            host_proactive_decision=None,
            selected_candidate=None,
        )

    if str(decision_payload.get("status") or "").strip() != _CANDIDATE_READY:
        return SubjectSystemV1DeliveryBridgeResult(
            status="held",
            reason=f"host_proactive_decision:{decision_payload.get('reason') or decision_payload.get('status') or 'held'}",
            pending_proactive_followup=None,
            host_proactive_decision=decision_payload,
            selected_candidate=None,
        )

    selected_candidate = _build_selected_candidate(
        subject_system_v1=subject_payload,
        host_proactive_decision=decision_payload,
    )
    _normalize_selected_candidate_expression_context(
        state=state,
        selected_candidate=selected_candidate,
    )
    draft_text = _verbalize_subject_system_candidate(
        state=state,
        selected_candidate=selected_candidate,
    )
    if not draft_text:
        duplicate_audit_texts = (
            _trim_text(selected_candidate.get("source_draft_text"), limit=220),
            _candidate_audit_text_for_rejection_reason(selected_candidate),
        )
        for duplicate_audit_text in duplicate_audit_texts:
            if not duplicate_audit_text:
                continue
            duplicate_reason = _duplicate_topic_outreach_reason(
                state,
                selected_candidate,
                verbalized_text=duplicate_audit_text,
            )
            if duplicate_reason:
                return SubjectSystemV1DeliveryBridgeResult(
                    status="held",
                    reason=duplicate_reason,
                    pending_proactive_followup=None,
                    host_proactive_decision=decision_payload,
                    selected_candidate=selected_candidate,
                )
    expression_judge = _evaluate_final_text_candidate(
        state=state,
        selected_candidate=selected_candidate,
        final_text=draft_text,
    )
    selected_candidate["expression_judge"] = dict(expression_judge)
    if expression_judge["status"] != "accepted":
        selected_candidate["retry_later_reason"] = expression_judge["reason"]
        selected_candidate["retry_attempt_count"] = int(selected_candidate.get("retry_attempt_count") or 0) + 1
        selected_candidate["next_retry_after_seconds"] = 300.0
        return SubjectSystemV1DeliveryBridgeResult(
            status=str(expression_judge["status"]),
            reason=str(expression_judge["reason"]),
            pending_proactive_followup=None,
            host_proactive_decision=decision_payload,
            selected_candidate=selected_candidate,
        )
    duplicate_reason = _duplicate_topic_outreach_reason(
        state,
        selected_candidate,
        verbalized_text=draft_text,
    )
    if duplicate_reason:
        return SubjectSystemV1DeliveryBridgeResult(
            status="held",
            reason=duplicate_reason,
            pending_proactive_followup=None,
            host_proactive_decision=decision_payload,
            selected_candidate=selected_candidate,
        )
    pacing_floor_reason = _thought_probe_pacing_floor_reason(
        state,
        selected_candidate,
        now_ts=now_ts,
    )
    if pacing_floor_reason:
        return SubjectSystemV1DeliveryBridgeResult(
            status="held",
            reason=pacing_floor_reason,
            pending_proactive_followup=None,
            host_proactive_decision=decision_payload,
            selected_candidate=selected_candidate,
        )
    expression_block_reason = _proactive_expression_block_reason(
        state=state,
        selected_candidate=selected_candidate,
        verbalized_text=draft_text,
    )
    if expression_block_reason:
        selected_candidate["retry_later_reason"] = expression_block_reason
        selected_candidate["retry_attempt_count"] = int(selected_candidate.get("retry_attempt_count") or 0) + 1
        selected_candidate["next_retry_after_seconds"] = 300.0
        return SubjectSystemV1DeliveryBridgeResult(
            status="retry_later",
            reason=expression_block_reason,
            pending_proactive_followup=None,
            host_proactive_decision=decision_payload,
            selected_candidate=selected_candidate,
        )
    if selected_candidate.get("recent_topic_conversational_fallback_applied"):
        duplicate_reason = _duplicate_topic_outreach_reason(
            state,
            selected_candidate,
            verbalized_text=draft_text,
        )
        if duplicate_reason:
            return SubjectSystemV1DeliveryBridgeResult(
                status="held",
                reason=duplicate_reason,
                pending_proactive_followup=None,
                host_proactive_decision=decision_payload,
                selected_candidate=selected_candidate,
            )
    mode = str(decision_payload.get("mode") or "").strip()
    response_plan = build_direct_response_plan(
        draft_text,
        kind="ask" if mode == "ask" else "chat",
        delivery_kind="chat",
        authority_source="runtime_v2.subject_system_v1_delivery_bridge",
        reply_authority="model_chat",
        metadata={
            "conversation_act": "proactive_followup",
            "reply_origin": "subject_system_v1_proactive",
            "initiative_mode": f"subject_system_v1_{mode or 'candidate'}",
            "initiative_candidate_id": selected_candidate.get("candidate_id"),
            "initiative_source_cycle": selected_candidate.get("source_cycle"),
            "initiative_source_hash": selected_candidate.get("source_candidate_hash"),
            "initiative_score": selected_candidate.get("initiative_score"),
            "chat_expression_hint": {
                "source": "subject_system_v1",
                "mode": mode,
                "candidate_family": selected_candidate.get("candidate_family"),
                "topic_source": selected_candidate.get("topic_source"),
                "message_shape_hint": selected_candidate.get("message_shape_hint"),
            },
            "response_tendency_summary": dict(subject_payload.get("response_tendency") or {}),
            "topic_source": selected_candidate.get("topic_source"),
            "topic_fingerprint": selected_candidate.get("topic_fingerprint"),
            "topic_cluster_ref": selected_candidate.get("topic_cluster_ref"),
            "topic_anchor_summary": selected_candidate.get("topic_anchor_summary"),
            "topic_anchor_source": selected_candidate.get("topic_anchor_source"),
            "topic_anchor_kind": selected_candidate.get("topic_anchor_kind"),
            "topic_binding_mode": selected_candidate.get("topic_binding_mode"),
            "topic_sendability": selected_candidate.get("topic_sendability"),
            "topic_conversation_grade": selected_candidate.get("topic_conversation_grade"),
            "raw_topic_anchor_summary": selected_candidate.get("raw_topic_anchor_summary"),
            "effective_topic_anchor_summary": selected_candidate.get("effective_topic_anchor_summary"),
            "topic_anchor_rebound_source": selected_candidate.get("topic_anchor_rebound_source"),
            "weak_generic_topic_anchor": selected_candidate.get("weak_generic_topic_anchor"),
            "recent_topic_fallback_allowed": selected_candidate.get("recent_topic_fallback_allowed"),
            "recent_topic_conversational_fallback_applied": selected_candidate.get(
                "recent_topic_conversational_fallback_applied"
            ),
            "topic_summary": selected_candidate.get("topic_summary"),
            "message_shape_hint": selected_candidate.get("message_shape_hint"),
            "source_ref": selected_candidate.get("source_ref"),
            "source_draft_text": selected_candidate.get("source_draft_text"),
            "open_question": selected_candidate.get("open_question"),
            "final_text_candidate": selected_candidate.get("final_text_candidate"),
            "language_hint": selected_candidate.get("language_hint"),
            "style_intent": selected_candidate.get("style_intent"),
            "content_grounding": selected_candidate.get("content_grounding"),
            "generation_trace": selected_candidate.get("generation_trace"),
            "expression_judge": selected_candidate.get("expression_judge"),
            "hidden_premise": selected_candidate.get("hidden_premise"),
            "frame_anchor": selected_candidate.get("frame_anchor"),
            "quiet_state": selected_candidate.get("quiet_state"),
            "feedback_signal": selected_candidate.get("feedback_signal"),
            "outreach_reason": selected_candidate.get("outreach_reason"),
            "candidate_family": selected_candidate.get("candidate_family"),
            "zero_template_required": True,
        },
        state=state,
    )
    output_verdict = apply_output_check(response_plan, state)
    delivery_ready = bool(output_verdict.passed and output_verdict.reply_text)
    if not delivery_ready:
        blocked_reason = "output_check_blocked"
        if output_verdict.anti_template_status == "violation":
            blocked_reason = "proactive_template_or_specificity_blocked"
        return SubjectSystemV1DeliveryBridgeResult(
            status="held",
            reason=blocked_reason,
            pending_proactive_followup=None,
            host_proactive_decision=decision_payload,
            selected_candidate=selected_candidate,
            response_plan=response_plan,
            output_verdict=output_verdict,
        )

    created_at = (
        datetime.fromtimestamp(now_ts, tz=UTC).isoformat()
        if now_ts is not None
        else datetime.now(UTC).isoformat()
    )
    idle_seconds = _resolve_idle_seconds(
        state,
        now_ts=now_ts,
        subject_candidate=dict(subject_payload.get("host_proactive_candidate") or {}),
    )
    initiative_verdict = {
        "status": "delivery_ready",
        "reason": output_verdict.reason,
        "delivery_ready": True,
        "draft_reply_text": output_verdict.reply_text,
        "selected_candidate": dict(selected_candidate),
        "response_plan": _serialize_response_plan(response_plan),
        "output_verdict": _serialize_output_verdict(output_verdict),
    }
    timing_contract = _build_timing_contract(
        selected_candidate=selected_candidate,
        now_ts=now_ts,
        idle_seconds=idle_seconds,
    )
    pending_payload = {
        "schema_version": "mvp12.pending_proactive_followup.v1",
        "session_id": session_id,
        "created_at": created_at,
        "idle_seconds": idle_seconds,
        "delivery_status": "pending",
        "proactive_outreach_epoch": _current_outreach_epoch(state),
        "initiative_verdict": initiative_verdict,
        "timing_contract": timing_contract,
        "subject_system_v1_summary": {
            "candidate_family": selected_candidate.get("candidate_family"),
            "proposal_discipline": selected_candidate.get("proposal_discipline"),
            "behavioral_authority": selected_candidate.get("behavioral_authority"),
            "continuity_ref": selected_candidate.get("continuity_ref"),
            "topic_source": selected_candidate.get("topic_source"),
            "topic_fingerprint": selected_candidate.get("topic_fingerprint"),
            "topic_cluster_ref": selected_candidate.get("topic_cluster_ref"),
            "topic_anchor_summary": selected_candidate.get("topic_anchor_summary"),
            "topic_anchor_source": selected_candidate.get("topic_anchor_source"),
            "topic_anchor_kind": selected_candidate.get("topic_anchor_kind"),
            "topic_binding_mode": selected_candidate.get("topic_binding_mode"),
            "topic_sendability": selected_candidate.get("topic_sendability"),
            "topic_conversation_grade": selected_candidate.get("topic_conversation_grade"),
            "raw_topic_anchor_summary": selected_candidate.get("raw_topic_anchor_summary"),
            "effective_topic_anchor_summary": selected_candidate.get("effective_topic_anchor_summary"),
            "topic_anchor_rebound_source": selected_candidate.get("topic_anchor_rebound_source"),
            "weak_generic_topic_anchor": selected_candidate.get("weak_generic_topic_anchor"),
            "recent_topic_fallback_allowed": selected_candidate.get("recent_topic_fallback_allowed"),
            "recent_topic_conversational_fallback_applied": selected_candidate.get(
                "recent_topic_conversational_fallback_applied"
            ),
            "topic_summary": selected_candidate.get("topic_summary"),
            "message_shape_hint": selected_candidate.get("message_shape_hint"),
            "source_ref": selected_candidate.get("source_ref"),
            "final_text_candidate": selected_candidate.get("final_text_candidate"),
            "language_hint": selected_candidate.get("language_hint"),
            "style_intent": selected_candidate.get("style_intent"),
            "content_grounding": selected_candidate.get("content_grounding"),
            "generation_trace": selected_candidate.get("generation_trace"),
            "expression_judge": selected_candidate.get("expression_judge"),
            "timing_mode": ((timing_contract or {}).get("timing_mode")),
            "timing_basis": ((selected_candidate.get("timing_advice") or {}).get("timing_basis")),
            "quiet_state": selected_candidate.get("quiet_state"),
            "feedback_signal": selected_candidate.get("feedback_signal"),
            "outreach_reason": selected_candidate.get("outreach_reason"),
            "host_pacing_floor_not_before_at": selected_candidate.get("host_pacing_floor_not_before_at"),
            "host_pacing_floor_seconds": selected_candidate.get("host_pacing_floor_seconds"),
        },
        "host_proactive_decision": dict(decision_payload),
    }
    if hasattr(state, "set_pending_proactive_followup"):
        state.set_pending_proactive_followup(pending_payload)
    if hasattr(state, "record"):
        state.record(
            "subject_system_v1_proactive_bridge",
            {
                "status": "pending_created",
                "reason": output_verdict.reason,
                "candidate_id": selected_candidate.get("candidate_id"),
                "candidate_family": selected_candidate.get("candidate_family"),
                "mode": mode,
                "topic_fingerprint": selected_candidate.get("topic_fingerprint"),
                "topic_cluster_ref": selected_candidate.get("topic_cluster_ref"),
                "topic_anchor_summary": selected_candidate.get("topic_anchor_summary"),
                "topic_anchor_source": selected_candidate.get("topic_anchor_source"),
                "topic_anchor_kind": selected_candidate.get("topic_anchor_kind"),
                "topic_binding_mode": selected_candidate.get("topic_binding_mode"),
                "topic_sendability": selected_candidate.get("topic_sendability"),
                "topic_conversation_grade": selected_candidate.get("topic_conversation_grade"),
                "timing_mode": (timing_contract or {}).get("timing_mode"),
                "reply_origin": "subject_system_v1_proactive",
                "text_preview": output_verdict.reply_text[:120],
            },
        )
    return SubjectSystemV1DeliveryBridgeResult(
        status="pending_created",
        reason=output_verdict.reason,
        pending_proactive_followup=pending_payload,
        host_proactive_decision=decision_payload,
        selected_candidate=selected_candidate,
        response_plan=response_plan,
        output_verdict=output_verdict,
    )
