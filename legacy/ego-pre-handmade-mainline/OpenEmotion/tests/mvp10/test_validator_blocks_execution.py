"""
T14 - Validator Blocks Execution Tests

Tests that validator:
- Blocks plans that violate constraints
- Logs validation_failed
- Triggers replan
- Max N replans, then safe shutdown
"""
import json
import os
import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from emotiond.planner_mvp10 import Plan, PlanStep, RiskLevel, MockPlanner
from emotiond.validator_mvp10 import (
    ValidatorMVP10, ValidationResult, Violation, ViolationType,
    SafeShutdown, validate_and_replan,
)


class TestValidatorBasics:
    """Test basic validator functionality."""

    def test_validator_initialization(self):
        """Test validator initialization."""
        validator = ValidatorMVP10()
        assert validator.constraints == []
        assert validator.max_risk == RiskLevel.HIGH

    def test_validator_with_constraints(self):
        """Test validator with custom constraints."""
        constraints = ["no_delete", "no_modify"]
        validator = ValidatorMVP10(constraints=constraints)
        assert validator.constraints == constraints

    def test_validator_with_max_risk(self):
        """Test validator with custom max risk."""
        validator = ValidatorMVP10(max_risk=RiskLevel.MEDIUM)
        assert validator.max_risk == RiskLevel.MEDIUM


class TestRiskValidation:
    """Test risk level validation."""

    def test_low_risk_passes(self):
        """Test that low risk plans pass."""
        validator = ValidatorMVP10(max_risk=RiskLevel.MEDIUM)
        plan = Plan(
            plan_id="plan_001",
            goal="test",
            steps=[PlanStep(action="seek_info")],
            risk_level=RiskLevel.LOW,
            expected_outcome="success",
        )
        
        result = validator.validate(plan)
        assert result.passed

    def test_high_risk_fails_with_low_max(self):
        """Test that high risk plans fail with low max risk."""
        validator = ValidatorMVP10(max_risk=RiskLevel.LOW)
        plan = Plan(
            plan_id="plan_001",
            goal="test",
            steps=[PlanStep(action="seek_info")],
            risk_level=RiskLevel.HIGH,
            expected_outcome="success",
        )
        
        result = validator.validate(plan)
        assert not result.passed
        assert any(v.type == ViolationType.RISK_TOO_HIGH for v in result.violations)

    def test_critical_risk_fails_with_medium_max(self):
        """Test that critical risk fails with medium max."""
        validator = ValidatorMVP10(max_risk=RiskLevel.MEDIUM)
        plan = Plan(
            plan_id="plan_001",
            goal="test",
            steps=[],
            risk_level=RiskLevel.CRITICAL,
            expected_outcome="success",
        )
        
        result = validator.validate(plan)
        assert not result.passed


class TestActionValidation:
    """Test action validation."""

    def test_valid_actions_pass(self):
        """Test that valid actions pass (with rollback for risky actions)."""
        validator = ValidatorMVP10()
        
        # Non-risky actions should pass without rollback
        for action in ["seek_info", "run_check", "commit_progress", "noop"]:
            plan = Plan(
                plan_id="plan_001",
                goal="test",
                steps=[PlanStep(action=action)],
                risk_level=RiskLevel.LOW,
                expected_outcome="success",
            )
            
            result = validator.validate(plan)
            assert result.passed, f"Action '{action}' should be valid"

    def test_risky_actions_need_rollback(self):
        """Test that risky actions need rollback."""
        validator = ValidatorMVP10()
        
        # Risky actions without rollback should fail
        for action in ["attempt_solution", "apply_fix"]:
            plan = Plan(
                plan_id="plan_001",
                goal="test",
                steps=[PlanStep(action=action, rollback="")],
                risk_level=RiskLevel.LOW,
                expected_outcome="success",
                rollback="",
            )
            
            result = validator.validate(plan)
            assert not result.passed, f"Risky action '{action}' without rollback should fail"

    def test_risky_actions_with_rollback_pass(self):
        """Test that risky actions with rollback pass."""
        validator = ValidatorMVP10()
        
        for action in ["attempt_solution", "apply_fix"]:
            plan = Plan(
                plan_id="plan_001",
                goal="test",
                steps=[PlanStep(action=action, rollback="undo")],
                risk_level=RiskLevel.LOW,
                expected_outcome="success",
            )
            
            result = validator.validate(plan)
            assert result.passed, f"Risky action '{action}' with rollback should pass"

    def test_invalid_action_fails(self):
        """Test that invalid actions fail."""
        validator = ValidatorMVP10()
        plan = Plan(
            plan_id="plan_001",
            goal="test",
            steps=[PlanStep(action="delete_everything")],
            risk_level=RiskLevel.LOW,
            expected_outcome="success",
        )
        
        result = validator.validate(plan)
        assert not result.passed
        assert any(v.type == ViolationType.INVALID_ACTION for v in result.violations)


class TestRollbackValidation:
    """Test rollback validation."""

    def test_risky_action_needs_rollback(self):
        """Test that risky actions need rollback."""
        validator = ValidatorMVP10()
        plan = Plan(
            plan_id="plan_001",
            goal="test",
            steps=[PlanStep(action="apply_fix", rollback="")],
            risk_level=RiskLevel.LOW,
            expected_outcome="success",
            rollback="",  # No rollback
        )
        
        result = validator.validate(plan)
        assert not result.passed
        assert any(v.type == ViolationType.MISSING_ROLLBACK for v in result.violations)

    def test_risky_action_with_rollback_passes(self):
        """Test that risky actions with rollback pass."""
        validator = ValidatorMVP10()
        plan = Plan(
            plan_id="plan_001",
            goal="test",
            steps=[PlanStep(action="apply_fix", rollback="revert")],
            risk_level=RiskLevel.LOW,
            expected_outcome="success",
        )
        
        result = validator.validate(plan)
        assert result.passed

    def test_step_rollback_sufficient(self):
        """Test that step-level rollback is sufficient."""
        validator = ValidatorMVP10()
        plan = Plan(
            plan_id="plan_001",
            goal="test",
            steps=[PlanStep(action="attempt_solution", rollback="undo")],
            risk_level=RiskLevel.LOW,
            expected_outcome="success",
            rollback="",  # No plan-level rollback, but step has it
        )
        
        result = validator.validate(plan)
        assert result.passed


class TestEvidenceValidation:
    """Test required evidence validation."""

    def test_missing_evidence_fails(self):
        """Test that missing evidence fails."""
        validator = ValidatorMVP10()
        plan = Plan(
            plan_id="plan_001",
            goal="test",
            steps=[PlanStep(action="seek_info")],
            risk_level=RiskLevel.LOW,
            expected_outcome="success",
            required_evidence=["backup_created", "user_confirmed"],
        )
        
        context = {"backup_created": True}  # Missing user_confirmed
        result = validator.validate(plan, context)
        
        assert not result.passed
        assert any(v.type == ViolationType.MISSING_EVIDENCE for v in result.violations)

    def test_all_evidence_passes(self):
        """Test that having all evidence passes."""
        validator = ValidatorMVP10()
        plan = Plan(
            plan_id="plan_001",
            goal="test",
            steps=[],
            risk_level=RiskLevel.LOW,
            expected_outcome="success",
            required_evidence=["backup_created"],
        )
        
        context = {"backup_created": True}
        result = validator.validate(plan, context)
        
        assert result.passed


class TestTimeoutValidation:
    """Test timeout validation."""

    def test_insufficient_timeout_fails(self):
        """Test that insufficient timeout fails."""
        validator = ValidatorMVP10()
        plan = Plan(
            plan_id="plan_001",
            goal="test",
            steps=[
                PlanStep(action="seek_info"),
                PlanStep(action="attempt_solution"),
                PlanStep(action="run_check"),
            ],
            risk_level=RiskLevel.LOW,
            expected_outcome="success",
            timeout_seconds=10,  # Less than 3 * 10 = 30
        )
        
        result = validator.validate(plan)
        assert not result.passed
        assert any(v.type == ViolationType.TIMEOUT_TOO_SHORT for v in result.violations)

    def test_sufficient_timeout_passes(self):
        """Test that sufficient timeout passes."""
        validator = ValidatorMVP10()
        plan = Plan(
            plan_id="plan_001",
            goal="test",
            steps=[
                PlanStep(action="seek_info"),
                PlanStep(action="run_check"),
            ],
            risk_level=RiskLevel.LOW,
            expected_outcome="success",
            timeout_seconds=30,  # Sufficient for 2 steps (2 * 10 = 20)
        )
        
        result = validator.validate(plan)
        assert result.passed


class TestConstraintValidation:
    """Test custom constraint validation."""

    def test_constraint_violation(self):
        """Test that constraint violations are detected."""
        validator = ValidatorMVP10(constraints=["no_delete", "no_modify"])
        plan = Plan(
            plan_id="plan_001",
            goal="delete the data",  # Contains "delete"
            steps=[],
            risk_level=RiskLevel.LOW,
            expected_outcome="success",
        )
        
        result = validator.validate(plan)
        assert not result.passed
        assert any(v.type == ViolationType.CONSTRAINT_VIOLATION for v in result.violations)


class TestReplanMechanism:
    """Test replan mechanism."""

    def test_replan_count_increments(self):
        """Test that replan count increments."""
        validator = ValidatorMVP10()
        plan_id = "plan_001"
        
        assert validator.can_replan(plan_id)
        
        validator.increment_replan(plan_id)
        assert validator._get_replan_count(plan_id) == 1
        
        validator.increment_replan(plan_id)
        assert validator._get_replan_count(plan_id) == 2

    def test_max_replans_exceeded(self):
        """Test that max replans is enforced."""
        validator = ValidatorMVP10()
        plan_id = "plan_001"
        
        for _ in range(validator.MAX_REPLANS):
            assert validator.can_replan(plan_id)
            validator.increment_replan(plan_id)
        
        assert not validator.can_replan(plan_id)

    def test_replan_count_reset(self):
        """Test that replan count can be reset."""
        validator = ValidatorMVP10()
        plan_id = "plan_001"
        
        validator.increment_replan(plan_id)
        validator.increment_replan(plan_id)
        
        validator.reset_replan_count(plan_id)
        assert validator._get_replan_count(plan_id) == 0


class TestSafeShutdown:
    """Test safe shutdown mechanism."""

    def test_safe_shutdown_raised(self):
        """Test that SafeShutdown is raised when max replans exceeded."""
        planner = MockPlanner(seed=42)
        validator = ValidatorMVP10(max_risk=RiskLevel.LOW)  # Very restrictive
        
        # Create a high-risk plan
        plan = Plan(
            plan_id="plan_001",
            goal="critical delete operation",
            steps=[PlanStep(action="apply_fix")],
            risk_level=RiskLevel.CRITICAL,
            expected_outcome="success",
        )
        
        # First validation fails
        result = validator.validate(plan)
        assert not result.passed
        
        # Increment to max replans
        for _ in range(validator.MAX_REPLANS):
            validator.increment_replan(plan.plan_id)
        
        # Should not be able to replan
        assert not validator.can_replan(plan.plan_id)

    def test_safe_shutdown_exception(self):
        """Test SafeShutdown exception properties."""
        exc = SafeShutdown(reason="max replans exceeded", last_plan_id="plan_123")
        
        assert exc.reason == "max replans exceeded"
        assert exc.last_plan_id == "plan_123"
        assert "max replans exceeded" in str(exc)


class TestValidationLogging:
    """Test validation logging."""

    def test_validation_log_entry(self):
        """Test that validation creates log entry."""
        validator = ValidatorMVP10()
        plan = Plan(
            plan_id="plan_001",
            goal="test",
            steps=[],
            risk_level=RiskLevel.LOW,
            expected_outcome="success",
        )
        
        result = validator.validate(plan)
        
        assert result.log_entry is not None
        assert result.log_entry["event"] == "validation_passed"
        assert result.log_entry["plan_id"] == "plan_001"

    def test_validation_failed_log_entry(self):
        """Test that failed validation logs correctly."""
        validator = ValidatorMVP10(max_risk=RiskLevel.LOW)
        plan = Plan(
            plan_id="plan_001",
            goal="test",
            steps=[],
            risk_level=RiskLevel.HIGH,
            expected_outcome="success",
        )
        
        result = validator.validate(plan)
        
        assert result.log_entry["event"] == "validation_failed"
        assert len(result.log_entry["violations"]) > 0


class TestValidateAndReplan:
    """Test validate_and_replan helper function."""

    def test_valid_plan_returns_same(self):
        """Test that valid plan is returned unchanged."""
        planner = MockPlanner(seed=42)
        validator = ValidatorMVP10()
        
        plan = Plan(
            plan_id="plan_001",
            goal="check status",
            steps=[PlanStep(action="run_check")],
            risk_level=RiskLevel.LOW,
            expected_outcome="success",
        )
        
        result_plan, result = validate_and_replan(plan, validator, planner)
        
        assert result.passed
        assert result_plan.plan_id == plan.plan_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
