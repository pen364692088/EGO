"""
MVP15 T01: Reflection Infrastructure Tests
"""
import pytest

from emotiond.reflection_engine import (
    ReflectionState,
    ReflectionJob,
    ReflectionType,
    CounterfactualRun,
    DiagnosisRecord,
    ReflectionProposal,
    ReflectionEngine,
    get_reflection_engine,
    reset_reflection_engine,
)


class TestReflectionSchema:
    """Tests for reflection schema."""
    
    def test_reflection_job_defaults(self):
        """ReflectionJob should have sensible defaults."""
        job = ReflectionJob(
            job_id="test",
            reflection_type=ReflectionType.STATE_AUDIT,
            target="test_target"
        )
        assert job.status == "pending"
        assert job.findings == []
    
    def test_job_lifecycle(self):
        """Job should progress through lifecycle."""
        job = ReflectionJob(
            job_id="test",
            reflection_type=ReflectionType.STATE_AUDIT,
            target="test"
        )
        
        job.start()
        assert job.status == "running"
        assert job.started_at is not None
        
        job.complete(["finding1"], ["proposal1"], 0.8)
        assert job.status == "completed"
        assert len(job.findings) == 1
        assert job.confidence == 0.8
    
    def test_counterfactual_run(self):
        """CounterfactualRun should track traces."""
        run = CounterfactualRun(
            run_id="test",
            counterfactual_type="what_if",
            premise="What if X?",
            actual_state_hash="abc123"
        )
        
        run.add_trace({"event": "step1"})
        assert len(run.trace_entries) == 1
    
    def test_diagnosis_record(self):
        """DiagnosisRecord should track resolution."""
        diag = DiagnosisRecord(
            diagnosis_id="test",
            issue_type="error",
            description="Test issue"
        )
        
        assert diag.status == "identified"
        
        diag.resolve("Fixed")
        assert diag.status == "resolved"
        assert diag.proposed_fix == "Fixed"
    
    def test_reflection_proposal(self):
        """ReflectionProposal should track approval."""
        prop = ReflectionProposal(
            proposal_id="test",
            proposal_type="change",
            description="Test proposal"
        )
        
        assert prop.status == "proposed"
        assert not prop.approved
        
        prop.approve("test_user", {"reason": "looks good"})
        assert prop.approved
        assert prop.status == "approved"
    
    def test_reflection_history(self):
        """ReflectionHistory should manage entries."""
        from emotiond.reflection_engine.schema import ReflectionHistory
        
        history = ReflectionHistory()
        
        job = ReflectionJob(
            job_id="test",
            reflection_type=ReflectionType.STATE_AUDIT,
            target="test"
        )
        
        history.add_job(job)
        assert len(history.jobs) == 1
        
        recent = history.get_recent_jobs(1)
        assert recent[0].job_id == "test"


class TestReflectionEngine:
    """Tests for ReflectionEngine."""
    
    def test_singleton(self):
        """Should return same instance."""
        reset_reflection_engine()
        
        e1 = get_reflection_engine()
        e2 = get_reflection_engine()
        
        assert e1 is e2
    
    def test_create_reflection_job(self):
        """Should create reflection job."""
        reset_reflection_engine()
        engine = get_reflection_engine()
        
        job = engine.create_reflection_job(
            ReflectionType.STATE_AUDIT,
            "test_target"
        )
        
        assert job.job_id is not None
        assert job.status == "pending"
    
    def test_execute_state_audit(self):
        """Should execute state audit."""
        reset_reflection_engine()
        engine = get_reflection_engine()
        
        job = engine.create_reflection_job(
            ReflectionType.STATE_AUDIT,
            "identity_check"
        )
        
        completed = engine.execute_reflection(job)
        
        assert completed.status == "completed"
        assert len(completed.findings) > 0
    
    def test_execute_error_diagnosis(self):
        """Should execute error diagnosis."""
        reset_reflection_engine()
        engine = get_reflection_engine()
        
        job = engine.create_reflection_job(
            ReflectionType.ERROR_DIAGNOSIS,
            "recurring_error",
            {"error_type": "validation", "count": 10}
        )
        
        completed = engine.execute_reflection(job)
        
        assert completed.status == "completed"
        assert "validation" in str(completed.findings).lower()
    
    def test_create_counterfactual_run(self):
        """Should create counterfactual run."""
        reset_reflection_engine()
        engine = get_reflection_engine()
        
        run = engine.create_counterfactual_run(
            "what_if",
            "What if we used different strategy?",
            "hash123"
        )
        
        assert run.run_id is not None
        assert len(run.trace_entries) > 0
    
    def test_create_diagnosis(self):
        """Should create diagnosis."""
        reset_reflection_engine()
        engine = get_reflection_engine()
        
        diag = engine.create_diagnosis(
            "bias",
            "Detected bias in decision making",
            {"severity": "medium"},
            severity=0.6
        )
        
        assert diag.diagnosis_id is not None
        assert diag.status == "identified"
    
    def test_create_proposal(self):
        """Should create proposal."""
        reset_reflection_engine()
        engine = get_reflection_engine()
        
        prop = engine.create_proposal(
            "policy_update",
            "Update decision threshold",
            "Current threshold too low"
        )
        
        assert prop.proposal_id is not None
        assert prop.status == "proposed"
    
    def test_approve_proposal(self):
        """Should approve proposal."""
        reset_reflection_engine()
        engine = get_reflection_engine()
        
        prop = engine.create_proposal("test", "Test proposal")
        
        approved = engine.approve_proposal(prop.proposal_id, "admin")
        
        assert approved is not None
        assert approved.approved
    
    def test_get_health(self):
        """Should return health status."""
        reset_reflection_engine()
        engine = get_reflection_engine()
        
        health = engine.get_health()
        
        assert "healthy" in health
        assert "success_rate" in health


class TestExitCriteria:
    """Tests for MVP15 Exit Criteria."""
    
    def test_reflection_capability(self):
        """EC1: Reflection capability working."""
        reset_reflection_engine()
        engine = get_reflection_engine()
        
        job = engine.create_reflection_job(
            ReflectionType.STATE_AUDIT,
            "test"
        )
        completed = engine.execute_reflection(job)
        
        assert completed.status == "completed"
        assert len(completed.findings) > 0
    
    def test_counterfactual_capability(self):
        """EC2: Counterfactual capability working."""
        reset_reflection_engine()
        engine = get_reflection_engine()
        
        run = engine.create_counterfactual_run(
            "what_if",
            "What if?",
            "hash"
        )
        
        assert run.run_id is not None
        assert len(run.trace_entries) > 0
    
    def test_proposal_discipline(self):
        """EC3: Proposals remain under governance."""
        reset_reflection_engine()
        engine = get_reflection_engine()
        
        prop = engine.create_proposal("test", "Test")
        
        # Proposal starts as proposed, not approved
        assert prop.status == "proposed"
        assert not prop.approved
        
        # Must be explicitly approved
        engine.approve_proposal(prop.proposal_id, "governor")
        assert prop.approved
    
    def test_replayability(self):
        """EC5: Reflection jobs replayable."""
        reset_reflection_engine()
        engine = get_reflection_engine()
        
        job = engine.create_reflection_job(
            ReflectionType.STATE_AUDIT,
            "test"
        )
        completed = engine.execute_reflection(job)
        
        # Job should have full history
        assert completed.job_id is not None
        assert completed.started_at is not None
        assert completed.completed_at is not None
        assert completed.findings is not None
    
    def test_metrics_success_rate(self):
        """EC6: reflection_job_success_rate >= 95%."""
        reset_reflection_engine()
        engine = get_reflection_engine()
        
        # Run multiple jobs
        for _ in range(10):
            job = engine.create_reflection_job(
                ReflectionType.STATE_AUDIT,
                "test"
            )
            engine.execute_reflection(job)
        
        health = engine.get_health()
        assert health["success_rate"] >= 0.95
