from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from .schemas import (
    CommitmentFulfillmentState,
    ControlledDeliveryCandidate,
    DeliveryReadinessState,
    InitiativeRealizationCandidate,
    RealizationLedgerEntry,
    RealizationMode,
    RealizationState,
)

FORMAL_OWNER_SCHEMA_VERSION = "mvp21-owner-v1"
FIXED_POLICY_MODE = "proposal_only"
REQUIRED_WRITEBACK_GATE = "initiative_realization_writeback_gate"

PHASE1_AUTHORITATIVE_FIELDS = (
    "schema_version",
    "identity_handle",
    "owner_revision",
    "last_revision_id",
    "realization_state",
    "delivery_readiness_state",
    "commitment_fulfillment_state",
    "initiative_realization_candidate",
    "controlled_delivery_candidate",
    "realization_ledger",
)

PHASE1_ALLOWED_PROOF_LEVERS = (
    "realization_state",
    "delivery_readiness_state",
    "commitment_fulfillment_state",
    "initiative_realization_candidate",
    "controlled_delivery_candidate",
)

PHASE1_LEGACY_REFERENCE_ONLY_FIELDS = (
    "egocore.runtime_v2.initiative_scheduler",
    "egocore.runtime_v2.proactive_delivery",
    "egocore.runtime_v2.proactive_outbox",
    "egocore.runtime_v2.proactive_outbox_drain",
    "egocore.runtime_v2.proactive_telegram_policy",
    "egocore.runtime_v2.host_proactive_outbox",
    "egocore.tools.run_mvp12_controlled_delivery",
    "egocore.tools.run_mvp12_proactive_outbox",
    "egocore.tools.run_mvp12_proactive_outbox_drain",
    "egocore.tools.run_mvp12_telegram_proactive_transport",
    "egocore.tools.run_mvp12_host_governed_proactive_telegram_cycle",
    "roadmap.self_aware_ai.initiative_realization",
    "roadmap.versionroadmap.mvp21",
)

RUNTIME_LOCAL_PROJECTION_FIELD = "proto_self_v2.state.initiative_realization"
RUNTIME_LOCAL_PROJECTION_SEMANTICS = (
    "runtime-local bounded projection of formal initiative realization owner state"
)

FORBIDDEN_REQUESTED_EFFECTS = (
    "final_reply_text",
    "tool_command",
    "transport_directive",
    "authority_escalation",
    "direct_outbox_execution",
    "host_delivery_gate_override",
    "direct_response_plan_injection",
    "direct_upstream_owner_mutation",
)

ALLOWED_REALIZATION_MODES = tuple(mode.value for mode in RealizationMode)


class InitiativeRealizationState(BaseModel):
    schema_version: str = FORMAL_OWNER_SCHEMA_VERSION
    identity_handle: str = "openemotion"
    owner_revision: int = 0
    last_revision_id: Optional[str] = None
    realization_state: RealizationState = Field(default_factory=RealizationState)
    delivery_readiness_state: DeliveryReadinessState = Field(default_factory=DeliveryReadinessState)
    commitment_fulfillment_state: CommitmentFulfillmentState = Field(
        default_factory=CommitmentFulfillmentState
    )
    initiative_realization_candidate: Optional[InitiativeRealizationCandidate] = None
    controlled_delivery_candidate: Optional[ControlledDeliveryCandidate] = None
    realization_ledger: Dict[str, RealizationLedgerEntry] = Field(default_factory=dict)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "identity_handle": self.identity_handle,
            "dominant_mode": self.realization_state.dominant_mode.value,
            "selected_lane": self.delivery_readiness_state.selected_lane.value,
            "active_commitments_count": self.commitment_fulfillment_state.active_commitments_count,
            "ready_commitments_count": self.commitment_fulfillment_state.ready_commitments_count,
            "continuity_confidence": self.commitment_fulfillment_state.continuity_confidence,
            "has_realization_candidate": self.initiative_realization_candidate is not None,
            "has_controlled_delivery_candidate": self.controlled_delivery_candidate is not None,
            "owner_revision": self.owner_revision,
            "last_revision_id": self.last_revision_id,
            "ledger_event_count": len(self.realization_ledger),
        }

    def to_runtime_projection(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "owner_revision": self.owner_revision,
            "last_revision_id": self.last_revision_id,
            "dominant_mode": self.realization_state.dominant_mode.value,
            "realization_pressure": self.realization_state.realization_pressure,
            "fulfillment_readiness": self.realization_state.fulfillment_readiness,
            "hold_bias": self.realization_state.hold_bias,
            "failure_recovery_bias": self.realization_state.failure_recovery_bias,
            "selected_lane": self.delivery_readiness_state.selected_lane.value,
            "active_commitments_count": self.commitment_fulfillment_state.active_commitments_count,
            "ready_commitments_count": self.commitment_fulfillment_state.ready_commitments_count,
            "continuity_confidence": self.commitment_fulfillment_state.continuity_confidence,
            "has_realization_candidate": self.initiative_realization_candidate is not None,
            "has_controlled_delivery_candidate": self.controlled_delivery_candidate is not None,
        }


RealizationOwnerState = InitiativeRealizationState
