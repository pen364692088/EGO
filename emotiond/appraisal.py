"""
MVP-4 D2: Appraisal Engine

Implements a 5-dimensional appraisal system that transforms events into 
structured evaluations based on cognitive appraisal theory.

Appraisal dimensions:
- goal_progress [-1, 1]: 趋近/受阻 (approaching/blocked)
- expectation_violation [0, 1]: 违背预期/承诺
- controllability [0, 1]: 我能不能改变局势
- social_threat [0, 1]: 关系威胁
- novelty [0, 1]: 新奇/信息增益
"""
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field
from emotiond.models import Event
from emotiond.other_minds import apply_other_minds_to_appraisal
from emotiond.state import AffectState, MoodState, BondState


class AppraisalResult(BaseModel):
    """
    Structured appraisal result for an event.
    
    Contains 5 appraisal dimensions plus derived emotion label and intensity.
    """
    goal_progress: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
        description="How much the event moves toward (+) or away from (-) goals"
    )
    expectation_violation: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="How much the event violates expectations or promises"
    )
    controllability: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="How much control the agent has over the situation"
    )
    social_threat: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="How much the event threatens social relationships"
    )
    novelty: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="How novel or surprising the event is"
    )
    observed_delta: Dict[str, float] = Field(
        default_factory=lambda: {"safety": 0.0, "energy": 0.0},
        description="Observed changes in interoceptive states for learning"
    )
    emotion_label: str = Field(
        default="neutral",
        description="Primary emotion label: joy, sadness, fear, anger, curiosity, confusion, boredom"
    )
    intensity: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Intensity of the emotion (0.0 to 1.0)"
    )
    reasoning: List[str] = Field(
        default_factory=list,
        description="Explanation for each appraisal dimension"
    )


class AppraisalContext(BaseModel):
    """
    Context for appraisal computation.
    
    Combines affect, mood, and relationship state for context-aware appraisal.
    """
    affect: Optional[Dict[str, float]] = None
    mood: Optional[Dict[str, float]] = None
    bond: Optional[Dict[str, float]] = None
    event_history: Optional[List[Dict[str, Any]]] = None
    promise_state: Optional[Dict[str, Any]] = None  # Track promises made
    cold_treatment_duration: float = 0.0  # How long the cold treatment has been going
    target: Optional[str] = None  # target for other-minds modulation


# Event subtype to appraisal dimension mappings
EVENT_APPRAISAL_SIGNATURES = {
    # Positive events
    "care": {
        "goal_progress": 0.4,
        "expectation_violation": 0.0,
        "controllability": 0.3,
        "social_threat": 0.0,
        "novelty": 0.2,
    },
    "apology": {
        "goal_progress": 0.2,
        "expectation_violation": 0.1,  # Mild surprise
        "controllability": 0.4,
        "social_threat": 0.0,
        "novelty": 0.3,
    },
    "repair_success": {
        "goal_progress": 0.5,
        "expectation_violation": 0.0,
        "controllability": 0.6,
        "social_threat": 0.0,
        "novelty": 0.1,
    },
    # Negative events
    "rejection": {
        "goal_progress": -0.5,
        "expectation_violation": 0.3,
        "controllability": 0.2,
        "social_threat": 0.7,
        "novelty": 0.3,
    },
    "betrayal": {
        "goal_progress": -0.7,
        "expectation_violation": 0.8,
        "controllability": 0.3,
        "social_threat": 0.9,
        "novelty": 0.5,
    },
    "ignored": {
        "goal_progress": -0.2,
        "expectation_violation": 0.2,
        "controllability": 0.1,
        "social_threat": 0.4,
        "novelty": 0.1,
    },
    # Neutral
    "neutral": {
        "goal_progress": 0.0,
        "expectation_violation": 0.0,
        "controllability": 0.5,
        "social_threat": 0.0,
        "novelty": 0.0,
    },
    "time_passed": {
        "goal_progress": 0.0,
        "expectation_violation": 0.0,
        "controllability": 1.0,  # Time is uncontrollable
        "social_threat": 0.0,
        "novelty": 0.0,
    },
    # Uncertainty
    "uncertain": {
        "goal_progress": 0.0,
        "expectation_violation": 0.3,
        "controllability": 0.3,
        "social_threat": 0.2,
        "novelty": 0.5,
    },
}


def compute_goal_progress(
    event: Event,
    context: AppraisalContext,
    base_value: float = 0.0
) -> Tuple[float, str]:
    """
    Compute goal_progress dimension.
    
    Positive = moving toward goals, Negative = blocked/obstacles.
    
    Contextual factors:
    - Promise breaks → more negative
    - Long cold treatment → more negative when finally acknowledged
    - Positive user messages → positive
    """
    reasoning = []
    value = base_value
    
    # Base value from event subtype signature
    subtype = event.meta.get("subtype", "neutral") if event.meta else "neutral"
    
    # Check for promise context
    if context.promise_state:
        promise_broken = context.promise_state.get("broken", False)
        promise_made = context.promise_state.get("made", False)
        
        if promise_broken:
            # "算了" after a promise → blocked goal
            value = min(value, -0.6)
            reasoning.append("Goal blocked by promise break")
        elif promise_made and event.text and "算了" in event.text:
            # "算了" after a promise made by the other party
            value = -0.5
            reasoning.append("Dismissive response after promise")
    
    # Check for cold treatment duration
    if context.cold_treatment_duration > 0:
        # Longer cold treatment → more significant when contact resumes
        if subtype == "care" or (event.text and any(w in event.text.lower() for w in ["好", "嗯", "好的"])):
            # Finally acknowledged after cold treatment
            if context.cold_treatment_duration > 3600:  # > 1 hour
                value = min(value + 0.3, 0.6)
                reasoning.append(f"Relief after {context.cold_treatment_duration/60:.0f}min cold treatment")
            else:
                value = min(value + 0.1, 0.4)
                reasoning.append("Brief acknowledgment")
        elif event.text and "算了" in event.text:
            # "算了" during cold treatment
            if context.cold_treatment_duration > 3600:
                value = -0.7
                reasoning.append("Dismissive after extended cold treatment")
    
    # Event text analysis
    if event.text:
        text_lower = event.text.lower()
        
        # Positive signals
        if any(w in text_lower for w in ["好", "好的", "嗯", "行", "可以", "同意"]):
            if not reasoning:
                value = max(value, 0.2)
                reasoning.append("Agreement/acceptance")
        elif any(w in text_lower for w in ["谢谢", "感谢", "喜欢", "爱"]):
            value = max(value, 0.4)
            reasoning.append("Positive expression")
        elif any(w in text_lower for w in ["成功", "完成", "达成"]):
            value = max(value, 0.5)
            reasoning.append("Goal achievement")
        
        # Negative signals
        elif any(w in text_lower for w in ["算了", "不用了", "放弃"]):
            if not reasoning:
                value = min(value, -0.3)
                reasoning.append("Dismissive/rejection")
        elif any(w in text_lower for w in ["不行", "不能", "拒绝"]):
            value = min(value, -0.4)
            reasoning.append("Explicit refusal")
        elif any(w in text_lower for w in ["失败", "错过", "损失"]):
            value = min(value, -0.5)
            reasoning.append("Goal failure")
    
    if not reasoning:
        reasoning.append(f"Base goal_progress from {subtype}: {base_value:.2f}")
    
    # Clamp to [-1, 1]
    value = max(-1.0, min(1.0, value))
    
    return value, reasoning[0] if reasoning else f"Base: {base_value:.2f}"


def compute_expectation_violation(
    event: Event,
    context: AppraisalContext,
    base_value: float = 0.0
) -> Tuple[float, str]:
    """
    Compute expectation_violation dimension.
    
    Higher = more unexpected/violating of expectations.
    
    Contextual factors:
    - Promise breaks → high violation
    - Unpredictable behavior → higher violation
    - Consistent patterns → lower violation
    """
    reasoning = []
    value = base_value
    
    # Check for promise breaks explicitly
    if context.promise_state and context.promise_state.get("broken", False):
        value = max(value, 0.7)
        reasoning.append("Promise broken")
    
    # Event text analysis for explicit promise mentions
    if event.text:
        text_lower = event.text.lower()
        
        # Breaking commitment patterns
        if any(w in text_lower for w in ["本来", "说好", "答应", "承诺"]):
            if any(w in text_lower for w in ["但是", "可是", "算了"]):
                value = max(value, 0.6)
                reasoning.append("Broken commitment language")
        
        # Unexpected rejection
        if "算了" in text_lower:
            # Check context for expectation
            if context.bond and context.bond.get("bond", 0) > 0.5:
                # High bond → unexpected rejection
                value = max(value, 0.5)
                reasoning.append("Unexpected rejection from close relationship")
    
    # Check relationship context
    if context.bond:
        trust = context.bond.get("trust", 0.5)
        # Low trust → lower expectation of good behavior
        if trust < 0.3 and value > 0.3:
            value *= 0.7  # Reduce violation when trust is already low
            reasoning.append("Low trust reduces expectation")
    
    if not reasoning:
        reasoning.append(f"Base expectation_violation: {base_value:.2f}")
    
    # Clamp to [0, 1]
    value = max(0.0, min(1.0, value))
    
    return value, reasoning[0]


def compute_controllability(
    event: Event,
    context: AppraisalContext,
    base_value: float = 0.5
) -> Tuple[float, str]:
    """
    Compute controllability dimension.
    
    Higher = more control over the situation.
    
    Contextual factors:
    - Own actions → higher controllability
    - External events → lower controllability
    - Time-based events → zero controllability
    """
    reasoning = []
    value = base_value
    
    # Event type affects controllability
    if event.type == "user_message":
        # User messages are somewhat controllable (we can respond)
        value = max(value, 0.4)
        reasoning.append("User message - moderate control via response")
    elif event.type == "assistant_reply":
        # Own replies are highly controllable
        value = max(value, 0.8)
        reasoning.append("Own action - high control")
    elif event.type == "world_event":
        # World events depend on subtype
        subtype = event.meta.get("subtype", "neutral") if event.meta else "neutral"
        if subtype == "time_passed":
            value = 0.0
            reasoning.append("Time passage - no control")
        elif subtype in ["betrayal", "rejection"]:
            value = 0.2
            reasoning.append("External negative event - low control")
        elif subtype == "care":
            value = 0.3
            reasoning.append("External care - some control over response")
    
    # Event text analysis
    if event.text:
        text_lower = event.text.lower()
        
        # Controllable actions
        if any(w in text_lower for w in ["可以", "能够", "我会"]):
            value = max(value, 0.6)
            reasoning.append("Controllable action indicated")
        
        # Uncontrollable situations
        elif any(w in text_lower for w in ["必须", "不得不", "无法"]):
            value = min(value, 0.3)
            reasoning.append("Uncontrollable constraint indicated")
    
    if not reasoning:
        reasoning.append(f"Base controllability: {base_value:.2f}")
    
    # Clamp to [0, 1]
    value = max(0.0, min(1.0, value))
    
    return value, reasoning[0]


def compute_social_threat(
    event: Event,
    context: AppraisalContext,
    base_value: float = 0.0
) -> Tuple[float, str]:
    """
    Compute social_threat dimension.
    
    Higher = more threat to social relationships.
    
    Contextual factors:
    - Rejection/betrayal → high threat
    - Cold treatment duration → increasing threat
    - Relationship strength → moderates threat
    """
    reasoning = []
    value = base_value
    
    # Check cold treatment duration
    if context.cold_treatment_duration > 0:
        # Threat increases with duration
        threat_from_duration = min(0.8, context.cold_treatment_duration / 7200)  # Max at 2 hours
        value = max(value, threat_from_duration)
        reasoning.append(f"Cold treatment duration: {context.cold_treatment_duration/60:.0f}min")
    
    # Event text analysis
    if event.text:
        text_lower = event.text.lower()
        
        # High threat signals
        if any(w in text_lower for w in ["讨厌", "恨", "不再", "结束", "分手", "离开"]):
            value = max(value, 0.8)
            reasoning.append("High threat language")
        elif "算了" in text_lower:
            # Dismissive language
            if context.cold_treatment_duration > 1800:  # 30 min
                value = max(value, 0.6)
                reasoning.append("Dismissive after cold treatment")
            else:
                value = max(value, 0.3)
                reasoning.append("Dismissive language")
        
        # Moderate threat
        elif any(w in text_lower for w in ["算了", "不用", "别", "不要"]):
            value = max(value, 0.3)
            reasoning.append("Rejection language")
    
    # Relationship context moderates threat
    if context.bond:
        bond = context.bond.get("bond", 0)
        grudge = context.bond.get("grudge", 0)
        
        # High bond → threat feels more significant
        if bond > 0.6:
            value = min(1.0, value * 1.2)
            reasoning.append("High bond amplifies threat")
        
        # Existing grudge → threat confirms pattern
        if grudge > 0.5:
            value = max(value, 0.4)
            reasoning.append("Existing grudge reinforces threat")
    
    if not reasoning:
        reasoning.append(f"Base social_threat: {base_value:.2f}")
    
    # Clamp to [0, 1]
    value = max(0.0, min(1.0, value))
    
    return value, reasoning[0]


def compute_novelty(
    event: Event,
    context: AppraisalContext,
    base_value: float = 0.0
) -> Tuple[float, str]:
    """
    Compute novelty dimension.
    
    Higher = more new/surprising/informative.
    
    Contextual factors:
    - First time occurrence → higher novelty
    - Repetitive pattern → lower novelty
    - Prediction error → correlates with novelty
    """
    reasoning = []
    value = base_value
    
    # Check event history for repetition
    if context.event_history:
        recent_types = [e.get("subtype") for e in context.event_history[-10:]]
        subtype = event.meta.get("subtype", "neutral") if event.meta else "neutral"
        
        if recent_types.count(subtype) > 3:
            # Repetitive pattern
            value = min(value, 0.1)
            reasoning.append("Repetitive pattern detected")
        elif subtype not in recent_types[-5:]:
            # Novel event type
            value = max(value, 0.5)
            reasoning.append("Novel event type")
    
    # Event text analysis for surprise/novelty
    if event.text:
        text_lower = event.text.lower()
        
        # Novelty indicators
        if any(w in text_lower for w in ["突然", "意外", "没想到", "惊喜"]):
            value = max(value, 0.7)
            reasoning.append("Explicit novelty/surprise")
        elif any(w in text_lower for w in ["第一次", "新", "从未"]):
            value = max(value, 0.6)
            reasoning.append("First-time/new indication")
        
        # Repetition indicators
        elif any(w in text_lower for w in ["又是", "总是", "每次", "老是这样"]):
            value = min(value, 0.2)
            reasoning.append("Repetitive pattern language")
    
    # Affect state affects novelty perception
    if context.affect:
        arousal = context.affect.get("arousal", 0.3)
        # High arousal can amplify novelty perception
        if arousal > 0.6:
            value = min(1.0, value * 1.1)
    
    if not reasoning:
        reasoning.append(f"Base novelty: {base_value:.2f}")
    
    # Clamp to [0, 1]
    value = max(0.0, min(1.0, value))
    
    return value, reasoning[0]


def compute_observed_delta(
    event: Event,
    context: AppraisalContext
) -> Dict[str, float]:
    """
    Compute observed changes in interoceptive states.
    
    Used for learning predictions about actions.
    
    Returns:
        Dict with 'safety' and 'energy' keys
    """
    from emotiond.config import get_observed_delta as get_delta_from_config
    
    # Get base delta from event subtype
    subtype = event.meta.get("subtype", "neutral") if event.meta else "neutral"
    delta = get_delta_from_config(subtype)
    
    # Modify based on context
    if context.affect:
        current_safety = context.affect.get("social_safety", 0.6)
        current_energy = context.affect.get("energy", 0.7)
        
        # Diminishing returns for already high values
        if current_safety > 0.8 and delta["safety"] > 0:
            delta["safety"] *= 0.5
        if current_energy < 0.3 and delta["energy"] < 0:
            delta["energy"] *= 1.5  # More draining when tired
    
    return delta


def appraise_event(
    event: Event,
    context: Optional[AppraisalContext] = None,
    affect: Optional[AffectState] = None,
    mood: Optional[MoodState] = None,
    bond: Optional[BondState] = None,
    target: Optional[str] = None
) -> AppraisalResult:
    """
    Main appraisal function.
    
    Transforms an event into a structured appraisal result.
    
    Args:
        event: The event to appraise
        context: Optional full context (if provided, other params ignored)
        affect: Current affect state
        mood: Current mood state
        bond: Current relationship state with event target
    
    Returns:
        AppraisalResult with dimensions, emotion label, and reasoning
    """
    # Build context if not provided
    if context is None:
        # Convert bond to dict, excluding the 'target' field
        bond_dict = None
        if bond:
            bond_dict = {
                "bond": bond.bond,
                "trust": bond.trust,
                "grudge": bond.grudge,
                "repair_bank": bond.repair_bank,
                "uncertainty": getattr(bond, 'uncertainty', 0.5)
            }
        
        context = AppraisalContext(
            affect=affect.to_dict() if affect else None,
            mood=mood.to_dict() if mood else None,
            bond=bond_dict,
            target=(target or (bond.target if bond else None))
        )
    
    # Get base signature from event subtype
    subtype = event.meta.get("subtype", "neutral") if event.meta else "neutral"
    base_signature = EVENT_APPRAISAL_SIGNATURES.get(subtype, EVENT_APPRAISAL_SIGNATURES["neutral"])
    
    # Compute each dimension
    goal_progress, gp_reason = compute_goal_progress(event, context, base_signature["goal_progress"])
    expectation_violation, ev_reason = compute_expectation_violation(event, context, base_signature["expectation_violation"])
    controllability, ct_reason = compute_controllability(event, context, base_signature["controllability"])
    social_threat, st_reason = compute_social_threat(event, context, base_signature["social_threat"])
    novelty, nv_reason = compute_novelty(event, context, base_signature["novelty"])
    
    # Compute observed delta for learning
    observed_delta = compute_observed_delta(event, context)
    
    # Build reasoning list
    reasoning = [
        f"goal_progress: {gp_reason}",
        f"expectation_violation: {ev_reason}",
        f"controllability: {ct_reason}",
        f"social_threat: {st_reason}",
        f"novelty: {nv_reason}",
    ]
    
    # Map to emotion (will be done in emotion_labels.py, but we provide defaults)
    from emotiond.emotion_labels import map_to_emotion
    emotion_label, intensity = map_to_emotion(
        goal_progress=goal_progress,
        expectation_violation=expectation_violation,
        controllability=controllability,
        social_threat=social_threat,
        novelty=novelty,
        affect=affect,
        mood=mood
    )
    
    return AppraisalResult(
        goal_progress=goal_progress,
        expectation_violation=expectation_violation,
        controllability=controllability,
        social_threat=social_threat,
        novelty=novelty,
        observed_delta=observed_delta,
        emotion_label=emotion_label,
        intensity=intensity,
        reasoning=reasoning
    )


def create_context_from_state(
    affect: Optional[AffectState] = None,
    mood: Optional[MoodState] = None,
    bond: Optional[BondState] = None,
    event_history: Optional[List[Dict[str, Any]]] = None,
    promise_state: Optional[Dict[str, Any]] = None,
    cold_treatment_duration: float = 0.0,
    target: Optional[str] = None
) -> AppraisalContext:
    """
    Helper to create an AppraisalContext from state components.
    
    Args:
        affect: Current affect state
        mood: Current mood state
        bond: Current relationship state
        event_history: Recent event history
        promise_state: Current promise state
        cold_treatment_duration: Duration of cold treatment in seconds
    
    Returns:
        AppraisalContext ready for appraisal
    """
    bond_dict = None
    if bond:
        bond_dict = {
            "bond": bond.bond,
            "trust": bond.trust,
            "grudge": bond.grudge,
            "repair_bank": bond.repair_bank,
            "uncertainty": bond.uncertainty
        }
    
    return AppraisalContext(
        affect=affect.to_dict() if affect else None,
        mood=mood.to_dict() if mood else None,
        bond=bond_dict,
        event_history=event_history,
        promise_state=promise_state,
        cold_treatment_duration=cold_treatment_duration,
        target=target
    )


# MVP-8: emotional reasoning intermediate representation
from dataclasses import dataclass


@dataclass
class EmotionalReasoning:
    primary_emotion: str
    emotion_intensity: float
    interpretation: str
    predicted_risk: float
    action_tendency: str
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_emotion": self.primary_emotion,
            "emotion_intensity": self.emotion_intensity,
            "interpretation": self.interpretation,
            "predicted_risk": self.predicted_risk,
            "action_tendency": self.action_tendency,
            "confidence": self.confidence,
        }


def compute_emotional_reasoning(
    event: Event,
    appraisal: Any,
    prediction_error: float,
    social_safety: float,
    regulation_budget: float,
) -> EmotionalReasoning:
    """Derive emotion-as-intermediate-variable for interpretation/prediction/decision."""
    if isinstance(appraisal, dict):
        threat = float(appraisal.get("social_threat", 0.0))
        goal = float(appraisal.get("goal_progress", 0.0))
        intensity = float(appraisal.get("intensity", 0.0))
    else:
        threat = float(getattr(appraisal, "social_threat", 0.0))
        goal = float(getattr(appraisal, "goal_progress", 0.0))
        intensity = float(getattr(appraisal, "intensity", 0.0))

    if threat > 0.7:
        emotion, tendency = "fear", "protect"
    elif goal < -0.4:
        emotion, tendency = "sadness", "withdraw"
    elif goal > 0.35 and threat < 0.35:
        emotion, tendency = "trust", "approach"
    elif prediction_error > 0.35:
        emotion, tendency = "confusion", "clarify"
    else:
        emotion, tendency = "caution", "observe"

    predicted_risk = max(0.0, min(1.0, 0.5 * threat + 0.3 * prediction_error + 0.2 * (1.0 - social_safety)))
    confidence = max(0.0, min(1.0, 1.0 - abs(prediction_error - intensity)))
    interpretation = f"event={event.type}, goal={goal:.2f}, threat={threat:.2f}, budget={regulation_budget:.2f}"

    return EmotionalReasoning(
        primary_emotion=emotion,
        emotion_intensity=intensity,
        interpretation=interpretation,
        predicted_risk=predicted_risk,
        action_tendency=tendency,
        confidence=confidence,
    )
