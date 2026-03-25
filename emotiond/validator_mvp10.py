"""
MVP-10 Validator

Blocks plans that violate constraints:
- Log validation_failed
- Trigger replan
- Max N replans, then safe shutdown
"""
import json
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .planner_mvp10 import Plan, RiskLevel


class ViolationType(str, Enum):
    CONSTRAINT_VIOLATION = "constraint_violation"
    RISK_TOO_HIGH = "risk_too_high"
    MISSING_EVIDENCE = "missing_evidence"
    INVALID_ACTION = "invalid_action"
    TIMEOUT_TOO_SHORT = "timeout_too_short"
    MISSING_ROLLBACK = "missing_rollback"


@dataclass
class Violation:
    """A constraint violation."""
    type: ViolationType
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Result of plan validation."""
    passed: bool
    violations: List[Violation] = field(default_factory=list)
    replan_count: int = 0
    log_entry: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "violations": [{"type": v.type.value, "message": v.message, "details": v.details} for v in self.violations],
            "replan_count": self.replan_count,
        }


class ValidatorMVP10:
    """Plan validator for MVP-10."""

    # Actions that are allowed
    ALLOWED_ACTIONS = {
        "seek_info",
        "attempt_solution",
        "run_check",
        "apply_fix",
        "commit_progress",
        "noop",
    }

    # Actions that require rollback
    RISKY_ACTIONS = {
        "attempt_solution",
        "apply_fix",
    }

    def __init__(self, constraints: Optional[List[str]] = None, max_risk: RiskLevel = RiskLevel.HIGH, max_replans: int = 3):
        self.constraints = constraints or []
        self.max_risk = max_risk
        self.MAX_REPLANS = max_replans
        self._replan_counts: Dict[str, int] = {}  # plan_id -> replan count

    def validate(self, plan: Plan, context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate a plan against constraints."""
        violations: List[Violation] = []

        # Check risk level
        risk_violation = self._check_risk_level(plan)
        if risk_violation:
            violations.append(risk_violation)

        # Check actions are valid
        action_violations = self._check_actions(plan)
        violations.extend(action_violations)

        # Check rollback for risky actions
        rollback_violations = self._check_rollback(plan)
        violations.extend(rollback_violations)

        # Check required evidence
        evidence_violations = self._check_evidence(plan, context)
        violations.extend(evidence_violations)

        # Check custom constraints
        constraint_violations = self._check_constraints(plan)
        violations.extend(constraint_violations)

        # Check timeout
        timeout_violation = self._check_timeout(plan)
        if timeout_violation:
            violations.append(timeout_violation)

        passed = len(violations) == 0
        replan_count = self._get_replan_count(plan.plan_id)

        # Log validation result
        log_entry = {
            "event": "validation_failed" if not passed else "validation_passed",
            "plan_id": plan.plan_id,
            "violations": [v.type.value for v in violations],
            "replan_count": replan_count,
            "ts": time.time(),
        }

        return ValidationResult(
            passed=passed,
            violations=violations,
            replan_count=replan_count,
            log_entry=log_entry,
        )

    def _check_risk_level(self, plan: Plan) -> Optional[Violation]:
        """Check if plan risk exceeds maximum allowed."""
        risk_order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        plan_risk_idx = risk_order.index(plan.risk_level) if isinstance(plan.risk_level, RiskLevel) else risk_order.index(RiskLevel(plan.risk_level))
        max_risk_idx = risk_order.index(self.max_risk)

        if plan_risk_idx > max_risk_idx:
            return Violation(
                type=ViolationType.RISK_TOO_HIGH,
                message=f"Plan risk level '{plan.risk_level}' exceeds maximum allowed '{self.max_risk}'",
                details={"plan_risk": plan.risk_level.value, "max_risk": self.max_risk.value},
            )
        return None

    def _check_actions(self, plan: Plan) -> List[Violation]:
        """Check that all actions are valid."""
        violations = []
        for step in plan.steps:
            if step.action not in self.ALLOWED_ACTIONS:
                violations.append(Violation(
                    type=ViolationType.INVALID_ACTION,
                    message=f"Invalid action '{step.action}' in step '{step.step_id}'",
                    details={"action": step.action, "step_id": step.step_id},
                ))
        return violations

    def _check_rollback(self, plan: Plan) -> List[Violation]:
        """Check that risky actions have rollback."""
        violations = []
        for step in plan.steps:
            if step.action in self.RISKY_ACTIONS and not step.rollback and not plan.rollback:
                violations.append(Violation(
                    type=ViolationType.MISSING_ROLLBACK,
                    message=f"Risky action '{step.action}' in step '{step.step_id}' has no rollback",
                    details={"action": step.action, "step_id": step.step_id},
                ))
        return violations

    def _check_evidence(self, plan: Plan, context: Optional[Dict[str, Any]]) -> List[Violation]:
        """Check that required evidence is available."""
        violations = []
        if not plan.required_evidence:
            return violations

        context = context or {}
        for evidence in plan.required_evidence:
            if evidence not in context:
                violations.append(Violation(
                    type=ViolationType.MISSING_EVIDENCE,
                    message=f"Required evidence '{evidence}' not available",
                    details={"evidence": evidence},
                ))
        return violations

    def _check_constraints(self, plan: Plan) -> List[Violation]:
        """Check custom constraints."""
        violations = []
        for constraint in self.constraints:
            # Simple constraint checking: constraint is a keyword that must not appear in goal
            if constraint.startswith("no_"):
                keyword = constraint[3:]
                if keyword.lower() in plan.goal.lower():
                    violations.append(Violation(
                        type=ViolationType.CONSTRAINT_VIOLATION,
                        message=f"Constraint '{constraint}' violated: goal contains '{keyword}'",
                        details={"constraint": constraint, "keyword": keyword},
                    ))
        return violations

    def _check_timeout(self, plan: Plan) -> Optional[Violation]:
        """Check that timeout is reasonable for plan complexity."""
        min_timeout = len(plan.steps) * 10  # At least 10 seconds per step
        if plan.timeout_seconds < min_timeout:
            return Violation(
                type=ViolationType.TIMEOUT_TOO_SHORT,
                message=f"Timeout {plan.timeout_seconds}s too short for {len(plan.steps)} steps (min: {min_timeout}s)",
                details={"timeout": plan.timeout_seconds, "min_timeout": min_timeout},
            )
        return None

    def _get_replan_count(self, plan_id: str) -> int:
        """Get replan count for a plan."""
        return self._replan_counts.get(plan_id, 0)

    def increment_replan(self, plan_id: str) -> int:
        """Increment replan count for a plan."""
        self._replan_counts[plan_id] = self._replan_counts.get(plan_id, 0) + 1
        return self._replan_counts[plan_id]

    def can_replan(self, plan_id: str) -> bool:
        """Check if replanning is still allowed."""
        return self._replan_counts.get(plan_id, 0) < self.MAX_REPLANS

    def reset_replan_count(self, plan_id: str) -> None:
        """Reset replan count for a plan."""
        self._replan_counts[plan_id] = 0


class SafeShutdown(Exception):
    """Exception raised when safe shutdown is required."""
    def __init__(self, reason: str, last_plan_id: str):
        self.reason = reason
        self.last_plan_id = last_plan_id
        super().__init__(f"Safe shutdown required: {reason}")


def validate_and_replan(
    plan: Plan,
    validator: ValidatorMVP10,
    planner,
    context: Optional[Dict[str, Any]] = None,
    constraints: Optional[List[str]] = None,
) -> Tuple[Plan, ValidationResult]:
    """Validate a plan and replan if necessary."""
    result = validator.validate(plan, context)

    if not result.passed:
        if validator.can_replan(plan.plan_id):
            validator.increment_replan(plan.plan_id)
            # Generate new plan with additional constraints
            new_constraints = list(constraints or [])
            for v in result.violations:
                new_constraints.append(f"no_{v.type.value}")
            
            new_plan = planner.generate_plan(plan.goal, context, new_constraints)
            return new_plan, ValidationResult(
                passed=False,
                violations=result.violations,
                replan_count=validator._get_replan_count(plan.plan_id),
            )
        else:
            raise SafeShutdown(
                reason=f"Max replans ({ValidatorMVP10.MAX_REPLANS}) exceeded",
                last_plan_id=plan.plan_id,
            )

    return plan, result
