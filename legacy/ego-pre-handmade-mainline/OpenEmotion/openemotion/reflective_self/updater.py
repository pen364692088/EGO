from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional

from .governance import validate_reflective_state
from .schemas import (
    CounterfactualRecord,
    DiagnosisRecord,
    ReflectionQueueItem,
    ReflectionTarget,
    ReflectionTargetType,
    RevisionProposal,
    UnresolvedReflectionItem,
)
from .state import ReflectiveSelfState
from .store import ReflectiveSelfStore


def _make_id(prefix: str) -> str:
    return f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}"


class ReflectiveSelfOwner:
    _instance: Optional["ReflectiveSelfOwner"] = None

    def __init__(
        self,
        initial_state: Optional[ReflectiveSelfState] = None,
        *,
        store: Optional[ReflectiveSelfStore] = None,
    ):
        self.state = initial_state.model_copy(deep=True) if initial_state is not None else ReflectiveSelfState()
        self.store = store or ReflectiveSelfStore()

    @classmethod
    def get_instance(cls) -> "ReflectiveSelfOwner":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def enqueue_reflection(
        self,
        *,
        target_type: ReflectionTargetType,
        target_reference: str,
        trigger_source: str,
        priority: float = 0.5,
        evidence_refs: Optional[list[str]] = None,
        requested_effects: Optional[list[str]] = None,
    ) -> ReflectionQueueItem:
        reflection_id = _make_id("reflection")
        item = ReflectionQueueItem(
            reflection_id=reflection_id,
            target_type=target_type,
            target_reference=target_reference,
            priority=priority,
            trigger_source=trigger_source,
            evidence_refs=list(evidence_refs or []),
            requested_effects=list(requested_effects or []),
        )
        self.state.reflection_queue[reflection_id] = item
        self.state.reflection_history.record(
            entry_id=_make_id("history"),
            entry_type="reflection_enqueued",
            linked_record_id=reflection_id,
            details={"target_reference": target_reference, "target_type": target_type.value},
        )
        self.state.update_timestamp()
        return item

    def upsert_target(
        self,
        *,
        target_id: str,
        target_type: ReflectionTargetType,
        reference: str,
        reason: str,
        salience: float = 0.5,
        evidence_refs: Optional[list[str]] = None,
    ) -> ReflectionTarget:
        target = ReflectionTarget(
            target_id=target_id,
            target_type=target_type,
            reference=reference,
            salience=salience,
            reason=reason,
            evidence_refs=list(evidence_refs or []),
        )
        self.state.reflection_targets[target_id] = target
        self.state.update_timestamp()
        return target

    def start_reflection(self, reflection_id: str) -> ReflectionQueueItem:
        item = self.state.reflection_queue[reflection_id]
        item.status = "running"
        item.started_at = time.time()
        self.state.reflection_history.record(
            entry_id=_make_id("history"),
            entry_type="reflection_started",
            linked_record_id=reflection_id,
            details={"status": item.status},
        )
        self.state.update_timestamp()
        return item

    def complete_reflection(
        self,
        reflection_id: str,
        *,
        resolution_note: str = "",
        final_status: str = "completed",
    ) -> ReflectionQueueItem:
        item = self.state.reflection_queue.pop(reflection_id)
        item.status = final_status
        item.completed_at = time.time()
        item.resolution_note = resolution_note or None
        self.state.reflection_history.record(
            entry_id=_make_id("history"),
            entry_type="reflection_completed",
            linked_record_id=reflection_id,
            details={"status": item.status, "resolution_note": resolution_note},
        )
        self.state.update_timestamp()
        return item

    def record_diagnosis(
        self,
        *,
        analyzed_target: str,
        detected_pattern: str,
        confidence: float,
        supporting_evidence: Optional[list[str]] = None,
        suggested_action: Optional[str] = None,
    ) -> DiagnosisRecord:
        diagnosis_id = _make_id("diagnosis")
        record = DiagnosisRecord(
            diagnosis_id=diagnosis_id,
            analyzed_target=analyzed_target,
            detected_pattern=detected_pattern,
            confidence=confidence,
            supporting_evidence=list(supporting_evidence or []),
            suggested_action=suggested_action,
        )
        self.state.diagnosis_records[diagnosis_id] = record
        self.state.reflection_history.record(
            entry_id=_make_id("history"),
            entry_type="diagnosis_recorded",
            linked_record_id=diagnosis_id,
            details={"analyzed_target": analyzed_target},
        )
        self.state.update_timestamp()
        return record

    def record_counterfactual(
        self,
        *,
        baseline_reference: str,
        alternative_path: str,
        expected_difference: Dict[str, Any],
        evidence_basis: Optional[list[str]] = None,
        uncertainty_level: float = 0.5,
        truth_status: str = "counterfactual_uncertain",
    ) -> CounterfactualRecord:
        counterfactual_id = _make_id("counterfactual")
        record = CounterfactualRecord(
            counterfactual_id=counterfactual_id,
            baseline_reference=baseline_reference,
            alternative_path=alternative_path,
            expected_difference=dict(expected_difference),
            evidence_basis=list(evidence_basis or []),
            uncertainty_level=uncertainty_level,
            truth_status=truth_status,
        )
        self.state.counterfactual_records[counterfactual_id] = record
        self.state.reflection_history.record(
            entry_id=_make_id("history"),
            entry_type="counterfactual_recorded",
            linked_record_id=counterfactual_id,
            details={"baseline_reference": baseline_reference},
        )
        self.state.update_timestamp()
        return record

    def propose_revision(
        self,
        *,
        target_layer: str,
        proposed_change: Dict[str, Any],
        justification: str,
        required_gate: str,
        requested_effects: Optional[list[str]] = None,
    ) -> RevisionProposal:
        proposal_id = _make_id("proposal")
        record = RevisionProposal(
            proposal_id=proposal_id,
            target_layer=target_layer,
            proposed_change=dict(proposed_change),
            justification=justification,
            required_gate=required_gate,
            requested_effects=list(requested_effects or []),
        )
        self.state.revision_proposals[proposal_id] = record
        self.state.reflection_history.record(
            entry_id=_make_id("history"),
            entry_type="revision_proposed",
            linked_record_id=proposal_id,
            details={"target_layer": target_layer},
        )
        self.state.update_timestamp()
        return record

    def set_proposal_gate_status(
        self,
        proposal_id: str,
        *,
        status: str,
        gate_verdict: str,
        gate_reference: str,
        reason: str = "",
    ) -> RevisionProposal:
        proposal = self.state.revision_proposals[proposal_id]
        proposal.status = status
        proposal.gate_metadata = {
            "gate_verdict": gate_verdict,
            "gate_reference": gate_reference,
            "reason": reason,
            "updated_at": time.time(),
        }
        self.state.reflection_history.record(
            entry_id=_make_id("history"),
            entry_type="proposal_gate_status_updated",
            linked_record_id=proposal_id,
            details=dict(proposal.gate_metadata),
        )
        self.state.update_timestamp()
        return proposal

    def add_unresolved_item(
        self,
        *,
        summary: str,
        linked_record_id: Optional[str] = None,
        severity: float = 0.5,
    ) -> UnresolvedReflectionItem:
        item_id = _make_id("unresolved")
        item = UnresolvedReflectionItem(
            item_id=item_id,
            summary=summary,
            linked_record_id=linked_record_id,
            severity=severity,
        )
        self.state.unresolved_reflection_items[item_id] = item
        self.state.reflection_history.record(
            entry_id=_make_id("history"),
            entry_type="unresolved_item_added",
            linked_record_id=item_id,
            details={"severity": severity},
        )
        self.state.update_timestamp()
        return item

    def get_runtime_projection(self) -> Dict[str, Any]:
        return self.state.to_runtime_projection()

    def check_health(self) -> Dict[str, Any]:
        summary = self.state.get_summary()
        verdict = validate_reflective_state(self.state)
        issues = list(verdict.violations)
        if summary["reflection_pressure"] > 0.8:
            issues.append("high_reflection_pressure")
        return {"healthy": len(issues) == 0, "issues": issues, "summary": summary}

    def persist(self, *, update_source: str, trace_reference: Optional[str] = None):
        record = self.store.save(self.state, update_source=update_source, trace_reference=trace_reference)
        persisted = self.store.load()
        if persisted is not None:
            self.state = persisted
        return record

    def get_state(self) -> ReflectiveSelfState:
        return self.state

    def get_summary(self) -> Dict[str, Any]:
        return self.state.get_summary()


def get_reflective_self_owner() -> ReflectiveSelfOwner:
    return ReflectiveSelfOwner.get_instance()


def reset_reflective_self_owner() -> None:
    ReflectiveSelfOwner.reset()
