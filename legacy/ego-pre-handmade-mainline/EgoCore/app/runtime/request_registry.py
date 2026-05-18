"""Legacy request lifecycle registry kept for compatibility.

⚠️ Status:
- still used by `app/runtime/agent_runner.py`
- still referenced by old runtime/request lifecycle tests
- not the formal lifecycle truth for Telegram Runtime v2 mainline

Use this module only for compatibility containment, migration, or legacy test support.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from .request_identity import RequestIdentity, derive_chain_id
from .request_lifecycle import RequestLifecycleState, is_actionable, normalize_runtime_status


@dataclass
class TurnRecord:
    turn_id: str
    session_key: str
    message_text: str
    classified_as: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    message_id: Optional[str] = None
    linked_request_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "session_key": self.session_key,
            "message_text": self.message_text,
            "classified_as": self.classified_as,
            "created_at": self.created_at,
            "message_id": self.message_id,
            "linked_request_id": self.linked_request_id,
        }


@dataclass
class RequestRecord:
    request_id: str
    origin_turn_id: str
    session_key: str
    objective: str
    request_type: str  # new_task|follow_up|other
    status: str  # compatibility field; normalized by RequestLifecycleState
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    linked_targets: List[str] = field(default_factory=list)
    reply_sent: bool = False
    reply_sent_at: Optional[str] = None
    superseded_by: Optional[str] = None
    chain_id: Optional[str] = None
    parent_request_id: Optional[str] = None

    def build_identity(self, active_chain_id: Optional[str] = None) -> RequestIdentity:
        return RequestIdentity(
            request_id=self.request_id,
            chain_id=self.chain_id or derive_chain_id(
                request_id=self.request_id,
                request_kind=self.request_type,
                parent_request_id=self.parent_request_id,
                active_chain_id=active_chain_id,
            ),
            session_key=self.session_key,
            origin_turn_id=self.origin_turn_id,
            request_kind=self.request_type if self.request_type in {"new_task", "follow_up", "chat", "query"} else "other",
            parent_request_id=self.parent_request_id,
            superseded_by=self.superseded_by,
            bound_target_paths=list(self.linked_targets),
            created_at=self.created_at,
        )

    @property
    def lifecycle_state(self) -> RequestLifecycleState:
        return normalize_runtime_status(self.status)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "chain_id": self.chain_id,
            "parent_request_id": self.parent_request_id,
            "origin_turn_id": self.origin_turn_id,
            "session_key": self.session_key,
            "objective": self.objective,
            "request_type": self.request_type,
            "status": self.status,
            "lifecycle_state": self.lifecycle_state.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "linked_targets": self.linked_targets,
            "reply_sent": self.reply_sent,
            "reply_sent_at": self.reply_sent_at,
            "superseded_by": self.superseded_by,
        }


class RequestRegistry:
    def __init__(self):
        self.turns: Dict[str, TurnRecord] = {}
        self.requests: Dict[str, RequestRecord] = {}
        self.latest_turn_by_session: Dict[str, str] = {}
        self.latest_request_by_session: Dict[str, str] = {}
        self.active_request_by_session: Dict[str, str] = {}
        self.active_chain_by_session: Dict[str, str] = {}

    def record_turn(self, turn: TurnRecord) -> None:
        self.turns[turn.turn_id] = turn
        self.latest_turn_by_session[turn.session_key] = turn.turn_id

    def record_request(self, req: RequestRecord) -> None:
        if not req.chain_id:
            req.chain_id = derive_chain_id(
                request_id=req.request_id,
                request_kind=req.request_type,
                parent_request_id=req.parent_request_id,
                active_chain_id=self.active_chain_by_session.get(req.session_key),
            )
        self.requests[req.request_id] = req
        self.latest_request_by_session[req.session_key] = req.request_id
        if req.request_type in {"new_task", "follow_up"} and is_actionable(req.lifecycle_state):
            self.active_request_by_session[req.session_key] = req.request_id
            self.active_chain_by_session[req.session_key] = req.chain_id

    def bind_turn_to_request(self, turn_id: str, request_id: str) -> None:
        turn = self.turns.get(turn_id)
        if turn:
            turn.linked_request_id = request_id

    def get_request_by_turn(self, turn_id: str) -> Optional[RequestRecord]:
        for req in self.requests.values():
            if req.origin_turn_id == turn_id:
                return req
        return None

    def get_latest_request(self, session_key: str) -> Optional[RequestRecord]:
        rid = self.latest_request_by_session.get(session_key)
        return self.requests.get(rid) if rid else None

    def get_latest_task_request(self, session_key: str) -> Optional[RequestRecord]:
        active = self.get_active_request(session_key)
        if active:
            return active
        items = [r for r in self.requests.values() if r.session_key == session_key and r.request_type in {"new_task", "follow_up"} and not r.superseded_by]
        if not items:
            return None
        items.sort(key=lambda r: r.created_at)
        return items[-1]

    def get_active_request(self, session_key: str) -> Optional[RequestRecord]:
        rid = self.active_request_by_session.get(session_key)
        req = self.requests.get(rid) if rid else None
        if req and is_actionable(req.lifecycle_state) and not req.superseded_by:
            return req
        return None

    def get_active_chain_id(self, session_key: str) -> Optional[str]:
        active = self.get_active_request(session_key)
        if active:
            return active.chain_id
        return self.active_chain_by_session.get(session_key)

    def get_latest_unresolved_request(self, session_key: str) -> Optional[RequestRecord]:
        active = self.get_active_request(session_key)
        if active:
            return active
        items = [
            r for r in self.requests.values()
            if r.session_key == session_key
            and r.request_type in {"new_task", "follow_up"}
            and is_actionable(r.lifecycle_state)
            and not r.superseded_by
        ]
        if not items:
            return None
        current_chain = self.get_active_chain_id(session_key)
        if current_chain:
            same_chain = [r for r in items if r.chain_id == current_chain]
            if same_chain:
                same_chain.sort(key=lambda r: r.created_at)
                return same_chain[-1]
        items.sort(key=lambda r: r.created_at)
        return items[-1]

    def mark_reply_sent(self, request_id: str) -> None:
        req = self.requests.get(request_id)
        if req:
            req.reply_sent = True
            req.reply_sent_at = datetime.now(timezone.utc).isoformat()
            req.updated_at = req.reply_sent_at

    def supersede_request(self, old_request_id: str, new_request_id: str) -> None:
        req = self.requests.get(old_request_id)
        if not req:
            return
        req.superseded_by = new_request_id
        req.status = RequestLifecycleState.SUPERSEDED.value
        req.updated_at = datetime.now(timezone.utc).isoformat()
        if self.active_request_by_session.get(req.session_key) == old_request_id:
            self.active_request_by_session.pop(req.session_key, None)

    def update_status(self, request_id: str, status: str) -> None:
        req = self.requests.get(request_id)
        if req:
            normalized = normalize_runtime_status(status)
            req.status = normalized.value
            req.updated_at = datetime.now(timezone.utc).isoformat()
            if is_actionable(normalized) and not req.superseded_by:
                self.active_request_by_session[req.session_key] = request_id
                if req.chain_id:
                    self.active_chain_by_session[req.session_key] = req.chain_id
            elif self.active_request_by_session.get(req.session_key) == request_id and not is_actionable(normalized):
                self.active_request_by_session.pop(req.session_key, None)


_registry: Optional[RequestRegistry] = None

def get_request_registry() -> RequestRegistry:
    global _registry
    if _registry is None:
        _registry = RequestRegistry()
    return _registry
