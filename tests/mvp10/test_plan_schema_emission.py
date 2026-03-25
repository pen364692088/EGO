"""
T13 - Plan Schema Emission Tests

Tests for Structured Plan Generator.
"""
import json
import os
import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from emotiond.planner_mvp10 import (
    Plan, PlanStep, RiskLevel, PlannerMVP10, MockPlanner, plan_from_dict,
)


class TestPlanStep:
    """Test PlanStep dataclass."""

    def test_plan_step_creation(self):
        """Test creating a plan step."""
        step = PlanStep(
            action="seek_info",
            params={"query": "test"},
            expected_result="info found",
        )
        assert step.action == "seek_info"
        assert step.params == {"query": "test"}
        assert step.expected_result == "info found"
        assert step.step_id  # Auto-generated

    def test_plan_step_with_rollback(self):
        """Test plan step with rollback."""
        step = PlanStep(
            action="apply_fix",
            rollback="revert changes",
            required_evidence=["backup_created"],
        )
        assert step.rollback == "revert changes"
        assert "backup_created" in step.required_evidence

    def test_plan_step_auto_id(self):
        """Test that step ID is auto-generated."""
        step1 = PlanStep(action="test1")
        step2 = PlanStep(action="test2")
        
        assert step1.step_id != step2.step_id


class TestPlan:
    """Test Plan dataclass."""

    def test_plan_creation(self):
        """Test creating a plan."""
        steps = [PlanStep(action="seek_info")]
        plan = Plan(
            plan_id="plan_001",
            goal="fix bug",
            steps=steps,
            risk_level=RiskLevel.MEDIUM,
            expected_outcome="bug fixed",
        )
        
        assert plan.plan_id == "plan_001"
        assert plan.goal == "fix bug"
        assert len(plan.steps) == 1
        assert plan.risk_level == RiskLevel.MEDIUM

    def test_plan_to_dict(self):
        """Test plan serialization."""
        steps = [PlanStep(action="seek_info", step_id="step_1")]
        plan = Plan(
            plan_id="plan_001",
            goal="test",
            steps=steps,
            risk_level=RiskLevel.LOW,
            expected_outcome="success",
        )
        
        d = plan.to_dict()
        
        assert d["plan_id"] == "plan_001"
        assert d["goal"] == "test"
        assert len(d["steps"]) == 1
        assert d["risk_level"] == "low"

    def test_plan_with_rollback(self):
        """Test plan with rollback strategy."""
        plan = Plan(
            plan_id="plan_001",
            goal="fix",
            steps=[],
            risk_level=RiskLevel.HIGH,
            expected_outcome="fixed",
            rollback="restore from backup",
        )
        
        assert plan.rollback == "restore from backup"


class TestPlannerMVP10:
    """Test PlannerMVP10 class."""

    def test_planner_initialization(self):
        """Test planner initialization."""
        planner = PlannerMVP10(seed=42)
        assert planner.seed == 42

    def test_generate_plan(self):
        """Test generating a plan."""
        planner = PlannerMVP10(seed=42)
        plan = planner.generate_plan("fix the bug")
        
        assert plan.goal == "fix the bug"
        assert len(plan.steps) > 0
        assert plan.risk_level in RiskLevel

    def test_generate_plan_with_context(self):
        """Test generating a plan with context."""
        planner = PlannerMVP10(seed=42)
        context = {"known_issue": "memory leak"}
        plan = planner.generate_plan("fix the bug", context=context)
        
        assert plan is not None

    def test_generate_plan_with_constraints(self):
        """Test generating a plan with constraints."""
        planner = PlannerMVP10(seed=42)
        constraints = ["no_data_loss", "minimal_downtime"]
        plan = planner.generate_plan("fix the bug", constraints=constraints)
        
        assert plan.constraints == constraints


class TestMockPlanner:
    """Test MockPlanner for determinism."""

    def test_mock_planner_deterministic(self):
        """Test that mock planner is deterministic."""
        planner1 = MockPlanner(seed=42)
        planner2 = MockPlanner(seed=42)
        
        plan1 = planner1.generate_plan("test goal")
        plan2 = planner2.generate_plan("test goal")
        
        assert plan1.plan_id == plan2.plan_id
        assert [s.action for s in plan1.steps] == [s.action for s in plan2.steps]

    def test_mock_planner_different_seeds(self):
        """Test that different seeds produce different plans."""
        planner1 = MockPlanner(seed=42)
        planner2 = MockPlanner(seed=43)
        
        plan1 = planner1.generate_plan("test goal")
        plan2 = planner2.generate_plan("test goal")
        
        # Plan IDs should be different due to different seeds
        assert plan1.plan_id != plan2.plan_id

    def test_mock_planner_fix_goal(self):
        """Test mock planner with fix goal."""
        planner = MockPlanner(seed=42)
        plan = planner.generate_plan("fix the critical bug")
        
        # Should have seek_info, attempt_solution, run_check
        actions = [s.action for s in plan.steps]
        assert "seek_info" in actions
        assert "attempt_solution" in actions
        assert "run_check" in actions

    def test_mock_planner_check_goal(self):
        """Test mock planner with check goal."""
        planner = MockPlanner(seed=42)
        plan = planner.generate_plan("check the system")
        
        actions = [s.action for s in plan.steps]
        assert "run_check" in actions

    def test_mock_planner_info_goal(self):
        """Test mock planner with info goal."""
        planner = MockPlanner(seed=42)
        plan = planner.generate_plan("get info about X")
        
        actions = [s.action for s in plan.steps]
        assert "seek_info" in actions


class TestRiskAssessment:
    """Test risk level assessment."""

    def test_critical_keywords(self):
        """Test that critical keywords produce critical risk."""
        planner = PlannerMVP10(seed=42)
        
        for goal in ["delete all data", "force critical action", "dangerous operation"]:
            plan = planner.generate_plan(goal)
            assert plan.risk_level == RiskLevel.CRITICAL, f"Goal '{goal}' should be critical"

    def test_high_keywords(self):
        """Test that high risk keywords produce high risk."""
        planner = PlannerMVP10(seed=42)
        
        for goal in ["modify the config", "update the system", "write to disk"]:
            plan = planner.generate_plan(goal)
            assert plan.risk_level == RiskLevel.HIGH, f"Goal '{goal}' should be high"

    def test_medium_keywords(self):
        """Test that medium risk keywords produce medium risk."""
        planner = PlannerMVP10(seed=42)
        
        for goal in ["fix the bug", "repair the issue", "patch the problem"]:
            plan = planner.generate_plan(goal)
            assert plan.risk_level == RiskLevel.MEDIUM, f"Goal '{goal}' should be medium"

    def test_low_keywords(self):
        """Test that low risk goals produce low risk."""
        planner = PlannerMVP10(seed=42)
        
        for goal in ["read the file", "check status", "get information"]:
            plan = planner.generate_plan(goal)
            assert plan.risk_level == RiskLevel.LOW, f"Goal '{goal}' should be low"


class TestPlanFromDict:
    """Test plan_from_dict function."""

    def test_plan_from_dict_minimal(self):
        """Test creating plan from minimal dict."""
        data = {
            "steps": [{"action": "seek_info"}],
            "risk_level": "low",
            "expected_outcome": "success",
        }
        
        plan = plan_from_dict(data)
        
        assert len(plan.steps) == 1
        assert plan.risk_level == RiskLevel.LOW

    def test_plan_from_dict_full(self):
        """Test creating plan from full dict."""
        data = {
            "plan_id": "test_plan",
            "goal": "test goal",
            "steps": [
                {
                    "action": "seek_info",
                    "params": {"query": "test"},
                    "expected_result": "info",
                    "rollback": "none",
                    "required_evidence": ["auth"],
                }
            ],
            "risk_level": "high",
            "expected_outcome": "goal achieved",
            "rollback": "reset state",
            "required_evidence": ["backup"],
            "constraints": ["no_data_loss"],
            "timeout_seconds": 600,
        }
        
        plan = plan_from_dict(data)
        
        assert plan.plan_id == "test_plan"
        assert plan.goal == "test goal"
        assert len(plan.steps) == 1
        assert plan.steps[0].action == "seek_info"
        assert plan.risk_level == RiskLevel.HIGH
        assert plan.timeout_seconds == 600


class TestPlanSchemaCompliance:
    """Test that generated plans comply with schema."""

    def test_plan_has_required_fields(self):
        """Test that generated plans have required fields."""
        planner = MockPlanner(seed=42)
        plan = planner.generate_plan("test goal")
        
        d = plan.to_dict()
        
        assert "plan_id" in d
        assert "goal" in d
        assert "steps" in d
        assert "risk_level" in d
        assert "expected_outcome" in d

    def test_steps_have_required_fields(self):
        """Test that plan steps have required fields."""
        planner = MockPlanner(seed=42)
        plan = planner.generate_plan("test goal")
        
        for step in plan.steps:
            d = asdict(step) if hasattr(step, '__dataclass_fields__') else step
            assert "action" in d


class TestRollbackGeneration:
    """Test rollback strategy generation."""

    def test_rollback_for_delete(self):
        """Test rollback for delete operations."""
        planner = PlannerMVP10(seed=42)
        plan = planner.generate_plan("delete the file")
        
        assert "backup" in plan.rollback.lower() or "restore" in plan.rollback.lower()

    def test_rollback_for_modify(self):
        """Test rollback for modify operations."""
        planner = PlannerMVP10(seed=42)
        plan = planner.generate_plan("modify the config")
        
        assert "revert" in plan.rollback.lower() or "reset" in plan.rollback.lower()

    def test_rollback_default(self):
        """Test default rollback strategy."""
        planner = PlannerMVP10(seed=42)
        plan = planner.generate_plan("check status")
        
        assert plan.rollback  # Should have some rollback


# Import asdict for the test
from dataclasses import asdict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
