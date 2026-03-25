"""
MVP-10 Executor

Executes actions in a toy environment:
- Actions: seek_info, attempt_solution, run_check, apply_fix, commit_progress
- Outcome: success/fail/partial + reason
"""
import time
import random
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod


class OutcomeStatus(str, Enum):
    SUCCESS = "success"
    FAIL = "fail"
    PARTIAL = "partial"


@dataclass
class ExecutionOutcome:
    """Result of an action execution."""
    status: OutcomeStatus
    reason: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value if isinstance(self.status, OutcomeStatus) else self.status,
            "reason": self.reason,
            "evidence": self.evidence,
            "duration_ms": self.duration_ms,
        }


class ActionExecutor(ABC):
    """Abstract base class for action executors."""

    @abstractmethod
    def execute(self, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> ExecutionOutcome:
        """Execute an action and return the outcome."""
        pass


class ToyEnvironment:
    """
    Toy environment for testing the execution loop.
    
    Simulates a simple world where:
    - seek_info: Returns mock information
    - attempt_solution: May succeed or fail based on context
    - run_check: Validates state
    - apply_fix: Applies a fix to the environment
    - commit_progress: Saves state changes
    """

    def __init__(self, seed: int = 0):
        self.seed = seed
        self.rng = random.Random(seed)
        self.state: Dict[str, Any] = {
            "knowledge": [],
            "problems": [],
            "fixes_applied": [],
            "checks_passed": 0,
            "progress_saved": False,
        }
        self._action_history: List[Dict[str, Any]] = []

    def reset(self) -> None:
        """Reset environment to initial state."""
        self.rng = random.Random(self.seed)
        self.state = {
            "knowledge": [],
            "problems": [],
            "fixes_applied": [],
            "checks_passed": 0,
            "progress_saved": False,
        }
        self._action_history = []

    def get_state(self) -> Dict[str, Any]:
        """Get current environment state."""
        return dict(self.state)

    def set_problem(self, problem: str) -> None:
        """Set a problem for the environment to solve."""
        self.state["problems"].append(problem)

    def execute(self, action: str, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionOutcome:
        """Execute an action in the toy environment."""
        start_time = time.time()
        context = context or {}
        
        # Record action
        self._action_history.append({
            "action": action,
            "params": params,
            "ts": start_time,
        })

        # Execute based on action type
        if action == "seek_info":
            outcome = self._seek_info(params, context)
        elif action == "attempt_solution":
            outcome = self._attempt_solution(params, context)
        elif action == "run_check":
            outcome = self._run_check(params, context)
        elif action == "apply_fix":
            outcome = self._apply_fix(params, context)
        elif action == "commit_progress":
            outcome = self._commit_progress(params, context)
        elif action == "noop":
            outcome = ExecutionOutcome(status=OutcomeStatus.SUCCESS, reason="No action taken")
        else:
            outcome = ExecutionOutcome(status=OutcomeStatus.FAIL, reason=f"Unknown action: {action}")

        outcome.duration_ms = (time.time() - start_time) * 1000
        return outcome

    def _seek_info(self, params: Dict[str, Any], context: Dict[str, Any]) -> ExecutionOutcome:
        """Seek information about something."""
        query = params.get("query", "general")
        
        # Deterministic mock response based on query
        info = f"Info about: {query}"
        self.state["knowledge"].append(info)
        
        return ExecutionOutcome(
            status=OutcomeStatus.SUCCESS,
            reason=f"Found information about '{query}'",
            evidence={"query": query, "result": info},
        )

    def _attempt_solution(self, params: Dict[str, Any], context: Dict[str, Any]) -> ExecutionOutcome:
        """Attempt to solve a problem."""
        approach = params.get("approach", "general")
        
        # Deterministic outcome based on approach and state
        if self.state["problems"]:
            problem = self.state["problems"][0]
            
            # Solution success depends on having knowledge
            if self.state["knowledge"]:
                # Remove the problem
                self.state["problems"].pop(0)
                return ExecutionOutcome(
                    status=OutcomeStatus.SUCCESS,
                    reason=f"Solution '{approach}' resolved problem: {problem}",
                    evidence={"approach": approach, "resolved": problem},
                )
            else:
                return ExecutionOutcome(
                    status=OutcomeStatus.PARTIAL,
                    reason="No knowledge available for solution",
                    evidence={"approach": approach},
                )
        else:
            return ExecutionOutcome(
                status=OutcomeStatus.SUCCESS,
                reason="No problems to solve",
                evidence={"approach": approach},
            )

    def _run_check(self, params: Dict[str, Any], context: Dict[str, Any]) -> ExecutionOutcome:
        """Run a validation check."""
        validation_type = params.get("validation", "standard")
        
        # Check passes if no problems remain
        if not self.state["problems"]:
            self.state["checks_passed"] += 1
            return ExecutionOutcome(
                status=OutcomeStatus.SUCCESS,
                reason=f"All checks passed ({validation_type})",
                evidence={"validation": validation_type, "passed": True},
            )
        else:
            return ExecutionOutcome(
                status=OutcomeStatus.FAIL,
                reason=f"Checks failed: {len(self.state['problems'])} problems remain",
                evidence={"validation": validation_type, "passed": False, "problems": self.state["problems"]},
            )

    def _apply_fix(self, params: Dict[str, Any], context: Dict[str, Any]) -> ExecutionOutcome:
        """Apply a fix to the environment."""
        fix_type = params.get("type", "standard")
        target = params.get("target", "general")
        
        # Record the fix
        fix_record = {"type": fix_type, "target": target}
        self.state["fixes_applied"].append(fix_record)
        
        # Fix may resolve a problem
        if self.state["problems"]:
            self.state["problems"].pop(0)
            return ExecutionOutcome(
                status=OutcomeStatus.SUCCESS,
                reason=f"Fix '{fix_type}' applied to '{target}'",
                evidence=fix_record,
            )
        else:
            return ExecutionOutcome(
                status=OutcomeStatus.SUCCESS,
                reason="Fix applied (no problems to fix)",
                evidence=fix_record,
            )

    def _commit_progress(self, params: Dict[str, Any], context: Dict[str, Any]) -> ExecutionOutcome:
        """Commit progress to state."""
        update = params.get("update", "general")
        
        self.state["progress_saved"] = True
        
        return ExecutionOutcome(
            status=OutcomeStatus.SUCCESS,
            reason=f"Progress committed: {update}",
            evidence={"update": update, "state": self.get_state()},
        )


class ExecutorMVP10:
    """Main executor for MVP-10."""

    def __init__(self, environment: Optional[ToyEnvironment] = None, seed: int = 0):
        self.environment = environment or ToyEnvironment(seed=seed)
        self.seed = seed

    def execute_step(self, step: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionOutcome:
        """Execute a single plan step."""
        action = step.get("action", "noop")
        params = step.get("params", {})
        
        return self.environment.execute(action, params, context)

    def execute_plan(self, plan_steps: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> List[ExecutionOutcome]:
        """Execute all steps in a plan."""
        outcomes = []
        for step in plan_steps:
            outcome = self.execute_step(step, context)
            outcomes.append(outcome)
            
            # Stop on failure unless step says to continue
            if outcome.status == OutcomeStatus.FAIL:
                break
        
        return outcomes

    def reset(self) -> None:
        """Reset executor and environment."""
        self.environment.reset()


def create_executor(seed: int = 0) -> ExecutorMVP10:
    """Create an executor with given seed."""
    return ExecutorMVP10(seed=seed)
