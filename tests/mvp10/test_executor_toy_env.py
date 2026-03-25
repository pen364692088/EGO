"""
T15 - Executor Toy Environment Tests

Tests for the executor and toy environment.
"""
import json
import os
import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from emotiond.executor_mvp10 import (
    ToyEnvironment, ExecutorMVP10, ExecutionOutcome, OutcomeStatus,
    ActionExecutor, create_executor,
)


class TestToyEnvironment:
    """Test toy environment functionality."""

    def test_environment_initialization(self):
        """Test environment initialization."""
        env = ToyEnvironment(seed=42)
        
        assert env.seed == 42
        assert env.state["knowledge"] == []
        assert env.state["problems"] == []
        assert env.state["fixes_applied"] == []

    def test_environment_reset(self):
        """Test environment reset."""
        env = ToyEnvironment(seed=42)
        env.set_problem("test_problem")
        env.execute("seek_info", {"query": "test"})
        
        env.reset()
        
        assert env.state["knowledge"] == []
        assert env.state["problems"] == []

    def test_get_state(self):
        """Test getting state."""
        env = ToyEnvironment(seed=42)
        state = env.get_state()
        
        assert isinstance(state, dict)
        assert "knowledge" in state
        assert "problems" in state

    def test_set_problem(self):
        """Test setting a problem."""
        env = ToyEnvironment(seed=42)
        env.set_problem("bug_001")
        
        assert "bug_001" in env.state["problems"]


class TestSeekInfo:
    """Test seek_info action."""

    def test_seek_info_success(self):
        """Test seek_info returns success."""
        env = ToyEnvironment(seed=42)
        outcome = env.execute("seek_info", {"query": "test query"})
        
        assert outcome.status == OutcomeStatus.SUCCESS
        assert "test query" in outcome.reason

    def test_seek_info_adds_knowledge(self):
        """Test seek_info adds to knowledge."""
        env = ToyEnvironment(seed=42)
        env.execute("seek_info", {"query": "diagnose bug"})
        
        assert len(env.state["knowledge"]) == 1
        assert "diagnose bug" in env.state["knowledge"][0]

    def test_seek_info_evidence(self):
        """Test seek_info provides evidence."""
        env = ToyEnvironment(seed=42)
        outcome = env.execute("seek_info", {"query": "test"})
        
        assert "query" in outcome.evidence
        assert "result" in outcome.evidence


class TestAttemptSolution:
    """Test attempt_solution action."""

    def test_attempt_solution_with_knowledge(self):
        """Test attempt_solution with prior knowledge."""
        env = ToyEnvironment(seed=42)
        env.set_problem("bug")
        env.execute("seek_info", {"query": "diagnose"})  # Add knowledge first
        outcome = env.execute("attempt_solution", {"approach": "fix"})
        
        assert outcome.status == OutcomeStatus.SUCCESS
        assert len(env.state["problems"]) == 0  # Problem solved

    def test_attempt_solution_without_knowledge(self):
        """Test attempt_solution without knowledge."""
        env = ToyEnvironment(seed=42)
        env.set_problem("bug")
        outcome = env.execute("attempt_solution", {"approach": "fix"})
        
        # Should be partial without knowledge
        assert outcome.status == OutcomeStatus.PARTIAL

    def test_attempt_solution_no_problems(self):
        """Test attempt_solution with no problems."""
        env = ToyEnvironment(seed=42)
        outcome = env.execute("attempt_solution", {"approach": "fix"})
        
        assert outcome.status == OutcomeStatus.SUCCESS
        assert "No problems" in outcome.reason


class TestRunCheck:
    """Test run_check action."""

    def test_run_check_passes_no_problems(self):
        """Test run_check passes when no problems."""
        env = ToyEnvironment(seed=42)
        outcome = env.execute("run_check", {"validation": "full"})
        
        assert outcome.status == OutcomeStatus.SUCCESS
        assert env.state["checks_passed"] == 1

    def test_run_check_fails_with_problems(self):
        """Test run_check fails when problems exist."""
        env = ToyEnvironment(seed=42)
        env.set_problem("bug")
        outcome = env.execute("run_check", {"validation": "full"})
        
        assert outcome.status == OutcomeStatus.FAIL
        assert outcome.evidence["passed"] == False


class TestApplyFix:
    """Test apply_fix action."""

    def test_apply_fix_resolves_problem(self):
        """Test apply_fix resolves a problem."""
        env = ToyEnvironment(seed=42)
        env.set_problem("bug")
        outcome = env.execute("apply_fix", {"type": "patch", "target": "code"})
        
        assert outcome.status == OutcomeStatus.SUCCESS
        assert len(env.state["problems"]) == 0

    def test_apply_fix_recorded(self):
        """Test apply_fix is recorded."""
        env = ToyEnvironment(seed=42)
        env.execute("apply_fix", {"type": "patch", "target": "code"})
        
        assert len(env.state["fixes_applied"]) == 1

    def test_apply_fix_no_problems(self):
        """Test apply_fix with no problems."""
        env = ToyEnvironment(seed=42)
        outcome = env.execute("apply_fix", {"type": "patch"})
        
        assert outcome.status == OutcomeStatus.SUCCESS


class TestCommitProgress:
    """Test commit_progress action."""

    def test_commit_progress_success(self):
        """Test commit_progress succeeds."""
        env = ToyEnvironment(seed=42)
        outcome = env.execute("commit_progress", {"update": "state_saved"})
        
        assert outcome.status == OutcomeStatus.SUCCESS
        assert env.state["progress_saved"] == True

    def test_commit_progress_includes_state(self):
        """Test commit_progress includes state in evidence."""
        env = ToyEnvironment(seed=42)
        outcome = env.execute("commit_progress", {"update": "test"})
        
        assert "state" in outcome.evidence


class TestNoopAction:
    """Test noop action."""

    def test_noop_success(self):
        """Test noop returns success."""
        env = ToyEnvironment(seed=42)
        outcome = env.execute("noop", {})
        
        assert outcome.status == OutcomeStatus.SUCCESS
        assert "No action" in outcome.reason


class TestInvalidAction:
    """Test invalid action handling."""

    def test_invalid_action_fails(self):
        """Test invalid action returns failure."""
        env = ToyEnvironment(seed=42)
        outcome = env.execute("invalid_action", {})
        
        assert outcome.status == OutcomeStatus.FAIL
        assert "Unknown action" in outcome.reason


class TestExecutorMVP10:
    """Test ExecutorMVP10 class."""

    def test_executor_initialization(self):
        """Test executor initialization."""
        executor = ExecutorMVP10(seed=42)
        
        assert executor.seed == 42
        assert executor.environment is not None

    def test_execute_step(self):
        """Test executing a step."""
        executor = ExecutorMVP10(seed=42)
        step = {"action": "seek_info", "params": {"query": "test"}}
        
        outcome = executor.execute_step(step)
        
        assert outcome.status == OutcomeStatus.SUCCESS

    def test_execute_plan(self):
        """Test executing a plan."""
        executor = ExecutorMVP10(seed=42)
        steps = [
            {"action": "seek_info", "params": {"query": "diagnose"}},
            {"action": "attempt_solution", "params": {"approach": "fix"}},
        ]
        
        outcomes = executor.execute_plan(steps)
        
        assert len(outcomes) == 2

    def test_execute_plan_stops_on_fail(self):
        """Test plan execution stops on failure."""
        executor = ExecutorMVP10(seed=42)
        executor.environment.set_problem("bug")
        
        steps = [
            {"action": "run_check", "params": {}},  # Will fail
            {"action": "seek_info", "params": {}},  # Should not execute
        ]
        
        outcomes = executor.execute_plan(steps)
        
        assert len(outcomes) == 1  # Stopped after first failure

    def test_executor_reset(self):
        """Test executor reset."""
        executor = ExecutorMVP10(seed=42)
        executor.environment.set_problem("bug")
        executor.execute_step({"action": "seek_info", "params": {}})
        
        executor.reset()
        
        assert executor.environment.state["problems"] == []
        assert executor.environment.state["knowledge"] == []


class TestDeterminism:
    """Test deterministic execution."""

    def test_same_seed_same_outcomes(self):
        """Test that same seed produces same outcomes."""
        executor1 = ExecutorMVP10(seed=42)
        executor2 = ExecutorMVP10(seed=42)
        
        executor1.environment.set_problem("bug")
        executor2.environment.set_problem("bug")
        
        outcome1 = executor1.execute_step({"action": "seek_info", "params": {"query": "test"}})
        outcome2 = executor2.execute_step({"action": "seek_info", "params": {"query": "test"}})
        
        assert outcome1.status == outcome2.status
        assert outcome1.reason == outcome2.reason

    def test_state_evolution_deterministic(self):
        """Test that state evolution is deterministic."""
        executor1 = ExecutorMVP10(seed=42)
        executor2 = ExecutorMVP10(seed=42)
        
        steps = [
            {"action": "seek_info", "params": {"query": "a"}},
            {"action": "seek_info", "params": {"query": "b"}},
            {"action": "commit_progress", "params": {"update": "done"}},
        ]
        
        outcomes1 = executor1.execute_plan(steps)
        executor2.reset()
        outcomes2 = executor2.execute_plan(steps)
        
        assert len(outcomes1) == len(outcomes2)
        for o1, o2 in zip(outcomes1, outcomes2):
            assert o1.status == o2.status


class TestOutcomeData:
    """Test outcome data structure."""

    def test_outcome_to_dict(self):
        """Test outcome serialization."""
        outcome = ExecutionOutcome(
            status=OutcomeStatus.SUCCESS,
            reason="test reason",
            evidence={"key": "value"},
            duration_ms=123.45,
        )
        
        d = outcome.to_dict()
        
        assert d["status"] == "success"
        assert d["reason"] == "test reason"
        assert d["evidence"] == {"key": "value"}
        assert d["duration_ms"] == 123.45

    def test_outcome_duration_tracked(self):
        """Test that outcome duration is tracked."""
        env = ToyEnvironment(seed=42)
        outcome = env.execute("seek_info", {"query": "test"})
        
        assert outcome.duration_ms >= 0


class TestCreateExecutor:
    """Test create_executor helper."""

    def test_create_executor(self):
        """Test create_executor function."""
        executor = create_executor(seed=123)
        
        assert isinstance(executor, ExecutorMVP10)
        assert executor.seed == 123


class TestActionHistory:
    """Test action history tracking."""

    def test_actions_recorded(self):
        """Test that actions are recorded in history."""
        env = ToyEnvironment(seed=42)
        
        env.execute("seek_info", {"query": "a"})
        env.execute("run_check", {"validation": "b"})
        
        assert len(env._action_history) == 2
        assert env._action_history[0]["action"] == "seek_info"
        assert env._action_history[1]["action"] == "run_check"


class TestProblemSolvingWorkflow:
    """Test complete problem-solving workflow."""

    def test_full_workflow(self):
        """Test complete problem-solving workflow."""
        env = ToyEnvironment(seed=42)
        env.set_problem("critical_bug")
        
        # 1. Seek info
        outcome1 = env.execute("seek_info", {"query": "diagnose critical_bug"})
        assert outcome1.status == OutcomeStatus.SUCCESS
        
        # 2. Attempt solution (should succeed with knowledge)
        outcome2 = env.execute("attempt_solution", {"approach": "fix"})
        assert outcome2.status == OutcomeStatus.SUCCESS
        
        # 3. Run check (should pass - no problems)
        outcome3 = env.execute("run_check", {"validation": "full"})
        assert outcome3.status == OutcomeStatus.SUCCESS
        
        # 4. Commit progress
        outcome4 = env.execute("commit_progress", {"update": "bug_fixed"})
        assert outcome4.status == OutcomeStatus.SUCCESS
        
        # Verify final state
        assert len(env.state["problems"]) == 0
        assert env.state["progress_saved"] == True
        assert env.state["checks_passed"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
