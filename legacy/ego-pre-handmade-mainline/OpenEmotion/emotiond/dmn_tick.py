"""
US-707: DMN Tick v0 (Default Mode Network)

Background tick for consolidation, ledger audit, and optional rollouts.
Default: Low frequency (30-120s), gated proactive reminders.
"""
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import time


@dataclass
class TickResult:
    """Result of a DMN tick execution"""
    timestamp: str
    consolidation_done: bool = False
    ledger_audit_done: bool = False
    rollouts_done: bool = False
    proactive_triggered: bool = False
    proactive_message: Optional[str] = None
    tension_level: float = 0.0
    details: Dict = field(default_factory=dict)


class DMNTick:
    """
    Default Mode Network simulation for background processing.
    
    Runs at low frequency to avoid disrupting user interactions.
    Performs consolidation, ledger audit, and optional proactive reminders.
    """
    
    def __init__(
        self,
        interval_seconds: float = 60.0,
        tension_threshold: float = 0.5,
        cooldown_seconds: float = 300.0,
        enable_rollouts: bool = False
    ):
        self.interval_seconds = interval_seconds
        self.tension_threshold = tension_threshold
        self.cooldown_seconds = cooldown_seconds
        self.enable_rollouts = enable_rollouts
        
        self.last_tick: Optional[datetime] = None
        self.last_proactive: Optional[datetime] = None
        self.tick_count = 0
        self.history: List[TickResult] = []
        self.max_history = 100
    
    def should_tick(self) -> bool:
        """Check if enough time has passed since last tick"""
        if self.last_tick is None:
            return True
        
        elapsed = (datetime.now() - self.last_tick).total_seconds()
        return elapsed >= self.interval_seconds
    
    def should_trigger_proactive(self, tension: float) -> bool:
        """Check if proactive reminder should be triggered"""
        if tension < self.tension_threshold:
            return False
        
        if self.last_proactive is None:
            return True
        
        elapsed = (datetime.now() - self.last_proactive).total_seconds()
        return elapsed >= self.cooldown_seconds
    
    def _normalize_rollout_result(self, rollout_result: Any) -> Dict[str, Any]:
        """Normalize rollout output to stable schema.

        Standard shape: {"suggestions": [...], "reason": str, "cycle_refs": [...]}.
        """
        if isinstance(rollout_result, dict):
            suggestions = rollout_result.get("suggestions")
            if suggestions is None:
                # backward-compat fallback for older rollout callbacks
                suggestions = []
                if "pending_tools" in rollout_result:
                    suggestions = [
                        {
                            "type": "tool_request",
                            "value": x,
                            "weight": 0.1,
                        }
                        for x in (rollout_result.get("pending_tools") or [])
                    ]
            return {
                "suggestions": suggestions if isinstance(suggestions, list) else [],
                "reason": str(rollout_result.get("reason", "rollout_fn")),
                "cycle_refs": list(rollout_result.get("cycle_refs") or []),
            }

        if isinstance(rollout_result, list):
            return {
                "suggestions": rollout_result,
                "reason": "rollout_fn",
                "cycle_refs": [],
            }

        return {
            "suggestions": [],
            "reason": "rollout_fn",
            "cycle_refs": [],
        }

    def tick(
        self,
        ledger_tension: float = 0.0,
        consolidation_fn: Optional[Callable] = None,
        audit_fn: Optional[Callable] = None,
        rollout_fn: Optional[Callable] = None
    ) -> TickResult:
        """
        Execute a DMN tick.
        
        Args:
            ledger_tension: Current tension level from ledger audit
            consolidation_fn: Optional consolidation function
            audit_fn: Optional audit function
            rollout_fn: Optional rollout function
        
        Returns:
            TickResult with execution details
        """
        self.tick_count += 1
        self.last_tick = datetime.now()
        
        result = TickResult(
            timestamp=datetime.now().isoformat(),
            tension_level=ledger_tension
        )
        
        # 1. Consolidation (always run if function provided)
        if consolidation_fn:
            try:
                consolidation_fn()
                result.consolidation_done = True
            except Exception as e:
                result.details["consolidation_error"] = str(e)
        
        # 2. Ledger audit
        if audit_fn:
            try:
                audit_result = audit_fn()
                result.ledger_audit_done = True
                result.details["audit_result"] = audit_result
            except Exception as e:
                result.details["audit_error"] = str(e)
        
        # 3. Optional rollouts (if enabled)
        if self.enable_rollouts and rollout_fn:
            try:
                rollout_result = rollout_fn()
                normalized_rollout = self._normalize_rollout_result(rollout_result)
                result.rollouts_done = True
                result.details["rollout_result"] = normalized_rollout
                result.details["suggestions"] = normalized_rollout.get("suggestions", [])
            except Exception as e:
                result.details["rollout_error"] = str(e)
        
        # 4. Proactive reminder check
        if self.should_trigger_proactive(ledger_tension):
            result.proactive_triggered = True
            result.proactive_message = self._generate_proactive_message(ledger_tension)
            self.last_proactive = datetime.now()
        
        # Store in history
        self.history.append(result)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        
        return result
    
    def _generate_proactive_message(self, tension: float) -> str:
        """Generate proactive reminder message based on tension"""
        if tension >= 0.8:
            return "High tension detected. Consider following up on pending commitments."
        elif tension >= 0.6:
            return "Moderate tension. Some commitments may need attention."
        else:
            return "Low-level tension noted. Continue monitoring."
    
    def get_summary(self) -> Dict:
        """Get summary of DMN tick state"""
        return {
            "tick_count": self.tick_count,
            "interval_seconds": self.interval_seconds,
            "last_tick": self.last_tick.isoformat() if self.last_tick else None,
            "last_proactive": self.last_proactive.isoformat() if self.last_proactive else None,
            "tension_threshold": self.tension_threshold,
            "cooldown_seconds": self.cooldown_seconds,
            "enable_rollouts": self.enable_rollouts
        }


def create_dmn_tick(
    interval_seconds: float = 60.0,
    enable_rollouts: bool = False
) -> DMNTick:
    """Factory function to create DMN tick with defaults"""
    return DMNTick(
        interval_seconds=interval_seconds,
        enable_rollouts=enable_rollouts
    )
