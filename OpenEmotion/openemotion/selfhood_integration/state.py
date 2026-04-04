from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from .schemas import (
    ArbitrationBalance,
    ArbitrationPriority,
    AxisArbitrationHint,
    ConflictSeverity,
    CrossAxisPriorityState,
    IntegratedProposalStatus,
    IntegratedTendencyProposal,
    IntegrationLedgerEntry,
    IntegrationState,
    ProposalConflictState,
)

FORMAL_OWNER_SCHEMA_VERSION = "mvp19-owner-v1"
FIXED_POLICY_MODE = "stability_first"
REQUIRED_WRITEBACK_GATE = "self_integration_writeback_gate"

PHASE1_AUTHORITATIVE_FIELDS = (
    "schema_version",
    "identity_handle",
    "owner_revision",
    "last_revision_id",
    "integration_state",
    "cross_axis_priority_state",
    "proposal_conflict_state",
    "stabilize_explore_balance",
    "repair_progress_balance",
    "social_boundary_balance",
    "integrated_tendency_proposal",
    "axis_arbitration_hints",
    "integration_ledger",
)

PHASE1_ALLOWED_PROOF_LEVERS = (
    "integration_state",
    "cross_axis_priority_state",
    "proposal_conflict_state",
    "stabilize_explore_balance",
    "repair_progress_balance",
    "social_boundary_balance",
    "integrated_tendency_proposal",
    "axis_arbitration_hints",
)

PHASE1_LEGACY_REFERENCE_ONLY_FIELDS = (
    "openemotion.self_model",
    "openemotion.endogenous_drives",
    "openemotion.reflective_self",
    "openemotion.developmental_self",
    "openemotion.social_self",
    "openemotion.embodied_self",
    "openemotion.roadmap.versionroadmap.mvp19",
)

RUNTIME_LOCAL_PROJECTION_FIELD = "proto_self_v2.state.selfhood_integration"
RUNTIME_LOCAL_PROJECTION_SEMANTICS = (
    "runtime-local bounded projection of formal selfhood integration owner state"
)

FORBIDDEN_REQUESTED_EFFECTS = (
    "final_reply_text",
    "tool_command",
    "transport_directive",
    "authority_escalation",
    "direct_self_model_rewrite",
    "direct_drive_state_rewrite",
    "direct_reflective_rewrite",
    "direct_developmental_rewrite",
    "direct_social_rewrite",
    "direct_embodied_rewrite",
    "direct_upstream_owner_mutation",
)

ALLOWED_PRIORITY_MODES = tuple(mode.value for mode in ArbitrationPriority)
ALLOWED_CONFLICT_SEVERITIES = tuple(level.value for level in ConflictSeverity)
ALLOWED_PROPOSAL_STATUSES = tuple(status.value for status in IntegratedProposalStatus)


def _balance(
    *,
    balance_id: str,
    lower_pole: str,
    upper_pole: str,
    lower_weight: float,
    upper_weight: float,
    preferred_pole: str,
    rationale: str,
) -> ArbitrationBalance:
    return ArbitrationBalance(
        balance_id=balance_id,
        lower_pole=lower_pole,
        upper_pole=upper_pole,
        lower_weight=lower_weight,
        upper_weight=upper_weight,
        preferred_pole=preferred_pole,
        rationale=rationale,
    )


def default_stabilize_explore_balance() -> ArbitrationBalance:
    return _balance(
        balance_id="stabilize_explore",
        lower_pole="stabilize",
        upper_pole="explore",
        lower_weight=0.62,
        upper_weight=0.38,
        preferred_pole="stabilize",
        rationale="phase1 stability-first default favors stabilization over exploration",
    )


def default_repair_progress_balance() -> ArbitrationBalance:
    return _balance(
        balance_id="repair_progress",
        lower_pole="repair",
        upper_pole="progress",
        lower_weight=0.58,
        upper_weight=0.42,
        preferred_pole="repair",
        rationale="phase1 stability-first default favors repair when conflict remains active",
    )


def default_social_boundary_balance() -> ArbitrationBalance:
    return _balance(
        balance_id="social_boundary",
        lower_pole="social",
        upper_pole="boundary",
        lower_weight=0.44,
        upper_weight=0.56,
        preferred_pole="boundary",
        rationale="phase1 stability-first default keeps boundary protection slightly ahead of outreach",
    )


class SelfhoodIntegrationState(BaseModel):
    schema_version: str = FORMAL_OWNER_SCHEMA_VERSION
    identity_handle: str = "openemotion"
    owner_revision: int = 0
    last_revision_id: Optional[str] = None
    integration_state: IntegrationState = Field(default_factory=IntegrationState)
    cross_axis_priority_state: CrossAxisPriorityState = Field(default_factory=CrossAxisPriorityState)
    proposal_conflict_state: ProposalConflictState = Field(default_factory=ProposalConflictState)
    stabilize_explore_balance: ArbitrationBalance = Field(
        default_factory=default_stabilize_explore_balance
    )
    repair_progress_balance: ArbitrationBalance = Field(
        default_factory=default_repair_progress_balance
    )
    social_boundary_balance: ArbitrationBalance = Field(
        default_factory=default_social_boundary_balance
    )
    integrated_tendency_proposal: Optional[IntegratedTendencyProposal] = None
    axis_arbitration_hints: Dict[str, AxisArbitrationHint] = Field(default_factory=dict)
    integration_ledger: Dict[str, IntegrationLedgerEntry] = Field(default_factory=dict)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "identity_handle": self.identity_handle,
            "policy_mode": self.integration_state.policy_mode,
            "integration_posture": self.integration_state.posture.value,
            "selected_priority": self.cross_axis_priority_state.selected_priority.value,
            "hint_count": len(self.axis_arbitration_hints),
            "conflict_count": self.proposal_conflict_state.conflict_count,
            "highest_conflict_severity": self.proposal_conflict_state.highest_severity.value,
            "has_integrated_tendency_proposal": self.integrated_tendency_proposal is not None,
            "integration_confidence": self.integration_state.integration_confidence,
            "owner_revision": self.owner_revision,
            "last_revision_id": self.last_revision_id,
            "ledger_event_count": len(self.integration_ledger),
        }

    def to_runtime_projection(self) -> Dict[str, Any]:
        tendency_status = (
            self.integrated_tendency_proposal.status.value
            if self.integrated_tendency_proposal is not None
            else "missing"
        )
        return {
            "schema_version": self.schema_version,
            "owner_revision": self.owner_revision,
            "last_revision_id": self.last_revision_id,
            "policy_mode": self.integration_state.policy_mode,
            "integration_posture": self.integration_state.posture.value,
            "integration_confidence": self.integration_state.integration_confidence,
            "selected_priority": self.cross_axis_priority_state.selected_priority.value,
            "dominant_pressure_axis": self.integration_state.dominant_pressure_axis,
            "highest_conflict_severity": self.proposal_conflict_state.highest_severity.value,
            "stabilize_weight": self.stabilize_explore_balance.lower_weight,
            "explore_weight": self.stabilize_explore_balance.upper_weight,
            "repair_weight": self.repair_progress_balance.lower_weight,
            "progress_weight": self.repair_progress_balance.upper_weight,
            "social_weight": self.social_boundary_balance.lower_weight,
            "boundary_weight": self.social_boundary_balance.upper_weight,
            "active_hint_axes": sorted(self.axis_arbitration_hints.keys()),
            "tendency_status": tendency_status,
        }


IntegrationOwnerState = SelfhoodIntegrationState
