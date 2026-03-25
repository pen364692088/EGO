"""
MVP-10 T11: Valence Policy Module

Maps valence/drive state to policy parameters that influence behavior.
Chain: valence/drives → policy_params → scoring → focus → plan/action

Output parameters:
- risk_aversion: How risk-averse to be (higher = more cautious)
- exploration_temp: Temperature for exploration (higher = more random)
- plan_depth: How deep to plan (higher = more steps)
- reflect_threshold: Threshold for triggering reflection
"""
import time
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
import importlib.util
import os

# Import from legacy drives.py file (not drives/ directory)
_drives_spec = importlib.util.spec_from_file_location(
    "drives_legacy",
    os.path.join(os.path.dirname(__file__), "drives.py")
)
_drives_legacy = importlib.util.module_from_spec(_drives_spec)
_drives_spec.loader.exec_module(_drives_legacy)
DriveType = _drives_legacy.DriveType
Drives = _drives_legacy.Drives


@dataclass
class PolicyParams:
    """
    Policy parameters derived from valence and drives.
    
    These parameters influence how the agent makes decisions:
    - risk_aversion: 0.0 (risk-seeking) to 1.0 (risk-averse)
    - exploration_temp: 0.0 (greedy) to 1.0 (highly exploratory)
    - plan_depth: 1 (shallow) to 5 (deep planning)
    - reflect_threshold: 0.0 (always reflect) to 1.0 (rarely reflect)
    """
    risk_aversion: float = 0.5
    exploration_temp: float = 0.3
    plan_depth: int = 3
    reflect_threshold: float = 0.5
    ts: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_aversion": self.risk_aversion,
            "exploration_temp": self.exploration_temp,
            "plan_depth": self.plan_depth,
            "reflect_threshold": self.reflect_threshold,
            "ts": self.ts,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyParams":
        return cls(
            risk_aversion=data.get("risk_aversion", 0.5),
            exploration_temp=data.get("exploration_temp", 0.3),
            plan_depth=data.get("plan_depth", 3),
            reflect_threshold=data.get("reflect_threshold", 0.5),
            ts=data.get("ts", time.time()),
        )


class ValencePolicy:
    """
    Maps valence and drives to policy parameters.
    
    The policy parameters influence:
    1. How the agent scores candidates
    2. How much exploration vs exploitation
    3. How deeply to plan
    4. When to trigger reflection
    
    High valence → lower risk_aversion, lower exploration
    Low valence → higher risk_aversion, higher exploration
    
    Low competence drive → higher reflect_threshold
    Low safety drive → higher risk_aversion
    Low curiosity drive → lower exploration_temp
    """
    
    # Default parameter ranges
    RISK_AVERSION_RANGE = (0.2, 0.8)
    EXPLORATION_TEMP_RANGE = (0.1, 0.6)
    PLAN_DEPTH_RANGE = (1, 5)
    REFLECT_THRESHOLD_RANGE = (0.2, 0.8)
    
    def __init__(
        self,
        risk_range: Optional[tuple] = None,
        exploration_range: Optional[tuple] = None,
        depth_range: Optional[tuple] = None,
        reflect_range: Optional[tuple] = None,
    ):
        """
        Initialize ValencePolicy with optional custom ranges.
        
        Args:
            risk_range: (min, max) for risk_aversion
            exploration_range: (min, max) for exploration_temp
            depth_range: (min, max) for plan_depth
            reflect_range: (min, max) for reflect_threshold
        """
        self.risk_range = risk_range or self.RISK_AVERSION_RANGE
        self.exploration_range = exploration_range or self.EXPLORATION_TEMP_RANGE
        self.depth_range = depth_range or self.PLAN_DEPTH_RANGE
        self.reflect_range = reflect_range or self.REFLECT_THRESHOLD_RANGE
        
        # Cache last computed params
        self._last_params: Optional[PolicyParams] = None
        self._last_valence: Optional[float] = None
    
    def compute(
        self,
        valence: float,
        drives: Optional[Drives] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> PolicyParams:
        """
        Compute policy parameters from valence and drives.
        
        Args:
            valence: Current valence (-1.0 to 1.0)
            drives: Optional Drives instance for drive-aware policy
            context: Optional context (e.g., failure count, urgency)
        
        Returns:
            PolicyParams instance
        """
        context = context or {}
        
        # Normalize valence to [0, 1]
        v = (valence + 1.0) / 2.0  # 0 = very negative, 1 = very positive
        
        # Base values from valence
        # High valence → lower risk aversion (feeling confident)
        # Low valence → higher risk aversion (feeling threatened)
        base_risk = self._lerp(
            self.risk_range[1],  # High risk aversion at low valence
            self.risk_range[0],  # Low risk aversion at high valence
            v
        )
        
        # High valence → lower exploration (exploit)
        # Low valence → higher exploration (seek alternatives)
        base_exploration = self._lerp(
            self.exploration_range[1],  # High exploration at low valence
            self.exploration_range[0],  # Low exploration at high valence
            v
        )
        
        # High valence → deeper planning (feeling capable)
        # Low valence → shallower planning (feeling uncertain)
        base_depth = int(self._lerp(
            self.depth_range[0],
            self.depth_range[1],
            v
        ))
        
        # High valence → higher reflect threshold (less reflection)
        # Low valence → lower reflect threshold (more reflection)
        base_reflect = self._lerp(
            self.reflect_range[0],  # More reflection at low valence
            self.reflect_range[1],  # Less reflection at high valence
            v
        )
        
        # Apply drive modifiers if provided
        if drives:
            competence = drives.get_level(DriveType.COMPETENCE)
            safety = drives.get_level(DriveType.SAFETY)
            curiosity = drives.get_level(DriveType.CURIOSITY)
            
            # Low competence → more reflection
            if competence < 0.3:
                base_reflect *= 0.7  # Lower threshold = more reflection
            
            # Low safety → higher risk aversion
            if safety < 0.3:
                base_risk = min(self.risk_range[1], base_risk * 1.2)
            
            # Low curiosity → lower exploration
            if curiosity < 0.4:
                base_exploration *= 0.8
        
        # Apply context modifiers
        failure_count = context.get("failure_count", 0)
        if failure_count > 0:
            # Increase risk aversion and reflection after failures
            base_risk = min(self.risk_range[1], base_risk + 0.1 * failure_count)
            base_reflect = max(self.reflect_range[0], base_reflect - 0.1 * failure_count)
        
        urgency = context.get("urgency", 0.0)
        if urgency > 0.5:
            # High urgency → shallower planning
            base_depth = max(self.depth_range[0], base_depth - 1)
        
        # Clamp all values to their ranges
        risk_aversion = max(self.risk_range[0], min(self.risk_range[1], base_risk))
        exploration_temp = max(self.exploration_range[0], min(self.exploration_range[1], base_exploration))
        plan_depth = max(self.depth_range[0], min(self.depth_range[1], base_depth))
        reflect_threshold = max(self.reflect_range[0], min(self.reflect_range[1], base_reflect))
        
        params = PolicyParams(
            risk_aversion=round(risk_aversion, 3),
            exploration_temp=round(exploration_temp, 3),
            plan_depth=plan_depth,
            reflect_threshold=round(reflect_threshold, 3),
        )
        
        # Cache
        self._last_params = params
        self._last_valence = valence
        
        return params
    
    def _lerp(self, a: float, b: float, t: float) -> float:
        """Linear interpolation between a and b by t."""
        return a + (b - a) * t
    
    def get_last_params(self) -> Optional[PolicyParams]:
        """Get the last computed policy params."""
        return self._last_params
    
    def apply_to_scores(
        self,
        scores: Dict[str, float],
        params: Optional[PolicyParams] = None,
    ) -> Dict[str, float]:
        """
        Apply policy parameters to candidate scores.
        
        This is where exploration temperature affects scoring.
        
        Args:
            scores: Dict mapping candidate id to base score
            params: PolicyParams to apply (uses last computed if None)
        
        Returns:
            Dict of adjusted scores
        """
        params = params or self._last_params
        if params is None:
            return scores
        
        import math
        
        adjusted = {}
        for cid, score in scores.items():
            # Apply exploration temperature via softmax-like scaling
            # Higher temp → more uniform scores
            # Lower temp → more extreme differences
            temp = params.exploration_temp
            
            if temp < 0.01:
                # Very low temp → keep original scores
                adjusted[cid] = score
            else:
                # Scale scores towards mean based on temperature
                mean_score = sum(scores.values()) / len(scores)
                deviation = score - mean_score
                
                # Reduce deviation based on temperature
                # High temp (0.5) → deviation * 0.5
                # Low temp (0.1) → deviation * 0.9
                scale = 1.0 - temp
                adjusted[cid] = mean_score + deviation * scale
        
        return adjusted
    
    def should_reflect(
        self,
        trigger_score: float,
        params: Optional[PolicyParams] = None,
    ) -> bool:
        """
        Determine if reflection should be triggered.
        
        Args:
            trigger_score: Score that triggers reflection (e.g., prediction error)
            params: PolicyParams to use (uses last computed if None)
        
        Returns:
            True if reflection should be triggered
        """
        params = params or self._last_params
        if params is None:
            return trigger_score > 0.5
        
        # Lower threshold = more reflection
        return trigger_score > params.reflect_threshold
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize policy state to dict."""
        return {
            "risk_range": self.risk_range,
            "exploration_range": self.exploration_range,
            "depth_range": self.depth_range,
            "reflect_range": self.reflect_range,
            "last_params": self._last_params.to_dict() if self._last_params else None,
            "last_valence": self._last_valence,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValencePolicy":
        """Deserialize policy state from dict."""
        policy = cls(
            risk_range=tuple(data.get("risk_range", cls.RISK_AVERSION_RANGE)),
            exploration_range=tuple(data.get("exploration_range", cls.EXPLORATION_TEMP_RANGE)),
            depth_range=tuple(data.get("depth_range", cls.PLAN_DEPTH_RANGE)),
            reflect_range=tuple(data.get("reflect_range", cls.REFLECT_THRESHOLD_RANGE)),
        )
        
        if data.get("last_params"):
            policy._last_params = PolicyParams.from_dict(data["last_params"])
        policy._last_valence = data.get("last_valence")
        
        return policy


def compute_policy_chain(
    valence: float,
    drives: Drives,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Compute the full chain: valence/drives → policy_params.
    
    This is a convenience function that combines:
    1. Policy parameter computation
    2. Candidate score adjustment
    3. Reflection decision
    
    Args:
        valence: Current valence (-1.0 to 1.0)
        drives: Drives instance
        context: Optional context
    
    Returns:
        Dict with policy_params, adjusted_scores, and chain metadata
    """
    policy = ValencePolicy()
    params = policy.compute(valence, drives, context)
    
    # Generate candidates from drives
    candidates = drives.generate_candidates(context)
    
    # Get base scores
    base_scores = {c.id: c.score for c in candidates}
    
    # Apply policy to scores
    adjusted_scores = policy.apply_to_scores(base_scores, params)
    
    return {
        "valence": valence,
        "policy_params": params.to_dict(),
        "base_scores": base_scores,
        "adjusted_scores": adjusted_scores,
        "low_drives": [dt.value for dt in drives.get_low_drives()],
    }
