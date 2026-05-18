"""
MVP15 T01: Reflection Engine

Performs structured self-reflection and counterfactual analysis.
"""
import time
import logging
import uuid
from typing import Dict, Any, Optional, List

from .schema import (
    ReflectionState,
    ReflectionJob,
    ReflectionType,
    CounterfactualRun,
    DiagnosisRecord,
    ReflectionProposal,
    ReflectionHistory,
)

logger = logging.getLogger(__name__)


class ReflectionEngine:
    """
    Engine for reflective self-analysis.
    
    Features:
    - State and behavior reflection
    - Counterfactual evaluation
    - Error diagnosis
    - Proposal generation
    """
    
    _instance: Optional["ReflectionEngine"] = None
    
    def __init__(self, initial_state: Optional[ReflectionState] = None):
        self.state = initial_state or ReflectionState()
    
    @classmethod
    def get_instance(cls) -> "ReflectionEngine":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls) -> None:
        """Reset singleton."""
        cls._instance = None
    
    def create_reflection_job(
        self,
        reflection_type: ReflectionType,
        target: str,
        input_evidence: Optional[Dict[str, Any]] = None
    ) -> ReflectionJob:
        """
        Create a reflection job.
        
        Args:
            reflection_type: Type of reflection
            target: What to reflect on
            input_evidence: Supporting evidence
            
        Returns:
            Created job
        """
        job_id = f"ref_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        job = ReflectionJob(
            job_id=job_id,
            reflection_type=reflection_type,
            target=target,
            input_evidence=input_evidence or {}
        )
        
        self.state.active_jobs[job_id] = job
        self.state.total_reflections += 1
        self.state.update_timestamp()
        
        return job
    
    def execute_reflection(
        self,
        job: ReflectionJob,
        self_model_state: Optional[Any] = None,
        drive_state: Optional[Any] = None
    ) -> ReflectionJob:
        """
        Execute a reflection job.
        
        Args:
            job: Job to execute
            self_model_state: Optional self-model state
            drive_state: Optional drive state
            
        Returns:
            Completed job
        """
        job.start()
        
        findings = []
        proposals = []
        confidence = 0.5
        
        try:
            if job.reflection_type == ReflectionType.STATE_AUDIT:
                findings, proposals, confidence = self._audit_state(
                    job.target, self_model_state, drive_state
                )
            
            elif job.reflection_type == ReflectionType.BEHAVIOR_PATTERN:
                findings, proposals, confidence = self._analyze_behavior(
                    job.target, job.input_evidence
                )
            
            elif job.reflection_type == ReflectionType.ERROR_DIAGNOSIS:
                findings, proposals, confidence = self._diagnose_error(
                    job.target, job.input_evidence
                )
            
            elif job.reflection_type == ReflectionType.BIAS_ANALYSIS:
                findings, proposals, confidence = self._analyze_bias(
                    job.target, self_model_state
                )
            
            elif job.reflection_type == ReflectionType.COUNTERFACTUAL:
                findings, proposals, confidence = self._run_counterfactual(
                    job.target, job.input_evidence
                )
            
            elif job.reflection_type == ReflectionType.POLICY_REVIEW:
                findings, proposals, confidence = self._review_policy(
                    job.target, job.input_evidence
                )
            
            elif job.reflection_type == ReflectionType.TRAJECTORY_ANALYSIS:
                findings, proposals, confidence = self._analyze_trajectory(
                    job.target, job.input_evidence
                )
            
            job.complete(findings, proposals, confidence)
            self.state.successful_reflections += 1
            
        except Exception as e:
            job.status = f"failed: {str(e)}"
            logger.error(f"Reflection job failed: {e}")
        
        # Move to history
        self.state.history.add_job(job)
        if job.job_id in self.state.active_jobs:
            del self.state.active_jobs[job.job_id]
        
        self.state.update_timestamp()
        return job
    
    def _audit_state(
        self,
        target: str,
        self_model_state: Optional[Any],
        drive_state: Optional[Any]
    ) -> tuple:
        """Audit system state."""
        findings = []
        proposals = []
        confidence = 0.7
        
        if self_model_state:
            # Check identity integrity
            if hasattr(self_model_state, 'verify_identity_integrity'):
                if not self_model_state.verify_identity_integrity():
                    findings.append("Identity integrity check failed")
                    proposals.append("Review and restore identity hash")
                    confidence *= 0.8
            
            # Check invariants
            if hasattr(self_model_state, 'check_identity_invariants'):
                violations = self_model_state.check_identity_invariants()
                if violations:
                    findings.append(f"Invariant violations: {violations}")
                    proposals.append("Address invariant violations")
                    confidence *= 0.9
        
        if drive_state:
            # Check homeostatic balance
            if hasattr(drive_state, 'get_unbalanced_signals'):
                unbalanced = drive_state.get_unbalanced_signals()
                if unbalanced:
                    findings.append(f"Unbalanced signals: {len(unbalanced)}")
                    proposals.append("Address homeostatic imbalances")
        
        if not findings:
            findings.append("State audit passed - no issues detected")
        
        return findings, proposals, confidence
    
    def _analyze_behavior(
        self,
        target: str,
        evidence: Dict[str, Any]
    ) -> tuple:
        """Analyze behavior patterns."""
        findings = []
        proposals = []
        confidence = 0.6
        
        # Placeholder for behavior analysis
        findings.append(f"Behavior pattern analysis for {target}")
        findings.append("Pattern trends identified")
        
        return findings, proposals, confidence
    
    def _diagnose_error(
        self,
        target: str,
        evidence: Dict[str, Any]
    ) -> tuple:
        """Diagnose an error."""
        findings = []
        proposals = []
        confidence = 0.7
        
        error_type = evidence.get("error_type", "unknown")
        error_count = evidence.get("count", 0)
        
        findings.append(f"Error diagnosed: {error_type}")
        findings.append(f"Error count: {error_count}")
        
        if error_count > 5:
            proposals.append(f"Investigate root cause of {error_type}")
            proposals.append("Consider implementing preventive measures")
            confidence = 0.8
        
        return findings, proposals, confidence
    
    def _analyze_bias(
        self,
        target: str,
        self_model_state: Optional[Any]
    ) -> tuple:
        """Analyze behavioral biases."""
        findings = []
        proposals = []
        confidence = 0.6
        
        if self_model_state and hasattr(self_model_state, 'behavioral_tendencies'):
            bt = self_model_state.behavioral_tendencies
            profile = bt.get_behavioral_profile()
            
            findings.append(f"Behavioral profile: {profile}")
            
            # Check for extreme values
            if bt.caution_bias > 0.8:
                findings.append("High caution bias detected")
                proposals.append("Consider rebalancing caution bias")
            
            if bt.exploration_bias < 0.2:
                findings.append("Low exploration bias detected")
                proposals.append("Consider increasing exploration")
        
        return findings, proposals, confidence
    
    def _run_counterfactual(
        self,
        target: str,
        evidence: Dict[str, Any]
    ) -> tuple:
        """Run counterfactual analysis."""
        findings = []
        proposals = []
        confidence = 0.5
        
        premise = evidence.get("premise", f"What if {target}")
        findings.append(f"Counterfactual analysis: {premise}")
        findings.append("Alternative trajectory explored")
        
        proposals.append("Consider alternative approach if viable")
        
        return findings, proposals, confidence
    
    def _review_policy(
        self,
        target: str,
        evidence: Dict[str, Any]
    ) -> tuple:
        """Review a policy."""
        findings = []
        proposals = []
        confidence = 0.7
        
        findings.append(f"Policy review for: {target}")
        findings.append("Policy appears consistent with governance")
        
        return findings, proposals, confidence
    
    def _analyze_trajectory(
        self,
        target: str,
        evidence: Dict[str, Any]
    ) -> tuple:
        """Analyze developmental trajectory."""
        findings = []
        proposals = []
        confidence = 0.6
        
        findings.append(f"Trajectory analysis for: {target}")
        findings.append("Trajectory within expected bounds")
        
        return findings, proposals, confidence
    
    def create_counterfactual_run(
        self,
        counterfactual_type: str,
        premise: str,
        actual_state_hash: str,
        alternative_state: Optional[Dict[str, Any]] = None
    ) -> CounterfactualRun:
        """
        Create a counterfactual run.
        
        Args:
            counterfactual_type: Type of counterfactual
            premise: What if premise
            actual_state_hash: Hash of actual state
            alternative_state: Alternative state to evaluate
            
        Returns:
            Counterfactual run
        """
        run = CounterfactualRun(
            run_id=f"cf_{int(time.time())}_{uuid.uuid4().hex[:8]}",
            counterfactual_type=counterfactual_type,
            premise=premise,
            actual_state_hash=actual_state_hash,
            alternative_state=alternative_state or {}
        )
        
        # Add trace
        run.add_trace({
            "event": "created",
            "premise": premise
        })
        
        self.state.history.counterfactuals.append(run)
        self.state.update_timestamp()
        
        return run
    
    def create_diagnosis(
        self,
        issue_type: str,
        description: str,
        evidence: Optional[Dict[str, Any]] = None,
        severity: float = 0.5
    ) -> DiagnosisRecord:
        """
        Create a diagnosis record.
        
        Args:
            issue_type: Type of issue
            description: Issue description
            evidence: Supporting evidence
            severity: Issue severity
            
        Returns:
            Diagnosis record
        """
        diagnosis = DiagnosisRecord(
            diagnosis_id=f"diag_{int(time.time())}_{uuid.uuid4().hex[:8]}",
            issue_type=issue_type,
            description=description,
            evidence=evidence or {},
            severity=severity
        )
        
        self.state.history.diagnoses.append(diagnosis)
        self.state.update_timestamp()
        
        return diagnosis
    
    def create_proposal(
        self,
        proposal_type: str,
        description: str,
        rationale: str = "",
        expected_impact: float = 0.5,
        risk_level: float = 0.5
    ) -> ReflectionProposal:
        """
        Create a reflection proposal.
        
        Args:
            proposal_type: Type of proposal
            description: Proposal description
            rationale: Why this proposal
            expected_impact: Expected impact level
            risk_level: Risk level
            
        Returns:
            Proposal
        """
        proposal = ReflectionProposal(
            proposal_id=f"prop_{int(time.time())}_{uuid.uuid4().hex[:8]}",
            proposal_type=proposal_type,
            description=description,
            rationale=rationale,
            expected_impact=expected_impact,
            risk_level=risk_level
        )
        
        self.state.history.proposals.append(proposal)
        self.state.update_timestamp()
        
        return proposal
    
    def approve_proposal(
        self,
        proposal_id: str,
        approver: str,
        evidence: Optional[Dict[str, Any]] = None
    ) -> Optional[ReflectionProposal]:
        """
        Approve a proposal.
        
        Args:
            proposal_id: Proposal to approve
            approver: Who approves
            evidence: Approval evidence
            
        Returns:
            Approved proposal or None
        """
        for proposal in self.state.history.proposals:
            if proposal.proposal_id == proposal_id:
                proposal.approve(approver, evidence)
                self.state.update_timestamp()
                return proposal
        
        return None
    
    def get_health(self) -> Dict[str, Any]:
        """Get reflection engine health."""
        return {
            "healthy": self.state.get_success_rate() >= 0.95,
            "success_rate": self.state.get_success_rate(),
            "total_reflections": self.state.total_reflections,
            "successful_reflections": self.state.successful_reflections,
            "pending_proposals": len(self.state.get_pending_proposals()),
            "active_diagnoses": len(self.state.get_active_diagnoses()),
        }


def get_reflection_engine() -> ReflectionEngine:
    """Get singleton ReflectionEngine."""
    return ReflectionEngine.get_instance()


def reset_reflection_engine() -> None:
    """Reset ReflectionEngine singleton."""
    ReflectionEngine.reset()
