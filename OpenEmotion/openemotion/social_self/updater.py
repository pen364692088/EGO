from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional

from .governance import validate_social_state
from .schemas import (
    BoundaryMode,
    CommitmentState,
    CommitmentStatus,
    OtherModelState,
    RelationMemoryEntry,
    RelationshipContinuityStatus,
    RepairProposalStatus,
    RepairState,
    SocialBoundaryState,
    TrustState,
)
from .state import REQUIRED_WRITEBACK_GATE, SocialSelfState
from .store import SocialSelfStore


def _make_id(prefix: str) -> str:
    return f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}"


class SocialSelfOwner:
    _instance: Optional["SocialSelfOwner"] = None

    def __init__(
        self,
        initial_state: Optional[SocialSelfState] = None,
        *,
        store: Optional[SocialSelfStore] = None,
    ):
        self.state = initial_state.model_copy(deep=True) if initial_state is not None else SocialSelfState()
        self.store = store or SocialSelfStore()

    @classmethod
    def get_instance(cls) -> "SocialSelfOwner":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def upsert_relation_memory(
        self,
        *,
        counterpart_id: str,
        relationship_summary: str,
        interaction_role: str = "user",
        continuity_status: RelationshipContinuityStatus = RelationshipContinuityStatus.ACTIVE,
        source_refs: Optional[list[str]] = None,
    ) -> RelationMemoryEntry:
        entry = RelationMemoryEntry(
            counterpart_id=counterpart_id,
            relationship_summary=relationship_summary,
            interaction_role=interaction_role,
            continuity_status=continuity_status,
            source_refs=list(source_refs or []),
        )
        self.state.relation_memory[counterpart_id] = entry
        return entry

    def upsert_other_model(
        self,
        *,
        counterpart_id: str,
        inferred_preferences: Optional[Dict[str, Any]] = None,
        inferred_constraints: Optional[list[str]] = None,
        confidence: float = 0.5,
        source_refs: Optional[list[str]] = None,
    ) -> OtherModelState:
        entry = OtherModelState(
            counterpart_id=counterpart_id,
            inferred_preferences=dict(inferred_preferences or {}),
            inferred_constraints=list(inferred_constraints or []),
            confidence=confidence,
            source_refs=list(source_refs or []),
        )
        self.state.other_model_state[counterpart_id] = entry
        return entry

    def set_trust_state(
        self,
        *,
        counterpart_id: str,
        trust_level: float,
        trust_basis: Optional[list[str]] = None,
        trust_delta: float = 0.0,
    ) -> TrustState:
        entry = TrustState(
            counterpart_id=counterpart_id,
            trust_level=trust_level,
            trust_basis=list(trust_basis or []),
            trust_delta=trust_delta,
        )
        self.state.trust_state[counterpart_id] = entry
        return entry

    def record_commitment(
        self,
        *,
        counterpart_id: str,
        summary: str,
        status: CommitmentStatus = CommitmentStatus.OPEN,
        due_hint: Optional[str] = None,
        source_refs: Optional[list[str]] = None,
        commitment_id: Optional[str] = None,
    ) -> CommitmentState:
        resolved_commitment_id = commitment_id or _make_id("commitment")
        entry = CommitmentState(
            commitment_id=resolved_commitment_id,
            counterpart_id=counterpart_id,
            summary=summary,
            status=status,
            due_hint=due_hint,
            source_refs=list(source_refs or []),
        )
        self.state.commitment_state[resolved_commitment_id] = entry
        return entry

    def propose_repair(
        self,
        *,
        counterpart_id: str,
        issue_summary: str,
        proposed_adjustment: Dict[str, Any],
        justification: str,
        source_refs: Optional[list[str]] = None,
        requested_effects: Optional[list[str]] = None,
        proposal_id: Optional[str] = None,
    ) -> RepairState:
        resolved_proposal_id = proposal_id or _make_id("repair")
        entry = RepairState(
            proposal_id=resolved_proposal_id,
            counterpart_id=counterpart_id,
            issue_summary=issue_summary,
            proposed_adjustment=dict(proposed_adjustment),
            justification=justification,
            required_gate=REQUIRED_WRITEBACK_GATE,
            requested_effects=list(requested_effects or []),
            source_refs=list(source_refs or []),
        )
        self.state.repair_state[resolved_proposal_id] = entry
        return entry

    def set_repair_status(
        self,
        proposal_id: str,
        *,
        status: RepairProposalStatus,
    ) -> RepairState:
        entry = self.state.repair_state[proposal_id]
        entry.status = status
        entry.updated_at = time.time()
        return entry

    def set_social_boundary(
        self,
        *,
        counterpart_id: str,
        caution_level: float,
        boundary_mode: BoundaryMode = BoundaryMode.CAUTIOUS,
        reason: str = "",
        source_refs: Optional[list[str]] = None,
    ) -> SocialBoundaryState:
        entry = SocialBoundaryState(
            counterpart_id=counterpart_id,
            caution_level=caution_level,
            boundary_mode=boundary_mode,
            reason=reason,
            source_refs=list(source_refs or []),
        )
        self.state.social_boundary_state[counterpart_id] = entry
        return entry

    def record_governance_event(
        self,
        *,
        event_type: str,
        reference_id: str,
        gate_verdict: str,
        details: Optional[Dict[str, Any]] = None,
        gate_name: str = REQUIRED_WRITEBACK_GATE,
    ):
        from .schemas import GovernanceLedgerEntry

        ledger_id = _make_id("governance")
        entry = GovernanceLedgerEntry(
            ledger_id=ledger_id,
            event_type=event_type,
            reference_id=reference_id,
            gate_name=gate_name,
            gate_verdict=gate_verdict,
            details=dict(details or {}),
        )
        self.state.governance_ledger[ledger_id] = entry
        return entry

    def get_runtime_projection(self) -> Dict[str, Any]:
        return self.state.to_runtime_projection()

    def get_summary(self) -> Dict[str, Any]:
        return self.state.get_summary()

    def check_health(self) -> Dict[str, Any]:
        summary = self.state.get_summary()
        verdict = validate_social_state(self.state)
        issues = list(verdict.violations)
        if summary["breached_commitment_count"] > 0:
            issues.append("breached_commitment_present")
        if summary["pending_repair_count"] > 3:
            issues.append("repair_queue_elevated")
        if summary["trust_count"] == 0:
            issues.append("trust_state_missing")
        return {"healthy": len(issues) == 0, "issues": issues, "summary": summary}

    def persist(self, *, update_source: str, trace_reference: Optional[str] = None):
        record = self.store.save(self.state, update_source=update_source, trace_reference=trace_reference)
        persisted = self.store.load()
        if persisted is not None:
            self.state = persisted
        return record

    def get_state(self) -> SocialSelfState:
        return self.state


def get_social_self_owner() -> SocialSelfOwner:
    return SocialSelfOwner.get_instance()


def reset_social_self_owner() -> None:
    SocialSelfOwner.reset()
