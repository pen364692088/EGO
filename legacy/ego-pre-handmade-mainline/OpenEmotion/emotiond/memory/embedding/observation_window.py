"""
Observation Window for Scope Expansion.

Tracks multi-round observation for expansion decisions.
Capability Owner: OpenEmotion

v6e: Scope Expansion Governance
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ObservationThresholds:
    """Thresholds for expansion decision."""
    # Sample size requirements
    min_total_sample_size: int = 60
    min_sample_size_per_scenario: int = 15
    
    # Observation rounds
    min_observation_rounds: int = 3
    
    # Quality metrics
    max_fallback_rate: float = 0.05  # 5%
    max_wrong_user_guard_trigger: int = 0
    max_p95_latency_ms: float = 100.0
    min_provider_health_rate: float = 0.98  # 98%
    min_quality_gain: float = 0.10  # 10%
    
    # Rollback thresholds
    rollback_fallback_rate: float = 0.10  # 10%
    rollback_p95_latency_ms: float = 300.0
    rollback_min_provider_health_rate: float = 0.95  # 95%
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "min_total_sample_size": self.min_total_sample_size,
            "min_sample_size_per_scenario": self.min_sample_size_per_scenario,
            "min_observation_rounds": self.min_observation_rounds,
            "max_fallback_rate": self.max_fallback_rate,
            "max_wrong_user_guard_trigger": self.max_wrong_user_guard_trigger,
            "max_p95_latency_ms": self.max_p95_latency_ms,
            "min_provider_health_rate": self.min_provider_health_rate,
            "min_quality_gain": self.min_quality_gain,
            "rollback_fallback_rate": self.rollback_fallback_rate,
            "rollback_p95_latency_ms": self.rollback_p95_latency_ms,
            "rollback_min_provider_health_rate": self.rollback_min_provider_health_rate,
        }


@dataclass
class ScenarioObservation:
    """Observation data for a single scenario."""
    scenario_name: str
    request_count: int = 0
    success_count: int = 0
    fallback_count: int = 0
    wrong_user_guard_trigger_count: int = 0
    latencies: List[float] = field(default_factory=list)
    quality_gain_signal: float = 0.0
    provider_health_success: int = 0
    provider_health_total: int = 0
    
    @property
    def fallback_rate(self) -> float:
        if self.request_count == 0:
            return 0.0
        return self.fallback_count / self.request_count
    
    @property
    def avg_latency_ms(self) -> Optional[float]:
        if not self.latencies:
            return None
        return sum(self.latencies) / len(self.latencies)
    
    @property
    def p95_latency_ms(self) -> Optional[float]:
        if not self.latencies:
            return None
        sorted_latencies = sorted(self.latencies)
        p95_idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[p95_idx] if p95_idx < len(sorted_latencies) else sorted_latencies[-1]
    
    @property
    def provider_health_rate(self) -> float:
        if self.provider_health_total == 0:
            return 0.0
        return self.provider_health_success / self.provider_health_total
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "request_count": self.request_count,
            "success_count": self.success_count,
            "fallback_count": self.fallback_count,
            "fallback_rate": round(self.fallback_rate, 4),
            "p95_latency_ms": round(self.p95_latency_ms, 2) if self.p95_latency_ms else None,
            "avg_latency_ms": round(self.avg_latency_ms, 2) if self.avg_latency_ms else None,
            "wrong_user_guard_trigger_count": self.wrong_user_guard_trigger_count,
            "quality_gain_signal": round(self.quality_gain_signal, 4),
            "provider_health_rate": round(self.provider_health_rate, 4),
        }


@dataclass
class ObservationRound:
    """Single observation round."""
    round_id: int
    timestamp: float
    scenarios: Dict[str, ScenarioObservation] = field(default_factory=dict)
    total_sample_size: int = 0
    verdict: str = "pending"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_id": self.round_id,
            "timestamp": self.timestamp,
            "total_sample_size": self.total_sample_size,
            "verdict": self.verdict,
            "scenarios": {k: v.to_dict() for k, v in self.scenarios.items()},
        }


class ObservationWindow:
    """Manages observation window for scope expansion decisions.
    
    Capability Owner: OpenEmotion
    
    Tracks:
    - Multiple observation rounds
    - Per-scenario metrics
    - Expansion readiness
    """
    
    WHITELIST_SCENARIOS = [
        "memory_search_hard_query",
        "narrative_recall_ambiguous_query", 
        "long_context_semantic_lookup",
    ]
    
    def __init__(
        self,
        thresholds: Optional[ObservationThresholds] = None,
    ):
        self.thresholds = thresholds or ObservationThresholds()
        self.rounds: List[ObservationRound] = []
        self.current_round: Optional[ObservationRound] = None
        self._round_counter = 0
        
    def start_round(self) -> ObservationRound:
        """Start a new observation round."""
        self._round_counter += 1
        self.current_round = ObservationRound(
            round_id=self._round_counter,
            timestamp=time.time(),
        )
        
        # Initialize scenarios
        for scenario in self.WHITELIST_SCENARIOS:
            self.current_round.scenarios[scenario] = ScenarioObservation(scenario_name=scenario)
        
        return self.current_round
    
    def record_observation(
        self,
        scenario_name: str,
        success: bool,
        latency_ms: float,
        fallback: bool = False,
        wrong_user_trigger: bool = False,
        quality_gain: float = 0.0,
        provider_healthy: bool = True,
    ) -> None:
        """Record an observation for a scenario."""
        if not self.current_round:
            self.start_round()
        
        if scenario_name not in self.current_round.scenarios:
            self.current_round.scenarios[scenario_name] = ScenarioObservation(scenario_name=scenario_name)
        
        obs = self.current_round.scenarios[scenario_name]
        obs.request_count += 1
        self.current_round.total_sample_size += 1
        
        if success:
            obs.success_count += 1
        if fallback:
            obs.fallback_count += 1
        if wrong_user_trigger:
            obs.wrong_user_guard_trigger_count += 1
        
        obs.latencies.append(latency_ms)
        obs.quality_gain_signal = quality_gain  # Use latest
        obs.provider_health_total += 1
        if provider_healthy:
            obs.provider_health_success += 1
    
    def end_round(self, verdict: str = "observed") -> ObservationRound:
        """End current observation round."""
        if not self.current_round:
            raise ValueError("No active observation round")
        
        self.current_round.verdict = verdict
        self.rounds.append(self.current_round)
        completed = self.current_round
        self.current_round = None
        return completed
    
    def get_aggregated_metrics(self) -> Dict[str, Any]:
        """Get aggregated metrics across all rounds."""
        # Aggregate by scenario
        scenario_totals: Dict[str, ScenarioObservation] = {}
        
        for round_data in self.rounds:
            for scenario_name, obs in round_data.scenarios.items():
                if scenario_name not in scenario_totals:
                    scenario_totals[scenario_name] = ScenarioObservation(scenario_name=scenario_name)
                
                total = scenario_totals[scenario_name]
                total.request_count += obs.request_count
                total.success_count += obs.success_count
                total.fallback_count += obs.fallback_count
                total.wrong_user_guard_trigger_count += obs.wrong_user_guard_trigger_count
                total.latencies.extend(obs.latencies)
                total.provider_health_success += obs.provider_health_success
                total.provider_health_total += obs.provider_health_total
        
        total_samples = sum(r.total_sample_size for r in self.rounds)
        total_fallbacks = sum(
            s.fallback_count for s in scenario_totals.values()
        )
        
        return {
            "total_sample_size": total_samples,
            "rounds_observed": len(self.rounds),
            "scenarios_covered": list(scenario_totals.keys()),
            "total_fallback_count": total_fallbacks,
            "total_fallback_rate": round(total_fallbacks / total_samples, 4) if total_samples > 0 else 0,
            "scenario_metrics": {k: v.to_dict() for k, v in scenario_totals.items()},
        }
    
    def check_readiness(self) -> Dict[str, Any]:
        """Check if ready for scope expansion."""
        metrics = self.get_aggregated_metrics()
        
        checks = []
        blockers = []
        
        # Check total sample size
        total_size = metrics["total_sample_size"]
        check = {
            "name": "total_sample_size",
            "threshold": self.thresholds.min_total_sample_size,
            "actual": total_size,
            "passed": total_size >= self.thresholds.min_total_sample_size,
        }
        checks.append(check)
        if not check["passed"]:
            blockers.append(f"Total sample size {total_size} < {self.thresholds.min_total_sample_size}")
        
        # Check observation rounds
        rounds = len(self.rounds)
        check = {
            "name": "observation_rounds",
            "threshold": self.thresholds.min_observation_rounds,
            "actual": rounds,
            "passed": rounds >= self.thresholds.min_observation_rounds,
        }
        checks.append(check)
        if not check["passed"]:
            blockers.append(f"Observation rounds {rounds} < {self.thresholds.min_observation_rounds}")
        
        # Check per-scenario sample size
        for scenario_name, obs in metrics["scenario_metrics"].items():
            if scenario_name in self.WHITELIST_SCENARIOS:
                check = {
                    "name": f"sample_size_{scenario_name}",
                    "threshold": self.thresholds.min_sample_size_per_scenario,
                    "actual": obs["request_count"],
                    "passed": obs["request_count"] >= self.thresholds.min_sample_size_per_scenario,
                }
                checks.append(check)
                if not check["passed"]:
                    blockers.append(f"Scenario {scenario_name}: {obs['request_count']} < {self.thresholds.min_sample_size_per_scenario}")
        
        # Check fallback rate
        fallback_rate = metrics["total_fallback_rate"]
        check = {
            "name": "fallback_rate",
            "threshold": self.thresholds.max_fallback_rate,
            "actual": fallback_rate,
            "passed": fallback_rate <= self.thresholds.max_fallback_rate,
        }
        checks.append(check)
        if not check["passed"]:
            blockers.append(f"Fallback rate {fallback_rate:.1%} > {self.thresholds.max_fallback_rate:.1%}")
        
        # Check wrong user triggers
        total_wrong_user = sum(
            obs.get("wrong_user_guard_trigger_count", 0) 
            for obs in metrics["scenario_metrics"].values()
        )
        check = {
            "name": "wrong_user_guard_trigger",
            "threshold": self.thresholds.max_wrong_user_guard_trigger,
            "actual": total_wrong_user,
            "passed": total_wrong_user <= self.thresholds.max_wrong_user_guard_trigger,
        }
        checks.append(check)
        if not check["passed"]:
            blockers.append(f"Wrong user triggers: {total_wrong_user} > {self.thresholds.max_wrong_user_guard_trigger}")
        
        return {
            "checks": checks,
            "blockers": blockers,
            "all_passed": len(blockers) == 0,
        }
    
    def export(self, path: Optional[str] = None) -> str:
        """Export observation window data."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "thresholds": self.thresholds.to_dict(),
            "rounds": [r.to_dict() for r in self.rounds],
            "aggregated": self.get_aggregated_metrics(),
            "readiness": self.check_readiness(),
        }
        
        output_path = Path(path) if path else None
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(f"observation_window_{timestamp}.json")
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        
        return str(output_path)
