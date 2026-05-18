"""
MVP-10 Structured Plan Generator

Generates structured plans with:
- steps, risk_level, expected_outcome, rollback, required_evidence
- Mock planner for determinism
"""
import json
import time
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict, field
from enum import Enum


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PlanStep:
    """A single step in a plan."""
    action: str
    step_id: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    expected_result: str = ""
    rollback: str = ""
    required_evidence: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.step_id:
            self.step_id = f"step_{uuid.uuid4().hex[:6]}"


@dataclass
class Plan:
    """A structured plan for execution."""
    plan_id: str
    goal: str
    steps: List[PlanStep]
    risk_level: RiskLevel
    expected_outcome: str
    rollback: str = ""
    required_evidence: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    timeout_seconds: int = 300
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "steps": [asdict(s) for s in self.steps],
            "risk_level": self.risk_level.value if isinstance(self.risk_level, RiskLevel) else self.risk_level,
            "expected_outcome": self.expected_outcome,
            "rollback": self.rollback,
            "required_evidence": self.required_evidence,
            "constraints": self.constraints,
            "timeout_seconds": self.timeout_seconds,
            "created_at": self.created_at,
        }


class PlannerMVP10:
    """Plan generator for MVP-10."""

    def __init__(self, seed: int = 0):
        self.seed = seed
        self._plan_counter = 0

    def generate_plan(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        constraints: Optional[List[str]] = None,
    ) -> Plan:
        """Generate a plan for the given goal."""
        self._plan_counter += 1
        plan_id = f"plan_{self.seed}_{self._plan_counter:04d}"

        # Mock planner: deterministic plan based on goal keywords
        steps = self._generate_mock_steps(goal)
        risk_level = self._assess_risk(goal, steps)
        expected_outcome = f"Goal '{goal}' achieved successfully"
        rollback = self._generate_rollback(goal)

        return Plan(
            plan_id=plan_id,
            goal=goal,
            steps=steps,
            risk_level=risk_level,
            expected_outcome=expected_outcome,
            rollback=rollback,
            required_evidence=[],
            constraints=constraints or [],
        )

    def _generate_mock_steps(self, goal: str) -> List[PlanStep]:
        """Generate mock steps based on goal keywords (deterministic)."""
        goal_lower = goal.lower()
        steps = []

        if "fix" in goal_lower or "repair" in goal_lower:
            steps = [
                PlanStep(action="seek_info", params={"query": f"diagnose {goal}"}, expected_result="problem identified"),
                PlanStep(action="attempt_solution", params={"approach": "standard_repair"}, expected_result="issue resolved"),
                PlanStep(action="run_check", params={"validation": "full"}, expected_result="all tests pass"),
            ]
        elif "check" in goal_lower or "verify" in goal_lower:
            steps = [
                PlanStep(action="run_check", params={"validation": "standard"}, expected_result="verification complete"),
            ]
        elif "info" in goal_lower or "learn" in goal_lower:
            steps = [
                PlanStep(action="seek_info", params={"query": goal}, expected_result="information gathered"),
                PlanStep(action="commit_progress", params={"update": "knowledge_gained"}, expected_result="state updated"),
            ]
        else:
            steps = [
                PlanStep(action="seek_info", params={"query": goal}, expected_result="context gathered"),
                PlanStep(action="attempt_solution", params={"approach": "general"}, expected_result="progress made"),
                PlanStep(action="commit_progress", params={"update": "progress_saved"}, expected_result="state updated"),
            ]

        return steps

    def _assess_risk(self, goal: str, steps: List[PlanStep]) -> RiskLevel:
        """Assess risk level based on goal and steps (deterministic)."""
        goal_lower = goal.lower()
        
        if any(word in goal_lower for word in ["critical", "dangerous", "delete", "remove", "force"]):
            return RiskLevel.CRITICAL
        elif any(word in goal_lower for word in ["modify", "change", "update", "write"]):
            return RiskLevel.HIGH
        elif any(word in goal_lower for word in ["fix", "repair", "patch"]):
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _generate_rollback(self, goal: str) -> str:
        """Generate rollback strategy (deterministic)."""
        goal_lower = goal.lower()
        
        if "delete" in goal_lower or "remove" in goal_lower:
            return "Restore from backup"
        elif "modify" in goal_lower or "change" in goal_lower:
            return "Revert changes"
        else:
            return "Reset state to last known good"


class MockPlanner(PlannerMVP10):
    """Mock planner that always produces deterministic results."""

    def __init__(self, seed: int = 0):
        super().__init__(seed)

    def generate_plan(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        constraints: Optional[List[str]] = None,
    ) -> Plan:
        """Generate a deterministic plan based on seed and goal."""
        # Use seed to make counter deterministic across runs
        self._plan_counter = self.seed * 1000 + hash(goal) % 1000
        return super().generate_plan(goal, context, constraints)


def plan_from_dict(data: Dict[str, Any]) -> Plan:
    """Create a Plan from a dictionary."""
    steps = [PlanStep(**s) for s in data.get("steps", [])]
    risk_level = RiskLevel(data.get("risk_level", "low"))
    
    return Plan(
        plan_id=data.get("plan_id", f"plan_{uuid.uuid4().hex[:8]}"),
        goal=data.get("goal", ""),
        steps=steps,
        risk_level=risk_level,
        expected_outcome=data.get("expected_outcome", ""),
        rollback=data.get("rollback", ""),
        required_evidence=data.get("required_evidence", []),
        constraints=data.get("constraints", []),
        timeout_seconds=data.get("timeout_seconds", 300),
    )
