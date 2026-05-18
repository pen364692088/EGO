from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional

from .governance import validate_embodied_state
from .schemas import (
    ActionConsequenceRecord,
    BoundaryPressureMode,
    BoundaryPressureState,
    EmbodiedProposal,
    EmbodiedProposalStatus,
    EmbodiedState,
    EnvironmentCouplingState,
    EnvironmentCouplingStatus,
    ResourcePressureState,
    SelfWorldBoundarySemantics,
)
from .state import REQUIRED_WRITEBACK_GATE, EmbodiedSelfState
from .store import EmbodiedSelfStore


def _make_id(prefix: str) -> str:
    return f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}"


class EmbodiedSelfOwner:
    _instance: Optional["EmbodiedSelfOwner"] = None

    def __init__(
        self,
        initial_state: Optional[EmbodiedSelfState] = None,
        *,
        store: Optional[EmbodiedSelfStore] = None,
    ):
        self.state = initial_state.model_copy(deep=True) if initial_state is not None else EmbodiedSelfState()
        self.store = store or EmbodiedSelfStore()

    @classmethod
    def get_instance(cls) -> "EmbodiedSelfOwner":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def set_embodied_state(
        self,
        *,
        resource_slack: float,
        perceived_load: float,
        action_readiness: float,
        last_action_source: str = "runtime",
        source_refs: Optional[list[str]] = None,
    ) -> EmbodiedState:
        entry = EmbodiedState(
            resource_slack=resource_slack,
            perceived_load=perceived_load,
            action_readiness=action_readiness,
            last_action_source=last_action_source,
            source_refs=list(source_refs or []),
        )
        self.state.embodied_state = entry
        return entry

    def upsert_environment_coupling(
        self,
        *,
        coupling_id: str,
        coupling_strength: float,
        controllability_estimate: float,
        recent_outcome_summary: str,
        status: EnvironmentCouplingStatus = EnvironmentCouplingStatus.STABLE,
        source_refs: Optional[list[str]] = None,
    ) -> EnvironmentCouplingState:
        entry = EnvironmentCouplingState(
            coupling_id=coupling_id,
            coupling_strength=coupling_strength,
            controllability_estimate=controllability_estimate,
            recent_outcome_summary=recent_outcome_summary,
            status=status,
            source_refs=list(source_refs or []),
        )
        self.state.environment_coupling_state[coupling_id] = entry
        return entry

    def set_resource_pressure(
        self,
        *,
        pressure_id: str,
        pressure_level: float,
        slack_level: float,
        recovery_bias: float = 0.0,
        source_refs: Optional[list[str]] = None,
    ) -> ResourcePressureState:
        entry = ResourcePressureState(
            pressure_id=pressure_id,
            pressure_level=pressure_level,
            slack_level=slack_level,
            recovery_bias=recovery_bias,
            source_refs=list(source_refs or []),
        )
        self.state.resource_pressure_state[pressure_id] = entry
        return entry

    def set_boundary_pressure(
        self,
        *,
        boundary_id: str,
        pressure_level: float,
        mode: BoundaryPressureMode = BoundaryPressureMode.GUARDED,
        reason: str = "",
        source_refs: Optional[list[str]] = None,
    ) -> BoundaryPressureState:
        entry = BoundaryPressureState(
            boundary_id=boundary_id,
            pressure_level=pressure_level,
            mode=mode,
            reason=reason,
            source_refs=list(source_refs or []),
        )
        self.state.boundary_pressure_state[boundary_id] = entry
        return entry

    def record_action_consequence(
        self,
        *,
        action_ref: str,
        outcome_type: str,
        consequence_summary: str,
        impact_score: float,
        controllability_estimate: float = 0.5,
        source_refs: Optional[list[str]] = None,
        consequence_id: Optional[str] = None,
    ):
        resolved_consequence_id = consequence_id or _make_id("consequence")
        entry = ActionConsequenceRecord(
            consequence_id=resolved_consequence_id,
            action_ref=action_ref,
            outcome_type=outcome_type,
            consequence_summary=consequence_summary,
            impact_score=impact_score,
            controllability_estimate=controllability_estimate,
            source_refs=list(source_refs or []),
        )
        self.state.action_consequence_memory[resolved_consequence_id] = entry
        return entry

    def set_self_world_boundary_semantics(
        self,
        *,
        distinction_summary: str,
        guard_bias: float,
        repair_bias: float,
        source_refs: Optional[list[str]] = None,
    ) -> SelfWorldBoundarySemantics:
        entry = SelfWorldBoundarySemantics(
            distinction_summary=distinction_summary,
            guard_bias=guard_bias,
            repair_bias=repair_bias,
            source_refs=list(source_refs or []),
        )
        self.state.self_world_boundary_semantics = entry
        return entry

    def propose_stabilization(
        self,
        *,
        target_ref: str,
        issue_summary: str,
        proposed_adjustment: Dict[str, Any],
        justification: str,
        source_refs: Optional[list[str]] = None,
        requested_effects: Optional[list[str]] = None,
        proposal_id: Optional[str] = None,
    ) -> EmbodiedProposal:
        resolved_proposal_id = proposal_id or _make_id("embodied")
        entry = EmbodiedProposal(
            proposal_id=resolved_proposal_id,
            target_ref=target_ref,
            issue_summary=issue_summary,
            proposed_adjustment=dict(proposed_adjustment),
            justification=justification,
            required_gate=REQUIRED_WRITEBACK_GATE,
            requested_effects=list(requested_effects or []),
            source_refs=list(source_refs or []),
        )
        self.state.proposal_history[resolved_proposal_id] = entry
        return entry

    def set_proposal_status(
        self,
        proposal_id: str,
        *,
        status: EmbodiedProposalStatus,
    ) -> EmbodiedProposal:
        entry = self.state.proposal_history[proposal_id]
        entry.status = status
        entry.updated_at = time.time()
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
        verdict = validate_embodied_state(self.state)
        issues = list(verdict.violations)
        if summary["max_resource_pressure"] > 0.8:
            issues.append("resource_pressure_elevated")
        if summary["max_boundary_pressure"] > 0.8:
            issues.append("boundary_pressure_elevated")
        if summary["consequence_count"] == 0:
            issues.append("action_consequence_memory_missing")
        return {"healthy": len(issues) == 0, "issues": issues, "summary": summary}

    def persist(self, *, update_source: str, trace_reference: Optional[str] = None):
        record = self.store.save(self.state, update_source=update_source, trace_reference=trace_reference)
        persisted = self.store.load()
        if persisted is not None:
            self.state = persisted
        return record

    def get_state(self) -> EmbodiedSelfState:
        return self.state


def get_embodied_self_owner() -> EmbodiedSelfOwner:
    return EmbodiedSelfOwner.get_instance()


def reset_embodied_self_owner() -> None:
    EmbodiedSelfOwner.reset()
