"""
MVP-4 D1: Hierarchical State System

Three-layer state hierarchy with different time scales:
- Affect (fast): Instantaneous reactions, changes in seconds
- Mood (medium): Baseline over recent period, changes in hours
- Bond/Trust (slow): Per-target relationship variables, changes in days/weeks
"""
import time
import math
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class AffectState:
    """
    Fast-changing affective state.
    
    Represents instantaneous emotional reactions.
    Changes on the order of seconds to minutes.
    """
    valence: float = 0.0  # -1.0 to 1.0
    arousal: float = 0.3  # -1.0 to 1.0
    anger: float = 0.0
    sadness: float = 0.0
    anxiety: float = 0.0
    joy: float = 0.0
    loneliness: float = 0.0
    social_safety: float = 0.6
    energy: float = 0.7
    uncertainty: float = 0.5  # How uncertain the current affect is
    last_updated: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "valence": self.valence,
            "arousal": self.arousal,
            "anger": self.anger,
            "sadness": self.sadness,
            "anxiety": self.anxiety,
            "joy": self.joy,
            "loneliness": self.loneliness,
            "social_safety": self.social_safety,
            "energy": self.energy,
            "uncertainty": self.uncertainty,
            "last_updated": self.last_updated
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AffectState":
        return cls(
            valence=data.get("valence", 0.0),
            arousal=data.get("arousal", 0.3),
            anger=data.get("anger", 0.0),
            sadness=data.get("sadness", 0.0),
            anxiety=data.get("anxiety", 0.0),
            joy=data.get("joy", 0.0),
            loneliness=data.get("loneliness", 0.0),
            social_safety=data.get("social_safety", 0.6),
            energy=data.get("energy", 0.7),
            uncertainty=data.get("uncertainty", 0.5),
            last_updated=data.get("last_updated", time.time())
        )


@dataclass
class MoodState:
    """
    Medium-changing mood baseline.
    
    Represents emotional baseline over recent period.
    "最近比较开心/低落/焦虑/疲惫"
    Changes on the order of hours to days.
    """
    valence: float = 0.0
    arousal: float = 0.3
    anxiety: float = 0.0
    joy: float = 0.0
    sadness: float = 0.0
    anger: float = 0.0
    loneliness: float = 0.0
    uncertainty: float = 0.5
    last_updated: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "valence": self.valence,
            "arousal": self.arousal,
            "anxiety": self.anxiety,
            "joy": self.joy,
            "sadness": self.sadness,
            "anger": self.anger,
            "loneliness": self.loneliness,
            "uncertainty": self.uncertainty,
            "last_updated": self.last_updated
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MoodState":
        return cls(
            valence=data.get("valence", 0.0),
            arousal=data.get("arousal", 0.3),
            anxiety=data.get("anxiety", 0.0),
            joy=data.get("joy", 0.0),
            sadness=data.get("sadness", 0.0),
            anger=data.get("anger", 0.0),
            loneliness=data.get("loneliness", 0.0),
            uncertainty=data.get("uncertainty", 0.5),
            last_updated=data.get("last_updated", time.time())
        )


@dataclass
class BondState:
    """
    Slow-changing bond/trust state per target.
    
    Represents relationship variables that are hard to change.
    Changes on the order of days to weeks.
    """
    target: str
    bond: float = 0.0  # -1.0 to 1.0
    trust: float = 0.0  # 0.0 to 1.0
    grudge: float = 0.0  # 0.0 to 1.0
    repair_bank: float = 0.0  # 0.0 to 1.0
    uncertainty: float = 0.5
    last_updated: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "bond": self.bond,
            "trust": self.trust,
            "grudge": self.grudge,
            "repair_bank": self.repair_bank,
            "uncertainty": self.uncertainty,
            "last_updated": self.last_updated
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BondState":
        return cls(
            target=data.get("target", ""),
            bond=data.get("bond", 0.0),
            trust=data.get("trust", 0.0),
            grudge=data.get("grudge", 0.0),
            repair_bank=data.get("repair_bank", 0.0),
            uncertainty=data.get("uncertainty", 0.5),
            last_updated=data.get("last_updated", time.time())
        )


def apply_time_passed_affect(
    affect: AffectState,
    mood: MoodState,
    time_seconds: float,
    decay_tau: float = 300.0,
    affect_to_mood_rate: float = 0.01
) -> tuple:
    """
    Apply time-based decay to affect, regressing toward mood baseline.
    
    Affect changes quickly (seconds/minutes).
    
    Args:
        affect: Current affect state
        mood: Current mood state (the target for affect decay)
        time_seconds: How much time has passed
        decay_tau: Time constant for affect decay (default 5 minutes)
        affect_to_mood_rate: How much affect influences mood
    
    Returns:
        Tuple of (updated_affect, updated_mood)
    """
    # Calculate decay factor
    decay = math.exp(-time_seconds / decay_tau)
    
    # Affect decays toward mood values
    new_affect = AffectState(
        valence=mood.valence + (affect.valence - mood.valence) * decay,
        arousal=mood.arousal + (affect.arousal - mood.arousal) * decay,
        anger=mood.anger + (affect.anger - mood.anger) * decay,
        sadness=mood.sadness + (affect.sadness - mood.sadness) * decay,
        anxiety=mood.anxiety + (affect.anxiety - mood.anxiety) * decay,
        joy=mood.joy + (affect.joy - mood.joy) * decay,
        loneliness=mood.loneliness + (affect.loneliness - mood.loneliness) * decay,
        social_safety=0.6 + (affect.social_safety - 0.6) * decay,  # Homeostasis baseline 0.6
        energy=min(1.0, 0.7 + (affect.energy - 0.7) * decay + 0.001 * time_seconds),  # Energy recovers
        uncertainty=affect.uncertainty + (1.0 - affect.uncertainty) * (1 - decay) * 0.1,  # Uncertainty grows
        last_updated=time.time()
    )
    
    # Affect has small influence on mood (accumulates over time)
    new_mood = MoodState(
        valence=mood.valence + (affect.valence - mood.valence) * affect_to_mood_rate * time_seconds / decay_tau,
        arousal=mood.arousal + (affect.arousal - mood.arousal) * affect_to_mood_rate * time_seconds / decay_tau,
        anxiety=mood.anxiety + (affect.anxiety - mood.anxiety) * affect_to_mood_rate * time_seconds / decay_tau,
        joy=mood.joy + (affect.joy - mood.joy) * affect_to_mood_rate * time_seconds / decay_tau,
        sadness=mood.sadness + (affect.sadness - mood.sadness) * affect_to_mood_rate * time_seconds / decay_tau,
        anger=mood.anger + (affect.anger - mood.anger) * affect_to_mood_rate * time_seconds / decay_tau,
        loneliness=mood.loneliness + (affect.loneliness - mood.loneliness) * affect_to_mood_rate * time_seconds / decay_tau,
        uncertainty=mood.uncertainty,
        last_updated=mood.last_updated
    )
    
    return new_affect, new_mood


def apply_time_passed_mood(
    mood: MoodState,
    time_seconds: float,
    decay_tau: float = 86400.0,
    baseline_valence: float = 0.0,
    baseline_arousal: float = 0.3
) -> MoodState:
    """
    Apply time-based decay to mood, regressing toward baseline.
    
    Mood changes slowly (hours/days).
    
    Args:
        mood: Current mood state
        time_seconds: How much time has passed
        decay_tau: Time constant for mood decay (default 24 hours)
        baseline_valence: Baseline valence to regress to
        baseline_arousal: Baseline arousal to regress to
    
    Returns:
        Updated mood state
    """
    decay = math.exp(-time_seconds / decay_tau)
    
    return MoodState(
        valence=baseline_valence + (mood.valence - baseline_valence) * decay,
        arousal=baseline_arousal + (mood.arousal - baseline_arousal) * decay,
        anxiety=mood.anxiety * decay,  # Emotions regress to 0
        joy=mood.joy * decay,
        sadness=mood.sadness * decay,
        anger=mood.anger * decay,
        loneliness=mood.loneliness * decay,
        uncertainty=mood.uncertainty + (1.0 - mood.uncertainty) * (1 - decay) * 0.1,
        last_updated=time.time()
    )


def apply_time_passed_bond(
    bond: BondState,
    time_seconds: float,
    change_rate: float = 0.001
) -> BondState:
    """
    Apply time-based change to bond/trust state.
    
    Bond/trust changes very slowly (days/weeks).
    
    Args:
        bond: Current bond state for a target
        time_seconds: How much time has passed
        change_rate: Very slow change rate (per day, so 0.001 means 0.1% per day)
    
    Returns:
        Updated bond state
    """
    # Bonds and grudges decay very slowly toward 0
    # Normalize by 86400 so change_rate is "per day"
    decay = math.exp(-time_seconds * change_rate / 86400)
    
    return BondState(
        target=bond.target,
        bond=bond.bond * decay,
        trust=bond.trust,  # Trust is more stable
        grudge=bond.grudge * decay,
        repair_bank=bond.repair_bank * decay,
        uncertainty=bond.uncertainty + (1.0 - bond.uncertainty) * (1 - decay) * 0.01,
        last_updated=time.time()
    )


class StateHierarchy:
    """
    Manages the three-layer state hierarchy.
    """
    
    def __init__(self):
        self.affect = AffectState()
        self.mood = MoodState()
        self.bonds: Dict[str, BondState] = {}
    
    def get_bond(self, target: str) -> BondState:
        """Get bond state for a target, creating if needed."""
        if target not in self.bonds:
            self.bonds[target] = BondState(target=target)
        return self.bonds[target]
    
    def apply_time_passed(
        self,
        time_seconds: float,
        affect_tau: float = 300.0,
        mood_tau: float = 86400.0,
        bond_rate: float = 0.001,
        affect_to_mood_rate: float = 0.01
    ):
        """
        Apply time-based decay to all state layers.
        
        Order matters: affect → mood → bond
        """
        # Affect decays toward mood
        self.affect, self.mood = apply_time_passed_affect(
            self.affect, self.mood, time_seconds,
            decay_tau=affect_tau,
            affect_to_mood_rate=affect_to_mood_rate
        )
        
        # Mood decays toward baseline
        self.mood = apply_time_passed_mood(
            self.mood, time_seconds,
            decay_tau=mood_tau
        )
        
        # Bonds decay very slowly
        for target in list(self.bonds.keys()):
            self.bonds[target] = apply_time_passed_bond(
                self.bonds[target], time_seconds,
                change_rate=bond_rate
            )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "affect": self.affect.to_dict(),
            "mood": self.mood.to_dict(),
            "bonds": {t: b.to_dict() for t, b in self.bonds.items()}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateHierarchy":
        hierarchy = cls()
        if "affect" in data:
            hierarchy.affect = AffectState.from_dict(data["affect"])
        if "mood" in data:
            hierarchy.mood = MoodState.from_dict(data["mood"])
        if "bonds" in data:
            for target, bond_data in data["bonds"].items():
                hierarchy.bonds[target] = BondState.from_dict(bond_data)
        return hierarchy
