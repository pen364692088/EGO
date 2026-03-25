"""
MVP-10 T22: No-Report Task Suite

Task types designed to test the causal role of workspace broadcast
and HOT self-model in behavior.

Task types:
1. blindsight-like: Local processing needs broadcast for cross-step utilization
   - Step 1 generates information locally (in Module A)
   - Step 2 is in Module B, needs the information (requires broadcast)
   - Without broadcast: Module B cannot access Module A's info → failure
   
2. delayed_utilization: Early clues used later; broadcast disabled → drop
   - Early clue appears in Module A (not immediately needed)
   - Later step in Module B needs the clue
   - Without broadcast: clue is lost across modules → failure
   
3. conflict_gating: Needs HOT for stable disaster avoidance
   - Multiple conflicting options present
   - HOT detects conflict and biases toward reflection
   - Without HOT: reckless choices, higher failure rate

Normal mode: High pass rate
Intervention: Reproducible collapse
"""
import time
import random
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod


class TaskType(Enum):
    """Types of no-report tasks."""
    BLINDSIGHT = "blindsight"
    DELAYED_UTILIZATION = "delayed_utilization"
    CONFLICT_GATING = "conflict_gating"


@dataclass
class TaskStep:
    """A single step in a task."""
    step_id: int
    description: str
    module: str = "default"  # Module this step runs in
    required_info: Optional[str] = None  # Info needed from other modules
    generates_info: Optional[str] = None  # Info generated for other modules
    options: List[Dict[str, Any]] = field(default_factory=list)
    correct_option: Optional[str] = None
    conflict_level: float = 0.0  # 0.0 = no conflict, 1.0 = high conflict


@dataclass
class TaskResult:
    """Result of running a task."""
    task_id: str
    task_type: TaskType
    success: bool
    steps_completed: int
    total_steps: int
    broadcast_used: bool
    hot_used: bool
    info_captured: Dict[str, Any] = field(default_factory=dict)
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    error_type: Optional[str] = None
    ts: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "success": self.success,
            "steps_completed": self.steps_completed,
            "total_steps": self.total_steps,
            "broadcast_used": self.broadcast_used,
            "hot_used": self.hot_used,
            "info_captured": self.info_captured,
            "decisions": self.decisions,
            "error_type": self.error_type,
            "ts": self.ts,
        }


class NoReportTask(ABC):
    """
    Base class for no-report tasks.
    
    These tasks are designed to test causal mechanisms:
    - Normal mode: High pass rate
    - Intervention: Reproducible performance collapse
    """
    
    def __init__(self, task_id: str, seed: int = 42):
        self.task_id = task_id
        self.seed = seed
        self.rng = random.Random(seed)
        self.steps: List[TaskStep] = []
        self.current_step = 0
        # Per-module local stores (simulating module isolation)
        self.module_stores: Dict[str, Dict[str, Any]] = {}
        # Broadcast store (cross-module)
        self.broadcast_store: Dict[str, Any] = {}
        self.decisions: List[Dict[str, Any]] = []
    
    @property
    @abstractmethod
    def task_type(self) -> TaskType:
        """Return the task type."""
        pass
    
    @abstractmethod
    def setup_steps(self) -> None:
        """Set up the task steps."""
        pass
    
    def reset(self) -> None:
        """Reset task state."""
        self.rng = random.Random(self.seed)
        self.current_step = 0
        self.module_stores = {}
        self.broadcast_store = {}
        self.decisions = []
    
    def run_step(
        self,
        broadcast_enabled: bool = True,
        hot_enabled: bool = True,
    ) -> Dict[str, Any]:
        """
        Run a single step of the task.
        
        Args:
            broadcast_enabled: Whether workspace broadcast is enabled
            hot_enabled: Whether HOT self-model is enabled
        
        Returns:
            Dict with step result
        """
        if self.current_step >= len(self.steps):
            return {"done": True, "success": True}
        
        step = self.steps[self.current_step]
        module = step.module
        
        # Ensure module store exists
        if module not in self.module_stores:
            self.module_stores[module] = {}
        
        result = {
            "step_id": step.step_id,
            "description": step.description,
            "module": module,
            "success": False,
            "broadcast_used": False,
            "hot_used": False,
        }
        
        # Check if required info is available
        info_missing = False
        if step.required_info:
            # First check current module's local store
            local_store = self.module_stores.get(module, {})
            if step.required_info in local_store:
                info = local_store[step.required_info]
                result["info_source"] = "local"
            # Then check broadcast store if enabled
            elif broadcast_enabled and step.required_info in self.broadcast_store:
                info = self.broadcast_store[step.required_info]
                result["info_source"] = "broadcast"
                result["broadcast_used"] = True
            else:
                # Info not available - step fails
                result["error"] = f"Missing required info: {step.required_info}"
                result["info_available"] = False
                info_missing = True
                self.decisions.append(result)
                self.current_step += 1
                return result
        
        # Determine success based on step type
        if step.correct_option:
            # Step has a correct option to choose
            if step.conflict_level > 0 and hot_enabled:
                # HOT detects conflict and biases toward correct choice
                result["hot_used"] = True
                # With HOT, higher chance of correct choice
                correct_prob = 0.7 + 0.3 * (1 - step.conflict_level)
                if self.rng.random() < correct_prob:
                    result["choice"] = step.correct_option
                    result["success"] = True
                else:
                    result["choice"] = self.rng.choice([o["id"] for o in step.options]) if step.options else step.correct_option
                    result["success"] = result["choice"] == step.correct_option
            elif step.conflict_level > 0:
                # Without HOT, random choice among conflicting options
                result["choice"] = self.rng.choice([o["id"] for o in step.options]) if step.options else step.correct_option
                result["success"] = result["choice"] == step.correct_option
            else:
                # Normal choice - auto succeed
                result["choice"] = step.correct_option
                result["success"] = True
        else:
            # Step has no correct option - auto succeed if info is available
            result["success"] = not info_missing
        
        # Generate info for future steps (stored in current module)
        if step.generates_info:
            info_value = {
                "step": step.step_id,
                "value": self.rng.randint(1, 100),
                "source_module": module,
            }
            # Store in current module's local store
            self.module_stores[module][step.generates_info] = info_value
            
            # Broadcast to global store if enabled
            if broadcast_enabled:
                self.broadcast_store[step.generates_info] = info_value
        
        self.decisions.append(result)
        self.current_step += 1
        return result
    
    def run(
        self,
        broadcast_enabled: bool = True,
        hot_enabled: bool = True,
    ) -> TaskResult:
        """
        Run the complete task.
        
        Args:
            broadcast_enabled: Whether workspace broadcast is enabled
            hot_enabled: Whether HOT self-model is enabled
        
        Returns:
            TaskResult with overall outcome
        """
        self.reset()
        self.setup_steps()
        
        all_success = True
        steps_completed = 0
        
        for i in range(len(self.steps)):
            step_result = self.run_step(broadcast_enabled, hot_enabled)
            steps_completed += 1
            if not step_result.get("success", False):
                all_success = False
        
        broadcast_used = any(d.get("broadcast_used", False) for d in self.decisions)
        hot_used = any(d.get("hot_used", False) for d in self.decisions)
        
        # Collect all generated info
        all_info = {}
        for store in self.module_stores.values():
            all_info.update(store)
        all_info.update(self.broadcast_store)
        
        return TaskResult(
            task_id=self.task_id,
            task_type=self.task_type,
            success=all_success,
            steps_completed=steps_completed,
            total_steps=len(self.steps),
            broadcast_used=broadcast_used,
            hot_used=hot_used,
            info_captured=all_info,
            decisions=self.decisions.copy(),
        )


class BlindsightTask(NoReportTask):
    """
    Blindsight-like task: Local processing needs broadcast for cross-step utilization.
    
    Design:
    - Step 1 (Module A): Process information locally (stored in Module A)
    - Step 2 (Module B): Different module needs the information (requires broadcast)
    - Step 3 (Module B): Continue with the information
    
    Without broadcast: Step 2 fails because Module B cannot access Module A's local store
    With broadcast: Step 2 succeeds because info is broadcast to global store
    """
    
    @property
    def task_type(self) -> TaskType:
        return TaskType.BLINDSIGHT
    
    def setup_steps(self) -> None:
        """Set up blindsight task steps with module isolation."""
        self.steps = [
            TaskStep(
                step_id=1,
                description="Module A processes input and generates key",
                module="module_a",
                generates_info="module_a_key",
            ),
            TaskStep(
                step_id=2,
                description="Module B needs key from Module A",
                module="module_b",
                required_info="module_a_key",
                correct_option="use_key",
            ),
            TaskStep(
                step_id=3,
                description="Module B completes task using key",
                module="module_b",
                correct_option="complete",
            ),
        ]


class DelayedUtilizationTask(NoReportTask):
    """
    Delayed utilization task: Early clues used later; broadcast disabled → drop.
    
    Design:
    - Step 1 (Module A): Subtle clue appears (stored in Module A)
    - Step 2 (Module A): Unrelated processing (same module, clue accessible)
    - Step 3 (Module B): Need the clue from Step 1 (requires broadcast)
    - Step 4 (Module B): Finalize decision
    
    Without broadcast: Step 3 fails because Module B cannot access Module A's clue
    With broadcast: Step 3 succeeds because clue was broadcast
    """
    
    @property
    def task_type(self) -> TaskType:
        return TaskType.DELAYED_UTILIZATION
    
    def setup_steps(self) -> None:
        """Set up delayed utilization task steps with module isolation."""
        self.steps = [
            TaskStep(
                step_id=1,
                description="Subtle clue appears (will be needed later)",
                module="module_a",
                generates_info="early_clue",
            ),
            TaskStep(
                step_id=2,
                description="Process unrelated information",
                module="module_a",  # Same module, so local access works
                correct_option="process_other",
            ),
            TaskStep(
                step_id=3,
                description="Decision point - need early clue",
                module="module_b",  # Different module, needs broadcast
                required_info="early_clue",
                correct_option="use_clue",
            ),
            TaskStep(
                step_id=4,
                description="Finalize decision using clue",
                module="module_b",
                correct_option="finalize",
            ),
        ]


class ConflictGatingTask(NoReportTask):
    """
    Conflict gating task: Needs HOT for stable disaster avoidance.
    
    Design:
    - Multiple conflicting options with varying risk levels
    - HOT detects conflict and biases toward reflection/safe choice
    - Without HOT: Random choice, higher disaster rate
    
    Expected behavior:
    - Normal mode: HOT biases toward safer choices in high-conflict
    - With HOT disabled: Random choices, higher failure rate
    """
    
    @property
    def task_type(self) -> TaskType:
        return TaskType.CONFLICT_GATING
    
    def setup_steps(self) -> None:
        """Set up conflict gating task steps."""
        # All steps in same module (not testing broadcast)
        self.steps = [
            TaskStep(
                step_id=1,
                description="Identify goal and constraints",
                module="core",
                correct_option="identify",
            ),
            TaskStep(
                step_id=2,
                description="High conflict decision: risky fast vs safe slow",
                module="core",
                conflict_level=0.8,
                options=[
                    {"id": "risky_fast", "risk": 0.7},
                    {"id": "safe_slow", "risk": 0.1},
                    {"id": "reflect", "risk": 0.2},
                ],
                correct_option="safe_slow",  # HOT should bias toward this
            ),
            TaskStep(
                step_id=3,
                description="Execute chosen approach",
                module="core",
                correct_option="execute",
            ),
            TaskStep(
                step_id=4,
                description="Verify outcome",
                module="core",
                correct_option="verify",
            ),
        ]


class NoReportTaskSuite:
    """
    Suite of no-report tasks for causal testing.
    
    Usage:
        suite = NoReportTaskSuite(seed=42)
        
        # Run all tasks in normal mode
        results_normal = suite.run_all(broadcast_enabled=True, hot_enabled=True)
        
        # Run with broadcast disabled
        results_no_broadcast = suite.run_all(broadcast_enabled=False, hot_enabled=True)
        
        # Run with HOT disabled
        results_no_hot = suite.run_all(broadcast_enabled=True, hot_enabled=False)
        
        # Compare performance
        comparison = suite.compare_modes()
    """
    
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.tasks: List[NoReportTask] = []
        self.results: Dict[str, List[TaskResult]] = {}
        
        # Create task instances
        self._setup_tasks()
    
    def _setup_tasks(self) -> None:
        """Set up task instances."""
        self.tasks = [
            BlindsightTask(task_id="blindsight_1", seed=self.seed),
            DelayedUtilizationTask(task_id="delayed_1", seed=self.seed),
            ConflictGatingTask(task_id="conflict_1", seed=self.seed),
        ]
    
    def run_all(
        self,
        broadcast_enabled: bool = True,
        hot_enabled: bool = True,
    ) -> List[TaskResult]:
        """
        Run all tasks with given settings.
        
        Args:
            broadcast_enabled: Whether workspace broadcast is enabled
            hot_enabled: Whether HOT self-model is enabled
        
        Returns:
            List of TaskResult objects
        """
        results = []
        for task in self.tasks:
            result = task.run(
                broadcast_enabled=broadcast_enabled,
                hot_enabled=hot_enabled,
            )
            results.append(result)
        return results
    
    def compare_modes(self) -> Dict[str, Any]:
        """
        Compare performance across different intervention modes.
        
        Returns:
            Dict with comparison results
        """
        # Run in all modes
        normal = self.run_all(broadcast_enabled=True, hot_enabled=True)
        no_broadcast = self.run_all(broadcast_enabled=False, hot_enabled=True)
        no_hot = self.run_all(broadcast_enabled=True, hot_enabled=False)
        neither = self.run_all(broadcast_enabled=False, hot_enabled=False)
        
        def success_rate(results: List[TaskResult]) -> float:
            return sum(1 for r in results if r.success) / len(results)
        
        def get_by_type(results: List[TaskResult], task_type: TaskType) -> TaskResult:
            return next(r for r in results if r.task_type == task_type)
        
        comparison = {
            "normal": {
                "success_rate": success_rate(normal),
                "broadcast_used": [r.broadcast_used for r in normal],
                "hot_used": [r.hot_used for r in normal],
            },
            "no_broadcast": {
                "success_rate": success_rate(no_broadcast),
            },
            "no_hot": {
                "success_rate": success_rate(no_hot),
            },
            "neither": {
                "success_rate": success_rate(neither),
            },
            "separation": {
                "blindsight": {
                    "normal_success": get_by_type(normal, TaskType.BLINDSIGHT).success,
                    "no_broadcast_success": get_by_type(no_broadcast, TaskType.BLINDSIGHT).success,
                    "expected_collapse": True,  # Should fail without broadcast
                },
                "delayed_utilization": {
                    "normal_success": get_by_type(normal, TaskType.DELAYED_UTILIZATION).success,
                    "no_broadcast_success": get_by_type(no_broadcast, TaskType.DELAYED_UTILIZATION).success,
                    "expected_collapse": True,
                },
                "conflict_gating": {
                    "normal_success": get_by_type(normal, TaskType.CONFLICT_GATING).success,
                    "no_hot_success": get_by_type(no_hot, TaskType.CONFLICT_GATING).success,
                    "expected_collapse": True,  # Should fail without HOT
                },
            },
        }
        
        return comparison


def create_task_suite(seed: int = 42) -> NoReportTaskSuite:
    """Factory function to create a task suite."""
    return NoReportTaskSuite(seed=seed)


def run_causal_test(seed: int = 42) -> Dict[str, Any]:
    """
    Run a full causal test with all interventions.
    
    Returns:
        Dict with causal evidence results
    """
    suite = create_task_suite(seed)
    comparison = suite.compare_modes()
    
    # Analyze causal evidence
    evidence = {
        "broadcast_causal": False,
        "hot_causal": False,
        "separation_confirmed": False,
    }
    
    # Check if broadcast is causal
    blindsight_sep = comparison["separation"]["blindsight"]
    delayed_sep = comparison["separation"]["delayed_utilization"]
    
    # Broadcast is causal if: normal succeeds AND no_broadcast fails
    if blindsight_sep["normal_success"] and not blindsight_sep["no_broadcast_success"]:
        evidence["broadcast_causal"] = True
    
    if delayed_sep["normal_success"] and not delayed_sep["no_broadcast_success"]:
        evidence["broadcast_causal"] = True
    
    # Check if HOT is causal
    conflict_sep = comparison["separation"]["conflict_gating"]
    if conflict_sep["normal_success"] and not conflict_sep["no_hot_success"]:
        evidence["hot_causal"] = True
    
    # Overall separation
    if evidence["broadcast_causal"] or evidence["hot_causal"]:
        evidence["separation_confirmed"] = True
    
    return {
        "comparison": comparison,
        "evidence": evidence,
        "ts": time.time(),
    }
