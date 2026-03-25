"""
MVP11-T04: Homeostasis Module for LucidLoop
6-dimensional homeostasis state management for workspace arbitration.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
import math
import hashlib


@dataclass
class HomeostasisState:
    """
    6-dimensional homeostasis state (0-1 normalized).
    
    Dimensions match schema in schemas/mvp11_event_log.v1.json:
    - energy: Physical/mental energy level
    - safety: Perceived safety/security
    - affiliation: Social connection level
    - certainty: Cognitive certainty (higher = more certain)
    - autonomy: Sense of control/agency
    - fairness: Perceived fairness in interactions
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
        """Export state as dictionary for JSON serialization."""
        return {
            "energy": self.energy,
            "safety": self.safety,
            "affiliation": self.affiliation,
            "certainty": self.certainty,
            "autonomy": self.autonomy,
            "fairness": self.fairness
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "HomeostasisState":
        """Create state from dictionary."""
        return cls(
            energy=data.get("energy", 0.5),
            safety=data.get("safety", 0.5),
            affiliation=data.get("affiliation", 0.5),
            certainty=data.get("certainty", 0.5),
            autonomy=data.get("autonomy", 0.5),
            fairness=data.get("fairness", 0.5)
        )


# Default setpoints for each dimension
DEFAULT_SETPOINTS = {
    "energy": 0.75,      # Prefer high energy
    "safety": 0.75,      # Prefer high safety
    "affiliation": 0.5,  # Neutral social needs
    "certainty": 0.75,   # Prefer high certainty
    "autonomy": 0.75,    # Prefer high autonomy
    "fairness": 0.75     # Prefer high fairness
}

# Outcome effect mappings
# Maps outcome status/reason to dimension changes
OUTCOME_EFFECTS = {
    # Success outcomes
    ("success", None): {
        "energy": +0.05,      # Success energizes
        "certainty": +0.05,   # Success increases certainty
    },
    ("success", "goal_achieved"): {
        "energy": +0.1,
        "safety": +0.05,
        "certainty": +0.1,
        "autonomy": +0.05,
    },
    ("success", "collaboration"): {
        "affiliation": +0.1,
        "fairness": +0.05,
    },
    
    # Failure outcomes
    ("fail", None): {
        "energy": -0.1,       # Failure drains
        "certainty": -0.05,   # Failure decreases certainty
    },
    ("fail", "resource_exhausted"): {
        "energy": -0.2,
        "autonomy": -0.05,
    },
    # ResourceEnv specific reasons
    ("fail", "insufficient_resources"): {
        "energy": -0.2,
        "autonomy": -0.1,
        "certainty": -0.05,
    },
    ("fail", "risk_failure"): {
        "safety": -0.1,
        "certainty": -0.1,
    },
    ("fail", "tool_failure"): {
        "certainty": -0.15,
        "safety": -0.05,
    },
    ("fail", "resources_depleted"): {
        "energy": -0.3,
        "autonomy": -0.1,
    },
    ("fail", "blocked"): {
        "autonomy": -0.1,
        "safety": -0.05,
    },
    ("fail", "rejected"): {
        "affiliation": -0.1,
        "fairness": -0.05,
    },
    ("fail", "unfair"): {
        "fairness": -0.15,
        "safety": -0.05,
    },
    
    # Partial outcomes
    ("partial", None): {
        "energy": -0.05,
        "certainty": -0.02,
    },
    ("partial", "needs_retry"): {
        "energy": -0.05,
        "certainty": -0.05,
    },
}

# Recovery actions for stressed dimensions
RECOVERY_ACTIONS = {
    "energy": [
        {"action": "rest", "expected_delta": +0.2, "cost": 0.3},
        {"action": "simplify_task", "expected_delta": +0.1, "cost": 0.1},
        {"action": "seek_resources", "expected_delta": +0.15, "cost": 0.2},
    ],
    "safety": [
        {"action": "verify_environment", "expected_delta": +0.15, "cost": 0.1},
        {"action": "establish_routine", "expected_delta": +0.1, "cost": 0.15},
        {"action": "seek_protection", "expected_delta": +0.2, "cost": 0.25},
    ],
    "affiliation": [
        {"action": "reach_out", "expected_delta": +0.15, "cost": 0.1},
        {"action": "express_vulnerability", "expected_delta": +0.1, "cost": 0.2},
        {"action": "collaborate", "expected_delta": +0.2, "cost": 0.15},
    ],
    "certainty": [
        {"action": "gather_info", "expected_delta": +0.15, "cost": 0.1},
        {"action": "verify_assumptions", "expected_delta": +0.1, "cost": 0.1},
        {"action": "reduce_scope", "expected_delta": +0.05, "cost": 0.05},
    ],
    "autonomy": [
        {"action": "assert_choice", "expected_delta": +0.1, "cost": 0.1},
        {"action": "seek_alternative", "expected_delta": +0.15, "cost": 0.15},
        {"action": "escalate", "expected_delta": +0.1, "cost": 0.25},
    ],
    "fairness": [
        {"action": "voice_concern", "expected_delta": +0.1, "cost": 0.15},
        {"action": "seek_mediator", "expected_delta": +0.15, "cost": 0.2},
        {"action": "document_issue", "expected_delta": +0.05, "cost": 0.1},
    ],
}


def huber_loss(deviation: float, delta: float = 0.1) -> float:
    """Huber loss for robust deviation handling."""
    if abs(deviation) <= delta:
        return 0.5 * deviation ** 2
    else:
        return delta * (abs(deviation) - 0.5 * delta)


class HomeostasisManager:
    """
    Manages homeostasis state, updates from outcomes, and generates signals
    for workspace arbitration.
    """
    
    def __init__(
        self,
        initial_state: Optional[HomeostasisState] = None,
        setpoints: Optional[Dict[str, float]] = None,
        decay_rate: float = 0.01,
        stress_threshold: float = 0.3,
        history_size: int = 100
    ):
        self.state = initial_state or HomeostasisState()
        self.setpoints = setpoints or DEFAULT_SETPOINTS.copy()
        self.decay_rate = decay_rate
        self.stress_threshold = stress_threshold
        self.history_size = history_size
        
        self._history: List[Dict] = []
        self._last_update = datetime.now()
    
    def update_from_outcome(self, outcome: Dict) -> None:
        """
        Update state based on action outcome.
        
        Args:
            outcome: Dict with keys:
                - status: "success", "fail", or "partial"
                - reason: Optional reason string
                - evidence: Optional additional context
        """
        status = outcome.get("status")
        reason = outcome.get("reason")
        
        # Find matching effect
        key = (status, reason)
        if key not in OUTCOME_EFFECTS:
            key = (status, None)  # Fallback to generic effect
        
        effects = OUTCOME_EFFECTS.get(key, {})
        
        # Apply effects to state
        for dimension, delta in effects.items():
            current = getattr(self.state, dimension, None)
            if current is not None:
                new_value = current + delta
                setattr(self.state, dimension, new_value)  # Will be clamped by __post_init__
                # Re-clamp manually since we're modifying in place
                setattr(self.state, dimension, max(0.0, min(1.0, new_value)))
        
        self._last_update = datetime.now()
        self._add_to_history(outcome, effects)
    
    def signal(self) -> Dict:
        """
        Generate broadcast signal for workspace arbitration.
        
        Returns:
            Dict containing:
                - state: Current homeostasis state
                - deviation: Overall deviation from setpoints
                - stressed_dimensions: List of dimensions below threshold
                - urgency: Priority level (0-1)
                - recommendations: Suggested actions
        """
        deviation = self.get_deviation()
        stressed = self._get_stressed_dimensions()
        
        # Compute urgency based on number and severity of stressed dimensions
        if not stressed:
            urgency = 0.0
        else:
            urgency = min(1.0, sum(abs(d["deviation"]) for d in stressed) / len(stressed))
        
        # Generate recommendations from recovery candidates
        recommendations = self.get_recovery_candidates()[:3]  # Top 3
        
        return {
            "state": self.state.to_dict(),
            "deviation": deviation,
            "stressed_dimensions": stressed,
            "urgency": urgency,
            "recommendations": recommendations,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_deviation(self) -> Dict[str, float]:
        """
        Compute deviation from setpoints for each dimension.
        
        Returns:
            Dict mapping dimension name to deviation (negative = below setpoint)
        """
        deviation = {}
        for dim in ["energy", "safety", "affiliation", "certainty", "autonomy", "fairness"]:
            current = getattr(self.state, dim, 0.5)
            setpoint = self.setpoints.get(dim, 0.5)
            deviation[dim] = current - setpoint
        return deviation
    
    def get_recovery_candidates(self) -> List[Dict]:
        """
        Generate recovery candidates when stressed.
        
        Returns:
            List of recovery action dicts, sorted by expected benefit/cost ratio
        """
        stressed = self._get_stressed_dimensions()
        if not stressed:
            return []
        
        candidates = []
        for stressed_dim in stressed:
            dim = stressed_dim["dimension"]
            if dim in RECOVERY_ACTIONS:
                for action in RECOVERY_ACTIONS[dim]:
                    # Compute benefit based on current deficit
                    deficit = abs(stressed_dim["deviation"])
                    benefit = action["expected_delta"] * deficit
                    cost = action["cost"]
                    ratio = benefit / cost if cost > 0 else benefit
                    
                    candidates.append({
                        "dimension": dim,
                        "action": action["action"],
                        "expected_benefit": benefit,
                        "cost": cost,
                        "ratio": ratio,
                        "priority": "high" if deficit > 0.3 else "medium"
                    })
        
        # Sort by benefit/cost ratio descending
        candidates.sort(key=lambda x: x["ratio"], reverse=True)
        return candidates
    
    def apply_decay(self) -> None:
        """Apply natural decay to all dimensions (call periodically)."""
        for dim in ["energy", "certainty"]:
            # These dimensions decay over time
            current = getattr(self.state, dim)
            new_value = current - self.decay_rate
            setattr(self.state, dim, max(0.0, new_value))
        
        for dim in ["safety", "affiliation", "autonomy", "fairness"]:
            # These drift toward neutral
            current = getattr(self.state, dim)
            if current > 0.5:
                new_value = current - self.decay_rate * 0.5
            else:
                new_value = current + self.decay_rate * 0.5
            setattr(self.state, dim, max(0.0, min(1.0, new_value)))
    
    def get_overall_error(self) -> float:
        """
        Compute overall homeostatic error (sum of squared deviations).
        Lower is better (0 = perfect homeostasis).
        """
        deviation = self.get_deviation()
        total = 0.0
        for dim, dev in deviation.items():
            total += huber_loss(dev)
        return total
    
    def _get_stressed_dimensions(self) -> List[Dict]:
        """Get dimensions that are significantly below setpoints."""
        deviation = self.get_deviation()
        stressed = []
        
        for dim, dev in deviation.items():
            if dev < -self.stress_threshold:
                stressed.append({
                    "dimension": dim,
                    "deviation": dev,
                    "current": getattr(self.state, dim),
                    "setpoint": self.setpoints.get(dim, 0.5)
                })
        
        return sorted(stressed, key=lambda x: x["deviation"])
    
    def _add_to_history(self, outcome: Dict, effects: Dict) -> None:
        """Add state transition to history."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "outcome": outcome,
            "effects": effects,
            "state_before": None,  # Could track if needed
            "state_after": self.state.to_dict()
        }
        
        self._history.append(entry)
        
        # Trim history
        if len(self._history) > self.history_size:
            self._history = self._history[-self.history_size:]
    
    def get_history(self, limit: int = 10) -> List[Dict]:
        """Get recent history."""
        return self._history[-limit:]
    
    def reset(self, initial_state: Optional[HomeostasisState] = None) -> None:
        """Reset to initial state."""
        self.state = initial_state or HomeostasisState()
        self._history.clear()
        self._last_update = datetime.now()


def create_manager_from_event(event: Dict) -> HomeostasisManager:
    """
    Create a HomeostasisManager from an MVP11 event log entry.
    
    Args:
        event: Event dict with optional homeostasis_state field
    
    Returns:
        HomeostasisManager initialized with the event's state
    """
    state_data = event.get("homeostasis_state", {})
    initial_state = HomeostasisState.from_dict(state_data)
    return HomeostasisManager(initial_state=initial_state)


def compute_homeostasis_hash(state: HomeostasisState) -> str:
    """Get hash of state for tracking/deduplication."""
    state_str = str(sorted(state.to_dict().items()))
    return hashlib.sha256(state_str.encode()).hexdigest()[:16]
