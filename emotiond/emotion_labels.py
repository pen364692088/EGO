"""
MVP-4 D3: Discrete Emotion Mapping

Maps appraisal dimensions to discrete emotion labels using rule-based logic.
Not a classifier - uses threshold-based rules grounded in appraisal theory.

Emotions:
- joy: Goal progress, positive valence
- sadness: Goal blocked, low controllability
- fear: Social threat, uncertainty
- anger: Expectation violation, controllable
- curiosity: Novelty, low social threat
- confusion: Uncertainty, prediction error
- boredom: Low novelty, no prediction error
"""
from typing import Dict, Tuple, Optional, List
from emotiond.state import AffectState, MoodState


# Emotion mapping rules - each emotion has dimension thresholds
# Format: {dimension: (min_threshold, max_threshold)}
EMOTION_RULES: Dict[str, Dict[str, Tuple[float, float]]] = {
    "joy": {
        "goal_progress": (0.25, 1.0),  # Goal progress toward goals
    },
    "sadness": {
        "goal_progress": (-1.0, -0.3),
        "controllability": (0.0, 0.5),
    },
    "fear": {
        "social_threat": (0.5, 1.0),
        "uncertainty": (0.5, 1.0),
    },
    "anger": {
        "expectation_violation": (0.5, 1.0),
        "controllability": (0.5, 1.0),
    },
    "curiosity": {
        "novelty": (0.5, 1.0),
        "social_threat": (0.0, 0.3),
    },
    "confusion": {
        "uncertainty": (0.6, 1.0),
        "prediction_error": (0.3, 1.0),
    },
    "boredom": {
        "novelty": (0.0, 0.15),  # Very low novelty only
    },
}

# Priority order for emotion matching (when multiple rules match)
EMOTION_PRIORITY = [
    "anger",    # Strong negative, high priority
    "fear",     # Safety-critical
    "joy",      # Strong positive
    "sadness",  # Low agency negative
    "curiosity", # Positive engagement
    "confusion", # Uncertain state
    "boredom",  # Low arousal state - lowest priority
]

# Intensity multipliers based on how far into the threshold range
INTENSITY_SCALES = {
    "joy": 1.0,
    "sadness": 0.9,
    "fear": 1.1,  # Fear tends to be intense
    "anger": 1.2,  # Anger tends to be intense
    "curiosity": 0.7,
    "confusion": 0.6,
    "boredom": 0.4,
}

# Mood sustainability factors
# How much mood affects each emotion
MOOD_INFLUENCE = {
    "joy": 0.3,
    "sadness": 0.4,
    "fear": 0.2,
    "anger": 0.3,
    "curiosity": 0.2,  # Curiosity is more state-dependent
    "confusion": 0.1,
    "boredom": 0.3,
}


def check_rule_match(
    dimension_values: Dict[str, float],
    rule: Dict[str, Tuple[float, float]]
) -> Tuple[bool, float]:
    """
    Check if dimension values match a rule.
    
    Args:
        dimension_values: Dict of dimension name -> value
        rule: Dict of dimension -> (min, max) thresholds
    
    Returns:
        Tuple of (matches, match_strength)
        - matches: True if all dimensions in rule are satisfied
        - match_strength: How strongly the rule matches (0-1)
    """
    matches = True
    total_strength = 0.0
    num_dimensions = 0
    
    for dim, (min_val, max_val) in rule.items():
        value = dimension_values.get(dim, 0.0)
        
        if min_val <= value <= max_val:
            # Calculate strength: how centered in the threshold range
            range_size = max_val - min_val
            if range_size > 0:
                # Strength is higher when more centered in the range
                center = (min_val + max_val) / 2
                dist_from_center = abs(value - center)
                strength = 1.0 - (dist_from_center / (range_size / 2))
                strength = min(1.0, max(0.5, strength))  # Min 0.5 if matched
            else:
                strength = 1.0 if value == min_val else 0.0
            
            total_strength += strength
            num_dimensions += 1
        else:
            matches = False
            break
    
    avg_strength = total_strength / num_dimensions if num_dimensions > 0 else 0.0
    
    return matches, avg_strength


def map_to_emotion(
    goal_progress: float = 0.0,
    expectation_violation: float = 0.0,
    controllability: float = 0.5,
    social_threat: float = 0.0,
    novelty: float = 0.0,
    uncertainty: float = 0.5,
    prediction_error: float = 0.0,
    valence: float = 0.0,
    affect: Optional[AffectState] = None,
    mood: Optional[MoodState] = None
) -> Tuple[str, float]:
    """
    Map appraisal dimensions to a discrete emotion label and intensity.
    
    Args:
        goal_progress: [-1, 1] goal progress
        expectation_violation: [0, 1] expectation violation
        controllability: [0, 1] control over situation
        social_threat: [0, 1] social threat level
        novelty: [0, 1] novelty of situation
        uncertainty: [0, 1] uncertainty level (default from affect or 0.5)
        prediction_error: [0, 1] prediction error magnitude
        valence: [-1, 1] valence (default from affect or 0.0)
        affect: Optional affect state for context
        mood: Optional mood state for sustainability
    
    Returns:
        Tuple of (emotion_label, intensity)
    """
    # Get values from affect if provided
    if affect is not None:
        valence = valence if valence != 0.0 else affect.valence
        uncertainty = uncertainty if uncertainty != 0.5 else affect.uncertainty
        prediction_error = prediction_error if prediction_error != 0.0 else getattr(affect, 'prediction_error', 0.0)
    
    # Build dimension values dict
    dimension_values = {
        "goal_progress": goal_progress,
        "expectation_violation": expectation_violation,
        "controllability": controllability,
        "social_threat": social_threat,
        "novelty": novelty,
        "uncertainty": uncertainty,
        "prediction_error": prediction_error,
        "valence": valence,
    }
    
    # Find all matching emotions
    matches: List[Tuple[str, float, float]] = []  # (emotion, strength, priority_weight)
    
    for emotion in EMOTION_PRIORITY:
        rule = EMOTION_RULES[emotion]
        is_match, strength = check_rule_match(dimension_values, rule)
        
        if is_match:
            # Priority weight: earlier in list = higher weight
            priority_weight = (len(EMOTION_PRIORITY) - EMOTION_PRIORITY.index(emotion)) / len(EMOTION_PRIORITY)
            matches.append((emotion, strength, priority_weight))
    
    # Select best match
    if not matches:
        # Default to neutral with low intensity
        return "neutral", 0.1
    
    # Sort by priority weight, then by strength
    matches.sort(key=lambda x: (x[2], x[1]), reverse=True)
    
    best_emotion, best_strength, _ = matches[0]
    
    # Calculate intensity
    base_intensity = best_strength * INTENSITY_SCALES.get(best_emotion, 1.0)
    
    # Apply mood influence
    mood_factor = 0.0
    if mood is not None:
        mood_influence = MOOD_INFLUENCE.get(best_emotion, 0.0)
        
        # Get relevant mood dimension
        if best_emotion == "joy":
            mood_factor = mood.joy * mood_influence
        elif best_emotion == "sadness":
            mood_factor = mood.sadness * mood_influence
        elif best_emotion == "anger":
            mood_factor = mood.anger * mood_influence
        elif best_emotion == "fear":
            mood_factor = mood.anxiety * mood_influence
        elif best_emotion == "curiosity":
            mood_factor = mood.arousal * mood_influence * 0.3  # Arousal contributes to curiosity
        elif best_emotion == "boredom":
            mood_factor = (1 - mood.arousal) * mood_influence  # Low arousal → boredom
    
    # Combine base intensity with mood factor
    intensity = base_intensity * (1 + mood_factor)
    intensity = max(0.0, min(1.0, intensity))  # Clamp to [0, 1]
    
    return best_emotion, intensity


def get_emotion_explanation(
    emotion: str,
    goal_progress: float,
    expectation_violation: float,
    controllability: float,
    social_threat: float,
    novelty: float
) -> str:
    """
    Generate a human-readable explanation for why this emotion was selected.
    
    Args:
        emotion: The selected emotion
        Other args: Appraisal dimension values
    
    Returns:
        Explanation string
    """
    explanations = {
        "joy": f"Positive goal progress ({goal_progress:.2f}) with good controllability ({controllability:.2f})",
        "sadness": f"Goal blocked ({goal_progress:.2f}) with low controllability ({controllability:.2f}) - feeling helpless",
        "fear": f"High social threat ({social_threat:.2f}) detected - safety concern",
        "anger": f"Expectation violated ({expectation_violation:.2f}) with potential for action (controllability: {controllability:.2f})",
        "curiosity": f"Novel situation ({novelty:.2f}) with low threat ({social_threat:.2f}) - engaging",
        "confusion": f"High uncertainty and prediction error - trying to understand",
        "boredom": f"Low novelty ({novelty:.2f}) with no prediction error - disengaged",
        "neutral": "No strong emotional signal detected",
    }
    
    return explanations.get(emotion, "Unknown emotion")


def get_emotion_blend(
    goal_progress: float = 0.0,
    expectation_violation: float = 0.0,
    controllability: float = 0.5,
    social_threat: float = 0.0,
    novelty: float = 0.0,
    uncertainty: float = 0.5,
    prediction_error: float = 0.0,
    valence: float = 0.0,
    affect: Optional[AffectState] = None,
    mood: Optional[MoodState] = None,
    threshold: float = 0.3
) -> Dict[str, float]:
    """
    Get a blend of emotions with their intensities.
    
    Unlike map_to_emotion which returns the primary emotion,
    this returns all emotions above a threshold.
    
    Args:
        Same as map_to_emotion
        threshold: Minimum intensity to include in blend
    
    Returns:
        Dict of emotion -> intensity for all emotions above threshold
    """
    # Get values from affect if provided
    if affect is not None:
        valence = valence if valence != 0.0 else affect.valence
        uncertainty = uncertainty if uncertainty != 0.5 else affect.uncertainty
        prediction_error = prediction_error if prediction_error != 0.0 else getattr(affect, 'prediction_error', 0.0)
    
    # Build dimension values dict
    dimension_values = {
        "goal_progress": goal_progress,
        "expectation_violation": expectation_violation,
        "controllability": controllability,
        "social_threat": social_threat,
        "novelty": novelty,
        "uncertainty": uncertainty,
        "prediction_error": prediction_error,
        "valence": valence,
    }
    
    blend: Dict[str, float] = {}
    
    for emotion in EMOTION_PRIORITY:
        rule = EMOTION_RULES[emotion]
        is_match, strength = check_rule_match(dimension_values, rule)
        
        if is_match:
            intensity = strength * INTENSITY_SCALES.get(emotion, 1.0)
            
            if intensity >= threshold:
                blend[emotion] = intensity
    
    # Sort by intensity descending
    blend = dict(sorted(blend.items(), key=lambda x: x[1], reverse=True))
    
    return blend


def is_sustainable_emotion(emotion: str, mood: Optional[MoodState] = None) -> bool:
    """
    Check if an emotion is sustainable given current mood state.
    
    Sustainability refers to whether the emotion can persist over time.
    
    Args:
        emotion: The emotion to check
        mood: Current mood state
    
    Returns:
        True if the emotion is sustainable
    """
    # Curiosity, confusion, and boredom are sustainability emotions
    # They can persist over time without requiring specific events
    sustainable_emotions = {"curiosity", "confusion", "boredom"}
    
    if emotion in sustainable_emotions:
        return True
    
    # Other emotions require specific appraisal conditions
    # They are not sustainable without ongoing events
    return False


def get_emotion_action_tendency(emotion: str) -> str:
    """
    Get the action tendency associated with an emotion.
    
    Based on appraisal theory, each emotion has a characteristic
    behavioral tendency.
    
    Args:
        emotion: The emotion label
    
    Returns:
        Action tendency description
    """
    tendencies = {
        "joy": "approach, share, savor",
        "sadness": "withdraw, seek comfort, conserve energy",
        "fear": "escape, avoid, seek safety",
        "anger": "confront, assert, change situation",
        "curiosity": "explore, investigate, learn",
        "confusion": "seek clarification, re-evaluate, pause",
        "boredom": "disengage, seek stimulation, change activity",
        "neutral": "observe, maintain",
    }
    
    return tendencies.get(emotion, "unknown")
