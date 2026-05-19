from __future__ import annotations

import hashlib
from typing import Any, Dict, List


_TEXT_NORMALIZATION_TRANSLATION = str.maketrans(
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


def normalize_proactive_text(value: Any, *, limit: int = 280) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    normalized = " ".join(text.translate(_TEXT_NORMALIZATION_TRANSLATION).split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip()


def build_sent_text_fingerprint(value: Any) -> str:
    normalized = normalize_proactive_text(value)
    if not normalized:
        return ""
    return f"text:{hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]}"


def build_proactive_outreach_epoch(state: Any) -> str:
    generation_id = int(getattr(state, "generation_id", 0) or 0)
    chat_state = getattr(state, "get_chat_state", lambda: None)()
    recent_user_turns = list(getattr(chat_state, "recent_user_turns", None) or [])
    return f"{generation_id}:{len(recent_user_turns)}"


def current_proactive_outreach_history(state: Any) -> List[Dict[str, Any]]:
    proto_self_context = dict(getattr(state, "proto_self_context", None) or {})
    history = list(proto_self_context.get("proactive_outreach_history") or [])
    current_epoch = build_proactive_outreach_epoch(state)
    return [
        dict(marker or {})
        for marker in history
        if str((marker or {}).get("proactive_outreach_epoch") or "").strip() == current_epoch
    ]


def append_proactive_outreach_marker(state: Any, marker: Dict[str, Any], *, max_items: int = 24) -> None:
    if getattr(state, "proto_self_context", None) is None:
        state.proto_self_context = {}
    history = list((state.proto_self_context or {}).get("proactive_outreach_history") or [])
    history.append(dict(marker or {}))
    state.proto_self_context["proactive_outreach_history"] = history[-max_items:]
