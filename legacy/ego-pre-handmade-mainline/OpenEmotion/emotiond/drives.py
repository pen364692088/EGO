"""
MVP-10 T10: Drives Module

Implements drive system for generating workspace candidates.
Drives represent intrinsic motivations that produce candidate actions.

DriveType enum: competence, coherence, efficiency, safety, curiosity
Drives class: maintain drive levels, generate candidates
Log drive changes to state_delta
"""
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class DriveType(Enum):
    """Types of intrinsic drives."""
    COMPETENCE = "competence"  # Desire to be effective, fix failures
    COHERENCE = "coherence"    # Desire for consistent beliefs/state
    EFFICIENCY = "efficiency"  # Desire for optimal resource use
    SAFETY = "safety"          # Desire for safety/stability
    CURIOSITY = "curiosity"    # Desire for exploration/learning


@dataclass
class DriveLevel:
    """Level of a single drive."""
    drive_type: DriveType
    level: float = 0.5  # 0.0 to 1.0, higher = more urgent need
    last_updated: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "drive_type": self.drive_type.value,
            "level": self.level,
            "last_updated": self.last_updated,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DriveLevel":
        return cls(
            drive_type=DriveType(data["drive_type"]),
            level=data.get("level", 0.5),
            last_updated=data.get("last_updated", time.time()),
        )


@dataclass
class DriveCandidate:
    """A candidate generated from a drive."""
    id: str
    drive_type: DriveType
    score: float
    description: str
    meta: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "drive_type": self.drive_type.value,
            "score": self.score,
            "description": self.description,
            "meta": self.meta,
        }


class Drives:
    """
    Manages drive levels and generates workspace candidates.
    
    Drives represent intrinsic motivations that produce candidate actions.
    When a drive level is low (below threshold), it generates candidates
    to address the need.
    """
    
    DEFAULT_THRESHOLDS = {
        DriveType.COMPETENCE: 0.3,   # Low competence → fix failure
        DriveType.COHERENCE: 0.4,    # Low coherence → resolve conflicts
        DriveType.EFFICIENCY: 0.3,   # Low efficiency → optimize
        DriveType.SAFETY: 0.2,       # Low safety → protect
        DriveType.CURIOSITY: 0.5,    # Low curiosity → explore
    }
    
    CANDIDATE_TEMPLATES = {
        DriveType.COMPETENCE: [
            {"id": "fix_failure_cause", "description": "Fix failure cause", "base_score": 0.8},
            {"id": "improve_skill", "description": "Improve skill in weak area", "base_score": 0.6},
            {"id": "resolve_error", "description": "Resolve encountered error", "base_score": 0.7},
        ],
        DriveType.COHERENCE: [
            {"id": "resolve_conflict", "description": "Resolve state conflict", "base_score": 0.7},
            {"id": "align_beliefs", "description": "Align inconsistent beliefs", "base_score": 0.5},
            {"id": "complete_pending", "description": "Complete pending tasks", "base_score": 0.6},
        ],
        DriveType.EFFICIENCY: [
            {"id": "optimize_process", "description": "Optimize current process", "base_score": 0.6},
            {"id": "reduce_waste", "description": "Reduce resource waste", "base_score": 0.5},
            {"id": "streamline_workflow", "description": "Streamline workflow", "base_score": 0.4},
        ],
        DriveType.SAFETY: [
            {"id": "assess_risks", "description": "Assess current risks", "base_score": 0.7},
            {"id": "strengthen_defense", "description": "Strengthen defensive measures", "base_score": 0.6},
            {"id": "backup_critical", "description": "Backup critical data", "base_score": 0.5},
        ],
        DriveType.CURIOSITY: [
            {"id": "explore_new", "description": "Explore new approach", "base_score": 0.6},
            {"id": "learn_pattern", "description": "Learn new pattern", "base_score": 0.5},
            {"id": "investigate_mystery", "description": "Investigate unknown", "base_score": 0.7},
        ],
    }
    
    def __init__(
        self,
        initial_levels: Optional[Dict[DriveType, float]] = None,
        thresholds: Optional[Dict[DriveType, float]] = None,
    ):
        """
        Initialize drives with optional custom levels and thresholds.
        
        Args:
            initial_levels: Initial drive levels (default 0.5 for all)
            thresholds: Thresholds for candidate generation (default DEFAULT_THRESHOLDS)
        """
        self.levels: Dict[DriveType, DriveLevel] = {}
        self.thresholds = thresholds or dict(self.DEFAULT_THRESHOLDS)
        self._state_delta_log: List[Dict[str, Any]] = []
        
        # Initialize all drive types
        for dt in DriveType:
            level = 0.5
            if initial_levels and dt in initial_levels:
                level = initial_levels[dt]
            self.levels[dt] = DriveLevel(drive_type=dt, level=level)
    
    def get_level(self, drive_type: DriveType) -> float:
        """Get the current level of a drive."""
        return self.levels[drive_type].level
    
    def set_level(self, drive_type: DriveType, level: float, reason: str = "") -> Dict[str, Any]:
        """
        Set the level of a drive and log the change.
        
        Args:
            drive_type: The drive to modify
            level: New level (clamped to [0, 1])
            reason: Reason for the change
        
        Returns:
            State delta dict for logging
        """
        level = max(0.0, min(1.0, level))
        old_level = self.levels[drive_type].level
        
        if abs(old_level - level) > 0.001:  # Only log meaningful changes
            self.levels[drive_type].level = level
            self.levels[drive_type].last_updated = time.time()
            
            delta = {
                "drive_type": drive_type.value,
                "before": old_level,
                "after": level,
                "reason": reason,
                "ts": time.time(),
            }
            self._state_delta_log.append(delta)
            return delta
        
        return {}
    
    def update_from_outcome(self, outcome_status: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Update drive levels based on action outcome.
        
        Args:
            outcome_status: "success", "fail", or "partial"
            context: Additional context about the outcome
        
        Returns:
            List of state deltas
        """
        deltas = []
        
        if outcome_status == "success":
            # Success increases competence, reduces curiosity
            d = self.set_level(DriveType.COMPETENCE, 
                              self.get_level(DriveType.COMPETENCE) + 0.1,
                              "outcome_success")
            if d:
                deltas.append(d)
            
            d = self.set_level(DriveType.CURIOSITY,
                              self.get_level(DriveType.CURIOSITY) - 0.05,
                              "outcome_success_explored")
            if d:
                deltas.append(d)
                
        elif outcome_status == "fail":
            # Failure decreases competence, increases curiosity
            d = self.set_level(DriveType.COMPETENCE,
                              self.get_level(DriveType.COMPETENCE) - 0.15,
                              "outcome_failure")
            if d:
                deltas.append(d)
            
            d = self.set_level(DriveType.CURIOSITY,
                              self.get_level(DriveType.CURIOSITY) + 0.1,
                              "outcome_failure_need_learning")
            if d:
                deltas.append(d)
                
            # Failure may affect safety
            if context.get("risk_level") == "high":
                d = self.set_level(DriveType.SAFETY,
                                  self.get_level(DriveType.SAFETY) - 0.1,
                                  "outcome_failure_high_risk")
                if d:
                    deltas.append(d)
        
        elif outcome_status == "partial":
            # Partial success has smaller effects
            d = self.set_level(DriveType.COMPETENCE,
                              self.get_level(DriveType.COMPETENCE) + 0.02,
                              "outcome_partial")
            if d:
                deltas.append(d)
        
        return deltas
    
    def generate_candidates(self, context: Optional[Dict[str, Any]] = None) -> List[DriveCandidate]:
        """
        Generate candidates from drives that are below threshold.
        
        Args:
            context: Optional context to influence candidate generation
        
        Returns:
            List of candidates sorted by score (highest first)
        """
        candidates = []
        context = context or {}
        
        for drive_type, level in self.levels.items():
            threshold = self.thresholds[drive_type]
            
            # Generate candidates when drive level is LOW (need is high)
            if level.level < threshold:
                urgency = (threshold - level.level) / threshold
                
                templates = self.CANDIDATE_TEMPLATES.get(drive_type, [])
                for i, template in enumerate(templates):
                    # Score = base_score * urgency * context modifier
                    score = template["base_score"] * urgency
                    
                    # Apply context modifiers
                    if context.get("has_failure"):
                        if drive_type == DriveType.COMPETENCE:
                            score *= 1.3  # Boost competence candidates after failure
                    
                    if context.get("exploration_mode"):
                        if drive_type == DriveType.CURIOSITY:
                            score *= 1.2  # Boost curiosity in exploration mode
                    
                    score = min(1.0, score)  # Cap at 1.0
                    
                    candidates.append(DriveCandidate(
                        id=f"{template['id']}_{drive_type.value}",
                        drive_type=drive_type,
                        score=round(score, 3),
                        description=template["description"],
                        meta={
                            "urgency": urgency,
                            "drive_level": level.level,
                            "threshold": threshold,
                        },
                    ))
        
        # Sort by score descending
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates
    
    def get_low_drives(self) -> List[DriveType]:
        """Get list of drives that are below threshold."""
        return [
            dt for dt, level in self.levels.items()
            if level.level < self.thresholds[dt]
        ]
    
    def get_state_delta_log(self) -> List[Dict[str, Any]]:
        """Get the log of state changes."""
        return self._state_delta_log.copy()
    
    def clear_state_delta_log(self) -> None:
        """Clear the state change log."""
        self._state_delta_log = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize drives state to dict."""
        return {
            "levels": {dt.value: level.to_dict() for dt, level in self.levels.items()},
            "thresholds": {dt.value: t for dt, t in self.thresholds.items()},
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Drives":
        """Deserialize drives state from dict."""
        drives = cls()
        
        if "levels" in data:
            for dt_str, level_data in data["levels"].items():
                dt = DriveType(dt_str)
                drives.levels[dt] = DriveLevel.from_dict(level_data)
        
        if "thresholds" in data:
            for dt_str, threshold in data["thresholds"].items():
                dt = DriveType(dt_str)
                drives.thresholds[dt] = threshold
        
        return drives


def drives_from_valence(valence: float) -> Dict[DriveType, float]:
    """
    Initialize drive levels based on valence.
    
    Positive valence → higher competence, lower curiosity
    Negative valence → lower competence, higher curiosity/safety
    
    Args:
        valence: -1.0 to 1.0
    
    Returns:
        Dict mapping drive types to initial levels
    """
    # Normalize valence to [0, 1] range
    v = (valence + 1.0) / 2.0  # 0 = very negative, 1 = very positive
    
    return {
        DriveType.COMPETENCE: 0.3 + 0.4 * v,  # 0.3-0.7
        DriveType.COHERENCE: 0.4 + 0.2 * v,   # 0.4-0.6
        DriveType.EFFICIENCY: 0.5,             # Neutral
        DriveType.SAFETY: 0.5 - 0.3 * (1 - v), # Higher with negative valence
        DriveType.CURIOSITY: 0.7 - 0.3 * v,    # Higher with negative valence
    }
