from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional


SEED_SCHEMA_VERSION = "proto_self_seed.v0.2"
SEED_SUBJECT_PROFILE = "seed_v0_2"

SeedEventType = Literal["user_event", "idle_check", "exec_result", "system_event"]
SeedRiskLevel = Literal["low", "medium", "high"]
SeedExecStatus = Literal["success", "failure", "blocked", "no_op"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class KernelEvent:
    event_type: SeedEventType
    source: str
    payload: Dict[str, Any] = field(default_factory=dict)
    runtime_summary: Dict[str, Any] = field(default_factory=dict)
    safety_context: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=utc_now_iso)
    schema_version: str = SEED_SCHEMA_VERSION

    def validate(self) -> None:
        if self.schema_version != SEED_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version mismatch: expected {SEED_SCHEMA_VERSION}, got {self.schema_version}"
            )
        if self.event_type not in {"user_event", "idle_check", "exec_result", "system_event"}:
            raise ValueError(f"unsupported event_type: {self.event_type!r}")
        if not isinstance(self.payload, dict):
            raise TypeError("payload must be a dict")
        if not isinstance(self.runtime_summary, dict):
            raise TypeError("runtime_summary must be a dict")
        if not isinstance(self.safety_context, dict):
            raise TypeError("safety_context must be a dict")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ActionSpec:
    action_type: str
    reason: str
    motivation_source: List[str]
    urge_score: float
    expected_gain: float
    risk_level: SeedRiskLevel
    reversible: bool
    requires_approval: bool
    target: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.risk_level not in {"low", "medium", "high"}:
            raise ValueError(f"unsupported risk_level: {self.risk_level!r}")
        if not self.action_type:
            raise ValueError("action_type must not be empty")
        if self.urge_score < 0.0:
            raise ValueError("urge_score must be >= 0.0")
        if not isinstance(self.motivation_source, list):
            raise TypeError("motivation_source must be a list")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExecResultEvent:
    action_type: str
    status: SeedExecStatus
    target: Optional[str] = None
    observed_gain: float = 0.0
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.status not in {"success", "failure", "blocked", "no_op"}:
            raise ValueError(f"unsupported exec status: {self.status!r}")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_kernel_event(
        self,
        *,
        source: str,
        runtime_summary: Optional[Dict[str, Any]] = None,
        safety_context: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> KernelEvent:
        return KernelEvent(
            event_type="exec_result",
            source=source,
            payload=self.to_dict(),
            runtime_summary=dict(runtime_summary or {}),
            safety_context=dict(safety_context or {}),
            timestamp=timestamp or utc_now_iso(),
        )


def seed_event_from_payload(payload: Optional[Dict[str, Any]]) -> Optional[KernelEvent]:
    if not payload:
        return None
    event = KernelEvent(
        event_type=payload.get("event_type", "system_event"),
        source=payload.get("source", "unknown"),
        payload=dict(payload.get("payload") or {}),
        runtime_summary=dict(payload.get("runtime_summary") or {}),
        safety_context=dict(payload.get("safety_context") or {}),
        timestamp=payload.get("timestamp") or utc_now_iso(),
        schema_version=payload.get("schema_version", SEED_SCHEMA_VERSION),
    )
    event.validate()
    return event
