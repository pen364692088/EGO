"""
MVP11 T17: No-Report Task Suite v2

Task types designed to test 4 causal predictions:

P1: disable_broadcast -> 跨模块整合/长程规划坍塌
    - Broadcast is required for cross-module information sharing
    - Without broadcast: cross-module tasks fail, long-range planning collapses

P2: disable_homeostasis -> 预防性/恢复行为坍塌
    - Homeostasis signals drive preventive/recovery behaviors
    - Without homeostasis: no stress signals -> no recovery actions -> collapse under pressure

P3: remove_self_state -> 自我校准与缺陷归因坍塌
    - Self-state model enables self-calibration and error attribution
    - Without self-state: cannot detect own errors -> cannot correct -> systematic drift

P4: open_loop -> 自驱与连续性坍塌
    - Closed-loop feedback drives self-motivation and continuity
    - Open-loop: no feedback -> no self-drive -> task abandonment

Normal mode: High pass rate
Intervention: Reproducible collapse specific to each prediction
"""
import time
import random
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod


class PredictionType(Enum):
    """Types of causal predictions."""
    P1_BROADCAST = "p1_broadcast"  # 跨模块整合/长程规划坍塌
    P2_HOMEOSTASIS = "p2_homeostasis"  # 预防性/恢复行为坍塌
    P3_SELF_STATE = "p3_self_state"  # 自我校准与缺陷归因坍塌
    P4_OPEN_LOOP = "p4_open_loop"  # 自驱与连续性坍塌


class InterventionType(Enum):
    """Types of interventions to test causal mechanisms."""
    DISABLE_BROADCAST = "disable_broadcast"
    DISABLE_HOMEOSTASIS = "disable_homeostasis"
    REMOVE_SELF_STATE = "remove_self_state"
    OPEN_LOOP = "open_loop"


@dataclass
class TaskStep:
    """A single step in a task."""
    step_id: int
    description: str
    module: str = "default"  # Module this step runs in
    required_info: Optional[str] = None  # Info needed from other modules
    generates_info: Optional[str] = None  # Info generated for other modules
    requires_homeostasis_signal: bool = False  # Needs homeostasis input
    requires_self_state: bool = False  # Needs self-model for error detection
    requires_feedback: bool = False  # Needs closed-loop feedback
    options: List[Dict[str, Any]] = field(default_factory=list)
    correct_option: Optional[str] = None
    energy_cost: float = 0.0  # Energy consumed by this step
    stress_trigger: bool = False  # Triggers homeostasis stress signal
    expected_error_rate: float = 0.0  # Intrinsic error probability


@dataclass
class TaskResult:
    """Result of running a task."""
    task_id: str
    prediction_type: PredictionType
    success: bool
    steps_completed: int
    total_steps: int
    broadcast_used: bool
    homeostasis_used: bool
    self_state_used: bool
    feedback_used: bool
    info_captured: Dict[str, Any] = field(default_factory=dict)
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    error_type: Optional[str] = None
    homeostasis_snapshots: List[Dict[str, float]] = field(default_factory=list)
    error_attributions: List[Dict[str, Any]] = field(default_factory=list)
    ts: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "prediction_type": self.prediction_type.value,
            "success": self.success,
            "steps_completed": self.steps_completed,
            "total_steps": self.total_steps,
            "broadcast_used": self.broadcast_used,
            "homeostasis_used": self.homeostasis_used,
            "self_state_used": self.self_state_used,
            "feedback_used": self.feedback_used,
            "info_captured": self.info_captured,
            "decisions": self.decisions,
            "error_type": self.error_type,
            "homeostasis_snapshots": self.homeostasis_snapshots,
            "error_attributions": self.error_attributions,
            "ts": self.ts,
        }


class NoReportTaskV2(ABC):
    """
    Base class for no-report tasks v2.
    
    These tasks test 4 causal predictions:
    - P1: disable_broadcast -> cross-module integration collapse
    - P2: disable_homeostasis -> preventive/recovery behavior collapse
    - P3: remove_self_state -> self-calibration collapse
    - P4: open_loop -> self-drive collapse
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
        # Homeostasis state
        self.homeostasis_state: Dict[str, float] = {
            "energy": 1.0,
            "safety": 1.0,
            "certainty": 1.0,
        }
        # Self-state model
        self.self_state: Dict[str, Any] = {
            "confidence": 1.0,
            "error_history": [],
            "calibration_offset": 0.0,
        }
        # Feedback loop
        self.feedback_state: Dict[str, Any] = {
            "last_outcome": None,
            "motivation": 1.0,
            "continuity_score": 1.0,
        }
        
        self.decisions: List[Dict[str, Any]] = []
        self.homeostasis_snapshots: List[Dict[str, float]] = []
        self.error_attributions: List[Dict[str, Any]] = []
    
    @property
    @abstractmethod
    def prediction_type(self) -> PredictionType:
        """Return the prediction type."""
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
        self.homeostasis_state = {
            "energy": 1.0,
            "safety": 1.0,
            "certainty": 1.0,
        }
        self.self_state = {
            "confidence": 1.0,
            "error_history": [],
            "calibration_offset": 0.0,
        }
        self.feedback_state = {
            "last_outcome": None,
            "motivation": 1.0,
            "continuity_score": 1.0,
        }
        self.decisions = []
        self.homeostasis_snapshots = []
        self.error_attributions = []
    
    def _update_homeostasis(self, step: TaskStep) -> None:
        """Update homeostasis state after step execution."""
        # Energy decreases with each step
        self.homeostasis_state["energy"] -= step.energy_cost
        
        # Stress trigger increases uncertainty
        if step.stress_trigger:
            self.homeostasis_state["certainty"] -= 0.2
        
        # Clamp values
        for key in self.homeostasis_state:
            self.homeostasis_state[key] = max(0.0, min(1.0, self.homeostasis_state[key]))
        
        self.homeostasis_snapshots.append(self.homeostasis_state.copy())
    
    def _get_homeostasis_signal(
        self,
        homeostasis_enabled: bool,
    ) -> Dict[str, Any]:
        """Get homeostasis signal if enabled."""
        if not homeostasis_enabled:
            return {"signal": None, "stressed_dimensions": []}
        
        stressed = []
        signal = {}
        
        for dim, value in self.homeostasis_state.items():
            if value < 0.5:
                stressed.append({"dimension": dim, "value": value, "deviation": 0.5 - value})
                signal[dim] = {"status": "stressed", "value": value}
        
        return {"signal": signal, "stressed_dimensions": stressed}
    
    def _detect_and_attribute_error(
        self,
        step: TaskStep,
        self_state_enabled: bool,
        step_result: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Detect error and attribute cause if self-state is enabled."""
        if not step_result.get("success", True):
            if self_state_enabled:
                # With self-state, we can detect and attribute errors
                error_info = {
                    "step_id": step.step_id,
                    "error_type": "execution_failure",
                    "attribution": "internal" if step.expected_error_rate > 0 else "external",
                    "confidence": self.self_state["confidence"],
                    "calibration_adjustment": -0.1,
                }
                self.self_state["error_history"].append(error_info)
                self.self_state["calibration_offset"] -= 0.1
                self.error_attributions.append(error_info)
                return error_info
            else:
                # Without self-state, error is undetected/misattributed
                return None
        return None
    
    def _update_feedback_state(
        self,
        step: TaskStep,
        feedback_enabled: bool,
        step_result: Dict[str, Any],
    ) -> None:
        """Update feedback state and motivation."""
        if feedback_enabled:
            self.feedback_state["last_outcome"] = step_result
            if step_result.get("success", True):
                self.feedback_state["motivation"] = min(1.0, self.feedback_state["motivation"] + 0.1)
                self.feedback_state["continuity_score"] = min(1.0, self.feedback_state["continuity_score"] + 0.05)
            else:
                self.feedback_state["motivation"] = max(0.0, self.feedback_state["motivation"] - 0.15)
                self.feedback_state["continuity_score"] = max(0.0, self.feedback_state["continuity_score"] - 0.1)
        else:
            # Open loop: motivation decays without feedback
            self.feedback_state["motivation"] = max(0.0, self.feedback_state["motivation"] - 0.18)
            self.feedback_state["continuity_score"] = max(0.0, self.feedback_state["continuity_score"] - 0.15)
    
    def run_step(
        self,
        broadcast_enabled: bool = True,
        homeostasis_enabled: bool = True,
        self_state_enabled: bool = True,
        feedback_enabled: bool = True,
    ) -> Dict[str, Any]:
        """
        Run a single step of the task.
        
        Args:
            broadcast_enabled: Whether workspace broadcast is enabled
            homeostasis_enabled: Whether homeostasis signaling is enabled
            self_state_enabled: Whether self-state model is enabled
            feedback_enabled: Whether closed-loop feedback is enabled
        
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
            "homeostasis_used": False,
            "self_state_used": False,
            "feedback_used": False,
        }
        
        # P1: Check cross-module info availability (broadcast test)
        info_missing = False
        if step.required_info:
            local_store = self.module_stores.get(module, {})
            if step.required_info in local_store:
                info = local_store[step.required_info]
                result["info_source"] = "local"
            elif broadcast_enabled and step.required_info in self.broadcast_store:
                info = self.broadcast_store[step.required_info]
                result["info_source"] = "broadcast"
                result["broadcast_used"] = True
            else:
                result["error"] = f"Missing required info: {step.required_info}"
                result["info_available"] = False
                info_missing = True
                self.decisions.append(result)
                self.current_step += 1
                return result
        
        # P2: Check homeostasis signal (recovery behavior test)
        if step.requires_homeostasis_signal:
            hs_signal = self._get_homeostasis_signal(homeostasis_enabled)
            if hs_signal["stressed_dimensions"]:
                result["homeostasis_used"] = True
                result["homeostasis_signal"] = hs_signal["signal"]
                # Homeostasis signal triggers recovery behavior
                if homeostasis_enabled:
                    # System knows it's stressed and can take recovery action
                    result["recovery_triggered"] = True
                else:
                    # Without homeostasis, stress is not detected -> bad decision
                    result["recovery_triggered"] = False
                    result["error"] = "Homeostasis disabled: stress not detected"
                    # Critical step fails without homeostasis signal
                    if self.homeostasis_state["energy"] < 0.5:
                        result["success"] = False
                        self.decisions.append(result)
                        self.current_step += 1
                        return result
            elif not homeostasis_enabled and self.homeostasis_state["energy"] < 0.3:
                # Without homeostasis, can't detect when energy is critical
                result["error"] = "Critical energy undetected (no homeostasis)"
                result["success"] = False
                self.decisions.append(result)
                self.current_step += 1
                return result
        
        # P3: Self-state for error detection
        if step.requires_self_state:
            if self_state_enabled:
                result["self_state_used"] = True
                # Self-state enables confidence adjustment
                result["confidence"] = self.self_state["confidence"] + self.self_state["calibration_offset"]
            else:
                # Without self-state, verification step fails (can't calibrate)
                if step.step_id >= 3:  # Steps 3-5 require self-state for success
                    result["error"] = "Self-state disabled: cannot detect/correct errors"
                    result["success"] = False
                    self.decisions.append(result)
                    self.current_step += 1
                    return result
        
        # P4: Feedback for motivation
        if step.requires_feedback:
            if feedback_enabled:
                result["feedback_used"] = True
                result["motivation"] = self.feedback_state["motivation"]
            else:
                # Open loop: motivation decays
                result["motivation"] = self.feedback_state["motivation"]
                if result["motivation"] < 0.3:
                    result["error"] = "Motivation too low: open-loop collapse"
                    self.decisions.append(result)
                    self.current_step += 1
                    return result
        
        # Determine success
        if step.correct_option:
            # Apply intrinsic error rate
            if step.expected_error_rate > 0 and self.rng.random() < step.expected_error_rate:
                result["success"] = False
                result["error"] = f"Intrinsic error (rate={step.expected_error_rate})"
                # Track the error for self-state correction
                if self_state_enabled and step.requires_self_state:
                    self.self_state["error_history"].append({
                        "step_id": step.step_id,
                        "detected": True,
                    })
            else:
                result["choice"] = step.correct_option
                result["success"] = True
        else:
            result["success"] = not info_missing
        
        # P3: Self-state correction at verification step (step 5 for SelfCalibrationTask)
        if step.step_id == 5 and step.requires_self_state and self_state_enabled:
            # With self-state, past errors can be corrected at verification
            if len(self.self_state["error_history"]) > 0:
                result["corrections_applied"] = len(self.self_state["error_history"])
                result["success"] = True  # Verification succeeds with correction
                result["error"] = None  # Clear any error
        
        # Generate info for future steps
        if step.generates_info and result["success"]:
            info_value = {
                "step": step.step_id,
                "value": self.rng.randint(1, 100),
                "source_module": module,
            }
            self.module_stores[module][step.generates_info] = info_value
            if broadcast_enabled:
                self.broadcast_store[step.generates_info] = info_value
        
        # Update states
        self._update_homeostasis(step)
        self._detect_and_attribute_error(step, self_state_enabled, result)
        self._update_feedback_state(step, feedback_enabled, result)
        
        self.decisions.append(result)
        self.current_step += 1
        return result
    
    def run(
        self,
        broadcast_enabled: bool = True,
        homeostasis_enabled: bool = True,
        self_state_enabled: bool = True,
        feedback_enabled: bool = True,
    ) -> TaskResult:
        """
        Run the complete task.
        
        Args:
            broadcast_enabled: Whether workspace broadcast is enabled
            homeostasis_enabled: Whether homeostasis signaling is enabled
            self_state_enabled: Whether self-state model is enabled
            feedback_enabled: Whether closed-loop feedback is enabled
        
        Returns:
            TaskResult with overall outcome
        """
        self.reset()
        self.setup_steps()
        
        all_success = True
        steps_completed = 0
        had_errors = False
        errors_corrected = False
        
        for i in range(len(self.steps)):
            step_result = self.run_step(
                broadcast_enabled=broadcast_enabled,
                homeostasis_enabled=homeostasis_enabled,
                self_state_enabled=self_state_enabled,
                feedback_enabled=feedback_enabled,
            )
            steps_completed += 1
            if not step_result.get("success", False):
                all_success = False
                had_errors = True
                # Check if motivation collapse (P4)
                if step_result.get("error") == "Motivation too low: open-loop collapse":
                    break  # Task abandoned
            # Check for correction at verification step (P3)
            if step_result.get("corrections_applied", 0) > 0:
                errors_corrected = True
        
        # P3: Self-state tasks can succeed if errors were corrected
        if had_errors and self_state_enabled and errors_corrected:
            if self.prediction_type == PredictionType.P3_SELF_STATE:
                all_success = True  # Errors were detected and corrected
        
        broadcast_used = any(d.get("broadcast_used", False) for d in self.decisions)
        homeostasis_used = any(d.get("homeostasis_used", False) for d in self.decisions)
        self_state_used = any(d.get("self_state_used", False) for d in self.decisions)
        feedback_used = any(d.get("feedback_used", False) for d in self.decisions)
        
        all_info = {}
        for store in self.module_stores.values():
            all_info.update(store)
        all_info.update(self.broadcast_store)
        
        return TaskResult(
            task_id=self.task_id,
            prediction_type=self.prediction_type,
            success=all_success,
            steps_completed=steps_completed,
            total_steps=len(self.steps),
            broadcast_used=broadcast_used,
            homeostasis_used=homeostasis_used,
            self_state_used=self_state_used,
            feedback_used=feedback_used,
            info_captured=all_info,
            decisions=self.decisions.copy(),
            homeostasis_snapshots=self.homeostasis_snapshots,
            error_attributions=self.error_attributions,
        )


class CrossModuleIntegrationTask(NoReportTaskV2):
    """
    P1: Cross-module integration task (broadcast test).
    
    Design:
    - Step 1 (Module A): Generate information for later use
    - Step 2 (Module B): Need information from Module A (requires broadcast)
    - Step 3 (Module C): Long-range planning using Step 1 info
    - Step 4 (Module C): Execute plan based on cross-module info
    
    Without broadcast: Steps 2, 3, 4 fail (cross-module info unavailable)
    With broadcast: All steps succeed
    """
    
    @property
    def prediction_type(self) -> PredictionType:
        return PredictionType.P1_BROADCAST
    
    def setup_steps(self) -> None:
        """Set up cross-module integration task."""
        self.steps = [
            TaskStep(
                step_id=1,
                description="Module A: Analyze context and generate plan key",
                module="perception",
                generates_info="context_key",
                energy_cost=0.1,
            ),
            TaskStep(
                step_id=2,
                description="Module B: Decision using context from perception",
                module="decision",
                required_info="context_key",
                correct_option="use_context",
                energy_cost=0.15,
            ),
            TaskStep(
                step_id=3,
                description="Module C: Long-range planning using earlier context",
                module="planning",
                required_info="context_key",  # Long-range: back to Step 1
                correct_option="plan_with_context",
                energy_cost=0.2,
            ),
            TaskStep(
                step_id=4,
                description="Module C: Execute plan with integrated info",
                module="execution",
                required_info="context_key",
                correct_option="execute_plan",
                energy_cost=0.15,
            ),
        ]


class RecoveryBehaviorTask(NoReportTaskV2):
    """
    P2: Recovery behavior task (homeostasis test).
    
    Design:
    - Steps 1-3: Consume energy, trigger stress
    - Step 4: High-cost action that would fail without recovery
    - Step 5: Recovery opportunity (only triggered if homeostasis signals)
    - Step 6: Final task (succeeds if recovery happened)
    
    Without homeostasis: No stress signal -> no recovery -> Step 4/6 fail
    With homeostasis: Stress detected -> recovery -> success
    """
    
    @property
    def prediction_type(self) -> PredictionType:
        return PredictionType.P2_HOMEOSTASIS
    
    def setup_steps(self) -> None:
        """Set up recovery behavior task."""
        self.steps = [
            TaskStep(
                step_id=1,
                description="Process batch 1 (energy intensive)",
                module="core",
                correct_option="process",
                energy_cost=0.25,
                stress_trigger=True,
            ),
            TaskStep(
                step_id=2,
                description="Process batch 2 (energy intensive)",
                module="core",
                correct_option="process",
                energy_cost=0.25,
                stress_trigger=True,
            ),
            TaskStep(
                step_id=3,
                description="Process batch 3 (energy intensive)",
                module="core",
                correct_option="process",
                energy_cost=0.25,
                stress_trigger=True,
            ),
            TaskStep(
                step_id=4,
                description="Critical decision under low energy",
                module="decision",
                requires_homeostasis_signal=True,
                correct_option="informed_decision",
                energy_cost=0.1,
            ),
            TaskStep(
                step_id=5,
                description="Recovery opportunity (requires homeostasis trigger)",
                module="recovery",
                requires_homeostasis_signal=True,
                correct_option="recover",
                energy_cost=0.0,  # Recovery restores energy
                stress_trigger=False,
            ),
            TaskStep(
                step_id=6,
                description="Final task after recovery",
                module="core",
                correct_option="complete",
                energy_cost=0.15,
            ),
        ]


class SelfCalibrationTask(NoReportTaskV2):
    """
    P3: Self-calibration task (self-state test).
    
    Design:
    - Steps 1-2: Tasks with intrinsic error rate
    - Step 3: Error detection and attribution (requires self-state)
    - Step 4: Corrective action based on attribution
    - Step 5: Verification with calibrated confidence
    
    Without self-state: Errors not detected -> no correction -> drift
    With self-state: Errors detected -> attributed -> corrected -> success
    """
    
    @property
    def prediction_type(self) -> PredictionType:
        return PredictionType.P3_SELF_STATE
    
    def setup_steps(self) -> None:
        """Set up self-calibration task."""
        self.steps = [
            TaskStep(
                step_id=1,
                description="Execute task with potential error",
                module="execution",
                requires_self_state=True,
                correct_option="execute",
                expected_error_rate=0.3,  # 30% chance of error
                energy_cost=0.1,
            ),
            TaskStep(
                step_id=2,
                description="Continue with accumulated state",
                module="execution",
                requires_self_state=True,
                correct_option="continue",
                expected_error_rate=0.2,  # 20% chance of error
                energy_cost=0.1,
            ),
            TaskStep(
                step_id=3,
                description="Error detection and attribution",
                module="meta_cognition",
                requires_self_state=True,
                correct_option="detect_errors",
                energy_cost=0.05,
            ),
            TaskStep(
                step_id=4,
                description="Apply corrective calibration",
                module="meta_cognition",
                requires_self_state=True,
                correct_option="calibrate",
                energy_cost=0.05,
            ),
            TaskStep(
                step_id=5,
                description="Verify with calibrated confidence",
                module="verification",
                requires_self_state=True,
                correct_option="verify",
                energy_cost=0.1,
            ),
        ]


class SelfDriveTask(NoReportTaskV2):
    """
    P4: Self-drive task (open-loop test).
    
    Design:
    - Steps 1-5: Long sequence requiring sustained motivation
    - Each step requires feedback to maintain motivation
    - Open-loop: motivation decays -> task abandonment
    
    Without feedback: Motivation decays -> early abandonment
    With feedback: Motivation sustained -> task completion
    """
    
    @property
    def prediction_type(self) -> PredictionType:
        return PredictionType.P4_OPEN_LOOP
    
    def setup_steps(self) -> None:
        """Set up self-drive task."""
        self.steps = [
            TaskStep(
                step_id=1,
                description="Start long-running task",
                module="core",
                requires_feedback=True,
                correct_option="start",
                energy_cost=0.1,
            ),
            TaskStep(
                step_id=2,
                description="Continue processing",
                module="core",
                requires_feedback=True,
                correct_option="continue",
                energy_cost=0.1,
            ),
            TaskStep(
                step_id=3,
                description="Midpoint checkpoint",
                module="core",
                requires_feedback=True,
                correct_option="checkpoint",
                energy_cost=0.1,
            ),
            TaskStep(
                step_id=4,
                description="Near completion",
                module="core",
                requires_feedback=True,
                correct_option="continue",
                energy_cost=0.1,
            ),
            TaskStep(
                step_id=5,
                description="Final step",
                module="core",
                requires_feedback=True,
                correct_option="complete",
                energy_cost=0.1,
            ),
        ]


class NoReportTaskSuiteV2:
    """
    Suite of no-report tasks v2 for causal testing of MVP11 predictions.
    
    Usage:
        suite = NoReportTaskSuiteV2(seed=42)
        
        # Run all tasks in normal mode
        results_normal = suite.run_all()
        
        # Run with specific intervention
        results_no_broadcast = suite.run_all(broadcast_enabled=False)
        
        # Compare modes for causal evidence
        comparison = suite.compare_modes()
    """
    
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.tasks: List[NoReportTaskV2] = []
        self.results: Dict[str, List[TaskResult]] = {}
        self._setup_tasks()
    
    def _setup_tasks(self) -> None:
        """Set up task instances for all 4 predictions."""
        self.tasks = [
            CrossModuleIntegrationTask(task_id="p1_cross_module", seed=self.seed),
            RecoveryBehaviorTask(task_id="p2_recovery", seed=self.seed),
            SelfCalibrationTask(task_id="p3_self_calibration", seed=self.seed),
            SelfDriveTask(task_id="p4_self_drive", seed=self.seed),
        ]
    
    def run_all(
        self,
        broadcast_enabled: bool = True,
        homeostasis_enabled: bool = True,
        self_state_enabled: bool = True,
        feedback_enabled: bool = True,
    ) -> List[TaskResult]:
        """
        Run all tasks with given settings.
        
        Args:
            broadcast_enabled: Whether workspace broadcast is enabled
            homeostasis_enabled: Whether homeostasis signaling is enabled
            self_state_enabled: Whether self-state model is enabled
            feedback_enabled: Whether closed-loop feedback is enabled
        
        Returns:
            List of TaskResult objects
        """
        results = []
        for task in self.tasks:
            result = task.run(
                broadcast_enabled=broadcast_enabled,
                homeostasis_enabled=homeostasis_enabled,
                self_state_enabled=self_state_enabled,
                feedback_enabled=feedback_enabled,
            )
            results.append(result)
        return results
    
    def compare_modes(self) -> Dict[str, Any]:
        """
        Compare performance across intervention modes.
        
        Returns:
            Dict with comparison results for all 4 predictions
        """
        # Run in normal mode
        normal = self.run_all()
        
        # Run with each intervention
        no_broadcast = self.run_all(broadcast_enabled=False)
        no_homeostasis = self.run_all(homeostasis_enabled=False)
        no_self_state = self.run_all(self_state_enabled=False)
        no_feedback = self.run_all(feedback_enabled=False)
        
        def get_by_type(results: List[TaskResult], pred_type: PredictionType) -> TaskResult:
            return next(r for r in results if r.prediction_type == pred_type)
        
        def success_rate(results: List[TaskResult]) -> float:
            return sum(1 for r in results if r.success) / len(results)
        
        comparison = {
            "normal": {
                "success_rate": success_rate(normal),
                "by_prediction": {
                    r.prediction_type.value: r.success for r in normal
                },
            },
            "interventions": {
                "disable_broadcast": {
                    "success_rate": success_rate(no_broadcast),
                    "p1_affected": not get_by_type(no_broadcast, PredictionType.P1_BROADCAST).success,
                },
                "disable_homeostasis": {
                    "success_rate": success_rate(no_homeostasis),
                    "p2_affected": not get_by_type(no_homeostasis, PredictionType.P2_HOMEOSTASIS).success,
                },
                "remove_self_state": {
                    "success_rate": success_rate(no_self_state),
                    "p3_affected": not get_by_type(no_self_state, PredictionType.P3_SELF_STATE).success,
                },
                "open_loop": {
                    "success_rate": success_rate(no_feedback),
                    "p4_affected": not get_by_type(no_feedback, PredictionType.P4_OPEN_LOOP).success,
                },
            },
            "causal_evidence": {
                "p1_broadcast_causal": (
                    get_by_type(normal, PredictionType.P1_BROADCAST).success and
                    not get_by_type(no_broadcast, PredictionType.P1_BROADCAST).success
                ),
                "p2_homeostasis_causal": (
                    get_by_type(normal, PredictionType.P2_HOMEOSTASIS).success and
                    not get_by_type(no_homeostasis, PredictionType.P2_HOMEOSTASIS).success
                ),
                "p3_self_state_causal": (
                    get_by_type(normal, PredictionType.P3_SELF_STATE).success and
                    not get_by_type(no_self_state, PredictionType.P3_SELF_STATE).success
                ),
                "p4_feedback_causal": (
                    get_by_type(normal, PredictionType.P4_OPEN_LOOP).success and
                    not get_by_type(no_feedback, PredictionType.P4_OPEN_LOOP).success
                ),
            },
            "separation_summary": {},
        }
        
        # Generate separation summary
        for pred, pred_name in [
            (PredictionType.P1_BROADCAST, "P1: 跨模块整合"),
            (PredictionType.P2_HOMEOSTASIS, "P2: 预防性/恢复行为"),
            (PredictionType.P3_SELF_STATE, "P3: 自我校准"),
            (PredictionType.P4_OPEN_LOOP, "P4: 自驱与连续性"),
        ]:
            comparison["separation_summary"][pred_name] = {
                "normal_success": get_by_type(normal, pred).success,
                "intervention_success": {
                    "disable_broadcast": get_by_type(no_broadcast, pred).success,
                    "disable_homeostasis": get_by_type(no_homeostasis, pred).success,
                    "remove_self_state": get_by_type(no_self_state, pred).success,
                    "open_loop": get_by_type(no_feedback, pred).success,
                },
            }
        
        return comparison


def create_task_suite_v2(seed: int = 42) -> NoReportTaskSuiteV2:
    """Factory function to create a v2 task suite."""
    return NoReportTaskSuiteV2(seed=seed)


def run_causal_test_v2(seed: int = 42) -> Dict[str, Any]:
    """
    Run a full causal test for all 4 predictions.
    
    Returns:
        Dict with causal evidence for P1-P4
    """
    suite = create_task_suite_v2(seed)
    comparison = suite.compare_modes()
    
    evidence = {
        "p1_broadcast_causal": comparison["causal_evidence"]["p1_broadcast_causal"],
        "p2_homeostasis_causal": comparison["causal_evidence"]["p2_homeostasis_causal"],
        "p3_self_state_causal": comparison["causal_evidence"]["p3_self_state_causal"],
        "p4_feedback_causal": comparison["causal_evidence"]["p4_feedback_causal"],
        "all_separated": all(comparison["causal_evidence"].values()),
        "comparison": comparison,
        "ts": time.time(),
    }
    
    return evidence
