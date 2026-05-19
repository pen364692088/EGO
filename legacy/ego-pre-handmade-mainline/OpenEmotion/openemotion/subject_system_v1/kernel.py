from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional

from openemotion.proto_self_v2.self_model_context import extract_runtime_self_model_context
from openemotion.subject_system_v1.schemas import (
    SubjectIdentityInvariants,
    SubjectSystemV1Result,
)


ALLOWED_CANDIDATE_FAMILIES = {
    "commitment_followup",
    "repair_review",
    "bounded_reminder",
    "thought_probe",
}
FAILURE_STATUSES = {"failed", "blocked", "timeout", "error"}
TIMING_ADVICE_SCHEMA_VERSION = "subject_system_v1.timing_advice.v1"
EXPRESSION_CANDIDATE_SCHEMA_VERSION = "subject_system_v1.expression_candidate.v1"
TIMING_DELAY_WINDOW = "delay_window"
TIMING_READINESS_THRESHOLD = "readiness_threshold"
TIMING_BASES = {"continuity", "commitment", "repair", "mixed"}
PROACTIVE_TOPIC_PERMISSION_ALLOW = "long_term_allow"
EXPLICIT_CHAT_FOLLOWUP_SOURCE = "explicit_same_thread_followup_request"
QUIET_STATE_NORMAL = "normal"
QUIET_STATE_REDUCED = "reduced"
QUIET_STATE_PAUSED = "paused"


def _as_dict(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    to_dict = getattr(raw, "to_dict", None)
    if callable(to_dict):
        converted = to_dict()
        if isinstance(converted, dict):
            return dict(converted)
    return {}


def _as_optional_dict(raw: Any) -> Optional[Dict[str, Any]]:
    normalized = _as_dict(raw)
    return normalized or None


def _clamp01(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.0
    return max(0.0, min(1.0, numeric))


def _positive_seconds(value: Any) -> Optional[float]:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric < 0.0:
        return 0.0
    return round(numeric, 1)


def _trim_text(value: Any, *, limit: int = 160) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _detect_language_hint(*values: Any) -> str:
    joined = " ".join(str(value or "") for value in values if str(value or "").strip())
    if not joined:
        return "unknown"
    has_cjk = any("\u4e00" <= char <= "\u9fff" for char in joined)
    has_latin = any(("a" <= char.lower() <= "z") for char in joined)
    if has_cjk and has_latin:
        return "mixed"
    if has_cjk:
        return "zh"
    if has_latin:
        return "en"
    return "unknown"


def _ensure_terminal_punctuation(text: str) -> str:
    if not text:
        return ""
    if text.endswith(("。", "？", "！", ".", "?", "!")):
        return text
    return f"{text}。"


def _shape_final_text_candidate(
    *,
    raw_candidate: Dict[str, Any],
    candidate_family: str,
    topic_anchor_summary: str,
    topic_summary: str,
    draft_text: str,
    open_question: str,
) -> tuple[str, str]:
    explicit = _trim_text(
        raw_candidate.get("final_text_candidate")
        or raw_candidate.get("visible_text_candidate")
        or raw_candidate.get("final_text")
        or "",
        limit=280,
    )
    if explicit:
        return explicit, "provided_final_text_candidate"

    def _topic_bound(final_text: str, method: str) -> tuple[str, str]:
        anchor = _trim_text(topic_anchor_summary, limit=120)
        if candidate_family != "thought_probe" or not anchor or anchor in final_text:
            return final_text, method
        return f"关于“{anchor}”，{final_text}", f"topic_bound_{method}"

    raw_draft = _trim_text(raw_candidate.get("draft_text") or draft_text, limit=240)
    raw_question = _trim_text(raw_candidate.get("open_question") or open_question, limit=160)
    shape = str(raw_candidate.get("message_shape_hint") or "short_view").strip() or "short_view"
    if raw_question and not raw_question.endswith(("？", "?", "。", ".")):
        raw_question = f"{raw_question}？"
    if shape == "question_only" and raw_question:
        return _topic_bound(raw_question, "question_only_candidate")
    if shape == "thought_plus_question" and raw_draft and raw_question:
        if raw_question in raw_draft:
            return _topic_bound(raw_draft, "draft_text_candidate")
        return _topic_bound(
            f"{_ensure_terminal_punctuation(raw_draft)} {raw_question}",
            "draft_plus_question_candidate",
        )
    if raw_draft:
        return _topic_bound(raw_draft, "draft_text_candidate")
    if candidate_family == "thought_probe" and raw_question and topic_summary:
        return _topic_bound(raw_question, "question_only_candidate")
    return "", "missing_final_text_candidate"


def _build_expression_candidate_fields(
    *,
    raw_candidate: Dict[str, Any],
    candidate_family: str,
    topic_anchor_summary: str,
    topic_summary: str,
    source_ref: str,
    draft_text: str,
    open_question: str,
    generation_source: str,
) -> Dict[str, Any]:
    existing_style_intent = _as_dict(raw_candidate.get("style_intent"))
    existing_content_grounding = _as_dict(raw_candidate.get("content_grounding"))
    existing_generation_trace = _as_dict(raw_candidate.get("generation_trace"))
    final_text, method = _shape_final_text_candidate(
        raw_candidate=raw_candidate,
        candidate_family=candidate_family,
        topic_anchor_summary=topic_anchor_summary,
        topic_summary=topic_summary,
        draft_text=draft_text,
        open_question=open_question,
    )
    if not final_text:
        return {
            "language_hint": _detect_language_hint(topic_anchor_summary, topic_summary, draft_text, open_question),
            "style_intent": existing_style_intent or {
                "candidate_family": candidate_family,
                "message_shape_hint": str(raw_candidate.get("message_shape_hint") or ""),
                "question_policy": "default_no_question_for_proactive",
            },
            "content_grounding": existing_content_grounding or {
                "topic_anchor_summary": topic_anchor_summary,
                "topic_summary": topic_summary,
                "source_ref": source_ref,
                "grounding_status": "insufficient_for_final_text",
            },
            "generation_trace": existing_generation_trace or {
                "schema_version": EXPRESSION_CANDIDATE_SCHEMA_VERSION,
                "source": generation_source,
                "method": method,
                "llm_status": "not_called",
            },
        }
    question_count = final_text.count("?") + final_text.count("？")
    return {
        "final_text_candidate": final_text,
        "language_hint": _detect_language_hint(final_text, topic_anchor_summary, topic_summary),
        "style_intent": existing_style_intent or {
            "candidate_family": candidate_family,
            "message_shape_hint": str(raw_candidate.get("message_shape_hint") or ""),
            "question_policy": "one_or_zero_questions",
            "question_count": question_count,
        },
        "content_grounding": existing_content_grounding or {
            "topic_anchor_summary": topic_anchor_summary,
            "topic_summary": topic_summary,
            "source_ref": source_ref,
            "grounding_status": "candidate_grounded" if (topic_anchor_summary or topic_summary or source_ref) else "ungrounded",
        },
        "generation_trace": existing_generation_trace or {
            "schema_version": EXPRESSION_CANDIDATE_SCHEMA_VERSION,
            "source": generation_source,
            "method": method,
            "llm_status": "not_called",
        },
    }


def _bounded_reminder_topic_anchor(
    *,
    runtime_summary: Dict[str, Any],
    initiative_context: Dict[str, Any],
) -> tuple[str, str]:
    recent_dialogue_reflection = _as_dict(runtime_summary.get("recent_dialogue_reflection"))
    topic_anchor_kind = str(recent_dialogue_reflection.get("topic_anchor_kind") or "").strip()
    topic_anchor = _sanitize_topic_anchor_summary(recent_dialogue_reflection.get("topic_anchor"), limit=96)
    if topic_anchor and topic_anchor_kind == "substantive_topic":
        return topic_anchor, str(recent_dialogue_reflection.get("topic_anchor_source") or "recent_dialogue")

    anchor_preview = _sanitize_topic_anchor_summary(initiative_context.get("chat_followup_anchor_preview"), limit=96)
    if not anchor_preview:
        return "", ""
    for marker in (
        "我们继续聊",
        "继续聊",
        "接着聊",
        "围绕",
        "关于",
    ):
        if marker in anchor_preview:
            fragment = anchor_preview.split(marker, 1)[1].strip()
            for tail in (
                "你待会儿",
                "你待会",
                "待会儿",
                "待会",
                "之后",
                "等下",
                "不要等我",
            ):
                fragment = fragment.split(tail, 1)[0].strip()
            fragment = _sanitize_topic_anchor_summary(fragment, limit=96)
            if fragment:
                return fragment, "chat_followup_anchor_preview"
    return anchor_preview, "chat_followup_anchor_preview"


def _build_bounded_reminder_final_text_candidate(
    *,
    runtime_summary: Dict[str, Any],
    initiative_context: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if str(initiative_context.get("chat_followup_source") or "").strip() != EXPLICIT_CHAT_FOLLOWUP_SOURCE:
        return None

    topic_anchor, topic_anchor_source = _bounded_reminder_topic_anchor(
        runtime_summary=runtime_summary,
        initiative_context=initiative_context,
    )
    source_ref = str(initiative_context.get("continuity_ref") or "").strip()
    if topic_anchor:
        final_text = (
            f"我接着刚才的“{topic_anchor}”往前说一个具体看法："
            "关键点在于把目标、反馈和现实约束持续接起来，而不是只在单轮里显得连贯。"
        )
        grounding_status = "candidate_grounded"
    else:
        final_text = (
            "我按刚才的约定接回来：这里最值得继续推进的是把刚才的话题落到一个可验证的下一步，"
            "而不是只停在提醒本身。"
        )
        grounding_status = "continuity_bound_without_topic_anchor"

    return {
        "final_text_candidate": _trim_text(final_text, limit=280),
        "topic_anchor_summary": topic_anchor,
        "topic_anchor_source": topic_anchor_source,
        "topic_summary": topic_anchor,
        "source_ref": source_ref,
        "message_shape_hint": "short_view",
        "content_grounding": {
            "topic_anchor_summary": topic_anchor,
            "topic_summary": topic_anchor,
            "source_ref": source_ref,
            "grounding_status": grounding_status,
        },
        "generation_trace": {
            "schema_version": EXPRESSION_CANDIDATE_SCHEMA_VERSION,
            "source": "openemotion.subject_system_v1.bounded_reminder_followup_synthesis",
            "method": "explicit_same_thread_followup_candidate",
            "llm_status": "not_called",
        },
    }


def _first_clause(value: Any, *, limit: int = 96) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    for separator in ("。", "？", "！", "；", "，", ".", "?", "!", ";", ","):
        text = text.split(separator, 1)[0].strip()
        if text:
            break
    return _trim_text(text, limit=limit)


_TOPIC_IDENTITY_TRANSLATION = str.maketrans(
    {
        "。": " ",
        "，": " ",
        "；": " ",
        "：": " ",
        "！": " ",
        "？": " ",
        ".": " ",
        ",": " ",
        ";": " ",
        ":": " ",
        "!": " ",
        "?": " ",
        "“": " ",
        "”": " ",
        "\"": " ",
        "'": " ",
        "（": " ",
        "）": " ",
        "(": " ",
        ")": " ",
        "[": " ",
        "]": " ",
        "{": " ",
        "}": " ",
        "\n": " ",
        "\r": " ",
        "\t": " ",
    }
)

_META_TOPIC_ANCHOR_EXACT = {
    "前提",
    "这个前提",
    "那个前提",
    "这条判断的前提",
    "判断",
    "这个判断",
    "那个判断",
    "这条判断",
    "问题",
    "这个问题",
    "那个问题",
    "问题本身",
    "边界",
    "定义",
}
_WEAK_GENERIC_TOPIC_ANCHOR_EXACT = {
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
}
_THOUGHT_PROBE_META_REFLECTION_MARKERS = (
    "判断",
    "前提",
    "问题",
    "边界",
    "定义",
    "默认",
    "成立",
    "展开",
)
_META_REFERENCE_REPLACEMENTS = (
    ("表面上的判断", "“{anchor}”这个判断"),
    ("这条判断的前提", "“{anchor}”这个判断背后的前提"),
    ("这条判断", "“{anchor}”这个判断"),
    ("这个判断", "“{anchor}”这个判断"),
    ("那个判断", "“{anchor}”这个判断"),
    ("这个问题", "“{anchor}”这个问题"),
    ("那个问题", "“{anchor}”这个问题"),
    ("问题本身", "“{anchor}”这个问题本身"),
)


def _normalize_topic_seed_fragment(value: Any, *, limit: int = 120) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    normalized = " ".join(text.translate(_TOPIC_IDENTITY_TRANSLATION).split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip()


def _sanitize_topic_anchor_summary(value: Any, *, limit: int = 96) -> str:
    text = _first_clause(value, limit=limit).strip()
    return text.rstrip("。！？?!,.，；;：: ").strip()


def _is_meta_topic_anchor(value: Any) -> bool:
    normalized = _normalize_topic_seed_fragment(value, limit=96)
    if not normalized:
        return True
    return normalized in _META_TOPIC_ANCHOR_EXACT


def _is_weak_generic_topic_anchor(value: Any) -> bool:
    normalized = _normalize_topic_seed_fragment(value, limit=96)
    if not normalized:
        return False
    if normalized in _WEAK_GENERIC_TOPIC_ANCHOR_EXACT:
        return True
    if len(normalized) <= 12 and any(marker in normalized for marker in _WEAK_GENERIC_TOPIC_ANCHOR_EXACT):
        return True
    return "能力" in normalized and ("如何实现" in normalized or "怎么实现" in normalized) and len(normalized) <= 18


def _bind_meta_reference_to_anchor(text: Any, *, topic_anchor_summary: str) -> str:
    body = _trim_text(text, limit=220)
    anchor = _sanitize_topic_anchor_summary(topic_anchor_summary, limit=96)
    if not body or not anchor:
        return body
    rewritten = body
    for source, replacement in _META_REFERENCE_REPLACEMENTS:
        rewritten = rewritten.replace(source, replacement.format(anchor=anchor))
    if f"“{anchor}”" in rewritten or anchor in rewritten:
        return rewritten
    return f"关于“{anchor}”，{rewritten}"


def _resolve_thought_probe_binding(
    thought_candidate: Dict[str, Any],
    recent_dialogue_reflection: Dict[str, Any],
) -> Dict[str, str]:
    recent_topic_kind = str(recent_dialogue_reflection.get("topic_anchor_kind") or "").strip() or "none"
    recent_topic_source = str(recent_dialogue_reflection.get("topic_anchor_source") or "").strip() or "none"
    recent_topic_anchor = _sanitize_topic_anchor_summary(recent_dialogue_reflection.get("topic_anchor"), limit=120)
    if recent_topic_kind != "substantive_topic":
        recent_topic_anchor = ""
    candidate_anchor = _sanitize_topic_anchor_summary(thought_candidate.get("frame_anchor"), limit=96)
    candidate_anchor_is_weak = _is_weak_generic_topic_anchor(candidate_anchor)
    free_jump = _is_free_jump_candidate(thought_candidate, recent_dialogue_reflection)

    if free_jump and candidate_anchor and not _is_meta_topic_anchor(candidate_anchor) and not candidate_anchor_is_weak:
        return {
            "topic_anchor_summary": candidate_anchor,
            "topic_binding_mode": "free_jump_candidate",
            "topic_sendability": "free_jump_topic",
            "topic_anchor_source": "free_jump_candidate",
            "topic_anchor_kind": "substantive_topic",
        }
    if recent_topic_anchor:
        binding = {
            "topic_anchor_summary": recent_topic_anchor,
            "topic_binding_mode": "recent_topic",
            "topic_sendability": "anchored_topic",
            "topic_anchor_source": recent_topic_source,
            "topic_anchor_kind": recent_topic_kind,
        }
        if candidate_anchor_is_weak:
            binding.update(
                {
                    "raw_topic_anchor_summary": candidate_anchor,
                    "effective_topic_anchor_summary": recent_topic_anchor,
                    "topic_anchor_rebound_source": "recent_substantive_topic",
                    "weak_generic_topic_anchor": True,
                    "recent_topic_fallback_allowed": True,
                }
            )
        return binding
    if candidate_anchor and not _is_meta_topic_anchor(candidate_anchor) and not candidate_anchor_is_weak:
        return {
            "topic_anchor_summary": candidate_anchor,
            "topic_binding_mode": "free_jump_candidate",
            "topic_sendability": "free_jump_topic",
            "topic_anchor_source": "free_jump_candidate",
            "topic_anchor_kind": "substantive_topic",
        }
    if candidate_anchor and candidate_anchor_is_weak:
        return {
            "topic_anchor_summary": candidate_anchor,
            "raw_topic_anchor_summary": candidate_anchor,
            "effective_topic_anchor_summary": "",
            "topic_anchor_rebound_source": "",
            "topic_binding_mode": "none",
            "topic_sendability": "meta_only",
            "topic_anchor_source": "free_jump_candidate",
            "topic_anchor_kind": "substantive_topic",
            "weak_generic_topic_anchor": True,
            "recent_topic_fallback_allowed": False,
        }
    return {
        "topic_anchor_summary": "",
        "topic_binding_mode": "none",
        "topic_sendability": "meta_only",
        "topic_anchor_source": recent_topic_source if recent_topic_kind == "prompt_like_request" else "none",
        "topic_anchor_kind": recent_topic_kind if recent_topic_kind == "prompt_like_request" else "none",
    }


def _looks_like_meta_reflection_text(value: Any) -> bool:
    normalized = _normalize_topic_seed_fragment(value, limit=180)
    if not normalized:
        return True
    return any(marker in normalized for marker in _THOUGHT_PROBE_META_REFLECTION_MARKERS)


def _classify_thought_probe_conversation_grade(
    thought_candidate: Dict[str, Any],
    binding: Dict[str, str],
) -> str:
    if str(binding.get("topic_sendability") or "").strip() == "meta_only":
        return "meta_reflection_only"
    frame_anchor = _sanitize_topic_anchor_summary(thought_candidate.get("frame_anchor"), limit=96)
    if not _is_meta_topic_anchor(frame_anchor) and not _is_weak_generic_topic_anchor(frame_anchor):
        return "conversational"
    text_fields = [
        thought_candidate.get("hidden_premise"),
        thought_candidate.get("draft_text"),
        thought_candidate.get("open_question"),
    ]
    populated = [value for value in text_fields if str(value or "").strip()]
    if not populated:
        return "meta_reflection_only"
    if all(_looks_like_meta_reflection_text(value) for value in populated):
        return "meta_reflection_only"
    return "conversational"


def _analyze_thought_probe_candidates(
    thought_candidates: list[Dict[str, Any]],
    *,
    initiative_context: Dict[str, Any],
    recent_dialogue_reflection: Dict[str, Any],
) -> Dict[str, Optional[Dict[str, Any]]]:
    quiet_state = str(initiative_context.get("quiet_state") or "").strip()
    last_sent_source_ref = str(initiative_context.get("last_sent_proactive_source_ref") or "").strip()
    sent_topic_fingerprints = {
        str(value or "").strip()
        for value in list(initiative_context.get("sent_topic_fingerprints_since_user_turn") or [])
        if str(value or "").strip()
    }
    sent_topic_clusters = {
        str(value or "").strip()
        for value in list(initiative_context.get("sent_topic_clusters_since_user_turn") or [])
        if str(value or "").strip()
    }
    ranked: list[tuple[int, int, float, Dict[str, Any]]] = []
    first_meta_only: Optional[Dict[str, Any]] = None
    first_unanchored: Optional[Dict[str, Any]] = None
    for candidate in _compress_thought_candidates_by_cluster(thought_candidates):
        normalized = _as_dict(candidate)
        if not normalized:
            continue
        if not bool(normalized.get("delivery_ready")):
            continue
        if not str(normalized.get("draft_text") or "").strip():
            continue
        source_hash = str(normalized.get("source_candidate_hash") or normalized.get("candidate_id") or "").strip()
        if not source_hash:
            continue
        source_ref = f"internal_reflection:{source_hash}"
        if last_sent_source_ref and source_ref == last_sent_source_ref:
            continue
        if str(normalized.get("topic_cluster_ref") or "").strip() in sent_topic_clusters:
            continue
        if str(normalized.get("topic_fingerprint") or "").strip() in sent_topic_fingerprints:
            continue
        binding = _resolve_thought_probe_binding(normalized, recent_dialogue_reflection)
        normalized.update(binding)
        normalized["topic_conversation_grade"] = _classify_thought_probe_conversation_grade(normalized, binding)
        if binding["topic_sendability"] == "meta_only":
            raw_anchor = _sanitize_topic_anchor_summary(
                normalized.get("frame_anchor") or normalized.get("hidden_premise"),
                limit=96,
            )
            if raw_anchor:
                first_meta_only = first_meta_only or dict(normalized)
            else:
                first_unanchored = first_unanchored or dict(normalized)
            continue
        initiative_score = round(_clamp01(normalized.get("initiative_score")), 3)
        if quiet_state == QUIET_STATE_REDUCED and initiative_score < 0.72:
            continue
        binding_mode = str(binding.get("topic_binding_mode") or "").strip()
        weak_generic_anchor = bool(normalized.get("weak_generic_topic_anchor"))
        binding_priority = 0
        if binding_mode == "recent_topic" and not weak_generic_anchor:
            binding_priority = 2
        elif binding_mode in {"recent_topic", "free_jump_candidate"}:
            binding_priority = 1
        ranked.append(
            (
                1 if normalized["topic_conversation_grade"] == "conversational" else 0,
                binding_priority,
                initiative_score,
                normalized,
            )
        )
    if not ranked:
        return {
            "selected": None,
            "blocked_meta_only": first_meta_only,
            "blocked_unanchored": first_unanchored,
        }
    ranked.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    return {
        "selected": ranked[0][3],
        "blocked_meta_only": first_meta_only,
        "blocked_unanchored": first_unanchored,
    }


def _build_thought_probe_topic_identity(thought_candidate: Dict[str, Any]) -> Dict[str, str]:
    seed_parts = [
        _normalize_topic_seed_fragment(thought_candidate.get("frame_kind"), limit=48),
        _normalize_topic_seed_fragment(thought_candidate.get("frame_anchor"), limit=96),
        _normalize_topic_seed_fragment(thought_candidate.get("hidden_premise"), limit=120),
        _normalize_topic_seed_fragment(thought_candidate.get("open_question"), limit=120),
    ]
    if not any(seed_parts[1:]):
        seed_parts[2] = _normalize_topic_seed_fragment(_first_clause(thought_candidate.get("draft_text"), limit=120))
    seed = "||".join(seed_parts).strip("|")
    if not seed:
        seed = _normalize_topic_seed_fragment(thought_candidate.get("source_candidate_hash") or thought_candidate.get("candidate_id"))
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return {
        "topic_fingerprint": f"thought_topic:{digest[:20]}",
        "topic_cluster_ref": f"thought_cluster:{digest[:16]}",
    }


def _normalize_timing_advice(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    timing_advice = _as_dict(raw.get("timing_advice"))
    if not timing_advice:
        return None
    timing_mode = str(timing_advice.get("timing_mode") or "").strip()
    if timing_mode not in {TIMING_DELAY_WINDOW, TIMING_READINESS_THRESHOLD}:
        return None

    normalized = {
        "schema_version": str(timing_advice.get("schema_version") or TIMING_ADVICE_SCHEMA_VERSION),
        "timing_mode": timing_mode,
        "earliest_send_after_seconds": _positive_seconds(timing_advice.get("earliest_send_after_seconds")),
        "preferred_send_after_seconds": _positive_seconds(timing_advice.get("preferred_send_after_seconds")),
        "latest_send_after_seconds": _positive_seconds(timing_advice.get("latest_send_after_seconds")),
        "readiness_score": None,
        "readiness_threshold": None,
        "timing_basis": str(timing_advice.get("timing_basis") or "mixed"),
        "timing_confidence": round(_clamp01(timing_advice.get("timing_confidence")), 3),
    }
    if normalized["timing_basis"] not in TIMING_BASES:
        normalized["timing_basis"] = "mixed"
    if timing_mode == TIMING_READINESS_THRESHOLD:
        if timing_advice.get("readiness_score") is not None:
            normalized["readiness_score"] = round(_clamp01(timing_advice.get("readiness_score")), 3)
        if timing_advice.get("readiness_threshold") is not None:
            normalized["readiness_threshold"] = round(_clamp01(timing_advice.get("readiness_threshold")), 3)
    return normalized


def _normalize_identity_invariants(runtime_summary: Dict[str, Any]) -> SubjectIdentityInvariants:
    projection = extract_runtime_self_model_context(runtime_summary)
    return SubjectIdentityInvariants(
        identity_handle=str(projection.get("identity_handle") or ""),
        tool_authority_boundary=dict(projection.get("tool_authority_boundary") or {}),
        limitations=list(projection.get("limitations") or []),
        active_goals=list(projection.get("active_goals") or []),
        standing_commitments=list(projection.get("standing_commitments") or []),
        confidence_by_domain=dict(projection.get("confidence_by_domain") or {}),
    )


def _normalize_text(value: Any) -> str:
    return "".join(str(value or "").strip().lower().split())


def _is_free_jump_candidate(
    thought_candidate: Dict[str, Any],
    recent_dialogue_reflection: Dict[str, Any],
) -> bool:
    topic_anchor = _normalize_text(recent_dialogue_reflection.get("topic_anchor"))
    frame_anchor = _normalize_text(
        thought_candidate.get("frame_anchor")
        or thought_candidate.get("hidden_premise")
        or thought_candidate.get("draft_text")
    )
    if not topic_anchor or not frame_anchor:
        return False
    return topic_anchor not in frame_anchor and frame_anchor not in topic_anchor


def _compress_thought_candidates_by_cluster(
    thought_candidates: list[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    clustered: Dict[str, tuple[float, int, Dict[str, Any]]] = {}
    for index, candidate in enumerate(thought_candidates):
        normalized = _as_dict(candidate)
        if not normalized:
            continue
        topic_identity = _build_thought_probe_topic_identity(normalized)
        normalized.update(topic_identity)
        cluster_ref = str(normalized.get("topic_cluster_ref") or "").strip()
        if not cluster_ref:
            continue
        initiative_score = round(_clamp01(normalized.get("initiative_score")), 3)
        current = clustered.get(cluster_ref)
        if current is None or initiative_score > current[0]:
            clustered[cluster_ref] = (initiative_score, index, normalized)
    return [item[2] for item in sorted(clustered.values(), key=lambda item: item[1])]


def _select_thought_probe_candidate(
    thought_candidates: list[Dict[str, Any]],
    *,
    initiative_context: Dict[str, Any],
    recent_dialogue_reflection: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    return _analyze_thought_probe_candidates(
        thought_candidates,
        initiative_context=initiative_context,
        recent_dialogue_reflection=recent_dialogue_reflection,
    ).get("selected")


def _build_thought_probe_timing_advice(
    thought_candidate: Dict[str, Any],
    initiative_context: Dict[str, Any],
) -> Dict[str, Any]:
    initiative_score = _clamp01(thought_candidate.get("initiative_score"))
    quiet_state = str(initiative_context.get("quiet_state") or QUIET_STATE_NORMAL).strip() or QUIET_STATE_NORMAL
    feedback_signal = str(initiative_context.get("feedback_signal") or "").strip()
    if quiet_state == QUIET_STATE_REDUCED or feedback_signal == "inferred_cooling":
        earliest = max(900.0, min(1800.0, 1500.0 - (initiative_score * 360.0)))
        preferred = min(earliest + 420.0, 2400.0)
        latest = preferred + 2400.0
        timing_confidence = 0.5 + (initiative_score * 0.18)
    else:
        earliest = max(180.0, min(540.0, 420.0 - (initiative_score * 180.0)))
        if feedback_signal == "inferred_reengaged":
            earliest = max(180.0, earliest - 60.0)
        preferred = min(earliest + 180.0, 960.0)
        latest = preferred + 1800.0
        timing_confidence = 0.56 + (initiative_score * 0.26)
    return {
        "schema_version": TIMING_ADVICE_SCHEMA_VERSION,
        "timing_mode": TIMING_DELAY_WINDOW,
        "earliest_send_after_seconds": _positive_seconds(earliest),
        "preferred_send_after_seconds": _positive_seconds(preferred),
        "latest_send_after_seconds": _positive_seconds(latest),
        "readiness_score": None,
        "readiness_threshold": None,
        "timing_basis": "mixed",
        "timing_confidence": round(_clamp01(timing_confidence), 3),
    }


def _build_thought_probe_timing_reasoning_trace(
    thought_candidate: Dict[str, Any],
    timing_advice: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "schema_version": "subject_system_v1.timing_reasoning_trace.v1",
        "candidate_family": "thought_probe",
        "timing_mode": str(timing_advice.get("timing_mode") or ""),
        "timing_basis": str(timing_advice.get("timing_basis") or "mixed"),
        "initiative_score": round(_clamp01(thought_candidate.get("initiative_score")), 3),
        "frame_kind": str(thought_candidate.get("frame_kind") or ""),
        "frame_anchor": str(thought_candidate.get("frame_anchor") or ""),
        "hidden_premise": _first_clause(thought_candidate.get("hidden_premise"), limit=72),
    }


def _synthesize_thought_probe_candidate(
    proto_self_result: Dict[str, Any],
    runtime_summary: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    initiative_context = _as_dict(runtime_summary.get("initiative_context"))
    proactive_topic_permission = str(initiative_context.get("proactive_topic_permission") or "").strip()
    if proactive_topic_permission != PROACTIVE_TOPIC_PERMISSION_ALLOW:
        return None
    quiet_state = str(initiative_context.get("quiet_state") or QUIET_STATE_NORMAL).strip() or QUIET_STATE_NORMAL
    if quiet_state == QUIET_STATE_PAUSED:
        return None

    developmental_summary = _as_dict(proto_self_result.get("developmental_summary"))
    thought_candidates = list(developmental_summary.get("background_thought_candidates") or [])
    recent_dialogue_reflection = _as_dict(runtime_summary.get("recent_dialogue_reflection"))
    analysis = _analyze_thought_probe_candidates(
        thought_candidates,
        initiative_context=initiative_context,
        recent_dialogue_reflection=recent_dialogue_reflection,
    )
    selected = analysis.get("selected")
    if selected is None:
        return None

    source_hash = str(selected.get("source_candidate_hash") or selected.get("candidate_id") or "").strip()
    if not source_hash:
        return None

    topic_summary = (
        _first_clause(selected.get("hidden_premise"))
        or _first_clause(selected.get("frame_anchor"))
        or _first_clause(selected.get("draft_text"))
    )
    open_question = _trim_text(selected.get("open_question"), limit=140)
    draft_text = _trim_text(selected.get("draft_text"), limit=220)
    if open_question and not open_question.endswith(("？", "?", "。", ".")):
        open_question = f"{open_question}？"
    if draft_text and open_question:
        message_shape_hint = "thought_plus_question"
    elif open_question:
        message_shape_hint = "question_only"
    else:
        message_shape_hint = "short_view"

    timing_advice = _build_thought_probe_timing_advice(selected, initiative_context)
    outreach_reason = (
        "free_jump_internal_reflection"
        if _is_free_jump_candidate(selected, recent_dialogue_reflection)
        else "topic_deepening_internal_reflection"
    )
    candidate_payload = {
        "candidate_id": f"thought_probe:{source_hash}",
        "candidate_label": "governed_self_initiated_topic_outreach",
        "candidate_family": "thought_probe",
        "proposal_discipline": "proposal_only",
        "behavioral_authority": "none",
        "topic_source": "internal_reflection",
        "topic_fingerprint": str(selected.get("topic_fingerprint") or ""),
        "topic_cluster_ref": str(selected.get("topic_cluster_ref") or ""),
        "topic_anchor_summary": str(selected.get("topic_anchor_summary") or ""),
        "topic_anchor_source": str(selected.get("topic_anchor_source") or ""),
        "topic_anchor_kind": str(selected.get("topic_anchor_kind") or ""),
        "topic_binding_mode": str(selected.get("topic_binding_mode") or ""),
        "topic_sendability": str(selected.get("topic_sendability") or ""),
        "topic_conversation_grade": str(selected.get("topic_conversation_grade") or "conversational"),
        "raw_topic_anchor_summary": str(selected.get("raw_topic_anchor_summary") or ""),
        "effective_topic_anchor_summary": str(selected.get("effective_topic_anchor_summary") or ""),
        "topic_anchor_rebound_source": str(selected.get("topic_anchor_rebound_source") or ""),
        "weak_generic_topic_anchor": bool(selected.get("weak_generic_topic_anchor")),
        "recent_topic_fallback_allowed": bool(selected.get("recent_topic_fallback_allowed")),
        "topic_summary": topic_summary,
        "message_shape_hint": message_shape_hint,
        "source_ref": f"internal_reflection:{source_hash}",
        "source_candidate_hash": source_hash,
        "frame_anchor": _trim_text(selected.get("frame_anchor"), limit=96),
        "hidden_premise": _trim_text(selected.get("hidden_premise"), limit=160),
        "draft_text": draft_text,
        "open_question": open_question,
        "initiative_score": round(_clamp01(selected.get("initiative_score")), 3),
        "continuity_ref": f"internal_reflection:{source_hash}",
        "continuity_basis": f"internal_reflection:{source_hash}",
        "proactive_topic_permission": proactive_topic_permission,
        "quiet_state": quiet_state,
        "quiet_until": initiative_context.get("quiet_until"),
        "outreach_aggression_mode": str(initiative_context.get("outreach_aggression_mode") or ""),
        "outreach_feedback_adaptation": str(initiative_context.get("outreach_feedback_adaptation") or ""),
        "feedback_signal": str(initiative_context.get("feedback_signal") or ""),
        "outreach_reason": outreach_reason,
        "timing_advice": timing_advice,
        "timing_reasoning_trace": _build_thought_probe_timing_reasoning_trace(selected, timing_advice),
    }
    candidate_payload.update(
        _build_expression_candidate_fields(
            raw_candidate=candidate_payload,
            candidate_family="thought_probe",
            topic_anchor_summary=str(candidate_payload.get("topic_anchor_summary") or ""),
            topic_summary=str(candidate_payload.get("topic_summary") or ""),
            source_ref=str(candidate_payload.get("source_ref") or ""),
            draft_text=draft_text,
            open_question=open_question,
            generation_source="openemotion.subject_system_v1.thought_probe_synthesis",
        )
    )
    return candidate_payload


def _infer_candidate_family(
    *,
    raw_candidate: Dict[str, Any],
    initiative_context: Dict[str, Any],
    commitment_execution_snapshot: Dict[str, Any],
    initiative_policy_hints: Dict[str, Any],
) -> str:
    explicit = str(raw_candidate.get("candidate_family") or "").strip()
    if explicit in ALLOWED_CANDIDATE_FAMILIES:
        return explicit

    trigger = str(initiative_context.get("initiative_trigger") or "").strip()
    if trigger in ALLOWED_CANDIDATE_FAMILIES:
        return trigger

    delivery_bias = str(initiative_policy_hints.get("delivery_bias") or "").strip()
    blocked_commitment_refs = list(initiative_context.get("blocked_commitment_refs") or [])
    recent_delivery_status = str(commitment_execution_snapshot.get("recent_delivery_status") or "").strip().lower()
    commitment_mode = str(commitment_execution_snapshot.get("commitment_mode") or "").strip()

    if blocked_commitment_refs or delivery_bias == "repair_review" or recent_delivery_status in FAILURE_STATUSES:
        return "repair_review"
    if commitment_mode in {"blocked", "repair"}:
        return "repair_review"
    if int(commitment_execution_snapshot.get("active_commitments_count") or 0) > 0:
        return "commitment_followup"
    return "bounded_reminder"


def _normalize_host_proactive_candidate(
    proto_self_result: Dict[str, Any],
    runtime_summary: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    raw_candidate = _as_dict(proto_self_result.get("host_proactive_candidate"))
    if not raw_candidate:
        raw_candidate = _synthesize_thought_probe_candidate(proto_self_result, runtime_summary) or {}
    if not raw_candidate:
        return None

    trace_payload = _as_dict(proto_self_result.get("trace_payload"))
    initiative_context = {
        **_as_dict(runtime_summary.get("initiative_context")),
        **_as_dict(trace_payload.get("initiative_context")),
    }
    selfhood_context = _as_dict(trace_payload.get("selfhood_integration_context"))
    commitment_execution_snapshot = _as_dict(proto_self_result.get("commitment_execution_snapshot"))
    initiative_policy_hints = _as_dict(proto_self_result.get("initiative_policy_hints"))
    developmental_continuity_snapshot = _as_dict(proto_self_result.get("developmental_continuity_snapshot"))

    continuity_confidence = _clamp01(
        commitment_execution_snapshot.get("continuity_confidence")
        or initiative_context.get("continuity_confidence")
        or developmental_continuity_snapshot.get("identity_preservation_confidence")
        or developmental_continuity_snapshot.get("continuity_score")
    )
    recent_delivery_status = str(commitment_execution_snapshot.get("recent_delivery_status") or "").strip().lower()
    delivery_failure = bool(initiative_context.get("delivery_failure")) or recent_delivery_status in FAILURE_STATUSES
    selfhood_priority = str(
        selfhood_context.get("selected_priority")
        or _as_dict(proto_self_result.get("cross_axis_priority_snapshot")).get("selected_priority")
        or _as_dict(proto_self_result.get("integrated_policy_hints")).get("integrated_priority")
        or ""
    )
    candidate_family = _infer_candidate_family(
        raw_candidate=raw_candidate,
        initiative_context=initiative_context,
        commitment_execution_snapshot=commitment_execution_snapshot,
        initiative_policy_hints=initiative_policy_hints,
    )
    if (
        candidate_family == "bounded_reminder"
        and not str(raw_candidate.get("final_text_candidate") or "").strip()
        and not str(raw_candidate.get("visible_text_candidate") or "").strip()
        and not str(raw_candidate.get("final_text") or "").strip()
    ):
        bounded_expression = _build_bounded_reminder_final_text_candidate(
            runtime_summary=runtime_summary,
            initiative_context=initiative_context,
        )
        if bounded_expression:
            raw_candidate = {**raw_candidate, **bounded_expression}

    normalized = dict(raw_candidate)
    normalized["candidate_family"] = candidate_family
    normalized["proposal_discipline"] = str(raw_candidate.get("proposal_discipline") or "proposal_only")
    normalized["behavioral_authority"] = str(raw_candidate.get("behavioral_authority") or "none")
    normalized["continuity_ref"] = str(
        raw_candidate.get("continuity_ref")
        or raw_candidate.get("continuity_basis")
        or initiative_context.get("continuity_ref")
        or ""
    )
    normalized["continuity_confidence"] = round(continuity_confidence, 3)
    normalized["delivery_failure"] = delivery_failure
    normalized["selfhood_priority"] = selfhood_priority
    normalized["idle_seconds"] = float(initiative_context.get("idle_seconds") or 0.0)
    normalized["runtime_projection_source"] = str(runtime_summary.get("self_model_context_source") or "")
    normalized["timing_advice"] = _normalize_timing_advice(raw_candidate)
    normalized["timing_reasoning_trace"] = _as_optional_dict(raw_candidate.get("timing_reasoning_trace"))
    if candidate_family == "thought_probe":
        normalized["continuity_confidence"] = round(
            max(
                continuity_confidence,
                _clamp01(raw_candidate.get("initiative_score")),
                _clamp01(raw_candidate.get("timing_advice", {}).get("timing_confidence")),
            ),
            3,
        )
        normalized["topic_source"] = str(raw_candidate.get("topic_source") or "internal_reflection")
        normalized["topic_fingerprint"] = str(raw_candidate.get("topic_fingerprint") or "")
        normalized["topic_cluster_ref"] = str(raw_candidate.get("topic_cluster_ref") or "")
        normalized["topic_anchor_summary"] = str(raw_candidate.get("topic_anchor_summary") or "")
        normalized["raw_topic_anchor_summary"] = str(raw_candidate.get("raw_topic_anchor_summary") or "")
        normalized["effective_topic_anchor_summary"] = str(raw_candidate.get("effective_topic_anchor_summary") or "")
        normalized["topic_anchor_rebound_source"] = str(raw_candidate.get("topic_anchor_rebound_source") or "")
        normalized["weak_generic_topic_anchor"] = bool(raw_candidate.get("weak_generic_topic_anchor"))
        normalized["recent_topic_fallback_allowed"] = bool(raw_candidate.get("recent_topic_fallback_allowed"))
        normalized["topic_binding_mode"] = str(raw_candidate.get("topic_binding_mode") or "")
        normalized["topic_sendability"] = str(raw_candidate.get("topic_sendability") or "")
        normalized["topic_summary"] = str(raw_candidate.get("topic_summary") or "")
        normalized["message_shape_hint"] = str(raw_candidate.get("message_shape_hint") or "short_view")
        normalized["source_ref"] = str(raw_candidate.get("source_ref") or normalized["continuity_ref"])
        normalized["draft_text"] = str(raw_candidate.get("draft_text") or "")
        normalized["open_question"] = str(raw_candidate.get("open_question") or "")
        normalized["initiative_score"] = round(_clamp01(raw_candidate.get("initiative_score")), 3)
        normalized["proactive_topic_permission"] = str(raw_candidate.get("proactive_topic_permission") or "")
        normalized["quiet_state"] = str(raw_candidate.get("quiet_state") or "")
        normalized["quiet_until"] = raw_candidate.get("quiet_until")
        normalized["outreach_aggression_mode"] = str(raw_candidate.get("outreach_aggression_mode") or "")
        normalized["outreach_feedback_adaptation"] = str(raw_candidate.get("outreach_feedback_adaptation") or "")
        normalized["feedback_signal"] = str(raw_candidate.get("feedback_signal") or "")
        normalized["outreach_reason"] = str(raw_candidate.get("outreach_reason") or "")
    expression_fields = _build_expression_candidate_fields(
        raw_candidate=raw_candidate,
        candidate_family=candidate_family,
        topic_anchor_summary=str(
            normalized.get("topic_anchor_summary")
            or raw_candidate.get("topic_anchor_summary")
            or ""
        ),
        topic_summary=str(normalized.get("topic_summary") or raw_candidate.get("topic_summary") or ""),
        source_ref=str(normalized.get("source_ref") or normalized.get("continuity_ref") or ""),
        draft_text=str(raw_candidate.get("draft_text") or ""),
        open_question=str(raw_candidate.get("open_question") or ""),
        generation_source="openemotion.subject_system_v1.normalize_host_proactive_candidate",
    )
    normalized.update(expression_fields)
    return normalized


def _build_trace_payload(
    proto_self_result: Dict[str, Any],
    runtime_summary: Dict[str, Any],
) -> Dict[str, Any]:
    raw_trace = _as_dict(proto_self_result.get("trace_payload"))
    commitment_execution_snapshot = _as_dict(proto_self_result.get("commitment_execution_snapshot"))
    developmental_continuity_snapshot = _as_dict(proto_self_result.get("developmental_continuity_snapshot"))
    trace_payload: Dict[str, Any] = {
        "schema_version": "subject_system_v1.trace_payload.v1",
        "source_trace_schema_version": str(raw_trace.get("schema_version") or ""),
        "event_id": str(proto_self_result.get("event_id") or raw_trace.get("event_id") or ""),
        "update_packet_hash": str(raw_trace.get("update_packet_hash") or ""),
        "subject_profile": str(proto_self_result.get("subject_profile") or ""),
        "self_model_context_source": str(runtime_summary.get("self_model_context_source") or ""),
        "initiative_context": {
            key: value
            for key, value in {
                **_as_dict(runtime_summary.get("initiative_context")),
                **_as_dict(raw_trace.get("initiative_context")),
            }.items()
            if key
            in {
                "initiative_trigger",
                "continuity_ref",
                "continuity_confidence",
                "selected_priority",
                "idle_seconds",
                "chat_followup_source",
                "chat_followup_inferred",
                "explicit_followup_text_matched",
                "pending_commitment_source",
                "proactive_topic_permission",
                "outreach_aggression_mode",
                "outreach_feedback_adaptation",
                "quiet_state",
                "quiet_until",
                "feedback_signal",
                "last_sent_proactive_source_ref",
                "sent_topic_fingerprints_since_user_turn",
                "sent_topic_clusters_since_user_turn",
            }
        },
        "selfhood_integration_context": {
            key: value
            for key, value in _as_dict(raw_trace.get("selfhood_integration_context")).items()
            if key in {"selected_priority", "highest_conflict_severity"}
        },
        "host_proactive_context": {
            key: value
            for key, value in _as_dict(raw_trace.get("host_proactive_context")).items()
            if key in {"source", "host_lane_hint", "delivery_readiness", "readiness_basis"}
        },
    }
    continuity_confidence = _clamp01(
        commitment_execution_snapshot.get("continuity_confidence")
        or developmental_continuity_snapshot.get("identity_preservation_confidence")
        or developmental_continuity_snapshot.get("continuity_score")
    )
    if continuity_confidence:
        trace_payload["continuity_confidence"] = round(continuity_confidence, 3)
    normalized_candidate = _normalize_host_proactive_candidate(proto_self_result, runtime_summary)
    if normalized_candidate:
        host_proactive_context = dict(trace_payload.get("host_proactive_context") or {})
        if normalized_candidate.get("timing_advice"):
            host_proactive_context["timing_advice"] = dict(normalized_candidate.get("timing_advice") or {})
        if normalized_candidate.get("timing_reasoning_trace"):
            host_proactive_context["timing_reasoning_trace"] = dict(
                normalized_candidate.get("timing_reasoning_trace") or {}
            )
        for key in (
            "candidate_family",
            "topic_source",
            "topic_fingerprint",
            "topic_cluster_ref",
            "topic_anchor_summary",
            "topic_anchor_source",
            "topic_anchor_kind",
            "topic_binding_mode",
            "topic_sendability",
            "topic_conversation_grade",
            "raw_topic_anchor_summary",
            "effective_topic_anchor_summary",
            "topic_anchor_rebound_source",
            "weak_generic_topic_anchor",
            "recent_topic_fallback_allowed",
            "topic_summary",
            "message_shape_hint",
            "source_ref",
            "initiative_score",
            "proactive_topic_permission",
            "outreach_aggression_mode",
            "outreach_feedback_adaptation",
            "quiet_state",
            "quiet_until",
            "feedback_signal",
            "outreach_reason",
            "final_text_candidate",
            "language_hint",
            "style_intent",
            "content_grounding",
            "generation_trace",
        ):
            value = normalized_candidate.get(key)
            if value not in (None, "", [], {}):
                host_proactive_context[key] = value
        trace_payload["host_proactive_context"] = host_proactive_context
    elif str(_as_dict(runtime_summary.get("initiative_context")).get("initiative_trigger") or "").strip() == "thought_probe":
        analysis = _analyze_thought_probe_candidates(
            list(_as_dict(proto_self_result.get("developmental_summary")).get("background_thought_candidates") or []),
            initiative_context=_as_dict(runtime_summary.get("initiative_context")),
            recent_dialogue_reflection=_as_dict(runtime_summary.get("recent_dialogue_reflection")),
        )
        blocked = analysis.get("blocked_unanchored") or analysis.get("blocked_meta_only")
        if blocked:
            host_proactive_context = dict(trace_payload.get("host_proactive_context") or {})
            host_proactive_context["candidate_family"] = "thought_probe"
            host_proactive_context["topic_fingerprint"] = str(blocked.get("topic_fingerprint") or "")
            host_proactive_context["topic_cluster_ref"] = str(blocked.get("topic_cluster_ref") or "")
            host_proactive_context["topic_anchor_summary"] = str(blocked.get("topic_anchor_summary") or "")
            host_proactive_context["topic_anchor_source"] = str(blocked.get("topic_anchor_source") or "")
            host_proactive_context["topic_anchor_kind"] = str(blocked.get("topic_anchor_kind") or "")
            host_proactive_context["topic_binding_mode"] = str(blocked.get("topic_binding_mode") or "")
            host_proactive_context["topic_sendability"] = str(blocked.get("topic_sendability") or "")
            host_proactive_context["topic_conversation_grade"] = str(
                blocked.get("topic_conversation_grade") or "meta_reflection_only"
            )
            host_proactive_context["thought_probe_hold_reason"] = (
                "proactive_anchor_prompt_like"
                if str(blocked.get("topic_anchor_kind") or "").strip() == "prompt_like_request"
                else (
                    "proactive_topic_unanchored"
                    if analysis.get("blocked_unanchored") is blocked
                    else "proactive_meta_only_candidate"
                )
            )
            trace_payload["host_proactive_context"] = host_proactive_context
    return trace_payload


def normalize_proto_self_result(
    proto_self_result: Dict[str, Any] | None,
    runtime_summary: Dict[str, Any] | None,
) -> SubjectSystemV1Result:
    normalized_result = dict(proto_self_result or {})
    normalized_runtime_summary = dict(runtime_summary or {})
    response_tendency = _as_optional_dict(normalized_result.get("response_tendency"))

    return SubjectSystemV1Result(
        identity_invariants=_normalize_identity_invariants(normalized_runtime_summary),
        self_model_delta=_as_dict(normalized_result.get("self_model_delta")),
        memory_update=_as_dict(normalized_result.get("memory_update")),
        appraisal_state_delta=_as_dict(normalized_result.get("drives_delta")),
        reflection_writeback_candidate=_as_optional_dict(
            normalized_result.get("reflection_writeback_candidate")
        ),
        policy_hint=_as_dict(normalized_result.get("policy_hint")),
        response_tendency=response_tendency,
        host_proactive_candidate=_normalize_host_proactive_candidate(
            normalized_result,
            normalized_runtime_summary,
        ),
        trace_payload=_build_trace_payload(normalized_result, normalized_runtime_summary),
    )
