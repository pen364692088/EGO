"""
Offline Rollouts v0 (US-704)

Implements "think before you speak" capability through offline simulation.
Default is OFF for safety and efficiency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .drive_homeostasis import DriveState, get_drive


class RolloutBranch(str, Enum):
    """Types of rollout branches"""
    CLARIFY = "clarify"
    DEFER = "defer"
    ESCALATE = "escalate"
    DEFAULT = "default"


@dataclass
class RolloutCandidate:
    """A candidate action to simulate."""
    branch: RolloutBranch
    action: str
    predicted_outcome: str = ""
    predicted_drive_delta: Dict[str, float] = field(default_factory=dict)
    base_score: float = 0.5
    drive_score: float = 0.0
    final_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "branch": self.branch.value,
            "action": self.action,
            "predicted_outcome": self.predicted_outcome,
            "predicted_drive_delta": self.predicted_drive_delta,
            "base_score": self.base_score,
            "drive_score": self.drive_score,
            "final_score": self.final_score,
        }


@dataclass
class RolloutResult:
    """Result of rollout simulation."""
    candidates: List[RolloutCandidate] = field(default_factory=list)
    selected_branch: RolloutBranch = RolloutBranch.DEFAULT
    reasoning: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidates": [c.to_dict() for c in self.candidates],
            "selected_branch": self.selected_branch.value,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp,
        }


class RolloutEngine:
    """
    Engine for offline rollout simulation.
    
    By default, rollouts are DISABLED for safety.
    Enable only for diagnostic/recovery scenarios.
    """
    
    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.history: List[RolloutResult] = []
    
    def enable(self) -> None:
        """Enable rollouts."""
        self.enabled = True
    
    def disable(self) -> None:
        """Disable rollouts."""
        self.enabled = False
    
    def generate_candidates(
        self,
        context: str,
        drive_state: DriveState,
        available_branches: Optional[List[RolloutBranch]] = None,
    ) -> List[RolloutCandidate]:
        """
        Generate rollout candidates for a context.
        
        Args:
            context: The current situation/context
            drive_state: Current drive state
            available_branches: Which branches to consider
        
        Returns:
            List of candidate actions
        """
        if available_branches is None:
            available_branches = [
                RolloutBranch.DEFAULT,
                RolloutBranch.CLARIFY,
                RolloutBranch.DEFER,
                RolloutBranch.ESCALATE,
            ]
        
        candidates = []
        
        for branch in available_branches:
            candidate = RolloutCandidate(
                branch=branch,
                action=self._generate_action(branch, context),
            )
            
            # Predict drive changes
            candidate.predicted_drive_delta = self._predict_drive_delta(
                branch, drive_state
            )
            
            # Compute scores
            candidate.base_score = self._compute_base_score(branch)
            candidate.drive_score = self._compute_drive_score(
                drive_state, candidate.predicted_drive_delta
            )
            candidate.final_score = candidate.base_score + candidate.drive_score
            
            candidates.append(candidate)
        
        return candidates
    
    def select_best(
        self,
        candidates: List[RolloutCandidate],
        drive_state: DriveState,
    ) -> Tuple[RolloutCandidate, str]:
        """
        Select the best candidate.
        
        Args:
            candidates: List of candidates
            drive_state: Current drive state
        
        Returns:
            (selected_candidate, reasoning) tuple
        """
        if not candidates:
            return RolloutCandidate(branch=RolloutBranch.DEFAULT, action="default"), "No candidates available"
        
        # Sort by final score
        sorted_candidates = sorted(candidates, key=lambda c: c.final_score, reverse=True)
        selected = sorted_candidates[0]
        
        reasoning = f"Selected {selected.branch.value} (score={selected.final_score:.2f})"
        
        return selected, reasoning
    
    def run_rollouts(
        self,
        context: str,
        drive_state: DriveState,
    ) -> Optional[RolloutResult]:
        """
        Run offline rollouts.
        
        Returns None if rollouts are disabled.
        """
        if not self.enabled:
            return None
        
        candidates = self.generate_candidates(context, drive_state)
        selected, reasoning = self.select_best(candidates, drive_state)
        
        result = RolloutResult(
            candidates=candidates,
            selected_branch=selected.branch,
            reasoning=reasoning,
        )
        
        self.history.append(result)
        return result
    
    def _generate_action(self, branch: RolloutBranch, context: str) -> str:
        """Generate action description for a branch."""
        actions = {
            RolloutBranch.DEFAULT: "proceed with standard response",
            RolloutBranch.CLARIFY: "ask clarifying questions",
            RolloutBranch.DEFER: "postpone action for later",
            RolloutBranch.ESCALATE: "escalate to higher priority handling",
        }
        return actions.get(branch, "unknown action")
    
    def _predict_drive_delta(
        self,
        branch: RolloutBranch,
        drive_state: DriveState,
    ) -> Dict[str, float]:
        """Predict how a branch affects drive state."""
        deltas = {
            RolloutBranch.DEFAULT: {"uncertainty": 0.0, "fatigue": 0.0},
            RolloutBranch.CLARIFY: {"uncertainty": -0.3, "fatigue": 0.1},
            RolloutBranch.DEFER: {"uncertainty": 0.1, "fatigue": -0.1},
            RolloutBranch.ESCALATE: {"uncertainty": -0.1, "safety": 0.1},
        }
        return deltas.get(branch, {})
    
    def _compute_base_score(self, branch: RolloutBranch) -> float:
        """Compute base score for a branch."""
        scores = {
            RolloutBranch.DEFAULT: 0.5,
            RolloutBranch.CLARIFY: 0.6,
            RolloutBranch.DEFER: 0.4,
            RolloutBranch.ESCALATE: 0.3,
        }
        return scores.get(branch, 0.5)
    
    def _compute_drive_score(
        self,
        drive_state: DriveState,
        predicted_delta: Dict[str, float],
    ) -> float:
        """Compute drive-based score adjustment."""
        current_error = get_drive().drive_error()
        
        # Apply predicted delta (simplified)
        predicted_state = DriveState.from_dict(drive_state.to_dict())
        for attr, delta in predicted_delta.items():
            current = getattr(predicted_state, attr, 0.5)
            setattr(predicted_state, attr, max(0, min(1, current + delta)))
        
        predicted_error = get_drive().drive_error()
        
        # Score improvement = error reduction
        return (current_error - predicted_error) * 0.5
