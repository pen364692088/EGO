from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ToolExecutionResult:
    success: bool
    tool: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    cwd: Optional[str] = None
    timed_out: bool = False
    truncated: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> "ToolExecutionResult":
        payload = dict(data or {})
        return cls(
            success=bool(payload.get("success")),
            tool=str(payload.get("tool") or "unknown"),
            stdout=str(payload.get("stdout") or payload.get("output") or ""),
            stderr=str(payload.get("stderr") or payload.get("error") or ""),
            exit_code=int(payload.get("exit_code", 0 if payload.get("success") else 1)),
            cwd=payload.get("cwd"),
            timed_out=bool(payload.get("timed_out") or payload.get("timeout") or False),
            truncated=bool(payload.get("truncated") or payload.get("truncated_output") or False),
            metadata=dict(payload.get("metadata") or {}),
            raw=dict(payload.get("raw") or payload),
        )


@dataclass
class CompletionContract:
    target: str
    verifier: str = "file_write"
    expected: Optional[str] = None
    effect_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> "CompletionContract | None":
        payload = dict(data or {})
        target = payload.get("target") or payload.get("path")
        if not target:
            return None
        return cls(
            target=str(target),
            verifier=str(payload.get("verifier") or payload.get("kind") or cls._infer_verifier(str(target))),
            expected=payload.get("expected"),
            effect_type=payload.get("effect_type"),
            metadata={k: v for k, v in payload.items() if k not in {"target", "path", "verifier", "kind", "expected", "effect_type"}},
        )

    @staticmethod
    def _infer_verifier(target: str) -> str:
        lowered = target.lower()
        if lowered.endswith(".html") or lowered.endswith(".htm"):
            return "html_effect"
        return "file_write"


@dataclass
class CompletionVerificationResult:
    passed: bool
    reason: str
    verifier: str
    target: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DeliveryIdentity:
    session_id: str
    delivery_kind: str
    body: str
    request_id: Optional[str] = None
    source_message_id: Optional[str] = None

    def dedupe_key(self) -> str:
        return "|".join([
            self.session_id,
            self.request_id or "-",
            self.source_message_id or "-",
            self.delivery_kind,
            self.body.strip(),
        ])


@dataclass
class DeliveryLedger:
    last_busy_notice_at: Optional[float] = None
    last_failure_notice_at: Optional[float] = None
    last_failure_notice_text: Optional[str] = None
    sent_keys: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
