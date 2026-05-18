"""
MVP-6.1 D1+D4: Target-Conditioned Somatic Markers + Recovery Dynamics

Five-dimensional body state representation with:
- Global body state (shared across all targets)
- Target-specific residual layers (per-target conditioning)
- Shrinkage-based regularization (n_obs-aware)
- Parameterized recovery dynamics per dimension (MVP-6.1 D4)

Dimensions:
- energy: Physical/mental energy level [0, 1]
- safety_stress: Perceived safety vs stress [0, 1] (0=stress, 1=safety)
- social_need: Need for social interaction [0, 1]
- novelty_need: Need for novelty/exploration [0, 1]
- focus_fatigue: Mental focus fatigue [0, 1] (0=focused, 1=fatigued)

Architecture:
- global_body: Shared baseline state
- target_residual[target_id]: Per-target conditioned offsets
- shrinkage: Regularizes residuals based on evidence count
- recovery_dynamics: Parameterized decay/recovery rates per dimension

Trace records:
- global_body_delta: Changes to global state
- target_residual_delta: Changes to target residual (if applicable)
- shrinkage_weight: Effective residual weight this round

Telemetry (MVP-6.1 D4):
- recovery_half_life_steps: Steps to recover halfway to baseline
- collapse_duration: Steps spent in low energy/high stress state
"""
import time
import math
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field


@dataclass
class RecoveryDynamics:
    """
    MVP-6.1 D4: Parameterized recovery dynamics for a body dimension.
    
    Each dimension has configurable:
    - recovery_rate: Speed of recovery when below baseline
    - decay_rate: Speed of decay when above baseline
    - half_life_seconds: Time to recover halfway to baseline
    
    These parameters enable:
    1. Per-dimension recovery tuning
    2. Telemetry for recovery diagnostics
    3. AutoTune optimization targets
    """
    recovery_rate: float = 0.001  # Per second toward baseline when below
    decay_rate: float = 0.0005    # Per second toward baseline when above
    half_life_seconds: float = 600.0  # Seconds to recover 50% to baseline
    
    def compute_half_life_steps(self, step_seconds: float = 1.0) -> float:
        """
        Calculate half-life in discrete steps.
        
        Args:
            step_seconds: Duration of one step in seconds
            
        Returns:
            Number of steps to recover halfway to baseline
        """
        if step_seconds <= 0:
            step_seconds = 1.0
        return self.half_life_seconds / step_seconds
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "recovery_rate": self.recovery_rate,
            "decay_rate": self.decay_rate,
            "half_life_seconds": self.half_life_seconds,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryDynamics":
        return cls(
            recovery_rate=data.get("recovery_rate", 0.001),
            decay_rate=data.get("decay_rate", 0.0005),
            half_life_seconds=data.get("half_life_seconds", 600.0),
        )


@dataclass
class BodyStateDimension:
    """
    A single dimension of the body state vector with parameterized recovery.
    
    Attributes:
        value: Current value [0, 1]
        uncertainty: Uncertainty of the value [0, 1]
        last_updated: Timestamp of last update
        recovery_dynamics: Parameterized recovery/decay rates (MVP-6.1 D4)
        baseline: Homeostatic baseline value
    """
    value: float = 0.5
    uncertainty: float = 0.5
    last_updated: float = field(default_factory=time.time)
    
    # MVP-6.1 D4: Parameterized recovery dynamics
    recovery_dynamics: RecoveryDynamics = field(default_factory=RecoveryDynamics)
    baseline: float = 0.5  # Homeostatic baseline
    
    # Legacy aliases for backward compatibility
    @property
    def recovery_rate(self) -> float:
        return self.recovery_dynamics.recovery_rate
    
    @recovery_rate.setter
    def recovery_rate(self, val: float):
        self.recovery_dynamics.recovery_rate = val
    
    @property
    def decay_rate(self) -> float:
        return self.recovery_dynamics.decay_rate
    
    @decay_rate.setter
    def decay_rate(self, val: float):
        self.recovery_dynamics.decay_rate = val
    
    @property
    def regression_rate(self) -> float:
        """Backward compatibility alias for decay_rate."""
        return self.recovery_dynamics.decay_rate
    
    @regression_rate.setter
    def regression_rate(self, val: float):
        self.recovery_dynamics.decay_rate = val
    
    @property
    def half_life_seconds(self) -> float:
        return self.recovery_dynamics.half_life_seconds
    
    @half_life_seconds.setter
    def half_life_seconds(self, val: float):
        self.recovery_dynamics.half_life_seconds = val
    
    def __post_init__(self):
        """Clamp values to valid ranges after initialization."""
        # Handle dict deserialization
        if isinstance(self.recovery_dynamics, dict):
            self.recovery_dynamics = RecoveryDynamics.from_dict(self.recovery_dynamics)
        self._clamp()
    
    def _clamp(self):
        """Clamp value and uncertainty to valid ranges [0, 1]."""
        self.value = max(0.0, min(1.0, self.value))
        self.uncertainty = max(0.0, min(1.0, self.uncertainty))
    
    def update(self, delta: float, observation_uncertainty: float = 0.1) -> "BodyStateDimension":
        """
        Update dimension value with a delta, reducing uncertainty.
        
        Args:
            delta: Change in value (can be positive or negative)
            observation_uncertainty: Uncertainty of this observation [0, 1]
        
        Returns:
            Self for chaining
        """
        self.value += delta
        self._clamp()
        # Observation reduces uncertainty
        self.uncertainty = max(0.0, self.uncertainty - 0.05)
        self.uncertainty = max(self.uncertainty, observation_uncertainty)
        self.last_updated = time.time()
        return self
    
    def set_value(self, value: float, uncertainty: Optional[float] = None) -> "BodyStateDimension":
        """
        Set dimension value directly.
        
        Args:
            value: New value [0, 1]
            uncertainty: Optional new uncertainty [0, 1]
        
        Returns:
            Self for chaining
        """
        self.value = value
        if uncertainty is not None:
            self.uncertainty = uncertainty
        self._clamp()
        self.last_updated = time.time()
        return self
    
    def apply_time_passed(self, seconds: float) -> "BodyStateDimension":
        """
        Apply time-based dynamics: recovery toward baseline or decay.
        
        MVP-6.1 D4: Uses parameterized recovery_dynamics for consistent
        recovery/decay behavior per dimension.
        
        If value is below baseline, it recovers (increases).
        If value is above baseline, it decays (decreases).
        Uncertainty grows over time.
        
        Args:
            seconds: Time passed in seconds
        
        Returns:
            Self for chaining
        """
        rd = self.recovery_dynamics
        
        if self.value < self.baseline:
            # Recovery toward baseline (when below)
            recovery = rd.recovery_rate * seconds
            self.value = min(self.baseline, self.value + recovery)
        elif self.value > self.baseline:
            # Decay toward baseline (when above)
            decay = rd.decay_rate * seconds
            self.value = max(self.baseline, self.value - decay)
        
        # Uncertainty grows over time (we become less certain)
        uncertainty_growth = 0.0001 * seconds
        self.uncertainty = min(1.0, self.uncertainty + uncertainty_growth)
        
        self._clamp()
        return self
    
    def calculate_recovery_half_life_steps(self, step_seconds: float = 1.0) -> float:
        """
        MVP-6.1 D4: Calculate half-life in steps for telemetry.
        
        Args:
            step_seconds: Duration of one step in seconds
            
        Returns:
            Number of steps to recover 50% toward baseline
        """
        return self.recovery_dynamics.compute_half_life_steps(step_seconds)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "value": self.value,
            "uncertainty": self.uncertainty,
            "last_updated": self.last_updated,
            "recovery_dynamics": self.recovery_dynamics.to_dict(),
            "baseline": self.baseline,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BodyStateDimension":
        """Deserialize from dictionary."""
        dim = cls(
            value=data.get("value", 0.5),
            uncertainty=data.get("uncertainty", 0.5),
            last_updated=data.get("last_updated", time.time()),
            recovery_dynamics=RecoveryDynamics.from_dict(data.get("recovery_dynamics", {})),
            baseline=data.get("baseline", 0.5),
        )
        return dim


@dataclass
class TargetResidual:
    """
    Per-target residual offsets for body state dimensions.
    
    These represent learned deviations from global body state
    that are specific to interactions with a particular target.
    
    Attributes:
        safety_stress: Residual for safety_stress dimension
        social_need: Residual for social_need dimension
        novelty_need: Residual for novelty_need dimension
        n_obs: Number of observations for this target
        evidence_strength: Accumulated evidence strength [0, 1]
        last_updated: Timestamp of last update
    """
    safety_stress: float = 0.0  # Residual offset [-1, 1]
    social_need: float = 0.0    # Residual offset [-1, 1]
    novelty_need: float = 0.0   # Residual offset [-1, 1]
    n_obs: int = 0              # Number of observations
    evidence_strength: float = 0.0  # Accumulated evidence [0, 1]
    last_updated: float = field(default_factory=time.time)
    
    def __post_init__(self):
        """Clamp residual values."""
        self._clamp()
    
    def _clamp(self):
        """Clamp residuals to valid ranges."""
        self.safety_stress = max(-1.0, min(1.0, self.safety_stress))
        self.social_need = max(-1.0, min(1.0, self.social_need))
        self.novelty_need = max(-1.0, min(1.0, self.novelty_need))
        self.evidence_strength = max(0.0, min(1.0, self.evidence_strength))
    
    def update(self, safety_stress_delta: float = 0.0, 
               social_need_delta: float = 0.0,
               novelty_need_delta: float = 0.0,
               evidence_increment: float = 0.1) -> "TargetResidual":
        """
        Update residual values with new observations.
        
        Args:
            safety_stress_delta: Change in safety_stress residual
            social_need_delta: Change in social_need residual
            novelty_need_delta: Change in novelty_need residual
            evidence_increment: Amount to increase evidence strength
        
        Returns:
            Self for chaining
        """
        self.safety_stress += safety_stress_delta
        self.social_need += social_need_delta
        self.novelty_need += novelty_need_delta
        self.n_obs += 1
        self.evidence_strength = min(1.0, self.evidence_strength + evidence_increment)
        self.last_updated = time.time()
        self._clamp()
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "safety_stress": self.safety_stress,
            "social_need": self.social_need,
            "novelty_need": self.novelty_need,
            "n_obs": self.n_obs,
            "evidence_strength": self.evidence_strength,
            "last_updated": self.last_updated,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TargetResidual":
        """Deserialize from dictionary."""
        return cls(
            safety_stress=data.get("safety_stress", 0.0),
            social_need=data.get("social_need", 0.0),
            novelty_need=data.get("novelty_need", 0.0),
            n_obs=data.get("n_obs", 0),
            evidence_strength=data.get("evidence_strength", 0.0),
            last_updated=data.get("last_updated", time.time()),
        )


class Shrinkage:
    """
    Shrinkage-based regularization for target residuals.
    
    Implements: residual_effective = shrink(residual_raw, n_obs, k)
    
    When n_obs is small, residual is shrunk toward 0 (not trusted).
    When n_obs is large, residual approaches raw value (trusted).
    
    shrinkage_weight = n_obs / (n_obs + k)
    residual_effective = residual_raw * shrinkage_weight
    """
    
    def __init__(self, k: float = 10.0):
        """
        Initialize shrinkage with hyperparameter k.
        
        Args:
            k: Shrinkage parameter. Higher k = more conservative (more observations needed
               before residual is trusted). Lower k = more aggressive (residual trusted sooner).
        """
        self.k = max(1.0, k)  # Ensure k >= 1
    
    def compute_weight(self, n_obs: int) -> float:
        """
        Compute shrinkage weight based on observation count.
        
        Args:
            n_obs: Number of observations
        
        Returns:
            Shrinkage weight [0, 1]
        """
        if n_obs <= 0:
            return 0.0
        return n_obs / (n_obs + self.k)
    
    def apply(self, residual_raw: float, n_obs: int) -> float:
        """
        Apply shrinkage to a raw residual value.
        
        Args:
            residual_raw: Raw residual value
            n_obs: Number of observations
        
        Returns:
            Shrunk residual value
        """
        weight = self.compute_weight(n_obs)
        return residual_raw * weight
    
    def apply_to_target_residual(self, residual: TargetResidual) -> Dict[str, float]:
        """
        Apply shrinkage to all dimensions of a target residual.
        
        Args:
            residual: TargetResidual to shrink
        
        Returns:
            Dictionary of shrunk residual values
        """
        weight = self.compute_weight(residual.n_obs)
        return {
            "safety_stress": residual.safety_stress * weight,
            "social_need": residual.social_need * weight,
            "novelty_need": residual.novelty_need * weight,
            "shrinkage_weight": weight,
            "n_obs": residual.n_obs,
        }


# MVP-6.1 D4: Recovery telemetry for diagnostics
@dataclass
class RecoveryTelemetry:
    """
    Telemetry data for recovery dynamics monitoring.
    
    Tracks:
    - recovery_half_life_steps: Steps to recover 50% to baseline
    - collapse_duration: Steps spent in collapsed state (low energy/high stress)
    - recovery_trajectory: History of recovery for analysis
    """
    dimension_name: str
    half_life_steps: float = 0.0
    collapse_duration: int = 0
    recovery_trajectory: List[Tuple[int, float]] = field(default_factory=list)
    is_collapsed: bool = False
    collapse_start_step: int = -1
    
    def record_step(self, step: int, value: float, collapse_threshold: float = 0.3):
        """
        Record a step for telemetry analysis.
        
        Args:
            step: Current step number
            value: Current dimension value
            collapse_threshold: Threshold below which state is considered collapsed
        """
        self.recovery_trajectory.append((step, value))
        
        # Track collapse duration
        if value < collapse_threshold:
            if not self.is_collapsed:
                self.is_collapsed = True
                self.collapse_start_step = step
        else:
            if self.is_collapsed:
                # End of collapse period
                self.collapse_duration += step - self.collapse_start_step
                self.is_collapsed = False
                self.collapse_start_step = -1
    
    def finalize(self, final_step: int):
        """Finalize telemetry, accounting for ongoing collapse."""
        if self.is_collapsed and self.collapse_start_step >= 0:
            self.collapse_duration += final_step - self.collapse_start_step
            self.is_collapsed = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension_name": self.dimension_name,
            "half_life_steps": self.half_life_steps,
            "collapse_duration": self.collapse_duration,
            "recovery_trajectory": self.recovery_trajectory[-100:],  # Keep last 100
            "is_collapsed": self.is_collapsed,
        }


@dataclass
class BodyStateVector:
    """
    Five-dimensional virtual body state vector with target conditioning.
    
    Architecture:
    - Global dimensions: energy, focus_fatigue (primarily global)
    - Global baselines: safety_stress, social_need, novelty_need
    - Target residuals: Per-target offsets for safety_stress, social_need, novelty_need
    - Recovery dynamics: Parameterized per-dimension recovery (MVP-6.1 D4)
    
    Dimensions:
    - energy: Physical/mental energy [0, 1] (baseline 0.7)
    - safety_stress: Safety vs stress [0, 1] (baseline 0.6, 1=safety)
    - social_need: Need for social interaction [0, 1] (baseline 0.5)
    - novelty_need: Need for novelty [0, 1] (baseline 0.5)
    - focus_fatigue: Focus fatigue [0, 1] (baseline 0.3, higher=more fatigued)
    """
    
    # Each dimension with specific defaults and recovery dynamics
    energy: BodyStateDimension = field(default_factory=lambda: BodyStateDimension(
        value=0.7, uncertainty=0.3, baseline=0.7,
        recovery_dynamics=RecoveryDynamics(recovery_rate=0.001, decay_rate=0.0003, half_life_seconds=300)
    ))
    safety_stress: BodyStateDimension = field(default_factory=lambda: BodyStateDimension(
        value=0.6, uncertainty=0.4, baseline=0.6,
        recovery_dynamics=RecoveryDynamics(recovery_rate=0.0008, decay_rate=0.0005, half_life_seconds=600)
    ))
    social_need: BodyStateDimension = field(default_factory=lambda: BodyStateDimension(
        value=0.5, uncertainty=0.5, baseline=0.5,
        recovery_dynamics=RecoveryDynamics(recovery_rate=0.0005, decay_rate=0.0005, half_life_seconds=900)
    ))
    novelty_need: BodyStateDimension = field(default_factory=lambda: BodyStateDimension(
        value=0.5, uncertainty=0.5, baseline=0.5,
        recovery_dynamics=RecoveryDynamics(recovery_rate=0.0003, decay_rate=0.0003, half_life_seconds=1200)
    ))
    focus_fatigue: BodyStateDimension = field(default_factory=lambda: BodyStateDimension(
        value=0.3, uncertainty=0.4, baseline=0.3,
        recovery_dynamics=RecoveryDynamics(recovery_rate=0.002, decay_rate=0.001, half_life_seconds=180)
    ))
    
    # Target-specific residual layers
    target_residuals: Dict[str, TargetResidual] = field(default_factory=dict)
    
    # Shrinkage hyperparameter (tunable)
    shrinkage_k: float = 10.0
    
    # MVP-6.1 D4: Recovery telemetry
    recovery_telemetry: Dict[str, RecoveryTelemetry] = field(default_factory=dict)
    _step_counter: int = 0
    
    def __post_init__(self):
        """Ensure all dimensions are properly initialized."""
        # Ensure each dimension is a BodyStateDimension instance
        if not isinstance(self.energy, BodyStateDimension):
            if isinstance(self.energy, dict):
                self.energy = BodyStateDimension.from_dict(self.energy)
            else:
                self.energy = BodyStateDimension()
        if not isinstance(self.safety_stress, BodyStateDimension):
            if isinstance(self.safety_stress, dict):
                self.safety_stress = BodyStateDimension.from_dict(self.safety_stress)
            else:
                self.safety_stress = BodyStateDimension()
        if not isinstance(self.social_need, BodyStateDimension):
            if isinstance(self.social_need, dict):
                self.social_need = BodyStateDimension.from_dict(self.social_need)
            else:
                self.social_need = BodyStateDimension()
        if not isinstance(self.novelty_need, BodyStateDimension):
            if isinstance(self.novelty_need, dict):
                self.novelty_need = BodyStateDimension.from_dict(self.novelty_need)
            else:
                self.novelty_need = BodyStateDimension()
        if not isinstance(self.focus_fatigue, BodyStateDimension):
            if isinstance(self.focus_fatigue, dict):
                self.focus_fatigue = BodyStateDimension.from_dict(self.focus_fatigue)
            else:
                self.focus_fatigue = BodyStateDimension()
        
        # Deserialize target residuals if needed
        if self.target_residuals:
            deserialized = {}
            for target_id, residual in self.target_residuals.items():
                if isinstance(residual, dict):
                    deserialized[target_id] = TargetResidual.from_dict(residual)
                else:
                    deserialized[target_id] = residual
            self.target_residuals = deserialized
        else:
            self.target_residuals = {}
        
        # Initialize recovery telemetry
        self._init_recovery_telemetry()
    
    def _init_recovery_telemetry(self):
        """Initialize recovery telemetry for all dimensions."""
        for dim_name in ["energy", "safety_stress", "social_need", "novelty_need", "focus_fatigue"]:
            if dim_name not in self.recovery_telemetry:
                self.recovery_telemetry[dim_name] = RecoveryTelemetry(dimension_name=dim_name)
    
    def get_target_residual(self, target_id: str) -> TargetResidual:
        """
        Get or create target residual for a specific target.
        
        Args:
            target_id: Target identifier
        
        Returns:
            TargetResidual for this target
        """
        if target_id not in self.target_residuals:
            self.target_residuals[target_id] = TargetResidual()
        return self.target_residuals[target_id]
    
    def get_effective_value(self, dimension: str, target_id: Optional[str] = None) -> float:
        """
        Get effective body state value, optionally target-conditioned.
        
        For target-conditioned dimensions (safety_stress, social_need, novelty_need),
        applies shrinkage-regularized residual if target_id is provided.
        
        Args:
            dimension: Dimension name
            target_id: Optional target for conditioning
        
        Returns:
            Effective value [0, 1]
        """
        # Get global base value
        dim = getattr(self, dimension, None)
        if dim is None:
            return 0.5
        
        base_value = dim.value
        
        # Apply target residual for target-conditioned dimensions
        if target_id and dimension in ("safety_stress", "social_need", "novelty_need"):
            residual = self.target_residuals.get(target_id)
            if residual:
                shrinkage = Shrinkage(self.shrinkage_k)
                shrunk = shrinkage.apply_to_target_residual(residual)
                residual_value = shrunk.get(dimension, 0.0)
                # Apply residual (clamped to valid range)
                base_value = max(0.0, min(1.0, base_value + residual_value))
        
        return base_value
    
    def get_effective_values(self, target_id: Optional[str] = None) -> Dict[str, float]:
        """
        Get all effective body state values, optionally target-conditioned.
        
        Args:
            target_id: Optional target for conditioning
        
        Returns:
            Dictionary of effective values
        """
        return {
            "energy": self.get_effective_value("energy", target_id),
            "safety_stress": self.get_effective_value("safety_stress", target_id),
            "social_need": self.get_effective_value("social_need", target_id),
            "novelty_need": self.get_effective_value("novelty_need", target_id),
            "focus_fatigue": self.get_effective_value("focus_fatigue", target_id),
        }
    
    def apply_time_passed(self, seconds: float) -> "BodyStateVector":
        """
        Apply time-based dynamics to all dimensions.
        
        MVP-6.1 D4: Uses parameterized recovery dynamics per dimension.
        Also updates recovery telemetry.
        
        Args:
            seconds: Time passed in seconds
        
        Returns:
            Self for chaining
        """
        self.energy.apply_time_passed(seconds)
        self.safety_stress.apply_time_passed(seconds)
        self.social_need.apply_time_passed(seconds)
        self.novelty_need.apply_time_passed(seconds)
        self.focus_fatigue.apply_time_passed(seconds)
        
        # MVP-6.1 D4: Update recovery telemetry
        self._update_recovery_telemetry()
        
        return self
    
    def _update_recovery_telemetry(self):
        """Update recovery telemetry for all dimensions."""
        self._step_counter += 1
        
        for dim_name, dim in [
            ("energy", self.energy),
            ("safety_stress", self.safety_stress),
            ("social_need", self.social_need),
            ("novelty_need", self.novelty_need),
            ("focus_fatigue", self.focus_fatigue),
        ]:
            if dim_name in self.recovery_telemetry:
                telemetry = self.recovery_telemetry[dim_name]
                # Update half-life from current dynamics
                telemetry.half_life_steps = dim.calculate_recovery_half_life_steps()
                # Record step
                telemetry.record_step(self._step_counter, dim.value)
    
    def get_recovery_telemetry(self) -> Dict[str, Dict[str, Any]]:
        """
        MVP-6.1 D4: Get recovery telemetry for all dimensions.
        
        Returns:
            Dictionary mapping dimension names to telemetry data
        """
        # Finalize any ongoing collapses
        for telemetry in self.recovery_telemetry.values():
            telemetry.finalize(self._step_counter)
        
        return {
            name: telemetry.to_dict()
            for name, telemetry in self.recovery_telemetry.items()
        }
    
    def get_recovery_half_life_steps(self) -> Dict[str, float]:
        """
        MVP-6.1 D4: Get recovery half-life in steps for all dimensions.
        
        Returns:
            Dictionary mapping dimension names to half-life steps
        """
        return {
            "energy": self.energy.calculate_recovery_half_life_steps(),
            "safety_stress": self.safety_stress.calculate_recovery_half_life_steps(),
            "social_need": self.social_need.calculate_recovery_half_life_steps(),
            "novelty_need": self.novelty_need.calculate_recovery_half_life_steps(),
            "focus_fatigue": self.focus_fatigue.calculate_recovery_half_life_steps(),
        }
    
    def get_collapse_duration(self) -> Dict[str, int]:
        """
        MVP-6.1 D4: Get collapse duration (steps spent below threshold) for all dimensions.
        
        Returns:
            Dictionary mapping dimension names to collapse duration in steps
        """
        # Finalize any ongoing collapses
        for telemetry in self.recovery_telemetry.values():
            telemetry.finalize(self._step_counter)
        
        return {
            name: telemetry.collapse_duration
            for name, telemetry in self.recovery_telemetry.items()
        }
    
    def update_from_event(self, event_type: str, event_subtype: Optional[str] = None,
                          meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Update body state based on event type and subtype.
        
        Args:
            event_type: Type of event (user_message, assistant_reply, world_event)
            event_subtype: Subtype for world_events
            meta: Additional metadata including target_id for residual updates
        
        Returns:
            Trace record with deltas and shrinkage info
        """
        target_id = meta.get("target_id") if meta else None
        smoke_mode = bool(meta and str(meta.get("category", "")).lower() == "smoke" and str(meta.get("scenario_name", "")).lower().startswith("smoke_"))

        # Production-path tunables (autotune-visible)
        try:
            from emotiond import config as _cfg
            residual_update_gain = float(_cfg.get_auto_tune_param("residual_update_gain", 1.0))
            residual_evidence_increment = float(_cfg.get_auto_tune_param("residual_evidence_increment", 0.1))
        except Exception:
            residual_update_gain = 1.0
            residual_evidence_increment = 0.1

        # Smoke diagnostics boost (guarded by dual gate)
        residual_test_gain = 5.0 if smoke_mode else 1.0
        evidence_increment = 0.3 if smoke_mode else residual_evidence_increment
        
        trace = {
            "global_body_delta": {},
            "target_residual_delta": None,
            "shrinkage_weight": None,
        }
        
        deltas = {
            "energy": 0.0,
            "safety_stress": 0.0,
            "social_need": 0.0,
            "novelty_need": 0.0,
            "focus_fatigue": 0.0,
        }
        
        if event_type == "user_message":
            # User interaction affects energy and focus
            deltas["energy"] = -0.02  # Small energy cost
            deltas["focus_fatigue"] = 0.01  # Slight fatigue
            deltas["social_need"] = -0.03  # Social need partially satisfied
            self.energy.update(deltas["energy"])
            self.focus_fatigue.update(deltas["focus_fatigue"])
            self.social_need.update(deltas["social_need"])
            
        elif event_type == "assistant_reply":
            # Responding costs energy and increases fatigue
            deltas["energy"] = -0.03
            deltas["focus_fatigue"] = 0.02
            self.energy.update(deltas["energy"])
            self.focus_fatigue.update(deltas["focus_fatigue"])
            
        elif event_type == "world_event" and event_subtype:
            subtype_deltas = self._get_subtype_deltas(event_subtype, meta)
            deltas.update(subtype_deltas)
            
            # Apply global deltas
            if deltas["energy"]:
                self.energy.update(deltas["energy"])
            if deltas["focus_fatigue"]:
                self.focus_fatigue.update(deltas["focus_fatigue"])
            
            # Apply target-conditioned deltas to residuals if target specified
            if target_id and any(deltas.get(d) for d in ["safety_stress", "social_need", "novelty_need"]):
                residual = self.get_target_residual(target_id)
                
                # Store pre-update state for trace
                pre_n_obs = residual.n_obs
                
                # Update residual (smoke scenarios can boost signal for sensitivity probes)
                residual.update(
                    safety_stress_delta=deltas.get("safety_stress", 0.0) * residual_update_gain * residual_test_gain,
                    social_need_delta=deltas.get("social_need", 0.0) * residual_update_gain * residual_test_gain,
                    novelty_need_delta=deltas.get("novelty_need", 0.0) * residual_update_gain * residual_test_gain,
                    evidence_increment=evidence_increment
                )
                
                # Compute shrinkage
                shrinkage = Shrinkage(self.shrinkage_k)
                trace["shrinkage_weight"] = shrinkage.compute_weight(residual.n_obs)
                trace["target_residual_delta"] = {
                    "target_id": target_id,
                    "safety_stress": deltas.get("safety_stress", 0.0),
                    "social_need": deltas.get("social_need", 0.0),
                    "novelty_need": deltas.get("novelty_need", 0.0),
                    "n_obs_before": pre_n_obs,
                    "n_obs_after": residual.n_obs,
                }
            else:
                # Apply global updates for non-targeted events
                if deltas["safety_stress"]:
                    self.safety_stress.update(deltas["safety_stress"])
                if deltas["social_need"]:
                    self.social_need.update(deltas["social_need"])
                if deltas["novelty_need"]:
                    self.novelty_need.update(deltas["novelty_need"])
            
            if event_subtype == "time_passed":
                # Time passage has its own dynamics handled by apply_time_passed
                seconds = meta.get("seconds", 60) if meta else 60
                self.apply_time_passed(seconds)
        
        trace["global_body_delta"] = {k: v for k, v in deltas.items() if v != 0.0}
        return trace
    
    def _get_subtype_deltas(self, subtype: str, meta: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
        """Get deltas for world event subtypes."""
        deltas = {
            "energy": 0.0,
            "safety_stress": 0.0,
            "social_need": 0.0,
            "novelty_need": 0.0,
            "focus_fatigue": 0.0,
        }
        
        if subtype == "care":
            deltas["energy"] = 0.05
            deltas["safety_stress"] = 0.10
            deltas["social_need"] = -0.05
        elif subtype == "rejection":
            deltas["energy"] = -0.08
            deltas["safety_stress"] = -0.15
            deltas["social_need"] = 0.10
        elif subtype == "betrayal":
            deltas["energy"] = -0.15
            deltas["safety_stress"] = -0.25
            deltas["social_need"] = 0.05
            deltas["focus_fatigue"] = 0.05
        elif subtype == "apology":
            deltas["safety_stress"] = 0.08
            deltas["energy"] = 0.02
        elif subtype == "repair_success":
            deltas["energy"] = 0.05
            deltas["safety_stress"] = 0.12
            deltas["social_need"] = -0.03
        elif subtype == "ignored":
            deltas["social_need"] = 0.08
            deltas["safety_stress"] = -0.05
            deltas["energy"] = -0.03
        elif subtype == "novelty":
            deltas["novelty_need"] = -0.10  # Novelty satisfied
            deltas["energy"] = 0.03
        elif subtype == "routine":
            deltas["novelty_need"] = 0.05  # Novelty increases with routine
            deltas["focus_fatigue"] = -0.02  # Routine reduces fatigue
        
        return deltas
    
    def get_energy_budget_factor(self) -> float:
        """
        Calculate energy budget factor from body state energy.
        
        This provides compatibility with the existing energy_budget system.
        energy_budget in EmotionState is derived from body_state.energy.
        
        Returns:
            Energy budget factor [0, 1] suitable for regulation_budget
        """
        # Map energy [0, 1] to budget factor with a slight curve
        # Higher energy = higher budget
        energy = self.energy.value
        # Apply a gentle curve: budget = energy^0.5 (square root)
        # This means low energy has disproportionate impact on budget
        return math.sqrt(energy)
    
    def get_summary(self, target_id: Optional[str] = None) -> Dict[str, float]:
        """Get a summary of all dimension values (global or target-conditioned)."""
        return self.get_effective_values(target_id)
    
    def get_uncertainties(self) -> Dict[str, float]:
        """Get uncertainties for all dimensions."""
        return {
            "energy": self.energy.uncertainty,
            "safety_stress": self.safety_stress.uncertainty,
            "social_need": self.social_need.uncertainty,
            "novelty_need": self.novelty_need.uncertainty,
            "focus_fatigue": self.focus_fatigue.uncertainty,
        }
    
    def get_target_residual_summary(self, target_id: str) -> Optional[Dict[str, Any]]:
        """
        Get summary of target residual for a specific target.
        
        Args:
            target_id: Target identifier
        
        Returns:
            Dictionary with raw residual, shrunk residual, and metadata
        """
        residual = self.target_residuals.get(target_id)
        if not residual:
            return None
        
        shrinkage = Shrinkage(self.shrinkage_k)
        shrunk = shrinkage.apply_to_target_residual(residual)
        
        return {
            "target_id": target_id,
            "raw_residual": {
                "safety_stress": residual.safety_stress,
                "social_need": residual.social_need,
                "novelty_need": residual.novelty_need,
            },
            "shrunk_residual": {
                "safety_stress": shrunk["safety_stress"],
                "social_need": shrunk["social_need"],
                "novelty_need": shrunk["novelty_need"],
            },
            "shrinkage_weight": shrunk["shrinkage_weight"],
            "n_obs": residual.n_obs,
            "evidence_strength": residual.evidence_strength,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "energy": self.energy.to_dict(),
            "safety_stress": self.safety_stress.to_dict(),
            "social_need": self.social_need.to_dict(),
            "novelty_need": self.novelty_need.to_dict(),
            "focus_fatigue": self.focus_fatigue.to_dict(),
            "target_residuals": {k: v.to_dict() for k, v in self.target_residuals.items()},
            "shrinkage_k": self.shrinkage_k,
            "recovery_telemetry": {k: v.to_dict() for k, v in self.recovery_telemetry.items()},
            "_step_counter": self._step_counter,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BodyStateVector":
        """Deserialize from dictionary."""
        vector = cls(
            energy=BodyStateDimension.from_dict(data.get("energy", {})),
            safety_stress=BodyStateDimension.from_dict(data.get("safety_stress", {})),
            social_need=BodyStateDimension.from_dict(data.get("social_need", {})),
            novelty_need=BodyStateDimension.from_dict(data.get("novelty_need", {})),
            focus_fatigue=BodyStateDimension.from_dict(data.get("focus_fatigue", {})),
            target_residuals=data.get("target_residuals", {}),
            shrinkage_k=data.get("shrinkage_k", 10.0),
        )
        # Restore telemetry if present
        if "recovery_telemetry" in data:
            for name, tel_data in data["recovery_telemetry"].items():
                vector.recovery_telemetry[name] = RecoveryTelemetry(
                    dimension_name=tel_data.get("dimension_name", name),
                    half_life_steps=tel_data.get("half_life_steps", 0.0),
                    collapse_duration=tel_data.get("collapse_duration", 0),
                )
        if "_step_counter" in data:
            vector._step_counter = data["_step_counter"]
        return vector
    
    def clone(self) -> "BodyStateVector":
        """Create a deep copy of this body state vector."""
        return BodyStateVector.from_dict(self.to_dict())


# Global body state instance (singleton pattern)
_global_body_state: Optional[BodyStateVector] = None


def get_body_state() -> BodyStateVector:
    """Get the global body state vector (creates if needed)."""
    global _global_body_state
    if _global_body_state is None:
        _global_body_state = BodyStateVector()
    return _global_body_state


def set_body_state(body_state: BodyStateVector) -> None:
    """Set the global body state vector."""
    global _global_body_state
    _global_body_state = body_state


def reset_body_state() -> BodyStateVector:
    """Reset the global body state vector to defaults."""
    global _global_body_state
    _global_body_state = BodyStateVector()
    return _global_body_state


def get_shrinkage(k: Optional[float] = None) -> Shrinkage:
    """
    Get a shrinkage instance.
    
    Args:
        k: Optional override for shrinkage parameter
    
    Returns:
        Shrinkage instance
    """
    if k is None:
        k = get_body_state().shrinkage_k
    return Shrinkage(k)


# MVP-6.1 D4: Recovery dynamics configuration helpers
def set_dimension_recovery_params(
    dimension: str,
    recovery_rate: Optional[float] = None,
    decay_rate: Optional[float] = None,
    half_life_seconds: Optional[float] = None
) -> None:
    """
    Set recovery dynamics parameters for a dimension.
    
    Args:
        dimension: Dimension name (energy, safety_stress, social_need, novelty_need, focus_fatigue)
        recovery_rate: Recovery rate toward baseline when below
        decay_rate: Decay rate toward baseline when above
        half_life_seconds: Half-life in seconds for telemetry
    """
    body = get_body_state()
    dim = getattr(body, dimension, None)
    if dim is None:
        raise ValueError(f"Unknown dimension: {dimension}")
    
    if recovery_rate is not None:
        dim.recovery_dynamics.recovery_rate = recovery_rate
    if decay_rate is not None:
        dim.recovery_dynamics.decay_rate = decay_rate
    if half_life_seconds is not None:
        dim.recovery_dynamics.half_life_seconds = half_life_seconds


def get_recovery_diagnostics() -> Dict[str, Any]:
    """
    Get comprehensive recovery diagnostics for all dimensions.
    
    Returns:
        Dictionary with recovery_half_life_steps, collapse_duration, and telemetry
    """
    body = get_body_state()
    return {
        "recovery_half_life_steps": body.get_recovery_half_life_steps(),
        "collapse_duration": body.get_collapse_duration(),
        "telemetry": body.get_recovery_telemetry(),
        "current_values": {
            "energy": body.energy.value,
            "safety_stress": body.safety_stress.value,
            "social_need": body.social_need.value,
            "novelty_need": body.novelty_need.value,
            "focus_fatigue": body.focus_fatigue.value,
        },
        "baselines": {
            "energy": body.energy.baseline,
            "safety_stress": body.safety_stress.baseline,
            "social_need": body.social_need.baseline,
            "novelty_need": body.novelty_need.baseline,
            "focus_fatigue": body.focus_fatigue.baseline,
        },
    }
