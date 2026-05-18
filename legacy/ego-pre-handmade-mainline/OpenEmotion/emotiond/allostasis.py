"""
MVP-5 D2: Allostasis Budget System

Energy budget dynamics for fatigue/recovery management.

Core principles:
- energy_budget ∈ [0, 1]: 1 = fully energized, 0 = exhausted
- Decreases on: high conflict, high uncertainty, consecutive prediction errors
- Increases on: time_passed (configurable recovery constant)
- Couples to: language intensity/length, w_explore, learning rate

Trace records:
- Budget deltas with concise reason tags each turn
"""
import time
import math
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum


class BudgetChangeReason(Enum):
    """Reasons for energy budget changes."""
    HIGH_CONFLICT = "high_conflict"
    HIGH_UNCERTAINTY = "high_uncertainty"
    PREDICTION_ERROR = "prediction_error"
    CONSECUTIVE_ERRORS = "consecutive_errors"
    TIME_PASSED = "time_passed"
    REJECTION = "rejection"
    BETRAYAL = "betrayal"
    CARE = "care"
    REPAIR = "repair"
    IGNORED = "ignored"
    USER_NEGATIVE = "user_negative"
    USER_POSITIVE = "user_positive"


@dataclass
class BudgetDelta:
    """Records a single budget change with reason."""
    delta: float  # Change amount (negative = decrease, positive = increase)
    reason: str  # BudgetChangeReason value
    old_value: float
    new_value: float
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "delta": round(self.delta, 4),
            "reason": self.reason,
            "old_value": round(self.old_value, 4),
            "new_value": round(self.new_value, 4),
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }


class AllostasisBudget:
    """
    Energy budget manager for allostasis.

    Manages energy_budget ∈ [0, 1] with:
    - Depletion on stressful events (conflict, uncertainty, errors)
    - Recovery over time
    - Guidance for decision-making (language, exploration, learning)
    """

    def __init__(
        self,
        initial_budget: float = 1.0,
        recovery_rate: float = 0.05,  # Per minute of rest
        conflict_depletion: float = 0.15,
        uncertainty_depletion: float = 0.08,
        error_depletion: float = 0.10,
        consecutive_error_multiplier: float = 1.5,
        min_budget: float = 0.0,
        max_budget: float = 1.0
    ):
        """
        Initialize allostasis budget.

        Args:
            initial_budget: Starting energy budget [0, 1]
            recovery_rate: Budget recovery per minute of rest
            conflict_depletion: Depletion on high conflict
            uncertainty_depletion: Depletion on high uncertainty
            error_depletion: Depletion per prediction error
            consecutive_error_multiplier: Multiplier for consecutive errors
            min_budget: Minimum budget floor
            max_budget: Maximum budget ceiling
        """
        self._budget = max(min_budget, min(max_budget, initial_budget))
        self.recovery_rate = recovery_rate
        self.conflict_depletion = conflict_depletion
        self.uncertainty_depletion = uncertainty_depletion
        self.error_depletion = error_depletion
        self.consecutive_error_multiplier = consecutive_error_multiplier
        self.min_budget = min_budget
        self.max_budget = max_budget

        self._history: List[BudgetDelta] = []
        self._max_history_size = 100
        self._consecutive_errors = 0
        self._last_update_time = time.time()

    @property
    def budget(self) -> float:
        """Current energy budget value."""
        return round(self._budget, 4)

    @property
    def is_low(self) -> bool:
        """True if budget is below 0.3 (fatigued)."""
        return self._budget < 0.3

    @property
    def is_critical(self) -> bool:
        """True if budget is below 0.1 (exhausted)."""
        return self._budget < 0.1

    @property
    def fatigue_level(self) -> str:
        """Return fatigue level as string."""
        if self._budget >= 0.7:
            return "energized"
        elif self._budget >= 0.4:
            return "moderate"
        elif self._budget >= 0.2:
            return "fatigued"
        else:
            return "exhausted"

    def _clamp(self, value: float) -> float:
        """Clamp value to [min_budget, max_budget]."""
        return max(self.min_budget, min(self.max_budget, value))

    def _record_delta(
        self,
        delta: float,
        reason: str,
        old_value: float,
        metadata: Dict[str, Any] = None
    ) -> BudgetDelta:
        """Record a budget change."""
        delta_record = BudgetDelta(
            delta=delta,
            reason=reason,
            old_value=old_value,
            new_value=self._budget,
            metadata=metadata or {}
        )
        self._history.append(delta_record)

        # Trim history if too large
        if len(self._history) > self._max_history_size:
            self._history = self._history[-self._max_history_size:]

        return delta_record

    def deplete(
        self,
        amount: float,
        reason: str,
        metadata: Dict[str, Any] = None
    ) -> BudgetDelta:
        """
        Deplete budget by amount.

        Args:
            amount: Amount to deplete (will be subtracted)
            reason: Reason for depletion
            metadata: Additional context

        Returns:
            BudgetDelta record
        """
        old_value = self._budget
        self._budget = self._clamp(self._budget - abs(amount))
        actual_delta = self._budget - old_value  # Negative

        return self._record_delta(actual_delta, reason, old_value, metadata)

    def replenish(
        self,
        amount: float,
        reason: str,
        metadata: Dict[str, Any] = None
    ) -> BudgetDelta:
        """
        Replenish budget by amount.

        Args:
            amount: Amount to add
            reason: Reason for replenishment
            metadata: Additional context

        Returns:
            BudgetDelta record
        """
        old_value = self._budget
        self._budget = self._clamp(self._budget + abs(amount))
        actual_delta = self._budget - old_value  # Positive

        return self._record_delta(actual_delta, reason, old_value, metadata)

    def apply_time_passed(self, seconds: float) -> BudgetDelta:
        """
        Apply natural recovery over time.

        Args:
            seconds: Time passed in seconds

        Returns:
            BudgetDelta record
        """
        # Convert seconds to minutes for recovery calculation
        minutes = seconds / 60.0
        recovery_amount = self.recovery_rate * minutes

        # Recovery is slower at higher budget levels (diminishing returns)
        # Use logistic-like curve: recovery * (1 - budget^2)
        efficiency = 1.0 - (self._budget ** 2)
        actual_recovery = recovery_amount * efficiency

        return self.replenish(
            actual_recovery,
            BudgetChangeReason.TIME_PASSED.value,
            {"seconds": seconds, "minutes": minutes, "efficiency": round(efficiency, 4)}
        )

    def on_prediction_error(
        self,
        error_magnitude: float,
        is_consecutive: bool = False
    ) -> BudgetDelta:
        """
        Handle prediction error event.

        Args:
            error_magnitude: Size of prediction error [0, 1]
            is_consecutive: Whether this is part of a consecutive streak

        Returns:
            BudgetDelta record
        """
        if is_consecutive:
            self._consecutive_errors += 1
            multiplier = 1.0 + (self._consecutive_errors * 0.2)
        else:
            self._consecutive_errors = 0
            multiplier = 1.0

        # Scale depletion by error magnitude
        amount = self.error_depletion * error_magnitude * multiplier

        return self.deplete(
            amount,
            BudgetChangeReason.CONSECUTIVE_ERRORS.value if is_consecutive else BudgetChangeReason.PREDICTION_ERROR.value,
            {"error_magnitude": round(error_magnitude, 4), "multiplier": round(multiplier, 2), "consecutive_count": self._consecutive_errors}
        )

    def on_high_conflict(self, conflict_intensity: float = 1.0) -> BudgetDelta:
        """
        Handle high conflict event.

        Args:
            conflict_intensity: Intensity of conflict [0, 1]

        Returns:
            BudgetDelta record
        """
        amount = self.conflict_depletion * conflict_intensity
        return self.deplete(
            amount,
            BudgetChangeReason.HIGH_CONFLICT.value,
            {"intensity": round(conflict_intensity, 4)}
        )

    def on_high_uncertainty(self, uncertainty_level: float) -> BudgetDelta:
        """
        Handle high uncertainty event.

        Args:
            uncertainty_level: Uncertainty level [0, 1]

        Returns:
            BudgetDelta record
        """
        # Only deplete if uncertainty is above threshold
        if uncertainty_level < 0.5:
            return None

        # Scale by how far above threshold
        scaled_uncertainty = (uncertainty_level - 0.5) * 2  # Normalize to [0, 1]
        amount = self.uncertainty_depletion * scaled_uncertainty

        return self.deplete(
            amount,
            BudgetChangeReason.HIGH_UNCERTAINTY.value,
            {"uncertainty_level": round(uncertainty_level, 4)}
        )

    def on_event_subtype(self, subtype: str, intensity: float = 1.0) -> Optional[BudgetDelta]:
        """
        Handle world_event subtype.

        Args:
            subtype: Event subtype (rejection, betrayal, care, etc.)
            intensity: Event intensity [0, 1]

        Returns:
            BudgetDelta record or None if no change
        """
        subtype_depletion_map = {
            "rejection": (0.12, BudgetChangeReason.REJECTION),
            "betrayal": (0.20, BudgetChangeReason.BETRAYAL),
            "care": (-0.05, BudgetChangeReason.CARE),  # Negative = replenishment
            "repair_success": (-0.03, BudgetChangeReason.REPAIR),
            "ignored": (0.05, BudgetChangeReason.IGNORED),
        }

        if subtype not in subtype_depletion_map:
            return None

        amount, reason = subtype_depletion_map[subtype]
        amount = amount * intensity

        if amount < 0:
            return self.replenish(abs(amount), reason.value, {"intensity": round(intensity, 4)})
        else:
            return self.deplete(amount, reason.value, {"intensity": round(intensity, 4)})

    def on_user_message(self, is_negative: bool = False, is_positive: bool = False) -> Optional[BudgetDelta]:
        """
        Handle user message impact on budget.

        Args:
            is_negative: Whether message has negative sentiment
            is_positive: Whether message has positive sentiment

        Returns:
            BudgetDelta record or None
        """
        if is_negative:
            return self.deplete(0.03, BudgetChangeReason.USER_NEGATIVE.value)
        elif is_positive:
            return self.replenish(0.02, BudgetChangeReason.USER_POSITIVE.value)
        return None

    def reset_consecutive_errors(self):
        """Reset consecutive error counter (e.g., after successful prediction)."""
        self._consecutive_errors = 0

    def get_language_guidance(self) -> Dict[str, Any]:
        """
        Get guidance for language generation based on budget.

        Returns:
            Dict with intensity_cap, length_cap, tone_guidance
        """
        if self._budget >= 0.7:
            return {
                "intensity_cap": 1.0,
                "length_cap": 1.0,
                "tone_guidance": "normal",
                "max_tokens_suggestion": 200
            }
        elif self._budget >= 0.4:
            return {
                "intensity_cap": 0.8,
                "length_cap": 0.9,
                "tone_guidance": "moderate",
                "max_tokens_suggestion": 150
            }
        elif self._budget >= 0.2:
            return {
                "intensity_cap": 0.6,
                "length_cap": 0.7,
                "tone_guidance": "concise",
                "max_tokens_suggestion": 100
            }
        else:
            return {
                "intensity_cap": 0.4,
                "length_cap": 0.5,
                "tone_guidance": "minimal",
                "max_tokens_suggestion": 50
            }

    def get_explore_weight(self, base_w_explore: float = 0.5) -> float:
        """
        Get adjusted w_explore based on budget.

        Low budget reduces exploration tendency.

        Args:
            base_w_explore: Base exploration weight

        Returns:
            Adjusted w_explore
        """
        # Linear reduction: at budget=0, explore is halved
        fatigue_factor = 0.5 + (0.5 * self._budget)
        return base_w_explore * fatigue_factor

    def get_learning_rate_multiplier(self) -> float:
        """
        Get learning rate multiplier based on budget.

        Low budget makes learning more conservative.

        Returns:
            Multiplier for learning rate
        """
        # Conservative when fatigued: at budget=0, learning rate is 0.5x
        return 0.5 + (0.5 * self._budget)

    def get_update_amplitude_cap(self) -> float:
        """
        Get maximum update amplitude based on budget.

        Low budget caps how large updates can be.

        Returns:
            Maximum amplitude for updates
        """
        # Cap shrinks with fatigue: 0.2 at full energy, 0.05 at exhausted
        return 0.05 + (0.15 * self._budget)

    def get_history(self, limit: int = 10) -> List[BudgetDelta]:
        """Get recent budget history."""
        return self._history[-limit:]

    def get_history_dicts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent budget history as dicts."""
        return [d.to_dict() for d in self._history[-limit:]]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize budget state."""
        return {
            "budget": self.budget,
            "fatigue_level": self.fatigue_level,
            "is_low": self.is_low,
            "is_critical": self.is_critical,
            "consecutive_errors": self._consecutive_errors,
            "recent_deltas": self.get_history_dicts(5)
        }


# Global budget instance
_budget_instance: Optional[AllostasisBudget] = None


def get_budget(
    recovery_rate: float = None,
    conflict_depletion: float = None,
    uncertainty_depletion: float = None,
    error_depletion: float = None
) -> AllostasisBudget:
    """
    Get or create global budget instance.

    Args:
        recovery_rate: Optional override for recovery rate
        conflict_depletion: Optional override for conflict depletion
        uncertainty_depletion: Optional override for uncertainty depletion
        error_depletion: Optional override for error depletion

    Returns:
        AllostasisBudget instance
    """
    global _budget_instance
    if _budget_instance is None:
        kwargs = {}
        if recovery_rate is not None:
            kwargs["recovery_rate"] = recovery_rate
        if conflict_depletion is not None:
            kwargs["conflict_depletion"] = conflict_depletion
        if uncertainty_depletion is not None:
            kwargs["uncertainty_depletion"] = uncertainty_depletion
        if error_depletion is not None:
            kwargs["error_depletion"] = error_depletion
        _budget_instance = AllostasisBudget(**kwargs)
    return _budget_instance


def reset_budget():
    """Reset global budget instance (for testing)."""
    global _budget_instance
    _budget_instance = None


def calculate_budget_from_state(
    state_dict: Dict[str, Any],
    previous_budget: float = 1.0,
    time_passed_seconds: float = 0
) -> Tuple[float, List[BudgetDelta]]:
    """
    Calculate new budget from emotion state.

    Utility function for integration with existing state management.

    Args:
        state_dict: Dict with uncertainty, prediction_error, etc.
        previous_budget: Previous budget value
        time_passed_seconds: Time since last update

    Returns:
        Tuple of (new_budget, list of BudgetDeltas)
    """
    budget = AllostasisBudget(initial_budget=previous_budget)
    deltas = []

    # Apply time-based recovery first
    if time_passed_seconds > 0:
        delta = budget.apply_time_passed(time_passed_seconds)
        deltas.append(delta)

    # Check for high uncertainty
    uncertainty = state_dict.get("uncertainty", 0.0)
    if uncertainty > 0.6:
        delta = budget.on_high_uncertainty(uncertainty)
        if delta:
            deltas.append(delta)

    # Check for prediction error
    prediction_error = state_dict.get("prediction_error", 0.0)
    if prediction_error > 0.2:
        delta = budget.on_prediction_error(prediction_error)
        deltas.append(delta)

    return budget.budget, deltas
