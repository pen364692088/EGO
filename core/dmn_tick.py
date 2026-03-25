"""
DMN Tick v0 (US-707)

Implements low-frequency background tick for:
- Memory consolidation
- Ledger audit
- Optional rollouts
- Proactive reminders (gated)

Default tick interval: 60 seconds (configurable)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .drive_homeostasis import DriveState, get_drive, drive_error
from .episodic_memory import EpisodeStore
from .self_model import SelfModel


class TickAction(str, Enum):
    """Actions that can be performed in a tick."""
    CONSOLIDATE = "consolidate"
    AUDIT_LEDGER = "audit_ledger"
    RUN_ROLLOUTS = "run_rollouts"
    PROACTIVE_REMINDER = "proactive_reminder"


@dataclass
class TickResult:
    """Result of a tick execution."""
    actions_performed: List[str] = field(default_factory=list)
    consolidation_count: int = 0
    ledger_issues: List[str] = field(default_factory=list)
    rollout_result: Optional[Dict[str, Any]] = None
    reminder_sent: bool = False
    duration_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "actions_performed": self.actions_performed,
            "consolidation_count": self.consolidation_count,
            "ledger_issues": self.ledger_issues,
            "rollout_result": self.rollout_result,
            "reminder_sent": self.reminder_sent,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }


@dataclass
class ProactiveGate:
    """
    Gate for proactive reminders.
    
    Prevents spamming the user with reminders.
    """
    tension_threshold: float = 0.7
    cooldown_minutes: int = 30
    min_user_window_hours: List[int] = field(default_factory=lambda: [9, 10, 11, 14, 15, 16])  # 9-11am, 2-4pm
    
    last_reminder: Optional[str] = None
    current_tension: float = 0.0
    
    def should_remind(self, tension: float) -> bool:
        """Check if a reminder should be sent."""
        self.current_tension = tension
        
        # Check tension threshold
        if tension < self.tension_threshold:
            return False
        
        # Check cooldown
        if self.last_reminder:
            last = datetime.fromisoformat(self.last_reminder.replace("Z", "+00:00"))
            elapsed = datetime.now(timezone.utc) - last
            if elapsed < timedelta(minutes=self.cooldown_minutes):
                return False
        
        # Check user window
        now_hour = datetime.now(timezone.utc).hour
        if now_hour not in self.min_user_window_hours:
            return False
        
        return True
    
    def record_reminder(self) -> None:
        """Record that a reminder was sent."""
        self.last_reminder = datetime.now(timezone.utc).isoformat()


class DMNTick:
    """
    Default Mode Network - background tick process.
    
    Performs maintenance tasks at low frequency.
    """
    
    def __init__(
        self,
        episode_store: Optional[EpisodeStore] = None,
        self_model: Optional[SelfModel] = None,
        drive_state: Optional[DriveState] = None,
        tick_interval_seconds: int = 60,
    ):
        self.episode_store = episode_store or EpisodeStore()
        self.self_model = self_model or SelfModel()
        self.drive_state = drive_state or DriveState()
        self.tick_interval = tick_interval_seconds
        
        self.proactive_gate = ProactiveGate()
        self.history: List[TickResult] = []
        self._last_tick: Optional[str] = None
    
    def tick(
        self,
        enable_rollouts: bool = False,
        enable_proactive: bool = False,
    ) -> TickResult:
        """
        Execute a tick.
        
        Args:
            enable_rollouts: Whether to run rollouts
            enable_proactive: Whether to allow proactive reminders
        
        Returns:
            TickResult with actions performed
        """
        start_time = time.time()
        result = TickResult()
        
        # 1. Memory consolidation
        consolidated = self._consolidate_memory()
        if consolidated > 0:
            result.actions_performed.append(TickAction.CONSOLIDATE.value)
            result.consolidation_count = consolidated
        
        # 2. Ledger audit
        issues = self._audit_ledger()
        if issues:
            result.actions_performed.append(TickAction.AUDIT_LEDGER.value)
            result.ledger_issues = issues
        
        # 3. Optional rollouts
        if enable_rollouts:
            result.actions_performed.append(TickAction.RUN_ROLLOUTS.value)
            # Rollout would be performed here if enabled
        
        # 4. Proactive reminders (gated)
        if enable_proactive:
            tension = self._compute_tension()
            if self.proactive_gate.should_remind(tension):
                result.actions_performed.append(TickAction.PROACTIVE_REMINDER.value)
                result.reminder_sent = True
                self.proactive_gate.record_reminder()
        
        result.duration_ms = (time.time() - start_time) * 1000
        self._last_tick = datetime.now(timezone.utc).isoformat()
        self.history.append(result)
        
        return result
    
    def _consolidate_memory(self) -> int:
        """
        Consolidate memory (cleanup, summarization).
        
        Returns:
            Number of episodes consolidated
        """
        if not self.episode_store:
            return 0
        
        # Cleanup expired episodes
        removed = self.episode_store.cleanup_expired()
        
        # Could add summarization here
        return removed
    
    def _audit_ledger(self) -> List[str]:
        """
        Audit the relationship ledger for issues.
        
        Returns:
            List of issues found
        """
        issues = []
        
        # Check for unresolved tensions
        drive_err = drive_error(self.drive_state)
        if drive_err > 0.5:
            issues.append(f"high_drive_error: {drive_err:.2f}")
        
        # Check self-model consistency
        if self.self_model:
            # Could add more sophisticated checks
            pass
        
        return issues
    
    def _compute_tension(self) -> float:
        """
        Compute tension level for proactive gating.
        
        Tension is a combination of:
        - Drive error
        - Unresolved issues
        - Time since last interaction
        """
        base_tension = get_drive().drive_error()
        
        # Could add more factors
        return min(1.0, base_tension * 1.5)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current tick status."""
        return {
            "last_tick": self._last_tick,
            "tick_interval": self.tick_interval,
            "history_count": len(self.history),
            "proactive_gate": {
                "current_tension": self.proactive_gate.current_tension,
                "last_reminder": self.proactive_gate.last_reminder,
            },
        }
