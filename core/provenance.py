"""
Provenance + Signature Attribution (US-643)

Provides cryptographic signing for internal artifacts to prevent
prompt injection of fake "self memories" or "self thoughts".
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class Source(str, Enum):
    """Origin of an artifact"""
    USER = "user"
    SYSTEM = "system"
    INFERENCE = "inference"
    ROLLOUT = "rollout"
    REFLECTION = "reflection"
    MEMORY = "memory"


@dataclass
class Provenance:
    """
    Provenance record for an artifact.
    
    Attributes:
        source: Origin of the artifact
        signature: HMAC signature (if signed)
        timestamp: Creation time (ISO 8601)
        trace_id: Unique trace identifier
        parent_id: Optional parent provenance ID (for chains)
    """
    source: Source
    signature: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value if isinstance(self.source, Source) else self.source,
            "signature": self.signature,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Provenance":
        return cls(
            source=Source(data["source"]),
            signature=data.get("signature"),
            timestamp=data.get("timestamp", ""),
            trace_id=data.get("trace_id", str(uuid.uuid4())),
            parent_id=data.get("parent_id"),
        )


def _get_signing_secret() -> bytes:
    """Get the signing secret from environment."""
    secret = os.environ.get("EMOTIOND_SIGNING_SECRET", "default-dev-secret")
    return secret.encode("utf-8")


def sign_payload(payload: dict[str, Any], secret: Optional[bytes] = None) -> str:
    """
    Sign a payload with HMAC-SHA256.
    
    Args:
        payload: The data to sign
        secret: Signing secret (defaults to EMOTIOND_SIGNING_SECRET env var)
    
    Returns:
        Hex-encoded signature
    """
    if secret is None:
        secret = _get_signing_secret()
    
    # Canonical JSON serialization
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hmac.new(secret, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_signature(payload: dict[str, Any], signature: str, secret: Optional[bytes] = None) -> bool:
    """
    Verify a payload signature.
    
    Args:
        payload: The data to verify
        signature: Expected hex-encoded signature
        secret: Signing secret (defaults to EMOTIOND_SIGNING_SECRET env var)
    
    Returns:
        True if signature is valid, False otherwise
    """
    expected = sign_payload(payload, secret)
    return hmac.compare_digest(expected, signature)


def sign_artifact(artifact: dict[str, Any], source: Source, parent_id: Optional[str] = None) -> dict[str, Any]:
    """
    Sign an artifact and add provenance.
    
    Args:
        artifact: The artifact to sign (will be modified in place)
        source: Origin of the artifact
        parent_id: Optional parent provenance ID
    
    Returns:
        The artifact with provenance added
    """
    provenance = Provenance(source=source, parent_id=parent_id)
    
    # Sign the artifact content (without provenance to avoid circular dependency)
    content = {k: v for k, v in artifact.items() if k != "provenance"}
    provenance.signature = sign_payload(content)
    
    artifact["provenance"] = provenance.to_dict()
    return artifact


def verify_artifact(artifact: dict[str, Any]) -> bool:
    """
    Verify an artifact's signature.
    
    Args:
        artifact: The artifact to verify (must have provenance field)
    
    Returns:
        True if valid, False if invalid or missing signature
    """
    prov_data = artifact.get("provenance")
    if not prov_data:
        return False
    
    provenance = Provenance.from_dict(prov_data)
    if not provenance.signature:
        return False
    
    # Verify content matches signature
    content = {k: v for k, v in artifact.items() if k != "provenance"}
    return verify_signature(content, provenance.signature)


def is_internal_source(source: Source | str) -> bool:
    """Check if a source is internal (requires signature validation)."""
    if isinstance(source, str):
        source = Source(source)
    return source in (Source.SYSTEM, Source.INFERENCE, Source.ROLLOUT, Source.REFLECTION, Source.MEMORY)


def validate_provenance_for_write(artifact: dict[str, Any]) -> tuple[bool, str]:
    """
    Validate provenance before writing to internal storage.
    
    Returns:
        (is_valid, reason) tuple
    """
    prov_data = artifact.get("provenance")
    if not prov_data:
        return False, "missing_provenance"
    
    provenance = Provenance.from_dict(prov_data)
    
    # Internal sources MUST have valid signatures
    if is_internal_source(provenance.source):
        if not provenance.signature:
            return False, "missing_signature_for_internal_source"
        if not verify_artifact(artifact):
            return False, "invalid_signature"
    
    return True, "ok"
