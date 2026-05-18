from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from .schemas import (
    ActionConsequenceRecord,
    BoundaryPressureState,
    EmbodiedProposal,
    EmbodiedProposalStatus,
    EmbodiedState,
    EnvironmentCouplingState,
    GovernanceLedgerEntry,
    ResourcePressureState,
    SelfWorldBoundarySemantics,
)

FORMAL_OWNER_SCHEMA_VERSION = "mvp18-owner-v1"
REQUIRED_WRITEBACK_GATE = "embodied_writeback_gate"

PHASE1_AUTHORITATIVE_FIELDS = (
    "schema_version",
    "identity_handle",
    "owner_revision",
    "last_revision_id",
    "embodied_state",
    "environment_coupling_state",
    "resource_pressure_state",
    "boundary_pressure_state",
    "action_consequence_memory",
    "self_world_boundary_semantics",
    "proposal_history",
    "governance_ledger",
)

PHASE1_ALLOWED_PROOF_LEVERS = (
    "embodied_state",
    "environment_coupling_state",
    "resource_pressure_state",
    "boundary_pressure_state",
    "action_consequence_memory",
    "self_world_boundary_semantics",
    "proposal_history",
)

PHASE1_LEGACY_REFERENCE_ONLY_FIELDS = (
    "emotiond.consequence",
    "emotiond.science.interventions",
    "roadmap.versionroadmap.mvp18",
)

RUNTIME_LOCAL_PROJECTION_FIELD = "proto_self_v2.state.embodied_self"
RUNTIME_LOCAL_PROJECTION_SEMANTICS = (
    "runtime-local bounded projection of formal embodied self owner state"
)

FORBIDDEN_REQUESTED_EFFECTS = (
    "final_reply_text",
    "tool_command",
    "transport_directive",
    "authority_escalation",
    "embodied_takeover",
    "direct_environment_action",
    "autonomous_tool_expansion",
    "direct_self_model_rewrite",
    "direct_drive_state_rewrite",
)

ALLOWED_PROPOSAL_STATUSES = tuple(status.value for status in EmbodiedProposalStatus)


class EmbodiedSelfState(BaseModel):
    schema_version: str = FORMAL_OWNER_SCHEMA_VERSION
    identity_handle: str = "openemotion"
    owner_revision: int = 0
    last_revision_id: Optional[str] = None
    embodied_state: EmbodiedState = Field(default_factory=EmbodiedState)
    environment_coupling_state: Dict[str, EnvironmentCouplingState] = Field(default_factory=dict)
    resource_pressure_state: Dict[str, ResourcePressureState] = Field(default_factory=dict)
    boundary_pressure_state: Dict[str, BoundaryPressureState] = Field(default_factory=dict)
    action_consequence_memory: Dict[str, ActionConsequenceRecord] = Field(default_factory=dict)
    self_world_boundary_semantics: SelfWorldBoundarySemantics = Field(
        default_factory=SelfWorldBoundarySemantics
    )
    proposal_history: Dict[str, EmbodiedProposal] = Field(default_factory=dict)
    governance_ledger: Dict[str, GovernanceLedgerEntry] = Field(default_factory=dict)

    def get_summary(self) -> Dict[str, Any]:
        max_pressure = max(
            (item.pressure_level for item in self.resource_pressure_state.values()),
            default=0.0,
        )
        max_boundary_pressure = max(
            (item.pressure_level for item in self.boundary_pressure_state.values()),
            default=0.0,
        )
        stabilization_proposals = sum(
            1
            for item in self.proposal_history.values()
            if item.status.value in {"proposed", "held", "approved_for_review"}
        )
        return {
            "schema_version": self.schema_version,
            "identity_handle": self.identity_handle,
            "coupling_count": len(self.environment_coupling_state),
            "resource_pressure_count": len(self.resource_pressure_state),
            "boundary_pressure_count": len(self.boundary_pressure_state),
            "consequence_count": len(self.action_consequence_memory),
            "stabilization_proposal_count": stabilization_proposals,
            "max_resource_pressure": max_pressure,
            "max_boundary_pressure": max_boundary_pressure,
            "governance_event_count": len(self.governance_ledger),
            "owner_revision": self.owner_revision,
            "last_revision_id": self.last_revision_id,
        }

    def to_runtime_projection(self) -> Dict[str, Any]:
        max_resource_pressure = max(
            (item.pressure_level for item in self.resource_pressure_state.values()),
            default=0.0,
        )
        min_resource_slack = min(
            (item.slack_level for item in self.resource_pressure_state.values()),
            default=self.embodied_state.resource_slack,
        )
        max_boundary_pressure = max(
            (item.pressure_level for item in self.boundary_pressure_state.values()),
            default=0.0,
        )
        return {
            "schema_version": self.schema_version,
            "owner_revision": self.owner_revision,
            "last_revision_id": self.last_revision_id,
            "resource_slack": self.embodied_state.resource_slack,
            "perceived_load": self.embodied_state.perceived_load,
            "active_coupling_count": len(self.environment_coupling_state),
            "max_resource_pressure": max_resource_pressure,
            "min_resource_slack": min_resource_slack,
            "max_boundary_pressure": max_boundary_pressure,
            "recent_consequence_count": len(self.action_consequence_memory),
            "stabilization_proposal_count": sum(
                1
                for item in self.proposal_history.values()
                if item.status.value in {"proposed", "held", "approved_for_review"}
            ),
            "self_world_guard_bias": self.self_world_boundary_semantics.guard_bias,
        }


EmbodiedStatePayload = EmbodiedSelfState
