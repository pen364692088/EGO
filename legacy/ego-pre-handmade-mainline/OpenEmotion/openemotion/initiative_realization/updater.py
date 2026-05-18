from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional

from .governance import validate_realization_state
from .schemas import (
    CommitmentFulfillmentState,
    CommitmentFulfillmentStatus,
    ControlledDeliveryCandidate,
    ControlledDeliveryCandidateStatus,
    DeliveryReadinessState,
    InitiativeRealizationCandidate,
    RealizationLedgerEntry,
    RealizationMode,
    RealizationProposalStatus,
    RealizationState,
)
from .state import InitiativeRealizationState, REQUIRED_WRITEBACK_GATE
from .store import InitiativeRealizationStore


def _make_id(prefix: str) -> str:
    return f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}"


class InitiativeRealizationOwner:
    _instance: Optional["InitiativeRealizationOwner"] = None

    def __init__(
        self,
        initial_state: Optional[InitiativeRealizationState] = None,
        *,
        store: Optional[InitiativeRealizationStore] = None,
    ):
        self.state = (
            initial_state.model_copy(deep=True) if initial_state is not None else InitiativeRealizationState()
        )
        self.store = store or InitiativeRealizationStore()

    @classmethod
    def get_instance(cls) -> "InitiativeRealizationOwner":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def set_realization_state(
        self,
        *,
        dominant_mode: RealizationMode,
        realization_pressure: float,
        fulfillment_readiness: float,
        hold_bias: float,
        failure_recovery_bias: float,
        rationale_summary: str,
        source_refs: Optional[list[str]] = None,
    ) -> RealizationState:
        entry = RealizationState(
            dominant_mode=dominant_mode,
            realization_pressure=realization_pressure,
            fulfillment_readiness=fulfillment_readiness,
            hold_bias=hold_bias,
            failure_recovery_bias=failure_recovery_bias,
            rationale_summary=rationale_summary,
            source_refs=list(source_refs or []),
        )
        self.state.realization_state = entry
        return entry

    def set_delivery_readiness_state(
        self,
        *,
        selected_lane: RealizationMode,
        hold_weight: float,
        review_weight: float,
        prepare_weight: float,
        mediate_weight: float,
        fulfill_weight: float,
        lane_reason: str,
        host_lane_hints: Optional[list[str]] = None,
        source_refs: Optional[list[str]] = None,
    ) -> DeliveryReadinessState:
        entry = DeliveryReadinessState(
            selected_lane=selected_lane,
            hold_weight=hold_weight,
            review_weight=review_weight,
            prepare_weight=prepare_weight,
            mediate_weight=mediate_weight,
            fulfill_weight=fulfill_weight,
            lane_reason=lane_reason,
            host_lane_hints=list(host_lane_hints or []),
            source_refs=list(source_refs or []),
        )
        self.state.delivery_readiness_state = entry
        return entry

    def set_commitment_fulfillment_state(
        self,
        *,
        status: CommitmentFulfillmentStatus,
        active_commitments_count: int,
        ready_commitments_count: int,
        realized_commitment_refs: Optional[list[str]] = None,
        blocked_commitment_refs: Optional[list[str]] = None,
        continuity_confidence: float,
        fulfillment_summary: str,
        source_refs: Optional[list[str]] = None,
    ) -> CommitmentFulfillmentState:
        entry = CommitmentFulfillmentState(
            status=status,
            active_commitments_count=active_commitments_count,
            ready_commitments_count=ready_commitments_count,
            realized_commitment_refs=list(realized_commitment_refs or []),
            blocked_commitment_refs=list(blocked_commitment_refs or []),
            continuity_confidence=continuity_confidence,
            fulfillment_summary=fulfillment_summary,
            source_refs=list(source_refs or []),
        )
        self.state.commitment_fulfillment_state = entry
        return entry

    def propose_realization(
        self,
        *,
        candidate_label: str,
        selected_mode: RealizationMode,
        proposed_effects: Dict[str, Any],
        justification: str,
        source_refs: Optional[list[str]] = None,
        requested_effects: Optional[list[str]] = None,
        candidate_id: Optional[str] = None,
    ) -> InitiativeRealizationCandidate:
        resolved_candidate_id = candidate_id or _make_id("realization")
        entry = InitiativeRealizationCandidate(
            candidate_id=resolved_candidate_id,
            candidate_label=candidate_label,
            selected_mode=selected_mode,
            proposed_effects=dict(proposed_effects),
            justification=justification,
            required_gate=REQUIRED_WRITEBACK_GATE,
            requested_effects=list(requested_effects or []),
            source_refs=list(source_refs or []),
        )
        self.state.initiative_realization_candidate = entry
        return entry

    def set_initiative_realization_candidate_status(
        self,
        *,
        status: RealizationProposalStatus,
    ) -> InitiativeRealizationCandidate:
        if self.state.initiative_realization_candidate is None:
            raise KeyError("initiative_realization_candidate_missing")
        candidate = self.state.initiative_realization_candidate
        candidate.status = status
        candidate.updated_at = time.time()
        return candidate

    def set_controlled_delivery_candidate(
        self,
        *,
        candidate_label: str,
        readiness_basis: str,
        delivery_readiness: float,
        host_lane_hint: str = "host_proactive_outbox",
        source_refs: Optional[list[str]] = None,
        requested_effects: Optional[list[str]] = None,
        candidate_id: Optional[str] = None,
    ) -> ControlledDeliveryCandidate:
        resolved_candidate_id = candidate_id or _make_id("delivery_candidate")
        entry = ControlledDeliveryCandidate(
            candidate_id=resolved_candidate_id,
            candidate_label=candidate_label,
            readiness_basis=readiness_basis,
            delivery_readiness=delivery_readiness,
            host_lane_hint=host_lane_hint,
            requested_effects=list(requested_effects or []),
            source_refs=list(source_refs or []),
        )
        self.state.controlled_delivery_candidate = entry
        return entry

    def set_controlled_delivery_candidate_status(
        self,
        *,
        status: ControlledDeliveryCandidateStatus,
    ) -> ControlledDeliveryCandidate:
        if self.state.controlled_delivery_candidate is None:
            raise KeyError("controlled_delivery_candidate_missing")
        candidate = self.state.controlled_delivery_candidate
        candidate.status = status
        candidate.updated_at = time.time()
        return candidate

    def record_realization_event(
        self,
        *,
        event_type: str,
        reference_id: str,
        gate_verdict: str,
        details: Optional[Dict[str, Any]] = None,
        gate_name: str = REQUIRED_WRITEBACK_GATE,
    ) -> RealizationLedgerEntry:
        ledger_id = _make_id("realization_ledger")
        entry = RealizationLedgerEntry(
            ledger_id=ledger_id,
            event_type=event_type,
            reference_id=reference_id,
            gate_name=gate_name,
            gate_verdict=gate_verdict,
            details=dict(details or {}),
        )
        self.state.realization_ledger[ledger_id] = entry
        return entry

    def get_runtime_projection(self) -> Dict[str, Any]:
        return self.state.to_runtime_projection()

    def get_summary(self) -> Dict[str, Any]:
        return self.state.get_summary()

    def check_health(self) -> Dict[str, Any]:
        summary = self.state.get_summary()
        verdict = validate_realization_state(self.state)
        issues = list(verdict.violations)
        if summary["active_commitments_count"] == 0:
            issues.append("commitment_fulfillment_missing")
        if summary["ready_commitments_count"] == 0:
            issues.append("delivery_readiness_missing")
        if summary["continuity_confidence"] < 0.4:
            issues.append("continuity_confidence_low")
        if self.state.initiative_realization_candidate is None:
            issues.append("initiative_realization_candidate_missing")
        if self.state.controlled_delivery_candidate is None:
            issues.append("controlled_delivery_candidate_missing")
        return {"healthy": len(issues) == 0, "issues": issues, "summary": summary}

    def persist(self, *, update_source: str, trace_reference: Optional[str] = None):
        record = self.store.save(self.state, update_source=update_source, trace_reference=trace_reference)
        persisted = self.store.load()
        if persisted is not None:
            self.state = persisted
        return record

    def get_state(self) -> InitiativeRealizationState:
        return self.state


def get_initiative_realization_owner() -> InitiativeRealizationOwner:
    return InitiativeRealizationOwner.get_instance()


def reset_initiative_realization_owner() -> None:
    InitiativeRealizationOwner.reset()
