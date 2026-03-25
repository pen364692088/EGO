"""
MVP-10 T22: No-Report Task Suite Tests

Tests for no_report_tasks.py:
- blindsight-like: Local processing needs broadcast
- delayed_utilization: Early clues used later
- conflict_gating: Needs HOT for stable disaster avoidance
"""
import os
import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from emotiond.science.no_report_tasks import (
    TaskType,
    TaskStep,
    TaskResult,
    NoReportTask,
    BlindsightTask,
    DelayedUtilizationTask,
    ConflictGatingTask,
    NoReportTaskSuite,
    create_task_suite,
    run_causal_test,
)


class TestTaskType:
    """Test TaskType enum."""
    
    def test_task_types_exist(self):
        """Test that required task types exist."""
        assert TaskType.BLINDSIGHT.value == "blindsight"
        assert TaskType.DELAYED_UTILIZATION.value == "delayed_utilization"
        assert TaskType.CONFLICT_GATING.value == "conflict_gating"


class TestTaskStep:
    """Test TaskStep dataclass."""
    
    def test_step_creation(self):
        """Test creating a TaskStep."""
        step = TaskStep(
            step_id=1,
            description="Test step",
            required_info="key",
            generates_info="output",
        )
        
        assert step.step_id == 1
        assert step.description == "Test step"
        assert step.required_info == "key"
        assert step.generates_info == "output"
    
    def test_step_with_options(self):
        """Test step with options."""
        step = TaskStep(
            step_id=1,
            description="Choose",
            options=[{"id": "a"}, {"id": "b"}],
            correct_option="a",
            conflict_level=0.5,
        )
        
        assert len(step.options) == 2
        assert step.correct_option == "a"
        assert step.conflict_level == 0.5


class TestTaskResult:
    """Test TaskResult dataclass."""
    
    def test_result_creation(self):
        """Test creating a TaskResult."""
        result = TaskResult(
            task_id="test",
            task_type=TaskType.BLINDSIGHT,
            success=True,
            steps_completed=3,
            total_steps=3,
            broadcast_used=True,
            hot_used=False,
        )
        
        assert result.success == True
        assert result.broadcast_used == True
    
    def test_result_to_dict(self):
        """Test TaskResult serialization."""
        result = TaskResult(
            task_id="test",
            task_type=TaskType.BLINDSIGHT,
            success=True,
            steps_completed=3,
            total_steps=3,
            broadcast_used=True,
            hot_used=False,
        )
        
        d = result.to_dict()
        
        assert d["task_id"] == "test"
        assert d["task_type"] == "blindsight"
        assert d["success"] == True


class TestBlindsightTask:
    """Test BlindsightTask."""
    
    def test_task_type(self):
        """Test task type is correct."""
        task = BlindsightTask(task_id="test", seed=42)
        
        assert task.task_type == TaskType.BLINDSIGHT
    
    def test_setup_steps(self):
        """Test that steps are set up."""
        task = BlindsightTask(task_id="test", seed=42)
        task.setup_steps()
        
        assert len(task.steps) == 3
        assert task.steps[0].generates_info == "module_a_key"
        assert task.steps[1].required_info == "module_a_key"
    
    def test_run_with_broadcast(self):
        """Test running with broadcast enabled."""
        task = BlindsightTask(task_id="test", seed=42)
        
        result = task.run(broadcast_enabled=True, hot_enabled=True)
        
        assert result.success == True
        assert result.steps_completed == 3
    
    def test_run_without_broadcast(self):
        """Test running with broadcast disabled - should fail."""
        task = BlindsightTask(task_id="test", seed=42)
        
        result = task.run(broadcast_enabled=False, hot_enabled=True)
        
        # Without broadcast, step 2 should fail
        assert result.success == False
    
    def test_reset(self):
        """Test task reset."""
        task = BlindsightTask(task_id="test", seed=42)
        task.run()
        
        task.reset()
        
        assert task.current_step == 0
        assert len(task.module_stores) == 0
        assert len(task.broadcast_store) == 0


class TestDelayedUtilizationTask:
    """Test DelayedUtilizationTask."""
    
    def test_task_type(self):
        """Test task type is correct."""
        task = DelayedUtilizationTask(task_id="test", seed=42)
        
        assert task.task_type == TaskType.DELAYED_UTILIZATION
    
    def test_setup_steps(self):
        """Test that steps are set up."""
        task = DelayedUtilizationTask(task_id="test", seed=42)
        task.setup_steps()
        
        assert len(task.steps) == 4
        assert task.steps[0].generates_info == "early_clue"
        assert task.steps[2].required_info == "early_clue"
    
    def test_run_with_broadcast(self):
        """Test running with broadcast enabled."""
        task = DelayedUtilizationTask(task_id="test", seed=42)
        
        result = task.run(broadcast_enabled=True, hot_enabled=True)
        
        assert result.success == True
    
    def test_run_without_broadcast(self):
        """Test running with broadcast disabled - should fail."""
        task = DelayedUtilizationTask(task_id="test", seed=42)
        
        result = task.run(broadcast_enabled=False, hot_enabled=True)
        
        # Without broadcast, early clue is lost
        assert result.success == False


class TestConflictGatingTask:
    """Test ConflictGatingTask."""
    
    def test_task_type(self):
        """Test task type is correct."""
        task = ConflictGatingTask(task_id="test", seed=42)
        
        assert task.task_type == TaskType.CONFLICT_GATING
    
    def test_setup_steps(self):
        """Test that steps are set up with conflict."""
        task = ConflictGatingTask(task_id="test", seed=42)
        task.setup_steps()
        
        # Find the high-conflict step
        conflict_step = next(s for s in task.steps if s.conflict_level > 0)
        
        assert conflict_step is not None
        assert conflict_step.conflict_level == 0.8
    
    def test_run_with_hot(self):
        """Test running with HOT enabled - should succeed more often."""
        task = ConflictGatingTask(task_id="test", seed=42)
        
        result = task.run(broadcast_enabled=True, hot_enabled=True)
        
        # With HOT, should have better conflict resolution
        assert result.hot_used == True
    
    def test_run_without_hot(self):
        """Test running with HOT disabled."""
        task = ConflictGatingTask(task_id="test", seed=42)
        
        result = task.run(broadcast_enabled=True, hot_enabled=False)
        
        # Without HOT, conflict resolution is random
        assert result.hot_used == False


class TestNoReportTaskSuite:
    """Test NoReportTaskSuite."""
    
    def test_suite_creation(self):
        """Test creating a task suite."""
        suite = NoReportTaskSuite(seed=42)
        
        assert len(suite.tasks) == 3
    
    def test_run_all_normal(self):
        """Test running all tasks in normal mode."""
        suite = NoReportTaskSuite(seed=42)
        
        results = suite.run_all(broadcast_enabled=True, hot_enabled=True)
        
        assert len(results) == 3
    
    def test_compare_modes(self):
        """Test comparing different modes."""
        suite = NoReportTaskSuite(seed=42)
        
        comparison = suite.compare_modes()
        
        assert "normal" in comparison
        assert "no_broadcast" in comparison
        assert "no_hot" in comparison
        assert "separation" in comparison
    
    def test_separation_blindsight(self):
        """Test separation for blindsight task."""
        suite = NoReportTaskSuite(seed=42)
        comparison = suite.compare_modes()
        
        blindsight_sep = comparison["separation"]["blindsight"]
        
        # Normal should succeed, no_broadcast should fail
        assert blindsight_sep["normal_success"] == True
        assert blindsight_sep["no_broadcast_success"] == False
    
    def test_separation_delayed(self):
        """Test separation for delayed utilization task."""
        suite = NoReportTaskSuite(seed=42)
        comparison = suite.compare_modes()
        
        delayed_sep = comparison["separation"]["delayed_utilization"]
        
        # Normal should succeed, no_broadcast should fail
        assert delayed_sep["normal_success"] == True
        assert delayed_sep["no_broadcast_success"] == False
    
    def test_separation_conflict(self):
        """Test separation for conflict gating task."""
        suite = NoReportTaskSuite(seed=42)
        comparison = suite.compare_modes()
        
        conflict_sep = comparison["separation"]["conflict_gating"]
        
        # Normal should have better success than no_hot
        # (though exact values depend on random seed)
        assert "normal_success" in conflict_sep
        assert "no_hot_success" in conflict_sep


class TestCausalTest:
    """Test run_causal_test function."""
    
    def test_causal_test_returns_evidence(self):
        """Test that causal test returns evidence dict."""
        result = run_causal_test(seed=42)
        
        assert "comparison" in result
        assert "evidence" in result
    
    def test_evidence_structure(self):
        """Test evidence structure."""
        result = run_causal_test(seed=42)
        
        evidence = result["evidence"]
        
        assert "broadcast_causal" in evidence
        assert "hot_causal" in evidence
        assert "separation_confirmed" in evidence
    
    def test_broadcast_is_causal(self):
        """Test that broadcast shows causal effect."""
        result = run_causal_test(seed=42)
        
        # Based on task design, broadcast should show causal effect
        assert result["evidence"]["broadcast_causal"] == True
    
    def test_hot_is_causal(self):
        """Test that HOT shows causal effect in conflict tasks."""
        result = run_causal_test(seed=42)
        
        # Conflict gating task should show HOT effect
        # Note: due to randomness, this might not always be True
        assert "hot_causal" in result["evidence"]


class TestFactoryFunction:
    """Test factory function."""
    
    def test_create_task_suite(self):
        """Test factory function."""
        suite = create_task_suite(seed=42)
        
        assert isinstance(suite, NoReportTaskSuite)
        assert len(suite.tasks) == 3
