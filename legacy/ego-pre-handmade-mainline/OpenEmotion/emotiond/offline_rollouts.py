"""
US-704: Offline Rollouts v0

Low-cost "think before acting" simulation for recovery optimization.
Default: DISABLED (--enable-rollouts flag required)
"""
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import math


@dataclass
class RolloutBranch:
    """A single rollout branch representing a possible action trajectory"""
    name: str
    action: str
    estimated_recovery: float
    relationship_impact: float
    drive_error_reduction: float
    risk_score: float
    confidence: float = 0.5
    trace: List[Dict] = field(default_factory=list)
    
    def compute_score(self, weights: Optional[Dict[str, float]] = None) -> float:
        if weights is None:
            weights = {"recovery": 0.4, "relationship": 0.3, "drive_error": 0.2, "risk_penalty": 0.1}
        score = (
            weights["recovery"] * self.estimated_recovery +
            weights["relationship"] * max(0, self.relationship_impact) +
            weights["drive_error"] * self.drive_error_reduction -
            weights["risk_penalty"] * self.risk_score
        )
        return score * self.confidence


@dataclass
class RolloutResult:
    """Result of offline rollout simulation"""
    enabled: bool
    branches: List[RolloutBranch] = field(default_factory=list)
    best_branch: Optional[str] = None
    best_score: float = 0.0
    recommendation: Optional[str] = None
    trace_id: str = ""
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.trace_id:
            self.trace_id = hashlib.sha256(f"{datetime.now().isoformat()}".encode()).hexdigest()[:16]
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class OfflineRollouts:
    BRANCH_TEMPLATES = {
        "clarify": {"action": "seek_clarification", "base_recovery": 0.3, "base_risk": 0.1, "relationship_neutral": True},
        "defer": {"action": "pause_and_reflect", "base_recovery": 0.2, "base_risk": 0.05, "relationship_neutral": True},
        "escalate": {"action": "raise_urgency", "base_recovery": 0.5, "base_risk": 0.4, "relationship_neutral": False}
    }
    
    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.history: List[RolloutResult] = []
        self.max_history = 100
    
    def generate_branches(self, context: Dict[str, Any], drive_error: float = 0.0,
                         relationship_health: float = 0.5, grudge_level: float = 0.0) -> List[RolloutBranch]:
        if not self.enabled:
            return []
        branches = []
        for branch_name, template in self.BRANCH_TEMPLATES.items():
            recovery = self._estimate_recovery(template, drive_error, relationship_health, grudge_level)
            rel_impact = self._estimate_relationship_impact(template, relationship_health, grudge_level)
            drive_reduction = self._estimate_drive_reduction(template, drive_error)
            risk = self._estimate_risk(template, grudge_level)
            branch = RolloutBranch(
                name=branch_name, action=template["action"],
                estimated_recovery=recovery, relationship_impact=rel_impact,
                drive_error_reduction=drive_reduction, risk_score=risk,
                confidence=self._compute_confidence(context)
            )
            branches.append(branch)
        return branches
    
    def _estimate_recovery(self, template: Dict, drive_error: float, relationship_health: float, grudge_level: float) -> float:
        base = template["base_recovery"]
        drive_factor = 1.0 + drive_error * 0.5
        rel_factor = 1.0 + (1.0 - relationship_health) * 0.3
        grudge_penalty = grudge_level * 0.2
        if template["action"] == "pause_and_reflect":
            grudge_penalty *= 1.5
        return max(0.0, min(1.0, base * drive_factor * rel_factor - grudge_penalty))
    
    def _estimate_relationship_impact(self, template: Dict, relationship_health: float, grudge_level: float) -> float:
        if template["relationship_neutral"]:
            return 0.0
        base_impact = 0.0
        volatility = (1.0 - relationship_health) * 0.3
        if grudge_level > 0.5:
            base_impact = -0.2 * grudge_level
        return base_impact - volatility
    
    def _estimate_drive_reduction(self, template: Dict, drive_error: float) -> float:
        if drive_error < 0.1:
            return 0.0
        if template["action"] == "seek_clarification":
            return min(drive_error * 0.3, 0.3)
        elif template["action"] == "pause_and_reflect":
            return min(drive_error * 0.2, 0.2)
        elif template["action"] == "raise_urgency":
            return min(drive_error * 0.5, 0.4)
        return 0.0
    
    def _estimate_risk(self, template: Dict, grudge_level: float) -> float:
        base_risk = template["base_risk"]
        if not template["relationship_neutral"]:
            return min(1.0, base_risk + grudge_level * 0.3)
        return base_risk
    
    def _compute_confidence(self, context: Dict) -> float:
        context_keys = len(context)
        return min(1.0, context_keys / 10.0 * 0.5 + 0.3)
    
    def select_best_branch(self, branches: List[RolloutBranch], weights: Optional[Dict[str, float]] = None) -> Tuple[Optional[str], float]:
        if not branches:
            return None, 0.0
        best_name = None
        best_score = float("-inf")
        for branch in branches:
            score = branch.compute_score(weights)
            if score > best_score:
                best_score = score
                best_name = branch.name
        return best_name, best_score
    
    def run_rollouts(self, context: Dict[str, Any], drive_error: float = 0.0,
                     relationship_health: float = 0.5, grudge_level: float = 0.0) -> RolloutResult:
        if not self.enabled:
            return RolloutResult(enabled=False)
        branches = self.generate_branches(context, drive_error, relationship_health, grudge_level)
        best_name, best_score = self.select_best_branch(branches)
        recommendation = None
        if best_name:
            recommendation = f"Recommend: {best_name} (score={best_score:.3f})"
        result = RolloutResult(enabled=True, branches=branches, best_branch=best_name,
                              best_score=best_score, recommendation=recommendation)
        self.history.append(result)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        return result


def is_rollouts_enabled() -> bool:
    import os
    return os.getenv("EMOTIOND_ENABLE_ROLLOUTS", "").strip().lower() in ["1", "true", "yes", "on"]


def create_rollout_system() -> OfflineRollouts:
    return OfflineRollouts(enabled=is_rollouts_enabled())
