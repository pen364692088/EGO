"""
MVP16: Developmental Manager

Manages long-horizon developmental continuity with real persistence.
"""
import time
import json
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List

from .schema import (
    DevelopmentalState,
    DevelopmentalEpisode,
    TransitionRecord,
    GrowthMetric,
    DevelopmentalTrajectory,
)


# Default persistence path - can be overridden for testing
DEFAULT_STATE_PATH = Path(__file__).parent.parent.parent / "data" / "developmental_state.json"


class DevelopmentalManager:
    """Manager for open developmental continuity with real persistence."""
    
    _instance: Optional["DevelopmentalManager"] = None
    
    def __init__(
        self, 
        initial_state: Optional[DevelopmentalState] = None,
        state_path: Optional[Path] = None
    ):
        self._state_path = state_path or DEFAULT_STATE_PATH
        
        if initial_state is not None:
            self.state = initial_state
        else:
            # Try to load from persistence first
            loaded_state = self._load_state()
            if loaded_state is not None:
                self.state = loaded_state
            else:
                # Only create default state if no persisted state exists
                self.state = DevelopmentalState()
                self._initialize_metrics()
    
    @classmethod
    def get_instance(cls, state_path: Optional[Path] = None) -> "DevelopmentalManager":
        if cls._instance is None:
            cls._instance = cls(state_path=state_path)
        return cls._instance
    
    @classmethod
    def reset(cls, clear_persistence: bool = False, state_path: Optional[Path] = None) -> None:
        """Reset the manager instance.
        
        Args:
            clear_persistence: If True, also delete the persisted state file.
            state_path: Path to state file (for testing).
        """
        # Clear persistence if requested, regardless of instance state
        if clear_persistence:
            path = state_path or DEFAULT_STATE_PATH
            if path.exists():
                path.unlink()
        
        # Clear instance
        cls._instance = None
    
    def _load_state(self) -> Optional[DevelopmentalState]:
        """Load state from persistence. Returns None if no persisted state exists."""
        if not self._state_path.exists():
            return None
        
        try:
            data = json.loads(self._state_path.read_text())
            return DevelopmentalState(**data)
        except (json.JSONDecodeError, Exception):
            # If persisted state is corrupted, return None
            return None
    
    def save(self) -> bool:
        """Persist current state to disk."""
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(self.state.model_dump_json(indent=2))
            return True
        except Exception:
            return False
    
    def has_real_data(self) -> bool:
        """Check if this manager has real developmental data (not just defaults).
        
        Real data means:
        - At least one recorded episode, OR
        - At least one recorded transition, OR
        - Metrics that were explicitly set (not just initialized with defaults)
        """
        has_episodes = len(self.state.trajectory.episodes) > 0
        has_transitions = len(self.state.trajectory.transitions) > 0
        
        # Check if metrics were explicitly updated (have history)
        has_real_metrics = any(
            len(m.history) > 0 for m in self.state.metrics.values()
        )
        
        return has_episodes or has_transitions or has_real_metrics
    
    def has_persisted_state(self) -> bool:
        """Check if a persisted state file exists."""
        return self._state_path.exists()
    
    def _initialize_metrics(self) -> None:
        """Initialize default metrics. Only called when no persisted state exists."""
        default_metrics = [
            ("continuity_score", 0.8),
            ("growth_rate", 0.5),
            ("identity_stability", 1.0),
            ("governance_compliance", 1.0),
        ]
        for name, value in default_metrics:
            if name not in self.state.metrics:
                self.state.metrics[name] = GrowthMetric(metric_name=name, value=value)
    
    def record_episode(
        self,
        episode_type: str,
        phase: str,
        description: str = ""
    ) -> DevelopmentalEpisode:
        episode = DevelopmentalEpisode(
            episode_id=f"ep_{int(time.time())}_{uuid.uuid4().hex[:8]}",
            episode_type=episode_type,
            phase=phase,
            description=description
        )
        self.state.trajectory.episodes.append(episode)
        self.state.update_timestamp()
        self.save()  # Auto-persist
        return episode
    
    def complete_episode(self, episode_id: str, achievements: List[str]) -> bool:
        for ep in self.state.trajectory.episodes:
            if ep.episode_id == episode_id:
                ep.completed_at = time.time()
                ep.achievements = achievements
                self.state.update_timestamp()
                self.save()  # Auto-persist
                return True
        return False
    
    def record_transition(
        self,
        from_phase: str,
        to_phase: str,
        approved: bool = False,
        approver: Optional[str] = None
    ) -> TransitionRecord:
        transition = TransitionRecord(
            transition_id=f"tr_{int(time.time())}_{uuid.uuid4().hex[:8]}",
            from_phase=from_phase,
            to_phase=to_phase,
            approved=approved,
            approver=approver
        )
        self.state.trajectory.transitions.append(transition)
        self.state.trajectory.current_phase = to_phase
        self.state.update_timestamp()
        self.save()  # Auto-persist
        return transition
    
    def update_metric(self, name: str, value: float) -> GrowthMetric:
        if name not in self.state.metrics:
            self.state.metrics[name] = GrowthMetric(metric_name=name, value=value)
        else:
            metric = self.state.metrics[name]
            metric.history.append(metric.value)
            metric.value = value
            # Calculate trend based on history
            if len(metric.history) >= 2:
                metric.trend = "improving" if value > metric.history[-1] else ("declining" if value < metric.history[-1] else "stable")
            else:
                metric.trend = "stable"
        self.state.update_timestamp()
        self.save()  # Auto-persist
        return self.state.metrics[name]
    
    def check_identity_preservation(self) -> bool:
        return self.state.trajectory.identity_preserved
    
    def get_continuity_score(self) -> float:
        return self.state.get_long_horizon_score()
    
    def get_summary(self) -> Dict[str, Any]:
        return {
            "current_phase": self.state.trajectory.current_phase,
            "episodes": len(self.state.trajectory.episodes),
            "transitions": len(self.state.trajectory.transitions),
            "identity_preserved": self.state.trajectory.identity_preserved,
            "continuity_score": self.get_continuity_score(),
            "has_real_data": self.has_real_data(),
            "persisted": self.has_persisted_state(),
        }


def get_developmental_manager(state_path: Optional[Path] = None) -> DevelopmentalManager:
    return DevelopmentalManager.get_instance(state_path=state_path)


def reset_developmental_manager(
    clear_persistence: bool = False, 
    state_path: Optional[Path] = None
) -> None:
    """Reset the developmental manager.
    
    Args:
        clear_persistence: If True, also delete persisted state file.
        state_path: Path to state file (for testing).
    """
    DevelopmentalManager.reset(clear_persistence=clear_persistence, state_path=state_path)
