from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Literal, Dict, Any


RequestKind = Literal["new_task", "follow_up", "chat", "query", "other"]


@dataclass
class RequestIdentity:
    """Formal host-owned identity for a request and its actionable chain."""

    request_id: str
    chain_id: str
    session_key: str
    origin_turn_id: str
    request_kind: RequestKind
    parent_request_id: Optional[str] = None
    superseded_by: Optional[str] = None
    bound_target_paths: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "chain_id": self.chain_id,
            "session_key": self.session_key,
            "origin_turn_id": self.origin_turn_id,
            "request_kind": self.request_kind,
            "parent_request_id": self.parent_request_id,
            "superseded_by": self.superseded_by,
            "bound_target_paths": self.bound_target_paths,
            "created_at": self.created_at,
        }


def derive_chain_id(
    request_id: str,
    request_kind: str,
    parent_request_id: Optional[str] = None,
    active_chain_id: Optional[str] = None,
) -> str:
    """Use the active chain for follow-ups, otherwise start a new chain."""
    if request_kind == "follow_up":
        if active_chain_id:
            return active_chain_id
        if parent_request_id:
            return parent_request_id
    return request_id
