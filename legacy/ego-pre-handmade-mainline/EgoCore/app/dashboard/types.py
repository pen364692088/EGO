from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SemanticSummary:
    intent_code: str
    host_posture_code: str
    result_state_code: str
    growth_motion_code: str
    evidence_state_code: str
    why_codes: List[str] = field(default_factory=list)
    headline_code: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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
    source_type: Optional[str] = None
    sample_scope: str = "real_user"
    sample_scope_reason: Optional[str] = None
    response_plan_status: Optional[str] = None
    closure_family_id: Optional[str] = None
    session_id: Optional[str] = None
    thread_id: Optional[str] = None
    outcome_signature: Optional[str] = None
    reflection_trigger: Optional[str] = None
    semantic: Optional[SemanticSummary] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        if self.semantic is not None:
            payload["semantic"] = self.semantic.to_dict()
        return payload


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
    focus_goal: Optional[str] = None
    revision_counter: int = 0
    identity_light_hash: Optional[str] = None
    semantic: Optional[SemanticSummary] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        if self.semantic is not None:
            payload["semantic"] = self.semantic.to_dict()
        return payload


@dataclass
class AgencyRunRecord:
    sample_id: str
    timestamp: str
    session_id: Optional[str]
    subject_profile: str
    idle_check: bool
    idle_eligible: bool
    urge_score: Optional[float]
    candidate_generated: bool
    candidate_actions: List[str]
    suppression_reason: Optional[str]
    governor_status: Optional[str]
    requires_approval: bool
    final_host_action: Optional[str]
    exec_result_type: Optional[str]
    writeback_applied: bool
    focus_goal: Optional[str]
    identity_light_hash: Optional[str]
    revision_counter: int
    trace_completeness: bool
    evidence_source: str
    direct_execution_violation: bool = False
    semantic: Optional[SemanticSummary] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        if self.semantic is not None:
            payload["semantic"] = self.semantic.to_dict()
        return payload


@dataclass
class AgencyLatestState:
    sample_id: str
    timestamp: str
    subject_profile: str
    session_id: Optional[str]
    focus_goal: Optional[str]
    urge_score: Optional[float]
    candidate_actions: List[str]
    governor_status: Optional[str]
    final_host_action: Optional[str]
    exec_result_type: Optional[str]
    writeback_applied: bool
    revision_counter: int
    trace_completeness: bool
    semantic: Optional[SemanticSummary] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        if self.semantic is not None:
            payload["semantic"] = self.semantic.to_dict()
        return payload


@dataclass
class AgencyRollup:
    generated_at: str
    last_sample_timestamp: Optional[str]
    freshness_seconds: Optional[float]
    profile_scope: List[str]
    summary: Dict[str, Any]
    latest_state: Optional[AgencyLatestState]
    funnel: Dict[str, int]
    trends: List[Dict[str, Any]]
    distributions: Dict[str, Dict[str, int]]
    recent_turns: List[Dict[str, Any]]
    excluded_counts: Dict[str, int]
    semantic_summary: Dict[str, Dict[str, int]] = field(default_factory=dict)
    headline_code: str = "unknown"
    story_cards: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        if self.latest_state is not None:
            payload["latest_state"] = self.latest_state.to_dict()
        return payload


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
    semantic: Optional[SemanticSummary] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        if self.semantic is not None:
            payload["semantic"] = self.semantic.to_dict()
        return payload


@dataclass
class RunsRollup:
    generated_at: str
    last_sample_timestamp: Optional[str]
    freshness_seconds: Optional[float]
    headline_code: str
    summary: Dict[str, Any]
    charts: Dict[str, Any]
    continuity: List[Dict[str, Any]]
    recent_runs: List[Dict[str, Any]]
    records: List[Dict[str, Any]]
    semantic_summary: Dict[str, Dict[str, int]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GrowthRollup:
    generated_at: str
    last_sample_timestamp: Optional[str]
    freshness_seconds: Optional[float]
    headline_code: str
    summary: Dict[str, Any]
    charts: Dict[str, Any]
    recent_growth: List[Dict[str, Any]]
    records: List[Dict[str, Any]]
    semantic_summary: Dict[str, Dict[str, int]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FailuresRollup:
    generated_at: str
    last_sample_timestamp: Optional[str]
    freshness_seconds: Optional[float]
    headline_code: str
    summary: Dict[str, Any]
    charts: Dict[str, Any]
    recent_failures: List[Dict[str, Any]]
    records: List[Dict[str, Any]]
    semantic_summary: Dict[str, Dict[str, int]]
    gap_summary: Dict[str, Any]

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
    dashboard_schema_version: int = 1
    real_user_runs: int = 0
    fixture_like_runs: int = 0
    continuity_status: Dict[str, str] = field(default_factory=dict)
    gap_type_counts: Dict[str, int] = field(default_factory=dict)
    plasticity_chain_count: int = 0
    reflection_candidate_count: int = 0
    agency_records: int = 0
    agency_profile_scope: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FlowViewRecord:
    sample_id: str
    channel: str
    timestamp: Optional[str]
    input_summary: Dict[str, Any]
    host_ingress_summary: Dict[str, Any]
    subject_summary: Dict[str, Any]
    canonical_fields_summary: Dict[str, Any]
    reply_evolution_summary: Dict[str, Any]
    host_arbitration_summary: Dict[str, Any]
    output_summary: Dict[str, Any]
    chain_status: Dict[str, Any]
    failure_or_gap_summary: Dict[str, Any]
    artifact_refs: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
