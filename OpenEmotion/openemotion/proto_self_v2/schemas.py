from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openemotion.proto_self.schemas import (
    KernelEvent,
    ReflectionNote,
    ResponseTendency,
    normalize_safety_context,
)
from openemotion.proto_self_v2.seed_schemas import SEED_SUBJECT_PROFILE, seed_event_from_payload


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
    subject_profile: Optional[str] = None
    seed_event: Optional[Dict[str, Any]] = None
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
        if self.seed_event is not None and not isinstance(self.seed_event, dict):
            raise TypeError("seed_event must be a dict when provided")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event": self.event.to_dict(),
            "subject_profile": self.subject_profile,
            "seed_event": self.seed_event,
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
        if self.subject_profile:
            runtime_summary["subject_profile"] = self.subject_profile
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

    def to_seed_kernel_event(self):
        if self.subject_profile != SEED_SUBJECT_PROFILE:
            return None
        if self.seed_event:
            return seed_event_from_payload(self.seed_event)
        return None


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
        subject_profile=payload.get("subject_profile"),
        seed_event=dict(payload.get("seed_event") or {}) or None,
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
    subject_profile: Optional[str] = None
    identity_delta: Dict[str, Any] = field(default_factory=dict)
    self_model_delta: Dict[str, Any] = field(default_factory=dict)
    drives_delta: Dict[str, Any] = field(default_factory=dict)
    cycles_delta: Dict[str, Any] = field(default_factory=dict)
    predictive_reflective_delta: Dict[str, Any] = field(default_factory=dict)
    seed_state_delta: Dict[str, Any] = field(default_factory=dict)
    memory_update: Dict[str, Any] = field(default_factory=dict)
    candidate_actions: List[Dict[str, Any]] = field(default_factory=list)
    reflection_note: Optional[ReflectionNote] = None
    policy_hint: Dict[str, Any] = field(default_factory=dict)
    response_tendency: Optional[ResponseTendency] = None
    confidence_meta: Dict[str, Any] = field(default_factory=dict)
    developmental_summary: Dict[str, Any] = field(default_factory=dict)
    developmental_shadow_delta: Dict[str, Any] = field(default_factory=dict)
    developmental_gate: Dict[str, Any] = field(default_factory=dict)
    developmental_self_delta: Dict[str, Any] = field(default_factory=dict)
    developmental_proposal_candidates: List[Dict[str, Any]] = field(default_factory=list)
    developmental_continuity_snapshot: Dict[str, Any] = field(default_factory=dict)
    developmental_priority_hints: Dict[str, Any] = field(default_factory=dict)
    developmental_audit_entries: List[Dict[str, Any]] = field(default_factory=list)
    developmental_writeback_candidate: Optional[Dict[str, Any]] = None
    embodied_self_delta: Dict[str, Any] = field(default_factory=dict)
    consequence_update_candidates: List[Dict[str, Any]] = field(default_factory=list)
    resource_boundary_snapshot: Dict[str, Any] = field(default_factory=dict)
    embodied_policy_hints: Dict[str, Any] = field(default_factory=dict)
    repair_or_stabilize_proposal_candidates: List[Dict[str, Any]] = field(default_factory=list)
    embodied_writeback_candidate: Optional[Dict[str, Any]] = None
    social_self_delta: Dict[str, Any] = field(default_factory=dict)
    relation_update_candidates: List[Dict[str, Any]] = field(default_factory=list)
    trust_commitment_snapshot: Dict[str, Any] = field(default_factory=dict)
    social_policy_hints: Dict[str, Any] = field(default_factory=dict)
    repair_proposal_candidates: List[Dict[str, Any]] = field(default_factory=list)
    social_writeback_candidate: Optional[Dict[str, Any]] = None
    self_integration_delta: Dict[str, Any] = field(default_factory=dict)
    cross_axis_priority_snapshot: Dict[str, Any] = field(default_factory=dict)
    proposal_conflict_snapshot: Dict[str, Any] = field(default_factory=dict)
    integrated_policy_hints: Dict[str, Any] = field(default_factory=dict)
    integrated_tendency_proposal: Optional[Dict[str, Any]] = None
    axis_arbitration_hints: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    integration_audit_entries: List[Dict[str, Any]] = field(default_factory=list)
    self_integration_writeback_candidate: Optional[Dict[str, Any]] = None
    initiative_self_delta: Dict[str, Any] = field(default_factory=dict)
    initiative_proposal_candidates: List[Dict[str, Any]] = field(default_factory=list)
    commitment_execution_snapshot: Dict[str, Any] = field(default_factory=dict)
    initiative_policy_hints: Dict[str, Any] = field(default_factory=dict)
    host_proactive_candidate: Optional[Dict[str, Any]] = None
    initiative_audit_entries: List[Dict[str, Any]] = field(default_factory=list)
    initiative_writeback_candidate: Optional[Dict[str, Any]] = None
    initiative_realization_context: Dict[str, Any] = field(default_factory=dict)
    initiative_realization_delta: Dict[str, Any] = field(default_factory=dict)
    commitment_fulfillment_candidates: List[Dict[str, Any]] = field(default_factory=list)
    delivery_readiness_snapshot: Dict[str, Any] = field(default_factory=dict)
    host_lane_hints: List[str] = field(default_factory=list)
    controlled_delivery_candidate: Optional[Dict[str, Any]] = None
    initiative_realization_audit_entries: List[Dict[str, Any]] = field(default_factory=list)
    initiative_realization_writeback_candidate: Optional[Dict[str, Any]] = None
    endogenous_drive_delta: Dict[str, Any] = field(default_factory=dict)
    drive_state_snapshot: Dict[str, Any] = field(default_factory=dict)
    priority_snapshot: Dict[str, Any] = field(default_factory=dict)
    candidate_bias_terms: Dict[str, float] = field(default_factory=dict)
    self_maintenance_candidate: Optional[Dict[str, Any]] = None
    drive_audit_entries: List[Dict[str, Any]] = field(default_factory=list)
    reflective_self_delta: Dict[str, Any] = field(default_factory=dict)
    revision_proposal_candidates: List[Dict[str, Any]] = field(default_factory=list)
    confidence_adjustment_hints: Dict[str, Any] = field(default_factory=dict)
    maintenance_priority_hints: Dict[str, Any] = field(default_factory=dict)
    reflection_writeback_candidate: Optional[Dict[str, Any]] = None
    trace_payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "subject_profile": self.subject_profile,
            "identity_delta": self.identity_delta,
            "self_model_delta": self.self_model_delta,
            "drives_delta": self.drives_delta,
            "cycles_delta": self.cycles_delta,
            "predictive_reflective_delta": self.predictive_reflective_delta,
            "seed_state_delta": self.seed_state_delta,
            "memory_update": self.memory_update,
            "candidate_actions": self.candidate_actions,
            "reflection_note": self.reflection_note.to_dict() if self.reflection_note else None,
            "policy_hint": self.policy_hint,
            "response_tendency": self.response_tendency.to_dict() if self.response_tendency else None,
            "confidence_meta": self.confidence_meta,
            "developmental_summary": self.developmental_summary,
            "developmental_shadow_delta": self.developmental_shadow_delta,
            "developmental_gate": self.developmental_gate,
            "developmental_self_delta": self.developmental_self_delta,
            "developmental_proposal_candidates": self.developmental_proposal_candidates,
            "developmental_continuity_snapshot": self.developmental_continuity_snapshot,
            "developmental_priority_hints": self.developmental_priority_hints,
            "developmental_audit_entries": self.developmental_audit_entries,
            "developmental_writeback_candidate": self.developmental_writeback_candidate,
            "embodied_self_delta": self.embodied_self_delta,
            "consequence_update_candidates": self.consequence_update_candidates,
            "resource_boundary_snapshot": self.resource_boundary_snapshot,
            "embodied_policy_hints": self.embodied_policy_hints,
            "repair_or_stabilize_proposal_candidates": self.repair_or_stabilize_proposal_candidates,
            "embodied_writeback_candidate": self.embodied_writeback_candidate,
            "social_self_delta": self.social_self_delta,
            "relation_update_candidates": self.relation_update_candidates,
            "trust_commitment_snapshot": self.trust_commitment_snapshot,
            "social_policy_hints": self.social_policy_hints,
            "repair_proposal_candidates": self.repair_proposal_candidates,
            "social_writeback_candidate": self.social_writeback_candidate,
            "self_integration_delta": self.self_integration_delta,
            "cross_axis_priority_snapshot": self.cross_axis_priority_snapshot,
            "proposal_conflict_snapshot": self.proposal_conflict_snapshot,
            "integrated_policy_hints": self.integrated_policy_hints,
            "integrated_tendency_proposal": self.integrated_tendency_proposal,
            "axis_arbitration_hints": self.axis_arbitration_hints,
            "integration_audit_entries": self.integration_audit_entries,
            "self_integration_writeback_candidate": self.self_integration_writeback_candidate,
            "initiative_self_delta": self.initiative_self_delta,
            "initiative_proposal_candidates": self.initiative_proposal_candidates,
            "commitment_execution_snapshot": self.commitment_execution_snapshot,
            "initiative_policy_hints": self.initiative_policy_hints,
            "host_proactive_candidate": self.host_proactive_candidate,
            "initiative_audit_entries": self.initiative_audit_entries,
            "initiative_writeback_candidate": self.initiative_writeback_candidate,
            "initiative_realization_context": self.initiative_realization_context,
            "initiative_realization_delta": self.initiative_realization_delta,
            "commitment_fulfillment_candidates": self.commitment_fulfillment_candidates,
            "delivery_readiness_snapshot": self.delivery_readiness_snapshot,
            "host_lane_hints": self.host_lane_hints,
            "controlled_delivery_candidate": self.controlled_delivery_candidate,
            "initiative_realization_audit_entries": self.initiative_realization_audit_entries,
            "initiative_realization_writeback_candidate": self.initiative_realization_writeback_candidate,
            "endogenous_drive_delta": self.endogenous_drive_delta,
            "drive_state_snapshot": self.drive_state_snapshot,
            "priority_snapshot": self.priority_snapshot,
            "candidate_bias_terms": self.candidate_bias_terms,
            "self_maintenance_candidate": self.self_maintenance_candidate,
            "drive_audit_entries": self.drive_audit_entries,
            "reflective_self_delta": self.reflective_self_delta,
            "revision_proposal_candidates": self.revision_proposal_candidates,
            "confidence_adjustment_hints": self.confidence_adjustment_hints,
            "maintenance_priority_hints": self.maintenance_priority_hints,
            "reflection_writeback_candidate": self.reflection_writeback_candidate,
            "trace_payload": self.trace_payload,
        }


def serialize_kernel_output_v2(output: KernelOutputV2) -> Dict[str, Any]:
    return output.to_dict()
