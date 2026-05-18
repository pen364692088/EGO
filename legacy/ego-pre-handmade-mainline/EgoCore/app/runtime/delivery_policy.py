import hashlib
from dataclasses import dataclass
from typing import Optional, Dict, Any, Literal


DeliveryKind = Literal["ack", "progress", "ask", "final", "chat"]


@dataclass
class DeliveryIdentity:
    request_id: Optional[str]
    session_key: str
    delivery_kind: DeliveryKind
    normalized_body: str
    normalized_body_hash: str
    source_ingress_message_id: Optional[str] = None

    @classmethod
    def build(
        cls,
        *,
        session_key: str,
        reply_text: str,
        delivery_kind: DeliveryKind,
        request_id: Optional[str] = None,
        source_ingress_message_id: Optional[str] = None,
    ) -> "DeliveryIdentity":
        normalized_body = (reply_text or "").strip()
        normalized_body_hash = hashlib.sha256(normalized_body.encode("utf-8")).hexdigest()
        return cls(
            request_id=request_id,
            session_key=session_key,
            delivery_kind=delivery_kind,
            normalized_body=normalized_body,
            normalized_body_hash=normalized_body_hash,
            source_ingress_message_id=source_ingress_message_id,
        )

    def primary_key(self) -> tuple[Optional[str], str, str]:
        return (self.request_id, self.delivery_kind, self.normalized_body_hash)

    def fallback_key(self) -> tuple[str, Optional[str], str]:
        return (self.session_key, self.source_ingress_message_id, self.normalized_body_hash)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "session_key": self.session_key,
            "delivery_kind": self.delivery_kind,
            "normalized_body": self.normalized_body,
            "normalized_body_hash": self.normalized_body_hash,
            "source_ingress_message_id": self.source_ingress_message_id,
        }


class DeliveryDedupePolicy:
    """Runtime-owned duplicate suppression policy."""

    def __init__(self):
        self._seen_primary: set[tuple[Optional[str], str, str]] = set()
        self._seen_fallback: set[tuple[str, Optional[str], str]] = set()

    def should_suppress(self, identity: DeliveryIdentity) -> bool:
        if not identity.normalized_body:
            return False
        if identity.request_id is not None:
            key = identity.primary_key()
            if key in self._seen_primary:
                return True
            return False
        fallback = identity.fallback_key()
        return fallback in self._seen_fallback

    def mark_sent(self, identity: DeliveryIdentity) -> None:
        if not identity.normalized_body:
            return
        if identity.request_id is not None:
            self._seen_primary.add(identity.primary_key())
        else:
            self._seen_fallback.add(identity.fallback_key())
