from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional

from .governance import validate_initiative_state
from .schemas import (
    CommitmentContinuityState,
    CommitmentContinuityStatus,
    HostProactiveCandidate,
    HostProactiveCandidateStatus,
    InitiativeLedgerEntry,
    InitiativePriority,
    InitiativePriorityState,
    InitiativeProposalCandidate,
    InitiativeProposalStatus,
    InitiativeState,
)
from .state import InitiativeSelfState, REQUIRED_WRITEBACK_GATE
from .store import InitiativeSelfStore


def _make_id(prefix: str) -> str:
    return f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}"


class InitiativeSelfOwner:
    _instance: Optional["InitiativeSelfOwner"] = None

    def __init__(
        self,
        initial_state: Optional[InitiativeSelfState] = None,
        *,
        store: Optional[InitiativeSelfStore] = None,
    ):
        self.state = initial_state.model_copy(deep=True) if initial_state is not None else InitiativeSelfState()
        self.store = store or InitiativeSelfStore()

    @classmethod
    def get_instance(cls) -> "InitiativeSelfOwner":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def set_initiative_state(
        self,
        *,
        dominant_mode: InitiativePriority,
        initiative_pressure: float,
        commitment_carryover_bias: float,
        recent_delivery_sensitivity: float,
        rationale_summary: str,
        source_refs: Optional[list[str]] = None,
    ) -> InitiativeState:
        entry = InitiativeState(
            dominant_mode=dominant_mode,
            initiative_pressure=initiative_pressure,
            commitment_carryover_bias=commitment_carryover_bias,
            recent_delivery_sensitivity=recent_delivery_sensitivity,
            rationale_summary=rationale_summary,
            source_refs=list(source_refs or []),
        )
        self.state.initiative_state = entry
        return entry

    def set_initiative_priority_state(
        self,
        *,
        selected_priority: InitiativePriority,
        hold_weight: float,
        review_weight: float,
        prepare_weight: float,
        carry_forward_weight: float,
        schedule_weight: float,
        priority_reason: str,
        upstream_pressure_sources: Optional[list[str]] = None,
        source_refs: Optional[list[str]] = None,
    ) -> InitiativePriorityState:
        entry = InitiativePriorityState(
            selected_priority=selected_priority,
            hold_weight=hold_weight,
            review_weight=review_weight,
            prepare_weight=prepare_weight,
            carry_forward_weight=carry_forward_weight,
            schedule_weight=schedule_weight,
            priority_reason=priority_reason,
            upstream_pressure_sources=list(upstream_pressure_sources or []),
            source_refs=list(source_refs or []),
        )
        self.state.initiative_priority_state = entry
        return entry

    def set_commitment_continuity_state(
        self,
        *,
        status: CommitmentContinuityStatus,
        active_commitments_count: int,
        carried_commitment_refs: Optional[list[str]] = None,
        blocked_commitment_refs: Optional[list[str]] = None,
        continuity_confidence: float,
        carryover_summary: str,
        source_refs: Optional[list[str]] = None,
    ) -> CommitmentContinuityState:
        entry = CommitmentContinuityState(
            status=status,
            active_commitments_count=active_commitments_count,
            carried_commitment_refs=list(carried_commitment_refs or []),
            blocked_commitment_refs=list(blocked_commitment_refs or []),
            continuity_confidence=continuity_confidence,
            carryover_summary=carryover_summary,
            source_refs=list(source_refs or []),
        )
        self.state.commitment_continuity_state = entry
        return entry

    def propose_initiative(
        self,
        *,
        proposal_label: str,
        priority_mode: InitiativePriority,
        proposed_effects: Dict[str, Any],
        justification: str,
        source_refs: Optional[list[str]] = None,
        requested_effects: Optional[list[str]] = None,
        proposal_id: Optional[str] = None,
    ) -> InitiativeProposalCandidate:
        resolved_proposal_id = proposal_id or _make_id("initiative")
        entry = InitiativeProposalCandidate(
            proposal_id=resolved_proposal_id,
            proposal_label=proposal_label,
            priority_mode=priority_mode,
            proposed_effects=dict(proposed_effects),
            justification=justification,
            required_gate=REQUIRED_WRITEBACK_GATE,
            requested_effects=list(requested_effects or []),
            source_refs=list(source_refs or []),
        )
        self.state.initiative_proposal_candidate = entry
        return entry

    def set_initiative_proposal_status(
        self,
        *,
        status: InitiativeProposalStatus,
    ) -> InitiativeProposalCandidate:
        if self.state.initiative_proposal_candidate is None:
            raise KeyError("initiative_proposal_candidate_missing")
        proposal = self.state.initiative_proposal_candidate
        proposal.status = status
        proposal.updated_at = time.time()
        return proposal

    def set_host_proactive_candidate(
        self,
        *,
        candidate_label: str,
        continuity_basis: str,
        host_lane_hint: str = "host_proactive_outbox",
        source_refs: Optional[list[str]] = None,
        requested_effects: Optional[list[str]] = None,
        candidate_id: Optional[str] = None,
    ) -> HostProactiveCandidate:
        resolved_candidate_id = candidate_id or _make_id("host_candidate")
        entry = HostProactiveCandidate(
            candidate_id=resolved_candidate_id,
            candidate_label=candidate_label,
            continuity_basis=continuity_basis,
            host_lane_hint=host_lane_hint,
            requested_effects=list(requested_effects or []),
            source_refs=list(source_refs or []),
        )
        self.state.host_proactive_candidate = entry
        return entry

    def set_host_proactive_candidate_status(
        self,
        *,
        status: HostProactiveCandidateStatus,
    ) -> HostProactiveCandidate:
        if self.state.host_proactive_candidate is None:
            raise KeyError("host_proactive_candidate_missing")
        candidate = self.state.host_proactive_candidate
        candidate.status = status
        candidate.updated_at = time.time()
        return candidate

    def record_initiative_event(
        self,
        *,
        event_type: str,
        reference_id: str,
        gate_verdict: str,
        details: Optional[Dict[str, Any]] = None,
        gate_name: str = REQUIRED_WRITEBACK_GATE,
    ) -> InitiativeLedgerEntry:
        ledger_id = _make_id("initiative_ledger")
        entry = InitiativeLedgerEntry(
            ledger_id=ledger_id,
            event_type=event_type,
            reference_id=reference_id,
            gate_name=gate_name,
            gate_verdict=gate_verdict,
            details=dict(details or {}),
        )
        self.state.initiative_ledger[ledger_id] = entry
        return entry

    def get_runtime_projection(self) -> Dict[str, Any]:
        return self.state.to_runtime_projection()

    def get_summary(self) -> Dict[str, Any]:
        return self.state.get_summary()

    def check_health(self) -> Dict[str, Any]:
        summary = self.state.get_summary()
        verdict = validate_initiative_state(self.state)
        issues = list(verdict.violations)
        if summary["active_commitments_count"] == 0:
            issues.append("commitment_continuity_missing")
        if summary["continuity_confidence"] < 0.4:
            issues.append("continuity_confidence_low")
        if self.state.initiative_proposal_candidate is None:
            issues.append("initiative_proposal_candidate_missing")
        if self.state.host_proactive_candidate is None:
            issues.append("host_proactive_candidate_missing")
        return {"healthy": len(issues) == 0, "issues": issues, "summary": summary}

    def persist(self, *, update_source: str, trace_reference: Optional[str] = None):
        record = self.store.save(self.state, update_source=update_source, trace_reference=trace_reference)
        persisted = self.store.load()
        if persisted is not None:
            self.state = persisted
        return record

    def get_state(self) -> InitiativeSelfState:
        return self.state


def get_initiative_self_owner() -> InitiativeSelfOwner:
    return InitiativeSelfOwner.get_instance()


def reset_initiative_self_owner() -> None:
    InitiativeSelfOwner.reset()
