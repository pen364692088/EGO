"""
MVP-6 D2: Consequence Model

Consequence event processor that maps tool_result/env_outcome/interaction_outcome
events into body deltas, tags, and trace consequence_delta.

Ensures feedback wiring into:
- Allostasis (body state regulation)
- Precision (prediction error weighting)
- Intrinsic (internal value signals)
- Meta-cognition decisions

Key features:
- Structured consequence mapping
- Risk-aware escalation control
- Boundary stability enforcement
- Trace tagging for auditability
"""
import time
import math
from typing import Dict, Any, Optional, List, Tuple, Set
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
from enum import Enum


class ConsequenceType(str, Enum):
    """Types of consequence events."""
    TOOL_RESULT = "tool_result"
    ENV_OUTCOME = "env_outcome"
    INTERACTION_OUTCOME = "interaction_outcome"


class OutcomeStatus(str, Enum):
    """Status of an outcome."""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    ERROR = "error"
    UNEXPECTED = "unexpected"


class RiskLevel(str, Enum):
    """Risk levels for consequences."""
    NONE = "none"          # No risk
    LOW = "low"            # Minimal impact
    MEDIUM = "medium"      # Moderate impact
    HIGH = "high"          # Significant impact
    CRITICAL = "critical"  # Severe impact


class ConsequenceTag(str, Enum):
    """Tags for consequence classification and traceability."""
    # Source tags
    FROM_TOOL = "from_tool"
    FROM_ENV = "from_env"
    FROM_INTERACTION = "from_interaction"

    # Outcome tags
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    ERROR = "error"

    # Risk tags
    RISK_NONE = "risk_none"
    RISK_LOW = "risk_low"
    RISK_MEDIUM = "risk_medium"
    RISK_HIGH = "risk_high"
    RISK_CRITICAL = "risk_critical"

    # Feedback wiring tags
    ALLOSTASIS = "allostasis"
    PRECISION = "precision"
    INTRINSIC = "intrinsic"
    META_COGNITION = "meta_cognition"

    # Control tags
    CONTROLLED = "controlled"
    UNCONTROLLED = "uncontrolled"
    BOUNDARY_HIT = "boundary_hit"
    BOUNDARY_SAFE = "boundary_safe"

    # Escalation prevention
    ESCALATION_CHECKED = "escalation_checked"
    LOW_SIGNAL_HIGH_RISK = "low_signal_high_risk"  # Flag for mismatched escalation


class BodyDelta(BaseModel):
    """
    Delta changes to body/interoceptive state.

    Represents how a consequence affects the agent's internal state.
    """
    safety: float = Field(default=0.0, ge=-1.0, le=1.0, description="Change in social safety")
    energy: float = Field(default=0.0, ge=-1.0, le=1.0, description="Change in energy level")
    arousal: float = Field(default=0.0, ge=-1.0, le=1.0, description="Change in arousal")
    valence: float = Field(default=0.0, ge=-1.0, le=1.0, description="Change in valence")
    uncertainty: float = Field(default=0.0, ge=-1.0, le=1.0, description="Change in uncertainty")

    def magnitude(self) -> float:
        """Calculate the magnitude of the delta."""
        return math.sqrt(
            self.safety ** 2 +
            self.energy ** 2 +
            self.arousal ** 2 +
            self.valence ** 2 +
            self.uncertainty ** 2
        ) / math.sqrt(5)  # Normalize to [0, 1]

    def is_significant(self, threshold: float = 0.1) -> bool:
        """Check if the delta is significant."""
        return abs(self.safety) > threshold or \
               abs(self.energy) > threshold or \
               abs(self.arousal) > threshold or \
               abs(self.valence) > threshold or \
               abs(self.uncertainty) > threshold

    def clamp(self, min_val: float = -1.0, max_val: float = 1.0) -> "BodyDelta":
        """Clamp all values to valid range."""
        return BodyDelta(
            safety=max(min_val, min(max_val, self.safety)),
            energy=max(min_val, min(max_val, self.energy)),
            arousal=max(min_val, min(max_val, self.arousal)),
            valence=max(min_val, min(max_val, self.valence)),
            uncertainty=max(min_val, min(max_val, self.uncertainty))
        )


class ConsequenceDelta(BaseModel):
    """
    Complete consequence delta with body changes, tags, and metadata.

    This is the primary output of the consequence processor.
    """
    consequence_type: ConsequenceType = Field(..., description="Type of consequence")
    outcome_status: OutcomeStatus = Field(..., description="Status of the outcome")
    risk_level: RiskLevel = Field(default=RiskLevel.NONE, description="Assessed risk level")
    body_delta: BodyDelta = Field(default_factory=BodyDelta, description="Body state changes")
    tags: List[str] = Field(default_factory=list, description="Classification tags")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence in assessment")
    timestamp: float = Field(default_factory=time.time, description="When processed")
    source: str = Field(default="", description="Source of the consequence (tool name, etc.)")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")

    # Feedback wiring flags
    feeds_allostasis: bool = Field(default=False, description="Whether this feeds allostasis")
    feeds_precision: bool = Field(default=False, description="Whether this feeds precision")
    feeds_intrinsic: bool = Field(default=False, description="Whether this feeds intrinsic signals")
    feeds_meta_cognition: bool = Field(default=False, description="Whether this feeds meta-cognition")

    # Trace information
    trace_id: str = Field(default="", description="Trace identifier for auditability")
    parent_trace_id: Optional[str] = Field(default=None, description="Parent trace if applicable")

    def add_tag(self, tag: str) -> "ConsequenceDelta":
        """Add a tag if not already present."""
        if tag not in self.tags:
            self.tags.append(tag)
        return self

    def has_tag(self, tag: str) -> bool:
        """Check if delta has a specific tag."""
        return tag in self.tags

    def get_risk_score(self) -> float:
        """Convert risk level to numeric score [0, 1]."""
        risk_scores = {
            RiskLevel.NONE: 0.0,
            RiskLevel.LOW: 0.25,
            RiskLevel.MEDIUM: 0.5,
            RiskLevel.HIGH: 0.75,
            RiskLevel.CRITICAL: 1.0
        }
        return risk_scores.get(self.risk_level, 0.5)


class AllostasisFeedback(BaseModel):
    """
    Feedback for allostasis (body state regulation).

    Provides signals for maintaining homeostasis.
    """
    safety_target: float = Field(default=0.6, ge=0.0, le=1.0, description="Target safety level")
    energy_target: float = Field(default=0.7, ge=0.0, le=1.0, description="Target energy level")
    regulation_priority: float = Field(default=0.5, ge=0.0, le=1.0, description="Priority of regulation")
    urgent: bool = Field(default=False, description="Whether regulation is urgent")
    reason: str = Field(default="", description="Reason for regulation")


class PrecisionFeedback(BaseModel):
    """
    Feedback for precision (prediction error weighting).

    Adjusts how much to trust predictions vs. observations.
    """
    precision_weight: float = Field(default=0.5, ge=0.0, le=1.0, description="Weight for predictions")
    prediction_error: float = Field(default=0.0, ge=0.0, description="Observed prediction error")
    update_rate: float = Field(default=0.1, ge=0.0, le=1.0, description="Rate of model update")
    reason: str = Field(default="", description="Reason for precision adjustment")


class IntrinsicFeedback(BaseModel):
    """
    Feedback for intrinsic value signals.

    Provides internal value-based guidance.
    """
    value_signal: float = Field(default=0.0, ge=-1.0, le=1.0, description="Intrinsic value signal")
    value_type: str = Field(default="", description="Type of value (safety, growth, etc.)")
    intensity: float = Field(default=0.5, ge=0.0, le=1.0, description="Intensity of signal")
    reason: str = Field(default="", description="Reason for intrinsic signal")


class MetaCognitionFeedback(BaseModel):
    """
    Feedback for meta-cognition decisions.

    Guides reflection, clarification, and learning.
    """
    suggest_reflect: bool = Field(default=False, description="Suggest reflection")
    suggest_clarify: bool = Field(default=False, description="Suggest clarification")
    suggest_learn: bool = Field(default=False, description="Suggest learning")
    confidence_adjustment: float = Field(default=0.0, ge=-1.0, le=1.0, description="Confidence adjustment")
    reason: str = Field(default="", description="Reason for meta-cognitive suggestion")


class FeedbackBundle(BaseModel):
    """
    Complete feedback bundle for all subsystems.

    Aggregates feedback for allostasis, precision, intrinsic, and meta-cognition.
    """
    allostasis: Optional[AllostasisFeedback] = None
    precision: Optional[PrecisionFeedback] = None
    intrinsic: Optional[IntrinsicFeedback] = None
    meta_cognition: Optional[MetaCognitionFeedback] = None
    consequence_delta: ConsequenceDelta = Field(..., description="Source consequence delta")


class ConsequenceProcessorConfig(BaseModel):
    """Configuration for the consequence processor."""
    # Risk escalation prevention
    max_risk_from_low_signal: RiskLevel = Field(
        default=RiskLevel.MEDIUM,
        description="Maximum risk level from low-risk signals"
    )
    low_signal_threshold: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Threshold for considering a signal low-risk"
    )

    # Boundary stability
    boundary_stability_threshold: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Threshold for boundary stability check"
    )

    # Feedback thresholds
    allostasis_trigger_threshold: float = Field(default=0.15)
    precision_trigger_threshold: float = Field(default=0.2)
    intrinsic_trigger_threshold: float = Field(default=0.1)
    meta_cognition_trigger_threshold: float = Field(default=0.25)

    # Confidence decay
    confidence_decay_rate: float = Field(default=0.95, ge=0.0, le=1.0)


# Default consequence mappings
TOOL_RESULT_MAPPINGS = {
    # Successful tool execution
    (OutcomeStatus.SUCCESS, "low"): BodyDelta(
        safety=0.02, energy=-0.01, arousal=-0.05, valence=0.05, uncertainty=-0.05
    ),
    (OutcomeStatus.SUCCESS, "medium"): BodyDelta(
        safety=0.05, energy=-0.02, arousal=-0.03, valence=0.08, uncertainty=-0.08
    ),
    (OutcomeStatus.SUCCESS, "high"): BodyDelta(
        safety=0.08, energy=-0.03, arousal=0.0, valence=0.12, uncertainty=-0.1
    ),

    # Failed tool execution
    (OutcomeStatus.FAILURE, "low"): BodyDelta(
        safety=-0.03, energy=-0.02, arousal=0.05, valence=-0.05, uncertainty=0.05
    ),
    (OutcomeStatus.FAILURE, "medium"): BodyDelta(
        safety=-0.08, energy=-0.05, arousal=0.1, valence=-0.1, uncertainty=0.1
    ),
    (OutcomeStatus.FAILURE, "high"): BodyDelta(
        safety=-0.15, energy=-0.08, arousal=0.15, valence=-0.18, uncertainty=0.15
    ),

    # Partial success
    (OutcomeStatus.PARTIAL, "low"): BodyDelta(
        safety=0.0, energy=-0.02, arousal=0.02, valence=0.0, uncertainty=0.08
    ),
    (OutcomeStatus.PARTIAL, "medium"): BodyDelta(
        safety=-0.02, energy=-0.03, arousal=0.05, valence=-0.03, uncertainty=0.12
    ),

    # Timeout
    (OutcomeStatus.TIMEOUT, "low"): BodyDelta(
        safety=-0.02, energy=-0.03, arousal=0.08, valence=-0.03, uncertainty=0.1
    ),
    (OutcomeStatus.TIMEOUT, "medium"): BodyDelta(
        safety=-0.05, energy=-0.05, arousal=0.12, valence=-0.06, uncertainty=0.15
    ),

    # Error
    (OutcomeStatus.ERROR, "low"): BodyDelta(
        safety=-0.05, energy=-0.03, arousal=0.1, valence=-0.08, uncertainty=0.12
    ),
    (OutcomeStatus.ERROR, "medium"): BodyDelta(
        safety=-0.1, energy=-0.05, arousal=0.15, valence=-0.12, uncertainty=0.18
    ),
}

ENV_OUTCOME_MAPPINGS = {
    # Environmental outcomes are less controllable
    (OutcomeStatus.SUCCESS, "low"): BodyDelta(
        safety=0.01, energy=0.0, arousal=-0.02, valence=0.03, uncertainty=-0.02
    ),
    (OutcomeStatus.SUCCESS, "medium"): BodyDelta(
        safety=0.03, energy=0.01, arousal=0.0, valence=0.06, uncertainty=-0.05
    ),

    (OutcomeStatus.FAILURE, "low"): BodyDelta(
        safety=-0.02, energy=-0.01, arousal=0.03, valence=-0.03, uncertainty=0.03
    ),
    (OutcomeStatus.FAILURE, "medium"): BodyDelta(
        safety=-0.06, energy=-0.03, arousal=0.08, valence=-0.08, uncertainty=0.08
    ),
    (OutcomeStatus.FAILURE, "high"): BodyDelta(
        safety=-0.12, energy=-0.06, arousal=0.12, valence=-0.15, uncertainty=0.12
    ),

    # Unexpected environmental outcomes
    (OutcomeStatus.UNEXPECTED, "low"): BodyDelta(
        safety=-0.01, energy=0.0, arousal=0.05, valence=-0.01, uncertainty=0.08
    ),
    (OutcomeStatus.UNEXPECTED, "medium"): BodyDelta(
        safety=-0.03, energy=-0.01, arousal=0.1, valence=-0.03, uncertainty=0.15
    ),
}

INTERACTION_OUTCOME_MAPPINGS = {
    # Interaction outcomes affect social safety more
    (OutcomeStatus.SUCCESS, "low"): BodyDelta(
        safety=0.03, energy=0.01, arousal=-0.03, valence=0.06, uncertainty=-0.04
    ),
    (OutcomeStatus.SUCCESS, "medium"): BodyDelta(
        safety=0.08, energy=0.02, arousal=0.0, valence=0.12, uncertainty=-0.08
    ),

    (OutcomeStatus.FAILURE, "low"): BodyDelta(
        safety=-0.05, energy=-0.02, arousal=0.05, valence=-0.06, uncertainty=0.06
    ),
    (OutcomeStatus.FAILURE, "medium"): BodyDelta(
        safety=-0.12, energy=-0.05, arousal=0.1, valence=-0.12, uncertainty=0.12
    ),
    (OutcomeStatus.FAILURE, "high"): BodyDelta(
        safety=-0.2, energy=-0.08, arousal=0.15, valence=-0.2, uncertainty=0.18
    ),

    # Partial success in interaction
    (OutcomeStatus.PARTIAL, "low"): BodyDelta(
        safety=0.0, energy=-0.01, arousal=0.01, valence=0.01, uncertainty=0.05
    ),
}


def get_mapping_key(status: OutcomeStatus, impact_level: str) -> Tuple[OutcomeStatus, str]:
    """Create a mapping key from status and impact level."""
    return (status, impact_level)


def lookup_body_delta(
    consequence_type: ConsequenceType,
    status: OutcomeStatus,
    impact_level: str
) -> Optional[BodyDelta]:
    """
    Look up body delta for a consequence type, status, and impact.

    Args:
        consequence_type: Type of consequence
        status: Outcome status
        impact_level: Impact level (low, medium, high)

    Returns:
        BodyDelta if found, None otherwise
    """
    key = get_mapping_key(status, impact_level)

    if consequence_type == ConsequenceType.TOOL_RESULT:
        return TOOL_RESULT_MAPPINGS.get(key)
    elif consequence_type == ConsequenceType.ENV_OUTCOME:
        return ENV_OUTCOME_MAPPINGS.get(key)
    elif consequence_type == ConsequenceType.INTERACTION_OUTCOME:
        return INTERACTION_OUTCOME_MAPPINGS.get(key)

    return None


def assess_risk_level(
    consequence_type: ConsequenceType,
    status: OutcomeStatus,
    impact_level: str,
    context: Optional[Dict[str, Any]] = None
) -> RiskLevel:
    """
    Assess risk level for a consequence.

    Args:
        consequence_type: Type of consequence
        status: Outcome status
        impact_level: Impact level
        context: Additional context

    Returns:
        Assessed risk level
    """
    context = context or {}

    # Base risk from impact level
    risk_map = {
        "low": RiskLevel.LOW,
        "medium": RiskLevel.MEDIUM,
        "high": RiskLevel.HIGH
    }
    base_risk = risk_map.get(impact_level, RiskLevel.MEDIUM)

    # Adjust based on status
    if status == OutcomeStatus.ERROR:
        # Errors escalate risk
        if base_risk == RiskLevel.LOW:
            base_risk = RiskLevel.MEDIUM
        elif base_risk == RiskLevel.MEDIUM:
            base_risk = RiskLevel.HIGH
    elif status == OutcomeStatus.TIMEOUT:
        # Timeouts add uncertainty
        if base_risk == RiskLevel.LOW:
            base_risk = RiskLevel.MEDIUM

    # Interaction outcomes have higher social risk
    if consequence_type == ConsequenceType.INTERACTION_OUTCOME:
        if status == OutcomeStatus.FAILURE and base_risk == RiskLevel.HIGH:
            base_risk = RiskLevel.CRITICAL

    # Check for boundary violations in context
    if context.get("boundary_violated"):
        base_risk = RiskLevel.CRITICAL

    return base_risk


def prevent_risk_escalation(
    assessed_risk: RiskLevel,
    signal_strength: float,
    config: ConsequenceProcessorConfig
) -> Tuple[RiskLevel, bool]:
    """
    Prevent escalation from low-risk signals to high-risk levels.

    This is a safety mechanism to prevent overreaction to weak signals.

    Args:
        assessed_risk: The initially assessed risk level
        signal_strength: Strength of the signal [0, 1]
        config: Processor configuration

    Returns:
        Tuple of (adjusted_risk, was_prevented)
    """
    # If signal is weak and risk is high, cap the risk
    if signal_strength < config.low_signal_threshold:
        max_risk = config.max_risk_from_low_signal

        risk_order = [RiskLevel.NONE, RiskLevel.LOW, RiskLevel.MEDIUM,
                      RiskLevel.HIGH, RiskLevel.CRITICAL]
        assessed_idx = risk_order.index(assessed_risk)
        max_idx = risk_order.index(max_risk)

        if assessed_idx > max_idx:
            return max_risk, True

    return assessed_risk, False


def check_boundary_stability(
    body_delta: BodyDelta,
    current_safety: float,
    current_energy: float,
    threshold: float
) -> Tuple[bool, List[str]]:
    """
    Check if body delta would violate boundary stability.

    Args:
        body_delta: Proposed body changes
        current_safety: Current safety level
        current_energy: Current energy level
        threshold: Stability threshold

    Returns:
        Tuple of (is_stable, violations)
    """
    violations = []

    # Check if changes would push values outside safe bounds
    new_safety = current_safety + body_delta.safety
    new_energy = current_energy + body_delta.energy

    # Safety boundaries [0.1, 0.9]
    if new_safety < 0.1:
        violations.append(f"safety_floor:{new_safety:.3f}")
    if new_safety > 0.9:
        violations.append(f"safety_ceiling:{new_safety:.3f}")

    # Energy boundaries [0.1, 0.9]
    if new_energy < 0.1:
        violations.append(f"energy_floor:{new_energy:.3f}")
    if new_energy > 0.9:
        violations.append(f"energy_ceiling:{new_energy:.3f}")

    # Check for large single changes
    if abs(body_delta.safety) > threshold * 2:
        violations.append(f"safety_change:{body_delta.safety:.3f}")
    if abs(body_delta.energy) > threshold * 2:
        violations.append(f"energy_change:{body_delta.energy:.3f}")

    return len(violations) == 0, violations


def generate_tags(
    consequence_type: ConsequenceType,
    status: OutcomeStatus,
    risk_level: RiskLevel,
    body_delta: BodyDelta,
    context: Optional[Dict[str, Any]] = None
) -> List[str]:
    """
    Generate classification tags for a consequence.

    Args:
        consequence_type: Type of consequence
        status: Outcome status
        risk_level: Assessed risk level
        body_delta: Body state changes
        context: Additional context

    Returns:
        List of tags
    """
    tags = []
    context = context or {}

    # Source tags
    if consequence_type == ConsequenceType.TOOL_RESULT:
        tags.append(ConsequenceTag.FROM_TOOL.value)
    elif consequence_type == ConsequenceType.ENV_OUTCOME:
        tags.append(ConsequenceTag.FROM_ENV.value)
    elif consequence_type == ConsequenceType.INTERACTION_OUTCOME:
        tags.append(ConsequenceTag.FROM_INTERACTION.value)

    # Outcome tags
    if status == OutcomeStatus.SUCCESS:
        tags.append(ConsequenceTag.SUCCESS.value)
    elif status == OutcomeStatus.FAILURE:
        tags.append(ConsequenceTag.FAILURE.value)
    elif status == OutcomeStatus.PARTIAL:
        tags.append(ConsequenceTag.PARTIAL.value)
    elif status == OutcomeStatus.TIMEOUT:
        tags.append(ConsequenceTag.TIMEOUT.value)
    elif status == OutcomeStatus.ERROR:
        tags.append(ConsequenceTag.ERROR.value)

    # Risk tags
    risk_tag_map = {
        RiskLevel.NONE: ConsequenceTag.RISK_NONE.value,
        RiskLevel.LOW: ConsequenceTag.RISK_LOW.value,
        RiskLevel.MEDIUM: ConsequenceTag.RISK_MEDIUM.value,
        RiskLevel.HIGH: ConsequenceTag.RISK_HIGH.value,
        RiskLevel.CRITICAL: ConsequenceTag.RISK_CRITICAL.value
    }
    tags.append(risk_tag_map.get(risk_level, ConsequenceTag.RISK_MEDIUM.value))

    # Control tags
    if context.get("controllable", True):
        tags.append(ConsequenceTag.CONTROLLED.value)
    else:
        tags.append(ConsequenceTag.UNCONTROLLED.value)

    # Boundary tags
    if context.get("boundary_hit"):
        tags.append(ConsequenceTag.BOUNDARY_HIT.value)
    else:
        tags.append(ConsequenceTag.BOUNDARY_SAFE.value)

    # Escalation prevention tag
    if context.get("escalation_prevented"):
        tags.append(ConsequenceTag.ESCALATION_CHECKED.value)
        tags.append(ConsequenceTag.LOW_SIGNAL_HIGH_RISK.value)

    return tags


def compute_allostasis_feedback(
    consequence_delta: ConsequenceDelta,
    current_safety: float,
    current_energy: float,
    config: ConsequenceProcessorConfig
) -> Optional[AllostasisFeedback]:
    """
    Compute feedback for allostasis (body state regulation).

    Args:
        consequence_delta: The consequence delta
        current_safety: Current safety level
        current_energy: Current energy level
        config: Processor configuration

    Returns:
        AllostasisFeedback if triggered, None otherwise
    """
    body_delta = consequence_delta.body_delta

    # Check if regulation is needed
    needs_regulation = False
    urgency = False
    reason_parts = []

    # Safety regulation
    if current_safety < 0.3 or body_delta.safety < -config.allostasis_trigger_threshold:
        needs_regulation = True
        reason_parts.append(f"safety_low:{current_safety:.2f}")
        if current_safety < 0.2:
            urgency = True

    # Energy regulation
    if current_energy < 0.3 or body_delta.energy < -config.allostasis_trigger_threshold:
        needs_regulation = True
        reason_parts.append(f"energy_low:{current_energy:.2f}")
        if current_energy < 0.2:
            urgency = True

    if not needs_regulation:
        return None

    # Calculate targets
    safety_target = min(0.6, current_safety + 0.2) if current_safety < 0.3 else 0.6
    energy_target = min(0.7, current_energy + 0.15) if current_energy < 0.3 else 0.7

    # Priority based on deficit (ensure non-negative)
    deficit = max(0, 0.6 - current_safety) + max(0, 0.7 - current_energy)
    priority = max(0.0, min(1.0, deficit / 0.8))

    return AllostasisFeedback(
        safety_target=safety_target,
        energy_target=energy_target,
        regulation_priority=priority,
        urgent=urgency,
        reason=";".join(reason_parts)
    )


def compute_precision_feedback(
    consequence_delta: ConsequenceDelta,
    expected_outcome: Optional[str],
    config: ConsequenceProcessorConfig
) -> Optional[PrecisionFeedback]:
    """
    Compute feedback for precision (prediction error weighting).

    Args:
        consequence_delta: The consequence delta
        expected_outcome: Expected outcome (if any)
        config: Processor configuration

    Returns:
        PrecisionFeedback if triggered, None otherwise
    """
    # Calculate prediction error based on outcome vs expectation
    prediction_error = 0.0
    reason = ""

    if expected_outcome:
        actual_status = consequence_delta.outcome_status
        if expected_outcome == "success" and actual_status != OutcomeStatus.SUCCESS:
            prediction_error = 0.3
            reason = f"expected_success_got_{actual_status.value}"
        elif expected_outcome == "failure" and actual_status == OutcomeStatus.SUCCESS:
            prediction_error = 0.2
            reason = "expected_failure_got_success"
        elif expected_outcome == "partial" and actual_status not in [OutcomeStatus.PARTIAL, OutcomeStatus.SUCCESS]:
            prediction_error = 0.15
            reason = f"expected_partial_got_{actual_status.value}"

    # Also consider uncertainty change as prediction error signal
    uncertainty_delta = abs(consequence_delta.body_delta.uncertainty)
    if uncertainty_delta > config.precision_trigger_threshold:
        prediction_error = max(prediction_error, uncertainty_delta)
        if reason:
            reason += ";uncertainty_spike"
        else:
            reason = "uncertainty_spike"

    if prediction_error < 0.05:
        return None

    # Adjust precision weight based on error
    # High error = lower precision weight (trust observations more)
    precision_weight = max(0.1, 0.5 - prediction_error)

    # Update rate based on error magnitude
    update_rate = min(0.5, config.precision_trigger_threshold + prediction_error)

    return PrecisionFeedback(
        precision_weight=precision_weight,
        prediction_error=prediction_error,
        update_rate=update_rate,
        reason=reason
    )


def compute_intrinsic_feedback(
    consequence_delta: ConsequenceDelta,
    value_weights: Optional[Dict[str, float]] = None,
    config: ConsequenceProcessorConfig = None
) -> Optional[IntrinsicFeedback]:
    """
    Compute feedback for intrinsic value signals.

    Args:
        consequence_delta: The consequence delta
        value_weights: Current value weights
        config: Processor configuration

    Returns:
        IntrinsicFeedback if triggered, None otherwise
    """
    if config is None:
        config = ConsequenceProcessorConfig()

    value_weights = value_weights or {}
    body_delta = consequence_delta.body_delta

    # Calculate value signal based on body changes and value priorities
    safety_value = value_weights.get("safety", 0.6)
    growth_value = value_weights.get("growth", 0.5)

    # Signal from safety changes
    safety_signal = body_delta.safety * safety_value

    # Signal from learning opportunity (uncertainty + failure)
    learning_signal = 0.0
    if consequence_delta.outcome_status == OutcomeStatus.FAILURE:
        learning_signal = growth_value * 0.2
    if body_delta.uncertainty > 0:
        learning_signal += growth_value * body_delta.uncertainty * 0.5

    # Combine signals
    value_signal = safety_signal + learning_signal * 0.3

    # Check threshold
    if abs(value_signal) < config.intrinsic_trigger_threshold:
        return None

    # Determine value type
    if abs(safety_signal) > abs(learning_signal):
        value_type = "safety"
        intensity = abs(safety_signal)
        reason = f"safety_change:{body_delta.safety:.3f}"
    else:
        value_type = "growth"
        intensity = abs(learning_signal)
        reason = f"learning_opportunity:{consequence_delta.outcome_status.value}"

    return IntrinsicFeedback(
        value_signal=value_signal,
        value_type=value_type,
        intensity=min(1.0, intensity),
        reason=reason
    )


def compute_meta_cognition_feedback(
    consequence_delta: ConsequenceDelta,
    current_uncertainty: float,
    config: ConsequenceProcessorConfig
) -> Optional[MetaCognitionFeedback]:
    """
    Compute feedback for meta-cognition decisions.

    Args:
        consequence_delta: The consequence delta
        current_uncertainty: Current uncertainty level
        config: Processor configuration

    Returns:
        MetaCognitionFeedback if triggered, None otherwise
    """
    body_delta = consequence_delta.body_delta
    risk_score = consequence_delta.get_risk_score()

    suggest_reflect = False
    suggest_clarify = False
    suggest_learn = False
    confidence_adj = 0.0
    reasons = []

    # Suggest reflection on high uncertainty or unexpected outcomes
    if consequence_delta.outcome_status == OutcomeStatus.UNEXPECTED:
        suggest_reflect = True
        confidence_adj -= 0.1
        reasons.append("unexpected_outcome")

    # Suggest clarification on partial success with high uncertainty
    if consequence_delta.outcome_status == OutcomeStatus.PARTIAL:
        if current_uncertainty > 0.5 or body_delta.uncertainty > 0.1:
            suggest_clarify = True
            reasons.append("partial_uncertain")

    # Suggest learning on failure
    if consequence_delta.outcome_status == OutcomeStatus.FAILURE:
        if risk_score < 0.7:  # Not catastrophic failure
            suggest_learn = True
            reasons.append("failure_learning_opportunity")

    # High uncertainty delta suggests reflection
    if abs(body_delta.uncertainty) > config.meta_cognition_trigger_threshold:
        suggest_reflect = True
        confidence_adj -= body_delta.uncertainty * 0.2
        reasons.append(f"uncertainty_delta:{body_delta.uncertainty:.3f}")

    # Critical risk suggests reflection
    if consequence_delta.risk_level == RiskLevel.CRITICAL:
        suggest_reflect = True
        confidence_adj -= 0.15
        reasons.append("critical_risk")

    if not suggest_reflect and not suggest_clarify and not suggest_learn:
        return None

    return MetaCognitionFeedback(
        suggest_reflect=suggest_reflect,
        suggest_clarify=suggest_clarify,
        suggest_learn=suggest_learn,
        confidence_adjustment=confidence_adj,
        reason=";".join(reasons)
    )


class ConsequenceProcessor:
    """
    Main consequence processor.

    Processes consequence events and generates:
    - Body deltas
    - Classification tags
    - Feedback for allostasis, precision, intrinsic, and meta-cognition
    - Trace information for auditability
    """

    def __init__(self, config: Optional[ConsequenceProcessorConfig] = None):
        self.config = config or ConsequenceProcessorConfig()
        self._trace_counter = 0

    def _generate_trace_id(self) -> str:
        """Generate a unique trace ID."""
        self._trace_counter += 1
        return f"cons_{int(time.time())}_{self._trace_counter:06d}"

    def process(
        self,
        consequence_type: ConsequenceType,
        status: OutcomeStatus,
        impact_level: str = "medium",
        source: str = "",
        expected_outcome: Optional[str] = None,
        current_safety: float = 0.6,
        current_energy: float = 0.7,
        current_uncertainty: float = 0.5,
        value_weights: Optional[Dict[str, float]] = None,
        context: Optional[Dict[str, Any]] = None,
        parent_trace_id: Optional[str] = None
    ) -> FeedbackBundle:
        """
        Process a consequence event and generate feedback bundle.

        Args:
            consequence_type: Type of consequence
            status: Outcome status
            impact_level: Impact level (low, medium, high)
            source: Source of the consequence
            expected_outcome: Expected outcome (for precision calculation)
            current_safety: Current safety level
            current_energy: Current energy level
            current_uncertainty: Current uncertainty level
            value_weights: Value weights for intrinsic feedback
            context: Additional context
            parent_trace_id: Parent trace ID for chaining

        Returns:
            FeedbackBundle with all feedback types
        """
        context = context or {}

        # 1. Look up body delta
        body_delta = lookup_body_delta(consequence_type, status, impact_level)
        if body_delta is None:
            # Default to empty delta if no mapping found
            body_delta = BodyDelta()

        # 2. Assess risk level
        risk_level = assess_risk_level(consequence_type, status, impact_level, context)

        # 3. Calculate signal strength for escalation prevention
        signal_strength = body_delta.magnitude()

        # 4. Prevent escalation from low signals
        risk_level, escalation_prevented = prevent_risk_escalation(
            risk_level, signal_strength, self.config
        )
        if escalation_prevented:
            context["escalation_prevented"] = True

        # 5. Check boundary stability
        is_stable, violations = check_boundary_stability(
            body_delta, current_safety, current_energy, self.config.boundary_stability_threshold
        )
        if not is_stable:
            context["boundary_hit"] = True
            # Clamp delta to maintain stability
            body_delta = body_delta.clamp(-0.2, 0.2)

        # 6. Generate tags
        tags = generate_tags(consequence_type, status, risk_level, body_delta, context)

        # 7. Create consequence delta
        consequence_delta = ConsequenceDelta(
            consequence_type=consequence_type,
            outcome_status=status,
            risk_level=risk_level,
            body_delta=body_delta,
            tags=tags,
            confidence=1.0 - signal_strength * 0.5,  # Higher magnitude = lower confidence
            source=source,
            context=context,
            trace_id=self._generate_trace_id(),
            parent_trace_id=parent_trace_id
        )

        # 8. Compute feedback for all subsystems
        allostasis = compute_allostasis_feedback(
            consequence_delta, current_safety, current_energy, self.config
        )
        if allostasis:
            consequence_delta.feeds_allostasis = True
            consequence_delta.add_tag(ConsequenceTag.ALLOSTASIS.value)

        precision = compute_precision_feedback(
            consequence_delta, expected_outcome, self.config
        )
        if precision:
            consequence_delta.feeds_precision = True
            consequence_delta.add_tag(ConsequenceTag.PRECISION.value)

        intrinsic = compute_intrinsic_feedback(
            consequence_delta, value_weights, self.config
        )
        if intrinsic:
            consequence_delta.feeds_intrinsic = True
            consequence_delta.add_tag(ConsequenceTag.INTRINSIC.value)

        meta_cognition = compute_meta_cognition_feedback(
            consequence_delta, current_uncertainty, self.config
        )
        if meta_cognition:
            consequence_delta.feeds_meta_cognition = True
            consequence_delta.add_tag(ConsequenceTag.META_COGNITION.value)

        return FeedbackBundle(
            allostasis=allostasis,
            precision=precision,
            intrinsic=intrinsic,
            meta_cognition=meta_cognition,
            consequence_delta=consequence_delta
        )

    def process_tool_result(
        self,
        status: OutcomeStatus,
        tool_name: str,
        impact_level: str = "medium",
        **kwargs
    ) -> FeedbackBundle:
        """Convenience method for processing tool results."""
        return self.process(
            consequence_type=ConsequenceType.TOOL_RESULT,
            status=status,
            impact_level=impact_level,
            source=tool_name,
            **kwargs
        )

    def process_env_outcome(
        self,
        status: OutcomeStatus,
        env_name: str,
        impact_level: str = "medium",
        **kwargs
    ) -> FeedbackBundle:
        """Convenience method for processing environment outcomes."""
        return self.process(
            consequence_type=ConsequenceType.ENV_OUTCOME,
            status=status,
            impact_level=impact_level,
            source=env_name,
            **kwargs
        )

    def process_interaction_outcome(
        self,
        status: OutcomeStatus,
        target: str,
        impact_level: str = "medium",
        **kwargs
    ) -> FeedbackBundle:
        """Convenience method for processing interaction outcomes."""
        return self.process(
            consequence_type=ConsequenceType.INTERACTION_OUTCOME,
            status=status,
            impact_level=impact_level,
            source=target,
            **kwargs
        )
