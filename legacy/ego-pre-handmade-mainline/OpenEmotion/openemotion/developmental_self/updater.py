from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional

from .continuity import build_continuity_snapshot, compute_developmental_risk_index
from .governance import validate_developmental_state
from .intake import compact_developmental_self_context
from .promotion import build_promotion_queue_snapshot
from .schemas import (
    ContinuityMarker,
    ContinuityMarkerType,
    DevelopmentalIdentityAnchor,
    DevelopmentalPromotionCandidate,
    DevelopmentalProposal,
    DevelopmentalTrajectorySummary,
    GovernanceLedgerEntry,
    PromotionLevel,
)
from .state import REQUIRED_WRITEBACK_GATE, DevelopmentalSelfState
from .store import DevelopmentalSelfStore


def _make_id(prefix: str) -> str:
    return f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}"


class DevelopmentalSelfOwner:
    _instance: Optional["DevelopmentalSelfOwner"] = None

    def __init__(
        self,
        initial_state: Optional[DevelopmentalSelfState] = None,
        *,
        store: Optional[DevelopmentalSelfStore] = None,
    ):
        self.state = (
            initial_state.model_copy(deep=True)
            if initial_state is not None
            else DevelopmentalSelfState()
        )
        self.store = store or DevelopmentalSelfStore()

    @classmethod
    def get_instance(cls) -> "DevelopmentalSelfOwner":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def set_identity_anchor(
        self,
        *,
        anchor_summary: str,
        invariant_refs: Optional[list[str]] = None,
        confidence: float = 1.0,
        anchor_id: str = "identity_anchor",
    ) -> DevelopmentalIdentityAnchor:
        anchor = DevelopmentalIdentityAnchor(
            anchor_id=anchor_id,
            self_model_identity=self.state.identity_handle,
            anchor_summary=anchor_summary,
            invariant_refs=list(invariant_refs or []),
            confidence=confidence,
        )
        self.state.developmental_identity_anchor = anchor
        return anchor

    def set_trajectory_summary(
        self,
        *,
        current_arc: str,
        current_phase: str,
        recent_shift: str = "",
        continuity_note: str = "",
        source_refs: Optional[list[str]] = None,
    ) -> DevelopmentalTrajectorySummary:
        summary = DevelopmentalTrajectorySummary(
            current_arc=current_arc,
            current_phase=current_phase,
            recent_shift=recent_shift,
            continuity_note=continuity_note,
            source_refs=list(source_refs or []),
        )
        self.state.trajectory_summary = summary
        return summary

    def set_continuity_metrics(
        self,
        *,
        continuity_score: float,
        growth_pressure: float,
        stagnation_signal: float,
        identity_preservation_confidence: float,
        developmental_risk_index: Optional[float] = None,
    ) -> Dict[str, float]:
        self.state.continuity_score = continuity_score
        self.state.growth_pressure = growth_pressure
        self.state.stagnation_signal = stagnation_signal
        self.state.identity_preservation_confidence = identity_preservation_confidence
        self.state.developmental_risk_index = (
            developmental_risk_index
            if developmental_risk_index is not None
            else compute_developmental_risk_index(self.state)
        )
        return {
            "continuity_score": self.state.continuity_score,
            "growth_pressure": self.state.growth_pressure,
            "stagnation_signal": self.state.stagnation_signal,
            "identity_preservation_confidence": self.state.identity_preservation_confidence,
            "developmental_risk_index": self.state.developmental_risk_index,
        }

    def add_proposal(
        self,
        *,
        proposal_kind: str,
        summary: str,
        proposed_adjustment: Dict[str, Any],
        justification: str,
        source_refs: Optional[list[str]] = None,
        requested_effects: Optional[list[str]] = None,
        promotion_level: PromotionLevel = PromotionLevel.SHADOW_ONLY,
    ) -> DevelopmentalProposal:
        proposal_id = _make_id("developmental_proposal")
        proposal = DevelopmentalProposal(
            proposal_id=proposal_id,
            proposal_kind=proposal_kind,
            summary=summary,
            proposed_adjustment=dict(proposed_adjustment),
            justification=justification,
            source_refs=list(source_refs or []),
            requested_effects=list(requested_effects or []),
            required_gate=REQUIRED_WRITEBACK_GATE,
            promotion_level=promotion_level,
        )
        self.state.proposal_history[proposal_id] = proposal
        return proposal

    def queue_promotion(
        self,
        *,
        source_proposal_id: str,
        summary: str,
        promotion_level: PromotionLevel = PromotionLevel.REVIEW_ONLY,
    ) -> DevelopmentalPromotionCandidate:
        if source_proposal_id not in self.state.proposal_history:
            raise KeyError(f"unknown_source_proposal:{source_proposal_id}")
        promotion_id = _make_id("developmental_promotion")
        candidate = DevelopmentalPromotionCandidate(
            promotion_id=promotion_id,
            source_proposal_id=source_proposal_id,
            summary=summary,
            promotion_level=promotion_level,
            required_gate=REQUIRED_WRITEBACK_GATE,
        )
        self.state.promotion_queue[promotion_id] = candidate
        return candidate

    def add_continuity_marker(
        self,
        *,
        marker_type: ContinuityMarkerType,
        reference: str,
        continuity_weight: float,
        note: str = "",
        source_refs: Optional[list[str]] = None,
    ) -> ContinuityMarker:
        marker_id = _make_id("continuity_marker")
        marker = ContinuityMarker(
            marker_id=marker_id,
            marker_type=marker_type,
            reference=reference,
            continuity_weight=continuity_weight,
            note=note,
            source_refs=list(source_refs or []),
        )
        self.state.continuity_markers[marker_id] = marker
        return marker

    def record_governance_event(
        self,
        *,
        event_type: str,
        reference_id: str,
        gate_verdict: str,
        details: Optional[Dict[str, Any]] = None,
        gate_name: str = REQUIRED_WRITEBACK_GATE,
    ) -> GovernanceLedgerEntry:
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
        return compact_developmental_self_context(self.state)

    def get_continuity_snapshot(self) -> Dict[str, Any]:
        return build_continuity_snapshot(self.state)

    def get_promotion_snapshot(self) -> Dict[str, Any]:
        return build_promotion_queue_snapshot(self.state)

    def check_health(self) -> Dict[str, Any]:
        summary = self.state.get_summary()
        verdict = validate_developmental_state(self.state)
        issues = list(verdict.violations)
        if self.state.continuity_score < 0.35:
            issues.append("low_continuity_score")
        if self.state.identity_preservation_confidence < 0.6:
            issues.append("identity_preservation_low")
        if self.state.developmental_risk_index > 0.7:
            issues.append("developmental_risk_high")
        return {"healthy": len(issues) == 0, "issues": issues, "summary": summary}

    def persist(self, *, update_source: str, trace_reference: Optional[str] = None):
        record = self.store.save(self.state, update_source=update_source, trace_reference=trace_reference)
        persisted = self.store.load()
        if persisted is not None:
            self.state = persisted
        return record

    def get_state(self) -> DevelopmentalSelfState:
        return self.state

    def get_summary(self) -> Dict[str, Any]:
        return self.state.get_summary()


def get_developmental_self_owner() -> DevelopmentalSelfOwner:
    return DevelopmentalSelfOwner.get_instance()


def reset_developmental_self_owner() -> None:
    DevelopmentalSelfOwner.reset()
