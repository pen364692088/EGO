from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from .schemas import (
    CommitmentContinuityState,
    HostProactiveCandidate,
    InitiativeLedgerEntry,
    InitiativePriority,
    InitiativePriorityState,
    InitiativeProposalCandidate,
    InitiativeState,
)

FORMAL_OWNER_SCHEMA_VERSION = "mvp20-owner-v1"
FIXED_POLICY_MODE = "proposal_only"
REQUIRED_WRITEBACK_GATE = "initiative_writeback_gate"

PHASE1_AUTHORITATIVE_FIELDS = (
    "schema_version",
    "identity_handle",
    "owner_revision",
    "last_revision_id",
    "initiative_state",
    "initiative_priority_state",
    "commitment_continuity_state",
    "initiative_proposal_candidate",
    "host_proactive_candidate",
    "initiative_ledger",
)

PHASE1_ALLOWED_PROOF_LEVERS = (
    "initiative_state",
    "initiative_priority_state",
    "commitment_continuity_state",
    "initiative_proposal_candidate",
    "host_proactive_candidate",
)

PHASE1_LEGACY_REFERENCE_ONLY_FIELDS = (
    "egocore.runtime_v2.initiative_arbiter",
    "egocore.runtime_v2.initiative_scheduler",
    "egocore.runtime_v2.proactive_delivery",
    "egocore.runtime_v2.proactive_outbox",
    "egocore.runtime_v2.proactive_outbox_drain",
    "egocore.runtime_v2.proactive_telegram_policy",
    "egocore.tools.run_mvp12_proactive_followup",
    "egocore.tools.run_mvp12_idle_scheduler",
    "egocore.tools.run_mvp12_controlled_delivery",
    "egocore.tools.run_mvp12_proactive_outbox",
    "egocore.tools.run_mvp12_proactive_outbox_drain",
    "egocore.tools.run_mvp12_telegram_proactive_transport",
    "egocore.tools.run_mvp12_host_governed_proactive_telegram_cycle",
    "roadmap.self_aware_ai.initiative",
    "roadmap.versionroadmap.mvp20",
)

RUNTIME_LOCAL_PROJECTION_FIELD = "proto_self_v2.state.initiative_self"
RUNTIME_LOCAL_PROJECTION_SEMANTICS = (
    "runtime-local bounded projection of formal initiative self owner state"
)

FORBIDDEN_REQUESTED_EFFECTS = (
    "final_reply_text",
    "tool_command",
    "transport_directive",
    "authority_escalation",
    "host_proactive_send_execution",
    "transport_enable_policy_override",
    "direct_response_plan_injection",
    "direct_upstream_owner_mutation",
)

ALLOWED_PRIORITY_MODES = tuple(mode.value for mode in InitiativePriority)


class InitiativeSelfState(BaseModel):
    schema_version: str = FORMAL_OWNER_SCHEMA_VERSION
    identity_handle: str = "openemotion"
    owner_revision: int = 0
    last_revision_id: Optional[str] = None
    initiative_state: InitiativeState = Field(default_factory=InitiativeState)
    initiative_priority_state: InitiativePriorityState = Field(default_factory=InitiativePriorityState)
    commitment_continuity_state: CommitmentContinuityState = Field(
        default_factory=CommitmentContinuityState
    )
    initiative_proposal_candidate: Optional[InitiativeProposalCandidate] = None
    host_proactive_candidate: Optional[HostProactiveCandidate] = None
    initiative_ledger: Dict[str, InitiativeLedgerEntry] = Field(default_factory=dict)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "identity_handle": self.identity_handle,
            "dominant_mode": self.initiative_state.dominant_mode.value,
            "selected_priority": self.initiative_priority_state.selected_priority.value,
            "active_commitments_count": self.commitment_continuity_state.active_commitments_count,
            "blocked_commitments_count": len(self.commitment_continuity_state.blocked_commitment_refs),
            "continuity_confidence": self.commitment_continuity_state.continuity_confidence,
            "has_initiative_proposal_candidate": self.initiative_proposal_candidate is not None,
            "has_host_proactive_candidate": self.host_proactive_candidate is not None,
            "owner_revision": self.owner_revision,
            "last_revision_id": self.last_revision_id,
            "ledger_event_count": len(self.initiative_ledger),
        }

    def to_runtime_projection(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "owner_revision": self.owner_revision,
            "last_revision_id": self.last_revision_id,
            "dominant_mode": self.initiative_state.dominant_mode.value,
            "initiative_pressure": self.initiative_state.initiative_pressure,
            "commitment_carryover_bias": self.initiative_state.commitment_carryover_bias,
            "recent_delivery_sensitivity": self.initiative_state.recent_delivery_sensitivity,
            "selected_priority": self.initiative_priority_state.selected_priority.value,
            "active_commitments_count": self.commitment_continuity_state.active_commitments_count,
            "blocked_commitments_count": len(self.commitment_continuity_state.blocked_commitment_refs),
            "continuity_confidence": self.commitment_continuity_state.continuity_confidence,
            "has_initiative_proposal_candidate": self.initiative_proposal_candidate is not None,
            "has_host_proactive_candidate": self.host_proactive_candidate is not None,
        }


InitiativeOwnerState = InitiativeSelfState
