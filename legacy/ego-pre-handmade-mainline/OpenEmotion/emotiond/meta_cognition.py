"""
MVP-4 D5: Meta-cognition System for Reflection and Clarification

Enables the agent to recognize uncertainty and trigger reflection/clarification
behaviors instead of making premature decisions.

Core components:
- MetaCognitionTrigger: Detects when meta-cognition should be triggered
- MetaCognitionAction: Represents the action to take (ask_clarify, reflect, slow_down)
- MetaCognitionEngine: Main engine that evaluates state and returns actions

Trigger conditions:
- uncertainty > UNCERTAINTY_THRESHOLD (0.7)
- consecutive_prediction_errors >= 3
- high_impact_event_proximity (betrayal/rejection near threshold)
"""
import time
from typing import Dict, Any, Optional, Tuple, List
from pydantic import BaseModel, Field
from dataclasses import dataclass, field


class MetaCognitionAction(BaseModel):
    """
    Represents a meta-cognition action to modify decision behavior.
    
    Action types:
    - ask_clarify: Request clarification before proceeding
    - reflect: Add internal reflection to the decision
    - slow_down: Reduce intensity/confidence of language
    """
    action_type: str = Field(
        ...,
        description="Type of action: ask_clarify, reflect, or slow_down"
    )
    reason: str = Field(
        ...,
        description="Why this action was triggered"
    )
    suggested_response: str = Field(
        ...,
        description="Template for response modification"
    )
    intensity: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="How strongly to apply this action (0.0-1.0)"
    )
    trigger_source: str = Field(
        default="unknown",
        description="What triggered this action: uncertainty, prediction_error, or proximity"
    )


class MetaCognitionTrigger:
    """
    Detects when meta-cognition should be triggered based on state conditions.
    
    Trigger conditions:
    1. High uncertainty: uncertainty > UNCERTAINTY_THRESHOLD
    2. Prediction error streak: consecutive_prediction_errors >= 3
    3. Near-threshold events: high-impact event (betrayal/rejection) near but not at threshold
    """
    
    # Condition thresholds (can be overridden via environment or constructor)
    UNCERTAINTY_THRESHOLD = 0.7
    PREDICTION_ERROR_THRESHOLD = 0.3  # For consecutive errors
    NEAR_THRESHOLD_RATIO = 0.9  # For proximity detection
    MIN_PREDICTION_ERROR_STREAK = 3
    
    def __init__(
        self,
        uncertainty_threshold: float = None,
        prediction_error_threshold: float = None,
        near_threshold_ratio: float = None,
        min_prediction_error_streak: int = None
    ):
        """Initialize trigger with optional custom thresholds."""
        self.uncertainty_threshold = (
            uncertainty_threshold if uncertainty_threshold is not None 
            else self.UNCERTAINTY_THRESHOLD
        )
        self.prediction_error_threshold = (
            prediction_error_threshold if prediction_error_threshold is not None 
            else self.PREDICTION_ERROR_THRESHOLD
        )
        self.near_threshold_ratio = (
            near_threshold_ratio if near_threshold_ratio is not None 
            else self.NEAR_THRESHOLD_RATIO
        )
        self.min_prediction_error_streak = (
            min_prediction_error_streak if min_prediction_error_streak is not None 
            else self.MIN_PREDICTION_ERROR_STREAK
        )
    
    def should_trigger(
        self,
        state: Any,  # EmotionState
        context: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Evaluate if meta-cognition should trigger.
        
        Args:
            state: Current EmotionState with uncertainty, prediction_error, etc.
            context: Additional context including:
                - consecutive_prediction_errors: int
                - recent_events: List of recent events
                - relationship: Dict with bond, grudge, trust, etc.
        
        Returns:
            Tuple of (should_trigger: bool, reason: str)
        """
        # Check 1: High uncertainty
        uncertainty = getattr(state, 'uncertainty', 0.5)
        if uncertainty > self.uncertainty_threshold:
            return True, f"High uncertainty ({uncertainty:.2f} > {self.uncertainty_threshold})"
        
        # Check 2: Consecutive prediction errors
        consecutive_errors = context.get('consecutive_prediction_errors', 0)
        if consecutive_errors >= self.min_prediction_error_streak:
            return True, f"Consecutive prediction errors ({consecutive_errors} >= {self.min_prediction_error_streak})"
        
        # Check 3: Near-threshold high-impact event
        near_threshold_event = self._check_near_threshold_event(state, context)
        if near_threshold_event:
            return True, near_threshold_event
        
        return False, ""
    
    def _check_near_threshold_event(
        self,
        state: Any,
        context: Dict[str, Any]
    ) -> Optional[str]:
        """
        Check for high-impact events near but not at threshold.
        
        Specifically checks for betrayal/rejection signals that are close
        to triggering but haven't quite reached the threshold.
        """
        relationship = context.get('relationship', {})
        recent_events = context.get('recent_events', [])
        
        # Check grudge near threshold (could trigger betrayal-like response)
        grudge = relationship.get('grudge', 0.0)
        trust = relationship.get('trust', 0.5)
        
        # High grudge near threshold with low trust = risky situation
        if grudge >= self.near_threshold_ratio * 0.5 and trust < 0.3:
            return f"Near-threshold grudge ({grudge:.2f}) with low trust ({trust:.2f})"
        
        # Check for recent rejection/betrayal events
        for event in recent_events[-5:]:  # Last 5 events
            if isinstance(event, dict):
                meta = event.get('meta', {})
                subtype = meta.get('subtype') if meta else None
                
                if subtype == 'rejection':
                    # Rejection event with moderate intensity
                    intensity = meta.get('intensity', 0.5)
                    if intensity >= self.near_threshold_ratio * 0.5:
                        return f"Recent rejection event near threshold (intensity: {intensity:.2f})"
                
                elif subtype == 'betrayal':
                    # Any betrayal event is concerning
                    return f"Recent betrayal event detected"
        
        # Check affect state for high-arousal negative states
        valence = getattr(state, 'valence', 0.0)
        arousal = getattr(state, 'arousal', 0.3)
        anger = getattr(state, 'anger', 0.0)
        
        # High arousal + negative valence + elevated anger = volatile state
        if valence < -0.3 and arousal > 0.5 and anger > 0.3:
            return f"Volatile emotional state (valence: {valence:.2f}, arousal: {arousal:.2f}, anger: {anger:.2f})"
        
        return None


class MetaCognitionEngine:
    """
    Main engine for meta-cognition evaluation and action generation.
    
    Evaluates state and context to determine if meta-cognition should trigger,
    and if so, generates appropriate actions.
    """
    
    # Templates for different action types
    CLARIFICATION_TEMPLATES = {
        "zh": [
            "让我确认一下，你的意思是...？",
            "我想确保我理解正确，你是说...？",
            "能再解释一下吗？我想更好地理解你的意思。",
            "我需要确认一下，这样可以吗...？"
        ],
        "en": [
            "Let me make sure I understand - you mean...?",
            "I want to clarify - are you saying...?",
            "Could you help me understand better? I want to make sure I get this right.",
            "Just to confirm, by that you mean...?"
        ]
    }
    
    REFLECTION_TEMPLATES = {
        "zh": [
            "让我重新评估一下这个情况...",
            "我需要再想想这个...",
            "这个情况比较复杂，让我仔细考虑一下...",
            "我不太确定，让我重新思考..."
        ],
        "en": [
            "Let me reconsider this situation...",
            "I need to think about this more carefully...",
            "This is complex, let me reflect on it...",
            "I'm not entirely certain, let me reconsider..."
        ]
    }
    
    # Tone softening mappings
    TONE_SOFTENING = {
        # Chinese
        "肯定": "可能",
        "一定": "也许",
        "必须": "可以考虑",
        "应该": "或许",
        "确定": "我想",
        "绝对": "相对",
        # English
        "definitely": "probably",
        "certainly": "possibly",
        "must": "might want to",
        "should": "could",
        "surely": "perhaps",
        "absolutely": "relatively",
        "always": "often",
        "never": "rarely"
    }
    
    def __init__(
        self,
        trigger: Optional[MetaCognitionTrigger] = None,
        language: str = "zh"
    ):
        """
        Initialize the meta-cognition engine.
        
        Args:
            trigger: Custom MetaCognitionTrigger instance (optional)
            language: Default language for templates ("zh" or "en")
        """
        self.trigger = trigger or MetaCognitionTrigger()
        self.language = language
        self._prediction_error_history: List[float] = []
        self._last_trigger_time: float = 0.0
        self._min_trigger_interval: float = 60.0  # Minimum seconds between triggers
    
    def evaluate(
        self,
        state: Any,  # EmotionState
        context: Dict[str, Any]
    ) -> Optional[MetaCognitionAction]:
        """
        Evaluate if meta-cognition should trigger and return appropriate action.
        
        Args:
            state: Current EmotionState
            context: Additional context for evaluation
        
        Returns:
            MetaCognitionAction if triggered, None otherwise
        """
        # Rate limiting: don't trigger too frequently
        current_time = time.time()
        if current_time - self._last_trigger_time < self._min_trigger_interval:
            return None
        
        # Check trigger conditions
        should_trigger, reason = self.trigger.should_trigger(state, context)
        
        if not should_trigger:
            return None
        
        # Update trigger time
        self._last_trigger_time = current_time
        
        # Determine action type based on trigger source
        action_type = self._determine_action_type(state, context, reason)
        
        # Generate action
        action = self._generate_action(action_type, reason, state, context)
        
        return action
    
    def _determine_action_type(
        self,
        state: Any,
        context: Dict[str, Any],
        reason: str
    ) -> str:
        """
        Determine which action type to take based on the situation.
        
        Decision logic:
        - High uncertainty -> ask_clarify (need more information)
        - Prediction errors -> reflect (need to reconsider assumptions)
        - Near-threshold events -> slow_down (need to be cautious)
        """
        uncertainty = getattr(state, 'uncertainty', 0.5)
        consecutive_errors = context.get('consecutive_prediction_errors', 0)
        
        # High uncertainty: need clarification
        if uncertainty > self.trigger.uncertainty_threshold:
            return "ask_clarify"
        
        # Prediction error streak: need reflection
        if consecutive_errors >= self.trigger.min_prediction_error_streak:
            return "reflect"
        
        # Near-threshold event: slow down
        if "near-threshold" in reason.lower() or "volatile" in reason.lower():
            return "slow_down"
        
        # Default: ask for clarification
        return "ask_clarify"
    
    def _generate_action(
        self,
        action_type: str,
        reason: str,
        state: Any,
        context: Dict[str, Any]
    ) -> MetaCognitionAction:
        """Generate a MetaCognitionAction with appropriate response."""
        
        # Calculate intensity based on state
        intensity = self._calculate_intensity(state, context)
        
        # Get trigger source
        trigger_source = self._get_trigger_source(reason)
        
        if action_type == "ask_clarify":
            suggested = self.generate_clarification(context)
        elif action_type == "reflect":
            suggested = self.generate_reflection(state)
        elif action_type == "slow_down":
            suggested = "Applying caution to response."
        else:
            suggested = ""
        
        return MetaCognitionAction(
            action_type=action_type,
            reason=reason,
            suggested_response=suggested,
            intensity=intensity,
            trigger_source=trigger_source
        )
    
    def _calculate_intensity(self, state: Any, context: Dict[str, Any]) -> float:
        """Calculate how strongly to apply the meta-cognition action."""
        uncertainty = getattr(state, 'uncertainty', 0.5)
        consecutive_errors = context.get('consecutive_prediction_errors', 0)
        
        # Base intensity from uncertainty
        intensity = uncertainty
        
        # Boost for consecutive errors
        if consecutive_errors > 0:
            intensity = min(1.0, intensity + 0.1 * consecutive_errors)
        
        return min(1.0, max(0.0, intensity))
    
    def _get_trigger_source(self, reason: str) -> str:
        """Extract the trigger source from the reason string."""
        reason_lower = reason.lower()
        
        if "uncertainty" in reason_lower:
            return "uncertainty"
        elif "prediction error" in reason_lower:
            return "prediction_error"
        elif "near-threshold" in reason_lower or "volatile" in reason_lower:
            return "proximity"
        else:
            return "unknown"
    
    def generate_clarification(self, context: Dict[str, Any]) -> str:
        """
        Generate a clarification question.
        
        Args:
            context: Context containing user input, situation, etc.
        
        Returns:
            A clarification question template
        """
        import random
        
        lang = context.get('language', self.language)
        templates = self.CLARIFICATION_TEMPLATES.get(lang, self.CLARIFICATION_TEMPLATES['en'])
        
        # Select appropriate template based on context
        if context.get('has_question'):
            # User asked something - we need to confirm understanding
            return templates[0]
        elif context.get('emotional_content'):
            # Emotional content - express care
            return templates[2]
        else:
            # Default: random selection
            return random.choice(templates)
    
    def generate_reflection(self, state: Any) -> str:
        """
        Generate internal reflection text.
        
        Args:
            state: Current EmotionState
        
        Returns:
            An internal reflection string
        """
        import random
        
        # Get state values for context-aware reflection
        valence = getattr(state, 'valence', 0.0)
        uncertainty = getattr(state, 'uncertainty', 0.5)
        
        templates = self.REFLECTION_TEMPLATES.get(self.language, self.REFLECTION_TEMPLATES['en'])
        
        # Select based on emotional state
        if valence < -0.3:
            # Negative state - more cautious reflection
            return templates[2]
        elif uncertainty > 0.8:
            # Very uncertain - express uncertainty
            return templates[3]
        else:
            return random.choice(templates[:2])
    
    def soften_tone(self, text: str) -> str:
        """
        Soften the tone of a text by replacing assertive words.
        
        Args:
            text: Original text
        
        Returns:
            Text with softened tone
        """
        result = text
        for strong, soft in self.TONE_SOFTENING.items():
            # Case-insensitive replacement
            import re
            pattern = re.compile(re.escape(strong), re.IGNORECASE)
            result = pattern.sub(soft, result)
        
        return result
    
    def update_prediction_error_history(self, error: float):
        """Track prediction error history for streak detection."""
        self._prediction_error_history.append(error)
        
        # Keep only recent history
        if len(self._prediction_error_history) > 10:
            self._prediction_error_history = self._prediction_error_history[-10:]
    
    def get_consecutive_prediction_errors(self, threshold: float = 0.3) -> int:
        """Count consecutive prediction errors above threshold."""
        count = 0
        for error in reversed(self._prediction_error_history):
            if error > threshold:
                count += 1
            else:
                break
        return count


# Global instance for convenience
_meta_cognition_engine: Optional[MetaCognitionEngine] = None


def get_meta_cognition_engine() -> MetaCognitionEngine:
    """Get or create the global meta-cognition engine."""
    global _meta_cognition_engine
    if _meta_cognition_engine is None:
        _meta_cognition_engine = MetaCognitionEngine()
    return _meta_cognition_engine


def reset_meta_cognition_engine():
    """Reset the global meta-cognition engine (for testing)."""
    global _meta_cognition_engine
    _meta_cognition_engine = None


def apply_meta_cognition_to_decision(
    decision: Dict[str, Any],
    meta_action: MetaCognitionAction
) -> Dict[str, Any]:
    """
    Apply a meta-cognition action to a decision dict.
    
    Args:
        decision: The decision dict to modify
        meta_action: The meta-cognition action to apply
    
    Returns:
        Modified decision dict
    """
    if meta_action.action_type == "ask_clarify":
        # Add clarification to response
        if "explanation" in decision:
            decision["explanation"].append(meta_action.suggested_response)
        decision["meta_action"] = meta_action.model_dump()
        decision["needs_clarification"] = True
    
    elif meta_action.action_type == "reflect":
        # Add reflection to explanation
        if "explanation" in decision:
            decision["explanation"].append(meta_action.suggested_response)
        decision["meta_action"] = meta_action.model_dump()
        decision["internal_reflection"] = meta_action.suggested_response
    
    elif meta_action.action_type == "slow_down":
        # Soften tone
        if "tone" in decision:
            decision["tone"] = soften_decision_tone(decision["tone"])
        
        # Add caution note
        if "key_points" in decision:
            decision["key_points"].insert(0, "Proceeding with caution due to uncertainty")
        
        decision["meta_action"] = meta_action.model_dump()
        decision["caution_applied"] = True
    
    return decision


def soften_decision_tone(tone: str) -> str:
    """
    Soften a decision tone.
    
    Maps assertive tones to softer alternatives.
    """
    tone_mapping = {
        "confident": "cautious",
        "assertive": "tentative",
        "certain": "uncertain",
        "definitive": "exploratory",
        "cold": "neutral",
        "retaliatory": "guarded",
        # Preserve softer tones
        "warm": "warm",
        "soft": "soft",
        "neutral": "neutral",
        "guarded": "guarded",
        "cautious": "cautious"
    }
    
    return tone_mapping.get(tone.lower(), tone)


# Sustainability tracking
class MetaCognitionTracker:
    """
    Tracks meta-cognition triggering for sustainability analysis.
    
    Ensures meta-cognition:
    - Is not triggered too frequently
    - Is not triggered on confident decisions
    - Triggers consistently in uncertain situations
    """
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.trigger_history: List[Dict[str, Any]] = []
        self.total_evaluations = 0
        self.total_triggers = 0
    
    def record_evaluation(self, triggered: bool, uncertainty: float, reason: str = ""):
        """Record an evaluation for analysis."""
        self.total_evaluations += 1
        if triggered:
            self.total_triggers += 1
        
        self.trigger_history.append({
            "timestamp": time.time(),
            "triggered": triggered,
            "uncertainty": uncertainty,
            "reason": reason
        })
        
        # Trim history
        if len(self.trigger_history) > self.window_size:
            self.trigger_history = self.trigger_history[-self.window_size:]
    
    def get_trigger_rate(self) -> float:
        """Get the rate of triggering in recent history."""
        if not self.trigger_history:
            return 0.0
        
        recent = self.trigger_history[-self.window_size:]
        triggered = sum(1 for r in recent if r["triggered"])
        return triggered / len(recent)
    
    def is_triggering_sustainable(self, max_rate: float = 0.3) -> bool:
        """Check if triggering rate is within sustainable bounds."""
        return self.get_trigger_rate() <= max_rate
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get sustainability statistics."""
        return {
            "total_evaluations": self.total_evaluations,
            "total_triggers": self.total_triggers,
            "trigger_rate": self.get_trigger_rate(),
            "is_sustainable": self.is_triggering_sustainable(),
            "recent_triggers": self.trigger_history[-10:]
        }


# Global tracker
_tracker: Optional[MetaCognitionTracker] = None


def get_meta_cognition_tracker() -> MetaCognitionTracker:
    """Get or create the global tracker."""
    global _tracker
    if _tracker is None:
        _tracker = MetaCognitionTracker()
    return _tracker
