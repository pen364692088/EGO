from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional

from .governance import validate_selfhood_integration_state
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
from .state import (
    REQUIRED_WRITEBACK_GATE,
    SelfhoodIntegrationState,
)
from .store import SelfhoodIntegrationStore


def _make_id(prefix: str) -> str:
    return f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}"


class SelfhoodIntegrationOwner:
    _instance: Optional["SelfhoodIntegrationOwner"] = None

    def __init__(
        self,
        initial_state: Optional[SelfhoodIntegrationState] = None,
        *,
        store: Optional[SelfhoodIntegrationStore] = None,
    ):
        self.state = (
            initial_state.model_copy(deep=True)
            if initial_state is not None
            else SelfhoodIntegrationState()
        )
        self.store = store or SelfhoodIntegrationStore()

    @classmethod
    def get_instance(cls) -> "SelfhoodIntegrationOwner":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def set_integration_state(
        self,
        *,
        posture: ArbitrationPriority,
        dominant_pressure_axis: str,
        stability_bias: float,
        integration_confidence: float,
        active_axis_count: int,
        rationale_summary: str,
        source_refs: Optional[list[str]] = None,
    ) -> IntegrationState:
        entry = IntegrationState(
            posture=posture,
            dominant_pressure_axis=dominant_pressure_axis,
            stability_bias=stability_bias,
            integration_confidence=integration_confidence,
            active_axis_count=active_axis_count,
            rationale_summary=rationale_summary,
            source_refs=list(source_refs or []),
        )
        self.state.integration_state = entry
        return entry

    def set_cross_axis_priority_state(
        self,
        *,
        selected_priority: ArbitrationPriority,
        stabilize_weight: float,
        conserve_weight: float,
        guard_weight: float,
        review_weight: float,
        repair_weight: float,
        grow_weight: float,
        reflective_modifier: float,
        priority_reason: str,
        upstream_pressure_sources: Optional[list[str]] = None,
        source_refs: Optional[list[str]] = None,
    ) -> CrossAxisPriorityState:
        entry = CrossAxisPriorityState(
            selected_priority=selected_priority,
            stabilize_weight=stabilize_weight,
            conserve_weight=conserve_weight,
            guard_weight=guard_weight,
            review_weight=review_weight,
            repair_weight=repair_weight,
            grow_weight=grow_weight,
            reflective_modifier=reflective_modifier,
            priority_reason=priority_reason,
            upstream_pressure_sources=list(upstream_pressure_sources or []),
            source_refs=list(source_refs or []),
        )
        self.state.cross_axis_priority_state = entry
        return entry

    def set_proposal_conflict_state(
        self,
        *,
        highest_severity: ConflictSeverity,
        conflict_count: int,
        unresolved_conflict_refs: Optional[list[str]] = None,
        blocked_axes: Optional[list[str]] = None,
        resolution_posture: ArbitrationPriority = ArbitrationPriority.REVIEW,
        source_refs: Optional[list[str]] = None,
    ) -> ProposalConflictState:
        entry = ProposalConflictState(
            highest_severity=highest_severity,
            conflict_count=conflict_count,
            unresolved_conflict_refs=list(unresolved_conflict_refs or []),
            blocked_axes=list(blocked_axes or []),
            resolution_posture=resolution_posture,
            source_refs=list(source_refs or []),
        )
        self.state.proposal_conflict_state = entry
        return entry

    def _set_balance(
        self,
        *,
        field_name: str,
        balance_id: str,
        lower_pole: str,
        upper_pole: str,
        lower_weight: float,
        upper_weight: float,
        preferred_pole: str,
        rationale: str,
        source_refs: Optional[list[str]] = None,
    ) -> ArbitrationBalance:
        entry = ArbitrationBalance(
            balance_id=balance_id,
            lower_pole=lower_pole,
            upper_pole=upper_pole,
            lower_weight=lower_weight,
            upper_weight=upper_weight,
            preferred_pole=preferred_pole,
            rationale=rationale,
            source_refs=list(source_refs or []),
        )
        setattr(self.state, field_name, entry)
        return entry

    def set_stabilize_explore_balance(
        self,
        *,
        stabilize_weight: float,
        explore_weight: float,
        preferred_pole: str,
        rationale: str,
        source_refs: Optional[list[str]] = None,
    ) -> ArbitrationBalance:
        return self._set_balance(
            field_name="stabilize_explore_balance",
            balance_id="stabilize_explore",
            lower_pole="stabilize",
            upper_pole="explore",
            lower_weight=stabilize_weight,
            upper_weight=explore_weight,
            preferred_pole=preferred_pole,
            rationale=rationale,
            source_refs=source_refs,
        )

    def set_repair_progress_balance(
        self,
        *,
        repair_weight: float,
        progress_weight: float,
        preferred_pole: str,
        rationale: str,
        source_refs: Optional[list[str]] = None,
    ) -> ArbitrationBalance:
        return self._set_balance(
            field_name="repair_progress_balance",
            balance_id="repair_progress",
            lower_pole="repair",
            upper_pole="progress",
            lower_weight=repair_weight,
            upper_weight=progress_weight,
            preferred_pole=preferred_pole,
            rationale=rationale,
            source_refs=source_refs,
        )

    def set_social_boundary_balance(
        self,
        *,
        social_weight: float,
        boundary_weight: float,
        preferred_pole: str,
        rationale: str,
        source_refs: Optional[list[str]] = None,
    ) -> ArbitrationBalance:
        return self._set_balance(
            field_name="social_boundary_balance",
            balance_id="social_boundary",
            lower_pole="social",
            upper_pole="boundary",
            lower_weight=social_weight,
            upper_weight=boundary_weight,
            preferred_pole=preferred_pole,
            rationale=rationale,
            source_refs=source_refs,
        )

    def propose_integrated_tendency(
        self,
        *,
        tendency_label: str,
        priority_mode: ArbitrationPriority,
        proposed_effects: Dict[str, Any],
        justification: str,
        source_refs: Optional[list[str]] = None,
        requested_effects: Optional[list[str]] = None,
        proposal_id: Optional[str] = None,
    ) -> IntegratedTendencyProposal:
        resolved_proposal_id = proposal_id or _make_id("integrated")
        entry = IntegratedTendencyProposal(
            proposal_id=resolved_proposal_id,
            tendency_label=tendency_label,
            priority_mode=priority_mode,
            proposed_effects=dict(proposed_effects),
            justification=justification,
            required_gate=REQUIRED_WRITEBACK_GATE,
            requested_effects=list(requested_effects or []),
            source_refs=list(source_refs or []),
        )
        self.state.integrated_tendency_proposal = entry
        return entry

    def set_integrated_tendency_status(
        self,
        *,
        status: IntegratedProposalStatus,
    ) -> IntegratedTendencyProposal:
        if self.state.integrated_tendency_proposal is None:
            raise KeyError("integrated_tendency_proposal_missing")
        proposal = self.state.integrated_tendency_proposal
        proposal.status = status
        proposal.updated_at = time.time()
        return proposal

    def upsert_axis_arbitration_hint(
        self,
        *,
        axis_name: str,
        recommendation: str,
        priority_weight: float,
        guardrail_summary: str,
        source_refs: Optional[list[str]] = None,
    ) -> AxisArbitrationHint:
        entry = AxisArbitrationHint(
            hint_id=_make_id("axis_hint"),
            axis_name=axis_name,
            recommendation=recommendation,
            priority_weight=priority_weight,
            guardrail_summary=guardrail_summary,
            source_refs=list(source_refs or []),
        )
        self.state.axis_arbitration_hints[axis_name] = entry
        return entry

    def record_integration_event(
        self,
        *,
        event_type: str,
        reference_id: str,
        gate_verdict: str,
        details: Optional[Dict[str, Any]] = None,
        gate_name: str = REQUIRED_WRITEBACK_GATE,
    ) -> IntegrationLedgerEntry:
        ledger_id = _make_id("integration_ledger")
        entry = IntegrationLedgerEntry(
            ledger_id=ledger_id,
            event_type=event_type,
            reference_id=reference_id,
            gate_name=gate_name,
            gate_verdict=gate_verdict,
            details=dict(details or {}),
        )
        self.state.integration_ledger[ledger_id] = entry
        return entry

    def get_runtime_projection(self) -> Dict[str, Any]:
        return self.state.to_runtime_projection()

    def get_summary(self) -> Dict[str, Any]:
        return self.state.get_summary()

    def check_health(self) -> Dict[str, Any]:
        summary = self.state.get_summary()
        verdict = validate_selfhood_integration_state(self.state)
        issues = list(verdict.violations)
        if summary["highest_conflict_severity"] == "high":
            issues.append("high_conflict_pressure")
        if (
            summary["selected_priority"] not in {"stabilize", "conserve", "guard", "review"}
            and self.state.integration_state.stability_bias < 0.5
        ):
            issues.append("stability_first_bias_missing")
        if self.state.integrated_tendency_proposal is None:
            issues.append("integrated_tendency_missing")
        if not self.state.axis_arbitration_hints:
            issues.append("axis_arbitration_hints_missing")
        return {"healthy": len(issues) == 0, "issues": issues, "summary": summary}

    def persist(self, *, update_source: str, trace_reference: Optional[str] = None):
        record = self.store.save(
            self.state,
            update_source=update_source,
            trace_reference=trace_reference,
        )
        persisted = self.store.load()
        if persisted is not None:
            self.state = persisted
        return record

    def get_state(self) -> SelfhoodIntegrationState:
        return self.state


def get_selfhood_integration_owner() -> SelfhoodIntegrationOwner:
    return SelfhoodIntegrationOwner.get_instance()


def reset_selfhood_integration_owner() -> None:
    SelfhoodIntegrationOwner.reset()
