"""
MVP15 T01: Reflection Schema

Structured representation of reflection, counterfactual analysis,
and diagnosis records.
"""
import time
import hashlib
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class ReflectionType(str, Enum):
    """Types of reflection analysis."""
    STATE_AUDIT = "state_audit"
    BEHAVIOR_PATTERN = "behavior_pattern"
    ERROR_DIAGNOSIS = "error_diagnosis"
    BIAS_ANALYSIS = "bias_analysis"
    COUNTERFACTUAL = "counterfactual"
    POLICY_REVIEW = "policy_review"
    TRAJECTORY_ANALYSIS = "trajectory_analysis"


class ReflectionJob(BaseModel):
    """
    A single reflection analysis job.
    """
    job_id: str = Field(..., description="Unique job identifier")
    reflection_type: ReflectionType = Field(..., description="Type of reflection")
    target: str = Field(..., description="What is being reflected on")
    status: str = Field(default="pending", description="Job status")
    created_at: float = Field(default_factory=time.time)
    started_at: Optional[float] = Field(default=None)
    completed_at: Optional[float] = Field(default=None)
    
    # Input
    input_evidence: Dict[str, Any] = Field(default_factory=dict)
    
    # Output
    findings: List[str] = Field(default_factory=list)
    proposals: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Governance
    approved: bool = Field(default=False)
    approver: Optional[str] = Field(default=None)
    
    def start(self) -> None:
        """Mark job as started."""
        self.status = "running"
        self.started_at = time.time()
    
    def complete(self, findings: List[str], proposals: List[str], confidence: float) -> None:
        """Mark job as completed."""
        self.status = "completed"
        self.completed_at = time.time()
        self.findings = findings
        self.proposals = proposals
        self.confidence = confidence


class CounterfactualRun(BaseModel):
    """
    A counterfactual evaluation run.
    
    Explores "what if" scenarios with trace-linked evidence.
    """
    run_id: str = Field(..., description="Unique run identifier")
    counterfactual_type: str = Field(..., description="Type of counterfactual")
    premise: str = Field(..., description="What if premise")
    
    # Inputs
    actual_state_hash: str = Field(..., description="Hash of actual state")
    alternative_state: Dict[str, Any] = Field(default_factory=dict)
    
    # Outputs
    predicted_outcome: Optional[str] = Field(default=None)
    divergence_analysis: List[str] = Field(default_factory=list)
    uncertainty: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # Trace
    created_at: float = Field(default_factory=time.time)
    trace_entries: List[Dict[str, Any]] = Field(default_factory=list)
    
    def add_trace(self, entry: Dict[str, Any]) -> None:
        """Add a trace entry."""
        self.trace_entries.append({
            "timestamp": time.time(),
            **entry
        })


class DiagnosisRecord(BaseModel):
    """
    A self-diagnosis record.
    
    Documents identified issues and their root causes.
    """
    diagnosis_id: str = Field(..., description="Unique diagnosis identifier")
    issue_type: str = Field(..., description="Type of issue diagnosed")
    description: str = Field(..., description="Issue description")
    root_cause: Optional[str] = Field(default=None)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    severity: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # Resolution
    proposed_fix: Optional[str] = Field(default=None)
    status: str = Field(default="identified")
    
    created_at: float = Field(default_factory=time.time)
    resolved_at: Optional[float] = Field(default=None)
    
    def resolve(self, fix: str) -> None:
        """Mark as resolved."""
        self.proposed_fix = fix
        self.status = "resolved"
        self.resolved_at = time.time()


class ReflectionProposal(BaseModel):
    """
    A proposal generated from reflection.
    
    Proposals are subject to governance approval.
    """
    proposal_id: str = Field(..., description="Unique proposal identifier")
    proposal_type: str = Field(..., description="Type of proposal")
    description: str = Field(..., description="Proposal description")
    rationale: str = Field(default="", description="Why this proposal")
    
    # Governance
    status: str = Field(default="proposed")
    approved: bool = Field(default=False)
    approver: Optional[str] = Field(default=None)
    approval_evidence: Dict[str, Any] = Field(default_factory=dict)
    
    # Impact
    expected_impact: float = Field(default=0.5, ge=0.0, le=1.0)
    risk_level: float = Field(default=0.5, ge=0.0, le=1.0)
    
    created_at: float = Field(default_factory=time.time)
    
    def approve(self, approver: str, evidence: Optional[Dict[str, Any]] = None) -> None:
        """Approve the proposal."""
        self.approved = True
        self.approver = approver
        self.approval_evidence = evidence or {}
        self.status = "approved"
    
    def reject(self, reason: str) -> None:
        """Reject the proposal."""
        self.status = f"rejected: {reason}"


class ReflectionHistory(BaseModel):
    """History of reflection activities."""
    jobs: List[ReflectionJob] = Field(default_factory=list)
    counterfactuals: List[CounterfactualRun] = Field(default_factory=list)
    diagnoses: List[DiagnosisRecord] = Field(default_factory=list)
    proposals: List[ReflectionProposal] = Field(default_factory=list)
    
    max_entries: int = Field(default=500, description="Max entries per category")
    
    def add_job(self, job: ReflectionJob) -> None:
        """Add a reflection job."""
        self.jobs.append(job)
        if len(self.jobs) > self.max_entries:
            self.jobs = self.jobs[-self.max_entries:]
    
    def get_recent_jobs(self, n: int = 10) -> List[ReflectionJob]:
        """Get recent jobs."""
        return self.jobs[-n:]
    
    def get_completed_jobs(self) -> List[ReflectionJob]:
        """Get completed jobs."""
        return [j for j in self.jobs if j.status == "completed"]


class ReflectionState(BaseModel):
    """
    Complete reflection state for MVP15.
    """
    # Active reflection jobs
    active_jobs: Dict[str, ReflectionJob] = Field(default_factory=dict)
    
    # History
    history: ReflectionHistory = Field(default_factory=ReflectionHistory)
    
    # Metrics
    total_reflections: int = Field(default=0)
    successful_reflections: int = Field(default=0)
    
    # Metadata
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    version: str = Field(default="1.0.0")
    schema_version: str = Field(default="mvp15-v1")
    
    def update_timestamp(self) -> None:
        """Update timestamp."""
        self.updated_at = time.time()
    
    def get_success_rate(self) -> float:
        """Get reflection success rate."""
        if self.total_reflections == 0:
            return 1.0
        return self.successful_reflections / self.total_reflections
    
    def get_pending_proposals(self) -> List[ReflectionProposal]:
        """Get pending proposals."""
        return [p for p in self.history.proposals if p.status == "proposed"]
    
    def get_active_diagnoses(self) -> List[DiagnosisRecord]:
        """Get active diagnoses."""
        return [d for d in self.history.diagnoses if d.status == "identified"]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary."""
        return {
            "version": self.version,
            "total_reflections": self.total_reflections,
            "success_rate": self.get_success_rate(),
            "active_jobs": len(self.active_jobs),
            "pending_proposals": len(self.get_pending_proposals()),
            "active_diagnoses": len(self.get_active_diagnoses()),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
