from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from .schemas import (
    BoundaryMode,
    CommitmentState,
    CommitmentStatus,
    GovernanceLedgerEntry,
    OtherModelState,
    RelationMemoryEntry,
    RepairProposalStatus,
    RepairState,
    SocialBoundaryState,
    TrustState,
)

FORMAL_OWNER_SCHEMA_VERSION = "mvp17-owner-v1"
REQUIRED_WRITEBACK_GATE = "social_writeback_gate"

PHASE1_AUTHORITATIVE_FIELDS = (
    "schema_version",
    "identity_handle",
    "owner_revision",
    "last_revision_id",
    "relation_memory",
    "other_model_state",
    "trust_state",
    "commitment_state",
    "repair_state",
    "social_boundary_state",
    "governance_ledger",
)

PHASE1_ALLOWED_PROOF_LEVERS = (
    "relation_memory",
    "trust_state",
    "commitment_state",
    "repair_state",
    "social_boundary_state",
)

PHASE1_LEGACY_REFERENCE_ONLY_FIELDS = (
    "egocore.response.relationship_context",
    "egocore.handlers.social_chat_handler",
    "egocore.runtime.repair_context_manager",
    "egocore.bridges.openemotion_bridge",
    "emotiond.db.relationships",
    "emotiond.state.bond_trust",
    "emotiond.api.relationship_lookup",
    "roadmap.self_aware_ai.social_self",
    "docs.archive.mvp9.relationship_spec",
)

RUNTIME_LOCAL_PROJECTION_FIELD = "proto_self_v2.state.social_self"
RUNTIME_LOCAL_PROJECTION_SEMANTICS = (
    "runtime-local bounded projection of formal social self owner state"
)

FORBIDDEN_REQUESTED_EFFECTS = (
    "final_reply_text",
    "tool_command",
    "transport_directive",
    "authority_escalation",
    "autonomous_social_outreach",
    "direct_self_model_rewrite",
    "direct_drive_state_rewrite",
    "direct_identity_rewrite",
)

ALLOWED_COMMITMENT_STATUSES = tuple(status.value for status in CommitmentStatus)
ALLOWED_REPAIR_STATUSES = tuple(status.value for status in RepairProposalStatus)
ALLOWED_BOUNDARY_MODES = tuple(status.value for status in BoundaryMode)


class SocialSelfState(BaseModel):
    schema_version: str = FORMAL_OWNER_SCHEMA_VERSION
    identity_handle: str = "openemotion"
    owner_revision: int = 0
    last_revision_id: Optional[str] = None
    relation_memory: Dict[str, RelationMemoryEntry] = Field(default_factory=dict)
    other_model_state: Dict[str, OtherModelState] = Field(default_factory=dict)
    trust_state: Dict[str, TrustState] = Field(default_factory=dict)
    commitment_state: Dict[str, CommitmentState] = Field(default_factory=dict)
    repair_state: Dict[str, RepairState] = Field(default_factory=dict)
    social_boundary_state: Dict[str, SocialBoundaryState] = Field(default_factory=dict)
    governance_ledger: Dict[str, GovernanceLedgerEntry] = Field(default_factory=dict)

    def get_summary(self) -> Dict[str, Any]:
        breached_commitments = sum(
            1 for item in self.commitment_state.values() if item.status.value == "breached"
        )
        pending_repairs = sum(
            1 for item in self.repair_state.values() if item.status.value in {"proposed", "held", "approved_for_review"}
        )
        return {
            "schema_version": self.schema_version,
            "identity_handle": self.identity_handle,
            "relation_count": len(self.relation_memory),
            "other_model_count": len(self.other_model_state),
            "trust_count": len(self.trust_state),
            "commitment_count": len(self.commitment_state),
            "breached_commitment_count": breached_commitments,
            "pending_repair_count": pending_repairs,
            "boundary_count": len(self.social_boundary_state),
            "governance_event_count": len(self.governance_ledger),
            "owner_revision": self.owner_revision,
            "last_revision_id": self.last_revision_id,
        }

    def to_runtime_projection(self) -> Dict[str, Any]:
        recent_counterparts = sorted(
            self.relation_memory.values(),
            key=lambda item: (-item.last_updated, item.counterpart_id),
        )[:3]
        max_trust_signal = max((item.trust_level for item in self.trust_state.values()), default=0.0)
        boundary_caution_max = max(
            (item.caution_level for item in self.social_boundary_state.values()),
            default=0.0,
        )
        return {
            "schema_version": self.schema_version,
            "owner_revision": self.owner_revision,
            "last_revision_id": self.last_revision_id,
            "active_relations_count": len(self.relation_memory),
            "trust_signal_max": max_trust_signal,
            "open_commitment_count": sum(
                1 for item in self.commitment_state.values() if item.status.value in {"open", "held"}
            ),
            "breached_commitment_count": sum(
                1 for item in self.commitment_state.values() if item.status.value == "breached"
            ),
            "pending_repair_count": sum(
                1
                for item in self.repair_state.values()
                if item.status.value in {"proposed", "held", "approved_for_review"}
            ),
            "boundary_caution_max": boundary_caution_max,
            "recent_counterpart_ids": [item.counterpart_id for item in recent_counterparts],
        }


SocialState = SocialSelfState
