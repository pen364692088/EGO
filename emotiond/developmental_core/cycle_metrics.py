"""
MVP12 Cycle Metrics

Collects and persists metrics for developmental cycle monitoring.
Outputs to artifacts/mvp12/sandbox_metrics.json
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class CycleMetrics:
    """Metrics for a single cycle."""

    cycle_id: str
    success: bool
    trigger: str
    candidates_generated: int
    candidates_approved: int
    trace_hash: str
    replay_verified: bool = False
    sandbox_violations: int = 0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class SandboxMetrics:
    """
    Aggregate metrics for the developmental sandbox.

    Tracks overall health and performance of the developmental core.
    """

    total_cycles: int = 0
    successful_cycles: int = 0
    failed_cycles: int = 0
    cycle_success_rate: float = 1.0
    replay_consistency: float = 1.0
    candidate_pool_size: int = 0
    avg_candidates_per_cycle: float = 0.0
    sandbox_violations: int = 0

    # Extended metrics
    total_candidates_generated: int = 0
    total_candidates_approved: int = 0
    trigger_breakdown: Dict[str, int] = field(default_factory=dict)
    last_updated: str = ""


class CycleMetricsCollector:
    """
    Collects and persists cycle metrics.

    All metrics are written to artifacts/mvp12/sandbox_metrics.json
    """

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path or "artifacts/mvp12")
        self.metrics_file = self.storage_path / "sandbox_metrics.json"
        self.history_file = self.storage_path / "metrics_history.jsonl"

        # Ensure directory exists
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Initialize
        self._cycle_metrics: List[CycleMetrics] = []
        self._replay_verifications: List[Dict[str, Any]] = []
        self._sandbox_violations: List[Dict[str, Any]] = []

        self._load()

    def _load(self) -> None:
        """Load existing metrics from storage."""
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file, "r") as f:
                    data = json.load(f)
                    self._sandbox_violations = data.get("sandbox_violations_log", [])
            except (json.JSONDecodeError, IOError):
                pass

    def _save(self) -> None:
        """Persist metrics to storage."""
        metrics = self.get_aggregate_metrics()
        metrics["sandbox_violations_log"] = self._sandbox_violations[-100:]  # Keep last 100

        with open(self.metrics_file, "w") as f:
            json.dump(metrics, f, indent=2)

    def record_cycle(
        self,
        cycle_id: str,
        success: bool,
        trigger: str,
        candidates_generated: int,
        candidates_approved: int,
        trace_hash: str,
    ) -> None:
        """Record metrics for a completed cycle."""
        metrics = CycleMetrics(
            cycle_id=cycle_id,
            success=success,
            trigger=trigger,
            candidates_generated=candidates_generated,
            candidates_approved=candidates_approved,
            trace_hash=trace_hash,
        )

        self._cycle_metrics.append(metrics)
        self._save()

        # Append to history
        self._append_history(metrics)

    def record_replay_verification(
        self,
        cycle_id: str,
        verified: bool,
        error: Optional[str] = None,
    ) -> None:
        """Record a replay verification result."""
        self._replay_verifications.append({
            "cycle_id": cycle_id,
            "verified": verified,
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
        })
        self._save()

    def record_sandbox_violation(
        self,
        cycle_id: str,
        violation_type: str,
        details: Dict[str, Any],
    ) -> None:
        """Record a sandbox violation."""
        violation = {
            "cycle_id": cycle_id,
            "violation_type": violation_type,
            "details": details,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._sandbox_violations.append(violation)
        self._save()

    def update_pool_size(self, size: int) -> None:
        """Update the candidate pool size metric."""
        # This will be reflected in get_aggregate_metrics
        self._save()

    def get_aggregate_metrics(self) -> Dict[str, Any]:
        """Calculate and return aggregate metrics."""
        total = len(self._cycle_metrics)
        successful = sum(1 for m in self._cycle_metrics if m.success)
        failed = total - successful

        total_candidates = sum(m.candidates_generated for m in self._cycle_metrics)
        total_approved = sum(m.candidates_approved for m in self._cycle_metrics)

        # Calculate replay consistency
        verified_count = sum(
            1 for v in self._replay_verifications if v.get("verified", False)
        )
        total_verifications = len(self._replay_verifications)
        replay_consistency = verified_count / total_verifications if total_verifications > 0 else 1.0

        # Trigger breakdown
        trigger_breakdown: Dict[str, int] = {}
        for m in self._cycle_metrics:
            trigger_breakdown[m.trigger] = trigger_breakdown.get(m.trigger, 0) + 1

        # Sandbox violations from cycles
        cycle_violations = sum(m.sandbox_violations for m in self._cycle_metrics)
        total_violations = cycle_violations + len(self._sandbox_violations)

        return {
            "total_cycles": total,
            "successful_cycles": successful,
            "failed_cycles": failed,
            "cycle_success_rate": successful / total if total > 0 else 1.0,
            "replay_consistency": replay_consistency,
            "candidate_pool_size": 0,  # Updated externally
            "avg_candidates_per_cycle": total_candidates / total if total > 0 else 0.0,
            "sandbox_violations": total_violations,
            "total_candidates_generated": total_candidates,
            "total_candidates_approved": total_approved,
            "trigger_breakdown": trigger_breakdown,
            "last_updated": datetime.utcnow().isoformat(),
        }

    def _append_history(self, metrics: CycleMetrics) -> None:
        """Append cycle metrics to history log."""
        try:
            with open(self.history_file, "a") as f:
                f.write(json.dumps({
                    "cycle_id": metrics.cycle_id,
                    "success": metrics.success,
                    "trigger": metrics.trigger,
                    "candidates_generated": metrics.candidates_generated,
                    "candidates_approved": metrics.candidates_approved,
                    "trace_hash": metrics.trace_hash,
                    "timestamp": metrics.timestamp,
                }) + "\n")
        except IOError:
            pass

    def get_metrics(self) -> SandboxMetrics:
        """Get metrics as SandboxMetrics dataclass."""
        data = self.get_aggregate_metrics()
        return SandboxMetrics(
            total_cycles=data["total_cycles"],
            successful_cycles=data["successful_cycles"],
            failed_cycles=data["failed_cycles"],
            cycle_success_rate=data["cycle_success_rate"],
            replay_consistency=data["replay_consistency"],
            candidate_pool_size=data["candidate_pool_size"],
            avg_candidates_per_cycle=data["avg_candidates_per_cycle"],
            sandbox_violations=data["sandbox_violations"],
            total_candidates_generated=data["total_candidates_generated"],
            total_candidates_approved=data["total_candidates_approved"],
            trigger_breakdown=data["trigger_breakdown"],
            last_updated=data["last_updated"],
        )

    def get_recent_cycles(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent cycle metrics."""
        return [
            {
                "cycle_id": m.cycle_id,
                "success": m.success,
                "trigger": m.trigger,
                "candidates_generated": m.candidates_generated,
                "candidates_approved": m.candidates_approved,
                "timestamp": m.timestamp,
            }
            for m in self._cycle_metrics[-limit:]
        ]

    def get_violations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent sandbox violations."""
        return self._sandbox_violations[-limit:]

    def reset(self) -> None:
        """Reset all metrics."""
        self._cycle_metrics.clear()
        self._replay_verifications.clear()
        self._sandbox_violations.clear()
        self._save()


def create_metrics_collector(storage_path: Optional[str] = None) -> CycleMetricsCollector:
    """Factory function to create a metrics collector."""
    return CycleMetricsCollector(storage_path=storage_path)
