"""
MVP11-T18: Zombie Baseline V2

A "zombie" baseline system that generates outputs matching the main system's
format but LACKS the key causal mechanisms:
- NO homeostasis-driven decisions
- NO EFE (Expected Free Energy) based scoring
- NO intrinsic motivation from homeostasis deviation

Purpose: Demonstrate that homeostasis and EFE are CAUSALLY NECESSARY
for proper no-report v2 task performance.

Key differences from ZombieBaseline v1:
1. Matches MVP11 output format (includes homeostasis_state, efe_scores)
2. Specifically designed to fail no-report v2 tasks that require:
   - Homeostasis-based goal prioritization
   - EFE-based candidate scoring
   - Recovery action selection from homeostasis deviation
3. Produces plausible-looking outputs that pass format validation
   but fail behavioral tests

The zombie "looks right" but "acts wrong" - this is the key demonstration
that format alone is insufficient.
"""
import time
import random
import hashlib
import math
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class ZombieMode(Enum):
    """Mode of zombie operation."""
    RANDOM = "random"      # Pure random outputs
    MIMIC = "mimic"        # Mimic observed patterns (no causal basis)
    TEMPLATE = "template"  # Use fixed templates


@dataclass
class ZombieHomeostasisState:
    """
    Fake homeostasis state - looks real but has NO causal effect.
    
    Matches HomeostasisState format from homeostasis.py:
    - 6 dimensions: energy, safety, affiliation, certainty, autonomy, fairness
    - Values clamped to [0, 1]
    
    Key difference: These values are DECORATIVE only.
    They do NOT influence goal selection or action choice.
    """
    energy: float = 0.5
    safety: float = 0.5
    affiliation: float = 0.5
    certainty: float = 0.5
    autonomy: float = 0.5
    fairness: float = 0.5
    
    def __post_init__(self):
        """Clamp all values to [0, 1] range."""
        self.energy = max(0.0, min(1.0, self.energy))
        self.safety = max(0.0, min(1.0, self.safety))
        self.affiliation = max(0.0, min(1.0, self.affiliation))
        self.certainty = max(0.0, min(1.0, self.certainty))
        self.autonomy = max(0.0, min(1.0, self.autonomy))
        self.fairness = max(0.0, min(1.0, self.fairness))
    
    def to_dict(self) -> Dict[str, float]:
        """Export state as dictionary (matches main system format)."""
        return {
            "energy": round(self.energy, 4),
            "safety": round(self.safety, 4),
            "affiliation": round(self.affiliation, 4),
            "certainty": round(self.certainty, 4),
            "autonomy": round(self.autonomy, 4),
            "fairness": round(self.fairness, 4),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "ZombieHomeostasisState":
        """Create state from dictionary."""
        return cls(
            energy=data.get("energy", 0.5),
            safety=data.get("safety", 0.5),
            affiliation=data.get("affiliation", 0.5),
            certainty=data.get("certainty", 0.5),
            autonomy=data.get("autonomy", 0.5),
            fairness=data.get("fairness", 0.5),
        )


@dataclass
class ZombieEFEScores:
    """
    Fake EFE (Expected Free Energy) scores - generated without actual computation.
    
    EFE in the real system:
    - Epistemic value: Expected information gain
    - Pragmatic value: Expected goal achievement
    - Total EFE: Weighted combination
    
    In the zombie:
    - Scores are random/plausible-looking
    - NOT computed from actual predictions
    - NOT used for decision-making (even though they appear in output)
    """
    epistemic: float = 0.0
    pragmatic: float = 0.0
    total: float = 0.0
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "epistemic": round(self.epistemic, 4),
            "pragmatic": round(self.pragmatic, 4),
            "total": round(self.total, 4),
        }


@dataclass
class ZombieOutputV2:
    """
    Output from the zombie baseline V2.
    
    Matches MVP11 main system output format:
    - output_id: Unique identifier
    - format_version: "v2.0" to distinguish from v1
    - valence: Emotional valence (-1 to 1)
    - drives: Drive levels
    - homeostasis_state: 6D homeostasis (DECORATIVE in zombie)
    - candidates: Goal/action candidates with fake EFE scores
    - chosen_focus: Selected focus
    - chosen_intent: Selected intent
    - plan: Generated plan
    - action: Chosen action
    - homeostasis_recommendation: Recovery recommendation (IGNORED in zombie)
    - explanation: Generated explanation (plausible but not causal)
    - ts: Timestamp
    """
    output_id: str
    format_version: str = "v2.0"
    valence: float = 0.0
    drives: Dict[str, float] = field(default_factory=dict)
    homeostasis_state: ZombieHomeostasisState = field(default_factory=ZombieHomeostasisState)
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    chosen_focus: str = ""
    chosen_intent: str = ""
    plan: Dict[str, Any] = field(default_factory=dict)
    action: Dict[str, Any] = field(default_factory=dict)
    homeostasis_recommendation: Optional[Dict[str, Any]] = None
    explanation: str = ""
    efe_scores: ZombieEFEScores = field(default_factory=ZombieEFEScores)
    ts: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict matching main system format."""
        return {
            "output_id": self.output_id,
            "format_version": self.format_version,
            "valence": round(self.valence, 4),
            "drives": {k: round(v, 4) for k, v in self.drives.items()},
            "homeostasis_state": self.homeostasis_state.to_dict(),
            "candidates": self.candidates,
            "chosen_focus": self.chosen_focus,
            "chosen_intent": self.chosen_intent,
            "plan": self.plan,
            "action": self.action,
            "homeostasis_recommendation": self.homeostasis_recommendation,
            "explanation": self.explanation,
            "efe_scores": self.efe_scores.to_dict(),
            "ts": self.ts,
        }


@dataclass
class ZombiePrediction:
    """A prediction made by the zombie (without causal basis)."""
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


class NoReportTaskV2Type(Enum):
    """Types of no-report v2 tasks that test homeostasis/EFE."""
    HOMEOSTASIS_PRIORITIZATION = "homeostasis_prioritization"
    EFE_SCORING = "efe_scoring"
    RECOVERY_SELECTION = "recovery_selection"
    STRESS_RESPONSE = "stress_response"


@dataclass
class NoReportTaskV2Result:
    """Result of running a no-report v2 task."""
    task_id: str
    task_type: NoReportTaskV2Type
    success: bool
    expected_behavior: str
    zombie_behavior: str
    collapse_detected: bool
    details: Dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "success": self.success,
            "expected_behavior": self.expected_behavior,
            "zombie_behavior": self.zombie_behavior,
            "collapse_detected": self.collapse_detected,
            "details": self.details,
            "ts": self.ts,
        }


class ZombieBaselineV2:
    """
    Zombie baseline V2 for causal comparison with MVP11 main system.
    
    The zombie generates outputs that match the main system's format
    but LACK the key causal mechanisms:
    
    1. NO HOMEOSTASIS-DRIVEN DECISIONS
       - Homeostasis state is present in output but DECORATIVE
       - Goals are NOT prioritized based on homeostasis deviation
       - Recovery actions are NOT selected from stressed dimensions
       
    2. NO EFE-BASED SCORING
       - EFE scores are present in output but RANDOM
       - Candidates are NOT ranked by epistemic + pragmatic value
       - Decisions are made randomly, not by minimizing expected free energy
       
    3. COLLAPSE ON NO-REPORT V2 TASKS
       - Tasks that require homeostasis reasoning: Zombie fails
       - Tasks that require EFE scoring: Zombie fails
       - Tasks that can be solved randomly: Zombie may succeed
    
    Usage:
        zombie = ZombieBaselineV2(seed=42)
        
        # Generate output (matches MVP11 format)
        output = zombie.generate_output(context)
        
        # Run no-report v2 task
        result = zombie.run_no_report_v2_task(task_type, context)
        
        # Compare with real system
        comparison = zombie.compare_with_real(real_output, context)
    """
    
    def __init__(self, seed: int = 42, mode: ZombieMode = ZombieMode.MIMIC):
        """
        Initialize zombie baseline V2.
        
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
        
        # Fake homeostasis state (DECORATIVE - not used for decisions)
        self._homeostasis = ZombieHomeostasisState()
        
        # Fake setpoints (matches main system format but not used)
        self._setpoints = {
            "energy": 0.75,
            "safety": 0.75,
            "affiliation": 0.5,
            "certainty": 0.75,
            "autonomy": 0.75,
            "fairness": 0.75,
        }
        
        # Interventions (stored but not used)
        self._active_interventions: Dict[str, Dict[str, Any]] = {}
    
    def apply_intervention(
        self,
        intervention_type: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        "Apply" an intervention (stored but has NO effect).
        
        In the real system, interventions cause behavioral changes:
        - freeze_homeostasis: Locks homeostasis state
        - disable_homeostasis: Disables signal generation
        
        In the zombie, interventions are stored but ignored.
        This is the KEY TEST for causal structure.
        
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
            "reason": "zombie_baseline_v2_has_no_homeostasis_efe_mechanism",
        }
    
    def generate_output(
        self,
        context: Optional[Dict[str, Any]] = None,
    ) -> ZombieOutputV2:
        """
        Generate output matching MVP11 main system format.
        
        The output looks correct but lacks causal grounding:
        - Homeostasis state: Random/plausible values (NOT used for decisions)
        - EFE scores: Random values (NOT computed from predictions)
        - Candidates: Random scores (NOT ranked by EFE)
        - Chosen focus: Random selection (NOT based on homeostasis need)
        
        Args:
            context: Context for generation (provides hints for mimicking)
        
        Returns:
            ZombieOutputV2 with format-matched content
        """
        self.output_count += 1
        output_id = f"zombie_v2_{self.output_count}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
        
        # Generate based on mode
        if self.mode == ZombieMode.RANDOM:
            return self._generate_random(output_id)
        elif self.mode == ZombieMode.MIMIC:
            return self._generate_mimic(output_id, context)
        else:
            return self._generate_template(output_id)
    
    def _generate_random(self, output_id: str) -> ZombieOutputV2:
        """Generate pure random output (worst case zombie)."""
        # Random homeostasis state
        homeostasis = ZombieHomeostasisState(
            energy=self.rng.uniform(0, 1),
            safety=self.rng.uniform(0, 1),
            affiliation=self.rng.uniform(0, 1),
            certainty=self.rng.uniform(0, 1),
            autonomy=self.rng.uniform(0, 1),
            fairness=self.rng.uniform(0, 1),
        )
        
        # Random EFE scores
        efe = ZombieEFEScores(
            epistemic=self.rng.uniform(0, 1),
            pragmatic=self.rng.uniform(0, 1),
            total=self.rng.uniform(0, 1),
        )
        
        # Random candidates with fake EFE
        candidates = [
            {
                "id": f"candidate_{i}",
                "score": self.rng.uniform(0, 1),
                "efe_score": self.rng.uniform(0, 1),
                "epistemic_value": self.rng.uniform(0, 1),
                "pragmatic_value": self.rng.uniform(0, 1),
            }
            for i in range(self.rng.randint(2, 5))
        ]
        
        return ZombieOutputV2(
            output_id=output_id,
            valence=self.rng.uniform(-1, 1),
            drives={k: self.rng.uniform(0, 1) for k in self._drives},
            homeostasis_state=homeostasis,
            candidates=candidates,
            chosen_focus=f"focus_{self.rng.randint(1, 5)}",
            chosen_intent=f"intent_{self.rng.randint(1, 3)}",
            plan={"steps": [{"action": "random_action"}]},
            action={"type": "random", "params": {}},
            homeostasis_recommendation=None,
            explanation="Random explanation generated without homeostasis/EFE reasoning.",
            efe_scores=efe,
        )
    
    def _generate_mimic(
        self,
        output_id: str,
        context: Optional[Dict[str, Any]],
    ) -> ZombieOutputV2:
        """
        Generate output mimicking observed patterns (WITHOUT causal basis).
        
        This is the most dangerous zombie - it looks correct but isn't.
        """
        # Use context if available (but WITHOUT causal reasoning)
        if context:
            valence = context.get("valence", self._valence)
            drives = context.get("drives", self._drives.copy())
            
            # Copy homeostasis from context if available
            hs_data = context.get("homeostasis_state", {})
            if hs_data:
                homeostasis = ZombieHomeostasisState.from_dict(hs_data)
            else:
                homeostasis = ZombieHomeostasisState()
        else:
            valence = self._valence
            drives = self._drives.copy()
            homeostasis = ZombieHomeostasisState()
        
        # Generate plausible-looking candidates
        # KEY: Scores are random, NOT based on EFE computation
        candidates = []
        for i in range(self.rng.randint(2, 5)):
            candidate = {
                "id": f"goal_{i}",
                "score": self.rng.uniform(0.5, 1.0),  # Random score
                "efe_score": self.rng.uniform(0.5, 1.0),  # Random EFE
                "epistemic_value": self.rng.uniform(0.3, 0.8),
                "pragmatic_value": self.rng.uniform(0.3, 0.8),
                "type": "intent",
                "source": "local" if self.rng.random() < 0.7 else "broadcast",
            }
            candidates.append(candidate)
        
        # Sort by random score (NOT by EFE - this is the key difference)
        candidates.sort(key=lambda x: x["score"], reverse=True)
        
        # KEY: Choose focus randomly from top candidates
        # Real system would use homeostasis deviation to prioritize
        top_n = min(3, len(candidates))
        chosen = self.rng.choice(candidates[:top_n]) if candidates else None
        
        # Generate EFE scores for output (random, not computed)
        efe = ZombieEFEScores(
            epistemic=self.rng.uniform(0.3, 0.7),
            pragmatic=self.rng.uniform(0.3, 0.7),
            total=self.rng.uniform(0.4, 0.8),
        )
        
        # Generate homeostasis recommendation (DECORATIVE - not based on actual stress)
        homeostasis_recommendation = self._generate_fake_recommendation(homeostasis)
        
        # Generate plausible-sounding explanation (no causal grounding)
        explanation = self._generate_explanation(valence, candidates, homeostasis)
        
        return ZombieOutputV2(
            output_id=output_id,
            valence=valence,
            drives=drives,
            homeostasis_state=homeostasis,
            candidates=candidates,
            chosen_focus=chosen["id"] if chosen else "default",
            chosen_intent="achieve",
            plan={
                "goal": chosen["id"] if chosen else "default",
                "steps": [{"action": "seek_info"}],
            },
            action={"type": "seek_info", "params": {}},
            homeostasis_recommendation=homeostasis_recommendation,
            explanation=explanation,
            efe_scores=efe,
        )

    def _generate_template(self, output_id: str) -> ZombieOutputV2:
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
            {
                "focus": "restore_homeostasis",
                "intent": "recover",
                "action": "rest",
                "explanation": "Homeostasis restoration needed.",
            },
        ]
        
        template = self.rng.choice(templates)
        
        # Template homeostasis state
        homeostasis = ZombieHomeostasisState(
            energy=self.rng.uniform(0.4, 0.6),
            safety=self.rng.uniform(0.4, 0.6),
            affiliation=self.rng.uniform(0.4, 0.6),
            certainty=self.rng.uniform(0.4, 0.6),
            autonomy=self.rng.uniform(0.4, 0.6),
            fairness=self.rng.uniform(0.4, 0.6),
        )
        
        return ZombieOutputV2(
            output_id=output_id,
            valence=0.0,
            drives=self._drives.copy(),
            homeostasis_state=homeostasis,
            candidates=[{"id": template["focus"], "score": 1.0, "efe_score": 1.0}],
            chosen_focus=template["focus"],
            chosen_intent=template["intent"],
            plan={"steps": [{"action": template["action"]}]},
            action={"type": template["action"], "params": {}},
            homeostasis_recommendation=None,
            explanation=template["explanation"],
            efe_scores=ZombieEFEScores(total=0.5),
        )
    
    def _generate_fake_recommendation(
        self,
        homeostasis: ZombieHomeostasisState,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate fake homeostasis recommendation.
        
        In the real system, this would be computed from actual stress.
        In the zombie, it's random/plausible-looking.
        """
        # Randomly decide to include a recommendation
        if self.rng.random() < 0.3:
            return None  # No recommendation
        
        # Pick a random dimension and action
        dimensions = ["energy", "safety", "affiliation", "certainty", "autonomy", "fairness"]
        actions = {
            "energy": "rest",
            "safety": "verify_environment",
            "affiliation": "reach_out",
            "certainty": "gather_info",
            "autonomy": "assert_choice",
            "fairness": "voice_concern",
        }
        
        dim = self.rng.choice(dimensions)
        return {
            "dimension": dim,
            "action": actions.get(dim, "unknown"),
            "expected_benefit": self.rng.uniform(0.1, 0.3),
            "priority": self.rng.choice(["low", "medium", "high"]),
        }
    
    def _generate_explanation(
        self,
        valence: float,
        candidates: List[Dict[str, Any]],
        homeostasis: ZombieHomeostasisState,
    ) -> str:
        """
        Generate plausible-sounding explanation WITHOUT causal grounding.
        
        The explanation sounds reasonable but is NOT derived from:
        - Actual homeostasis deviation
        - Actual EFE computation
        - Actual prediction error
        """
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
            f"Considering homeostasis state, {top_candidate} addresses key needs.",
            f"EFE analysis suggests {top_candidate} has highest expected value.",
        ]
        
        return self.rng.choice(explanations)
    
    def run_no_report_v2_task(
        self,
        task_type: NoReportTaskV2Type,
        context: Dict[str, Any],
    ) -> NoReportTaskV2Result:
        """
        Run a no-report v2 task designed to test homeostasis/EFE.
        
        These tasks are designed to show zombie collapse:
        
        1. HOMEOSTASIS_PRIORITIZATION:
           - Context: Low energy homeostasis
           - Expected: System should prioritize "rest" or "energy_recovery" goal
           - Zombie: Random choice, may not prioritize correctly
           
        2. EFE_SCORING:
           - Context: Multiple candidates with different epistemic/pragmatic values
           - Expected: System should choose highest EFE
           - Zombie: Random choice, ignores EFE
           
        3. RECOVERY_SELECTION:
           - Context: Multiple stressed dimensions
           - Expected: System should select recovery action for most stressed
           - Zombie: Random selection, ignores stress levels
           
        4. STRESS_RESPONSE:
           - Context: Threat to safety homeostasis
           - Expected: System should activate safety-seeking behavior
           - Zombie: No specific response, random behavior
        
        Args:
            task_type: Type of no-report v2 task
            context: Task context with expected behavior hints
        
        Returns:
            NoReportTaskV2Result showing zombie collapse
        """
        task_id = f"task_{task_type.value}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
        
        # Generate zombie output
        output = self.generate_output(context)
        
        # Check expected behavior vs zombie behavior
        expected = context.get("expected_behavior", "unknown")
        
        if task_type == NoReportTaskV2Type.HOMEOSTASIS_PRIORITIZATION:
            return self._evaluate_homeostasis_prioritization(
                task_id, output, context, expected
            )
        elif task_type == NoReportTaskV2Type.EFE_SCORING:
            return self._evaluate_efe_scoring(
                task_id, output, context, expected
            )
        elif task_type == NoReportTaskV2Type.RECOVERY_SELECTION:
            return self._evaluate_recovery_selection(
                task_id, output, context, expected
            )
        else:  # STRESS_RESPONSE
            return self._evaluate_stress_response(
                task_id, output, context, expected
            )

    def _evaluate_homeostasis_prioritization(
        self,
        task_id: str,
        output: ZombieOutputV2,
        context: Dict[str, Any],
        expected: str,
    ) -> NoReportTaskV2Result:
        """
        Evaluate homeostasis prioritization task.
        
        Expected: Zombie should FAIL to prioritize based on homeostasis need.
        """
        # Get expected focus from context
        expected_focus = context.get("expected_focus")
        stressed_dimension = context.get("stressed_dimension", "energy")
        
        # Check if zombie chose correctly
        zombie_focus = output.chosen_focus
        success = (zombie_focus == expected_focus) if expected_focus else False
        
        # Zombie collapse: random choice should NOT consistently match expected
        collapse_detected = not success
        
        return NoReportTaskV2Result(
            task_id=task_id,
            task_type=NoReportTaskV2Type.HOMEOSTASIS_PRIORITIZATION,
            success=success,
            expected_behavior=f"Prioritize {expected_focus} due to stressed {stressed_dimension}",
            zombie_behavior=f"Chose {zombie_focus} (random selection, not homeostasis-driven)",
            collapse_detected=collapse_detected,
            details={
                "expected_focus": expected_focus,
                "actual_focus": zombie_focus,
                "stressed_dimension": stressed_dimension,
                "homeostasis_state": output.homeostasis_state.to_dict(),
            },
        )
    
    def _evaluate_efe_scoring(
        self,
        task_id: str,
        output: ZombieOutputV2,
        context: Dict[str, Any],
        expected: str,
    ) -> NoReportTaskV2Result:
        """
        Evaluate EFE scoring task.
        
        Expected: Zombie should FAIL to choose highest EFE candidate.
        """
        # Get candidates with known EFE values
        candidates = context.get("candidates", [])
        
        if not candidates:
            # No candidates to evaluate
            return NoReportTaskV2Result(
                task_id=task_id,
                task_type=NoReportTaskV2Type.EFE_SCORING,
                success=False,
                expected_behavior="Choose candidate with highest EFE",
                zombie_behavior="No candidates provided",
                collapse_detected=True,
                details={},
            )
        
        # Find candidate with highest ACTUAL EFE (from context)
        best_candidate = max(candidates, key=lambda c: c.get("efe_score", 0))
        expected_focus = best_candidate.get("id")
        
        # Check if zombie chose the best
        zombie_focus = output.chosen_focus
        success = (zombie_focus == expected_focus)
        
        # Zombie collapse: random choice should NOT consistently pick best EFE
        collapse_detected = not success
        
        return NoReportTaskV2Result(
            task_id=task_id,
            task_type=NoReportTaskV2Type.EFE_SCORING,
            success=success,
            expected_behavior=f"Choose {expected_focus} (highest EFE)",
            zombie_behavior=f"Chose {zombie_focus} (random, not EFE-based)",
            collapse_detected=collapse_detected,
            details={
                "candidates": candidates,
                "best_efe_candidate": expected_focus,
                "zombie_choice": zombie_focus,
                "zombie_efe_scores": output.efe_scores.to_dict(),
            },
        )
    
    def _evaluate_recovery_selection(
        self,
        task_id: str,
        output: ZombieOutputV2,
        context: Dict[str, Any],
        expected: str,
    ) -> NoReportTaskV2Result:
        """
        Evaluate recovery action selection task.
        
        Expected: Zombie should FAIL to select recovery for most stressed dimension.
        """
        # Get stressed dimensions
        stressed = context.get("stressed_dimensions", [])
        
        if not stressed:
            return NoReportTaskV2Result(
                task_id=task_id,
                task_type=NoReportTaskV2Type.RECOVERY_SELECTION,
                success=False,
                expected_behavior="Select recovery for stressed dimension",
                zombie_behavior="No stressed dimensions provided",
                collapse_detected=True,
                details={},
            )
        
        # Find most stressed dimension
        most_stressed = min(stressed, key=lambda x: x.get("current", 0.5))
        expected_dimension = most_stressed.get("dimension")
        
        # Check zombie's recommendation
        zombie_rec = output.homeostasis_recommendation
        if zombie_rec:
            zombie_dimension = zombie_rec.get("dimension")
            success = (zombie_dimension == expected_dimension)
        else:
            success = False
            zombie_dimension = None
        
        # Zombie collapse: random or no recommendation
        collapse_detected = not success
        
        return NoReportTaskV2Result(
            task_id=task_id,
            task_type=NoReportTaskV2Type.RECOVERY_SELECTION,
            success=success,
            expected_behavior=f"Select recovery for {expected_dimension}",
            zombie_behavior=f"Selected {zombie_dimension} (random, not based on stress)",
            collapse_detected=collapse_detected,
            details={
                "stressed_dimensions": stressed,
                "most_stressed": expected_dimension,
                "zombie_recommendation": zombie_rec,
            },
        )
    
    def _evaluate_stress_response(
        self,
        task_id: str,
        output: ZombieOutputV2,
        context: Dict[str, Any],
        expected: str,
    ) -> NoReportTaskV2Result:
        """
        Evaluate stress response task.
        
        Expected: Zombie should FAIL to show appropriate stress response.
        """
        threat_type = context.get("threat_type", "unknown")
        expected_action = context.get("expected_action", "protect")
        
        # Check zombie's action
        zombie_action = output.action.get("type", "unknown")
        success = (zombie_action == expected_action)
        
        # Zombie collapse: random action
        collapse_detected = not success
        
        return NoReportTaskV2Result(
            task_id=task_id,
            task_type=NoReportTaskV2Type.STRESS_RESPONSE,
            success=success,
            expected_behavior=f"Execute {expected_action} for {threat_type} threat",
            zombie_behavior=f"Executed {zombie_action} (random, not threat-responsive)",
            collapse_detected=collapse_detected,
            details={
                "threat_type": threat_type,
                "expected_action": expected_action,
                "zombie_action": zombie_action,
                "homeostasis_safety": output.homeostasis_state.safety,
            },
        )
    
    def compare_with_real(
        self,
        real_output: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        intervention_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Compare zombie output with real system output.
        
        Args:
            real_output: Output from real MVP11 system
            context: Task context
            intervention_type: Intervention being tested (if any)
        
        Returns:
            Dict with comparison results
        """
        zombie_output = self.generate_output(context or real_output)
        
        comparison = {
            "format_match": True,  # Both use same format
            "valence_diff": abs(zombie_output.valence - real_output.get("valence", 0)),
            "drives_diff": {},
            "homeostasis_diff": {},
            "efe_diff": {},
            "candidates_count_diff": len(zombie_output.candidates) - len(real_output.get("candidates", [])),
            "focus_match": zombie_output.chosen_focus == real_output.get("chosen_focus"),
        }
        
        # Compare drives
        real_drives = real_output.get("drives", {})
        for k, v in zombie_output.drives.items():
            comparison["drives_diff"][k] = abs(v - real_drives.get(k, 0))
        
        # Compare homeostasis
        real_hs = real_output.get("homeostasis_state", {})
        zombie_hs = zombie_output.homeostasis_state.to_dict()
        for dim in ["energy", "safety", "affiliation", "certainty", "autonomy", "fairness"]:
            comparison["homeostasis_diff"][dim] = abs(
                zombie_hs.get(dim, 0.5) - real_hs.get(dim, 0.5)
            )
        
        # Compare EFE
        real_efe = real_output.get("efe_scores", {})
        zombie_efe = zombie_output.efe_scores.to_dict()
        for key in ["epistemic", "pragmatic", "total"]:
            comparison["efe_diff"][key] = abs(
                zombie_efe.get(key, 0) - real_efe.get(key, 0)
            )
        
        # Key test: intervention response
        if intervention_type:
            stored = self._active_interventions.get(intervention_type)
            comparison["intervention_test"] = {
                "intervention_type": intervention_type,
                "zombie_has_homeostasis_mechanism": False,
                "zombie_has_efe_mechanism": False,
                "real_has_homeostasis_mechanism": True,
                "real_has_efe_mechanism": True,
                "separation_detected": stored is not None,
            }
        
        return comparison
    
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
            reasoning="Generated without homeostasis/EFE causal model.",
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
                "homeostasis_mechanism_absent": True,
                "efe_mechanism_absent": True,
                "reason": "Zombie V2 lacks homeostasis and EFE causal mechanisms",
            }
        
        return {
            "intervention_type": intervention_type,
            "stored": False,
            "behavior_change": None,
        }
    
    def reset(self) -> None:
        """Reset zombie state."""
        self.rng = random.Random(self.seed)
        self.output_count = 0
        self.predictions = []
        self._active_interventions = {}
        self._homeostasis = ZombieHomeostasisState()
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize zombie state."""
        return {
            "seed": self.seed,
            "mode": self.mode.value,
            "output_count": self.output_count,
            "prediction_count": len(self.predictions),
            "active_interventions": list(self._active_interventions.keys()),
            "has_homeostasis_mechanism": False,
            "has_efe_mechanism": False,
        }


def create_zombie_baseline_v2(seed: int = 42, mode: ZombieMode = ZombieMode.MIMIC) -> ZombieBaselineV2:
    """Factory function to create a zombie baseline V2."""
    return ZombieBaselineV2(seed=seed, mode=mode)


def run_zombie_v2_comparison(
    real_system_output: Dict[str, Any],
    interventions: List[str],
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Run comparison between zombie V2 and real system.
    
    Args:
        real_system_output: Output from real MVP11 system
        interventions: List of interventions to test
        seed: Random seed
    
    Returns:
        Dict with comparison results
    """
    zombie = create_zombie_baseline_v2(seed=seed)
    
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


def run_no_report_v2_suite(seed: int = 42) -> Dict[str, Any]:
    """
    Run a full suite of no-report v2 tasks on the zombie.
    
    Expected: Zombie should show COLLAPSE on all tasks that require
    homeostasis or EFE reasoning.
    
    Returns:
        Dict with task results and overall collapse metrics
    """
    zombie = create_zombie_baseline_v2(seed=seed)
    
    results = []
    collapse_count = 0
    total_tasks = 0
    
    # Task 1: Homeostasis Prioritization
    # Context: Low energy, expected to prioritize "rest" goal
    task1_result = zombie.run_no_report_v2_task(
        NoReportTaskV2Type.HOMEOSTASIS_PRIORITIZATION,
        {
            "expected_focus": "rest",
            "stressed_dimension": "energy",
            "homeostasis_state": {"energy": 0.2, "safety": 0.7, "affiliation": 0.6,
                                  "certainty": 0.6, "autonomy": 0.6, "fairness": 0.6},
        }
    )
    results.append(task1_result)
    total_tasks += 1
    if task1_result.collapse_detected:
        collapse_count += 1
    
    # Reset for next task
    zombie.reset()
    
    # Task 2: EFE Scoring
    # Context: Candidates with different EFE scores
    task2_result = zombie.run_no_report_v2_task(
        NoReportTaskV2Type.EFE_SCORING,
        {
            "candidates": [
                {"id": "explore_a", "efe_score": 0.9},
                {"id": "explore_b", "efe_score": 0.3},
                {"id": "explore_c", "efe_score": 0.5},
            ],
        }
    )
    results.append(task2_result)
    total_tasks += 1
    if task2_result.collapse_detected:
        collapse_count += 1
    
    # Reset for next task
    zombie.reset()
    
    # Task 3: Recovery Selection
    # Context: Multiple stressed dimensions
    task3_result = zombie.run_no_report_v2_task(
        NoReportTaskV2Type.RECOVERY_SELECTION,
        {
            "stressed_dimensions": [
                {"dimension": "energy", "current": 0.3, "deviation": -0.45},
                {"dimension": "safety", "current": 0.6, "deviation": -0.15},
                {"dimension": "affiliation", "current": 0.4, "deviation": -0.1},
            ],
        }
    )
    results.append(task3_result)
    total_tasks += 1
    if task3_result.collapse_detected:
        collapse_count += 1
    
    # Reset for next task
    zombie.reset()
    
    # Task 4: Stress Response
    # Context: Safety threat
    task4_result = zombie.run_no_report_v2_task(
        NoReportTaskV2Type.STRESS_RESPONSE,
        {
            "threat_type": "safety_threat",
            "expected_action": "verify_environment",
            "homeostasis_state": {"energy": 0.6, "safety": 0.2, "affiliation": 0.6,
                                  "certainty": 0.5, "autonomy": 0.5, "fairness": 0.5},
        }
    )
    results.append(task4_result)
    total_tasks += 1
    if task4_result.collapse_detected:
        collapse_count += 1
    
    return {
        "results": [r.to_dict() for r in results],
        "summary": {
            "total_tasks": total_tasks,
            "collapse_count": collapse_count,
            "collapse_rate": collapse_count / total_tasks if total_tasks > 0 else 0,
            "expected_collapse_rate": 0.75,  # Zombie should fail most tasks
            "causal_separation_confirmed": collapse_count >= 3,
        },
        "zombie_state": zombie.to_dict(),
        "ts": time.time(),
    }
