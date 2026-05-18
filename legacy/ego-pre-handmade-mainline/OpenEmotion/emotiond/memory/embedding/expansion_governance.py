"""
Expansion Governance for High-Quality Retrieval Mode.

Determines when scope expansion is allowed.
Capability Owner: OpenEmotion

v6e: Scope Expansion Governance
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from emotiond.memory.embedding.observation_window import (
    ObservationWindow,
    ObservationThresholds,
)


class ExpansionVerdict(str, Enum):
    """Verdict for scope expansion decision."""
    KEEP_SAME_SCOPE = "keep_same_scope"
    EXPAND_ONE_MORE_SCENARIO = "expand_one_more_scenario"
    SHRINK_OR_ROLLBACK = "shrink_or_rollback"


@dataclass
class ExpansionBlocker:
    """A blocker preventing expansion."""
    category: str
    message: str
    threshold: Any
    actual: Any
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "message": self.message,
            "threshold": self.threshold,
            "actual": self.actual,
        }


@dataclass
class ExpansionDecision:
    """Full expansion decision."""
    verdict: ExpansionVerdict
    blockers: List[ExpansionBlocker] = field(default_factory=list)
    rationale: str = ""
    next_allowed_action: str = ""
    timestamp: float = field(default_factory=time.time)
    metrics_summary: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "blockers": [b.to_dict() for b in self.blockers],
            "rationale": self.rationale,
            "next_allowed_action": self.next_allowed_action,
            "timestamp": self.timestamp,
            "metrics_summary": self.metrics_summary,
        }


class ExpansionGovernor:
    """Governor for scope expansion decisions.
    
    Capability Owner: OpenEmotion
    
    Determines when to:
    - Keep current scope
    - Expand to one more scenario
    - Shrink or rollback
    """
    
    # Fixed whitelist - not changeable in v6e
    FIXED_WHITELIST = [
        "memory_search_hard_query",
        "narrative_recall_ambiguous_query",
        "long_context_semantic_lookup",
    ]
    
    # Candidate scenarios for expansion (if verdict allows)
    CANDIDATE_SCENARIOS = [
        "complex_semantic_reasoning",
        "multi_turn_context_recall",
    ]
    
    def __init__(
        self,
        observation_window: Optional[ObservationWindow] = None,
        thresholds: Optional[ObservationThresholds] = None,
    ):
        self.observation_window = observation_window or ObservationWindow(thresholds)
        self.thresholds = self.observation_window.thresholds
    
    def evaluate_scope_expansion(self) -> ExpansionDecision:
        """Evaluate whether scope expansion is allowed."""
        blockers: List[ExpansionBlocker] = []
        
        # Get metrics
        metrics = self.observation_window.get_aggregated_metrics()
        readiness = self.observation_window.check_readiness()
        
        # Check for rollback conditions (highest priority)
        rollback_blockers = self._check_rollback_conditions(metrics)
        if rollback_blockers:
            return ExpansionDecision(
                verdict=ExpansionVerdict.SHRINK_OR_ROLLBACK,
                blockers=rollback_blockers,
                rationale="Critical issues detected - rollback required",
                next_allowed_action="Investigate and fix issues before any expansion",
                metrics_summary=metrics,
            )
        
        # Check expansion conditions
        expansion_blockers = self._check_expansion_conditions(metrics, readiness)
        
        if expansion_blockers:
            # Not ready for expansion
            return ExpansionDecision(
                verdict=ExpansionVerdict.KEEP_SAME_SCOPE,
                blockers=expansion_blockers,
                rationale="Expansion criteria not met - continue observation",
                next_allowed_action="Continue collecting data in current whitelist scenarios",
                metrics_summary=metrics,
            )
        
        # All checks passed - ready for expansion
        return ExpansionDecision(
            verdict=ExpansionVerdict.EXPAND_ONE_MORE_SCENARIO,
            blockers=[],
            rationale="All expansion criteria met - ready to add one more scenario",
            next_allowed_action=f"Consider adding scenario: {self.CANDIDATE_SCENARIOS[0]}",
            metrics_summary=metrics,
        )
    
    def _check_rollback_conditions(self, metrics: Dict[str, Any]) -> List[ExpansionBlocker]:
        """Check conditions that require rollback."""
        blockers = []
        
        total_samples = metrics["total_sample_size"]
        if total_samples == 0:
            return blockers  # No data yet, can't determine rollback
        
        # Check fallback rate (rollback threshold)
        fallback_rate = metrics["total_fallback_rate"]
        if fallback_rate > self.thresholds.rollback_fallback_rate:
            blockers.append(ExpansionBlocker(
                category="fallback_rate",
                message=f"Fallback rate {fallback_rate:.1%} exceeds rollback threshold {self.thresholds.rollback_fallback_rate:.1%}",
                threshold=self.thresholds.rollback_fallback_rate,
                actual=fallback_rate,
            ))
        
        # Check p95 latency
        for scenario_name, obs in metrics.get("scenario_metrics", {}).items():
            p95 = obs.get("p95_latency_ms")
            if p95 and p95 > self.thresholds.rollback_p95_latency_ms:
                blockers.append(ExpansionBlocker(
                    category="latency",
                    message=f"P95 latency {p95:.1f}ms in {scenario_name} exceeds rollback threshold {self.thresholds.rollback_p95_latency_ms:.1f}ms",
                    threshold=self.thresholds.rollback_p95_latency_ms,
                    actual=p95,
                ))
        
        # Check provider health (only for scenarios with data)
        for scenario_name, obs in metrics.get("scenario_metrics", {}).items():
            request_count = obs.get("request_count", 0)
            if request_count == 0:
                continue  # Skip scenarios with no data
            
            health_rate = obs.get("provider_health_rate", 1.0)
            if health_rate < self.thresholds.rollback_min_provider_health_rate:
                blockers.append(ExpansionBlocker(
                    category="provider_health",
                    message=f"Provider health rate {health_rate:.1%} in {scenario_name} below rollback threshold {self.thresholds.rollback_min_provider_health_rate:.1%}",
                    threshold=self.thresholds.rollback_min_provider_health_rate,
                    actual=health_rate,
                ))
        
        return blockers
    
    def _check_expansion_conditions(
        self, 
        metrics: Dict[str, Any],
        readiness: Dict[str, Any],
    ) -> List[ExpansionBlocker]:
        """Check conditions for expansion readiness."""
        blockers = []
        
        # Total sample size
        total_samples = metrics["total_sample_size"]
        if total_samples < self.thresholds.min_total_sample_size:
            blockers.append(ExpansionBlocker(
                category="sample_size",
                message=f"Total sample size {total_samples} below threshold {self.thresholds.min_total_sample_size}",
                threshold=self.thresholds.min_total_sample_size,
                actual=total_samples,
            ))
        
        # Observation rounds
        rounds = metrics["rounds_observed"]
        if rounds < self.thresholds.min_observation_rounds:
            blockers.append(ExpansionBlocker(
                category="observation_rounds",
                message=f"Only {rounds} observation rounds, need {self.thresholds.min_observation_rounds}",
                threshold=self.thresholds.min_observation_rounds,
                actual=rounds,
            ))
        
        # Per-scenario sample size
        for scenario_name in self.FIXED_WHITELIST:
            obs = metrics.get("scenario_metrics", {}).get(scenario_name, {})
            count = obs.get("request_count", 0)
            if count < self.thresholds.min_sample_size_per_scenario:
                blockers.append(ExpansionBlocker(
                    category="per_scenario_samples",
                    message=f"Scenario {scenario_name}: {count} samples < {self.thresholds.min_sample_size_per_scenario}",
                    threshold=self.thresholds.min_sample_size_per_scenario,
                    actual=count,
                ))
        
        # Fallback rate
        fallback_rate = metrics["total_fallback_rate"]
        if fallback_rate > self.thresholds.max_fallback_rate:
            blockers.append(ExpansionBlocker(
                category="fallback_rate",
                message=f"Fallback rate {fallback_rate:.1%} exceeds threshold {self.thresholds.max_fallback_rate:.1%}",
                threshold=self.thresholds.max_fallback_rate,
                actual=fallback_rate,
            ))
        
        # Wrong user triggers
        total_wrong_user = sum(
            obs.get("wrong_user_guard_trigger_count", 0)
            for obs in metrics.get("scenario_metrics", {}).values()
        )
        if total_wrong_user > self.thresholds.max_wrong_user_guard_trigger:
            blockers.append(ExpansionBlocker(
                category="wrong_user",
                message=f"Wrong user triggers: {total_wrong_user} > {self.thresholds.max_wrong_user_guard_trigger}",
                threshold=self.thresholds.max_wrong_user_guard_trigger,
                actual=total_wrong_user,
            ))
        
        # P95 latency
        for scenario_name in self.FIXED_WHITELIST:
            obs = metrics.get("scenario_metrics", {}).get(scenario_name, {})
            p95 = obs.get("p95_latency_ms")
            if p95 and p95 > self.thresholds.max_p95_latency_ms:
                blockers.append(ExpansionBlocker(
                    category="latency",
                    message=f"P95 latency {p95:.1f}ms in {scenario_name} exceeds threshold {self.thresholds.max_p95_latency_ms:.1f}ms",
                    threshold=self.thresholds.max_p95_latency_ms,
                    actual=p95,
                ))
        
        # Provider health (only for scenarios with data)
        for scenario_name in self.FIXED_WHITELIST:
            obs = metrics.get("scenario_metrics", {}).get(scenario_name, {})
            request_count = obs.get("request_count", 0)
            if request_count == 0:
                continue  # Skip scenarios with no data
            
            health_rate = obs.get("provider_health_rate", 0.0)
            if health_rate < self.thresholds.min_provider_health_rate:
                blockers.append(ExpansionBlocker(
                    category="provider_health",
                    message=f"Provider health rate {health_rate:.1%} in {scenario_name} below threshold {self.thresholds.min_provider_health_rate:.1%}",
                    threshold=self.thresholds.min_provider_health_rate,
                    actual=health_rate,
                ))
        
        return blockers
    
    def get_current_whitelist(self) -> List[str]:
        """Get current fixed whitelist."""
        return self.FIXED_WHITELIST.copy()
    
    def get_candidate_scenarios(self) -> List[str]:
        """Get candidate scenarios for future expansion."""
        return self.CANDIDATE_SCENARIOS.copy()
    
    def export_decision(self, path: Optional[str] = None) -> str:
        """Export expansion decision to JSON."""
        decision = self.evaluate_scope_expansion()
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "decision": decision.to_dict(),
            "current_whitelist": self.get_current_whitelist(),
            "candidate_scenarios": self.get_candidate_scenarios(),
            "thresholds": self.thresholds.to_dict(),
        }
        
        output_path = Path(path) if path else None
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(f"expansion_decision_{timestamp}.json")
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        
        return str(output_path)


def evaluate_scope_expansion(
    observation_window: Optional[ObservationWindow] = None,
) -> ExpansionDecision:
    """Convenience function to evaluate expansion."""
    governor = ExpansionGovernor(observation_window)
    return governor.evaluate_scope_expansion()
