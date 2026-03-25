"""
MVP12 Daemon Integration

Integrates CycleEngine into the background daemon process.
Supports idle-triggered developmental cycles.

All outputs are sandboxed and must go through Governor v2.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .cycle_engine import CycleEngine
from .hypothesis_generator import HypothesisGenerator
from .candidate_evaluator import CandidateEvaluator
from .cycle_memory import CycleMemory
from .models import CycleTrigger, CycleResult


@dataclass
class DaemonCycleConfig:
    """Configuration for daemon developmental cycles."""

    idle_threshold: float = 60.0  # Seconds of idle time to trigger cycle
    min_cycle_interval: float = 30.0  # Minimum seconds between cycles
    max_candidates_per_cycle: int = 5
    enable_metrics: bool = True
    storage_path: Optional[str] = None


@dataclass
class DaemonCycleResult:
    """Result of a daemon developmental cycle execution."""

    success: bool
    cycle_id: Optional[str] = None
    trigger: Optional[str] = None
    candidates_generated: int = 0
    candidates_approved: int = 0
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class DevelopmentalCycleDaemon:
    """
    Daemon integration for developmental cycles.

    Runs developmental cycles when the system is idle or other triggers fire.
    All outputs are sandboxed candidates that must go through Governor v2.
    """

    def __init__(
        self,
        config: Optional[DaemonCycleConfig] = None,
        seed: Optional[int] = None,
    ):
        self.config = config or DaemonCycleConfig()

        # Initialize components
        self.cycle_engine = CycleEngine(
            seed=seed,
            idle_threshold=self.config.idle_threshold,
        )
        self.hypothesis_generator = HypothesisGenerator(seed=seed)
        self.candidate_evaluator = CandidateEvaluator()
        self.cycle_memory = CycleMemory(storage_path=self.config.storage_path)

        # State tracking
        self._last_activity: Optional[datetime] = None
        self._last_cycle: Optional[datetime] = None
        self._running = False
        self._cycle_history: List[DaemonCycleResult] = []

    def update_activity(self, activity_time: Optional[datetime] = None) -> None:
        """Record user activity to reset idle timer."""
        self._last_activity = activity_time or datetime.utcnow()

    def get_idle_time(self) -> float:
        """Get seconds since last user activity."""
        if self._last_activity is None:
            return 0.0
        elapsed = (datetime.utcnow() - self._last_activity).total_seconds()
        return max(0.0, elapsed)

    def should_run_cycle(self) -> bool:
        """Check if conditions are met to run a developmental cycle."""
        # Check idle threshold
        idle_time = self.get_idle_time()
        if idle_time < self.config.idle_threshold:
            return False

        # Check minimum interval between cycles
        if self._last_cycle is not None:
            elapsed = (datetime.utcnow() - self._last_cycle).total_seconds()
            if elapsed < self.config.min_cycle_interval:
                return False

        return True

    def run_developmental_cycle(
        self,
        state_snapshot: Optional[Dict[str, Any]] = None,
        unresolved_tensions: Optional[List[Dict[str, Any]]] = None,
        long_term_goals: Optional[List[Dict[str, Any]]] = None,
    ) -> DaemonCycleResult:
        """
        Execute a complete developmental cycle.

        Pipeline:
        1. CycleEngine.start_cycle() -> creates context
        2. HypothesisGenerator.generate() -> creates candidates
        3. CandidateEvaluator.evaluate_batch() -> scores candidates
        4. CycleMemory.store_cycle() -> persists results

        Returns:
            DaemonCycleResult with cycle outcome
        """
        result = DaemonCycleResult(success=False)
        self._last_cycle = datetime.utcnow()

        try:
            # Determine trigger based on conditions
            triggers = self.cycle_engine.check_triggers(
                idle_time=self.get_idle_time(),
                unresolved_tensions=unresolved_tensions,
                long_term_goals=long_term_goals,
            )

            if not triggers:
                # Default to idle trigger if conditions met
                if self.should_run_cycle():
                    trigger = CycleTrigger.IDLE
                else:
                    result.error = "No cycle triggers active"
                    return result
            else:
                trigger = triggers[0]  # Use highest priority trigger

            result.trigger = trigger.value

            # Step 1: Start cycle
            context = self.cycle_engine.start_cycle(
                trigger=trigger,
                state_snapshot=state_snapshot,
            )
            result.cycle_id = context.cycle_id

            # Step 2: Generate candidates
            candidates = self.hypothesis_generator.generate(
                context=context,
                state_snapshot=state_snapshot,
                max_candidates=self.config.max_candidates_per_cycle,
            )
            result.candidates_generated = len(candidates)

            # Step 3: Evaluate candidates
            evaluations = self.candidate_evaluator.evaluate_batch(
                candidates=candidates,
                context=state_snapshot,
            )

            # Count approved candidates
            approved_count = 0
            for candidate, eval_result in zip(candidates, evaluations):
                if eval_result.approved_for_pool:
                    approved_count += 1
                    self.cycle_memory.add_to_pool(candidate, eval_result.score)

            result.candidates_approved = approved_count

            # Step 4: Complete and store cycle
            cycle_result = self.cycle_engine.complete_cycle(
                context=context,
                candidates=candidates,
            )
            self.cycle_memory.store_cycle(cycle_result)

            result.success = True

        except Exception as e:
            result.error = str(e)

        # Track history
        self._cycle_history.append(result)
        if len(self._cycle_history) > 100:
            self._cycle_history = self._cycle_history[-100:]

        return result

    def get_cycle_callback(self) -> Callable[[], DaemonCycleResult]:
        """
        Get a callback function for DMN tick integration.

        Usage:
            dmn_tick = DMNTick(...)
            dmn_tick.tick(
                rollout_fn=dev_daemon.get_cycle_callback()
            )
        """
        def _cycle_callback() -> Dict[str, Any]:
            result = self.run_developmental_cycle()
            return {
                "success": result.success,
                "cycle_id": result.cycle_id,
                "trigger": result.trigger,
                "candidates_generated": result.candidates_generated,
                "candidates_approved": result.candidates_approved,
                "error": result.error,
            }

        return _cycle_callback

    def get_pending_candidates(self) -> List[Dict[str, Any]]:
        """Get all pending candidates from the pool."""
        return self.cycle_memory.get_pending_candidates()

    def get_cycle_history(self, limit: int = 10) -> List[DaemonCycleResult]:
        """Get recent cycle history."""
        return self._cycle_history[-limit:]

    def get_metrics(self) -> Dict[str, Any]:
        """Get daemon cycle metrics."""
        total = len(self._cycle_history)
        successful = sum(1 for r in self._cycle_history if r.success)
        failed = total - successful

        total_candidates = sum(r.candidates_generated for r in self._cycle_history)
        total_approved = sum(r.candidates_approved for r in self._cycle_history)

        return {
            "total_cycles": total,
            "successful_cycles": successful,
            "failed_cycles": failed,
            "cycle_success_rate": successful / total if total > 0 else 1.0,
            "total_candidates_generated": total_candidates,
            "total_candidates_approved": total_approved,
            "pending_pool_size": len(self.get_pending_candidates()),
            "last_cycle": self._last_cycle.isoformat() if self._last_cycle else None,
            "idle_time": self.get_idle_time(),
        }

    def reset(self, seed: Optional[int] = None) -> None:
        """Reset daemon state."""
        self.cycle_engine.reset(seed=seed)
        self._last_activity = None
        self._last_cycle = None
        self._cycle_history.clear()


def create_dev_daemon(
    idle_threshold: float = 60.0,
    min_cycle_interval: float = 30.0,
    max_candidates_per_cycle: int = 5,
    seed: Optional[int] = None,
    storage_path: Optional[str] = None,
) -> DevelopmentalCycleDaemon:
    """Factory function to create a developmental cycle daemon."""
    config = DaemonCycleConfig(
        idle_threshold=idle_threshold,
        min_cycle_interval=min_cycle_interval,
        max_candidates_per_cycle=max_candidates_per_cycle,
        storage_path=storage_path,
    )
    return DevelopmentalCycleDaemon(config=config, seed=seed)
