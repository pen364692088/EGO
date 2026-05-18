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
    reflective_self_delta: Dict[str, Any] = field(default_factory=dict)
    revision_proposal_candidates: list = field(default_factory=list)
    confidence_adjustment_hints: Dict[str, Any] = field(default_factory=dict)
    maintenance_priority_hints: Dict[str, Any] = field(default_factory=dict)
    reflection_writeback_candidate: Optional[Dict[str, Any]] = None
    reflection_context: Dict[str, Any] = field(default_factory=dict)
    cycles_delta: Dict[str, Any] = field(default_factory=dict)
    predictive_reflective_delta: Dict[str, Any] = field(default_factory=dict)
    reflection_note: Optional[Dict[str, Any]] = None
    policy_hint: Dict[str, Any] = field(default_factory=dict)
    response_tendency: Optional[Dict[str, Any]] = None
    predicted_outcome: Any = None
    actual_outcome: Any = None
    adjustment_applied: Optional[str] = None
    next_guard: Optional[str] = None
    replay_variant_id: Optional[str] = None
    candidate_actions: list = field(default_factory=list)
    governor_hint: Dict[str, Any] = field(default_factory=dict)
    executed_action: Optional[Dict[str, Any]] = None
    exec_result: Optional[Dict[str, Any]] = None
    seed_state_delta: Dict[str, Any] = field(default_factory=dict)
    seed_state_snapshot: Dict[str, Any] = field(default_factory=dict)
    developmental: Dict[str, Any] = field(default_factory=dict)
    developmental_self_delta: Dict[str, Any] = field(default_factory=dict)
    developmental_proposal_candidates: list = field(default_factory=list)
    developmental_continuity_snapshot: Dict[str, Any] = field(default_factory=dict)
    developmental_priority_hints: Dict[str, Any] = field(default_factory=dict)
    developmental_audit_entries: list = field(default_factory=list)
    developmental_writeback_candidate: Optional[Dict[str, Any]] = None
    developmental_context: Dict[str, Any] = field(default_factory=dict)
    embodied_self_delta: Dict[str, Any] = field(default_factory=dict)
    consequence_update_candidates: list = field(default_factory=list)
    resource_boundary_snapshot: Dict[str, Any] = field(default_factory=dict)
    embodied_policy_hints: Dict[str, Any] = field(default_factory=dict)
    repair_or_stabilize_proposal_candidates: list = field(default_factory=list)
    embodied_writeback_candidate: Optional[Dict[str, Any]] = None
    environment_context: Dict[str, Any] = field(default_factory=dict)
    social_self_delta: Dict[str, Any] = field(default_factory=dict)
    relation_update_candidates: list = field(default_factory=list)
    trust_commitment_snapshot: Dict[str, Any] = field(default_factory=dict)
    social_policy_hints: Dict[str, Any] = field(default_factory=dict)
    repair_proposal_candidates: list = field(default_factory=list)
    social_writeback_candidate: Optional[Dict[str, Any]] = None
    social_context: Dict[str, Any] = field(default_factory=dict)
    selfhood_integration_context: Dict[str, Any] = field(default_factory=dict)
    self_integration_delta: Dict[str, Any] = field(default_factory=dict)
    cross_axis_priority_snapshot: Dict[str, Any] = field(default_factory=dict)
    proposal_conflict_snapshot: Dict[str, Any] = field(default_factory=dict)
    integrated_policy_hints: Dict[str, Any] = field(default_factory=dict)
    integrated_tendency_proposal: Optional[Dict[str, Any]] = None
    axis_arbitration_hints: Dict[str, Any] = field(default_factory=dict)
    integration_audit_entries: list = field(default_factory=list)
    self_integration_writeback_candidate: Optional[Dict[str, Any]] = None
    initiative_context: Dict[str, Any] = field(default_factory=dict)
    initiative_self_delta: Dict[str, Any] = field(default_factory=dict)
    initiative_proposal_candidates: list = field(default_factory=list)
    commitment_execution_snapshot: Dict[str, Any] = field(default_factory=dict)
    initiative_policy_hints: Dict[str, Any] = field(default_factory=dict)
    host_proactive_candidate: Optional[Dict[str, Any]] = None
    initiative_audit_entries: list = field(default_factory=list)
    initiative_writeback_candidate: Optional[Dict[str, Any]] = None
    initiative_realization_context: Dict[str, Any] = field(default_factory=dict)
    initiative_realization_delta: Dict[str, Any] = field(default_factory=dict)
    commitment_fulfillment_candidates: list = field(default_factory=list)
    delivery_readiness_snapshot: Dict[str, Any] = field(default_factory=dict)
    host_lane_hints: list = field(default_factory=list)
    controlled_delivery_candidate: Optional[Dict[str, Any]] = None
    initiative_realization_audit_entries: list = field(default_factory=list)
    initiative_realization_writeback_candidate: Optional[Dict[str, Any]] = None
    shadow_h1: Optional[Dict[str, Any]] = None
    timestamp: str = ""
    legacy_trace_payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
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
            "reflective_self_delta": self.reflective_self_delta,
            "revision_proposal_candidates": self.revision_proposal_candidates,
            "confidence_adjustment_hints": self.confidence_adjustment_hints,
            "maintenance_priority_hints": self.maintenance_priority_hints,
            "reflection_writeback_candidate": self.reflection_writeback_candidate,
            "reflection_context": self.reflection_context,
            "cycles_delta": self.cycles_delta,
            "predictive_reflective_delta": self.predictive_reflective_delta,
            "reflection_note": self.reflection_note,
            "policy_hint": self.policy_hint,
            "response_tendency": self.response_tendency,
            "predicted_outcome": self.predicted_outcome,
            "actual_outcome": self.actual_outcome,
            "adjustment_applied": self.adjustment_applied,
            "next_guard": self.next_guard,
            "replay_variant_id": self.replay_variant_id,
            "candidate_actions": self.candidate_actions,
            "governor_hint": self.governor_hint,
            "executed_action": self.executed_action,
            "exec_result": self.exec_result,
            "seed_state_delta": self.seed_state_delta,
            "seed_state_snapshot": self.seed_state_snapshot,
            "developmental": self.developmental,
            "developmental_self_delta": self.developmental_self_delta,
            "developmental_proposal_candidates": self.developmental_proposal_candidates,
            "developmental_continuity_snapshot": self.developmental_continuity_snapshot,
            "developmental_priority_hints": self.developmental_priority_hints,
            "developmental_audit_entries": self.developmental_audit_entries,
            "developmental_writeback_candidate": self.developmental_writeback_candidate,
            "developmental_context": self.developmental_context,
            "embodied_self_delta": self.embodied_self_delta,
            "consequence_update_candidates": self.consequence_update_candidates,
            "resource_boundary_snapshot": self.resource_boundary_snapshot,
            "embodied_policy_hints": self.embodied_policy_hints,
            "repair_or_stabilize_proposal_candidates": self.repair_or_stabilize_proposal_candidates,
            "embodied_writeback_candidate": self.embodied_writeback_candidate,
            "environment_context": self.environment_context,
            "social_self_delta": self.social_self_delta,
            "relation_update_candidates": self.relation_update_candidates,
            "trust_commitment_snapshot": self.trust_commitment_snapshot,
            "social_policy_hints": self.social_policy_hints,
            "repair_proposal_candidates": self.repair_proposal_candidates,
            "social_writeback_candidate": self.social_writeback_candidate,
            "social_context": self.social_context,
            "selfhood_integration_context": self.selfhood_integration_context,
            "self_integration_delta": self.self_integration_delta,
            "cross_axis_priority_snapshot": self.cross_axis_priority_snapshot,
            "proposal_conflict_snapshot": self.proposal_conflict_snapshot,
            "integrated_policy_hints": self.integrated_policy_hints,
            "integrated_tendency_proposal": self.integrated_tendency_proposal,
            "axis_arbitration_hints": self.axis_arbitration_hints,
            "integration_audit_entries": self.integration_audit_entries,
            "self_integration_writeback_candidate": self.self_integration_writeback_candidate,
            "initiative_context": self.initiative_context,
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
            "timestamp": self.timestamp,
            "legacy_trace_payload": self.legacy_trace_payload,
        }
        if self.shadow_h1 is not None:
            payload["shadow_h1"] = self.shadow_h1
        return payload


def build_trace_payload_v2(**kwargs: Any) -> Dict[str, Any]:
    return ProtoSelfTracePayloadV2(**kwargs).to_dict()
