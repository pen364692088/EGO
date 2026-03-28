from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from openemotion.proto_self.schemas import (
    KernelEvent,
    ReflectionNote,
    ResponseTendency,
    normalize_safety_context,
)


SCHEMA_VERSION = "proto_self.v2"
OUTPUT_SCHEMA_VERSION = "proto_self.output.v2"


def is_proto_self_v2_payload(payload: Dict[str, Any]) -> bool:
    return payload.get("schema_version") == SCHEMA_VERSION


@dataclass
class UpdateEventV2:
    actor: str = ""
    source: str = ""
    event_type: str = ""
    user_intent: Optional[str] = None
    raw_text: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actor": self.actor,
            "source": self.source,
            "event_type": self.event_type,
            "user_intent": self.user_intent,
            "raw_text": self.raw_text,
        }


@dataclass
class UpdatePacketV2:
    schema_version: str = SCHEMA_VERSION
    event_id: str = ""
    timestamp: str = ""
    event: UpdateEventV2 = field(default_factory=UpdateEventV2)
    executed_action_prev: Optional[Dict[str, Any]] = None
    external_outcome: Optional[Dict[str, Any]] = None
    runtime_summary: Dict[str, Any] = field(default_factory=dict)
    task_summary: Dict[str, Any] = field(default_factory=dict)
    conversation_summary: Dict[str, Any] = field(default_factory=dict)
    safety_context: Dict[str, Any] = field(default_factory=dict)
    intervention_context: Dict[str, Any] = field(default_factory=dict)
    prediction_snapshot_prev: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.safety_context = normalize_safety_context(self.safety_context)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event": self.event.to_dict(),
            "executed_action_prev": self.executed_action_prev,
            "external_outcome": self.external_outcome,
            "runtime_summary": self.runtime_summary,
            "task_summary": self.task_summary,
            "conversation_summary": self.conversation_summary,
            "safety_context": self.safety_context,
            "intervention_context": self.intervention_context,
            "prediction_snapshot_prev": self.prediction_snapshot_prev,
        }

    def to_v1_kernel_event(self) -> KernelEvent:
        runtime_summary = dict(self.runtime_summary)
        if self.executed_action_prev is not None:
            runtime_summary["executed_action_prev"] = self.executed_action_prev
        if self.intervention_context:
            runtime_summary["intervention_context"] = self.intervention_context
        if self.prediction_snapshot_prev:
            runtime_summary["prediction_snapshot_prev"] = self.prediction_snapshot_prev
        return KernelEvent(
            event_id=self.event_id,
            timestamp=self.timestamp,
            actor=self.event.actor,
            source=self.event.source,
            event_type=self.event.event_type,
            user_intent=self.event.user_intent,
            raw_text=self.event.raw_text,
            conversation_context=self.conversation_summary,
            task_context=self.task_summary,
            runtime_summary=runtime_summary,
            safety_context=self.safety_context,
            external_result=self.external_outcome,
        )


def update_packet_from_payload(payload: Dict[str, Any]) -> UpdatePacketV2:
    event_payload = payload.get("event") or {}
    if not event_payload:
        event_payload = {
            "actor": payload.get("actor", ""),
            "source": payload.get("source", ""),
            "event_type": payload.get("event_type", ""),
            "user_intent": payload.get("user_intent"),
            "raw_text": payload.get("raw_text"),
        }
    return UpdatePacketV2(
        schema_version=payload.get("schema_version", SCHEMA_VERSION),
        event_id=payload.get("event_id", ""),
        timestamp=payload.get("timestamp", ""),
        event=UpdateEventV2(
            actor=event_payload.get("actor", ""),
            source=event_payload.get("source", ""),
            event_type=event_payload.get("event_type", ""),
            user_intent=event_payload.get("user_intent"),
            raw_text=event_payload.get("raw_text"),
        ),
        executed_action_prev=payload.get("executed_action_prev"),
        external_outcome=payload.get("external_outcome", payload.get("external_result")),
        runtime_summary=payload.get("runtime_summary", {}),
        task_summary=payload.get("task_summary", payload.get("task_context", {})),
        conversation_summary=payload.get("conversation_summary", payload.get("conversation_context", {})),
        safety_context=payload.get("safety_context", {}),
        intervention_context=payload.get("intervention_context", {}),
        prediction_snapshot_prev=payload.get("prediction_snapshot_prev", {}),
    )


@dataclass
class KernelOutputV2:
    schema_version: str = OUTPUT_SCHEMA_VERSION
    event_id: str = ""
    identity_delta: Dict[str, Any] = field(default_factory=dict)
    self_model_delta: Dict[str, Any] = field(default_factory=dict)
    drives_delta: Dict[str, Any] = field(default_factory=dict)
    cycles_delta: Dict[str, Any] = field(default_factory=dict)
    predictive_reflective_delta: Dict[str, Any] = field(default_factory=dict)
    memory_update: Dict[str, Any] = field(default_factory=dict)
    reflection_note: Optional[ReflectionNote] = None
    policy_hint: Dict[str, Any] = field(default_factory=dict)
    response_tendency: Optional[ResponseTendency] = None
    confidence_meta: Dict[str, Any] = field(default_factory=dict)
    trace_payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "identity_delta": self.identity_delta,
            "self_model_delta": self.self_model_delta,
            "drives_delta": self.drives_delta,
            "cycles_delta": self.cycles_delta,
            "predictive_reflective_delta": self.predictive_reflective_delta,
            "memory_update": self.memory_update,
            "reflection_note": self.reflection_note.to_dict() if self.reflection_note else None,
            "policy_hint": self.policy_hint,
            "response_tendency": self.response_tendency.to_dict() if self.response_tendency else None,
            "confidence_meta": self.confidence_meta,
            "trace_payload": self.trace_payload,
        }


def serialize_kernel_output_v2(output: KernelOutputV2) -> Dict[str, Any]:
    return output.to_dict()
