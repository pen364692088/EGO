"""
MVP-5 D1: Precision Controller

Dynamic attention/weight arbitration system that computes precision weights
for different information channels based on uncertainty, prediction error,
ledger evidence, user affect confidence, and social threat.

Precision weights (all in [0, 1]):
- w_external: Trust in current user input
- w_internal: Trust in interoceptive states (energy, social_safety)
- w_memory: Trust in historical/ledger/bond data
- w_action: Action decisiveness (high = decisive, low = clarify/conservative)
- w_explore: Exploration tendency (questioning/curiosity)

These weights influence:
1. Meta-cognition triggers (clarify/reflect/slow_down)
2. Action selection preferences
3. Explanation generation
"""
import math
import time
from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel, Field
from dataclasses import dataclass, field


class PrecisionWeights(BaseModel):
    """
    Precision weights for attention arbitration.
    All weights are in [0, 1] and should sum to approximately 1.0
    for external/internal/memory (the evidence channels).
    """
    w_external: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Weight for trusting current user input"
    )
    w_internal: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Weight for trusting interoceptive states"
    )
    w_memory: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Weight for trusting historical/ledger/bond data"
    )
    w_action: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Action decisiveness: high = decisive, low = clarify"
    )
    w_explore: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Exploration tendency: high = ask/curious"
    )

    def get_primary_evidence_source(self) -> Tuple[str, float]:
        """Return the primary evidence source and its weight."""
        sources = [
            ("external", self.w_external),
            ("internal", self.w_internal),
            ("memory", self.w_memory)
        ]
        return max(sources, key=lambda x: x[1])

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "w_external": self.w_external,
            "w_internal": self.w_internal,
            "w_memory": self.w_memory,
            "w_action": self.w_action,
            "w_explore": self.w_explore
        }


class PrecisionContext(BaseModel):
    """Context inputs for precision computation."""
    uncertainty: float = Field(default=0.5, ge=0.0, le=1.0)
    prediction_error: float = Field(default=0.0, ge=0.0)
    consecutive_prediction_errors: int = Field(default=0, ge=0)
    ledger_evidence_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    user_affect_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    social_threat: float = Field(default=0.0, ge=0.0, le=1.0)
    bond_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    energy: float = Field(default=0.7, ge=0.0, le=1.0)
    social_safety: float = Field(default=0.6, ge=0.0, le=1.0)
    cold_treatment_duration: float = Field(default=0.0, ge=0.0)
    has_promise_context: bool = Field(default=False)


class PrecisionTraceEntry(BaseModel):
    """Trace entry for precision computation."""
    timestamp: float
    weights: PrecisionWeights
    context: PrecisionContext
    primary_source: str
    reasoning: List[str]


@dataclass
class PrecisionFactors:
    """Internal factors used in precision computation."""
    uncertainty_factor: float = 0.5
    prediction_error_factor: float = 0.0
    ledger_factor: float = 0.0
    affect_factor: float = 0.5
    threat_factor: float = 0.0
    energy_factor: float = 0.7
    safety_factor: float = 0.6
    bond_factor: float = 0.0


def sigmoid(x: float, steepness: float = 10.0, midpoint: float = 0.5) -> float:
    """Sigmoid function for smooth transitions."""
    return 1.0 / (1.0 + math.exp(-steepness * (x - midpoint)))


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp value to [min_val, max_val]."""
    return max(min_val, min(max_val, value))


class PrecisionController:
    """
    Main precision controller for dynamic weight arbitration.
    
    Computes precision weights based on multiple contextual factors:
    - Uncertainty: Higher uncertainty reduces w_external, increases w_memory
    - Prediction error: High errors reduce confidence in current input
    - Ledger evidence: Strong promise/violation evidence increases w_memory
    - User affect confidence: Low confidence reduces w_external
    - Social threat: High threat reduces w_action (more cautious)
    - Energy: Low energy reduces w_explore and w_action
    - Bond strength: Strong bonds increase w_memory
    """
    
    # Configuration constants
    UNCERTAINTY_THRESHOLD = 0.7
    PREDICTION_ERROR_THRESHOLD = 0.3
    HIGH_PREDICTION_ERROR_STREAK = 3
    SOCIAL_THREAT_THRESHOLD = 0.6
    LOW_ENERGY_THRESHOLD = 0.3
    LOW_SAFETY_THRESHOLD = 0.4
    STRONG_BOND_THRESHOLD = 0.6
    
    def __init__(self, seed: Optional[int] = None):
        """
        Initialize precision controller.
        
        Args:
            seed: Optional random seed for deterministic behavior
        """
        if seed is not None:
            import random
            random.seed(seed)
        self._history: List[PrecisionTraceEntry] = []
        self._max_history = 100
    
    def compute_weights(self, context: PrecisionContext) -> Tuple[PrecisionWeights, List[str]]:
        """
        Compute precision weights from context.
        
        Args:
            context: PrecisionContext with all input factors
        
        Returns:
            Tuple of (PrecisionWeights, reasoning_list)
        """
        reasoning = []
        
        # Step 1: Compute base weights from uncertainty
        w_external, w_internal, w_memory = self._compute_evidence_weights(context, reasoning)
        
        # Step 2: Compute w_action from threat, energy, and uncertainty
        w_action = self._compute_action_weight(context, reasoning)
        
        # Step 3: Compute w_explore from energy, threat, and uncertainty
        w_explore = self._compute_explore_weight(context, reasoning)
        
        weights = PrecisionWeights(
            w_external=w_external,
            w_internal=w_internal,
            w_memory=w_memory,
            w_action=w_action,
            w_explore=w_explore
        )
        
        return weights, reasoning
    
    def _compute_evidence_weights(
        self,
        context: PrecisionContext,
        reasoning: List[str]
    ) -> Tuple[float, float, float]:
        """
        Compute external/internal/memory weights.
        
        Returns:
            Tuple of (w_external, w_internal, w_memory)
        """
        # Base: equal weighting
        base_external = 0.4
        base_internal = 0.3
        base_memory = 0.3
        
        # Adjust for uncertainty
        # High uncertainty -> trust external less, memory more
        if context.uncertainty > self.UNCERTAINTY_THRESHOLD:
            uncertainty_penalty = (context.uncertainty - self.UNCERTAINTY_THRESHOLD) / (1 - self.UNCERTAINTY_THRESHOLD)
            base_external -= uncertainty_penalty * 0.2
            base_memory += uncertainty_penalty * 0.15
            reasoning.append(f"High uncertainty ({context.uncertainty:.2f}) reduces external trust")
        elif context.uncertainty < 0.3:
            # Low uncertainty -> trust external more
            base_external += 0.1
            base_memory -= 0.05
            reasoning.append(f"Low uncertainty ({context.uncertainty:.2f}) increases external trust")
        
        # Adjust for prediction error streak
        if context.consecutive_prediction_errors >= self.HIGH_PREDICTION_ERROR_STREAK:
            error_penalty = min(0.2, context.consecutive_prediction_errors * 0.05)
            base_external -= error_penalty
            base_internal += error_penalty * 0.5
            base_memory += error_penalty * 0.5
            reasoning.append(f"Prediction error streak ({context.consecutive_prediction_errors}) reduces external trust")
        
        # Adjust for user affect confidence
        if context.user_affect_confidence < 0.4:
            confidence_penalty = (0.4 - context.user_affect_confidence) / 0.4
            base_external -= confidence_penalty * 0.15
            base_internal += confidence_penalty * 0.1
            reasoning.append(f"Low affect confidence ({context.user_affect_confidence:.2f}) reduces external trust")
        
        # Adjust for ledger evidence
        if context.ledger_evidence_strength > 0.5:
            # Strong ledger evidence increases memory weight
            ledger_boost = (context.ledger_evidence_strength - 0.5) * 0.3
            base_memory += ledger_boost
            base_external -= ledger_boost * 0.5
            reasoning.append(f"Strong ledger evidence ({context.ledger_evidence_strength:.2f}) increases memory weight")
        
        # Adjust for bond strength
        if context.bond_strength > self.STRONG_BOND_THRESHOLD:
            bond_boost = (context.bond_strength - self.STRONG_BOND_THRESHOLD) / (1 - self.STRONG_BOND_THRESHOLD)
            base_memory += bond_boost * 0.1
            reasoning.append(f"Strong bond ({context.bond_strength:.2f}) increases memory weight")
        
        # Adjust for cold treatment
        if context.cold_treatment_duration > 1800:  # 30 minutes
            # Cold treatment reduces external trust
            cold_penalty = min(0.15, context.cold_treatment_duration / 36000)
            base_external -= cold_penalty
            base_internal += cold_penalty * 0.5
            base_memory += cold_penalty * 0.5
            reasoning.append(f"Cold treatment ({context.cold_treatment_duration/60:.0f}min) reduces external trust")
        
        # Normalize to sum to 1.0
        total = base_external + base_internal + base_memory
        if total > 0:
            w_external = clamp(base_external / total)
            w_internal = clamp(base_internal / total)
            w_memory = clamp(base_memory / total)
        else:
            w_external = w_internal = w_memory = 1.0 / 3.0
        
        return w_external, w_internal, w_memory
    
    def _compute_action_weight(self, context: PrecisionContext, reasoning: List[str]) -> float:
        """
        Compute w_action (decisiveness).
        
        High = decisive, low = clarify/conservative
        """
        base_action = 0.5
        
        # Social threat reduces decisiveness (more cautious)
        if context.social_threat > self.SOCIAL_THREAT_THRESHOLD:
            threat_penalty = (context.social_threat - self.SOCIAL_THREAT_THRESHOLD) / (1 - self.SOCIAL_THREAT_THRESHOLD)
            base_action -= threat_penalty * 0.3
            reasoning.append(f"High social threat ({context.social_threat:.2f}) reduces decisiveness")
        
        # Low energy reduces decisiveness
        if context.energy < self.LOW_ENERGY_THRESHOLD:
            energy_penalty = (self.LOW_ENERGY_THRESHOLD - context.energy) / self.LOW_ENERGY_THRESHOLD
            base_action -= energy_penalty * 0.2
            reasoning.append(f"Low energy ({context.energy:.2f}) reduces decisiveness")
        
        # Low safety reduces decisiveness
        if context.social_safety < self.LOW_SAFETY_THRESHOLD:
            safety_penalty = (self.LOW_SAFETY_THRESHOLD - context.social_safety) / self.LOW_SAFETY_THRESHOLD
            base_action -= safety_penalty * 0.25
            reasoning.append(f"Low social safety ({context.social_safety:.2f}) reduces decisiveness")
        
        # High uncertainty reduces decisiveness
        if context.uncertainty > self.UNCERTAINTY_THRESHOLD:
            uncertainty_penalty = (context.uncertainty - self.UNCERTAINTY_THRESHOLD) / (1 - self.UNCERTAINTY_THRESHOLD)
            base_action -= uncertainty_penalty * 0.2
            reasoning.append(f"High uncertainty reduces decisiveness")
        
        # Promise context increases decisiveness (commitment matters)
        if context.has_promise_context and context.ledger_evidence_strength > 0.3:
            base_action += 0.1
            reasoning.append("Promise context increases decisiveness")
        
        return clamp(base_action)
    
    def _compute_explore_weight(self, context: PrecisionContext, reasoning: List[str]) -> float:
        """
        Compute w_explore (exploration tendency).
        
        High = ask questions, seek clarification, curious
        """
        base_explore = 0.3
        
        # High uncertainty increases exploration (need more info)
        if context.uncertainty > 0.5:
            explore_boost = (context.uncertainty - 0.5) * 0.4
            base_explore += explore_boost
            reasoning.append(f"High uncertainty ({context.uncertainty:.2f}) increases exploration")
        
        # Low energy reduces exploration (conservative)
        if context.energy < self.LOW_ENERGY_THRESHOLD:
            energy_penalty = (self.LOW_ENERGY_THRESHOLD - context.energy) / self.LOW_ENERGY_THRESHOLD
            base_explore -= energy_penalty * 0.3
            reasoning.append(f"Low energy ({context.energy:.2f}) reduces exploration")
        
        # Social threat reduces exploration (risky)
        if context.social_threat > self.SOCIAL_THREAT_THRESHOLD:
            threat_penalty = (context.social_threat - self.SOCIAL_THREAT_THRESHOLD) / (1 - self.SOCIAL_THREAT_THRESHOLD)
            base_explore -= threat_penalty * 0.25
            reasoning.append(f"High social threat ({context.social_threat:.2f}) reduces exploration")
        
        # Low affect confidence increases exploration (need clarification)
        if context.user_affect_confidence < 0.5:
            explore_boost = (0.5 - context.user_affect_confidence) * 0.3
            base_explore += explore_boost
            reasoning.append(f"Low affect confidence ({context.user_affect_confidence:.2f}) increases exploration")
        
        # Strong bond increases exploration (safe to ask)
        if context.bond_strength > self.STRONG_BOND_THRESHOLD:
            bond_boost = (context.bond_strength - self.STRONG_BOND_THRESHOLD) / (1 - self.STRONG_BOND_THRESHOLD)
            base_explore += bond_boost * 0.15
            reasoning.append(f"Strong bond ({context.bond_strength:.2f}) increases exploration")
        
        return clamp(base_explore)
    
    def record_trace(
        self,
        weights: PrecisionWeights,
        context: PrecisionContext,
        reasoning: List[str]
    ) -> PrecisionTraceEntry:
        """Record a precision computation to trace history."""
        primary_source, _ = weights.get_primary_evidence_source()
        entry = PrecisionTraceEntry(
            timestamp=time.time(),
            weights=weights,
            context=context,
            primary_source=primary_source,
            reasoning=reasoning
        )
        self._history.append(entry)
        
        # Trim history
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        
        return entry
    
    def get_history(self, limit: int = 10) -> List[PrecisionTraceEntry]:
        """Get recent trace history."""
        return self._history[-limit:]
    
    def get_trace_summary(self) -> Dict[str, Any]:
        """Get summary statistics from trace history."""
        if not self._history:
            return {"count": 0}
        
        recent = self._history[-20:]
        avg_weights = {
            "w_external": sum(e.weights.w_external for e in recent) / len(recent),
            "w_internal": sum(e.weights.w_internal for e in recent) / len(recent),
            "w_memory": sum(e.weights.w_memory for e in recent) / len(recent),
            "w_action": sum(e.weights.w_action for e in recent) / len(recent),
            "w_explore": sum(e.weights.w_explore for e in recent) / len(recent),
        }
        
        source_counts = {}
        for e in recent:
            source_counts[e.primary_source] = source_counts.get(e.primary_source, 0) + 1
        
        return {
            "count": len(self._history),
            "recent_count": len(recent),
            "average_weights": avg_weights,
            "primary_source_distribution": source_counts
        }
    
    def clear_history(self):
        """Clear trace history."""
        self._history = []


# Global controller instance
_precision_controller: Optional[PrecisionController] = None


def get_precision_controller(seed: Optional[int] = None) -> PrecisionController:
    """Get or create the global precision controller."""
    global _precision_controller
    if _precision_controller is None:
        _precision_controller = PrecisionController(seed=seed)
    return _precision_controller


def reset_precision_controller():
    """Reset the global precision controller (for testing)."""
    global _precision_controller
    _precision_controller = None


def build_precision_context(
    uncertainty: float = 0.5,
    prediction_error: float = 0.0,
    consecutive_prediction_errors: int = 0,
    ledger_evidence_strength: float = 0.0,
    user_affect_confidence: float = 0.5,
    social_threat: float = 0.0,
    bond_strength: float = 0.0,
    energy: float = 0.7,
    social_safety: float = 0.6,
    cold_treatment_duration: float = 0.0,
    has_promise_context: bool = False
) -> PrecisionContext:
    """Helper to build a PrecisionContext."""
    return PrecisionContext(
        uncertainty=uncertainty,
        prediction_error=prediction_error,
        consecutive_prediction_errors=consecutive_prediction_errors,
        ledger_evidence_strength=ledger_evidence_strength,
        user_affect_confidence=user_affect_confidence,
        social_threat=social_threat,
        bond_strength=bond_strength,
        energy=energy,
        social_safety=social_safety,
        cold_treatment_duration=cold_treatment_duration,
        has_promise_context=has_promise_context
    )


def apply_precision_to_meta_cognition(
    weights: PrecisionWeights,
    base_trigger_uncertainty: float = 0.7
) -> float:
    """
    Apply precision weights to meta-cognition trigger threshold.
    
    Returns adjusted uncertainty threshold for triggering meta-cognition.
    Lower threshold = more likely to trigger clarification/reflect.
    """
    # Low w_action -> lower threshold (more cautious)
    # Low w_external -> lower threshold (don't trust input)
    adjustment = 0.0
    
    if weights.w_action < 0.4:
        adjustment -= 0.1
    if weights.w_external < 0.3:
        adjustment -= 0.1
    if weights.w_explore > 0.5:
        adjustment -= 0.05  # High explore -> more clarification
    
    return clamp(base_trigger_uncertainty + adjustment, 0.3, 0.9)


def apply_precision_to_action_selection(
    weights: PrecisionWeights,
    action_scores: Dict[str, float]
) -> Dict[str, float]:
    """
    Apply precision weights to action selection scores.
    
    Modifies action scores based on w_action and w_explore.
    """
    modified_scores = dict(action_scores)
    
    # Low w_action -> penalize aggressive actions, boost conservative
    if weights.w_action < 0.4:
        if "attack" in modified_scores:
            modified_scores["attack"] *= 0.5
        if "withdraw" in modified_scores:
            modified_scores["withdraw"] *= 1.2
        if "boundary" in modified_scores:
            modified_scores["boundary"] *= 1.1
    
    # High w_action -> boost decisive actions
    if weights.w_action > 0.7:
        if "approach" in modified_scores:
            modified_scores["approach"] *= 1.1
        if "repair_offer" in modified_scores:
            modified_scores["repair_offer"] *= 1.1
    
    # High w_explore -> boost approach (seeking)
    if weights.w_explore > 0.5:
        if "approach" in modified_scores:
            modified_scores["approach"] *= 1.15
    
    # Low w_explore -> penalize approach
    if weights.w_explore < 0.2:
        if "approach" in modified_scores:
            modified_scores["approach"] *= 0.9
    
    return modified_scores


def format_precision_summary(weights: PrecisionWeights, max_chars: int = 200) -> str:
    """
    Format a concise precision summary for explanations.
    
    Args:
        weights: PrecisionWeights to summarize
        max_chars: Maximum characters (for 3KB constraint compliance)
    
    Returns:
        Concise summary string
    """
    primary_source, primary_weight = weights.get_primary_evidence_source()
    
    summary = (
        f"Precision: ext={weights.w_external:.2f} int={weights.w_internal:.2f} "
        f"mem={weights.w_memory:.2f} act={weights.w_action:.2f} exp={weights.w_explore:.2f} "
        f"| primary={primary_source}({primary_weight:.2f})"
    )
    
    if len(summary) > max_chars:
        summary = summary[:max_chars-3] + "..."
    
    return summary


def get_precision_evidence_source_note(weights: PrecisionWeights) -> str:
    """Get a brief note about the primary evidence source."""
    primary_source, weight = weights.get_primary_evidence_source()
    
    notes = {
        "external": f"Prioritizing current input (w={weight:.2f})",
        "internal": f"Prioritizing interoceptive states (w={weight:.2f})",
        "memory": f"Prioritizing historical evidence (w={weight:.2f})"
    }
    
    return notes.get(primary_source, f"Primary: {primary_source} ({weight:.2f})")
