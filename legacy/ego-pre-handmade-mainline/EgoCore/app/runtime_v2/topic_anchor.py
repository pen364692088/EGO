from __future__ import annotations

import re
from typing import Any, Callable, Dict, Iterable, List, Optional

_MAX_CHAT_TURNS = 6
_GREETING_TURNS = {"你好", "你好啊", "hi", "hello", "/new"}
_PROACTIVE_TOPIC_CONTROL_MARKERS = (
    "以后可以主动找我",
    "以后可以主动来找我",
    "默认允许你主动找我",
    "默认允许你主动来找我",
    "以后允许你主动找我",
    "以后允许你主动来找我",
    "可以主动找我聊",
    "可以主动来找我聊",
    "可以自己找话题来找我",
    "可以自己想到什么就来找我",
    "可以继续主动找我",
    "可以继续主动来找我",
    "主动来找我",
    "主动找我",
    "自己找新话题",
    "不用每次都问我",
    "以后不要主动找我",
    "以后不要主动来找我",
    "别主动找我",
    "别主动来找我",
    "不要主动找我",
    "不要主动来找我",
    "取消主动找我",
    "关闭主动找我",
    "降低频率",
    "别太频繁",
    "不用那么频繁",
    "少主动一点",
    "别太密",
    "这几个小时先别打扰",
    "先别打扰",
    "暂停一下",
    "暂停一会",
    "先暂停",
    "安静一会",
    "恢复正常",
    "继续主动找我",
    "恢复主动",
    "恢复频率",
)
_EXPLICIT_FOLLOWUP_CONTROL_MARKERS = (
    "提醒我继续",
    "只发一个轻提醒",
    "轻提醒",
    "不要连续发",
    "会回来继续这个话题",
    "等下会回来继续这个话题",
    "之后可以提醒我继续",
)
_CONTINUATION_CONTROL_ACTS = {
    "thread_continue",
}
_BARE_CONTINUE_CONTROL_TURNS = (
    "继续",
    "continue",
)
_THREAD_CONTINUE_CONTROL_MARKERS = (
    "继续说",
    "展开说",
    "多说点",
    "接着说",
)
_SOLICITED_VIEW_MARKERS = (
    "你怎么看",
    "你觉得呢",
    "你觉得要怎么",
    "你有没有什么想法",
    "你有什么想法",
    "你有什么看法",
    "说说你的想法",
    "说说你的看法",
    "告诉我你的想法",
)
_SOLICITED_VIEW_PREFIX_PATTERNS = (
    r"^你怎么看(?:待)?",
    r"^你觉得呢",
    r"^你觉得要怎么",
    r"^你有没有什么想法(?:\s*可以告诉我)?",
    r"^你有什么想法(?:\s*可以告诉我)?",
    r"^你有什么看法",
    r"^说说你的(?:想法|看法)",
    r"^告诉我你的(?:想法|看法)",
)
_TOPIC_SUFFIX_PATTERNS = (
    r"(?:最大的瓶颈是什么|瓶颈是什么)$",
    r"(?:需要怎么做|该怎么做|要怎么做|怎么做)$",
    r"(?:该怎么看|怎么看)$",
    r"(?:为什么)$",
    r"(?:是什么)$",
)


def _normalize_turn_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _compact_turn_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().lower())


def _trim_recent_user_turn_records(
    records: Iterable[Dict[str, Any]],
    *,
    limit: int = _MAX_CHAT_TURNS,
) -> List[Dict[str, Any]]:
    cleaned: List[Dict[str, Any]] = []
    for raw in records:
        text = _normalize_turn_text((raw or {}).get("text"))
        if not text:
            continue
        cleaned.append(
            {
                "text": text,
                "conversation_act": str((raw or {}).get("conversation_act") or "").strip() or None,
                "timestamp": (raw or {}).get("timestamp"),
            }
        )
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[-limit:]


def build_user_turn_record(
    *,
    text: str,
    conversation_act: str,
    timestamp: Any,
) -> Dict[str, Any]:
    return {
        "text": _normalize_turn_text(text),
        "conversation_act": str(conversation_act or "").strip() or None,
        "timestamp": timestamp,
    }


def coerce_recent_user_turn_records(
    records: Optional[Iterable[Dict[str, Any]]],
    fallback_turns: Optional[Iterable[Any]] = None,
) -> List[Dict[str, Any]]:
    normalized = _trim_recent_user_turn_records(records or [])
    if normalized:
        return normalized
    fallback_records = [
        build_user_turn_record(
            text=str(turn or ""),
            conversation_act="unknown",
            timestamp=None,
        )
        for turn in list(fallback_turns or [])
        if _normalize_turn_text(turn)
    ]
    return _trim_recent_user_turn_records(fallback_records)


def sanitize_solicited_view_anchor(value: Any, *, limit: int = 80) -> Optional[str]:
    cleaned = _normalize_turn_text(value)
    if not cleaned or cleaned in _GREETING_TURNS:
        return None
    for pattern in _SOLICITED_VIEW_PREFIX_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned).strip(" ，。！？?!.：:")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return None
    return cleaned[:limit]


def build_topic_anchor_variants(value: Any, *, limit: int = 80) -> List[str]:
    cleaned = _normalize_turn_text(value).strip(" ，。！？?!.：:")
    if not cleaned:
        return []
    candidates = [cleaned[:limit]]
    for pattern in _TOPIC_SUFFIX_PATTERNS:
        simplified = re.sub(pattern, "", cleaned).strip(" ，。！？?!.：:")
        if simplified and simplified != cleaned:
            candidates.append(simplified[:limit])
            break
    deduped: List[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        token = candidate.strip()
        lowered = token.lower()
        if not token or lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(token)
    return deduped


def is_prompt_like_view_request(value: Any) -> bool:
    normalized = _normalize_turn_text(value)
    if not normalized:
        return False
    if sanitize_solicited_view_anchor(normalized):
        return False
    return any(marker in normalized for marker in _SOLICITED_VIEW_MARKERS)


def is_continuation_control_topic_turn(value: Any) -> bool:
    normalized = _normalize_turn_text(value)
    if not normalized:
        return False
    compact = _compact_turn_text(normalized)
    if compact in {_compact_turn_text(turn) for turn in _BARE_CONTINUE_CONTROL_TURNS}:
        return True
    if len(compact) <= 18 and any(_compact_turn_text(marker) in compact for marker in _THREAD_CONTINUE_CONTROL_MARKERS):
        return True
    return False


def is_meta_or_control_topic_turn(value: Any, *, include_prompt_like: bool = True) -> bool:
    normalized = _normalize_turn_text(value)
    if not normalized:
        return True
    if normalized in _GREETING_TURNS:
        return True
    if is_continuation_control_topic_turn(normalized):
        return True
    if include_prompt_like and is_prompt_like_view_request(normalized):
        return True
    compact = _compact_turn_text(normalized)
    markers = _PROACTIVE_TOPIC_CONTROL_MARKERS + _EXPLICIT_FOLLOWUP_CONTROL_MARKERS
    return any(_compact_turn_text(marker) in compact for marker in markers)


def is_non_substantive_topic_turn_record(
    record: Dict[str, Any],
    *,
    include_prompt_like: bool = True,
) -> bool:
    text = _normalize_turn_text((record or {}).get("text"))
    conversation_act = str((record or {}).get("conversation_act") or "").strip()
    if conversation_act in _CONTINUATION_CONTROL_ACTS:
        return True
    return is_meta_or_control_topic_turn(text, include_prompt_like=include_prompt_like)


def extract_recent_substantive_topic_anchor(
    user_turn_records: Iterable[Dict[str, Any]],
    *,
    skip_turn: Optional[Callable[[str], bool]] = None,
    exclude_text: Optional[str] = None,
) -> Dict[str, str]:
    records = _trim_recent_user_turn_records(user_turn_records)
    excluded = _normalize_turn_text(exclude_text)
    prompt_like_turn_preview = ""
    last_index = len(records) - 1

    for index in range(last_index, -1, -1):
        record = records[index]
        text = _normalize_turn_text(record.get("text"))
        if not text:
            continue
        if excluded and _normalize_turn_text(text) == excluded:
            continue
        if text in _GREETING_TURNS:
            continue

        source = "current_turn" if index == last_index else "prior_user_turn"
        conversation_act = str(record.get("conversation_act") or "").strip()
        if conversation_act == "solicited_view":
            anchor = sanitize_solicited_view_anchor(text, limit=120)
            if anchor:
                return {
                    "topic_anchor": anchor,
                    "topic_anchor_source": source,
                    "topic_anchor_kind": "substantive_topic",
                    "prompt_like_turn_preview": prompt_like_turn_preview,
            }
            prompt_like_turn_preview = text[:120]
            continue
        if skip_turn and skip_turn(text):
            continue
        if is_non_substantive_topic_turn_record(record, include_prompt_like=False):
            continue
        if is_prompt_like_view_request(text):
            prompt_like_turn_preview = text[:120]
            continue
        if is_meta_or_control_topic_turn(text, include_prompt_like=False):
            continue

        return {
            "topic_anchor": text[:120],
            "topic_anchor_source": source,
            "topic_anchor_kind": "substantive_topic",
            "prompt_like_turn_preview": prompt_like_turn_preview,
        }

    return {
        "topic_anchor": "",
        "topic_anchor_source": "none",
        "topic_anchor_kind": "prompt_like_request" if prompt_like_turn_preview else "none",
        "prompt_like_turn_preview": prompt_like_turn_preview,
    }
