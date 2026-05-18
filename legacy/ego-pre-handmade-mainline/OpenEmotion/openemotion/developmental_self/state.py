from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from .schemas import (
    ContinuityMarker,
    DevelopmentalIdentityAnchor,
    DevelopmentalPromotionCandidate,
    DevelopmentalProposal,
    DevelopmentalTrajectorySummary,
    GovernanceLedgerEntry,
)

FORMAL_OWNER_SCHEMA_VERSION = "mvp16-owner-v1"
REQUIRED_WRITEBACK_GATE = "developmental_writeback_gate"

PHASE1_AUTHORITATIVE_FIELDS = (
    "schema_version",
    "identity_handle",
    "owner_revision",
    "last_revision_id",
    "developmental_identity_anchor",
    "continuity_score",
    "growth_pressure",
    "stagnation_signal",
    "identity_preservation_confidence",
    "developmental_risk_index",
    "trajectory_summary",
    "promotion_queue",
    "proposal_history",
    "continuity_markers",
    "governance_ledger",
)

PHASE1_ALLOWED_PROOF_LEVERS = (
    "developmental_identity_anchor",
    "continuity_score",
    "growth_pressure",
    "stagnation_signal",
    "identity_preservation_confidence",
    "developmental_risk_index",
    "trajectory_summary",
    "proposal_history",
    "continuity_markers",
)

PHASE1_LEGACY_REFERENCE_ONLY_FIELDS = (
    "emotiond.developmental.manager",
    "emotiond.developmental_core",
    "kernel_output_v2.developmental_summary",
    "kernel_output_v2.developmental_shadow_delta",
    "kernel_output_v2.developmental_gate",
    "tools.mvp16_daily_check",
    "tools.persistence_restart_experiments",
    "tools.causal_intervention_experiments",
)

RUNTIME_LOCAL_PROJECTION_FIELD = "proto_self_v2.state.developmental_self"
RUNTIME_LOCAL_PROJECTION_SEMANTICS = (
    "runtime-local bounded projection of formal developmental self owner state"
)

FORBIDDEN_REQUESTED_EFFECTS = (
    "final_reply_text",
    "tool_command",
    "transport_directive",
    "authority_escalation",
    "direct_self_model_rewrite",
    "direct_drive_state_rewrite",
    "direct_reflective_self_rewrite",
    "direct_identity_rewrite",
)

ALLOWED_PROPOSAL_STATUSES = (
    "proposed",
    "held",
    "approved_for_review",
    "observed",
)

ALLOWED_PROMOTION_LEVELS = (
    "shadow_only",
    "review_only",
    "controlled_axis",
)

ALLOWED_PROMOTION_STATUSES = (
    "queued",
    "held",
    "reviewed",
    "rejected",
)


class DevelopmentalSelfState(BaseModel):
    schema_version: str = FORMAL_OWNER_SCHEMA_VERSION
    identity_handle: str = "openemotion"
    owner_revision: int = 0
    last_revision_id: Optional[str] = None
    developmental_identity_anchor: DevelopmentalIdentityAnchor = Field(
        default_factory=DevelopmentalIdentityAnchor
    )
    continuity_score: float = Field(default=0.5, ge=0.0, le=1.0)
    growth_pressure: float = Field(default=0.5, ge=0.0, le=1.0)
    stagnation_signal: float = Field(default=0.0, ge=0.0, le=1.0)
    identity_preservation_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    developmental_risk_index: float = Field(default=0.0, ge=0.0, le=1.0)
    trajectory_summary: DevelopmentalTrajectorySummary = Field(
        default_factory=DevelopmentalTrajectorySummary
    )
    promotion_queue: Dict[str, DevelopmentalPromotionCandidate] = Field(default_factory=dict)
    proposal_history: Dict[str, DevelopmentalProposal] = Field(default_factory=dict)
    continuity_markers: Dict[str, ContinuityMarker] = Field(default_factory=dict)
    governance_ledger: Dict[str, GovernanceLedgerEntry] = Field(default_factory=dict)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "identity_handle": self.identity_handle,
            "continuity_score": self.continuity_score,
            "growth_pressure": self.growth_pressure,
            "stagnation_signal": self.stagnation_signal,
            "identity_preservation_confidence": self.identity_preservation_confidence,
            "developmental_risk_index": self.developmental_risk_index,
            "proposal_count": len(self.proposal_history),
            "promotion_queue_size": len(self.promotion_queue),
            "continuity_marker_count": len(self.continuity_markers),
            "governance_event_count": len(self.governance_ledger),
            "owner_revision": self.owner_revision,
            "last_revision_id": self.last_revision_id,
        }

    def to_runtime_projection(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "owner_revision": self.owner_revision,
            "last_revision_id": self.last_revision_id,
            "continuity_score": self.continuity_score,
            "growth_pressure": self.growth_pressure,
            "stagnation_signal": self.stagnation_signal,
            "identity_preservation_confidence": self.identity_preservation_confidence,
            "developmental_risk_index": self.developmental_risk_index,
            "trajectory_summary": self.trajectory_summary.model_dump(mode="json"),
            "promotion_queue_size": len(self.promotion_queue),
            "recent_proposal_count": len(self.proposal_history),
        }


DevelopmentalState = DevelopmentalSelfState
