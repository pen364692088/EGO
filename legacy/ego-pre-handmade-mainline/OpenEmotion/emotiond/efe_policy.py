"""
MVP11-T07: EFE (Expected Free Energy) Policy Module

Computes Expected Free Energy terms for action selection and policy modulation.
EFE = risk * risk_weight + ambiguity * ambiguity_weight - info_gain * info_gain_weight + cost * cost_weight

Integration with homeostasis:
- Low safety → higher risk_weight (more risk-averse)
- Low certainty → higher info_gain_weight (seek more information)
- Low energy → higher cost_weight (conserve resources)
"""
import time
import os
import random
import math
import ast
from typing import Any, Dict, Optional
from dataclasses import dataclass, field

from .homeostasis import HomeostasisState
from .cycle_prior import load_cycle_memory, evaluate_cycle_prior


def _env_flag(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "on"}


DEFAULT_CYCLE_PRIOR_ENABLED = _env_flag("CYCLE_PRIOR_ENABLED", False)
DEFAULT_CYCLE_MEMORY_PATH = os.getenv("CYCLE_MEMORY_PATH", "artifacts/mvp11/cycle_memory.json")


@dataclass
class EFETerms:
    """
    Expected Free Energy terms (0-1 normalized).
    
    These terms represent different aspects of action evaluation:
    - risk: Potential negative outcome (higher = more risky)
    - ambiguity: Uncertainty in outcome prediction (higher = more ambiguous)
    - info_gain: Information seeking value (higher = more informative)
    - cost: Resource expenditure required (higher = more costly)
    """
    risk: float = 0.5
    ambiguity: float = 0.5
    info_gain: float = 0.5
    cost: float = 0.5
    ts: float = field(default_factory=time.time)
    
    def __post_init__(self):
        """Clamp all values to [0, 1] range."""
        self.risk = max(0.0, min(1.0, self.risk))
        self.ambiguity = max(0.0, min(1.0, self.ambiguity))
        self.info_gain = max(0.0, min(1.0, self.info_gain))
        self.cost = max(0.0, min(1.0, self.cost))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk": self.risk,
            "ambiguity": self.ambiguity,
            "info_gain": self.info_gain,
            "cost": self.cost,
            "ts": self.ts,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EFETerms":
        return cls(
            risk=data.get("risk", 0.5),
            ambiguity=data.get("ambiguity", 0.5),
            info_gain=data.get("info_gain", 0.5),
            cost=data.get("cost", 0.5),
            ts=data.get("ts", time.time()),
        )
    
    def compute_efe(self, weights: Dict[str, float]) -> float:
        """
        Compute Expected Free Energy value.
        
        EFE = risk * risk_weight + ambiguity * ambiguity_weight 
              - info_gain * info_gain_weight + cost * cost_weight
        
        Lower EFE = better action (less risk/cost, more info_gain)
        
        Args:
            weights: Dict with risk_weight, ambiguity_weight, info_gain_weight, cost_weight
        
        Returns:
            EFE value (can be negative due to info_gain subtraction)
        """
        risk_weight = weights.get("risk_weight", 1.0)
        ambiguity_weight = weights.get("ambiguity_weight", 1.0)
        info_gain_weight = weights.get("info_gain_weight", 1.0)
        cost_weight = weights.get("cost_weight", 1.0)
        
        return (
            self.risk * risk_weight +
            self.ambiguity * ambiguity_weight -
            self.info_gain * info_gain_weight +
            self.cost * cost_weight
        )



def _build_cycle_prior_trace(prior_applied: bool, bias_strength: float, matched_signatures: list) -> Optional[Dict[str, Any]]:
    """Build MVP11.4 compliant cycle_prior_trace for replay determinism."""
    if not prior_applied:
        return None
    return {
        "version": "mvp11.4.v1",
        "bias_strength": float(bias_strength or 0.0),
        "matched_signatures_topK": list(matched_signatures or []),
    }

class EFEPolicy:
    """
    EFE Policy Module for computing Expected Free Energy and policy parameters.
    
    Integrates with homeostasis state to modulate weights:
    - Low safety → higher risk_weight (more risk-averse)
    - Low certainty → higher info_gain_weight (seek more information)
    - Low energy → higher cost_weight (conserve resources)
    
    This module is part of the LucidLoop architecture for affective computing.
    """
    
    # Default weight ranges
    RISK_WEIGHT_RANGE = (0.5, 2.0)
    AMBIGUITY_WEIGHT_RANGE = (0.5, 1.5)
    INFO_GAIN_WEIGHT_RANGE = (0.5, 2.0)
    COST_WEIGHT_RANGE = (0.5, 2.0)
    PRECISION_RANGE = (0.1, 1.0)
    
    # Homeostasis thresholds for weight modulation
    SAFETY_THRESHOLD = 0.4  # Below this, increase risk_weight
    CERTAINTY_THRESHOLD = 0.4  # Below this, increase info_gain_weight
    ENERGY_THRESHOLD = 0.4  # Below this, increase cost_weight
    RNG_STATE_VERSION = "py_random_v1"
    
    def __init__(
        self,
        risk_weight_range: Optional[tuple] = None,
        ambiguity_weight_range: Optional[tuple] = None,
        info_gain_weight_range: Optional[tuple] = None,
        cost_weight_range: Optional[tuple] = None,
        precision_range: Optional[tuple] = None,
        seed: Optional[int] = None,
        rng: Optional[random.Random] = None,
        cycle_prior_enabled: Optional[bool] = None,
        cycle_memory_path: Optional[str] = None,
    ):
        """
        Initialize EFEPolicy with optional custom ranges.
        
        Args:
            risk_weight_range: (min, max) for risk_weight
            ambiguity_weight_range: (min, max) for ambiguity_weight
            info_gain_weight_range: (min, max) for info_gain_weight
            cost_weight_range: (min, max) for cost_weight
            precision_range: (min, max) for precision
        """
        self.risk_weight_range = risk_weight_range or self.RISK_WEIGHT_RANGE
        self.ambiguity_weight_range = ambiguity_weight_range or self.AMBIGUITY_WEIGHT_RANGE
        self.info_gain_weight_range = info_gain_weight_range or self.INFO_GAIN_WEIGHT_RANGE
        self.cost_weight_range = cost_weight_range or self.COST_WEIGHT_RANGE
        self.precision_range = precision_range or self.PRECISION_RANGE

        # RNG (replay/science mode)
        self._seed = seed
        self.rng = rng if rng is not None else random.Random(seed)

        self.cycle_prior_enabled = DEFAULT_CYCLE_PRIOR_ENABLED if cycle_prior_enabled is None else bool(cycle_prior_enabled)
        self.cycle_memory_path = cycle_memory_path or DEFAULT_CYCLE_MEMORY_PATH
        self._cycle_memory_cache: Optional[list] = None
        self._last_rank_trace: Optional[list] = None

        # Cache last computed values
        self._last_efe_terms: Optional[EFETerms] = None
        self._last_policy_params: Optional[Dict[str, float]] = None
        self._last_selection_trace: Optional[Dict[str, Any]] = None
    
    def compute_efe(
        self,
        candidate: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        homeostasis: Optional[HomeostasisState] = None,
    ) -> EFETerms:
        """
        Compute EFE terms for a candidate action.
        
        Args:
            candidate: Dict describing the candidate action with keys:
                - risk: Inherent risk level (0-1)
                - ambiguity: Uncertainty in prediction (0-1)
                - info_gain: Information value (0-1)
                - cost: Resource cost (0-1)
            context: Optional context (e.g., urgency, constraints)
            homeostasis: Optional homeostasis state for weight modulation
        
        Returns:
            EFETerms instance with computed values
        """
        context = context or {}
        
        # Extract base values from candidate
        risk = float(candidate.get("risk", 0.5))
        ambiguity = float(candidate.get("ambiguity", 0.5))
        info_gain = float(candidate.get("info_gain", 0.5))
        cost = float(candidate.get("cost", 0.5))
        
        # Apply context modifiers
        urgency = context.get("urgency", 0.0)
        if urgency > 0.7:
            # High urgency: reduce perceived risk (time pressure)
            risk *= 0.8
        
        constraints = context.get("constraints", [])
        if "risk_averse" in constraints:
            risk *= 1.2
        if "low_budget" in constraints:
            cost *= 1.3
        
        # Apply homeostasis modulation to terms
        if homeostasis:
            # Low safety increases perceived risk
            if homeostasis.safety < self.SAFETY_THRESHOLD:
                risk *= 1.0 + (self.SAFETY_THRESHOLD - homeostasis.safety) * 0.5
            
            # Low certainty increases perceived ambiguity
            if homeostasis.certainty < self.CERTAINTY_THRESHOLD:
                ambiguity *= 1.0 + (self.CERTAINTY_THRESHOLD - homeostasis.certainty) * 0.3
            
            # Low energy increases perceived cost
            if homeostasis.energy < self.ENERGY_THRESHOLD:
                cost *= 1.0 + (self.ENERGY_THRESHOLD - homeostasis.energy) * 0.5
        
        # Clamp to [0, 1]
        risk = max(0.0, min(1.0, risk))
        ambiguity = max(0.0, min(1.0, ambiguity))
        info_gain = max(0.0, min(1.0, info_gain))
        cost = max(0.0, min(1.0, cost))
        
        terms = EFETerms(
            risk=round(risk, 3),
            ambiguity=round(ambiguity, 3),
            info_gain=round(info_gain, 3),
            cost=round(cost, 3),
        )
        
        self._last_efe_terms = terms
        return terms
    
    def compute_policy_params(
        self,
        efe_terms: Optional[EFETerms] = None,
        homeostasis: Optional[HomeostasisState] = None,
    ) -> Dict[str, float]:
        """
        Compute policy parameters from EFE terms and homeostasis state.
        
        The weights modulate how each EFE term contributes to action selection:
        - risk_weight: Higher = more risk-averse
        - info_gain_weight: Higher = more exploration-seeking
        - cost_weight: Higher = more resource-conservative
        - precision: Confidence in action selection (inverse temperature)
        
        Args:
            efe_terms: EFETerms instance (uses last computed if None)
            homeostasis: Homeostasis state for weight modulation
        
        Returns:
            Dict with risk_weight, ambiguity_weight, info_gain_weight, cost_weight, precision
        """
        efe_terms = efe_terms or self._last_efe_terms
        if efe_terms is None:
            efe_terms = EFETerms()
        
        # Default weights (neutral)
        risk_weight = 1.0
        ambiguity_weight = 1.0
        info_gain_weight = 1.0
        cost_weight = 1.0
        precision = 0.5
        
        # Modulate weights based on homeostasis
        if homeostasis:
            # Low safety → higher risk_weight (more risk-averse)
            if homeostasis.safety < self.SAFETY_THRESHOLD:
                deficit = self.SAFETY_THRESHOLD - homeostasis.safety
                risk_weight = self._lerp(
                    self.risk_weight_range[0],
                    self.risk_weight_range[1],
                    deficit / self.SAFETY_THRESHOLD
                )
            
            # Low certainty → higher info_gain_weight (seek more information)
            if homeostasis.certainty < self.CERTAINTY_THRESHOLD:
                deficit = self.CERTAINTY_THRESHOLD - homeostasis.certainty
                info_gain_weight = self._lerp(
                    self.info_gain_weight_range[0],
                    self.info_gain_weight_range[1],
                    deficit / self.CERTAINTY_THRESHOLD
                )
            
            # Low energy → higher cost_weight (conserve resources)
            if homeostasis.energy < self.ENERGY_THRESHOLD:
                deficit = self.ENERGY_THRESHOLD - homeostasis.energy
                cost_weight = self._lerp(
                    self.cost_weight_range[0],
                    self.cost_weight_range[1],
                    deficit / self.ENERGY_THRESHOLD
                )
            
            # Precision based on overall homeostatic state
            # Better state → higher precision (more confident selection)
            overall_state = (
                homeostasis.energy +
                homeostasis.safety +
                homeostasis.certainty +
                homeostasis.autonomy
            ) / 4.0
            precision = self._lerp(
                self.precision_range[0],
                self.precision_range[1],
                overall_state
            )
        
        # Adjust weights based on EFE terms themselves
        # High risk → increase risk_weight
        if efe_terms.risk > 0.7:
            risk_weight *= 1.2
        
        # High ambiguity → increase ambiguity_weight
        if efe_terms.ambiguity > 0.7:
            ambiguity_weight *= 1.1
        
        # High info_gain → increase info_gain_weight (amplify exploration)
        if efe_terms.info_gain > 0.7:
            info_gain_weight *= 1.15
        
        # High cost → increase cost_weight (avoid expensive actions)
        if efe_terms.cost > 0.7:
            cost_weight *= 1.25
        
        # Clamp weights to ranges
        risk_weight = max(self.risk_weight_range[0], min(self.risk_weight_range[1], risk_weight))
        ambiguity_weight = max(self.ambiguity_weight_range[0], min(self.ambiguity_weight_range[1], ambiguity_weight))
        info_gain_weight = max(self.info_gain_weight_range[0], min(self.info_gain_weight_range[1], info_gain_weight))
        cost_weight = max(self.cost_weight_range[0], min(self.cost_weight_range[1], cost_weight))
        precision = max(self.precision_range[0], min(self.precision_range[1], precision))
        
        params = {
            "risk_weight": round(risk_weight, 3),
            "ambiguity_weight": round(ambiguity_weight, 3),
            "info_gain_weight": round(info_gain_weight, 3),
            "cost_weight": round(cost_weight, 3),
            "precision": round(precision, 3),
        }
        
        self._last_policy_params = params
        return params
    
    def _prior_enabled_for_context(self, context: Optional[Dict[str, Any]]) -> bool:
        if self.cycle_prior_enabled:
            return True
        ctx = context or {}
        manager = ctx.get("intervention_manager") if isinstance(ctx, dict) else None
        if manager is None:
            return False
        fn = getattr(manager, "is_cycle_prior_enabled", None)
        if callable(fn):
            try:
                return bool(fn())
            except Exception:
                return False
        return False

    def compute_full_efe(
        self,
        candidate: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        homeostasis: Optional[HomeostasisState] = None,
    ) -> float:
        """
        Compute the full EFE value for a candidate action.
        
        Combines compute_efe and compute_policy_params to get the final EFE score.
        Lower EFE = better action.
        
        Args:
            candidate: Dict describing the candidate action
            context: Optional context
            homeostasis: Optional homeostasis state
        
        Returns:
            EFE value (can be negative due to info_gain subtraction)
        """
        terms = self.compute_efe(candidate, context, homeostasis)
        params = self.compute_policy_params(terms, homeostasis)
        return terms.compute_efe(params)
    
    def rank_candidates(
        self,
        candidates: list,
        context: Optional[Dict[str, Any]] = None,
        homeostasis: Optional[HomeostasisState] = None,
    ) -> list:
        """
        Rank candidates by EFE value (lower = better).
        
        Args:
            candidates: List of candidate dicts
            context: Optional context
            homeostasis: Optional homeostasis state
        
        Returns:
            List of (candidate, efe_value) tuples, sorted by EFE ascending
        """
        ranked = []
        rank_trace = []
        cycle_items = []
        prior_enabled = self._prior_enabled_for_context(context)
        if prior_enabled:
            try:
                if self._cycle_memory_cache is None:
                    self._cycle_memory_cache = load_cycle_memory(self.cycle_memory_path)
                cycle_items = list(self._cycle_memory_cache or [])
            except Exception:
                cycle_items = []

        for candidate in candidates:
            base_efe = self.compute_full_efe(candidate, context, homeostasis)
            prior_trace = None
            adjusted_efe = base_efe

            if prior_enabled and cycle_items:
                ctx = dict(context or {})
                if isinstance(candidate, dict):
                    ctx.update(candidate)
                prior_trace = evaluate_cycle_prior(ctx, cycle_items, homeostasis, top_k=3)
                adjusted_efe = base_efe - float(prior_trace.get("bias_strength", 0.0) or 0.0)

            ranked.append((candidate, adjusted_efe))
            row = {
                "candidate": candidate,
                "efe_base": base_efe,
                "efe_adjusted": adjusted_efe,
            }
            if prior_trace is not None:
                row.update(prior_trace)
            rank_trace.append(row)
        
        # Sort by EFE ascending (lower = better)
        ranked.sort(key=lambda x: x[1])
        rank_trace.sort(key=lambda x: x["efe_adjusted"])
        self._last_rank_trace = rank_trace
        return ranked
    
    def select_action(
        self,
        candidates: list,
        context: Optional[Dict[str, Any]] = None,
        homeostasis: Optional[HomeostasisState] = None,
        stochastic: bool = True,
    ) -> tuple:
        """
        Select the best action from candidates using EFE.
        
        Args:
            candidates: List of candidate dicts
            context: Optional context
            homeostasis: Optional homeostasis state
            stochastic: If True, use softmax selection; else argmax
        
        Returns:
            (selected_candidate, efe_value, all_rankings)
        """
        ranked = self.rank_candidates(candidates, context, homeostasis)
        
        if not ranked:
            return None, None, ranked
        
        if not stochastic:
            # Deterministic: select lowest EFE
            selected_candidate, selected_efe = ranked[0]
            self._last_selection_trace = {
                "stochastic": False,
                "selected_idx": 0,
                "temperature": None,
                "probs": [1.0] + [0.0] * max(0, len(ranked) - 1),
                "sample_r": None,
                "selected_efe": selected_efe,
            }
            if self._last_rank_trace:
                top = self._last_rank_trace[0]
                if "cycle_prior_applied" in top:
                    prior_applied = bool(top.get("cycle_prior_applied"))
                    bias = float(top.get("bias_strength", 0.0) or 0.0)
                    sigs = top.get("matched_signatures_topK") or []
                    self._last_selection_trace["cycle_prior_applied"] = prior_applied
                    self._last_selection_trace["matched_signatures_topK"] = sigs
                    self._last_selection_trace["bias_strength"] = bias
                    # MVP11.4: nested trace for replay determinism
                    self._last_selection_trace["cycle_prior_trace"] = _build_cycle_prior_trace(
                        prior_applied, bias, sigs
                    )
            return selected_candidate, selected_efe, ranked
        
        # Stochastic: softmax over negative EFE (higher prob for lower EFE)
        
        # Get precision for temperature
        params = self._last_policy_params or self.compute_policy_params(homeostasis=homeostasis)
        precision = params.get("precision", 0.5)
        temperature = 1.0 / max(0.01, precision)  # Higher precision = lower temp
        
        # Compute softmax probabilities
        exp_scores = [math.exp(-efe / temperature) for _, efe in ranked]
        total = sum(exp_scores)
        probs = [s / total for s in exp_scores]
        
        # Sample (instance RNG for replayability)
        r = self.rng.random()
        cumulative = 0.0
        selected_idx = 0
        for i, p in enumerate(probs):
            cumulative += p
            if r <= cumulative:
                selected_idx = i
                break
        
        selected_candidate, selected_efe = ranked[selected_idx]
        self._last_selection_trace = {
            "stochastic": True,
            "temperature": temperature,
            "probs": probs,
            "sample_r": r,
            "selected_idx": selected_idx,
            "selected_efe": selected_efe,
        }
        if self._last_rank_trace and 0 <= selected_idx < len(self._last_rank_trace):
            chosen = self._last_rank_trace[selected_idx]
            if "cycle_prior_applied" in chosen:
                prior_applied = bool(chosen.get("cycle_prior_applied"))
                bias = float(chosen.get("bias_strength", 0.0) or 0.0)
                sigs = chosen.get("matched_signatures_topK") or []
                self._last_selection_trace["cycle_prior_applied"] = prior_applied
                self._last_selection_trace["matched_signatures_topK"] = sigs
                self._last_selection_trace["bias_strength"] = bias
                # MVP11.4: nested trace for replay determinism
                self._last_selection_trace["cycle_prior_trace"] = _build_cycle_prior_trace(
                    prior_applied, bias, sigs
                )
        return selected_candidate, selected_efe, ranked
    
    def _lerp(self, a: float, b: float, t: float) -> float:
        """Linear interpolation between a and b by t."""
        t = max(0.0, min(1.0, t))  # Clamp t to [0, 1]
        return a + (b - a) * t
    
    def get_last_efe_terms(self) -> Optional[EFETerms]:
        """Get the last computed EFE terms."""
        return self._last_efe_terms
    
    def get_last_policy_params(self) -> Optional[Dict[str, float]]:
        """Get the last computed policy params."""
        return self._last_policy_params

    def get_last_selection_trace(self) -> Optional[Dict[str, Any]]:
        """Get stochastic selection trace for replay/debug."""
        return self._last_selection_trace

    def _serialize_rng_state(self) -> str:
        """Serialize RNG internal state for exact continuation after restore."""
        return repr(self.rng.getstate())

    def _restore_rng_state(self, state_repr: Optional[str]) -> None:
        """Restore RNG state from serialized repr string."""
        if not state_repr:
            return
        self.rng.setstate(ast.literal_eval(state_repr))
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize policy state to dict."""
        return {
            "risk_weight_range": self.risk_weight_range,
            "ambiguity_weight_range": self.ambiguity_weight_range,
            "info_gain_weight_range": self.info_gain_weight_range,
            "cost_weight_range": self.cost_weight_range,
            "precision_range": self.precision_range,
            "seed": self._seed,
            "cycle_prior_enabled": self.cycle_prior_enabled,
            "cycle_memory_path": self.cycle_memory_path,
            "rng_state_version": self.RNG_STATE_VERSION,
            "rng_state": self._serialize_rng_state(),
            "last_efe_terms": self._last_efe_terms.to_dict() if self._last_efe_terms else None,
            "last_policy_params": self._last_policy_params,
            "last_selection_trace": self._last_selection_trace,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EFEPolicy":
        """Deserialize policy state from dict."""
        policy = cls(
            risk_weight_range=tuple(data.get("risk_weight_range", cls.RISK_WEIGHT_RANGE)),
            ambiguity_weight_range=tuple(data.get("ambiguity_weight_range", cls.AMBIGUITY_WEIGHT_RANGE)),
            info_gain_weight_range=tuple(data.get("info_gain_weight_range", cls.INFO_GAIN_WEIGHT_RANGE)),
            cost_weight_range=tuple(data.get("cost_weight_range", cls.COST_WEIGHT_RANGE)),
            precision_range=tuple(data.get("precision_range", cls.PRECISION_RANGE)),
            seed=data.get("seed"),
            cycle_prior_enabled=bool(data.get("cycle_prior_enabled", DEFAULT_CYCLE_PRIOR_ENABLED)),
            cycle_memory_path=data.get("cycle_memory_path", DEFAULT_CYCLE_MEMORY_PATH),
        )
        
        if data.get("last_efe_terms"):
            policy._last_efe_terms = EFETerms.from_dict(data["last_efe_terms"])
        policy._last_policy_params = data.get("last_policy_params")
        policy._last_selection_trace = data.get("last_selection_trace")
        if data.get("rng_state_version") == cls.RNG_STATE_VERSION:
            policy._restore_rng_state(data.get("rng_state"))
        
        return policy


def compute_efe_chain(
    candidate: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
    homeostasis: Optional[HomeostasisState] = None,
) -> Dict[str, Any]:
    """
    Compute the full EFE chain: candidate → EFE terms → policy params → EFE value.
    
    This is a convenience function that combines all EFE computations.
    
    Args:
        candidate: Dict describing the candidate action
        context: Optional context
        homeostasis: Optional homeostasis state
    
    Returns:
        Dict with efe_terms, policy_params, efe_value, and metadata
    """
    policy = EFEPolicy()
    terms = policy.compute_efe(candidate, context, homeostasis)
    params = policy.compute_policy_params(terms, homeostasis)
    efe_value = terms.compute_efe(params)
    
    return {
        "efe_terms": terms.to_dict(),
        "policy_params": params,
        "efe_value": efe_value,
        "homeostasis_modulated": homeostasis is not None,
        "ts": time.time(),
    }
