"""
MVP11-T11: Test Executor Updates Homeostasis

Tests for executor integration with resource_env and homeostasis.
"""
import json
import os
import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from emotiond.executor_mvp11 import (
    ExecutorMVP11,
    ExecutionMetadata,
    create_executor_mvp11,
    create_executor,
    ENABLE_MVP11_RESOURCE_ENV,
)
from emotiond.executor_mvp10 import ExecutionOutcome, OutcomeStatus
from emotiond.envs.resource_env import PerturbationType, create_resource_env
from emotiond.homeostasis import HomeostasisManager, HomeostasisState


class TestExecutorMVP11Basic:
    """Test basic executor functionality."""

    def test_executor_initialization(self):
        """Test executor initialization with MVP11 enabled."""
        executor = ExecutorMVP11(seed=0)
        
        assert executor.seed == 0
        assert executor.enable_mvp11 == True
        assert executor.resource_env is not None
        assert executor.homeostasis_manager is not None

    def test_executor_mvp10_mode(self):
        """Test executor in MVP10 compatibility mode."""
        executor = ExecutorMVP11(seed=0, enable_mvp11=False)
        
        assert executor.enable_mvp11 == False
        assert executor.resource_env is None
        assert executor.homeostasis_manager is None

    def test_executor_has_toy_environment(self):
        """Test executor has toy environment for MVP10 compatibility."""
        executor = ExecutorMVP11(seed=0)
        
        assert executor.toy_environment is not None
        assert executor.environment is executor.toy_environment


class TestExecutorExecution:
    """Test execution with resource tracking."""

    def test_execute_returns_outcome_and_metadata(self):
        """Test execute returns both outcome and metadata."""
        executor = create_executor_mvp11(seed=0)
        
        outcome, metadata = executor.execute({
            "type": "seek_info",
            "params": {"query": "test"},
        })
        
        assert isinstance(outcome, ExecutionOutcome)
        assert isinstance(metadata, ExecutionMetadata)

    def test_execute_metadata_contains_resource_state(self):
        """Test metadata contains resource state before and after."""
        executor = create_executor_mvp11(seed=0)
        
        outcome, metadata = executor.execute({
            "type": "seek_info",
            "params": {"query": "test"},
        })
        
        assert metadata.resource_state_before is not None
        assert metadata.resource_state_after is not None
        assert "time_remaining" in metadata.resource_state_before
        assert "energy_remaining" in metadata.resource_state_after

    def test_execute_metadata_contains_homeostasis_state(self):
        """Test metadata contains homeostasis state before and after."""
        executor = create_executor_mvp11(seed=0)
        
        outcome, metadata = executor.execute({
            "type": "seek_info",
            "params": {"query": "test"},
        })
        
        assert metadata.homeostasis_before is not None
        assert metadata.homeostasis_after is not None
        assert "energy" in metadata.homeostasis_before
        assert "certainty" in metadata.homeostasis_after

    def test_execute_mvp10_mode_no_metadata(self):
        """Test MVP10 mode returns None metadata."""
        executor = create_executor_mvp11(seed=0, enable_mvp11=False)
        
        outcome, metadata = executor.execute({
            "type": "seek_info",
            "params": {"query": "test"},
        })
        
        assert isinstance(outcome, ExecutionOutcome)
        assert metadata is None


class TestHomeostasisUpdate:
    """Test homeostasis updates from execution outcomes."""

    def test_homeostasis_updated_after_execution(self):
        """Test homeostasis state changes after execution."""
        executor = create_executor_mvp11(seed=0)
        
        initial_energy = executor.homeostasis_manager.state.energy
        initial_certainty = executor.homeostasis_manager.state.certainty
        
        # Execute several actions
        for _ in range(5):
            executor.execute({
                "type": "seek_info",
                "params": {"query": "test"},
            })
        
        # State should have changed
        assert executor.homeostasis_manager.state.energy != initial_energy

    def test_homeostasis_signal_available(self):
        """Test homeostasis signal is available."""
        executor = create_executor_mvp11(seed=0)
        
        signal = executor.get_homeostasis_signal()
        
        assert "state" in signal
        assert "deviation" in signal
        assert "urgency" in signal


class TestSelfDeficitDetection:
    """Test self-deficit detection."""

    def test_self_deficit_detected_low_energy(self):
        """Test self-deficit detected when energy is low."""
        executor = create_executor_mvp11(seed=0)
        
        # Drain energy below threshold
        executor.resource_env.energy_remaining = 20  # 20% of 100
        
        outcome, metadata = executor.execute({
            "type": "seek_info",
            "params": {"query": "test"},
        })
        
        assert metadata.self_deficit_detected == True
        assert "energy" in metadata.self_deficit_source.lower()

    def test_self_deficit_detected_low_time(self):
        """Test self-deficit detected when time is low."""
        executor = create_executor_mvp11(seed=0)
        
        # Drain time below threshold
        executor.resource_env.time_remaining = 15  # 15% of 100
        
        outcome, metadata = executor.execute({
            "type": "seek_info",
            "params": {"query": "test"},
        })
        
        assert metadata.self_deficit_detected == True
        assert "time" in metadata.self_deficit_source.lower()

    def test_self_deficit_history_recorded(self):
        """Test self-deficit events are recorded in history."""
        executor = create_executor_mvp11(seed=0)
        
        # Trigger deficit
        executor.resource_env.energy_remaining = 10
        executor.execute({"type": "seek_info", "params": {}})
        
        history = executor.get_self_deficit_history()
        
        assert len(history) > 0
        assert history[0]["type"] in ["energy_depletion", "time_depletion"]


class TestPerturbationInjection:
    """Test perturbation injection."""

    def test_inject_perturbation(self):
        """Test perturbation can be injected."""
        executor = create_executor_mvp11(seed=0)
        
        executor.inject_perturbation(PerturbationType.TOOL_FAILURE, 0.8)
        
        # Check perturbation is active
        state = executor.resource_env.get_state()
        assert state["perturbation"] == "tool_failure"

    def test_perturbation_affects_outcome(self):
        """Test perturbation affects execution outcome."""
        executor = create_executor_mvp11(seed=0)
        
        # Inject tool failure
        executor.inject_perturbation(PerturbationType.TOOL_FAILURE, 1.0)
        
        outcome, metadata = executor.execute({
            "type": "attempt_solution",
            "params": {"approach": "fix"},
        })
        
        # Metadata should show perturbation
        assert metadata.perturbation is not None


class TestPlanExecution:
    """Test plan execution."""

    def test_execute_plan(self):
        """Test executing a plan with multiple steps."""
        executor = create_executor_mvp11(seed=0)
        
        steps = [
            {"action": "seek_info", "params": {"query": "diagnose"}},
            {"action": "attempt_solution", "params": {"approach": "fix"}},
            {"action": "run_check", "params": {}},
        ]
        
        results = executor.execute_plan(steps)
        
        assert len(results) > 0
        for outcome, metadata in results:
            assert isinstance(outcome, ExecutionOutcome)

    def test_execute_plan_stops_on_fail(self):
        """Test plan execution stops on failure when resources depleted."""
        executor = create_executor_mvp11(seed=0)
        
        # Set resources to exactly cover one action (seek_info costs 0.1)
        executor.resource_env.time_remaining = 0.1
        executor.resource_env.energy_remaining = 0.1
        
        steps = [
            {"action": "seek_info", "params": {}},
            {"action": "seek_info", "params": {}},
            {"action": "seek_info", "params": {}},
        ]
        
        results = executor.execute_plan(steps)
        
        # First action succeeds (just enough resources)
        # Second action fails (resources depleted)
        assert len(results) == 2
        assert results[0][0].status == OutcomeStatus.SUCCESS
        assert results[1][0].status == OutcomeStatus.FAIL


class TestExecutorReset:
    """Test executor reset."""

    def test_reset_clears_history(self):
        """Test reset clears execution history."""
        executor = create_executor_mvp11(seed=0)
        
        # Execute some actions
        for _ in range(5):
            executor.execute({"type": "seek_info", "params": {}})
        
        executor.reset()
        
        assert len(executor.get_execution_history()) == 0
        assert len(executor.get_self_deficit_history()) == 0

    def test_reset_resets_resources(self):
        """Test reset resets resource state."""
        executor = create_executor_mvp11(seed=0)
        
        # Drain resources
        executor.resource_env.energy_remaining = 10
        executor.resource_env.time_remaining = 10
        
        executor.reset()
        
        state = executor.get_resource_state()
        assert state["energy_remaining"] == 100.0
        assert state["time_remaining"] == 100.0

    def test_reset_resets_homeostasis(self):
        """Test reset resets homeostasis state."""
        executor = create_executor_mvp11(seed=0)
        
        # Change homeostasis
        executor.homeostasis_manager.state.energy = 0.2
        
        executor.reset()
        
        # Homeostasis should be reset to initial state
        assert executor.homeostasis_manager.state.energy == 0.5


class TestSummary:
    """Test executor summary."""

    def test_get_summary(self):
        """Test get_summary returns expected fields."""
        executor = create_executor_mvp11(seed=0)
        
        summary = executor.get_summary()
        
        assert "total_executions" in summary
        assert "mvp11_enabled" in summary
        assert summary["mvp11_enabled"] == True

    def test_summary_includes_homeostasis(self):
        """Test summary includes homeostasis state."""
        executor = create_executor_mvp11(seed=0)
        
        summary = executor.get_summary()
        
        assert "homeostasis" in summary
        assert "homeostatic_error" in summary

    def test_summary_includes_resources(self):
        """Test summary includes resource state."""
        executor = create_executor_mvp11(seed=0)
        
        summary = executor.get_summary()
        
        assert "resource_state" in summary
        assert "self_deficit_count" in summary


class TestCreateExecutor:
    """Test factory functions."""

    def test_create_executor_mvp11(self):
        """Test create_executor_mvp11 function."""
        executor = create_executor_mvp11(seed=42)
        
        assert isinstance(executor, ExecutorMVP11)
        assert executor.seed == 42
        assert executor.enable_mvp11 == True

    def test_create_executor(self):
        """Test create_executor convenience function."""
        executor = create_executor(seed=42)
        
        assert isinstance(executor, ExecutorMVP11)
        assert executor.enable_mvp11 == True

    def test_create_executor_mvp10_mode(self):
        """Test create_executor with MVP11 disabled."""
        executor = create_executor(seed=42, enable_mvp11=False)
        
        assert executor.enable_mvp11 == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
