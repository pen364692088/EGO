from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Optional, Tuple


@dataclass(frozen=True)
class ProactiveTelegramEnablePolicy:
    enabled: bool
    allowed_chat_ids: Optional[FrozenSet[int]] = None
    allowed_session_prefixes: Tuple[str, ...] = ("telegram:dm:",)
    min_recent_user_turns: int = 2
    min_recent_assistant_replies: int = 1


@dataclass(frozen=True)
class ProactiveTelegramEnableVerdict:
    status: str
    reason: str
    session_id: str
    chat_id: Optional[int]
    recent_user_turn_count: int
    recent_assistant_reply_count: int

    @property
    def allowed(self) -> bool:
        return self.status == "allow"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "session_id": self.session_id,
            "chat_id": self.chat_id,
            "recent_user_turn_count": self.recent_user_turn_count,
            "recent_assistant_reply_count": self.recent_assistant_reply_count,
        }


def evaluate_proactive_telegram_enable_policy(
    *,
    session_id: str,
    state: Any,
    chat_id: Optional[int],
    policy: ProactiveTelegramEnablePolicy,
) -> ProactiveTelegramEnableVerdict:
    chat_state = getattr(state, "get_chat_state", lambda: None)()
    recent_user_turns = list(getattr(chat_state, "recent_user_turns", []) or [])
    recent_assistant_replies = list(getattr(chat_state, "recent_assistant_replies", []) or [])
    recent_user_turn_count = len(recent_user_turns)
    recent_assistant_reply_count = len(recent_assistant_replies)

    if not policy.enabled:
        return ProactiveTelegramEnableVerdict(
            "hold",
            "autodrain_disabled",
            session_id,
            chat_id,
            recent_user_turn_count,
            recent_assistant_reply_count,
        )
    if not isinstance(chat_id, int):
        return ProactiveTelegramEnableVerdict(
            "hold",
            "missing_chat_id",
            session_id,
            chat_id,
            recent_user_turn_count,
            recent_assistant_reply_count,
        )
    if policy.allowed_session_prefixes and not any(
        str(session_id or "").startswith(prefix) for prefix in policy.allowed_session_prefixes
    ):
        return ProactiveTelegramEnableVerdict(
            "hold",
            "session_scope_blocked",
            session_id,
            chat_id,
            recent_user_turn_count,
            recent_assistant_reply_count,
        )
    if policy.allowed_chat_ids is not None and chat_id not in policy.allowed_chat_ids:
        return ProactiveTelegramEnableVerdict(
            "hold",
            "chat_not_allowlisted",
            session_id,
            chat_id,
            recent_user_turn_count,
            recent_assistant_reply_count,
        )
    if recent_user_turn_count < max(1, int(policy.min_recent_user_turns)):
        return ProactiveTelegramEnableVerdict(
            "hold",
            "insufficient_recent_user_turns",
            session_id,
            chat_id,
            recent_user_turn_count,
            recent_assistant_reply_count,
        )
    if recent_assistant_reply_count < max(1, int(policy.min_recent_assistant_replies)):
        return ProactiveTelegramEnableVerdict(
            "hold",
            "insufficient_recent_assistant_replies",
            session_id,
            chat_id,
            recent_user_turn_count,
            recent_assistant_reply_count,
        )
    return ProactiveTelegramEnableVerdict(
        "allow",
        "ok",
        session_id,
        chat_id,
        recent_user_turn_count,
        recent_assistant_reply_count,
    )
