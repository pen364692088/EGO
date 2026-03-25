"""
MVP-6.2 D3: Rhythm Scheduler (节律/耐心/冷却)

Implements "when to prompt / when to speak / when to wait" rhythm control.

Input signals:
- time_passed: Time since last interaction
- user_burst: User speaking continuously
- tool_failure_rate: Recent tool failure frequency
- energy/focus_fatigue: Body state dimensions
- boredom/curiosity: Intrinsic motivation signals
- safety_stress: Safety/stress level

Output rhythm actions:
- respond_now: Normal response
- ask_clarify_then_wait: Request clarification and wait
- cooldown: Brief response with delayed follow-up

Requirements:
- Rhythm decisions affect body_state (e.g., over-interruption → focus_fatigue↑)
- Parameters纳入 AutoTune
- Full traceability in telemetry
"""
import time
import math
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum


class RhythmAction(Enum):
    """Rhythm action outcomes."""
    RESPOND_NOW = "respond_now"
    ASK_CLARIFY_THEN_WAIT = "ask_clarify_then_wait"
    COOLDOWN = "cooldown"


@dataclass
class RhythmSignal:
    """Input signals for rhythm decision."""
    time_passed_seconds: float = 0.0
    user_burst_count: int = 0  # Consecutive user messages
    tool_failure_count: int = 0  # Recent tool failures
    tool_attempt_count: int = 0  # Recent tool attempts
    energy: float = 0.5
    focus_fatigue: float = 0.3
    boredom: float = 0.0
    curiosity: float = 0.0
    safety_stress: float = 0.5
    last_rhythm_action: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "time_passed_seconds": self.time_passed_seconds,
            "user_burst_count": self.user_burst_count,
            "tool_failure_count": self.tool_failure_count,
            "tool_attempt_count": self.tool_attempt_count,
            "energy": self.energy,
            "focus_fatigue": self.focus_fatigue,
            "boredom": self.boredom,
            "curiosity": self.curiosity,
            "safety_stress": self.safety_stress,
            "last_rhythm_action": self.last_rhythm_action,
        }


@dataclass
class RhythmParameters:
    """Tunable parameters for rhythm scheduling (纳入 AutoTune)."""
    # Patience thresholds
    patience_base_seconds: float = 2.0  # Base patience before responding
    patience_fatigue_factor: float = 0.5  # Multiplier per unit fatigue
    patience_energy_factor: float = 0.3  # Multiplier per unit energy deficit
    
    # Burst handling
    burst_threshold: int = 3  # Messages to trigger burst mode
    burst_cooldown_multiplier: float = 2.0  # Patience multiplier during burst
    
    # Tool failure handling
    tool_failure_threshold: float = 0.5  # Failure rate to trigger caution
    tool_failure_cooldown_multiplier: float = 3.0  # Patience multiplier
    
    # Fatigue thresholds
    focus_fatigue_respond_threshold: float = 0.7  # Above this, prefer cooldown
    focus_fatigue_clarify_threshold: float = 0.85  # Above this, force clarify
    
    # Energy thresholds
    energy_respond_threshold: float = 0.3  # Below this, prefer cooldown
    energy_clarify_threshold: float = 0.15  # Below this, force clarify
    
    # Safety/stress thresholds
    safety_stress_respond_threshold: float = 0.3  # Below this, prefer cooldown
    
    # Boredom/curiosity modulation
    boredom_patience_reduction: float = 0.3  # Reduce patience when bored
    curiosity_patience_increase: float = 0.2  # Increase patience when curious
    
    # Cooldown duration
    cooldown_duration_seconds: float = 5.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "patience_base_seconds": self.patience_base_seconds,
            "patience_fatigue_factor": self.patience_fatigue_factor,
            "patience_energy_factor": self.patience_energy_factor,
            "burst_threshold": self.burst_threshold,
            "burst_cooldown_multiplier": self.burst_cooldown_multiplier,
            "tool_failure_threshold": self.tool_failure_threshold,
            "tool_failure_cooldown_multiplier": self.tool_failure_cooldown_multiplier,
            "focus_fatigue_respond_threshold": self.focus_fatigue_respond_threshold,
            "focus_fatigue_clarify_threshold": self.focus_fatigue_clarify_threshold,
            "energy_respond_threshold": self.energy_respond_threshold,
            "energy_clarify_threshold": self.energy_clarify_threshold,
            "safety_stress_respond_threshold": self.safety_stress_respond_threshold,
            "boredom_patience_reduction": self.boredom_patience_reduction,
            "curiosity_patience_increase": self.curiosity_patience_increase,
            "cooldown_duration_seconds": self.cooldown_duration_seconds,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RhythmParameters":
        return cls(
            patience_base_seconds=data.get("patience_base_seconds", 2.0),
            patience_fatigue_factor=data.get("patience_fatigue_factor", 0.5),
            patience_energy_factor=data.get("patience_energy_factor", 0.3),
            burst_threshold=data.get("burst_threshold", 3),
            burst_cooldown_multiplier=data.get("burst_cooldown_multiplier", 2.0),
            tool_failure_threshold=data.get("tool_failure_threshold", 0.5),
            tool_failure_cooldown_multiplier=data.get("tool_failure_cooldown_multiplier", 3.0),
            focus_fatigue_respond_threshold=data.get("focus_fatigue_respond_threshold", 0.7),
            focus_fatigue_clarify_threshold=data.get("focus_fatigue_clarify_threshold", 0.85),
            energy_respond_threshold=data.get("energy_respond_threshold", 0.3),
            energy_clarify_threshold=data.get("energy_clarify_threshold", 0.15),
            safety_stress_respond_threshold=data.get("safety_stress_respond_threshold", 0.3),
            boredom_patience_reduction=data.get("boredom_patience_reduction", 0.3),
            curiosity_patience_increase=data.get("curiosity_patience_increase", 0.2),
            cooldown_duration_seconds=data.get("cooldown_duration_seconds", 5.0),
        )


@dataclass
class RhythmDecision:
    """Output of rhythm scheduling decision."""
    action: RhythmAction
    patience_required: float  # Seconds to wait before acting
    reason: str  # Human-readable reason
    confidence: float  # Decision confidence [0, 1]
    body_state_impacts: Dict[str, float]  # Expected impacts on body state
    signal_snapshot: RhythmSignal  # Input signals at decision time
    parameters_snapshot: RhythmParameters  # Parameters used
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value,
            "patience_required": self.patience_required,
            "reason": self.reason,
            "confidence": self.confidence,
            "body_state_impacts": self.body_state_impacts,
            "signal_snapshot": self.signal_snapshot.to_dict(),
            "parameters_snapshot": self.parameters_snapshot.to_dict(),
            "timestamp": self.timestamp,
        }


class RhythmScheduler:
    """
    MVP-6.2 D3: Rhythm Scheduler
    
    Determines when to respond, when to ask for clarification,
    and when to enter cooldown based on body state and interaction patterns.
    """
    
    def __init__(self, parameters: Optional[RhythmParameters] = None):
        self.parameters = parameters or RhythmParameters()
        self._decision_history: List[RhythmDecision] = []
        self._max_history = 100
    
    def schedule(self, signal: RhythmSignal) -> RhythmDecision:
        """
        Determine the appropriate rhythm action based on input signals.
        
        Args:
            signal: Current rhythm signals
            
        Returns:
            RhythmDecision with action, patience, and impacts
        """
        params = self.parameters
        
        # Calculate effective patience threshold
        patience = self._calculate_patience_threshold(signal, params)
        
        # Determine action based on conditions
        action, reason, confidence = self._determine_action(signal, params, patience)
        
        # Calculate body state impacts
        impacts = self._calculate_body_state_impacts(signal, action, params)
        
        decision = RhythmDecision(
            action=action,
            patience_required=patience,
            reason=reason,
            confidence=confidence,
            body_state_impacts=impacts,
            signal_snapshot=signal,
            parameters_snapshot=params,
        )
        
        self._record_decision(decision)
        return decision
    
    def _calculate_patience_threshold(
        self, signal: RhythmSignal, params: RhythmParameters
    ) -> float:
        """Calculate the patience threshold based on signals."""
        patience = params.patience_base_seconds
        
        # Fatigue increases patience (we wait longer)
        fatigue_penalty = signal.focus_fatigue * params.patience_fatigue_factor
        patience *= (1 + fatigue_penalty)
        
        # Low energy increases patience
        energy_deficit = max(0, 0.5 - signal.energy)
        energy_penalty = energy_deficit * params.patience_energy_factor
        patience *= (1 + energy_penalty)
        
        # User burst increases patience
        if signal.user_burst_count >= params.burst_threshold:
            patience *= params.burst_cooldown_multiplier
        
        # High tool failure rate increases patience
        tool_failure_rate = self._calculate_tool_failure_rate(signal)
        if tool_failure_rate >= params.tool_failure_threshold:
            patience *= params.tool_failure_cooldown_multiplier
        
        # Boredom reduces patience (we want to respond faster)
        boredom_factor = 1 - (signal.boredom * params.boredom_patience_reduction)
        patience *= max(0.5, boredom_factor)
        
        # Curiosity increases patience (we want to wait for more info)
        curiosity_factor = 1 + (signal.curiosity * params.curiosity_patience_increase)
        patience *= curiosity_factor
        
        return max(0.1, patience)  # Minimum 0.1s patience
    
    def _calculate_tool_failure_rate(self, signal: RhythmSignal) -> float:
        """Calculate recent tool failure rate."""
        if signal.tool_attempt_count == 0:
            return 0.0
        return signal.tool_failure_count / signal.tool_attempt_count
    
    def _determine_action(
        self, signal: RhythmSignal, params: RhythmParameters, patience: float
    ) -> Tuple[RhythmAction, str, float]:
        """Determine the rhythm action based on conditions."""
        
        # Check for forced clarify conditions (highest priority)
        if signal.focus_fatigue >= params.focus_fatigue_clarify_threshold:
            return (
                RhythmAction.ASK_CLARIFY_THEN_WAIT,
                f"Focus fatigue ({signal.focus_fatigue:.2f}) exceeds clarify threshold ({params.focus_fatigue_clarify_threshold})",
                0.9
            )
        
        if signal.energy <= params.energy_clarify_threshold:
            return (
                RhythmAction.ASK_CLARIFY_THEN_WAIT,
                f"Energy ({signal.energy:.2f}) below clarify threshold ({params.energy_clarify_threshold})",
                0.9
            )
        
        # Check for cooldown conditions
        tool_failure_rate = self._calculate_tool_failure_rate(signal)
        cooldown_conditions = []
        
        if signal.focus_fatigue >= params.focus_fatigue_respond_threshold:
            cooldown_conditions.append(
                f"focus_fatigue ({signal.focus_fatigue:.2f}) >= {params.focus_fatigue_respond_threshold}"
            )
        
        if signal.energy <= params.energy_respond_threshold:
            cooldown_conditions.append(
                f"energy ({signal.energy:.2f}) <= {params.energy_respond_threshold}"
            )
        
        if signal.safety_stress <= params.safety_stress_respond_threshold:
            cooldown_conditions.append(
                f"safety_stress ({signal.safety_stress:.2f}) <= {params.safety_stress_respond_threshold}"
            )
        
        if tool_failure_rate >= params.tool_failure_threshold:
            cooldown_conditions.append(
                f"tool_failure_rate ({tool_failure_rate:.2f}) >= {params.tool_failure_threshold}"
            )
        
        if signal.user_burst_count >= params.burst_threshold:
            cooldown_conditions.append(
                f"user_burst ({signal.user_burst_count}) >= {params.burst_threshold}"
            )
        
        if cooldown_conditions:
            reason = "; ".join(cooldown_conditions)
            confidence = min(0.95, 0.7 + 0.05 * len(cooldown_conditions))
            return (RhythmAction.COOLDOWN, reason, confidence)
        
        # Default: respond now
        return (
            RhythmAction.RESPOND_NOW,
            f"All conditions normal (patience={patience:.2f}s)",
            0.95
        )
    
    def _calculate_body_state_impacts(
        self, signal: RhythmSignal, action: RhythmAction, params: RhythmParameters
    ) -> Dict[str, float]:
        """Calculate expected body state impacts from the rhythm action."""
        impacts = {
            "energy": 0.0,
            "focus_fatigue": 0.0,
            "safety_stress": 0.0,
        }
        
        if action == RhythmAction.RESPOND_NOW:
            # Responding costs energy and increases fatigue
            impacts["energy"] = -0.03
            impacts["focus_fatigue"] = 0.02
            # Rapid responses during burst increase fatigue more
            if signal.user_burst_count > 0:
                impacts["focus_fatigue"] += 0.01 * signal.user_burst_count
        
        elif action == RhythmAction.ASK_CLARIFY_THEN_WAIT:
            # Asking for clarification is less costly
            impacts["energy"] = -0.01
            impacts["focus_fatigue"] = 0.005
            # Waiting allows some recovery
            impacts["focus_fatigue"] -= 0.01
        
        elif action == RhythmAction.COOLDOWN:
            # Cooldown allows recovery
            impacts["energy"] = 0.01
            impacts["focus_fatigue"] = -0.02
            impacts["safety_stress"] = 0.01
        
        return impacts
    
    def _record_decision(self, decision: RhythmDecision) -> None:
        """Record decision to history."""
        self._decision_history.append(decision)
        if len(self._decision_history) > self._max_history:
            self._decision_history = self._decision_history[-self._max_history:]
    
    def get_decision_history(self, limit: int = 10) -> List[RhythmDecision]:
        """Get recent decision history."""
        return self._decision_history[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get rhythm scheduler statistics."""
        if not self._decision_history:
            return {
                "total_decisions": 0,
                "action_distribution": {},
                "average_confidence": 0.0,
                "average_patience": 0.0,
            }
        
        total = len(self._decision_history)
        action_counts = {}
        total_confidence = 0.0
        total_patience = 0.0
        
        for d in self._decision_history:
            action_counts[d.action.value] = action_counts.get(d.action.value, 0) + 1
            total_confidence += d.confidence
            total_patience += d.patience_required
        
        return {
            "total_decisions": total,
            "action_distribution": action_counts,
            "average_confidence": total_confidence / total,
            "average_patience": total_patience / total,
        }
    
    def update_parameters(self, parameters: RhythmParameters) -> None:
        """Update rhythm parameters (for AutoTune)."""
        self.parameters = parameters
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "parameters": self.parameters.to_dict(),
            "statistics": self.get_statistics(),
        }


# Global rhythm scheduler instance
_global_rhythm_scheduler: Optional[RhythmScheduler] = None


def get_rhythm_scheduler() -> RhythmScheduler:
    """Get the global rhythm scheduler instance."""
    global _global_rhythm_scheduler
    if _global_rhythm_scheduler is None:
        _global_rhythm_scheduler = RhythmScheduler()
    return _global_rhythm_scheduler


def set_rhythm_scheduler(scheduler: RhythmScheduler) -> None:
    """Set the global rhythm scheduler instance."""
    global _global_rhythm_scheduler
    _global_rhythm_scheduler = scheduler


def reset_rhythm_scheduler() -> RhythmScheduler:
    """Reset the global rhythm scheduler to default state."""
    global _global_rhythm_scheduler
    _global_rhythm_scheduler = RhythmScheduler()
    return _global_rhythm_scheduler


def schedule_rhythm(
    time_passed_seconds: float = 0.0,
    user_burst_count: int = 0,
    tool_failure_count: int = 0,
    tool_attempt_count: int = 0,
    energy: float = 0.5,
    focus_fatigue: float = 0.3,
    boredom: float = 0.0,
    curiosity: float = 0.0,
    safety_stress: float = 0.5,
    last_rhythm_action: Optional[str] = None,
) -> RhythmDecision:
    """
    Convenience function to schedule rhythm with individual parameters.
    
    Args:
        time_passed_seconds: Time since last interaction
        user_burst_count: Consecutive user messages
        tool_failure_count: Recent tool failures
        tool_attempt_count: Recent tool attempts
        energy: Current energy level [0, 1]
        focus_fatigue: Current focus fatigue [0, 1]
        boredom: Boredom level [0, 1]
        curiosity: Curiosity level [0, 1]
        safety_stress: Safety/stress level [0, 1]
        last_rhythm_action: Last rhythm action taken
        
    Returns:
        RhythmDecision with action and parameters
    """
    signal = RhythmSignal(
        time_passed_seconds=time_passed_seconds,
        user_burst_count=user_burst_count,
        tool_failure_count=tool_failure_count,
        tool_attempt_count=tool_attempt_count,
        energy=energy,
        focus_fatigue=focus_fatigue,
        boredom=boredom,
        curiosity=curiosity,
        safety_stress=safety_stress,
        last_rhythm_action=last_rhythm_action,
    )
    return get_rhythm_scheduler().schedule(signal)


def schedule_rhythm_from_body_state(
    body_state: Any,
    time_passed_seconds: float = 0.0,
    user_burst_count: int = 0,
    tool_failure_count: int = 0,
    tool_attempt_count: int = 0,
    boredom: float = 0.0,
    curiosity: float = 0.0,
    last_rhythm_action: Optional[str] = None,
) -> RhythmDecision:
    """
    Schedule rhythm using body state object.
    
    Args:
        body_state: BodyStateVector or compatible object with energy, focus_fatigue, safety_stress
        time_passed_seconds: Time since last interaction
        user_burst_count: Consecutive user messages
        tool_failure_count: Recent tool failures
        tool_attempt_count: Recent tool attempts
        boredom: Boredom level [0, 1]
        curiosity: Curiosity level [0, 1]
        last_rhythm_action: Last rhythm action taken
        
    Returns:
        RhythmDecision with action and parameters
    """
    # Extract values from body_state dimensions if available
    energy_val = 0.5
    focus_fatigue_val = 0.3
    safety_stress_val = 0.5
    
    if hasattr(body_state, 'energy'):
        energy_attr = getattr(body_state, 'energy')
        if hasattr(energy_attr, 'value'):
            energy_val = energy_attr.value
        else:
            energy_val = float(energy_attr)
    
    if hasattr(body_state, 'focus_fatigue'):
        fatigue_attr = getattr(body_state, 'focus_fatigue')
        if hasattr(fatigue_attr, 'value'):
            focus_fatigue_val = fatigue_attr.value
        else:
            focus_fatigue_val = float(fatigue_attr)
    
    if hasattr(body_state, 'safety_stress'):
        safety_attr = getattr(body_state, 'safety_stress')
        if hasattr(safety_attr, 'value'):
            safety_stress_val = safety_attr.value
        else:
            safety_stress_val = float(safety_attr)
    
    signal = RhythmSignal(
        time_passed_seconds=time_passed_seconds,
        user_burst_count=user_burst_count,
        tool_failure_count=tool_failure_count,
        tool_attempt_count=tool_attempt_count,
        energy=energy_val,
        focus_fatigue=focus_fatigue_val,
        boredom=boredom,
        curiosity=curiosity,
        safety_stress=safety_stress_val,
        last_rhythm_action=last_rhythm_action,
    )
    return get_rhythm_scheduler().schedule(signal)


def apply_rhythm_to_body_state(
    body_state: Any,
    decision: RhythmDecision,
) -> Dict[str, float]:
    """
    Apply rhythm decision impacts to body state.
    
    Args:
        body_state: BodyStateVector or compatible object
        decision: RhythmDecision with body_state_impacts
        
    Returns:
        Applied deltas
    """
    impacts = decision.body_state_impacts
    applied = {}
    
    for dimension, delta in impacts.items():
        if hasattr(body_state, dimension):
            dim_obj = getattr(body_state, dimension)
            if hasattr(dim_obj, 'update'):
                dim_obj.update(delta)
                applied[dimension] = delta
            elif hasattr(dim_obj, 'value'):
                dim_obj.value = max(0.0, min(1.0, dim_obj.value + delta))
                applied[dimension] = delta
    
    return applied
