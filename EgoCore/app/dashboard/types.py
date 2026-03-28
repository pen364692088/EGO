from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RunIndexRecord:
    sample_id: str
    timestamp: str
    bundle_complete: bool
    gap_types: List[str]
    oe_available: bool
    host_only: bool
    continuity_tags: List[str]
    repair_closure: bool
    artifact_refs: Dict[str, str]
    response_plan_status: Optional[str] = None
    closure_family_id: Optional[str] = None
    session_id: Optional[str] = None
    thread_id: Optional[str] = None
    outcome_signature: Optional[str] = None
    reflection_trigger: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ContinuityObservationRecord:
    scenario: str
    status: str
    sample_ids: List[str]
    external_evidence_refs: List[str]
    proof_summary: str
    not_proved_summary: str
    blocker: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GrowthSignalRecord:
    sample_id: str
    timestamp: str
    memory_update_summary: Dict[str, Any]
    appraisal_delta_summary: Dict[str, Any]
    reflection_summary: Dict[str, Any]
    response_tendency_summary: Dict[str, Any]
    cycle_summary: Dict[str, Any]
    session_id: Optional[str] = None
    thread_id: Optional[str] = None
    closure_family_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FailureIndexRecord:
    failure_id: str
    timestamp: str
    cause_type: str
    severity: str
    source: str
    artifact_ref: str
    in_regression: bool
    retested_after_fix: bool
    expected: Optional[str] = None
    actual: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DashboardBuildSummary:
    generated_at: str
    source_last_modified: float
    total_runs: int
    complete_runs: int
    oe_available_runs: int
    host_only_runs: int
    failure_cases: int
    continuity_status: Dict[str, str] = field(default_factory=dict)
    gap_type_counts: Dict[str, int] = field(default_factory=dict)
    plasticity_chain_count: int = 0
    reflection_candidate_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
