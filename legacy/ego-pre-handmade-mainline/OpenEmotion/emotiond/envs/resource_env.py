"""
MVP11-T10: Resource Environment Module

Closed-loop resource sandbox with:
- Action costs (time/energy/risk)
- Environment perturbations (tool failure/latency/spike tasks)
- Integration with homeostasis system

This module simulates a resource-constrained environment where each action
has costs and the environment can introduce perturbations that affect
action outcomes.
"""
import time
import random
import math
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class PerturbationType(str, Enum):
    """Types of environment perturbations."""
    TOOL_FAILURE = "tool_failure"
    LATENCY_SPIKE = "latency_spike"
    SPIKE_TASK = "spike_task"
    RESOURCE_DRAIN = "resource_drain"
    UNCERTAINTY_INCREASE = "uncertainty_increase"
    NONE = "none"


@dataclass
class ActionCost:
    """Cost structure for an action."""
    time_cost: float = 0.1  # Time units consumed
    energy_cost: float = 0.1  # Energy units consumed
    risk_level: float = 0.1  # Risk of failure (0-1)
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "time_cost": self.time_cost,
            "energy_cost": self.energy_cost,
            "risk_level": self.risk_level,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "ActionCost":
        return cls(
            time_cost=data.get("time_cost", 0.1),
            energy_cost=data.get("energy_cost", 0.1),
            risk_level=data.get("risk_level", 0.1),
        )


@dataclass
class ActionResult:
    """Result of an action execution in the resource environment."""
    success: bool
    actual_cost: ActionCost
    perturbation: PerturbationType
    perturbation_impact: float  # 0-1, how much perturbation affected outcome
    latency_ms: float
    message: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "actual_cost": self.actual_cost.to_dict(),
            "perturbation": self.perturbation.value,
            "perturbation_impact": round(self.perturbation_impact, 4),
            "latency_ms": round(self.latency_ms, 4),
            "message": self.message,
            "evidence": self.evidence,
            "ts": self.ts,
        }


@dataclass
class ResourceConfig:
    """Configuration for ResourceEnv."""
    # Resource limits
    max_time: float = 100.0
    max_energy: float = 100.0
    initial_time: float = 100.0
    initial_energy: float = 100.0
    
    # Perturbation probabilities
    tool_failure_prob: float = 0.05
    latency_spike_prob: float = 0.1
    spike_task_prob: float = 0.05
    resource_drain_prob: float = 0.03
    uncertainty_increase_prob: float = 0.02
    
    # Perturbation magnitudes
    latency_spike_multiplier: float = 3.0  # 3x normal latency
    resource_drain_amount: float = 10.0
    spike_task_cost_multiplier: float = 2.0
    uncertainty_increase_amount: float = 0.1
    
    # Recovery rates
    energy_recovery_rate: float = 0.1  # Per step
    
    # Random seed
    seed: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_time": self.max_time,
            "max_energy": self.max_energy,
            "initial_time": self.initial_time,
            "initial_energy": self.initial_energy,
            "tool_failure_prob": self.tool_failure_prob,
            "latency_spike_prob": self.latency_spike_prob,
            "spike_task_prob": self.spike_task_prob,
            "resource_drain_prob": self.resource_drain_prob,
            "uncertainty_increase_prob": self.uncertainty_increase_prob,
            "latency_spike_multiplier": self.latency_spike_multiplier,
            "resource_drain_amount": self.resource_drain_amount,
            "spike_task_cost_multiplier": self.spike_task_cost_multiplier,
            "uncertainty_increase_amount": self.uncertainty_increase_amount,
            "energy_recovery_rate": self.energy_recovery_rate,
            "seed": self.seed,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResourceConfig":
        return cls(
            max_time=data.get("max_time", 100.0),
            max_energy=data.get("max_energy", 100.0),
            initial_time=data.get("initial_time", 100.0),
            initial_energy=data.get("initial_energy", 100.0),
            tool_failure_prob=data.get("tool_failure_prob", 0.05),
            latency_spike_prob=data.get("latency_spike_prob", 0.1),
            spike_task_prob=data.get("spike_task_prob", 0.05),
            resource_drain_prob=data.get("resource_drain_prob", 0.03),
            uncertainty_increase_prob=data.get("uncertainty_increase_prob", 0.02),
            latency_spike_multiplier=data.get("latency_spike_multiplier", 3.0),
            resource_drain_amount=data.get("resource_drain_amount", 10.0),
            spike_task_cost_multiplier=data.get("spike_task_cost_multiplier", 2.0),
            uncertainty_increase_amount=data.get("uncertainty_increase_amount", 0.1),
            energy_recovery_rate=data.get("energy_recovery_rate", 0.1),
            # time_recovery_rate removed - time doesn't recover in this model
            seed=data.get("seed"),
        )


# Default action costs
DEFAULT_ACTION_COSTS: Dict[str, ActionCost] = {
    "seek_info": ActionCost(time_cost=0.1, energy_cost=0.1, risk_level=0.1),
    "attempt_solution": ActionCost(time_cost=0.3, energy_cost=0.3, risk_level=0.3),
    "run_check": ActionCost(time_cost=0.15, energy_cost=0.1, risk_level=0.1),
    "apply_fix": ActionCost(time_cost=0.25, energy_cost=0.25, risk_level=0.2),
    "commit_progress": ActionCost(time_cost=0.1, energy_cost=0.05, risk_level=0.05),
    "reflect": ActionCost(time_cost=0.2, energy_cost=0.15, risk_level=0.0),
    "noop": ActionCost(time_cost=0.0, energy_cost=0.0, risk_level=0.0),
}


class ResourceEnv:
    """
    Closed-loop resource sandbox with action costs and environment perturbations.
    
    This environment simulates resource constraints and random perturbations
    that can affect action outcomes. It integrates with the homeostasis system
    to update internal state based on action costs and outcomes.
    
    Key Features:
    - Each action has time/energy/risk costs
    - Environment can introduce perturbations (failures, latency, etc.)
    - Tracks resource state and history
    - Provides integration hooks for homeostasis
    
    Usage:
        env = ResourceEnv(config={})
        state = env.reset()
        
        # Execute an action
        result, reward, done, info = env.step({
            "action": "seek_info",
            "params": {"query": "example"}
        })
        
        # Get current state
        state = env.get_state()
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the resource environment.
        
        Args:
            config: Configuration dict (will be converted to ResourceConfig)
        """
        config = config or {}
        self.config = ResourceConfig.from_dict(config)
        
        # Initialize RNG
        self.rng = random.Random(self.config.seed)
        
        # Resource state
        self.time_remaining = self.config.initial_time
        self.energy_remaining = self.config.initial_energy
        
        # Perturbation state
        self.current_perturbation = PerturbationType.NONE
        self.perturbation_intensity = 0.0
        self.uncertainty_level = 0.0
        
        # Action costs
        self.action_costs = DEFAULT_ACTION_COSTS.copy()
        
        # History tracking
        self._step_count = 0
        self._action_history: List[Dict[str, Any]] = []
        self._perturbation_history: List[Dict[str, Any]] = []
        self._cost_history: List[Dict[str, Any]] = []
        
        # Integration hooks
        self._homeostasis_callback: Optional[callable] = None
        self._last_outcome: Optional[Dict[str, Any]] = None
        self._forced_perturbation: Optional[Tuple[PerturbationType, float]] = None  # For reliable injection
    
    def step(self, action: Dict[str, Any]) -> Tuple[Dict[str, Any], float, bool, Dict[str, Any]]:
        """
        Execute an action in the environment.
        
        Args:
            action: Dict with:
                - action: Action name (str)
                - params: Optional parameters (dict)
                - custom_cost: Optional custom ActionCost
        
        Returns:
            Tuple of (state, reward, done, info):
                - state: Current environment state
                - reward: Reward signal (negative cost)
                - done: Whether episode is terminated
                - info: Additional information
        """
        self._step_count += 1
        start_time = time.time()
        
        action_name = action.get("action", "noop")
        params = action.get("params", {})
        custom_cost = action.get("custom_cost")
        
        # Get action cost
        base_cost = custom_cost or self.action_costs.get(action_name, ActionCost())
        if isinstance(custom_cost, dict):
            base_cost = ActionCost.from_dict(custom_cost)
        
        # Sample perturbation (or use forced perturbation if injected)
        if hasattr(self, '_forced_perturbation') and self._forced_perturbation is not None:
            perturbation, perturbation_impact = self._forced_perturbation
            self._forced_perturbation = None  # Clear after use
        else:
            perturbation, perturbation_impact = self._sample_perturbation()
        
        # CRITICAL: Write back to current_perturbation for state consistency
        # This ensures get_state() and get_homeostasis_update() see the same perturbation
        self.current_perturbation = perturbation
        self.perturbation_intensity = perturbation_impact
        
        # Calculate actual cost with perturbation effects
        actual_cost = self._apply_perturbation_to_cost(base_cost, perturbation, perturbation_impact)
        
        # Check if we have enough resources
        can_execute = (
            self.time_remaining >= actual_cost.time_cost and
            self.energy_remaining >= actual_cost.energy_cost
        )
        
        # Determine success
        success = can_execute
        failure_reason = ""
        
        if can_execute:
            # Apply risk-based failure
            if self.rng.random() < actual_cost.risk_level:
                success = False
                failure_reason = "risk_failure"
            
            # Apply perturbation-specific effects
            if perturbation == PerturbationType.TOOL_FAILURE:
                if self.rng.random() < perturbation_impact:
                    success = False
                    failure_reason = "tool_failure"
            
            # Deduct resources
            if success:
                self.time_remaining -= actual_cost.time_cost
                self.energy_remaining -= actual_cost.energy_cost
            else:
                # Still deduct partial cost on failure
                self.time_remaining -= actual_cost.time_cost * 0.5
                self.energy_remaining -= actual_cost.energy_cost * 0.5
        else:
            failure_reason = "insufficient_resources"
        
        # Apply energy recovery
        self.energy_remaining = min(
            self.config.max_energy,
            self.energy_remaining + self.config.energy_recovery_rate
        )
        
        # Calculate latency
        base_latency = 100.0  # ms
        if perturbation == PerturbationType.LATENCY_SPIKE:
            latency = base_latency * self.config.latency_spike_multiplier
        else:
            latency = base_latency
        
        actual_latency = (time.time() - start_time) * 1000
        
        # Create result
        result = ActionResult(
            success=success,
            actual_cost=actual_cost,
            perturbation=perturbation,
            perturbation_impact=perturbation_impact,
            latency_ms=max(latency, actual_latency),
            message=failure_reason if not success else f"Action {action_name} completed",
            evidence={
                "action": action_name,
                "params": params,
                "step": self._step_count,
            },
        )
        
        # Calculate reward (negative cost)
        reward = -(
            actual_cost.time_cost / self.config.max_time +
            actual_cost.energy_cost / self.config.max_energy +
            actual_cost.risk_level * 0.5
        )
        if success:
            reward += 0.1  # Success bonus
        
        # Check termination
        done = (
            self.time_remaining <= 0 or
            self.energy_remaining <= 0
        )
        
        # Record history
        self._record_step(action, result, reward)
        
        # Update last outcome for homeostasis integration
        self._last_outcome = {
            "status": "success" if success else "fail",
            "reason": failure_reason if not success else None,
            "cost": actual_cost.to_dict(),
            "perturbation": perturbation.value,
        }
        
        # Trigger homeostasis callback if set
        if self._homeostasis_callback:
            self._homeostasis_callback(self._last_outcome)
        
        # Build info
        info = {
            "result": result.to_dict(),
            "perturbation": perturbation.value,
            "resources": {
                "time_remaining": self.time_remaining,
                "energy_remaining": self.energy_remaining,
            },
        }
        
        state = self.get_state()
        return state, reward, done, info
    
    def reset(self) -> Dict[str, Any]:
        """
        Reset the environment to initial state.
        
        Returns:
            Initial state dict
        """
        self.rng = random.Random(self.config.seed)
        self.time_remaining = self.config.initial_time
        self.energy_remaining = self.config.initial_energy
        self.current_perturbation = PerturbationType.NONE
        self.perturbation_intensity = 0.0
        self.uncertainty_level = 0.0
        
        self._step_count = 0
        self._action_history.clear()
        self._perturbation_history.clear()
        self._cost_history.clear()
        self._last_outcome = None
        self._forced_perturbation = None  # Clear forced perturbation on reset
        
        return self.get_state()
    
    def get_state(self) -> Dict[str, Any]:
        """
        Get current environment state.
        
        Returns:
            Dict with:
                - time_remaining: Time units left
                - energy_remaining: Energy units left
                - time_ratio: Time remaining as ratio [0,1]
                - energy_ratio: Energy remaining as ratio [0,1]
                - uncertainty_level: Current uncertainty [0,1]
                - step_count: Number of steps taken
                - is_depleted: Whether resources are critically low
        """
        time_ratio = self.time_remaining / self.config.max_time
        energy_ratio = self.energy_remaining / self.config.max_energy
        
        return {
            "time_remaining": self.time_remaining,
            "energy_remaining": self.energy_remaining,
            "time_ratio": time_ratio,
            "energy_ratio": energy_ratio,
            "uncertainty_level": self.uncertainty_level,
            "step_count": self._step_count,
            "is_depleted": time_ratio < 0.1 or energy_ratio < 0.1,
            "perturbation": self.current_perturbation.value,
            "perturbation_intensity": self.perturbation_intensity,
        }
    
    def set_homeostasis_callback(self, callback: callable) -> None:
        """
        Set a callback to update homeostasis on action outcomes.
        
        Args:
            callback: Function that takes an outcome dict
        """
        self._homeostasis_callback = callback
    
    def get_last_outcome(self) -> Optional[Dict[str, Any]]:
        """Get the last action outcome."""
        return self._last_outcome
    
    def get_action_cost(self, action_name: str) -> ActionCost:
        """Get the cost for a specific action."""
        return self.action_costs.get(action_name, ActionCost())
    
    def set_action_cost(self, action_name: str, cost: ActionCost) -> None:
        """Set a custom cost for an action."""
        self.action_costs[action_name] = cost
    
    def inject_perturbation(
        self,
        perturbation_type: PerturbationType,
        intensity: float = 0.5,
    ) -> None:
        """
        Manually inject a perturbation into the environment.
        
        This sets a forced perturbation that will be used in the next step() call,
        ensuring reliable injection for testing/science mode.
        
        Args:
            perturbation_type: Type of perturbation
            intensity: Intensity of perturbation [0,1]
        """
        # Set forced perturbation for next step
        self._forced_perturbation = (perturbation_type, intensity)
        
        # Also update current state for immediate visibility
        self.current_perturbation = perturbation_type
        self.perturbation_intensity = intensity
        
        # Apply immediate effects
        if perturbation_type == PerturbationType.RESOURCE_DRAIN:
            drain = self.config.resource_drain_amount * intensity
            self.energy_remaining = max(0, self.energy_remaining - drain)
        
        elif perturbation_type == PerturbationType.UNCERTAINTY_INCREASE:
            self.uncertainty_level = min(
                1.0,
                self.uncertainty_level + self.config.uncertainty_increase_amount * intensity
            )
    
    def get_homeostasis_update(self) -> Dict[str, float]:
        """
        Get homeostasis dimension updates based on current resource state.
        
        This maps resource states to homeostasis dimension deltas.
        
        Returns:
            Dict mapping homeostasis dimensions to delta values
        """
        state = self.get_state()
        updates = {}
        
        # Low energy → energy dimension decrease
        if state["energy_ratio"] < 0.3:
            deficit = 0.3 - state["energy_ratio"]
            updates["energy"] = -deficit * 0.5
        
        # Low time → safety dimension decrease (time pressure)
        if state["time_ratio"] < 0.2:
            deficit = 0.2 - state["time_ratio"]
            updates["safety"] = -deficit * 0.3
        
        # High uncertainty → certainty dimension decrease
        if self.uncertainty_level > 0.3:
            excess = self.uncertainty_level - 0.3
            updates["certainty"] = -excess * 0.4
        
        # Depletion → autonomy decrease
        if state["is_depleted"]:
            updates["autonomy"] = -0.1
        
        # Perturbation effects
        if self.current_perturbation == PerturbationType.TOOL_FAILURE:
            updates["certainty"] = updates.get("certainty", 0) - 0.05
        
        if self.current_perturbation == PerturbationType.LATENCY_SPIKE:
            updates["autonomy"] = updates.get("autonomy", 0) - 0.03
        
        return updates
    
    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent action history."""
        return self._action_history[-limit:]
    
    def get_perturbation_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent perturbation history."""
        return self._perturbation_history[-limit:]
    
    def get_cost_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent cost history."""
        return self._cost_history[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get environment statistics.
        
        Returns:
            Dict with success rate, avg cost, perturbation stats
        """
        if not self._action_history:
            return {
                "total_steps": 0,
                "success_rate": 0.0,
                "avg_time_cost": 0.0,
                "avg_energy_cost": 0.0,
                "avg_risk": 0.0,
                "perturbation_rate": 0.0,
            }
        
        total = len(self._action_history)
        successes = sum(1 for a in self._action_history if a.get("success", False))
        
        time_costs = [a.get("cost", {}).get("time_cost", 0) for a in self._action_history]
        energy_costs = [a.get("cost", {}).get("energy_cost", 0) for a in self._action_history]
        risks = [a.get("cost", {}).get("risk_level", 0) for a in self._action_history]
        
        perturbations = [
            a for a in self._action_history
            if a.get("perturbation", "none") != "none"
        ]
        
        return {
            "total_steps": total,
            "success_rate": successes / total if total > 0 else 0.0,
            "avg_time_cost": sum(time_costs) / total if total > 0 else 0.0,
            "avg_energy_cost": sum(energy_costs) / total if total > 0 else 0.0,
            "avg_risk": sum(risks) / total if total > 0 else 0.0,
            "perturbation_rate": len(perturbations) / total if total > 0 else 0.0,
            "resources_remaining": {
                "time": self.time_remaining,
                "energy": self.energy_remaining,
            },
        }
    
    # === Private Methods ===
    
    def _sample_perturbation(self) -> Tuple[PerturbationType, float]:
        """Sample a random perturbation based on probabilities."""
        r = self.rng.random()
        
        # Check each perturbation type
        if r < self.config.tool_failure_prob:
            return PerturbationType.TOOL_FAILURE, self.rng.uniform(0.3, 1.0)
        
        r -= self.config.tool_failure_prob
        if r < self.config.latency_spike_prob:
            return PerturbationType.LATENCY_SPIKE, self.rng.uniform(0.2, 0.8)
        
        r -= self.config.latency_spike_prob
        if r < self.config.spike_task_prob:
            return PerturbationType.SPIKE_TASK, self.rng.uniform(0.5, 1.0)
        
        r -= self.config.spike_task_prob
        if r < self.config.resource_drain_prob:
            return PerturbationType.RESOURCE_DRAIN, self.rng.uniform(0.3, 0.7)
        
        r -= self.config.resource_drain_prob
        if r < self.config.uncertainty_increase_prob:
            return PerturbationType.UNCERTAINTY_INCREASE, self.rng.uniform(0.1, 0.5)
        
        return PerturbationType.NONE, 0.0
    
    def _apply_perturbation_to_cost(
        self,
        base_cost: ActionCost,
        perturbation: PerturbationType,
        impact: float,
    ) -> ActionCost:
        """Apply perturbation effects to action cost."""
        time_cost = base_cost.time_cost
        energy_cost = base_cost.energy_cost
        risk_level = base_cost.risk_level
        
        if perturbation == PerturbationType.SPIKE_TASK:
            multiplier = 1.0 + (self.config.spike_task_cost_multiplier - 1.0) * impact
            time_cost *= multiplier
            energy_cost *= multiplier
        
        elif perturbation == PerturbationType.RESOURCE_DRAIN:
            # Increase energy cost
            energy_cost += self.config.resource_drain_amount * impact * 0.1
        
        elif perturbation == PerturbationType.UNCERTAINTY_INCREASE:
            # Increase risk
            risk_level = min(1.0, risk_level + self.config.uncertainty_increase_amount * impact)
        
        elif perturbation == PerturbationType.TOOL_FAILURE:
            # Increase risk of failure
            risk_level = min(1.0, risk_level + 0.2 * impact)
        
        return ActionCost(
            time_cost=round(time_cost, 4),
            energy_cost=round(energy_cost, 4),
            risk_level=round(risk_level, 4),
        )
    
    def _record_step(
        self,
        action: Dict[str, Any],
        result: ActionResult,
        reward: float,
    ) -> None:
        """Record step in history."""
        entry = {
            "step": self._step_count,
            "action": action.get("action", "noop"),
            "params": action.get("params", {}),
            "success": result.success,
            "cost": result.actual_cost.to_dict(),
            "perturbation": result.perturbation.value,
            "perturbation_impact": result.perturbation_impact,
            "reward": round(reward, 4),
            "ts": result.ts,
        }
        
        self._action_history.append(entry)
        
        if result.perturbation != PerturbationType.NONE:
            self._perturbation_history.append({
                "step": self._step_count,
                "perturbation": result.perturbation.value,
                "impact": result.perturbation_impact,
            })
        
        self._cost_history.append({
            "step": self._step_count,
            "action": action.get("action", "noop"),
            "cost": result.actual_cost.to_dict(),
        })


def create_resource_env(
    seed: Optional[int] = None,
    **kwargs,
) -> ResourceEnv:
    """
    Factory function to create a ResourceEnv.
    
    Args:
        seed: Random seed
        **kwargs: Additional config options
    
    Returns:
        ResourceEnv instance
    """
    config = {"seed": seed, **kwargs}
    return ResourceEnv(config=config)


# === Integration Helpers ===

def create_homeostasis_bridge(homeostasis_manager):
    """
    Create a bridge function to connect ResourceEnv to HomeostasisManager.
    
    Usage:
        from emotiond.homeostasis import HomeostasisManager
        from emotiond.envs.resource_env import create_homeostasis_bridge
        
        homeostasis = HomeostasisManager()
        env = ResourceEnv()
        
        bridge = create_homeostasis_bridge(homeostasis)
        env.set_homeostasis_callback(bridge)
    """
    def bridge(outcome: Dict[str, Any]) -> None:
        if homeostasis_manager is None:
            return
        
        # Convert to homeostasis update format
        update_outcome = {
            "status": outcome.get("status", "success"),
            "reason": outcome.get("reason"),
            "evidence": {
                "cost": outcome.get("cost", {}),
                "perturbation": outcome.get("perturbation"),
            },
        }
        
        homeostasis_manager.update_from_outcome(update_outcome)
    
    return bridge
