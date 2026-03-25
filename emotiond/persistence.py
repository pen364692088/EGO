"""
MVP-6.2 D4: Persistence Constraint (Self-Maintenance Objective)

Survival-style objective that treats self-maintenance as a hard constraint,
not just a slogan. Integrates with decision-making to balance persistence
against risk/ambiguity (information gain).

Three constraint categories:
1. Body Stability: Avoid chronic low energy, high safety_stress, focus_fatigue collapse
2. Relationship Assets: High bond targets → more cautious about harm; more sensitive to repair
3. Long-term Learning: Avoid stagnation from sustained low information gain

Key principles:
- Persistence does NOT override all goals; must trade off with risk/ambiguity
- All decisions traceable: explain why conservative/repair/retreat was chosen
- Telemetry for: collapse events, recovery half-life, strategy shifts under stress
"""
import time
import math
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum


class PersistenceStrategy(Enum):
    """Strategy choices driven by persistence constraints."""
    NORMAL = "normal"           # No persistence pressure
    CONSERVATIVE = "conservative"  # Cautious due to body/relationship stress
    REPAIR = "repair"           # Prioritize relationship repair
    RETREAT = "retreat"         # Withdraw to preserve resources
    MAINTENANCE = "maintenance"  # Focus on self-recovery


@dataclass
class PersistenceDecisionTrace:
    """Explainability payload for persistence strategy decisions."""
    strategy: str
    reason: str
    persistence_pressure: float
    risk: float
    ambiguity: float
    expected_info_gain: float
    tradeoff_score: float
    dominant_drivers: List[str] = field(default_factory=list)
    conservative_trigger: Optional[str] = None
    repair_trigger: Optional[str] = None
    retreat_trigger: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy,
            "reason": self.reason,
            "persistence_pressure": round(self.persistence_pressure, 4),
            "risk": round(self.risk, 4),
            "ambiguity": round(self.ambiguity, 4),
            "expected_info_gain": round(self.expected_info_gain, 4),
            "tradeoff_score": round(self.tradeoff_score, 4),
            "dominant_drivers": self.dominant_drivers,
            "conservative_trigger": self.conservative_trigger,
            "repair_trigger": self.repair_trigger,
            "retreat_trigger": self.retreat_trigger,
        }


@dataclass
class PersistenceCost:
    """
    Cost of an action from persistence perspective.
    
    Lower cost = more aligned with self-maintenance.
    """
    body_cost: float = 0.0      # Impact on body stability [0, 1]
    relationship_cost: float = 0.0  # Impact on relationship assets [0, 1]
    learning_cost: float = 0.0  # Impact on learning/stagnation [0, 1]
    
    def total_cost(self, weights: Optional[Dict[str, float]] = None) -> float:
        """Compute weighted total cost."""
        if weights is None:
            weights = {"body": 0.4, "relationship": 0.35, "learning": 0.25}
        return (
            self.body_cost * weights.get("body", 0.4) +
            self.relationship_cost * weights.get("relationship", 0.35) +
            self.learning_cost * weights.get("learning", 0.25)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "body_cost": round(self.body_cost, 4),
            "relationship_cost": round(self.relationship_cost, 4),
            "learning_cost": round(self.learning_cost, 4),
            "total": round(self.total_cost(), 4),
        }


@dataclass
class BodyStabilityMetrics:
    """
    Body stability tracking for persistence constraint.
    
    Tracks:
    - Chronic low energy episodes
    - Safety stress spikes
    - Focus fatigue collapse events
    """
    energy_low_threshold: float = 0.3
    safety_stress_high_threshold: float = 0.7
    focus_fatigue_high_threshold: float = 0.8
    
    # Episode tracking
    energy_low_episodes: int = 0
    safety_stress_spikes: int = 0
    focus_fatigue_collapses: int = 0
    
    # Current episode state
    in_energy_low_episode: bool = False
    in_safety_stress_spike: bool = False
    in_focus_collapse: bool = False
    
    # Episode start times
    energy_low_since: Optional[float] = None
    safety_stress_since: Optional[float] = None
    focus_collapse_since: Optional[float] = None
    
    # Recovery tracking - tracks end of ANY episode type
    last_episode_end_time: Optional[float] = None
    last_collapse_end_time: Optional[float] = None  # Alias for compatibility
    recovery_half_life_seconds: float = 300.0  # 5 min default
    
    def update(self, energy: float, safety_stress: float, focus_fatigue: float) -> Dict[str, Any]:
        """
        Update metrics with current body state.
        
        Returns:
            Dict with events triggered this update
        """
        events = {"new_episodes": [], "ended_episodes": []}
        now = time.time()
        was_in_any_episode = self.is_in_collapse()
        
        # Energy low tracking
        if energy < self.energy_low_threshold:
            if not self.in_energy_low_episode:
                self.in_energy_low_episode = True
                self.energy_low_since = now
                self.energy_low_episodes += 1
                events["new_episodes"].append("energy_low")
        else:
            if self.in_energy_low_episode:
                self.in_energy_low_episode = False
                self.energy_low_since = None
                events["ended_episodes"].append("energy_low")
        
        # Safety stress tracking
        if safety_stress > self.safety_stress_high_threshold:
            if not self.in_safety_stress_spike:
                self.in_safety_stress_spike = True
                self.safety_stress_since = now
                self.safety_stress_spikes += 1
                events["new_episodes"].append("safety_stress_spike")
        else:
            if self.in_safety_stress_spike:
                self.in_safety_stress_spike = False
                self.safety_stress_since = None
                events["ended_episodes"].append("safety_stress_spike")
        
        # Focus fatigue collapse tracking
        if focus_fatigue > self.focus_fatigue_high_threshold:
            if not self.in_focus_collapse:
                self.in_focus_collapse = True
                self.focus_collapse_since = now
                self.focus_fatigue_collapses += 1
                events["new_episodes"].append("focus_collapse")
        else:
            if self.in_focus_collapse:
                self.in_focus_collapse = False
                self.focus_collapse_since = None
                events["ended_episodes"].append("focus_collapse")
        
        # Track recovery time if any episode ended
        is_in_any_episode = self.is_in_collapse()
        if was_in_any_episode and not is_in_any_episode:
            self.last_episode_end_time = now
            self.last_collapse_end_time = now
        
        return events
    
    def get_stability_score(self) -> float:
        """
        Compute overall body stability score [0, 1].
        
        1.0 = perfectly stable, 0.0 = critical instability
        """
        score = 1.0
        
        # Penalize active episodes
        if self.in_energy_low_episode:
            score -= 0.2
        if self.in_safety_stress_spike:
            score -= 0.25
        if self.in_focus_collapse:
            score -= 0.35
        
        # Penalize history (diminishing returns)
        score -= min(0.2, self.energy_low_episodes * 0.02)
        score -= min(0.15, self.safety_stress_spikes * 0.015)
        score -= min(0.2, self.focus_fatigue_collapses * 0.03)
        
        return max(0.0, score)
    
    def is_in_collapse(self) -> bool:
        """Check if currently in any collapse state."""
        return self.in_energy_low_episode or self.in_safety_stress_spike or self.in_focus_collapse
    
    def time_since_last_collapse(self) -> Optional[float]:
        """Time in seconds since last collapse ended."""
        if self.last_episode_end_time is None:
            return None
        return time.time() - self.last_episode_end_time
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "energy_low_episodes": self.energy_low_episodes,
            "safety_stress_spikes": self.safety_stress_spikes,
            "focus_fatigue_collapses": self.focus_fatigue_collapses,
            "in_energy_low_episode": self.in_energy_low_episode,
            "in_safety_stress_spike": self.in_safety_stress_spike,
            "in_focus_collapse": self.in_focus_collapse,
            "stability_score": round(self.get_stability_score(), 4),
            "is_in_collapse": self.is_in_collapse(),
        }


@dataclass
class RelationshipAssetMetrics:
    """
    Relationship asset tracking for persistence constraint.
    
    Tracks:
    - Target bonds (high bond = more cautious about harm)
    - Repair sensitivity (high bond = more sensitive to repair opportunities)
    - Harm history per target
    """
    # Per-target tracking
    target_bonds: Dict[str, float] = field(default_factory=dict)
    target_reliability: Dict[str, float] = field(default_factory=dict)
    target_trust: Dict[str, float] = field(default_factory=dict)
    
    # Event tracking
    harm_events: Dict[str, int] = field(default_factory=dict)
    repair_attempts: Dict[str, int] = field(default_factory=dict)
    repair_successes: Dict[str, int] = field(default_factory=dict)
    
    # Thresholds
    high_bond_threshold: float = 0.7
    medium_bond_threshold: float = 0.4
    
    def update_target(self, target_id: str, bond: Optional[float] = None,
                      reliability: Optional[float] = None, trust: Optional[float] = None):
        """Update relationship metrics for a target."""
        if bond is not None:
            self.target_bonds[target_id] = bond
        if reliability is not None:
            self.target_reliability[target_id] = reliability
        if trust is not None:
            self.target_trust[target_id] = trust
    
    def update_bond(self, target_id: str, bond_value: float):
        """Update bond value for a target."""
        self.target_bonds[target_id] = bond_value
    
    def update_reliability(self, target_id: str, reliability: float):
        """Update reliability estimate for a target."""
        self.target_reliability[target_id] = reliability
    
    def get_bond(self, target_id: str) -> float:
        """Get bond level for a target (0 if unknown)."""
        return self.target_bonds.get(target_id, 0.0)
    
    def get_bond_level(self, target_id: str) -> str:
        """Get bond level category for a target."""
        bond = self.target_bonds.get(target_id, 0.0)
        if bond >= self.high_bond_threshold:
            return "high"
        elif bond >= self.medium_bond_threshold:
            return "medium"
        return "low"
    
    def is_high_bond(self, target_id: str) -> bool:
        """Check if target has high bond."""
        return self.get_bond(target_id) >= self.high_bond_threshold
    
    def record_harm(self, target_id: str):
        """Record a harm event toward a target."""
        self.harm_events[target_id] = self.harm_events.get(target_id, 0) + 1
    
    def record_repair(self, target_id: str, success: bool = True):
        """Record a repair attempt toward a target."""
        self.repair_attempts[target_id] = self.repair_attempts.get(target_id, 0) + 1
        if success:
            self.repair_successes[target_id] = self.repair_successes.get(target_id, 0) + 1
    
    def record_repair_attempt(self, target_id: str, success: bool = True):
        """Alias for record_repair."""
        self.record_repair(target_id, success)
    
    def get_repair_success_rate(self, target_id: str) -> float:
        """Get repair success rate for a target."""
        attempts = self.repair_attempts.get(target_id, 0)
        if attempts == 0:
            return 0.0
        return self.repair_successes.get(target_id, 0) / attempts
    
    def get_harm_avoidance_weight(self, target_id: str) -> float:
        """Get weight for avoiding harm to a target (higher = more avoid)."""
        bond = self.get_bond(target_id)
        return bond * 0.8  # Max 0.8 weight
    
    def get_repair_sensitivity(self, target_id: str) -> float:
        """Get repair sensitivity for a target (higher = more sensitive)."""
        bond = self.target_bonds.get(target_id, 0.0)
        # Base sensitivity scales with bond
        base = 0.3 + (bond * 0.5)
        # Bonus if we've harmed them before
        harm_count = self.harm_events.get(target_id, 0)
        harm_bonus = min(0.2, harm_count * 0.05)
        return min(1.0, base + harm_bonus)
    
    def get_asset_value(self, target_id: str) -> float:
        """Get overall asset value for a target."""
        bond = self.target_bonds.get(target_id, 0.0)
        reliability = self.target_reliability.get(target_id, 0.5)
        harm = self.harm_events.get(target_id, 0)
        # Asset value = bond * reliability - harm_penalty
        return max(0.0, bond * reliability - harm * 0.1)
    
    def should_prioritize_repair(self, target_id: str) -> Tuple[bool, str]:
        """
        Determine if repair should be prioritized for a target.
        
        Returns:
            (should_repair, reason)
        """
        bond = self.get_bond(target_id)
        harm = self.harm_events.get(target_id, 0)
        
        if bond >= self.high_bond_threshold and harm > 0:
            return True, f"high_bond({bond:.2f}) with harm({harm})"
        
        if harm >= 2:
            return True, f"repeated_harm({harm})"
        
        return False, "no_repair_needed"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_count": len(self.target_bonds),
            "high_bond_targets": sum(1 for b in self.target_bonds.values() if b >= self.high_bond_threshold),
            "total_harm_events": sum(self.harm_events.values()),
            "total_repair_attempts": sum(self.repair_attempts.values()),
        }


@dataclass
class LearningMetrics:
    """
    Long-term learning metrics for persistence constraint.
    
    Tracks:
    - Information gain over time
    - Stagnation detection (sustained low info gain)
    """
    info_gain_window: List[float] = field(default_factory=list)
    window_size: int = 100
    stagnation_threshold: float = 0.1
    burst_threshold: float = 0.5
    last_learning_burst: Optional[float] = None
    
    def record_info_gain(self, info_gain: float):
        """Record an information gain value."""
        self.info_gain_window.append(info_gain)
        if len(self.info_gain_window) > self.window_size:
            self.info_gain_window.pop(0)
        # Track learning burst
        if info_gain >= self.burst_threshold:
            self.last_learning_burst = time.time()
    
    def add_info_gain(self, info_gain: float):
        """Alias for record_info_gain."""
        self.record_info_gain(info_gain)
    
    def get_average_info_gain(self, last_n: Optional[int] = None) -> float:
        """Get average info gain over window (or last N)."""
        if not self.info_gain_window:
            return 0.0
        
        window = self.info_gain_window
        if last_n is not None:
            window = window[-last_n:]
        
        return sum(window) / len(window)
    
    def is_stagnating(self, window_size: int = 20) -> Tuple[bool, float]:
        """
        Check if system is stagnating (low info gain).
        
        Returns:
            (is_stagnating, avg_info_gain)
        """
        # Use minimum of window_size and available data
        available = len(self.info_gain_window)
        if available == 0:
            return False, 0.0
        
        use_window = min(window_size, available)
        avg = self.get_average_info_gain(use_window)
        
        # Only declare stagnation if we have enough samples
        if available < 5:
            return False, avg
        
        return avg < self.stagnation_threshold, avg
    
    def check_stagnation(self) -> bool:
        """Check and return stagnation status."""
        is_stag, _ = self.is_stagnating()
        return is_stag
    
    @property
    def is_stagnant(self) -> bool:
        """Property for stagnation status."""
        return self.check_stagnation()
    
    def get_learning_score(self) -> float:
        """Get overall learning score [0, 1]."""
        is_stag, avg = self.is_stagnating()
        if is_stag:
            return 0.3
        if avg > 0.5:
            return 1.0
        return 0.3 + (avg / 0.5) * 0.7
    
    def detect_learning_burst(self, threshold: float = 0.7) -> bool:
        """Detect if recent learning burst occurred."""
        if len(self.info_gain_window) < 5:
            return False
        recent_avg = sum(self.info_gain_window[-5:]) / 5
        return recent_avg > threshold
    
    def to_dict(self) -> Dict[str, Any]:
        is_stag, avg = self.is_stagnating()
        return {
            "window_size": len(self.info_gain_window),
            "average_info_gain": round(avg, 4),
            "is_stagnating": is_stag,
            "learning_score": round(self.get_learning_score(), 4),
        }


class PersistenceConstraint:
    """
    Main persistence constraint system.
    
    Integrates body stability, relationship assets, and learning metrics
    to guide strategy selection.
    """
    
    def __init__(self, high_bond_threshold: float = 0.7):
        self.body_metrics = BodyStabilityMetrics()
        self.relationship_metrics = RelationshipAssetMetrics(high_bond_threshold=high_bond_threshold)
        self.learning_metrics = LearningMetrics()
        
        # Strategy thresholds
        self.collapse_strategy_threshold = 0.3  # stability score below this -> conservative
        self.stagnation_strategy_threshold = 0.1  # info gain below this -> maintenance
        
        # Strategy history
        self.strategy_history: List[Tuple[str, str]] = []
        self.last_decision_trace: Optional[PersistenceDecisionTrace] = None

        # Tradeoff weights: persistence must not dominate by itself
        self.tradeoff_weights = {
            "persistence": 0.55,
            "risk": 0.25,
            "ambiguity": 0.20,
        }
    
    def update_body_state(self, energy: float, safety_stress: float, focus_fatigue: float) -> Dict[str, Any]:
        """Update body state metrics."""
        return self.body_metrics.update(energy, safety_stress, focus_fatigue)
    
    def update_relationship(self, target_id: str, bond: Optional[float] = None,
                           reliability: Optional[float] = None, trust: Optional[float] = None):
        """Update relationship metrics for a target."""
        self.relationship_metrics.update_target(target_id, bond, reliability, trust)
    
    def record_info_gain(self, info_gain: float):
        """Record information gain."""
        self.learning_metrics.add_info_gain(info_gain)
    
    def record_harm(self, target_id: str):
        """Record harm toward a target."""
        self.relationship_metrics.record_harm(target_id)
    
    def record_repair(self, target_id: str, success: bool = True):
        """Record repair attempt toward a target."""
        self.relationship_metrics.record_repair(target_id, success)
    
    def evaluate_action_cost(self, action: str, target_id: Optional[str] = None) -> PersistenceCost:
        """
        Evaluate the persistence cost of an action.
        
        Args:
            action: Action type (e.g., "approach", "attack", "repair", "withdraw")
            target_id: Optional target for relationship context
        
        Returns:
            PersistenceCost for the action
        """
        cost = PersistenceCost()
        
        # Body cost based on current state
        if self.body_metrics.is_in_collapse():
            cost.body_cost = 0.5  # Any action is costly during collapse
        else:
            cost.body_cost = 0.1  # Normal cost
        
        # Relationship cost
        if target_id:
            bond = self.relationship_metrics.get_bond(target_id)
            if action in ["attack", "harm", "betray"]:
                cost.relationship_cost = bond  # Higher bond = higher cost to harm
            elif action in ["repair", "apologize"]:
                cost.relationship_cost = 0.1  # Low cost for repair
            elif action == "approach":
                cost.relationship_cost = 0.2
        
        # Learning cost (stagnation penalty)
        is_stag, _ = self.learning_metrics.is_stagnating()
        if is_stag and action == "explore":
            cost.learning_cost = 0.0  # No cost for exploration when stagnating
        else:
            cost.learning_cost = 0.1
        
        return cost
    
    def _compute_persistence_pressure(self, target_id: Optional[str] = None) -> float:
        """Compute aggregate persistence pressure from the 3 constraint groups."""
        body_pressure = 1.0 - self.body_metrics.get_stability_score()
        learning_pressure = 1.0 - self.learning_metrics.get_learning_score()

        relationship_pressure = 0.0
        if target_id:
            bond = self.relationship_metrics.get_bond(target_id)
            harm = self.relationship_metrics.harm_events.get(target_id, 0)
            repair_sensitivity = self.relationship_metrics.get_repair_sensitivity(target_id)
            relationship_pressure = min(1.0, bond * 0.4 + min(1.0, harm * 0.2) + repair_sensitivity * 0.3)

        pressure = body_pressure * 0.45 + relationship_pressure * 0.30 + learning_pressure * 0.25
        return max(0.0, min(1.0, pressure))

    def select_strategy(self, target_id: Optional[str] = None) -> Tuple[PersistenceStrategy, str]:
        """Backward-compatible strategy API (uses neutral risk/ambiguity defaults)."""
        strategy, reason, _ = self.select_strategy_with_tradeoff(target_id=target_id)
        return strategy, reason

    def select_strategy_with_tradeoff(
        self,
        target_id: Optional[str] = None,
        risk: float = 0.0,
        ambiguity: float = 0.0,
        expected_info_gain: Optional[float] = None,
    ) -> Tuple[PersistenceStrategy, str, PersistenceDecisionTrace]:
        """Persistence decision with explicit tradeoff against risk/ambiguity."""
        risk = max(0.0, min(1.0, risk))
        ambiguity = max(0.0, min(1.0, ambiguity))
        if expected_info_gain is None:
            expected_info_gain = self.learning_metrics.get_average_info_gain(last_n=10)
        expected_info_gain = max(0.0, min(1.0, expected_info_gain))

        stability = self.body_metrics.get_stability_score()
        persistence_pressure = self._compute_persistence_pressure(target_id)
        tradeoff_score = (
            persistence_pressure * self.tradeoff_weights["persistence"]
            + risk * self.tradeoff_weights["risk"]
            + ambiguity * self.tradeoff_weights["ambiguity"]
        )

        dominant_drivers = []
        if persistence_pressure >= 0.4:
            dominant_drivers.append("persistence_pressure")
        if risk >= 0.4:
            dominant_drivers.append("risk")
        if ambiguity >= 0.4:
            dominant_drivers.append("ambiguity")

        conservative_trigger = None
        repair_trigger = None
        retreat_trigger = None

        if stability < 0.08 or self.body_metrics.focus_fatigue_collapses >= 3:
            strategy = PersistenceStrategy.RETREAT
            reason = f"critical_instability({stability:.2f})"
            retreat_trigger = reason
        elif self.body_metrics.is_in_collapse() or stability < self.collapse_strategy_threshold or tradeoff_score >= 0.45:
            strategy = PersistenceStrategy.CONSERVATIVE
            conservative_trigger = (
                f"collapse({self.body_metrics.is_in_collapse()})/stability({stability:.2f})/tradeoff({tradeoff_score:.2f})"
            )
            reason = f"conservative_pressure({tradeoff_score:.2f})"
        else:
            selected_repair_target = None
            if target_id and target_id in self.relationship_metrics.target_bonds:
                should_repair, repair_reason = self.relationship_metrics.should_prioritize_repair(target_id)
                if should_repair and (risk + ambiguity) < 1.6:
                    selected_repair_target = (target_id, repair_reason)
            if selected_repair_target is None:
                for tid in self.relationship_metrics.target_bonds:
                    should_repair, repair_reason = self.relationship_metrics.should_prioritize_repair(tid)
                    if should_repair and (risk + ambiguity) < 1.6:
                        selected_repair_target = (tid, repair_reason)
                        break

            if selected_repair_target is not None:
                strategy = PersistenceStrategy.REPAIR
                repair_trigger = f"repair_needed:{selected_repair_target[0]}({selected_repair_target[1]})"
                reason = repair_trigger
            else:
                is_stag, avg_gain = self.learning_metrics.is_stagnating()
                if is_stag and ambiguity < 0.75 and expected_info_gain < 0.2:
                    strategy = PersistenceStrategy.MAINTENANCE
                    reason = f"stagnation({avg_gain:.2f})"
                else:
                    strategy = PersistenceStrategy.NORMAL
                    reason = "normal_operation"

        trace = PersistenceDecisionTrace(
            strategy=strategy.value,
            reason=reason,
            persistence_pressure=persistence_pressure,
            risk=risk,
            ambiguity=ambiguity,
            expected_info_gain=expected_info_gain,
            tradeoff_score=tradeoff_score,
            dominant_drivers=dominant_drivers,
            conservative_trigger=conservative_trigger,
            repair_trigger=repair_trigger,
            retreat_trigger=retreat_trigger,
        )

        self.last_decision_trace = trace
        self.record_strategy(strategy, reason)
        return strategy, reason, trace
    
    def record_strategy(self, strategy: PersistenceStrategy, reason: str):
        """Record strategy selection to history."""
        self.strategy_history.append((strategy.value, reason))
        # Keep last 100
        if len(self.strategy_history) > 100:
            self.strategy_history.pop(0)
    
    def get_strategy_distribution(self) -> Dict[str, int]:
        """Get distribution of strategies used."""
        dist = {"normal": 0, "conservative": 0, "repair": 0, "retreat": 0, "maintenance": 0}
        for s, _ in self.strategy_history:
            if s in dist:
                dist[s] += 1
        return dist
    
    def get_telemetry(self) -> Dict[str, Any]:
        """Get full telemetry for persistence state."""
        strategy, reason, trace = self.select_strategy_with_tradeoff()
        return {
            "strategy": strategy.value,
            "strategy_reason": reason,
            "strategy_trace": trace.to_dict(),
            "body_stability": self.body_metrics.to_dict(),
            "relationship_assets": self.relationship_metrics.to_dict(),
            "learning": self.learning_metrics.to_dict(),
            "learning_health": self.learning_metrics.to_dict(),
            "strategy_distribution": self.get_strategy_distribution(),
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        strategy, reason, trace = self.select_strategy_with_tradeoff()
        return {
            "strategy": strategy.value,
            "strategy_reason": reason,
            "strategy_trace": trace.to_dict(),
            "body_metrics": self.body_metrics.to_dict(),
            "relationship_metrics": self.relationship_metrics.to_dict(),
            "learning_metrics": self.learning_metrics.to_dict(),
        }


class PersistenceDecisionContext:
    """
    Decision context for persistence-aware choices.
    
    Provides a unified interface for decision-making code to query
    persistence state and get recommendations.
    """
    
    def __init__(self, body_metrics: Optional[BodyStabilityMetrics] = None,
                 relationship_metrics: Optional[RelationshipAssetMetrics] = None,
                 learning_metrics: Optional[LearningMetrics] = None,
                 target_id: Optional[str] = None):
        self.body_metrics = body_metrics or BodyStabilityMetrics()
        self.relationship_metrics = relationship_metrics or RelationshipAssetMetrics()
        self.learning_metrics = learning_metrics or LearningMetrics()
        self.target_id = target_id
    
    def get_overall_persistence_score(self) -> float:
        """
        Compute overall persistence score [0, 1].
        
        1.0 = excellent persistence state
        0.0 = critical persistence state
        """
        # Body stability (40% weight)
        body_score = self.body_metrics.get_stability_score()
        
        # Relationship health (35% weight)
        rel_score = 1.0
        if self.target_id:
            bond = self.relationship_metrics.get_bond(self.target_id)
            harm = self.relationship_metrics.harm_events.get(self.target_id, 0)
            # Higher bond with harm = lower score
            rel_score = max(0.0, 1.0 - (harm * 0.2) - (bond * 0.1 * harm))
        
        # Learning health (25% weight)
        is_stag, _ = self.learning_metrics.is_stagnating()
        learning_score = 0.5 if is_stag else 1.0
        
        return body_score * 0.4 + rel_score * 0.35 + learning_score * 0.25
    
    def should_be_conservative(self) -> Tuple[bool, str]:
        """
        Determine if conservative strategy should be used.
        
        Returns:
            (should_conservative, reason)
        """
        stability = self.body_metrics.get_stability_score()
        if stability < 0.3:
            return True, f"body_instability({stability:.2f})"
        
        if self.body_metrics.is_in_collapse():
            return True, "active_collapse"
        
        # Also conservative if stagnating
        if self.learning_metrics.check_stagnation():
            return True, "stagnation_detected"
        
        return False, "normal_state"
    
    def should_prioritize_repair(self) -> Tuple[bool, str]:
        """
        Determine if repair should be prioritized.
        
        Returns:
            (should_repair, reason)
        """
        if self.target_id is None:
            return False, "no_target"
        
        return self.relationship_metrics.should_prioritize_repair(self.target_id)
    
    def should_retreat(self) -> Tuple[bool, str]:
        """
        Determine if retreat strategy should be used.
        
        Returns:
            (should_retreat, reason)
        """
        # Retreat if body is in critical state
        stability = self.body_metrics.get_stability_score()
        if stability < 0.15:
            return True, f"critical_instability({stability:.2f})"
        
        # Retreat if multiple collapses recently
        if self.body_metrics.focus_fatigue_collapses >= 3:
            return True, f"repeated_collapses({self.body_metrics.focus_fatigue_collapses})"
        
        return False, "no_retreat_needed"
    
    def get_recommended_patience(self) -> float:
        """
        Get recommended patience level based on persistence state.
        
        Returns:
            Recommended patience multiplier (0.5 = faster, 2.0 = slower)
        """
        patience = 1.0
        
        # Increase patience if body is stressed
        if self.body_metrics.in_focus_collapse:
            patience *= 2.0
        elif self.body_metrics.in_energy_low_episode:
            patience *= 1.5
        
        # Decrease patience if stagnating
        is_stag, _ = self.learning_metrics.is_stagnating()
        if is_stag:
            patience *= 0.7
        
        return patience
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize context to dict."""
        return {
            "overall_score": round(self.get_overall_persistence_score(), 4),
            "target_id": self.target_id,
            "body": self.body_metrics.to_dict(),
            "relationship": self.relationship_metrics.to_dict(),
            "learning": self.learning_metrics.to_dict(),
        }


# Global instance for singleton pattern
_persistence_constraint_instance: Optional[PersistenceConstraint] = None


def get_persistence_constraint() -> PersistenceConstraint:
    """Get the global persistence constraint instance."""
    global _persistence_constraint_instance
    if _persistence_constraint_instance is None:
        _persistence_constraint_instance = PersistenceConstraint()
    return _persistence_constraint_instance


def reset_persistence_constraint():
    """Reset the global persistence constraint instance."""
    global _persistence_constraint_instance
    _persistence_constraint_instance = None
