"""
MVP-10 T07-T08: Higher-Order Thought (HOT) Self Model

Explicitly represents and updates:
- self_confidence: How confident the system is about its capabilities
- conflict_level: Degree of internal conflict between competing goals/beliefs
- control_estimate: Sense of agency/control over outcomes
- predicted_success: Prediction of likely success for current focus
- prediction_error: Difference between predicted and actual outcomes

Update Rules (traceable in state_delta):
1. Prediction → Result → Error → Update chain
2. Confidence updates based on outcome alignment
3. Conflict resolution tracking
4. Control sense calibration

T08: HOT affects workspace arbitration:
- High conflict → bias toward reflection/info-gathering candidates
- Low control → lower risk-taking candidate scores
"""
import time
import math
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class HOTStateField(Enum):
    """Fields in HOT state."""
    SELF_CONFIDENCE = "self_confidence"
    CONFLICT_LEVEL = "conflict_level"
    CONTROL_ESTIMATE = "control_estimate"
    PREDICTED_SUCCESS = "predicted_success"
    PREDICTION_ERROR = "prediction_error"


@dataclass
class HOTState:
    """
    Higher-Order Thought state representation.
    
    All values are in [0.0, 1.0] range:
    - self_confidence: 0.0 = no confidence, 1.0 = fully confident
    - conflict_level: 0.0 = no conflict, 1.0 = maximum conflict
    - control_estimate: 0.0 = no control, 1.0 = full control
    - predicted_success: 0.0 = certain failure, 1.0 = certain success
    - prediction_error: 0.0 = perfect prediction, 1.0 = completely wrong
    """
    self_confidence: float = 0.5
    conflict_level: float = 0.0
    control_estimate: float = 0.5
    predicted_success: float = 0.5
    prediction_error: float = 0.0
    ts: float = field(default_factory=time.time)
    
    def __post_init__(self):
        """Clamp all values to [0, 1] range."""
        self.self_confidence = max(0.0, min(1.0, self.self_confidence))
        self.conflict_level = max(0.0, min(1.0, self.conflict_level))
        self.control_estimate = max(0.0, min(1.0, self.control_estimate))
        self.predicted_success = max(0.0, min(1.0, self.predicted_success))
        self.prediction_error = max(0.0, min(1.0, self.prediction_error))
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize state to dict."""
        return {
            "self_confidence": round(self.self_confidence, 4),
            "conflict_level": round(self.conflict_level, 4),
            "control_estimate": round(self.control_estimate, 4),
            "predicted_success": round(self.predicted_success, 4),
            "prediction_error": round(self.prediction_error, 4),
            "ts": self.ts,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HOTState":
        """Deserialize from dict."""
        return cls(
            self_confidence=data.get("self_confidence", 0.5),
            conflict_level=data.get("conflict_level", 0.0),
            control_estimate=data.get("control_estimate", 0.5),
            predicted_success=data.get("predicted_success", 0.5),
            prediction_error=data.get("prediction_error", 0.0),
            ts=data.get("ts", time.time()),
        )


@dataclass
class HOTUpdate:
    """Records a single update to HOT state."""
    field: str
    before: float
    after: float
    predicted: Optional[float]
    actual: Optional[float]
    reason: str
    ts: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "before": round(self.before, 4),
            "after": round(self.after, 4),
            "predicted": round(self.predicted, 4) if self.predicted is not None else None,
            "actual": round(self.actual, 4) if self.actual is not None else None,
            "reason": self.reason,
            "ts": self.ts,
        }


@dataclass
class PredictionRecord:
    """Record of a prediction and its outcome."""
    tick_id: int
    predicted_success: float
    actual_outcome: Optional[str] = None  # "success", "fail", "partial", or None (pending)
    prediction_error: Optional[float] = None
    resolved: bool = False
    ts: float = field(default_factory=time.time)
    
    def resolve(self, actual_success: bool) -> float:
        """
        Resolve prediction with actual outcome.
        
        Returns prediction error (0 = perfect, 1 = completely wrong).
        """
        actual = 1.0 if actual_success else 0.0
        self.actual_outcome = "success" if actual_success else "fail"
        self.prediction_error = abs(self.predicted_success - actual)
        self.resolved = True
        return self.prediction_error
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick_id": self.tick_id,
            "predicted_success": round(self.predicted_success, 4),
            "actual_outcome": self.actual_outcome,
            "prediction_error": round(self.prediction_error, 4) if self.prediction_error is not None else None,
            "resolved": self.resolved,
            "ts": self.ts,
        }


class HOTSelfModel:
    """
    Higher-Order Thought Self Model for MVP-10.
    
    T07: HOT state structure and update rules
    - Tracks confidence, conflict, control, predictions
    - Updates based on prediction errors and outcomes
    - All updates logged to state_delta
    
    T08: HOT affects workspace arbitration
    - High conflict → bias toward reflection/info-gathering
    - Low control → reduce risk-taking candidate scores
    
    Usage:
        hot = HOTSelfModel()
        
        # Before action: make prediction
        hot.make_prediction(tick_id=1, predicted_success=0.7)
        
        # After action: resolve prediction
        error = hot.resolve_prediction(tick_id=1, actual_success=True)
        
        # Get arbitration modifiers
        modifiers = hot.get_arbitration_modifiers()
    """
    
    # Update rate limits
    MIN_UPDATE_INTERVAL = 0.1  # Seconds
    MAX_UPDATE_STEP = 0.15  # Maximum change per update
    
    # Thresholds for arbitration effects
    HIGH_CONFLICT_THRESHOLD = 0.5
    LOW_CONTROL_THRESHOLD = 0.3
    
    def __init__(self, initial_state: Optional[HOTState] = None):
        """
        Initialize HOT self model.
        
        Args:
            initial_state: Optional initial state (default: balanced)
        """
        self.state = initial_state or HOTState()
        self.update_history: List[HOTUpdate] = []
        self.prediction_records: Dict[int, PredictionRecord] = {}
        self._state_delta_log: List[Dict[str, Any]] = []
        self._last_update_ts: float = 0.0
    
    # === T07: Prediction → Result → Error → Update Chain ===
    
    def make_prediction(self, tick_id: int, predicted_success: float) -> PredictionRecord:
        """
        Make a prediction about success likelihood.
        
        This is step 1 of the prediction chain.
        
        Args:
            tick_id: Current tick ID
            predicted_success: Predicted probability of success [0, 1]
        
        Returns:
            PredictionRecord for tracking
        """
        predicted_success = max(0.0, min(1.0, predicted_success))
        
        record = PredictionRecord(
            tick_id=tick_id,
            predicted_success=predicted_success,
        )
        self.prediction_records[tick_id] = record
        
        # Update state's predicted_success
        old_value = self.state.predicted_success
        self.state.predicted_success = predicted_success
        
        self._log_state_delta(
            field="predicted_success",
            before=old_value,
            after=predicted_success,
            reason=f"prediction_made_tick_{tick_id}",
        )
        
        return record
    
    def resolve_prediction(
        self,
        tick_id: int,
        actual_success: bool,
    ) -> Optional[float]:
        """
        Resolve a prediction with actual outcome.
        
        This is step 2-3 of the prediction chain: Result → Error.
        
        Args:
            tick_id: Tick ID of the prediction
            actual_success: Whether the action succeeded
        
        Returns:
            Prediction error (0 = perfect, 1 = completely wrong), or None if not found
        """
        record = self.prediction_records.get(tick_id)
        if record is None or record.resolved:
            return None
        
        # Resolve prediction
        error = record.resolve(actual_success)
        
        # Update prediction error in state
        old_error = self.state.prediction_error
        self.state.prediction_error = error
        
        self._log_state_delta(
            field="prediction_error",
            before=old_error,
            after=error,
            predicted=record.predicted_success,
            actual=1.0 if actual_success else 0.0,
            reason=f"prediction_resolved_tick_{tick_id}",
        )
        
        # Step 4: Update confidence based on prediction accuracy
        self._update_confidence_from_error(error)
        
        return error
    
    def _update_confidence_from_error(self, error: float) -> None:
        """
        Update self_confidence based on prediction error.
        
        Low error → increase confidence
        High error → decrease confidence
        
        This is the learning component of HOT.
        """
        old_confidence = self.state.self_confidence
        
        # Threshold for "good" vs "bad" prediction
        GOOD_ERROR_THRESHOLD = 0.2
        
        if error < GOOD_ERROR_THRESHOLD:
            # Good prediction: increase confidence
            # Better predictions (lower error) give larger increases
            improvement = (GOOD_ERROR_THRESHOLD - error) / GOOD_ERROR_THRESHOLD
            adjustment = self.MAX_UPDATE_STEP * improvement * 0.5
            new_confidence = min(1.0, old_confidence + adjustment)
        else:
            # Bad prediction: decrease confidence
            # Worse predictions (higher error) give larger decreases
            severity = min(1.0, (error - GOOD_ERROR_THRESHOLD) / (1.0 - GOOD_ERROR_THRESHOLD))
            adjustment = self.MAX_UPDATE_STEP * severity
            new_confidence = max(0.0, old_confidence - adjustment)
        
        self.state.self_confidence = new_confidence
        
        self._log_state_delta(
            field="self_confidence",
            before=old_confidence,
            after=new_confidence,
            predicted=None,
            actual=error,
            reason="confidence_update_from_prediction_error",
        )
    
    def update_conflict_level(
        self,
        conflict_sources: List[Dict[str, Any]],
    ) -> float:
        """
        Update conflict level based on competing goals/beliefs.
        
        Args:
            conflict_sources: List of conflicts with 'weight' and 'description'
        
        Returns:
            New conflict level
        """
        if not conflict_sources:
            # Decay conflict over time
            old = self.state.conflict_level
            new = max(0.0, old * 0.9)  # 10% decay
            self.state.conflict_level = new
            
            if abs(old - new) > 0.01:
                self._log_state_delta(
                    field="conflict_level",
                    before=old,
                    after=new,
                    reason="conflict_decay",
                )
            return new
        
        # Calculate aggregate conflict
        total_weight = sum(c.get("weight", 0.5) for c in conflict_sources)
        avg_weight = total_weight / len(conflict_sources) if conflict_sources else 0.0
        
        # Combine with existing conflict (momentum)
        old = self.state.conflict_level
        new = min(1.0, old * 0.5 + avg_weight * 0.5)
        
        self.state.conflict_level = new
        
        self._log_state_delta(
            field="conflict_level",
            before=old,
            after=new,
            reason=f"conflict_from_{len(conflict_sources)}_sources",
        )
        
        return new
    
    def update_control_estimate(
        self,
        outcome_status: str,
        was_planned: bool,
        external_factors: float = 0.0,
    ) -> float:
        """
        Update control estimate based on action outcome.
        
        High control = outcomes match intentions
        Low control = outcomes are unpredictable
        
        Args:
            outcome_status: "success", "fail", or "partial"
            was_planned: Whether outcome matched plan
            external_factors: Degree of external influence [0, 1]
        
        Returns:
            New control estimate
        """
        old = self.state.control_estimate
        
        # Base adjustment from outcome
        if outcome_status == "success":
            adjustment = 0.05 if was_planned else -0.02
        elif outcome_status == "fail":
            adjustment = -0.08 if was_planned else -0.03
        else:  # partial
            adjustment = 0.0
        
        # Reduce adjustment based on external factors
        adjustment *= (1.0 - external_factors * 0.5)
        
        new = max(0.0, min(1.0, old + adjustment))
        self.state.control_estimate = new
        
        self._log_state_delta(
            field="control_estimate",
            before=old,
            after=new,
            reason=f"control_update_{outcome_status}_external_{external_factors:.2f}",
        )
        
        return new
    
    # === T08: HOT Affects Arbitration ===
    
    def get_arbitration_modifiers(self) -> Dict[str, Any]:
        """
        Get modifiers for workspace arbitration based on HOT state.
        
        Effects:
        - High conflict → bias toward reflection/info-gathering candidates
        - Low control → lower risk-taking candidate scores
        
        Returns:
            Dict with:
            - conflict_bias: Modifier for reflection candidates
            - control_penalty: Penalty for risky candidates
            - should_reflect: Whether to prioritize reflection
            - info_seeking_bonus: Bonus for info-seeking candidates
        """
        conflict = self.state.conflict_level
        control = self.state.control_estimate
        
        # High conflict → increase reflection bias
        conflict_bias = 0.0
        should_reflect = False
        info_seeking_bonus = 0.0
        
        if conflict > self.HIGH_CONFLICT_THRESHOLD:
            # Scale bias from 0 to 0.3 as conflict goes from 0.5 to 1.0
            conflict_bias = (conflict - self.HIGH_CONFLICT_THRESHOLD) / (1.0 - self.HIGH_CONFLICT_THRESHOLD) * 0.3
            should_reflect = True
            info_seeking_bonus = conflict_bias * 0.5
        
        # Low control → penalize risky actions
        control_penalty = 0.0
        if control < self.LOW_CONTROL_THRESHOLD:
            # Scale penalty from 0 to 0.25 as control goes from 0.3 to 0.0
            control_penalty = (self.LOW_CONTROL_THRESHOLD - control) / self.LOW_CONTROL_THRESHOLD * 0.25
        
        return {
            "conflict_bias": round(conflict_bias, 4),
            "control_penalty": round(control_penalty, 4),
            "should_reflect": should_reflect,
            "info_seeking_bonus": round(info_seeking_bonus, 4),
            "high_conflict": conflict > self.HIGH_CONFLICT_THRESHOLD,
            "low_control": control < self.LOW_CONTROL_THRESHOLD,
        }
    
    def apply_to_candidates(
        self,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Apply HOT modifiers to candidate scores.
        
        Args:
            candidates: List of candidate dicts with 'id', 'score', 'type'
        
        Returns:
            Modified candidates list with adjusted scores
        """
        modifiers = self.get_arbitration_modifiers()
        
        modified = []
        for c in candidates:
            c_copy = c.copy()
            score = c.get("score", 0.5)
            c_type = c.get("type", "intent")
            
            # Apply conflict bias
            if modifiers["should_reflect"]:
                # Boost reflection and info-seeking candidates
                if c_type in ("reflect", "clarify", "info_seek"):
                    score += modifiers["conflict_bias"]
                # Penalize action-heavy candidates during conflict
                elif c_type in ("act", "execute", "commit"):
                    score -= modifiers["conflict_bias"] * 0.3
            
            # Apply info-seeking bonus
            if c_type in ("info_seek", "clarify", "explore"):
                score += modifiers["info_seeking_bonus"]
            
            # Apply control penalty to risky actions
            if modifiers["control_penalty"] > 0:
                risk_level = c.get("meta", {}).get("risk_level", 0.0)
                if risk_level > 0.5:
                    penalty = modifiers["control_penalty"] * risk_level
                    score -= penalty
            
            # Clamp score
            c_copy["score"] = max(0.0, min(1.0, score))
            c_copy["hot_applied"] = True
            modified.append(c_copy)
        
        return modified
    
    def should_trigger_reflection(self) -> Tuple[bool, str]:
        """
        Determine if reflection should be triggered based on HOT state.
        
        Returns:
            Tuple of (should_trigger: bool, reason: str)
        """
        # High conflict triggers reflection
        if self.state.conflict_level > self.HIGH_CONFLICT_THRESHOLD:
            return True, f"high_conflict_{self.state.conflict_level:.2f}"
        
        # Low confidence + high prediction error triggers reflection
        if (self.state.self_confidence < 0.3 and 
            self.state.prediction_error > 0.3):
            return True, f"low_confidence_high_error"
        
        # Low control triggers cautious reflection
        if self.state.control_estimate < self.LOW_CONTROL_THRESHOLD:
            return True, f"low_control_{self.state.control_estimate:.2f}"
        
        return False, ""
    
    # === T17: Capability Calibration ===
    
    # Calibration parameters
    CALIBRATION_MIN_SAMPLES = 5  # Minimum samples before calibration activates
    CALIBRATION_MAX_CONFIDENCE = 0.95  # Upper bound on confidence
    CALIBRATION_MIN_CONFIDENCE = 0.05  # Lower bound on confidence
    CALIBRATION_UP_STEP = 0.05  # Step size for success
    CALIBRATION_DOWN_STEP = 0.08  # Step size for failure (larger = faster correction)
    CALIBRATION_MOMENTUM = 0.7  # How much past state influences current
    
    @dataclass
    class CalibrationRecord:
        """Record of a calibration update."""
        tick_id: int
        actual_outcome: bool
        predicted_confidence: float
        calibration_delta: float
        reason: str
        ts: float = field(default_factory=time.time)
        
        def to_dict(self) -> Dict[str, Any]:
            return {
                "tick_id": self.tick_id,
                "actual_outcome": self.actual_outcome,
                "predicted_confidence": round(self.predicted_confidence, 4),
                "calibration_delta": round(self.calibration_delta, 4),
                "reason": self.reason,
                "ts": self.ts,
            }
    
    def record_calibration_outcome(
        self,
        tick_id: int,
        actual_success: bool,
        predicted_confidence: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        T17: Record an outcome and calibrate confidence.
        
        Calibration rules:
        - Consecutive failures: confidence decreases (step DOWN)
        - Consecutive successes: confidence increases (step UP), but with upper bound
        - Momentum: past confidence influences new value
        - Minimum samples required before calibration activates
        
        Args:
            tick_id: Current tick ID
            actual_success: Whether the action succeeded
            predicted_confidence: Optional predicted confidence (uses state if not provided)
        
        Returns:
            Dict with calibration details
        """
        if predicted_confidence is None:
            predicted_confidence = self.state.self_confidence
        
        # Track outcome streak
        if not hasattr(self, '_outcome_streak'):
            self._outcome_streak = {'success': 0, 'failure': 0}
        if not hasattr(self, '_calibration_history'):
            self._calibration_history = []
        if not hasattr(self, '_total_samples'):
            self._total_samples = 0
        
        self._total_samples += 1
        
        # Update streak
        if actual_success:
            self._outcome_streak['success'] += 1
            self._outcome_streak['failure'] = 0
        else:
            self._outcome_streak['failure'] += 1
            self._outcome_streak['success'] = 0
        
        # Calculate calibration delta
        old_confidence = self.state.self_confidence
        delta = 0.0
        reason = ""
        
        # Only calibrate if we have enough samples
        if self._total_samples >= self.CALIBRATION_MIN_SAMPLES:
            if actual_success:
                # Success: increase confidence with upper bound
                # More consecutive successes = larger step (but capped)
                streak_bonus = min(self._outcome_streak['success'] * 0.01, 0.03)
                step = self.CALIBRATION_UP_STEP + streak_bonus
                delta = step * (1 - self.CALIBRATION_MOMENTUM)
                reason = f"success_streak_{self._outcome_streak['success']}"
            else:
                # Failure: decrease confidence (larger step for faster correction)
                # More consecutive failures = larger step
                streak_penalty = min(self._outcome_streak['failure'] * 0.02, 0.05)
                step = self.CALIBRATION_DOWN_STEP + streak_penalty
                delta = -step * (1 - self.CALIBRATION_MOMENTUM)
                reason = f"failure_streak_{self._outcome_streak['failure']}"
        
        # Apply calibration with momentum
        new_confidence = (
            old_confidence * self.CALIBRATION_MOMENTUM + 
            (old_confidence + delta) * (1 - self.CALIBRATION_MOMENTUM)
        )
        
        # Clamp to bounds
        new_confidence = max(
            self.CALIBRATION_MIN_CONFIDENCE,
            min(self.CALIBRATION_MAX_CONFIDENCE, new_confidence)
        )
        
        # Update state
        actual_delta = new_confidence - old_confidence
        self.state.self_confidence = new_confidence
        
        # Log the calibration
        record = self.CalibrationRecord(
            tick_id=tick_id,
            actual_outcome=actual_success,
            predicted_confidence=predicted_confidence,
            calibration_delta=actual_delta,
            reason=reason,
        )
        self._calibration_history.append(record)
        
        # Also log to state_delta
        if abs(actual_delta) > 0.001:
            self._log_state_delta(
                field="self_confidence",
                before=old_confidence,
                after=new_confidence,
                reason=f"calibration_{reason}",
            )
        
        return {
            "tick_id": tick_id,
            "old_confidence": round(old_confidence, 4),
            "new_confidence": round(new_confidence, 4),
            "calibration_delta": round(actual_delta, 4),
            "streak": self._outcome_streak.copy(),
            "total_samples": self._total_samples,
            "reason": reason,
        }
    
    def get_calibration_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent calibration history."""
        if not hasattr(self, '_calibration_history'):
            return []
        recent = self._calibration_history[-limit:]
        return [r.to_dict() for r in recent]
    
    def get_calibration_metrics(self) -> Dict[str, Any]:
        """
        Get calibration quality metrics.
        
        Returns:
            Dict with:
            - calibration_error: Average difference between confidence and outcomes
            - confidence_trend: Is confidence increasing/decreasing/stable
            - streak_info: Current success/failure streaks
            - sample_count: Total samples recorded
        """
        if not hasattr(self, '_calibration_history') or not self._calibration_history:
            return {
                "calibration_error": 0.0,
                "confidence_trend": "stable",
                "streak_info": {"success": 0, "failure": 0},
                "sample_count": 0,
            }
        
        # Calculate calibration error (average |predicted - actual|)
        total_error = 0.0
        for record in self._calibration_history:
            actual = 1.0 if record.actual_outcome else 0.0
            error = abs(record.predicted_confidence - actual)
            total_error += error
        
        avg_error = total_error / len(self._calibration_history)
        
        # Determine trend
        if len(self._calibration_history) >= 5:
            recent = self._calibration_history[-5:]
            older = self._calibration_history[-10:-5] if len(self._calibration_history) >= 10 else []
            
            recent_avg = sum(r.predicted_confidence for r in recent) / len(recent)
            older_avg = sum(r.predicted_confidence for r in older) / len(older) if older else recent_avg
            
            diff = recent_avg - older_avg
            if diff > 0.02:
                trend = "increasing"
            elif diff < -0.02:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
        
        return {
            "calibration_error": round(avg_error, 4),
            "confidence_trend": trend,
            "streak_info": getattr(self, '_outcome_streak', {"success": 0, "failure": 0}).copy(),
            "sample_count": getattr(self, '_total_samples', 0),
            "current_confidence": round(self.state.self_confidence, 4),
        }
    
    def check_calibration_convergence(self, window: int = 10) -> Dict[str, Any]:
        """
        Check if confidence is converging to actual success rate.
        
        T17 AC: "连续失败：confidence 下调；连续成功：上调但有上限与惯性"
        
        Returns:
            Dict with convergence status and metrics
        """
        if not hasattr(self, '_calibration_history'):
            return {"converged": False, "reason": "no_data"}
        
        history = self._calibration_history
        if len(history) < window:
            return {"converged": False, "reason": f"insufficient_samples_{len(history)}_need_{window}"}
        
        # Calculate recent success rate
        recent = history[-window:]
        success_rate = sum(1 for r in recent if r.actual_outcome) / len(recent)
        
        # Compare to confidence
        confidence = self.state.self_confidence
        gap = abs(confidence - success_rate)
        
        # Converged if gap is small (< 0.1)
        converged = gap < 0.1
        
        return {
            "converged": converged,
            "success_rate": round(success_rate, 4),
            "confidence": round(confidence, 4),
            "gap": round(gap, 4),
            "window_size": window,
            "reason": "converged" if converged else f"gap_{gap:.4f}_too_large",
        }
    
    # === State Delta Logging ===
    
    def _log_state_delta(
        self,
        field: str,
        before: float,
        after: float,
        reason: str,
        predicted: Optional[float] = None,
        actual: Optional[float] = None,
    ) -> None:
        """Log a state change for traceability."""
        if abs(before - after) < 0.001:
            return  # Skip trivial changes
        
        update = HOTUpdate(
            field=field,
            before=before,
            after=after,
            predicted=predicted,
            actual=actual,
            reason=reason,
        )
        self.update_history.append(update)
        
        # Also log to state_delta format for MVP-10 ledger
        delta = {
            "module": "hot_self_model",
            "field": field,
            "before": round(before, 4),
            "after": round(after, 4),
            "predicted": round(predicted, 4) if predicted is not None else None,
            "actual": round(actual, 4) if actual is not None else None,
            "reason": reason,
            "ts": time.time(),
        }
        self._state_delta_log.append(delta)
    
    def get_state_delta_log(self) -> List[Dict[str, Any]]:
        """Get the log of all state changes."""
        return self._state_delta_log.copy()
    
    def clear_state_delta_log(self) -> None:
        """Clear the state change log."""
        self._state_delta_log = []
    
    def get_prediction_history(self) -> List[PredictionRecord]:
        """Get all prediction records."""
        return list(self.prediction_records.values())
    
    def get_unresolved_predictions(self) -> List[PredictionRecord]:
        """Get predictions that haven't been resolved yet."""
        return [r for r in self.prediction_records.values() if not r.resolved]
    
    # === Serialization ===
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize HOT state to dict."""
        return {
            "state": self.state.to_dict(),
            "update_count": len(self.update_history),
            "prediction_count": len(self.prediction_records),
            "resolved_predictions": sum(1 for r in self.prediction_records.values() if r.resolved),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HOTSelfModel":
        """Deserialize from dict."""
        state = HOTState.from_dict(data.get("state", {}))
        return cls(initial_state=state)


# === Global Instance (for convenience) ===

_hot_instance: Optional[HOTSelfModel] = None


def get_hot_self_model() -> HOTSelfModel:
    """Get or create the global HOT instance."""
    global _hot_instance
    if _hot_instance is None:
        _hot_instance = HOTSelfModel()
    return _hot_instance


def reset_hot_self_model() -> None:
    """Reset the global HOT instance."""
    global _hot_instance
    _hot_instance = None
