from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Literal, Optional

from app.response.relationship_context import RelationshipContext, RelationshipEvent
from app.response.style_profile import StyleProfile


ChatAct = Literal[
    "presence_check",
    "tone_feedback",
    "thread_continue",
    "light_chitchat",
    "social_keepalive",
    "task_bridge_request",
]

_MAX_CHAT_TURNS = 6


def normalize_chat_reply(text: str) -> str:
    raw = str(text or "").strip().lower()
    if not raw:
        return ""
    collapsed = " ".join(raw.split())
    for token in ("，", "。", "！", "？", "!", "?", ".", ",", "\"", "'", "“", "”", "：", ":"):
        collapsed = collapsed.replace(token, "")
    return collapsed.strip()


def _trim_recent(values: List[str], *, limit: int = _MAX_CHAT_TURNS) -> List[str]:
    cleaned = [str(value).strip() for value in values if str(value or "").strip()]
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[-limit:]


@dataclass
class ChatState:
    session_id: str = ""
    recent_user_turns: List[str] = field(default_factory=list)
    recent_assistant_replies: List[str] = field(default_factory=list)
    last_user_turn_at: Optional[float] = None
    last_assistant_reply_at: Optional[float] = None
    last_activity_at: Optional[float] = None
    last_user_tone_feedback: Optional[str] = None
    relationship_context: Dict[str, Any] = field(default_factory=dict)
    style_profile: Dict[str, Any] = field(default_factory=dict)
    active_task_summary: Optional[Dict[str, Any]] = None
    last_chat_act: Optional[str] = None

    def ensure_defaults(self, session_id: str) -> None:
        if not self.session_id:
            self.session_id = session_id
        if not self.relationship_context:
            self.relationship_context = RelationshipContext(session_id=session_id).to_dict()
        if not self.style_profile:
            self.style_profile = StyleProfile(session_id=session_id).to_dict()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "recent_user_turns": list(self.recent_user_turns),
            "recent_assistant_replies": list(self.recent_assistant_replies),
            "last_user_turn_at": self.last_user_turn_at,
            "last_assistant_reply_at": self.last_assistant_reply_at,
            "last_activity_at": self.last_activity_at,
            "last_user_tone_feedback": self.last_user_tone_feedback,
            "relationship_context": dict(self.relationship_context or {}),
            "style_profile": dict(self.style_profile or {}),
            "active_task_summary": dict(self.active_task_summary or {}) if self.active_task_summary else None,
            "last_chat_act": self.last_chat_act,
        }

    @classmethod
    def from_dict(cls, payload: Optional[Dict[str, Any]], *, session_id: str) -> "ChatState":
        state = cls(
            session_id=session_id,
            recent_user_turns=list((payload or {}).get("recent_user_turns") or []),
            recent_assistant_replies=list((payload or {}).get("recent_assistant_replies") or []),
            last_user_turn_at=(payload or {}).get("last_user_turn_at"),
            last_assistant_reply_at=(payload or {}).get("last_assistant_reply_at"),
            last_activity_at=(payload or {}).get("last_activity_at"),
            last_user_tone_feedback=(payload or {}).get("last_user_tone_feedback"),
            relationship_context=dict((payload or {}).get("relationship_context") or {}),
            style_profile=dict((payload or {}).get("style_profile") or {}),
            active_task_summary=(payload or {}).get("active_task_summary"),
            last_chat_act=(payload or {}).get("last_chat_act"),
        )
        state.ensure_defaults(session_id)
        state.recent_user_turns = _trim_recent(state.recent_user_turns)
        state.recent_assistant_replies = _trim_recent(state.recent_assistant_replies)
        return state

    def prepare_turn(
        self,
        *,
        user_text: str,
        chat_act: str,
        active_task_summary: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.ensure_defaults(self.session_id)
        text = str(user_text or "").strip()
        now_ts = time.time()
        if text:
            self.recent_user_turns = _trim_recent(self.recent_user_turns + [text])
            self.last_user_turn_at = now_ts
            self.last_activity_at = now_ts
        self.last_chat_act = chat_act or self.last_chat_act
        self.active_task_summary = dict(active_task_summary or {}) if active_task_summary else None

        relationship = RelationshipContext.from_dict(self.relationship_context)
        style = StyleProfile.from_dict(self.style_profile)
        event_type = RelationshipEvent.CHITCHAT.value
        impact = "neutral"

        if chat_act == "presence_check":
            event_type = RelationshipEvent.TESTING.value
        elif chat_act == "tone_feedback":
            event_type = RelationshipEvent.AFFECTIVE_PROBE.value
            impact = "negative"
            self.last_user_tone_feedback = text[:200] if text else self.last_user_tone_feedback
        elif chat_act == "task_bridge_request":
            event_type = RelationshipEvent.TASK_REQUEST.value

        relationship.record_event(
            event_type=event_type,
            user_input=text[:80],
            agent_response="",
            impact=impact,
        )

        if chat_act == "tone_feedback":
            relationship.last_user_feedback_about_tone = text[:200] if text else relationship.last_user_feedback_about_tone
            style.adjust_for_repair()
        elif chat_act == "task_bridge_request":
            style.adjust_for_task_mode()
        elif relationship.should_be_warmer():
            style.adjust_for_warming()

        self.relationship_context = relationship.to_dict()
        self.style_profile = style.to_dict()

    def finalize_turn(self, *, assistant_reply: str, chat_act: str) -> None:
        self.ensure_defaults(self.session_id)
        reply = str(assistant_reply or "").strip()
        now_ts = time.time()
        if reply:
            self.recent_assistant_replies = _trim_recent(self.recent_assistant_replies + [reply])
            self.last_assistant_reply_at = now_ts
            self.last_activity_at = now_ts

        relationship = RelationshipContext.from_dict(self.relationship_context)
        style = StyleProfile.from_dict(self.style_profile)

        if chat_act == "tone_feedback":
            relationship.mark_repair_resolved()
            if relationship.should_be_warmer():
                style.adjust_for_warming()

        self.relationship_context = relationship.to_dict()
        self.style_profile = style.to_dict()

    def recent_normalized_replies(self, *, limit: int = 3) -> List[str]:
        return [
            normalize_chat_reply(text)
            for text in self.recent_assistant_replies[-limit:]
            if normalize_chat_reply(text)
        ]

    def idle_seconds(self, *, now_ts: Optional[float] = None) -> float:
        anchor = self.last_activity_at or self.last_assistant_reply_at or self.last_user_turn_at
        if anchor is None:
            return 0.0
        current = time.time() if now_ts is None else float(now_ts)
        return max(0.0, current - float(anchor))
