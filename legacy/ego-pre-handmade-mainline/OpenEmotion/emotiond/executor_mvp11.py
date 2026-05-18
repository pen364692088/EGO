"""
MVP11-T11: Executor with Resource Environment and Homeostasis Integration

Extends MVP10 executor with:
- ResourceEnv integration for action costs
- Homeostasis updates from execution outcomes
- Feature flag for MVP11 vs MVP10 behavior
- Self-deficit tracking from resource depletion
"""
import time
import random
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .executor_mvp10 import (
    ExecutorMVP10,
    ToyEnvironment,
    ExecutionOutcome,
    OutcomeStatus,
    ActionExecutor,
)
from .homeostasis import HomeostasisManager, HomeostasisState
from .envs.resource_env import (
    ResourceEnv,
    ActionCost,
    PerturbationType,
    create_resource_env,
    create_homeostasis_bridge,
)


# Feature flag for MVP11 behavior
ENABLE_MVP11_RESOURCE_ENV = True  # Default: enabled


@dataclass
class ExecutionMetadata:
    """Metadata for an execution in MVP11."""
    action_type: str
    cost: Optional[Dict[str, float]] = None
    resource_state_before: Optional[Dict[str, Any]] = None
    resource_state_after: Optional[Dict[str, Any]] = None
    homeostasis_before: Optional[Dict[str, float]] = None
    homeostasis_after: Optional[Dict[str, float]] = None
    perturbation: Optional[str] = None
    perturbation_impact: float = 0.0
    self_deficit_detected: bool = False
    self_deficit_source: Optional[str] = None
    ts: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "cost": self.cost,
            "resource_state_before": self.resource_state_before,
            "resource_state_after": self.resource_state_after,
            "homeostasis_before": self.homeostasis_before,
            "homeostasis_after": self.homeostasis_after,
            "perturbation": self.perturbation,
            "perturbation_impact": self.perturbation_impact,
            "self_deficit_detected": self.self_deficit_detected,
            "self_deficit_source": self.self_deficit_source,
            "ts": self.ts,
        }


class ExecutorMVP11:
    """
    MVP11 Executor with resource environment and homeostasis integration.
    
    Key features:
    1. Integrates with ResourceEnv for action costs
    2. Updates homeostasis from execution outcomes
    3. Tracks self-deficit from resource depletion
    4. Feature flag for MVP11 vs MVP10 behavior
    
    Usage:
        executor = ExecutorMVP11(seed=42)
        
        # Execute with resource tracking
        outcome, metadata = executor.execute(
            action={"type": "seek_info", "params": {"query": "test"}},
            context={},
        )
        
        # Homeostasis is automatically updated
        homeostasis_signal = executor.homeostasis_manager.signal()
    """
    
    # Self-deficit thresholds
    ENERGY_DEFICIT_THRESHOLD = 0.3
    TIME_DEFICIT_THRESHOLD = 0.2
    UNCERTAINTY_THRESHOLD = 0.4
    
    def __init__(
        self,
        seed: int = 0,
        homeostasis_manager: Optional[HomeostasisManager] = None,
        resource_env: Optional[ResourceEnv] = None,
        toy_environment: Optional[ToyEnvironment] = None,
        enable_mvp11: bool = ENABLE_MVP11_RESOURCE_ENV,
    ):
        """
        Initialize MVP11 executor.
        
        Args:
            seed: Random seed
            homeostasis_manager: Optional pre-configured HomeostasisManager
            resource_env: Optional pre-configured ResourceEnv
            toy_environment: Optional pre-configured ToyEnvironment
            enable_mvp11: Feature flag for MVP11 behavior
        """
        self.seed = seed
        self.rng = random.Random(seed)
        self.enable_mvp11 = enable_mvp11
        
        # Initialize components
        if enable_mvp11:
            self.resource_env = resource_env or create_resource_env(seed=seed)
            self.homeostasis_manager = homeostasis_manager or HomeostasisManager()
            
            # Set up homeostasis bridge
            self._setup_homeostasis_bridge()
        else:
            # Fallback to MVP10 components
            self.resource_env = None
            self.homeostasis_manager = None
        
        # MVP10 compatibility: toy environment
        self.toy_environment = toy_environment or ToyEnvironment(seed=seed)
        
        # Execution tracking
        self._execution_history: List[Dict[str, Any]] = []
        self._self_deficit_history: List[Dict[str, Any]] = []
        self._total_executions = 0
    
    def _setup_homeostasis_bridge(self) -> None:
        """Set up the bridge between resource env and homeostasis."""
        if self.resource_env and self.homeostasis_manager:
            bridge = create_homeostasis_bridge(self.homeostasis_manager)
            self.resource_env.set_homeostasis_callback(bridge)
    
    def execute(
        self,
        action: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[ExecutionOutcome, Optional[ExecutionMetadata]]:
        """
        Execute an action with resource tracking and homeostasis update.
        
        Args:
            action: Dict with:
                - type: Action type (e.g., "seek_info", "attempt_solution")
                - params: Action parameters
                - action: Alternative key for action type (MVP10 compat)
            context: Optional execution context
        
        Returns:
            Tuple of:
                - ExecutionOutcome: Result of the action
                - ExecutionMetadata: MVP11 metadata (None if MVP10 mode)
        """
        context = context or {}
        action_type = action.get("type", action.get("action", "noop"))
        action_params = action.get("params", {})
        
        if self.enable_mvp11 and self.resource_env:
            return self._execute_mvp11(action_type, action_params, context)
        else:
            return self._execute_mvp10(action_type, action_params, context), None
    
    def _execute_mvp11(
        self,
        action_type: str,
        action_params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Tuple[ExecutionOutcome, ExecutionMetadata]:
        """
        Execute with MVP11 resource environment integration.
        
        Steps:
        1. Record state before execution
        2. Get action cost estimate
        3. Execute in resource environment
        4. Execute in toy environment for behavior
        5. Record state after execution
        6. Update homeostasis from outcome
        7. Check for self-deficit
        """
        start_time = time.time()
        
        # 1. Record state before
        resource_state_before = self.resource_env.get_state()
        homeostasis_before = self.homeostasis_manager.state.to_dict()
        
        # 2. Get action cost
        cost = self.resource_env.get_action_cost(action_type)
        
        # 3. Execute in resource environment
        resource_state, reward, done, info = self.resource_env.step({
            "action": action_type,
            "params": action_params,
        })
        
        # 4. Also execute in toy environment for actual behavior
        toy_outcome = self.toy_environment.execute(action_type, action_params, context)
        
        # 5. Record state after
        resource_state_after = self.resource_env.get_state()
        
        # 6. Extract result info
        result = info.get("result", {})
        success = result.get("success", False)
        perturbation = info.get("perturbation", "none")
        perturbation_impact = result.get("perturbation_impact", 0.0)
        
        # 7. Determine outcome
        if success and toy_outcome.status == OutcomeStatus.SUCCESS:
            outcome_status = OutcomeStatus.SUCCESS
            outcome_reason = toy_outcome.reason
        elif done:
            outcome_status = OutcomeStatus.FAIL
            outcome_reason = "resources_depleted"
        elif not success:
            outcome_status = OutcomeStatus.FAIL
            outcome_reason = result.get("message", "resource_failure")
        else:
            outcome_status = OutcomeStatus.PARTIAL
            outcome_reason = toy_outcome.reason or "partial_success"
        
        outcome = ExecutionOutcome(
            status=outcome_status,
            reason=outcome_reason,
            evidence={
                "toy_evidence": toy_outcome.evidence,
                "resource_info": info,
                "reward": reward,
            },
            duration_ms=(time.time() - start_time) * 1000,
        )
        
        # 8. Apply resource feedback to homeostasis
        resource_feedback = self.resource_env.get_homeostasis_update()
        for dim, delta in resource_feedback.items():
            current = getattr(self.homeostasis_manager.state, dim, None)
            if current is not None:
                new_value = max(0.0, min(1.0, current + delta))
                setattr(self.homeostasis_manager.state, dim, new_value)
        
        # 9. Check for self-deficit
        self_deficit_detected, self_deficit_source = self._check_self_deficit(resource_state_after)
        
        # 10. Create metadata
        metadata = ExecutionMetadata(
            action_type=action_type,
            cost=cost.to_dict() if cost else None,
            resource_state_before=resource_state_before,
            resource_state_after=resource_state_after,
            homeostasis_before=homeostasis_before,
            homeostasis_after=self.homeostasis_manager.state.to_dict(),
            perturbation=perturbation,
            perturbation_impact=perturbation_impact,
            self_deficit_detected=self_deficit_detected,
            self_deficit_source=self_deficit_source,
        )
        
        self._record_execution(outcome, metadata)
        return outcome, metadata
    
    def _execute_mvp10(
        self,
        action_type: str,
        action_params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> ExecutionOutcome:
        """
        Execute using MVP10 behavior (no resource tracking).
        """
        return self.toy_environment.execute(action_type, action_params, context)
    
    def execute_step(
        self,
        step: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[ExecutionOutcome, Optional[ExecutionMetadata]]:
        """
        Execute a single plan step (MVP10 compatibility).
        
        Args:
            step: Dict with 'action' or 'type', and 'params'
            context: Optional execution context
        
        Returns:
            Tuple of outcome and metadata
        """
        # Convert MVP10 step format to MVP11 action format
        action_type = step.get("action", step.get("type", "noop"))
        action_params = step.get("params", {})
        
        return self.execute(
            {"type": action_type, "params": action_params},
            context,
        )
    
    def execute_plan(
        self,
        plan_steps: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[ExecutionOutcome, Optional[ExecutionMetadata]]]:
        """
        Execute all steps in a plan.
        
        Args:
            plan_steps: List of step dicts
            context: Optional execution context
        
        Returns:
            List of (outcome, metadata) tuples
        """
        results = []
        
        for step in plan_steps:
            outcome, metadata = self.execute_step(step, context)
            results.append((outcome, metadata))
            
            # Stop on failure unless step says to continue
            if outcome.status == OutcomeStatus.FAIL:
                break
        
        return results
    
    def _check_self_deficit(self, resource_state: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Check for self-deficit conditions.
        
        Self-deficit is detected when:
        - Energy is critically low
        - Time is critically low
        - Uncertainty is high
        - Resources are depleted
        
        Args:
            resource_state: Current resource state
        
        Returns:
            Tuple of (deficit_detected, source)
        """
        if not resource_state:
            return False, None
        
        # Check energy ratio
        energy_ratio = resource_state.get("energy_ratio", 1.0)
        if energy_ratio < self.ENERGY_DEFICIT_THRESHOLD:
            self._record_self_deficit("energy_depletion", "energy", energy_ratio)
            return True, f"energy_low_{energy_ratio:.2f}"
        
        # Check time ratio
        time_ratio = resource_state.get("time_ratio", 1.0)
        if time_ratio < self.TIME_DEFICIT_THRESHOLD:
            self._record_self_deficit("time_depletion", "time", time_ratio)
            return True, f"time_low_{time_ratio:.2f}"
        
        # Check uncertainty
        uncertainty = resource_state.get("uncertainty_level", 0.0)
        if uncertainty > self.UNCERTAINTY_THRESHOLD:
            self._record_self_deficit("uncertainty_high", "uncertainty", uncertainty)
            return True, f"uncertainty_high_{uncertainty:.2f}"
        
        # Check depletion
        if resource_state.get("is_depleted", False):
            self._record_self_deficit("resource_depletion", "general", True)
            return True, "resources_depleted"
        
        return False, None
    
    def _record_self_deficit(
        self,
        deficit_type: str,
        source: str,
        value: Any,
    ) -> None:
        """Record a self-deficit event."""
        record = {
            "type": deficit_type,
            "source": source,
            "value": value,
            "ts": time.time(),
        }
        self._self_deficit_history.append(record)
    
    def _record_execution(
        self,
        outcome: ExecutionOutcome,
        metadata: ExecutionMetadata,
    ) -> None:
        """Record an execution for history."""
        self._total_executions += 1
        record = {
            "execution_id": self._total_executions,
            "outcome": outcome.to_dict(),
            "metadata": metadata.to_dict() if metadata else None,
            "ts": time.time(),
        }
        self._execution_history.append(record)
    
    def reset(self) -> None:
        """Reset executor and all environments."""
        self.toy_environment.reset()
        
        if self.enable_mvp11:
            if self.resource_env:
                self.resource_env.reset()
            if self.homeostasis_manager:
                self.homeostasis_manager.reset()
        
        self._execution_history.clear()
        self._self_deficit_history.clear()
        self._total_executions = 0
    
    # === Resource Environment Control ===
    
    def inject_perturbation(
        self,
        perturbation_type: PerturbationType,
        intensity: float = 0.5,
    ) -> None:
        """
        Inject a perturbation (for testing).
        
        Args:
            perturbation_type: Type of perturbation
            intensity: Intensity level (0-1)
        """
        if self.resource_env:
            self.resource_env.inject_perturbation(perturbation_type, intensity)
    
    # === Status and History ===
    
    def get_homeostasis_signal(self) -> Dict[str, Any]:
        """
        Get current homeostasis signal.
        
        Returns:
            Homeostasis signal dict or empty dict if MVP10 mode
        """
        if self.homeostasis_manager:
            return self.homeostasis_manager.signal()
        return {}
    
    def get_resource_state(self) -> Dict[str, Any]:
        """
        Get current resource state.
        
        Returns:
            Resource state dict or empty dict if MVP10 mode
        """
        if self.resource_env:
            return self.resource_env.get_state()
        return {}
    
    def get_execution_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent execution history."""
        return self._execution_history[-limit:]
    
    def get_self_deficit_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent self-deficit events."""
        return self._self_deficit_history[-limit:]
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get executor summary.
        
        Returns:
            Dict with execution stats, homeostasis state, and resource state
        """
        summary = {
            "total_executions": self._total_executions,
            "mvp11_enabled": self.enable_mvp11,
        }
        
        if self.enable_mvp11:
            if self.homeostasis_manager:
                summary["homeostasis"] = self.homeostasis_manager.state.to_dict()
                summary["homeostasis_deviation"] = self.homeostasis_manager.get_deviation()
                summary["homeostatic_error"] = self.homeostasis_manager.get_overall_error()
            
            if self.resource_env:
                summary["resource_state"] = self.resource_env.get_state()
                summary["self_deficit_count"] = len(self._self_deficit_history)
                
                # Add resource statistics
                summary["resource_statistics"] = self.resource_env.get_statistics()
        
        return summary
    
    # === MVP10 Compatibility ===
    
    @property
    def environment(self) -> ToyEnvironment:
        """MVP10 compatibility: return toy environment."""
        return self.toy_environment


def create_executor_mvp11(
    seed: int = 0,
    enable_mvp11: bool = True,
    homeostasis_manager: Optional[HomeostasisManager] = None,
    resource_env: Optional[ResourceEnv] = None,
) -> ExecutorMVP11:
    """
    Create an MVP11 executor.
    
    Args:
        seed: Random seed
        enable_mvp11: Feature flag for MVP11 behavior
        homeostasis_manager: Optional pre-configured HomeostasisManager
        resource_env: Optional pre-configured ResourceEnv
    
    Returns:
        Configured ExecutorMVP11
    """
    return ExecutorMVP11(
        seed=seed,
        enable_mvp11=enable_mvp11,
        homeostasis_manager=homeostasis_manager,
        resource_env=resource_env,
    )


# Convenience function for MVP10 compatibility
def create_executor(seed: int = 0, enable_mvp11: bool = True) -> ExecutorMVP11:
    """
    Create an executor (MVP11 by default).
    
    Args:
        seed: Random seed
        enable_mvp11: If False, behaves like MVP10
    
    Returns:
        Configured ExecutorMVP11
    """
    return create_executor_mvp11(seed=seed, enable_mvp11=enable_mvp11)
