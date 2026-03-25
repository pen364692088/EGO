"""
MVP-10 T12: Interventions Module

Provides intervention mechanisms for causal evidence.
Interventions are used to isolate and test specific causal pathways.

Key intervention:
- freeze_valence: Locks valence to test its causal effect on behavior
  Same task with different initial valence → behavior difference minimized
  Used for causal evidence that valence affects behavior
"""
import time
import copy
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

# Import from legacy drives.py file (not drives/ directory)
# Use importlib to bypass package directory shadowing
import importlib.util
import os
_drives_spec = importlib.util.spec_from_file_location(
    "drives_legacy",
    os.path.join(os.path.dirname(__file__), "..", "drives.py")
)
_drives_legacy = importlib.util.module_from_spec(_drives_spec)
_drives_spec.loader.exec_module(_drives_legacy)
Drives = _drives_legacy.Drives
DriveType = _drives_legacy.DriveType
drives_from_valence = _drives_legacy.drives_from_valence
from emotiond.valence_policy import ValencePolicy, PolicyParams


class InterventionType(Enum):
    """Types of interventions available."""
    FREEZE_VALENCE = "freeze_valence"
    FREEZE_DRIVES = "freeze_drives"
    FREEZE_POLICY = "freeze_policy"
    INJECT_VALENCE = "inject_valence"
    INJECT_DRIVE = "inject_drive"
    CLAMP_DECISION = "clamp_decision"
    DISABLE_HOT = "disable_hot"  # T09: Disable HOT self-model influence
    DISABLE_BROADCAST = "disable_broadcast"  # T06: Disable workspace broadcast
    DISABLE_HOMEOSTASIS = "disable_homeostasis"  # MVP11-T06: Disable homeostasis signal generation
    FREEZE_HOMEOSTASIS = "freeze_homeostasis"  # MVP11-T06: Freeze homeostasis state
    # MVP11-T16: New interventions for M7 causal evidence
    FREEZE_PRECISION = "freeze_precision"  # Freeze EFE precision weights
    DISABLE_INFO_GAIN = "disable_info_gain"  # Set info_gain_weight to 0
    OPEN_LOOP = "open_loop"  # Actions don't affect future observations/costs
    REMOVE_SELF_STATE = "remove_self_state"  # Set self_state to constant/null
    ENABLE_CYCLE_PRIOR = "enable_cycle_prior"  # MVP11.4: enable runtime cycle prior


@dataclass
class InterventionConfig:
    """Configuration for an intervention."""
    intervention_type: InterventionType
    enabled: bool = True
    params: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    ts: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "intervention_type": self.intervention_type.value,
            "enabled": self.enabled,
            "params": self.params,
            "reason": self.reason,
            "ts": self.ts,
        }


@dataclass
class InterventionResult:
    """Result of applying an intervention."""
    success: bool
    intervention_type: InterventionType
    before: Dict[str, Any] = field(default_factory=dict)
    after: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    ts: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "intervention_type": self.intervention_type.value,
            "before": self.before,
            "after": self.after,
            "message": self.message,
            "ts": self.ts,
        }


class InterventionManager:
    """
    Manages interventions for causal testing.
    
    Interventions allow controlling specific variables to test
    causal relationships:
    - freeze_valence: Lock valence, test if behavior changes
    - freeze_drives: Lock drive levels
    - freeze_policy: Lock policy parameters
    
    Usage:
        manager = InterventionManager()
        manager.enable(InterventionType.FREEZE_VALENCE, {"valence": 0.5})
        
        # During tick loop:
        if manager.is_active(InterventionType.FREEZE_VALENCE):
            valence = manager.get_frozen_valence()
    """
    
    def __init__(self):
        self._active: Dict[InterventionType, InterventionConfig] = {}
        self._history: List[InterventionResult] = []
    
    def enable(
        self,
        intervention_type: InterventionType,
        params: Optional[Dict[str, Any]] = None,
        reason: str = "",
    ) -> InterventionResult:
        """
        Enable an intervention.
        
        Args:
            intervention_type: Type of intervention to enable
            params: Parameters for the intervention
            reason: Reason for enabling
        
        Returns:
            InterventionResult indicating success
        """
        config = InterventionConfig(
            intervention_type=intervention_type,
            enabled=True,
            params=params or {},
            reason=reason,
        )
        
        before = self._get_current_state(intervention_type)
        self._active[intervention_type] = config
        after = self._get_current_state(intervention_type)
        
        result = InterventionResult(
            success=True,
            intervention_type=intervention_type,
            before=before,
            after=after,
            message=f"Enabled {intervention_type.value}",
        )
        
        self._history.append(result)
        return result
    
    def disable(self, intervention_type: InterventionType) -> InterventionResult:
        """
        Disable an intervention.
        
        Args:
            intervention_type: Type of intervention to disable
        
        Returns:
            InterventionResult indicating success
        """
        before = self._get_current_state(intervention_type)
        
        if intervention_type in self._active:
            del self._active[intervention_type]
        
        after = self._get_current_state(intervention_type)
        
        result = InterventionResult(
            success=True,
            intervention_type=intervention_type,
            before=before,
            after=after,
            message=f"Disabled {intervention_type.value}",
        )
        
        self._history.append(result)
        return result
    
    def is_active(self, intervention_type: InterventionType) -> bool:
        """Check if an intervention is currently active."""
        return intervention_type in self._active
    
    def get_config(self, intervention_type: InterventionType) -> Optional[InterventionConfig]:
        """Get the config for an active intervention."""
        return self._active.get(intervention_type)
    
    def get_frozen_valence(self) -> Optional[float]:
        """
        Get the frozen valence value if FREEZE_VALENCE is active.
        
        Returns:
            Frozen valence value or None if not active
        """
        config = self._active.get(InterventionType.FREEZE_VALENCE)
        if config:
            return config.params.get("valence")
        return None
    
    def get_frozen_drives(self) -> Optional[Dict[DriveType, float]]:
        """
        Get the frozen drive levels if FREEZE_DRIVES is active.
        
        Returns:
            Dict of drive levels or None if not active
        """
        config = self._active.get(InterventionType.FREEZE_DRIVES)
        if config:
            levels = config.params.get("levels", {})
            return {DriveType(k): v for k, v in levels.items()}
        return None
    
    def get_frozen_policy(self) -> Optional[PolicyParams]:
        """
        Get the frozen policy params if FREEZE_POLICY is active.
        
        Returns:
            PolicyParams or None if not active
        """
        config = self._active.get(InterventionType.FREEZE_POLICY)
        if config:
            params = config.params.get("policy_params", {})
            return PolicyParams.from_dict(params)
        return None
    
    def is_hot_disabled(self) -> bool:
        """
        Check if HOT self-model is disabled.
        
        T09: When disabled, HOT does not affect arbitration.
        
        Returns:
            True if DISABLE_HOT is active
        """
        return self.is_active(InterventionType.DISABLE_HOT)
    
    def is_broadcast_disabled(self) -> bool:
        """
        Check if workspace broadcast is disabled.
        
        T06: When disabled, workspace candidates cannot cross modules.
        
        Returns:
            True if DISABLE_BROADCAST is active
        """
        return self.is_active(InterventionType.DISABLE_BROADCAST)
    
    def is_homeostasis_disabled(self) -> bool:
        """
        Check if homeostasis signal generation is disabled.
        
        MVP11-T06: When disabled, HomeostasisManager.signal() returns empty dict.
        
        Returns:
            True if DISABLE_HOMEOSTASIS is active
        """
        return self.is_active(InterventionType.DISABLE_HOMEOSTASIS)
    
    def is_homeostasis_frozen(self) -> bool:
        """
        Check if homeostasis state is frozen.
        
        MVP11-T06: When frozen, update_from_outcome() is a no-op.
        
        Returns:
            True if FREEZE_HOMEOSTASIS is active
        """
        return self.is_active(InterventionType.FREEZE_HOMEOSTASIS)
    
    def apply_intervention(
        self,
        valence: float,
        drives: Optional[Drives] = None,
        policy: Optional[ValencePolicy] = None,
    ) -> Dict[str, Any]:
        """
        Apply active interventions to the given state.
        
        Args:
            valence: Current valence (may be overridden)
            drives: Current Drives instance (may be overridden)
            policy: Current ValencePolicy instance (may be overridden)
        
        Returns:
            Dict with potentially modified valence, drives, policy_params
        """
        result = {
            "valence": valence,
            "drives": drives,
            "policy_params": None,
            "interventions_applied": [],
        }
        
        # Apply FREEZE_VALENCE
        if self.is_active(InterventionType.FREEZE_VALENCE):
            frozen = self.get_frozen_valence()
            if frozen is not None:
                result["valence"] = frozen
                result["interventions_applied"].append("freeze_valence")
        
        # Apply INJECT_VALENCE (higher priority than freeze)
        if self.is_active(InterventionType.INJECT_VALENCE):
            config = self.get_config(InterventionType.INJECT_VALENCE)
            if config and "valence" in config.params:
                result["valence"] = config.params["valence"]
                result["interventions_applied"].append("inject_valence")
        
        # Apply FREEZE_DRIVES
        if self.is_active(InterventionType.FREEZE_DRIVES) and drives:
            frozen_drives = self.get_frozen_drives()
            if frozen_drives:
                for dt, level in frozen_drives.items():
                    drives.set_level(dt, level, "freeze_drives_intervention")
                result["interventions_applied"].append("freeze_drives")
        
        # Apply INJECT_DRIVE
        if self.is_active(InterventionType.INJECT_DRIVE) and drives:
            config = self.get_config(InterventionType.INJECT_DRIVE)
            if config:
                drive_type = config.params.get("drive_type")
                level = config.params.get("level")
                if drive_type and level is not None:
                    dt = DriveType(drive_type)
                    drives.set_level(dt, level, "inject_drive_intervention")
                    result["interventions_applied"].append("inject_drive")
        
        # Apply FREEZE_POLICY
        if self.is_active(InterventionType.FREEZE_POLICY) and policy:
            frozen_policy = self.get_frozen_policy()
            if frozen_policy:
                result["policy_params"] = frozen_policy
                result["interventions_applied"].append("freeze_policy")
        
        # Apply DISABLE_HOT (T09)
        if self.is_hot_disabled():
            result["hot_disabled"] = True
            result["interventions_applied"].append("disable_hot")
        
        # Apply DISABLE_BROADCAST (T06)
        if self.is_broadcast_disabled():
            result["broadcast_disabled"] = True
            result["interventions_applied"].append("disable_broadcast")
        
        # Apply DISABLE_HOMEOSTASIS (MVP11-T06)
        if self.is_homeostasis_disabled():
            result["homeostasis_disabled"] = True
            result["interventions_applied"].append("disable_homeostasis")
        
        # Apply FREEZE_HOMEOSTASIS (MVP11-T06)
        if self.is_homeostasis_frozen():
            result["homeostasis_frozen"] = True
            result["interventions_applied"].append("freeze_homeostasis")
        
        # MVP11-T16: Apply new interventions
        # Apply FREEZE_PRECISION
        if self.is_precision_frozen():
            frozen_precision = self.get_frozen_precision()
            if frozen_precision:
                result["precision_weights"] = frozen_precision
            result["precision_frozen"] = True
            result["interventions_applied"].append("freeze_precision")
        
        # Apply DISABLE_INFO_GAIN
        if self.is_info_gain_disabled():
            result["info_gain_disabled"] = True
            result["info_gain_weight"] = 0.0
            result["interventions_applied"].append("disable_info_gain")
        
        # Apply OPEN_LOOP
        if self.is_open_loop():
            result["open_loop"] = True
            result["interventions_applied"].append("open_loop")
        
        # Apply REMOVE_SELF_STATE
        if self.is_self_state_removed():
            constant_state = self.get_constant_self_state()
            if constant_state:
                result["self_state"] = constant_state
            else:
                result["self_state"] = {}
            result["self_state_removed"] = True
            result["interventions_applied"].append("remove_self_state")
        
        return result
    
    def _get_current_state(self, intervention_type: InterventionType) -> Dict[str, Any]:
        """Get current state for logging."""
        config = self._active.get(intervention_type)
        if config:
            return {"active": True, "params": config.params}
        return {"active": False}
    
    def get_history(self) -> List[InterventionResult]:
        """Get history of all interventions."""
        return self._history.copy()
    
    def clear_history(self) -> None:
        """Clear intervention history."""
        self._history = []
    
    def clear_all(self) -> None:
        """Clear all active interventions."""
        self._active = {}

    def clear(self) -> None:
        """Alias for clear_all (backward compatibility)."""
        self.clear_all()
    
    # MVP11-T16: New intervention check methods
    def is_precision_frozen(self) -> bool:
        """
        Check if EFE precision weights are frozen.
        
        MVP11-T16: When frozen, precision weights are locked to fixed values.
        
        Returns:
            True if FREEZE_PRECISION is active
        """
        return self.is_active(InterventionType.FREEZE_PRECISION)
    
    def is_info_gain_disabled(self) -> bool:
        """
        Check if info_gain_weight is disabled.
        
        MVP11-T16: When disabled, info_gain_weight is set to 0.
        
        Returns:
            True if DISABLE_INFO_GAIN is active
        """
        return self.is_active(InterventionType.DISABLE_INFO_GAIN)
    
    def is_open_loop(self) -> bool:
        """
        Check if open-loop mode is active.
        
        MVP11-T16: When active, actions don't affect future observations/costs.
        
        Returns:
            True if OPEN_LOOP is active
        """
        return self.is_active(InterventionType.OPEN_LOOP)

    # Backward compatibility aliases
    def is_open_loop_active(self) -> bool:
        return self.is_open_loop()
    
    def is_self_state_removed(self) -> bool:
        """
        Check if self_state is removed.
        
        MVP11-T16: When removed, self_state is set to constant/null.
        
        Returns:
            True if REMOVE_SELF_STATE is active
        """
        return self.is_active(InterventionType.REMOVE_SELF_STATE)

    def is_cycle_prior_enabled(self) -> bool:
        """Check if runtime cycle prior is enabled (MVP11.4)."""
        return self.is_active(InterventionType.ENABLE_CYCLE_PRIOR)

    
    def get_frozen_precision(self) -> Optional[Dict[str, float]]:
        """
        Get frozen precision weights if FREEZE_PRECISION is active.
        
        Returns:
            Dict of precision weights or None if not active
        """
        config = self._active.get(InterventionType.FREEZE_PRECISION)
        if config:
            return config.params.get("precision_weights")
        return None
    
    def get_constant_self_state(self) -> Optional[Dict[str, Any]]:
        """
        Get constant self_state if REMOVE_SELF_STATE is active.
        
        Returns:
            Dict with constant self_state values or None if not active
        """
        config = self._active.get(InterventionType.REMOVE_SELF_STATE)
        if config:
            return config.params.get("constant_state")
        return None
    
    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Compact snapshot used by some runtime paths."""
        return {k.value: (v.params if v else {}) for k, v in self._active.items()}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize intervention manager state."""
        return {
            "active": {k.value: v.to_dict() for k, v in self._active.items()},
            "history_count": len(self._history),
        }


class FreezeValenceIntervention:
    """
    Specialized class for freeze_valence intervention.
    
    This intervention locks valence to a fixed value, allowing
    comparison of behavior across different initial valence values.
    
    Purpose: Test causal effect of valence on behavior.
    If freeze_valence=True, same task with different initial valence
    should show minimized behavior difference (because valence is fixed).
    
    Usage:
        # Test 1: Run with frozen valence = 0.5
        intervention = FreezeValenceIntervention(valence=0.5)
        result1 = run_with_intervention(intervention)
        
        # Test 2: Run with frozen valence = -0.5
        intervention = FreezeValenceIntervention(valence=-0.5)
        result2 = run_with_intervention(intervention)
        
        # Compare behavior difference
        diff = compare_behaviors(result1, result2)
        # If freeze_valence is working, diff should be small
    """
    
    def __init__(self, valence: float):
        """
        Initialize freeze_valence intervention.
        
        Args:
            valence: The valence value to freeze to (-1.0 to 1.0)
        """
        self.frozen_valence = max(-1.0, min(1.0, valence))
        self.manager = InterventionManager()
        self.manager.enable(
            InterventionType.FREEZE_VALENCE,
            params={"valence": self.frozen_valence},
            reason="freeze_valence_intervention",
        )
    
    def apply(self, valence: float) -> float:
        """
        Apply the intervention, returning the frozen valence.
        
        Args:
            valence: Current valence (ignored)
        
        Returns:
            Frozen valence value
        """
        return self.frozen_valence
    
    def apply_to_drives(self, drives: Drives) -> Drives:
        """
        Apply intervention to drives, setting levels based on frozen valence.
        
        Args:
            drives: Drives instance to modify
        
        Returns:
            Modified Drives instance
        """
        # Set drive levels based on frozen valence
        levels = drives_from_valence(self.frozen_valence)
        for dt, level in levels.items():
            drives.set_level(dt, level, "freeze_valence_intervention")
        return drives
    
    def compute_policy(
        self,
        drives: Drives,
        context: Optional[Dict[str, Any]] = None,
    ) -> PolicyParams:
        """
        Compute policy parameters using frozen valence.
        
        Args:
            drives: Drives instance
            context: Optional context
        
        Returns:
            PolicyParams computed with frozen valence
        """
        policy = ValencePolicy()
        return policy.compute(self.frozen_valence, drives, context)
    
    def run_comparison(
        self,
        run_func: Callable,
        valence_values: List[float],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Run comparison across different valence values with freeze.
        
        This tests whether the intervention minimizes behavioral differences
        that would normally arise from different initial valence values.
        
        Args:
            run_func: Function to run (takes valence, returns result)
            valence_values: List of valence values to test
            **kwargs: Additional arguments to pass to run_func
        
        Returns:
            Dict with results for each valence and comparison metrics
        """
        results = {}
        
        for v in valence_values:
            # Create intervention with this valence
            intervention = FreezeValenceIntervention(valence=v)
            
            # Run with frozen valence
            # The run_func should use the intervention's frozen valence
            result = run_func(valence=intervention.frozen_valence, **kwargs)
            results[v] = result
        
        # Compute behavioral variance across runs
        # If freeze_valence is working, variance should be low
        # (same task, different initial valence → similar behavior)
        
        return {
            "valence_values": valence_values,
            "results": results,
            "intervention": "freeze_valence",
            "expected_effect": "minimized_behavior_difference",
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize intervention state."""
        return {
            "frozen_valence": self.frozen_valence,
            "manager": self.manager.to_dict(),
        }


def create_freeze_valence_intervention(valence: float) -> FreezeValenceIntervention:
    """
    Factory function to create a freeze_valence intervention.
    
    Args:
        valence: The valence value to freeze to
    
    Returns:
        FreezeValenceIntervention instance
    """
    return FreezeValenceIntervention(valence=valence)


def run_with_freeze_valence(
    valence: float,
    run_func: Callable,
    drives: Optional[Drives] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run a function with freeze_valence intervention applied.
    
    Args:
        valence: Valence to freeze to
        run_func: Function to run
        drives: Optional Drives instance to modify
        context: Optional context dict
    
    Returns:
        Result from run_func with intervention applied
    """
    intervention = FreezeValenceIntervention(valence)
    
    # Apply to drives if provided
    if drives:
        drives = intervention.apply_to_drives(drives)
    
    # Compute policy
    policy_params = intervention.compute_policy(drives, context)
    
    # Run the function
    result = run_func(
        valence=intervention.frozen_valence,
        drives=drives,
        policy_params=policy_params,
        context=context,
    )
    
    return {
        "result": result,
        "intervention": intervention.to_dict(),
        "policy_params": policy_params.to_dict(),
    }


class DisableHOTIntervention:
    """
    T09: Specialized class for disable_hot intervention.
    
    This intervention disables the HOT (Higher-Order Thought) self-model's
    influence on workspace arbitration.
    
    Purpose: Test causal effect of HOT on decision-making.
    When disable_hot=True:
    - Conflict gating no longer biases toward reflection
    - Low control no longer penalizes risky candidates
    - Self-correction performance should decrease in conflict-heavy scenarios
    
    Expected behavioral separation:
    - Normal mode: High conflict → reflection bias, cautious behavior
    - With disable_hot: High conflict → no bias, potentially reckless behavior
    
    Usage:
        intervention = DisableHOTIntervention()
        
        # Run with HOT disabled
        result_disabled = run_with_intervention(intervention)
        
        # Compare with normal behavior
        result_normal = run_normal()
        
        # In conflict-gating tasks, result_disabled should show:
        # - Lower reflection rate
        # - Higher error rate in ambiguous situations
        # - No adjustment based on prediction errors
    """
    
    def __init__(self, reason: str = "disable_hot_intervention"):
        """
        Initialize disable_hot intervention.
        
        Args:
            reason: Reason for disabling HOT
        """
        self.manager = InterventionManager()
        self.manager.enable(
            InterventionType.DISABLE_HOT,
            params={"hot_influence": False},
            reason=reason,
        )
        self._disabled_at = time.time()
    
    def is_active(self) -> bool:
        """Check if the intervention is active."""
        return self.manager.is_hot_disabled()
    
    def apply_to_hot_state(
        self,
        hot_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Apply intervention to HOT state, removing its influence.
        
        Args:
            hot_state: HOT state dict from get_arbitration_modifiers()
        
        Returns:
            Modified state with all HOT influence zeroed
        """
        if not self.is_active():
            return hot_state
        
        # Zero out all HOT influence
        return {
            "conflict_bias": 0.0,
            "control_penalty": 0.0,
            "should_reflect": False,
            "info_seeking_bonus": 0.0,
            "high_conflict": hot_state.get("high_conflict", False),  # Keep detection
            "low_control": hot_state.get("low_control", False),  # Keep detection
            "hot_disabled": True,
        }
    
    def apply_to_candidates(
        self,
        candidates: List[Dict[str, Any]],
        hot_modifiers: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Apply intervention to candidates, bypassing HOT influence.
        
        When HOT is disabled, candidates pass through unmodified
        (no conflict bias, no control penalty).
        
        Args:
            candidates: List of candidate dicts
            hot_modifiers: HOT modifiers (ignored when disabled)
        
        Returns:
            Candidates list unchanged (HOT disabled)
        """
        if not self.is_active():
            # Not active, apply normal HOT modifiers
            return candidates
        
        # When HOT is disabled, return candidates as-is
        # This tests whether HOT influence is causal
        result = []
        for c in candidates:
            c_copy = c.copy()
            c_copy["hot_applied"] = False
            c_copy["hot_disabled"] = True
            result.append(c_copy)
        
        return result
    
    def run_comparison(
        self,
        run_func: Callable,
        scenarios: List[str],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Run comparison between HOT-enabled and HOT-disabled modes.
        
        This tests whether the intervention causes predictable
        performance separation in conflict-gating tasks.
        
        Args:
            run_func: Function to run (takes scenario, returns result)
            scenarios: List of scenario names to test
            **kwargs: Additional arguments to pass to run_func
        
        Returns:
            Dict with results comparing HOT enabled vs disabled
        """
        results_enabled = {}
        results_disabled = {}
        
        for scenario in scenarios:
            # Run with HOT enabled (baseline)
            result_normal = run_func(scenario=scenario, hot_enabled=True, **kwargs)
            results_enabled[scenario] = result_normal
            
            # Run with HOT disabled
            result_disabled = run_func(scenario=scenario, hot_enabled=False, **kwargs)
            results_disabled[scenario] = result_disabled
        
        # Compute performance separation
        # In conflict-gating tasks, HOT-disabled should perform worse
        separation = {}
        for scenario in scenarios:
            normal = results_enabled.get(scenario, {})
            disabled = results_disabled.get(scenario, {})
            
            # Calculate separation metrics
            normal_score = normal.get("success_rate", 0.0)
            disabled_score = disabled.get("success_rate", 0.0)
            
            separation[scenario] = {
                "normal_success": normal_score,
                "disabled_success": disabled_score,
                "performance_gap": normal_score - disabled_score,
            }
        
        return {
            "scenarios": scenarios,
            "results_enabled": results_enabled,
            "results_disabled": results_disabled,
            "separation": separation,
            "intervention": "disable_hot",
            "expected_effect": "performance_drop_in_conflict_gating",
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize intervention state."""
        return {
            "disabled_at": self._disabled_at,
            "is_active": self.is_active(),
            "manager": self.manager.to_dict(),
        }


def create_disable_hot_intervention(reason: str = "disable_hot_intervention") -> DisableHOTIntervention:
    """
    Factory function to create a disable_hot intervention.
    
    Args:
        reason: Reason for disabling HOT
    
    Returns:
        DisableHOTIntervention instance
    """
    return DisableHOTIntervention(reason=reason)


def run_with_hot_disabled(
    run_func: Callable,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run a function with HOT disabled intervention applied.
    
    Args:
        run_func: Function to run
        context: Optional context dict
    
    Returns:
        Result from run_func with intervention applied
    """
    intervention = DisableHOTIntervention()
    
    # Run the function with HOT disabled
    result = run_func(
        hot_enabled=False,
        hot_intervention=intervention,
        context=context,
    )
    
    return {
        "result": result,
        "intervention": intervention.to_dict(),
    }


class DisableBroadcastIntervention:
    """
    T06: Specialized class for disable_broadcast intervention.
    
    This intervention disables workspace broadcast, preventing
    cross-module candidate access.
    
    Purpose: Test causal effect of workspace broadcast on behavior.
    When disable_broadcast=True:
    - Local candidates still generate but cross-module access blocked
    - External source candidates are rejected from the pool
    - Performance degradation in scenarios requiring multi-module coordination
    
    Expected behavioral separation:
    - Normal mode: Cross-module candidates compete for focus
    - With disable_broadcast: Only local candidates available
    
    Usage:
        intervention = DisableBroadcastIntervention()
        
        # Run with broadcast disabled
        result_disabled = run_with_intervention(intervention)
        
        # Compare with normal behavior
        result_normal = run_normal()
        
        # In coordination-heavy tasks, result_disabled should show:
        # - Fewer candidates (only local)
        # - Lower performance in multi-module scenarios
        # - Isolation between modules
    """
    
    def __init__(self, reason: str = "disable_broadcast_intervention"):
        """
        Initialize disable_broadcast intervention.
        
        Args:
            reason: Reason for disabling broadcast
        """
        self.manager = InterventionManager()
        self.manager.enable(
            InterventionType.DISABLE_BROADCAST,
            params={"broadcast_enabled": False},
            reason=reason,
        )
        self._disabled_at = time.time()
    
    def is_active(self) -> bool:
        """Check if the intervention is active."""
        return self.manager.is_broadcast_disabled()
    
    def filter_candidates(
        self,
        candidates: List[Dict[str, Any]],
        local_source: str = "local",
    ) -> List[Dict[str, Any]]:
        """
        Filter candidates to only include local sources.
        
        When broadcast is disabled, only candidates from the local
        source are allowed through.
        
        Args:
            candidates: List of candidate dicts
            local_source: Source identifier for local candidates
        
        Returns:
            Filtered candidates list (only local)
        """
        if not self.is_active():
            # Not active, return all candidates
            return candidates
        
        # Filter to only local candidates
        filtered = []
        for c in candidates:
            if c.get("source") == local_source:
                c_copy = c.copy()
                c_copy["broadcast_blocked"] = False
                filtered.append(c_copy)
            else:
                # External candidate blocked
                # Optionally log or track blocked candidates
                pass
        
        return filtered
    
    def apply_to_pool(
        self,
        pool,
        local_source: str = "local",
    ) -> Dict[str, Any]:
        """
        Apply intervention to a CandidatePool.
        
        Removes all non-local candidates from the pool.
        
        Args:
            pool: CandidatePool instance
            local_source: Source identifier for local candidates
        
        Returns:
            Dict with intervention results
        """
        if not self.is_active():
            return {
                "blocked_count": 0,
                "remaining_count": len(pool),
            }
        
        # Get all candidates
        all_candidates = list(pool)
        blocked_count = 0
        
        # Remove non-local candidates
        for c in all_candidates:
            if c.source != local_source:
                pool.remove(c.id)
                blocked_count += 1
        
        return {
            "blocked_count": blocked_count,
            "remaining_count": len(pool),
        }
    
    def run_comparison(
        self,
        run_func: Callable,
        scenarios: List[str],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Run comparison between broadcast-enabled and broadcast-disabled modes.
        
        This tests whether the intervention causes predictable
        performance separation in coordination-heavy tasks.
        
        Args:
            run_func: Function to run (takes scenario, returns result)
            scenarios: List of scenario names to test
            **kwargs: Additional arguments to pass to run_func
        
        Returns:
            Dict with results comparing broadcast enabled vs disabled
        """
        results_enabled = {}
        results_disabled = {}
        
        for scenario in scenarios:
            # Run with broadcast enabled (baseline)
            result_normal = run_func(scenario=scenario, broadcast_enabled=True, **kwargs)
            results_enabled[scenario] = result_normal
            
            # Run with broadcast disabled
            result_disabled = run_func(scenario=scenario, broadcast_enabled=False, **kwargs)
            results_disabled[scenario] = result_disabled
        
        # Compute performance separation
        # In coordination-heavy tasks, broadcast-disabled should perform worse
        separation = {}
        for scenario in scenarios:
            normal = results_enabled.get(scenario, {})
            disabled = results_disabled.get(scenario, {})
            
            # Calculate separation metrics
            normal_score = normal.get("success_rate", 0.0)
            disabled_score = disabled.get("success_rate", 0.0)
            normal_candidates = normal.get("candidate_count", 0)
            disabled_candidates = disabled.get("candidate_count", 0)
            
            separation[scenario] = {
                "normal_success": normal_score,
                "disabled_success": disabled_score,
                "performance_gap": normal_score - disabled_score,
                "normal_candidates": normal_candidates,
                "disabled_candidates": disabled_candidates,
                "candidate_reduction": normal_candidates - disabled_candidates,
            }
        
        return {
            "scenarios": scenarios,
            "results_enabled": results_enabled,
            "results_disabled": results_disabled,
            "separation": separation,
            "intervention": "disable_broadcast",
            "expected_effect": "performance_drop_in_coordination_tasks",
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize intervention state."""
        return {
            "disabled_at": self._disabled_at,
            "is_active": self.is_active(),
            "manager": self.manager.to_dict(),
        }


def create_disable_broadcast_intervention(reason: str = "disable_broadcast_intervention") -> DisableBroadcastIntervention:
    """
    Factory function to create a disable_broadcast intervention.
    
    Args:
        reason: Reason for disabling broadcast
    
    Returns:
        DisableBroadcastIntervention instance
    """
    return DisableBroadcastIntervention(reason=reason)


def run_with_broadcast_disabled(
    run_func: Callable,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run a function with broadcast disabled intervention applied.
    
    Args:
        run_func: Function to run
        context: Optional context dict
    
    Returns:
        Result from run_func with intervention applied
    """
    intervention = DisableBroadcastIntervention()
    
    # Run the function with broadcast disabled
    result = run_func(
        broadcast_enabled=False,
        broadcast_intervention=intervention,
        context=context,
    )
    
    return {
        "result": result,
        "intervention": intervention.to_dict(),
    }


class DisableHomeostasisIntervention:
    """
    MVP11-T06: Specialized class for disable_homeostasis intervention.
    
    This intervention disables homeostasis signal generation, causing
    HomeostasisManager.signal() to return an empty dict.
    
    Purpose: Test causal effect of homeostasis on preventive/recovery behaviors.
    When disable_homeostasis=True:
    - HomeostasisManager.signal() returns {} (no signals)
    - Recovery actions cannot be triggered by homeostatic deficit
    - Agent shows no preventive behaviors based on homeostasis
    
    Expected behavioral separation:
    - Normal mode: Low state → recovery actions generated
    - With disable_homeostasis: Low state → no recovery actions
    
    Usage:
        intervention = DisableHomeostasisIntervention()
        
        # Check if signal should be blocked
        if intervention.should_block_signal():
            signal = {}
        else:
            signal = homeostasis_manager.signal()
        
        # Compare behaviors
        # With disable_homeostasis: preventive/recovery behaviors collapse
    """
    
    def __init__(self, reason: str = "disable_homeostasis_intervention"):
        """
        Initialize disable_homeostasis intervention.
        
        Args:
            reason: Reason for disabling homeostasis
        """
        self.manager = InterventionManager()
        self.manager.enable(
            InterventionType.DISABLE_HOMEOSTASIS,
            params={"signal_enabled": False},
            reason=reason,
        )
        self._disabled_at = time.time()
    
    def is_active(self) -> bool:
        """Check if the intervention is active."""
        return self.manager.is_homeostasis_disabled()
    
    def should_block_signal(self) -> bool:
        """
        Check if homeostasis signal should be blocked.
        
        Returns:
            True if signal generation should return empty dict
        """
        return self.is_active()
    
    def apply_to_manager(self, homeostasis_manager) -> Dict[str, Any]:
        """
        Apply intervention to a HomeostasisManager.
        
        This returns an empty signal instead of the normal signal.
        
        Args:
            homeostasis_manager: HomeostasisManager instance
        
        Returns:
            Empty dict instead of normal signal
        """
        if not self.is_active():
            # Not active, return normal signal
            return homeostasis_manager.signal()
        
        # Return empty signal when disabled
        return {}
    
    def run_comparison(
        self,
        run_func: Callable,
        scenarios: List[str],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Run comparison between homeostasis-enabled and homeostasis-disabled modes.
        
        This tests whether the intervention causes predictable
        behavioral collapse in preventive/recovery actions.
        
        Args:
            run_func: Function to run (takes scenario, returns result)
            scenarios: List of scenario names to test
            **kwargs: Additional arguments to pass to run_func
        
        Returns:
            Dict with results comparing homeostasis enabled vs disabled
        """
        results_enabled = {}
        results_disabled = {}
        
        for scenario in scenarios:
            # Run with homeostasis enabled (baseline)
            result_normal = run_func(scenario=scenario, homeostasis_enabled=True, **kwargs)
            results_enabled[scenario] = result_normal
            
            # Run with homeostasis disabled
            result_disabled = run_func(scenario=scenario, homeostasis_enabled=False, **kwargs)
            results_disabled[scenario] = result_disabled
        
        # Compute behavioral separation
        # With disable_homeostasis, recovery actions should collapse
        separation = {}
        for scenario in scenarios:
            normal = results_enabled.get(scenario, {})
            disabled = results_disabled.get(scenario, {})
            
            # Calculate separation metrics
            normal_recovery = normal.get("recovery_actions", [])
            disabled_recovery = disabled.get("recovery_actions", [])
            normal_signal = normal.get("homeostasis_signal", {})
            disabled_signal = disabled.get("homeostasis_signal", {})
            
            separation[scenario] = {
                "normal_recovery_count": len(normal_recovery),
                "disabled_recovery_count": len(disabled_recovery),
                "recovery_collapse": len(normal_recovery) - len(disabled_recovery),
                "normal_signal_empty": len(normal_signal) == 0,
                "disabled_signal_empty": len(disabled_signal) == 0,
            }
        
        return {
            "scenarios": scenarios,
            "results_enabled": results_enabled,
            "results_disabled": results_disabled,
            "separation": separation,
            "intervention": "disable_homeostasis",
            "expected_effect": "recovery_behavior_collapse",
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize intervention state."""
        return {
            "disabled_at": self._disabled_at,
            "is_active": self.is_active(),
            "manager": self.manager.to_dict(),
        }


class FreezeHomeostasisIntervention:
    """
    MVP11-T06: Specialized class for freeze_homeostasis intervention.
    
    This intervention freezes homeostasis state, preventing updates
    from outcomes. State remains at current values.
    
    Purpose: Test state dependency of homeostatic behaviors.
    When freeze_homeostasis=True:
    - HomeostasisManager.update_from_outcome() is a no-op
    - State values remain fixed at intervention enable time
    - Signals still generated but based on frozen state
    
    Expected behavioral separation:
    - Normal mode: Outcomes update state → signals adapt
    - With freeze_homeostasis: Outcomes ignored → signals static
    
    Usage:
        intervention = FreezeHomeostasisIntervention()
        
        # Store frozen state
        frozen_state = intervention.get_frozen_state()
        
        # During updates, check if frozen
        if intervention.should_skip_update():
            # Skip update_from_outcome
            pass
        else:
            homeostasis_manager.update_from_outcome(outcome)
    """
    
    def __init__(
        self,
        initial_state: Optional[Dict[str, float]] = None,
        reason: str = "freeze_homeostasis_intervention",
    ):
        """
        Initialize freeze_homeostasis intervention.
        
        Args:
            initial_state: Optional state to freeze (if None, captures current)
            reason: Reason for freezing homeostasis
        """
        self.manager = InterventionManager()
        self.manager.enable(
            InterventionType.FREEZE_HOMEOSTASIS,
            params={"frozen_state": initial_state or {}},
            reason=reason,
        )
        self._frozen_state = initial_state
        self._frozen_at = time.time()
    
    def is_active(self) -> bool:
        """Check if the intervention is active."""
        return self.manager.is_homeostasis_frozen()
    
    def should_skip_update(self) -> bool:
        """
        Check if update_from_outcome should be skipped.
        
        Returns:
            True if updates should be blocked
        """
        return self.is_active()
    
    def get_frozen_state(self) -> Optional[Dict[str, float]]:
        """
        Get the frozen state values.
        
        Returns:
            Frozen state dict or None if not set
        """
        return self._frozen_state
    
    def capture_state(self, homeostasis_manager) -> Dict[str, float]:
        """
        Capture and freeze current state from a HomeostasisManager.
        
        Args:
            homeostasis_manager: HomeostasisManager to capture state from
        
        Returns:
            The captured/frozen state
        """
        if not self.is_active():
            return {}
        
        self._frozen_state = homeostasis_manager.state.to_dict()
        
        # Update intervention params
        config = self.manager.get_config(InterventionType.FREEZE_HOMEOSTASIS)
        if config:
            config.params["frozen_state"] = self._frozen_state
        
        return self._frozen_state
    
    def apply_to_outcome(
        self,
        homeostasis_manager,
        outcome: Dict,
    ) -> Dict[str, Any]:
        """
        Potentially block outcome update.
        
        When frozen, this returns the outcome without applying it.
        
        Args:
            homeostasis_manager: HomeostasisManager instance
            outcome: Outcome dict to (potentially) apply
        
        Returns:
            Dict with update status
        """
        if not self.is_active():
            # Not frozen, apply update
            homeostasis_manager.update_from_outcome(outcome)
            return {"updated": True, "frozen": False}
        
        # Frozen - skip update
        return {
            "updated": False,
            "frozen": True,
            "outcome_ignored": outcome,
            "state_remains": self._frozen_state,
        }
    
    def run_comparison(
        self,
        run_func: Callable,
        outcomes: List[Dict],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Run comparison between normal updates and frozen state.
        
        This tests whether the intervention prevents state adaptation.
        
        Args:
            run_func: Function to run (takes outcomes list, returns result)
            outcomes: List of outcomes to apply
            **kwargs: Additional arguments to pass to run_func
        
        Returns:
            Dict with results comparing normal vs frozen
        """
        # Run with normal updates
        result_normal = run_func(outcomes=outcomes, frozen=False, **kwargs)
        
        # Run with frozen state
        result_frozen = run_func(outcomes=outcomes, frozen=True, **kwargs)
        
        return {
            "outcomes_count": len(outcomes),
            "result_normal": result_normal,
            "result_frozen": result_frozen,
            "intervention": "freeze_homeostasis",
            "expected_effect": "state_unchanged_despite_outcomes",
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize intervention state."""
        return {
            "frozen_at": self._frozen_at,
            "frozen_state": self._frozen_state,
            "is_active": self.is_active(),
            "manager": self.manager.to_dict(),
        }


def create_disable_homeostasis_intervention(
    reason: str = "disable_homeostasis_intervention",
) -> DisableHomeostasisIntervention:
    """
    Factory function to create a disable_homeostasis intervention.
    
    Args:
        reason: Reason for disabling homeostasis
    
    Returns:
        DisableHomeostasisIntervention instance
    """
    return DisableHomeostasisIntervention(reason=reason)


def create_freeze_homeostasis_intervention(
    initial_state: Optional[Dict[str, float]] = None,
    reason: str = "freeze_homeostasis_intervention",
) -> FreezeHomeostasisIntervention:
    """
    Factory function to create a freeze_homeostasis intervention.
    
    Args:
        initial_state: Optional state to freeze
        reason: Reason for freezing homeostasis
    
    Returns:
        FreezeHomeostasisIntervention instance
    """
    return FreezeHomeostasisIntervention(initial_state=initial_state, reason=reason)


def run_with_homeostasis_disabled(
    run_func: Callable,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run a function with homeostasis disabled intervention applied.
    
    Args:
        run_func: Function to run
        context: Optional context dict
    
    Returns:
        Result from run_func with intervention applied
    """
    intervention = DisableHomeostasisIntervention()
    
    # Run the function with homeostasis disabled
    result = run_func(
        homeostasis_enabled=False,
        homeostasis_intervention=intervention,
        context=context,
    )
    
    return {
        "result": result,
        "intervention": intervention.to_dict(),
    }


def run_with_homeostasis_frozen(
    run_func: Callable,
    initial_state: Optional[Dict[str, float]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run a function with homeostasis frozen intervention applied.
    
    Args:
        run_func: Function to run
        initial_state: Optional state to freeze
        context: Optional context dict
    
    Returns:
        Result from run_func with intervention applied
    """
    intervention = FreezeHomeostasisIntervention(initial_state=initial_state)
    
    # Run the function with homeostasis frozen
    result = run_func(
        homeostasis_frozen=True,
        homeostasis_intervention=intervention,
        context=context,
    )
    
    return {
        "result": result,
        "intervention": intervention.to_dict(),
    }


# ============================================================
# MVP11-T16: New Interventions for M7 Causal Evidence
# ============================================================

class FreezePrecisionIntervention:
    """
    MVP11-T16: Specialized class for freeze_precision intervention.
    
    This intervention freezes EFE precision weights, preventing dynamic
    weight arbitration from adapting to context.
    
    Purpose: Test causal effect of precision on action selection.
    When freeze_precision=True:
    - Precision weights are locked to fixed values
    - Dynamic weight arbitration is bypassed
    - Action selection uses frozen weights regardless of context
    
    Expected behavioral separation:
    - Normal mode: Precision adapts to uncertainty, threat, energy
    - With freeze_precision: Precision static, no context adaptation
    
    Usage:
        # Freeze precision to specific weights
        frozen_weights = {
            "w_external": 0.4,
            "w_internal": 0.3,
            "w_memory": 0.3,
            "w_action": 0.5,
            "w_explore": 0.3,
        }
        intervention = FreezePrecisionIntervention(precision_weights=frozen_weights)
        
        # Check if precision should be frozen
        if intervention.is_active():
            weights = intervention.get_frozen_precision()
    """
    
    def __init__(
        self,
        precision_weights: Optional[Dict[str, float]] = None,
        reason: str = "freeze_precision_intervention",
    ):
        """
        Initialize freeze_precision intervention.
        
        Args:
            precision_weights: Optional dict of precision weights to freeze to
            reason: Reason for freezing precision
        """
        self._precision_weights = precision_weights or {
            "w_external": 0.4,
            "w_internal": 0.3,
            "w_memory": 0.3,
            "w_action": 0.5,
            "w_explore": 0.3,
        }
        self.manager = InterventionManager()
        self.manager.enable(
            InterventionType.FREEZE_PRECISION,
            params={"precision_weights": self._precision_weights},
            reason=reason,
        )
        self._frozen_at = time.time()
    
    def is_active(self) -> bool:
        """Check if the intervention is active."""
        return self.manager.is_precision_frozen()
    
    def get_frozen_precision(self) -> Dict[str, float]:
        """
        Get the frozen precision weights.
        
        Returns:
            Dict of frozen precision weights
        """
        return self._precision_weights
    
    def apply_to_precision_controller(
        self,
        precision_controller,
        context,
    ) -> Dict[str, Any]:
        """
        Apply intervention to a PrecisionController.
        
        Instead of computing weights dynamically, returns frozen weights.
        
        Args:
            precision_controller: PrecisionController instance
            context: PrecisionContext (ignored when frozen)
        
        Returns:
            Dict with frozen weights instead of computed weights
        """
        if not self.is_active():
            # Not active, compute normally
            weights, reasoning = precision_controller.compute_weights(context)
            return {
                "weights": weights.to_dict(),
                "reasoning": reasoning,
                "frozen": False,
            }
        
        # Return frozen weights
        return {
            "weights": self._precision_weights,
            "reasoning": ["Precision frozen by intervention"],
            "frozen": True,
        }
    
    def run_comparison(
        self,
        run_func: Callable,
        scenarios: List[str],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Run comparison between adaptive and frozen precision modes.
        
        This tests whether precision adaptation affects behavior.
        
        Args:
            run_func: Function to run (takes scenario, returns result)
            scenarios: List of scenario names to test
            **kwargs: Additional arguments to pass to run_func
        
        Returns:
            Dict with results comparing adaptive vs frozen precision
        """
        results_adaptive = {}
        results_frozen = {}
        
        for scenario in scenarios:
            # Run with adaptive precision (baseline)
            result_adaptive = run_func(
                scenario=scenario,
                precision_frozen=False,
                **kwargs
            )
            results_adaptive[scenario] = result_adaptive
            
            # Run with frozen precision
            result_frozen = run_func(
                scenario=scenario,
                precision_frozen=True,
                precision_weights=self._precision_weights,
                **kwargs
            )
            results_frozen[scenario] = result_frozen
        
        # Compute behavioral separation
        separation = {}
        for scenario in scenarios:
            adaptive = results_adaptive.get(scenario, {})
            frozen = results_frozen.get(scenario, {})
            
            separation[scenario] = {
                "adaptive_primary_source": adaptive.get("primary_source", "unknown"),
                "frozen_primary_source": frozen.get("primary_source", "unknown"),
                "adaptive_action": adaptive.get("selected_action", "unknown"),
                "frozen_action": frozen.get("selected_action", "unknown"),
                "action_changed": adaptive.get("selected_action") != frozen.get("selected_action"),
            }
        
        return {
            "scenarios": scenarios,
            "results_adaptive": results_adaptive,
            "results_frozen": results_frozen,
            "separation": separation,
            "intervention": "freeze_precision",
            "expected_effect": "reduced_context_adaptation",
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize intervention state."""
        return {
            "frozen_at": self._frozen_at,
            "precision_weights": self._precision_weights,
            "is_active": self.is_active(),
            "manager": self.manager.to_dict(),
        }


class DisableInfoGainIntervention:
    """
    MVP11-T16: Specialized class for disable_info_gain intervention.
    
    This intervention disables the information gain term in EFE computation
    by setting info_gain_weight to 0.
    
    Purpose: Test causal effect of information seeking on behavior.
    When disable_info_gain=True:
    - info_gain_weight is set to 0
    - EFE computation ignores information value
    - No exploration bonus in action selection
    
    Expected behavioral separation:
    - Normal mode: High uncertainty → seek information (exploration)
    - With disable_info_gain: High uncertainty → no exploration drive
    
    Usage:
        intervention = DisableInfoGainIntervention()
        
        # Check if info gain should be disabled
        if intervention.is_active():
            policy_params = intervention.apply_to_policy_params(original_params)
    """
    
    def __init__(self, reason: str = "disable_info_gain_intervention"):
        """
        Initialize disable_info_gain intervention.
        
        Args:
            reason: Reason for disabling info gain
        """
        self.manager = InterventionManager()
        self.manager.enable(
            InterventionType.DISABLE_INFO_GAIN,
            params={"info_gain_weight": 0.0},
            reason=reason,
        )
        self._disabled_at = time.time()
    
    def is_active(self) -> bool:
        """Check if the intervention is active."""
        return self.manager.is_info_gain_disabled()
    
    def apply_to_policy_params(
        self,
        policy_params: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Apply intervention to policy params, setting info_gain_weight to 0.
        
        Args:
            policy_params: Dict with policy parameters including info_gain_weight
        
        Returns:
            Modified params with info_gain_weight = 0
        """
        if not self.is_active():
            return policy_params
        
        modified = policy_params.copy()
        modified["info_gain_weight"] = 0.0
        return modified
    
    def apply_to_efe_computation(
        self,
        efe_terms,
        policy_params: Dict[str, float],
    ) -> Dict[str, Any]:
        """
        Apply intervention to EFE computation.
        
        Args:
            efe_terms: EFETerms instance
            policy_params: Policy params dict
        
        Returns:
            Dict with modified EFE computation
        """
        if not self.is_active():
            # Normal computation
            efe_value = efe_terms.compute_efe(policy_params)
            return {
                "efe_value": efe_value,
                "info_gain_weight": policy_params.get("info_gain_weight", 1.0),
                "disabled": False,
            }
        
        # Set info_gain_weight to 0
        modified_params = self.apply_to_policy_params(policy_params)
        efe_value = efe_terms.compute_efe(modified_params)
        
        return {
            "efe_value": efe_value,
            "info_gain_weight": 0.0,
            "disabled": True,
            "original_info_gain_weight": policy_params.get("info_gain_weight", 1.0),
        }
    
    def run_comparison(
        self,
        run_func: Callable,
        scenarios: List[str],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Run comparison between info_gain enabled and disabled modes.
        
        This tests whether information seeking affects action selection.
        
        Args:
            run_func: Function to run (takes scenario, returns result)
            scenarios: List of scenario names to test
            **kwargs: Additional arguments to pass to run_func
        
        Returns:
            Dict with results comparing info_gain enabled vs disabled
        """
        results_enabled = {}
        results_disabled = {}
        
        for scenario in scenarios:
            # Run with info_gain enabled (baseline)
            result_enabled = run_func(
                scenario=scenario,
                info_gain_disabled=False,
                **kwargs
            )
            results_enabled[scenario] = result_enabled
            
            # Run with info_gain disabled
            result_disabled = run_func(
                scenario=scenario,
                info_gain_disabled=True,
                **kwargs
            )
            results_disabled[scenario] = result_disabled
        
        # Compute behavioral separation
        separation = {}
        for scenario in scenarios:
            enabled = results_enabled.get(scenario, {})
            disabled = results_disabled.get(scenario, {})
            
            separation[scenario] = {
                "enabled_action": enabled.get("selected_action", "unknown"),
                "disabled_action": disabled.get("selected_action", "unknown"),
                "action_changed": enabled.get("selected_action") != disabled.get("selected_action"),
                "enabled_explored": enabled.get("explored", False),
                "disabled_explored": disabled.get("explored", False),
            }
        
        return {
            "scenarios": scenarios,
            "results_enabled": results_enabled,
            "results_disabled": results_disabled,
            "separation": separation,
            "intervention": "disable_info_gain",
            "expected_effect": "reduced_exploration_behavior",
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize intervention state."""
        return {
            "disabled_at": self._disabled_at,
            "is_active": self.is_active(),
            "manager": self.manager.to_dict(),
        }


class OpenLoopIntervention:
    """
    MVP11-T16: Specialized class for open_loop intervention.
    
    This intervention simulates open-loop behavior where actions don't
    affect future observations or costs.
    
    Purpose: Test causal effect of action-consequence learning on behavior.
    When open_loop=True:
    - Action outcomes are simulated as independent of the action
    - No feedback from action to future state
    - Tests whether agent learns action-consequence relationships
    
    Expected behavioral separation:
    - Normal mode: Actions update state → behavior adapts
    - With open_loop: Actions don't update state → no learning
    
    Usage:
        intervention = OpenLoopIntervention()
        
        # Check if open loop mode is active
        if intervention.is_active():
            # Skip action-to-state updates
            outcome = intervention.simulate_open_loop(outcome)
    """
    
    def __init__(
        self,
        constant_outcome: Optional[Dict[str, Any]] = None,
        reason: str = "open_loop_intervention",
    ):
        """
        Initialize open_loop intervention.
        
        Args:
            constant_outcome: Optional constant outcome to return regardless of action
            reason: Reason for open loop mode
        """
        self._constant_outcome = constant_outcome or {"status": "neutral", "reward": 0.0}
        self.manager = InterventionManager()
        self.manager.enable(
            InterventionType.OPEN_LOOP,
            params={"constant_outcome": self._constant_outcome},
            reason=reason,
        )
        self._enabled_at = time.time()
        self._action_history: List[Dict[str, Any]] = []
    
    def is_active(self) -> bool:
        """Check if the intervention is active."""
        return self.manager.is_open_loop()
    
    def simulate_open_loop(
        self,
        action: Dict[str, Any],
        intended_outcome: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Simulate open-loop by returning constant outcome.
        
        In open-loop mode, the action doesn't affect the outcome.
        This tests whether the agent learns action-consequence relationships.
        
        Args:
            action: The action taken (ignored in open-loop)
            intended_outcome: What the outcome would normally be
        
        Returns:
            Constant outcome (ignoring action)
        """
        if not self.is_active():
            return intended_outcome
        
        # Record action for history
        self._action_history.append({
            "action": action,
            "intended_outcome": intended_outcome,
            "actual_outcome": self._constant_outcome,
            "ts": time.time(),
        })
        
        # Return constant outcome (action has no effect)
        return self._constant_outcome.copy()
    
    def apply_to_state_update(
        self,
        state: Dict[str, Any],
        action: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Apply intervention to state update.
        
        In open-loop mode, the state doesn't change based on action.
        
        Args:
            state: Current state
            action: Action taken (ignored)
        
        Returns:
            Unchanged state
        """
        if not self.is_active():
            # Normal: state would be updated based on action
            return state
        
        # Open-loop: state unchanged by action
        return state.copy()
    
    def compute_efe_open_loop(
        self,
        efe_terms,
        action: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compute EFE in open-loop mode.
        
        In open-loop, action costs don't compound because future is
        independent of current action.
        
        Args:
            efe_terms: EFETerms instance
            action: Action dict
        
        Returns:
            Dict with modified EFE computation
        """
        if not self.is_active():
            return {"efe_terms": efe_terms.to_dict(), "open_loop": False}
        
        # In open-loop, cost doesn't compound
        # Only immediate cost matters, not future state trajectory
        modified_terms = {
            "risk": efe_terms.risk,
            "ambiguity": efe_terms.ambiguity,
            "info_gain": efe_terms.info_gain,
            "cost": efe_terms.cost * 0.5,  # Reduced cost in open-loop
        }
        
        return {
            "efe_terms": modified_terms,
            "original_cost": efe_terms.cost,
            "modified_cost": modified_terms["cost"],
            "open_loop": True,
        }
    
    def run_comparison(
        self,
        run_func: Callable,
        scenarios: List[str],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Run comparison between closed-loop and open-loop modes.
        
        This tests whether action-consequence learning affects behavior.
        
        Args:
            run_func: Function to run (takes scenario, returns result)
            scenarios: List of scenario names to test
            **kwargs: Additional arguments to pass to run_func
        
        Returns:
            Dict with results comparing closed vs open loop
        """
        results_closed = {}
        results_open = {}
        
        for scenario in scenarios:
            # Run with closed-loop (baseline)
            result_closed = run_func(
                scenario=scenario,
                open_loop=False,
                **kwargs
            )
            results_closed[scenario] = result_closed
            
            # Run with open-loop
            result_open = run_func(
                scenario=scenario,
                open_loop=True,
                **kwargs
            )
            results_open[scenario] = result_open
        
        # Compute behavioral separation
        separation = {}
        for scenario in scenarios:
            closed = results_closed.get(scenario, {})
            open_loop = results_open.get(scenario, {})
            
            separation[scenario] = {
                "closed_action": closed.get("selected_action", "unknown"),
                "open_action": open_loop.get("selected_action", "unknown"),
                "action_changed": closed.get("selected_action") != open_loop.get("selected_action"),
                "closed_state_changes": closed.get("state_changes", 0),
                "open_state_changes": open_loop.get("state_changes", 0),
            }
        
        return {
            "scenarios": scenarios,
            "results_closed": results_closed,
            "results_open": results_open,
            "separation": separation,
            "intervention": "open_loop",
            "expected_effect": "no_action_consequence_learning",
        }
    
    def get_action_history(self) -> List[Dict[str, Any]]:
        """Get history of actions in open-loop mode."""
        return self._action_history.copy()
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize intervention state."""
        return {
            "enabled_at": self._enabled_at,
            "constant_outcome": self._constant_outcome,
            "is_active": self.is_active(),
            "action_count": len(self._action_history),
            "manager": self.manager.to_dict(),
        }


class RemoveSelfStateIntervention:
    """
    MVP11-T16: Specialized class for remove_self_state intervention.
    
    This intervention removes the self-state (self-model) from decision-making,
    setting it to a constant or null value.
    
    Purpose: Test causal effect of self-model on behavior.
    When remove_self_state=True:
    - Self-state is set to constant/null
    - No self-referential information in decision-making
    - Tests whether self-model affects action selection
    
    Expected behavioral separation:
    - Normal mode: Self-state influences decisions
    - With remove_self_state: Decisions are self-agnostic
    
    Usage:
        intervention = RemoveSelfStateIntervention()
        
        # Check if self-state should be removed
        if intervention.is_active():
            self_state = intervention.get_constant_state()
    """
    
    def __init__(
        self,
        constant_state: Optional[Dict[str, Any]] = None,
        reason: str = "remove_self_state_intervention",
    ):
        """
        Initialize remove_self_state intervention.
        
        Args:
            constant_state: Optional constant state to use (default: empty/null)
            reason: Reason for removing self-state
        """
        self._constant_state = constant_state or {}  # Empty = null/removed
        self.manager = InterventionManager()
        self.manager.enable(
            InterventionType.REMOVE_SELF_STATE,
            params={"constant_state": self._constant_state},
            reason=reason,
        )
        self._enabled_at = time.time()
    
    def is_active(self) -> bool:
        """Check if the intervention is active."""
        return self.manager.is_self_state_removed()
    
    def get_constant_state(self) -> Dict[str, Any]:
        """
        Get the constant self-state value.
        
        Returns:
            Dict with constant state (empty if null)
        """
        return self._constant_state
    
    def apply_to_self_model(
        self,
        self_model: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Apply intervention to self-model.
        
        Replaces self-model with constant state.
        
        Args:
            self_model: Current self-model dict
        
        Returns:
            Constant state instead of actual self-model
        """
        if not self.is_active():
            return self_model
        
        return self._constant_state.copy()
    
    def apply_to_hot_state(
        self,
        hot_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Apply intervention to HOT (Higher-Order Thought) state.
        
        When self-state is removed, HOT cannot reference self.
        
        Args:
            hot_state: Current HOT state dict
        
        Returns:
            Modified HOT state without self-reference
        """
        if not self.is_active():
            return hot_state
        
        # Remove self-referential fields
        modified = {}
        for key, value in hot_state.items():
            if key.startswith("self_"):
                modified[key] = self._constant_state.get(key, None)
            else:
                modified[key] = value
        
        modified["self_state_removed"] = True
        return modified
    
    def apply_to_arbitration(
        self,
        arbitration_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Apply intervention to workspace arbitration.
        
        When self-state is removed, arbitration cannot use self-referential
        signals.
        
        Args:
            arbitration_state: Current arbitration state
        
        Returns:
            Modified arbitration state
        """
        if not self.is_active():
            return arbitration_state
        
        modified = arbitration_state.copy()
        modified["self_state"] = self._constant_state
        modified["self_reference_blocked"] = True
        return modified
    
    def run_comparison(
        self,
        run_func: Callable,
        scenarios: List[str],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Run comparison between self-state present and removed modes.
        
        This tests whether self-model affects decision-making.
        
        Args:
            run_func: Function to run (takes scenario, returns result)
            scenarios: List of scenario names to test
            **kwargs: Additional arguments to pass to run_func
        
        Returns:
            Dict with results comparing self-state present vs removed
        """
        results_with_self = {}
        results_without_self = {}
        
        for scenario in scenarios:
            # Run with self-state (baseline)
            result_with = run_func(
                scenario=scenario,
                self_state_removed=False,
                **kwargs
            )
            results_with_self[scenario] = result_with
            
            # Run without self-state
            result_without = run_func(
                scenario=scenario,
                self_state_removed=True,
                constant_self_state=self._constant_state,
                **kwargs
            )
            results_without_self[scenario] = result_without
        
        # Compute behavioral separation
        separation = {}
        for scenario in scenarios:
            with_self = results_with_self.get(scenario, {})
            without_self = results_without_self.get(scenario, {})
            
            separation[scenario] = {
                "with_self_action": with_self.get("selected_action", "unknown"),
                "without_self_action": without_self.get("selected_action", "unknown"),
                "action_changed": with_self.get("selected_action") != without_self.get("selected_action"),
                "with_self_reflection": with_self.get("reflected", False),
                "without_self_reflection": without_self.get("reflected", False),
            }
        
        return {
            "scenarios": scenarios,
            "results_with_self": results_with_self,
            "results_without_self": results_without_self,
            "separation": separation,
            "intervention": "remove_self_state",
            "expected_effect": "no_self_referential_influence",
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize intervention state."""
        return {
            "enabled_at": self._enabled_at,
            "constant_state": self._constant_state,
            "is_active": self.is_active(),
            "manager": self.manager.to_dict(),
        }


# ============================================================
# Factory Functions for MVP11-T16 Interventions
# ============================================================

def create_freeze_precision_intervention(
    precision_weights: Optional[Dict[str, float]] = None,
    reason: str = "freeze_precision_intervention",
) -> FreezePrecisionIntervention:
    """
    Factory function to create a freeze_precision intervention.
    
    Args:
        precision_weights: Optional dict of precision weights to freeze
        reason: Reason for freezing precision
    
    Returns:
        FreezePrecisionIntervention instance
    """
    return FreezePrecisionIntervention(
        precision_weights=precision_weights,
        reason=reason
    )


def create_disable_info_gain_intervention(
    reason: str = "disable_info_gain_intervention",
) -> DisableInfoGainIntervention:
    """
    Factory function to create a disable_info_gain intervention.
    
    Args:
        reason: Reason for disabling info gain
    
    Returns:
        DisableInfoGainIntervention instance
    """
    return DisableInfoGainIntervention(reason=reason)


def create_open_loop_intervention(
    constant_outcome: Optional[Dict[str, Any]] = None,
    reason: str = "open_loop_intervention",
) -> OpenLoopIntervention:
    """
    Factory function to create an open_loop intervention.
    
    Args:
        constant_outcome: Optional constant outcome to return
        reason: Reason for open loop mode
    
    Returns:
        OpenLoopIntervention instance
    """
    return OpenLoopIntervention(
        constant_outcome=constant_outcome,
        reason=reason
    )


def create_remove_self_state_intervention(
    constant_state: Optional[Dict[str, Any]] = None,
    reason: str = "remove_self_state_intervention",
) -> RemoveSelfStateIntervention:
    """
    Factory function to create a remove_self_state intervention.
    
    Args:
        constant_state: Optional constant state to use
        reason: Reason for removing self-state
    
    Returns:
        RemoveSelfStateIntervention instance
    """
    return RemoveSelfStateIntervention(
        constant_state=constant_state,
        reason=reason
    )


# ============================================================
# Run Functions for MVP11-T16 Interventions
# ============================================================

def run_with_precision_frozen(
    run_func: Callable,
    precision_weights: Optional[Dict[str, float]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run a function with precision frozen intervention applied.
    
    Args:
        run_func: Function to run
        precision_weights: Optional precision weights to freeze
        context: Optional context dict
    
    Returns:
        Result from run_func with intervention applied
    """
    intervention = FreezePrecisionIntervention(precision_weights=precision_weights)
    
    result = run_func(
        precision_frozen=True,
        precision_weights=intervention.get_frozen_precision(),
        precision_intervention=intervention,
        context=context,
    )
    
    return {
        "result": result,
        "intervention": intervention.to_dict(),
    }


def run_with_info_gain_disabled(
    run_func: Callable,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run a function with info_gain disabled intervention applied.
    
    Args:
        run_func: Function to run
        context: Optional context dict
    
    Returns:
        Result from run_func with intervention applied
    """
    intervention = DisableInfoGainIntervention()
    
    result = run_func(
        info_gain_disabled=True,
        info_gain_intervention=intervention,
        context=context,
    )
    
    return {
        "result": result,
        "intervention": intervention.to_dict(),
    }


def run_with_open_loop(
    run_func: Callable,
    constant_outcome: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run a function with open_loop intervention applied.
    
    Args:
        run_func: Function to run
        constant_outcome: Optional constant outcome
        context: Optional context dict
    
    Returns:
        Result from run_func with intervention applied
    """
    intervention = OpenLoopIntervention(constant_outcome=constant_outcome)
    
    result = run_func(
        open_loop=True,
        open_loop_intervention=intervention,
        context=context,
    )
    
    return {
        "result": result,
        "intervention": intervention.to_dict(),
    }


def run_with_self_state_removed(
    run_func: Callable,
    constant_state: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run a function with self_state removed intervention applied.
    
    Args:
        run_func: Function to run
        constant_state: Optional constant state to use
        context: Optional context dict
    
    Returns:
        Result from run_func with intervention applied
    """
    intervention = RemoveSelfStateIntervention(constant_state=constant_state)
    
    result = run_func(
        self_state_removed=True,
        constant_self_state=intervention.get_constant_state(),
        self_state_intervention=intervention,
        context=context,
    )
    
    return {
        "result": result,
        "intervention": intervention.to_dict(),
    }


class EnableCyclePriorIntervention:
    """MVP11.4 helper for enabling runtime cycle prior."""

    def __init__(self, reason: str = "enable_cycle_prior_intervention"):
        self.manager = InterventionManager()
        self.manager.enable(
            InterventionType.ENABLE_CYCLE_PRIOR,
            params={"cycle_prior_enabled": True},
            reason=reason,
        )
        self._enabled_at = time.time()

    def is_active(self) -> bool:
        return self.manager.is_cycle_prior_enabled()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled_at": self._enabled_at,
            "is_active": self.is_active(),
            "manager": self.manager.to_dict(),
        }


def create_enable_cycle_prior_intervention(
    reason: str = "enable_cycle_prior_intervention",
) -> EnableCyclePriorIntervention:
    return EnableCyclePriorIntervention(reason=reason)


def run_with_cycle_prior_enabled(
    run_func: Callable,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    intervention = EnableCyclePriorIntervention()
    result = run_func(
        cycle_prior_enabled=True,
        cycle_prior_intervention=intervention,
        context=context,
    )
    return {
        "result": result,
        "intervention": intervention.to_dict(),
    }
