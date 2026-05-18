from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid


@dataclass(slots=True)
class BusEvent:
    session_key: str
    kind: str
    payload: Dict[str, Any] = field(default_factory=dict)
    channel: str = "unknown"
    trace_id: Optional[str] = None
    message_id: Optional[int] = None
    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
