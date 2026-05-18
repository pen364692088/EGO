"""
MVP12 Cycle Engine

Generates internal reasoning cycles independent of user input.
All cycles are deterministic and replayable.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from .models import (
    CycleContext,
    CycleResult,
    CycleTrigger,
    Candidate,
)


class CycleEngine:
    """
    Engine for generating internal developmental cycles.

    Each cycle produces candidates that are sandboxed and must go through
    Governor v2 for approval before any action is taken.
    """

    def __init__(
        self,
        seed: Optional[int] = None,
        idle_threshold: float = 60.0,
        tension_threshold: float = 0.7,
    ):
        self.seed = seed or random.randint(0, 2**32 - 1)
        self.rng = random.Random(self.seed)
        self.idle_threshold = idle_threshold
        self.tension_threshold = tension_threshold
        self._cycle_count = 0
        self._pending_cycles: List[CycleContext] = []

    def check_triggers(
        self,
        idle_time: float = 0.0,
        unresolved_tensions: Optional[List[Dict[str, Any]]] = None,
        long_term_goals: Optional[List[Dict[str, Any]]] = None,
    ) -> List[CycleTrigger]:
        """Check which cycle triggers are active."""
        triggers = []

        # Idle trigger
        if idle_time > self.idle_threshold:
            triggers.append(CycleTrigger.IDLE)

        # Unresolved tension trigger
        if unresolved_tensions:
            max_tension = max(
                (t.get("intensity", 0) for t in unresolved_tensions),
                default=0
            )
            if max_tension > self.tension_threshold:
                triggers.append(CycleTrigger.UNRESOLVED_TENSION)

        # Long-term goal trigger
        if long_term_goals:
            for goal in long_term_goals:
                if goal.get("pressure", 0) > 0.5:
                    triggers.append(CycleTrigger.LONG_TERM_GOAL)
                    break

        return triggers

    def start_cycle(
        self,
        trigger: CycleTrigger,
        state_snapshot: Optional[Dict[str, Any]] = None,
        parent_cycle: Optional[str] = None,
    ) -> CycleContext:
        """Start a new developmental cycle."""
        self._cycle_count += 1
        cycle_seed = self.rng.randint(0, 2**32 - 1)

        context = CycleContext(
            seed=cycle_seed,
            trigger=trigger,
            parent_cycle=parent_cycle,
            state_snapshot=state_snapshot or {},
        )

        self._pending_cycles.append(context)
        return context

    def complete_cycle(
        self,
        context: CycleContext,
        candidates: List[Candidate],
        error: Optional[str] = None,
    ) -> CycleResult:
        """Complete a developmental cycle with generated candidates."""
        if context in self._pending_cycles:
            self._pending_cycles.remove(context)

        result = CycleResult(
            context=context,
            candidates=candidates,
            success=error is None,
            error=error,
        )

        return result

    def get_pending_cycles(self) -> List[CycleContext]:
        """Get all pending (incomplete) cycles."""
        return self._pending_cycles.copy()

    def get_cycle_count(self) -> int:
        """Get total number of cycles started."""
        return self._cycle_count

    def reset(self, seed: Optional[int] = None) -> None:
        """Reset the engine state."""
        self.seed = seed or random.randint(0, 2**32 - 1)
        self.rng = random.Random(self.seed)
        self._cycle_count = 0
        self._pending_cycles.clear()
