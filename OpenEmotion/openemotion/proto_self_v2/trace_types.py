from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


TRACE_SCHEMA_VERSION = "proto_self.trace.v2"


@dataclass
class ProtoSelfTracePayloadV2:
    schema_version: str = TRACE_SCHEMA_VERSION
    kernel_version: str = "proto_self.v2"
    event_id: str = ""
    subject_profile: Optional[str] = None
    idle_eligible: Optional[bool] = None
    urge_score: Optional[float] = None
    candidate_generated: Optional[bool] = None
    suppression_reason: Optional[str] = None
    update_packet_hash: str = ""
    state_revision_before: int = 0
    state_revision_after: int = 0
    retrieval_summary: Dict[str, Any] = field(default_factory=dict)
    constraint_summary: Dict[str, Any] = field(default_factory=dict)
    perceived: Dict[str, Any] = field(default_factory=dict)
    identity_delta: Dict[str, Any] = field(default_factory=dict)
    self_model_delta: Dict[str, Any] = field(default_factory=dict)
    drives_delta: Dict[str, Any] = field(default_factory=dict)
    endogenous_drive_delta: Dict[str, Any] = field(default_factory=dict)
    drive_state_snapshot: Dict[str, Any] = field(default_factory=dict)
    priority_snapshot: Dict[str, Any] = field(default_factory=dict)
    candidate_bias_terms: Dict[str, float] = field(default_factory=dict)
    self_maintenance_candidate: Optional[Dict[str, Any]] = None
    drive_audit_entries: list = field(default_factory=list)
    drive_context: Dict[str, Any] = field(default_factory=dict)
    cycles_delta: Dict[str, Any] = field(default_factory=dict)
    predictive_reflective_delta: Dict[str, Any] = field(default_factory=dict)
    reflection_note: Optional[Dict[str, Any]] = None
    policy_hint: Dict[str, Any] = field(default_factory=dict)
    response_tendency: Optional[Dict[str, Any]] = None
    candidate_actions: list = field(default_factory=list)
    governor_hint: Dict[str, Any] = field(default_factory=dict)
    executed_action: Optional[Dict[str, Any]] = None
    exec_result: Optional[Dict[str, Any]] = None
    seed_state_delta: Dict[str, Any] = field(default_factory=dict)
    seed_state_snapshot: Dict[str, Any] = field(default_factory=dict)
    developmental: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    legacy_trace_payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "kernel_version": self.kernel_version,
            "event_id": self.event_id,
            "subject_profile": self.subject_profile,
            "idle_eligible": self.idle_eligible,
            "urge_score": self.urge_score,
            "candidate_generated": self.candidate_generated,
            "suppression_reason": self.suppression_reason,
            "update_packet_hash": self.update_packet_hash,
            "state_revision_before": self.state_revision_before,
            "state_revision_after": self.state_revision_after,
            "retrieval_summary": self.retrieval_summary,
            "constraint_summary": self.constraint_summary,
            "perceived": self.perceived,
            "identity_delta": self.identity_delta,
            "self_model_delta": self.self_model_delta,
            "drives_delta": self.drives_delta,
            "endogenous_drive_delta": self.endogenous_drive_delta,
            "drive_state_snapshot": self.drive_state_snapshot,
            "priority_snapshot": self.priority_snapshot,
            "candidate_bias_terms": self.candidate_bias_terms,
            "self_maintenance_candidate": self.self_maintenance_candidate,
            "drive_audit_entries": self.drive_audit_entries,
            "drive_context": self.drive_context,
            "cycles_delta": self.cycles_delta,
            "predictive_reflective_delta": self.predictive_reflective_delta,
            "reflection_note": self.reflection_note,
            "policy_hint": self.policy_hint,
            "response_tendency": self.response_tendency,
            "candidate_actions": self.candidate_actions,
            "governor_hint": self.governor_hint,
            "executed_action": self.executed_action,
            "exec_result": self.exec_result,
            "seed_state_delta": self.seed_state_delta,
            "seed_state_snapshot": self.seed_state_snapshot,
            "developmental": self.developmental,
            "timestamp": self.timestamp,
            "legacy_trace_payload": self.legacy_trace_payload,
        }


def build_trace_payload_v2(**kwargs: Any) -> Dict[str, Any]:
    return ProtoSelfTracePayloadV2(**kwargs).to_dict()
