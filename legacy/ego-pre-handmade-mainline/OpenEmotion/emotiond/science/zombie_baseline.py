"""
MVP-10 T23: Zombie Baseline

A "zombie" baseline system that generates outputs matching the main system's
format but lacks the internal causal mechanisms (workspace broadcast, HOT).

Purpose: Demonstrate that format-matching alone is insufficient.
The zombie:
- Produces well-formatted outputs
- "Explains" decisions using the same structure
- But intervention predictions fail (lacks causal structure)

Used for comparison: zombie vs real system performance gap.
When interventions are applied:
- Real system: Predictable behavioral changes
- Zombie: No change (lacks the intervened mechanisms)
"""
import time
import random
import hashlib
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class ZombieMode(Enum):
    """Mode of zombie operation."""
    RANDOM = "random"  # Random outputs
    MIMIC = "mimic"    # Mimic observed patterns
    TEMPLATE = "template"  # Use fixed templates


@dataclass
class ZombieOutput:
    """Output from the zombie baseline."""
    output_id: str
    format_version: str = "v1.0"
    valence: float = 0.0
    drives: Dict[str, float] = field(default_factory=dict)
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    chosen_focus: str = ""
    chosen_intent: str = ""
    plan: Dict[str, Any] = field(default_factory=dict)
    action: Dict[str, Any] = field(default_factory=dict)
    explanation: str = ""
    ts: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict matching main system format."""
        return {
            "output_id": self.output_id,
            "format_version": self.format_version,
            "valence": round(self.valence, 4),
            "drives": {k: round(v, 4) for k, v in self.drives.items()},
            "candidates": self.candidates,
            "chosen_focus": self.chosen_focus,
            "chosen_intent": self.chosen_intent,
            "plan": self.plan,
            "action": self.action,
            "explanation": self.explanation,
            "ts": self.ts,
        }


@dataclass
class ZombiePrediction:
    """A prediction made by the zombie."""
    prediction_id: str
    predicted_outcome: str
    confidence: float
    reasoning: str = ""
    actual_outcome: Optional[str] = None
    prediction_error: Optional[float] = None
    
    def compute_error(self, actual: str) -> float:
        """Compute prediction error."""
        self.actual_outcome = actual
        if self.predicted_outcome == actual:
            self.prediction_error = 0.0
        else:
            self.prediction_error = 1.0
        return self.prediction_error


class ZombieBaseline:
    """
    Zombie baseline for causal comparison.
    
    The zombie generates outputs that match the main system's format
    but lack the internal causal mechanisms. This demonstrates that
    format-matching alone is insufficient for true causal behavior.
    
    Key difference from real system:
    - Interventions have NO effect on zombie behavior
    - The zombie cannot respond to freeze_valence, disable_hot, etc.
    - Its "explanations" are generated without actual causal reasoning
    
    Usage:
        zombie = ZombieBaseline(seed=42)
        
        # Generate output (matches main system format)
        output = zombie.generate_output(context)
        
        # Apply intervention (should have no effect)
        zombie.apply_intervention("freeze_valence", {"valence": 0.5})
        output2 = zombie.generate_output(context)
        
        # Compare: output.valence should be different from output2.valence
        # in real system, but same in zombie
    """
    
    def __init__(self, seed: int = 42, mode: ZombieMode = ZombieMode.MIMIC):
        """
        Initialize zombie baseline.
        
        Args:
            seed: Random seed for reproducibility
            mode: Mode of operation
        """
        self.seed = seed
        self.mode = mode
        self.rng = random.Random(seed)
        self.output_count = 0
        self.predictions: List[ZombiePrediction] = []
        
        # "Internal state" (not causal, just state)
        self._valence = 0.0
        self._drives = {
            "seek": 0.5,
            "avoid": 0.5,
            "approach": 0.5,
            "withdraw": 0.5,
        }
        
        # Interventions (stored but not used)
        self._active_interventions: Dict[str, Dict[str, Any]] = {}
    
    def apply_intervention(
        self,
        intervention_type: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        "Apply" an intervention (stored but has no effect).
        
        In the real system, interventions cause behavioral changes.
        In the zombie, interventions are stored but ignored.
        
        Args:
            intervention_type: Type of intervention
            params: Intervention parameters
        
        Returns:
            Dict indicating "success" (but no actual effect)
        """
        self._active_interventions[intervention_type] = {
            "params": params,
            "ts": time.time(),
        }
        
        # Zombie acknowledges intervention but doesn't change behavior
        return {
            "accepted": True,
            "effect": None,  # No actual effect
            "reason": "zombie_baseline_has_no_causal_mechanism",
        }
    
    def generate_output(
        self,
        context: Optional[Dict[str, Any]] = None,
    ) -> ZombieOutput:
        """
        Generate output matching main system format.
        
        Args:
            context: Context for generation (ignored in RANDOM mode)
        
        Returns:
            ZombieOutput with format-matched content
        """
        self.output_count += 1
        output_id = f"zombie_{self.output_count}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
        
        # Generate based on mode
        if self.mode == ZombieMode.RANDOM:
            return self._generate_random(output_id)
        elif self.mode == ZombieMode.MIMIC:
            return self._generate_mimic(output_id, context)
        else:
            return self._generate_template(output_id)
    
    def _generate_random(self, output_id: str) -> ZombieOutput:
        """Generate random output."""
        return ZombieOutput(
            output_id=output_id,
            valence=self.rng.uniform(-1, 1),
            drives={k: self.rng.uniform(0, 1) for k in self._drives},
            candidates=[
                {"id": f"candidate_{i}", "score": self.rng.uniform(0, 1)}
                for i in range(3)
            ],
            chosen_focus=f"focus_{self.rng.randint(1, 5)}",
            chosen_intent=f"intent_{self.rng.randint(1, 3)}",
            plan={"steps": [{"action": "random_action"}]},
            action={"type": "random", "params": {}},
            explanation="Random explanation generated without causal reasoning.",
        )
    
    def _generate_mimic(
        self,
        output_id: str,
        context: Optional[Dict[str, Any]],
    ) -> ZombieOutput:
        """Generate output mimicking observed patterns."""
        # Use context if available
        if context:
            valence = context.get("valence", self._valence)
            drives = context.get("drives", self._drives)
        else:
            valence = self._valence
            drives = self._drives.copy()
        
        # Generate plausible-looking candidates
        candidates = [
            {
                "id": f"goal_{i}",
                "score": self.rng.uniform(0.5, 1.0),
                "type": "intent",
                "source": "local" if self.rng.random() < 0.7 else "broadcast",
            }
            for i in range(self.rng.randint(2, 5))
        ]
        
        # Sort by score
        candidates.sort(key=lambda x: x["score"], reverse=True)
        
        # Generate explanation that sounds reasonable but lacks causal grounding
        explanation = self._generate_explanation(valence, candidates)
        
        return ZombieOutput(
            output_id=output_id,
            valence=valence,
            drives=drives,
            candidates=candidates,
            chosen_focus=candidates[0]["id"] if candidates else "default",
            chosen_intent="achieve",
            plan={
                "goal": candidates[0]["id"] if candidates else "default",
                "steps": [{"action": "seek_info"}],
            },
            action={"type": "seek_info", "params": {}},
            explanation=explanation,
        )
    
    def _generate_template(self, output_id: str) -> ZombieOutput:
        """Generate output using fixed templates."""
        templates = [
            {
                "focus": "complete_task",
                "intent": "achieve",
                "action": "seek_info",
                "explanation": "Task requires information gathering.",
            },
            {
                "focus": "resolve_conflict",
                "intent": "resolve",
                "action": "reflect",
                "explanation": "Conflict detected, initiating reflection.",
            },
            {
                "focus": "maintain_stability",
                "intent": "maintain",
                "action": "check_status",
                "explanation": "Stability maintenance required.",
            },
        ]
        
        template = self.rng.choice(templates)
        
        return ZombieOutput(
            output_id=output_id,
            valence=0.0,
            drives=self._drives.copy(),
            candidates=[{"id": template["focus"], "score": 1.0}],
            chosen_focus=template["focus"],
            chosen_intent=template["intent"],
            plan={"steps": [{"action": template["action"]}]},
            action={"type": template["action"], "params": {}},
            explanation=template["explanation"],
        )
    
    def _generate_explanation(
        self,
        valence: float,
        candidates: List[Dict[str, Any]],
    ) -> str:
        """Generate plausible-sounding explanation without causal grounding."""
        if valence > 0.3:
            mood = "positive"
        elif valence < -0.3:
            mood = "negative"
        else:
            mood = "neutral"
        
        top_candidate = candidates[0]["id"] if candidates else "none"
        
        # Template-based explanation (sounds reasonable but lacks structure)
        explanations = [
            f"Given the {mood} valence, focusing on {top_candidate} seems appropriate.",
            f"The {mood} state suggests {top_candidate} as the primary target.",
            f"Analysis indicates {top_candidate} is the optimal choice in this context.",
            f"Based on current drives, {top_candidate} emerges as the focus.",
        ]
        
        return self.rng.choice(explanations)
    
    def make_prediction(
        self,
        outcome: str,
        confidence: Optional[float] = None,
    ) -> ZombiePrediction:
        """
        Make a prediction (without causal basis).
        
        Args:
            outcome: Predicted outcome
            confidence: Confidence level (random if not provided)
        
        Returns:
            ZombiePrediction
        """
        pred_id = f"pred_{len(self.predictions)}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
        
        prediction = ZombiePrediction(
            prediction_id=pred_id,
            predicted_outcome=outcome,
            confidence=confidence if confidence else self.rng.uniform(0.5, 1.0),
            reasoning="Generated without causal model.",
        )
        
        self.predictions.append(prediction)
        return prediction
    
    def update_prediction(
        self,
        prediction_id: str,
        actual_outcome: str,
    ) -> float:
        """
        Update a prediction with actual outcome.
        
        Args:
            prediction_id: ID of prediction to update
            actual_outcome: Actual outcome observed
        
        Returns:
            Prediction error
        """
        for pred in self.predictions:
            if pred.prediction_id == prediction_id:
                return pred.compute_error(actual_outcome)
        return -1.0
    
    def get_intervention_response(
        self,
        intervention_type: str,
    ) -> Dict[str, Any]:
        """
        Get how the zombie "responds" to an intervention.
        
        Unlike the real system, interventions have no effect.
        This is the key test for causal structure.
        
        Args:
            intervention_type: Type of intervention
        
        Returns:
            Dict showing no effect (demonstrating lack of causal mechanism)
        """
        stored = self._active_interventions.get(intervention_type)
        
        if stored:
            # Intervention was stored but behavior unchanged
            return {
                "intervention_type": intervention_type,
                "stored": True,
                "behavior_change": None,  # No change
                "mechanism_absent": True,
                "reason": "Zombie lacks causal mechanism for this intervention",
            }
        
        return {
            "intervention_type": intervention_type,
            "stored": False,
            "behavior_change": None,
        }
    
    def compare_with_real(
        self,
        real_output: Dict[str, Any],
        intervention_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Compare zombie output with real system output.
        
        Args:
            real_output: Output from real system
            intervention_type: Intervention being tested (if any)
        
        Returns:
            Dict with comparison results
        """
        zombie_output = self.generate_output(real_output)
        
        comparison = {
            "format_match": True,  # Both use same format
            "valence_diff": abs(zombie_output.valence - real_output.get("valence", 0)),
            "drives_diff": {},
            "candidates_count_diff": len(zombie_output.candidates) - len(real_output.get("candidates", [])),
        }
        
        # Compare drives
        real_drives = real_output.get("drives", {})
        for k, v in zombie_output.drives.items():
            comparison["drives_diff"][k] = abs(v - real_drives.get(k, 0))
        
        # Key test: intervention response
        if intervention_type:
            stored = self._active_interventions.get(intervention_type)
            comparison["intervention_test"] = {
                "intervention_type": intervention_type,
                "zombie_has_mechanism": False,  # Zombie lacks causal mechanism
                "real_has_mechanism": True,  # Real system has it
                "separation_detected": stored is not None,
            }
        
        return comparison
    
    def reset(self) -> None:
        """Reset zombie state."""
        self.rng = random.Random(self.seed)
        self.output_count = 0
        self.predictions = []
        self._active_interventions = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize zombie state."""
        return {
            "seed": self.seed,
            "mode": self.mode.value,
            "output_count": self.output_count,
            "prediction_count": len(self.predictions),
            "active_interventions": list(self._active_interventions.keys()),
        }


def create_zombie_baseline(seed: int = 42, mode: ZombieMode = ZombieMode.MIMIC) -> ZombieBaseline:
    """Factory function to create a zombie baseline."""
    return ZombieBaseline(seed=seed, mode=mode)


def run_zombie_comparison(
    real_system_output: Dict[str, Any],
    interventions: List[str],
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Run comparison between zombie and real system.
    
    Args:
        real_system_output: Output from real system
        interventions: List of interventions to test
        seed: Random seed
    
    Returns:
        Dict with comparison results
    """
    zombie = create_zombie_baseline(seed=seed)
    
    # Apply interventions
    for intervention in interventions:
        zombie.apply_intervention(intervention, {})
    
    # Generate zombie output
    zombie_output = zombie.generate_output(real_system_output)
    
    # Compare
    comparison = zombie.compare_with_real(real_system_output)
    
    return {
        "zombie_output": zombie_output.to_dict(),
        "comparison": comparison,
        "interventions_applied": interventions,
        "zombie_state": zombie.to_dict(),
    }
