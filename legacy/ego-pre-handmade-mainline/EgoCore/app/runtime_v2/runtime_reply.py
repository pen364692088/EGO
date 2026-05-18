from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


@dataclass
class RuntimeV2Reply:
    reply_text: str
    delivery_kind: str
    status: str
    suppressible: bool = False
    request_id: Optional[str] = None
    # WS-1: Turn Isolation
    generation_id: Optional[int] = None
    turn_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RuntimeV2TurnResult:
    status: str
    state: Any
    reply: Optional[RuntimeV2Reply] = None
    finish_reason: Optional[str] = None
    checkpoint_payload: Optional[Dict[str, Any]] = None

    @property
    def reply_text(self) -> str:
        return self.reply.reply_text if self.reply else ""

    @property
    def delivery_kind(self) -> Optional[str]:
        return self.reply.delivery_kind if self.reply else None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "status": self.status,
            "state": self.state,
        }
        if self.reply is not None:
            data.update(self.reply.to_dict())
        else:
            data.update({"reply_text": "", "delivery_kind": None})
        data["finish_reason"] = self.finish_reason
        data["checkpoint_payload"] = self.checkpoint_payload
        return data
