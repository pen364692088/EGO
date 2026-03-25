"""
MVP-5 D3: Intrinsic Motivation System

Upgrades Curiosity/Boredom/Confusion to emerge from expected_info_gain and predictability:
- high expected_info_gain -> curiosity increase (ask_clarify/ask_more/propose_experiment guidance)
- sustained low info_gain + low prediction_error -> boredom increase (shift_topic/request_specific_goal guidance)
- high non-converging prediction_error -> confusion increase

Integrates with meta-cognition and decision explore tendency when social_threat is low.
"""
import time
import math
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field
from pydantic import BaseModel, Field


@dataclass
class InfoGainHistory:
    """History of information gain values for detecting sustained patterns."""
    values: List[float] = field(default_factory=list)
    timestamps: List[float] = field(default_factory=list)
    max_window_size: int = 20
    
    def add(self, value: float, timestamp: Optional[float] = None):
        """Add a new info gain value."""
        if timestamp is None:
            timestamp = time.time()
        self.values.append(value)
        self.timestamps.append(timestamp)
        
        # Keep only recent values
        if len(self.values) > self.max_window_size:
            self.values = self.values[-self.max_window_size:]
            self.timestamps = self.timestamps[-self.max_window_size:]
    
    def get_recent_average(self, window_size: int = 5) -> float:
        """Get average of recent values."""
        if not self.values:
            return 0.0
        recent = self.values[-window_size:]
        return sum(recent) / len(recent)
    
    def get_sustained_low_duration(self, threshold: float = 0.2) -> float:
        """Get duration of sustained low info gain (in seconds)."""
        if len(self.values) < 3:
            return 0.0
        
        # Find how long values have been below threshold
        low_count = 0
        for i in range(len(self.values) - 1, -1, -1):
            if self.values[i] < threshold:
                low_count += 1
            else:
                break
        
        if low_count < 3:
            return 0.0
        
        # Calculate duration from timestamps
        if len(self.timestamps) >= low_count:
            return self.timestamps[-1] - self.timestamps[-low_count]
        return 0.0
    
    def clear(self):
        """Clear history."""
        self.values = []
        self.timestamps = []


@dataclass
class PredictionErrorHistory:
    """History of prediction errors for detecting non-convergence."""
    values: List[float] = field(default_factory=list)
    timestamps: List[float] = field(default_factory=list)
    max_window_size: int = 10
    
    def add(self, value: float, timestamp: Optional[float] = None):
        """Add a new prediction error value."""
        if timestamp is None:
            timestamp = time.time()
        self.values.append(value)
        self.timestamps.append(timestamp)
        
        # Keep only recent values
        if len(self.values) > self.max_window_size:
            self.values = self.values[-self.max_window_size:]
            self.timestamps = self.timestamps[-self.max_window_size:]
    
    def is_non_converging(self, threshold: float = 0.3, min_samples: int = 3) -> bool:
        """Check if prediction errors are not converging (high and sustained)."""
        if len(self.values) < min_samples:
            return False
        
        recent = self.values[-min_samples:]
        # Non-converging = all recent errors are high
        return all(e > threshold for e in recent)
    
    def get_trend(self, window_size: int = 5) -> float:
        """Get trend of prediction errors (positive = increasing, negative = decreasing)."""
        if len(self.values) < 2:
            return 0.0
        
        recent = self.values[-window_size:]
        if len(recent) < 2:
            return 0.0
        
        # Simple linear trend
        n = len(recent)
        x_mean = (n - 1) / 2
        y_mean = sum(recent) / n
        
        numerator = sum((i - x_mean) * (recent[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0.0
        return numerator / denominator
    
    def clear(self):
        """Clear history."""
        self.values = []
        self.timestamps = []


class IntrinsicMotivationState(BaseModel):
    """
    Intrinsic motivation state with curiosity, boredom, and confusion.
    
    These emerge from expected_info_gain and predictability rather than
    being direct mappings from appraisal dimensions.
    """
    curiosity: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Curiosity level (0-1), emerges from high expected_info_gain"
    )
    boredom: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Boredom level (0-1), emerges from sustained low info_gain + low prediction_error"
    )
    confusion: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confusion level (0-1), emerges from high non-converging prediction_error"
    )
    expected_info_gain: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Expected information gain from current interaction"
    )
    predictability: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="How predictable the current situation is (1.0 = fully predictable)"
    )
    exploration_tendency: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Tendency to explore (increases with curiosity when social_threat is low)"
    )
    
    # Trace/explanation fields
    curiosity_trace: str = Field(
        default="",
        description="Explanation for curiosity level"
    )
    boredom_trace: str = Field(
        default="",
        description="Explanation for boredom level"
    )
    confusion_trace: str = Field(
        default="",
        description="Explanation for confusion level"
    )
    info_gain_trace: str = Field(
        default="",
        description="Explanation for expected_info_gain calculation"
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "curiosity": self.curiosity,
            "boredom": self.boredom,
            "confusion": self.confusion,
            "expected_info_gain": self.expected_info_gain,
            "predictability": self.predictability,
            "exploration_tendency": self.exploration_tendency,
            "curiosity_trace": self.curiosity_trace,
            "boredom_trace": self.boredom_trace,
            "confusion_trace": self.confusion_trace,
            "info_gain_trace": self.info_gain_trace,
        }


class IntrinsicMotivationEngine:
    """
    Engine for computing intrinsic motivation from expected_info_gain and predictability.
    """
    
    # Thresholds for emotion emergence
    CURIOSITY_INFO_GAIN_THRESHOLD = 0.6  # High info gain triggers curiosity
    BOREDOM_INFO_GAIN_THRESHOLD = 0.2    # Low info gain contributes to boredom
    BOREDOM_PREDICTION_ERROR_THRESHOLD = 0.15  # Low prediction error contributes to boredom
    CONFUSION_PREDICTION_ERROR_THRESHOLD = 0.4  # High prediction error triggers confusion
    
    # Time constants (in seconds)
    BOREDOM_SUSTAINED_LOW_DURATION = 60.0  # 1 minute of low info gain
    CONFUSION_NON_CONVERGING_WINDOW = 3    # Number of consecutive high errors
    
    # Decay rates
    CURIOSITY_DECAY = 0.1
    BOREDOM_DECAY = 0.05
    CONFUSION_DECAY = 0.15
    
    def __init__(self, seed: Optional[int] = None):
        """Initialize the engine with optional seed for determinism."""
        self.state = IntrinsicMotivationState()
        self.info_gain_history = InfoGainHistory()
        self.prediction_error_history = PredictionErrorHistory()
        self._rng_seed = seed
        
    def compute_expected_info_gain(
        self,
        uncertainty: float,
        novelty: float,
        social_threat: float,
        text: Optional[str] = None
    ) -> Tuple[float, str]:
        """
        Compute expected information gain from current context.
        
        Info gain is higher when:
        - Uncertainty is high (more to learn)
        - Novelty is high (new information)
        - Social threat is low (safe to explore)
        - Text contains questions or new topics
        
        Returns:
            Tuple of (expected_info_gain, explanation)
        """
        # Base info gain from uncertainty and novelty
        base_gain = (uncertainty * 0.4 + novelty * 0.4)
        
        # Social threat reduces expected info gain (defensive mode)
        threat_factor = 1.0 - (social_threat * 0.5)
        
        # Text analysis for info gain signals
        text_bonus = 0.0
        text_reason = ""
        if text:
            text_lower = text.lower()
            
            # Questions indicate info seeking
            if any(w in text_lower for w in ["?", "什么", "怎么", "为什么", "如何", "who", "what", "how", "why"]):
                text_bonus += 0.15
                text_reason = "question detected"
            
            # New topic indicators
            elif any(w in text_lower for w in ["new", "different", "试试", "尝试", "experiment", "test"]):
                text_bonus += 0.1
                text_reason = "new topic/experiment"
            
            # Explanations provide info
            elif any(w in text_lower for w in ["because", "原因", "解释", "explain", "reason"]):
                text_bonus += 0.08
                text_reason = "explanatory content"
        
        info_gain = min(1.0, base_gain * threat_factor + text_bonus)
        
        explanation = (
            f"base={base_gain:.2f}(uncertainty={uncertainty:.2f}, novelty={novelty:.2f}) "
            f"* threat_factor={threat_factor:.2f}(social_threat={social_threat:.2f}) "
            f"+ text_bonus={text_bonus:.2f}{f'({text_reason})' if text_reason else ''} "
            f"= {info_gain:.2f}"
        )
        
        return info_gain, explanation
    
    def compute_predictability(
        self,
        prediction_error: float,
        uncertainty: float,
        recent_prediction_errors: List[float]
    ) -> Tuple[float, str]:
        """
        Compute predictability of current situation.
        
        Predictability is higher when:
        - Prediction errors are low
        - Uncertainty is low
        - Recent errors are converging (decreasing)
        
        Returns:
            Tuple of (predictability, explanation)
        """
        # Base predictability from current error and uncertainty
        base_pred = 1.0 - max(prediction_error, uncertainty * 0.5)
        
        # Trend factor: converging errors increase predictability
        trend = self.prediction_error_history.get_trend()
        trend_factor = 1.0
        if trend < -0.01:  # Errors decreasing
            trend_factor = 1.1
        elif trend > 0.01:  # Errors increasing
            trend_factor = 0.9
        
        predictability = max(0.0, min(1.0, base_pred * trend_factor))
        
        explanation = (
            f"base={base_pred:.2f}(prediction_error={prediction_error:.2f}, uncertainty={uncertainty:.2f}) "
            f"* trend_factor={trend_factor:.2f}(trend={trend:+.3f}) = {predictability:.2f}"
        )
        
        return predictability, explanation
    
    def update(
        self,
        uncertainty: float = 0.5,
        novelty: float = 0.0,
        social_threat: float = 0.0,
        prediction_error: float = 0.0,
        text: Optional[str] = None,
        dt: float = 1.0
    ) -> IntrinsicMotivationState:
        """
        Update intrinsic motivation state based on current context.
        
        This is the main entry point that computes expected_info_gain and predictability,
        then derives curiosity, boredom, and confusion.
        """
        # Compute expected info gain
        info_gain, info_gain_trace = self.compute_expected_info_gain(
            uncertainty=uncertainty,
            novelty=novelty,
            social_threat=social_threat,
            text=text
        )
        self.state.expected_info_gain = info_gain
        self.state.info_gain_trace = info_gain_trace
        
        # Add to history
        self.info_gain_history.add(info_gain)
        self.prediction_error_history.add(prediction_error)
        
        # Compute predictability
        predictability, _ = self.compute_predictability(
            prediction_error=prediction_error,
            uncertainty=uncertainty,
            recent_prediction_errors=self.prediction_error_history.values
        )
        self.state.predictability = predictability
        
        # Update curiosity: high expected_info_gain -> curiosity increase
        curiosity_delta = 0.0
        curiosity_trace_parts = []
        
        if info_gain > self.CURIOSITY_INFO_GAIN_THRESHOLD:
            curiosity_delta = (info_gain - self.CURIOSITY_INFO_GAIN_THRESHOLD) * 0.5
            curiosity_trace_parts.append(f"high_info_gain({info_gain:.2f})")
        
        # Low social threat allows curiosity to grow
        if social_threat < 0.3 and curiosity_delta > 0:
            curiosity_delta *= 1.2  # Boost when safe
            curiosity_trace_parts.append(f"low_threat({social_threat:.2f})")
        
        self.state.curiosity = min(1.0, self.state.curiosity + curiosity_delta)
        self.state.curiosity = max(0.0, self.state.curiosity - self.CURIOSITY_DECAY * dt)
        
        if curiosity_trace_parts:
            self.state.curiosity_trace = f"Increased by: {', '.join(curiosity_trace_parts)}"
        else:
            self.state.curiosity_trace = f"Decayed to {self.state.curiosity:.2f} (no triggers)"
        
        # Update boredom: sustained low info_gain + low prediction_error -> boredom increase
        boredom_delta = 0.0
        boredom_trace_parts = []
        
        sustained_low_duration = self.info_gain_history.get_sustained_low_duration(
            threshold=self.BOREDOM_INFO_GAIN_THRESHOLD
        )
        
        if info_gain < self.BOREDOM_INFO_GAIN_THRESHOLD:
            if prediction_error < self.BOREDOM_PREDICTION_ERROR_THRESHOLD:
                # Both low info gain and low prediction error = predictable and uninformative
                boredom_delta = 0.1 * dt
                boredom_trace_parts.append(
                    f"low_info_gain({info_gain:.2f}) + low_prediction_error({prediction_error:.2f})"
                )
            
            # Sustained low info gain increases boredom
            if sustained_low_duration > self.BOREDOM_SUSTAINED_LOW_DURATION:
                boredom_delta += 0.05 * dt
                boredom_trace_parts.append(f"sustained_low({sustained_low_duration:.0f}s)")
        
        self.state.boredom = min(1.0, self.state.boredom + boredom_delta)
        self.state.boredom = max(0.0, self.state.boredom - self.BOREDOM_DECAY * dt)
        
        if boredom_trace_parts:
            self.state.boredom_trace = f"Increased by: {', '.join(boredom_trace_parts)}"
        else:
            self.state.boredom_trace = f"Decayed to {self.state.boredom:.2f} (no triggers)"
        
        # Update confusion: high non-converging prediction_error -> confusion increase
        confusion_delta = 0.0
        confusion_trace_parts = []
        
        is_non_converging = self.prediction_error_history.is_non_converging(
            threshold=self.CONFUSION_PREDICTION_ERROR_THRESHOLD,
            min_samples=self.CONFUSION_NON_CONVERGING_WINDOW
        )
        
        if prediction_error > self.CONFUSION_PREDICTION_ERROR_THRESHOLD:
            confusion_delta = (prediction_error - self.CONFUSION_PREDICTION_ERROR_THRESHOLD) * 0.4
            confusion_trace_parts.append(f"high_prediction_error({prediction_error:.2f})")
            
            if is_non_converging:
                confusion_delta += 0.1
                confusion_trace_parts.append("non_converging")
        
        self.state.confusion = min(1.0, self.state.confusion + confusion_delta)
        self.state.confusion = max(0.0, self.state.confusion - self.CONFUSION_DECAY * dt)
        
        if confusion_trace_parts:
            self.state.confusion_trace = f"Increased by: {', '.join(confusion_trace_parts)}"
        else:
            self.state.confusion_trace = f"Decayed to {self.state.confusion:.2f} (no triggers)"
        
        # Update exploration tendency: curiosity-driven when social_threat is low
        if social_threat < 0.4:
            self.state.exploration_tendency = min(1.0, self.state.curiosity * 1.2)
        else:
            # High threat suppresses exploration
            self.state.exploration_tendency = self.state.curiosity * 0.5
        
        return self.state
    
    def get_guidance(self) -> Dict[str, Any]:
        """
        Get guidance for meta-cognition and decision based on intrinsic motivation.
        
        Returns:
            Dict with guidance for ask_clarify, ask_more, shift_topic, propose_experiment
        """
        guidance = {
            "ask_clarify": False,
            "ask_more": False,
            "shift_topic": False,
            "propose_experiment": False,
            "reason": ""
        }
        
        reasons = []
        
        # High curiosity -> ask_more or propose_experiment
        if self.state.curiosity > 0.6:
            guidance["ask_more"] = True
            reasons.append(f"curiosity({self.state.curiosity:.2f})")
            
            if self.state.curiosity > 0.8:
                guidance["propose_experiment"] = True
                reasons.append("high_curiosity")
        
        # High confusion -> ask_clarify
        if self.state.confusion > 0.5:
            guidance["ask_clarify"] = True
            reasons.append(f"confusion({self.state.confusion:.2f})")
        
        # High boredom -> shift_topic
        if self.state.boredom > 0.5:
            guidance["shift_topic"] = True
            reasons.append(f"boredom({self.state.boredom:.2f})")
        
        guidance["reason"] = "; ".join(reasons) if reasons else "no_intrinsic_triggers"
        
        return guidance
    
    def reset(self):
        """Reset the engine to initial state."""
        self.state = IntrinsicMotivationState()
        self.info_gain_history.clear()
        self.prediction_error_history.clear()


# Global engine instance (singleton pattern for integration)
_intrinsic_engine: Optional[IntrinsicMotivationEngine] = None


def get_intrinsic_engine(seed: Optional[int] = None) -> IntrinsicMotivationEngine:
    """Get the global intrinsic motivation engine instance."""
    global _intrinsic_engine
    if _intrinsic_engine is None:
        _intrinsic_engine = IntrinsicMotivationEngine(seed=seed)
    return _intrinsic_engine


def reset_intrinsic_engine():
    """Reset the global intrinsic motivation engine."""
    global _intrinsic_engine
    _intrinsic_engine = None


def compute_intrinsic_motivation(
    uncertainty: float = 0.5,
    novelty: float = 0.0,
    social_threat: float = 0.0,
    prediction_error: float = 0.0,
    text: Optional[str] = None,
    dt: float = 1.0,
    seed: Optional[int] = None
) -> IntrinsicMotivationState:
    """
    Convenience function to compute intrinsic motivation in one call.
    
    This is the main API for integration with meta-cognition and decision.
    """
    engine = get_intrinsic_engine(seed=seed)
    return engine.update(
        uncertainty=uncertainty,
        novelty=novelty,
        social_threat=social_threat,
        prediction_error=prediction_error,
        text=text,
        dt=dt
    )


def apply_intrinsic_to_meta_cognition(
    meta_cognition_context: Dict[str, Any],
    intrinsic_state: IntrinsicMotivationState
) -> Dict[str, Any]:
    """
    Apply intrinsic motivation guidance to meta-cognition context.
    
    Integrates intrinsic motivation with meta-cognition by adding
    ask_more, shift_topic, propose_experiment to the context.
    """
    guidance = intrinsic_state.to_dict()
    
    # Add intrinsic triggers to context
    meta_cognition_context["intrinsic_motivation"] = guidance
    
    # Add specific flags for meta-cognition to consider
    if intrinsic_state.curiosity > 0.6:
        meta_cognition_context["intrinsic_ask_more"] = True
    if intrinsic_state.boredom > 0.5:
        meta_cognition_context["intrinsic_shift_topic"] = True
    if intrinsic_state.confusion > 0.5:
        meta_cognition_context["intrinsic_ask_clarify"] = True
    
    return meta_cognition_context


def apply_intrinsic_to_decision(
    decision_context: Dict[str, Any],
    intrinsic_state: IntrinsicMotivationState,
    social_threat: float = 0.0
) -> Dict[str, Any]:
    """
    Apply intrinsic motivation to decision context.
    
    Increases explore tendency when curiosity is high and social_threat is low.
    """
    # Only increase exploration when safe
    if social_threat < 0.4:
        decision_context["intrinsic_explore_boost"] = intrinsic_state.exploration_tendency * 0.3
    else:
        decision_context["intrinsic_explore_boost"] = 0.0
    
    decision_context["intrinsic_motivation"] = intrinsic_state.to_dict()
    
    return decision_context
