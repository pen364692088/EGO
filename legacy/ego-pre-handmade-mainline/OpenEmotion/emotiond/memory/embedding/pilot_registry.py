"""
Pilot Scenario Registry.

Manages pilot candidate scenarios separately from production whitelist.
Capability Owner: OpenEmotion

v6f: Candidate Scenario Pilot + Quality Signal Calibration
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class ScenarioStatus(str, Enum):
    """Status of a scenario."""
    PILOT_CANDIDATE = "pilot_candidate"  # Eligible for pilot
    PILOT_ACTIVE = "pilot_active"  # Currently in pilot
    PROMOTED = "promoted"  # Promoted to whitelist
    ROLLED_BACK = "rolled_back"  # Removed from pilot


@dataclass
class PilotScenario:
    """A scenario in pilot mode."""
    scenario_name: str
    status: ScenarioStatus = ScenarioStatus.PILOT_CANDIDATE
    pilot_start_time: Optional[float] = None
    pilot_sample_size: int = 0
    request_count: int = 0
    success_count: int = 0
    fallback_count: int = 0
    wrong_user_guard_trigger_count: int = 0
    latencies: List[float] = field(default_factory=list)
    quality_signal_samples: List[float] = field(default_factory=list)
    provider_health_success: int = 0
    provider_health_total: int = 0
    pilot_rounds: int = 0
    
    @property
    def fallback_rate(self) -> float:
        if self.request_count == 0:
            return 0.0
        return self.fallback_count / self.request_count
    
    @property
    def p95_latency_ms(self) -> Optional[float]:
        if not self.latencies:
            return None
        sorted_latencies = sorted(self.latencies)
        p95_idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[p95_idx] if p95_idx < len(sorted_latencies) else sorted_latencies[-1]
    
    @property
    def avg_latency_ms(self) -> Optional[float]:
        if not self.latencies:
            return None
        return sum(self.latencies) / len(self.latencies)
    
    @property
    def provider_health_rate(self) -> float:
        if self.provider_health_total == 0:
            return 0.0
        return self.provider_health_success / self.provider_health_total
    
    @property
    def avg_quality_signal(self) -> Optional[float]:
        if not self.quality_signal_samples:
            return None
        return sum(self.quality_signal_samples) / len(self.quality_signal_samples)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "status": self.status.value,
            "pilot_start_time": self.pilot_start_time,
            "pilot_sample_size": self.pilot_sample_size,
            "request_count": self.request_count,
            "success_count": self.success_count,
            "fallback_count": self.fallback_count,
            "fallback_rate": round(self.fallback_rate, 4),
            "p95_latency_ms": round(self.p95_latency_ms, 2) if self.p95_latency_ms else None,
            "avg_latency_ms": round(self.avg_latency_ms, 2) if self.avg_latency_ms else None,
            "wrong_user_guard_trigger_count": self.wrong_user_guard_trigger_count,
            "avg_quality_signal": round(self.avg_quality_signal, 4) if self.avg_quality_signal else None,
            "provider_health_rate": round(self.provider_health_rate, 4),
            "pilot_rounds": self.pilot_rounds,
        }


@dataclass
class PilotConfig:
    """Configuration for pilot mode."""
    enabled: bool = True
    pilot_percentage: int = 100  # 100% for pilot scenario
    
    # Thresholds for promotion
    min_pilot_sample_size: int = 30
    max_fallback_rate: float = 0.05
    max_wrong_user_guard_trigger: int = 0
    min_provider_health_rate: float = 0.98
    max_p95_latency_ms: float = 100.0
    min_quality_signal: float = 0.0  # Must be positive
    min_pilot_rounds: int = 2
    
    # Rollback thresholds
    rollback_fallback_rate: float = 0.10
    rollback_p95_latency_ms: float = 300.0
    rollback_min_provider_health_rate: float = 0.95
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "pilot_percentage": self.pilot_percentage,
            "min_pilot_sample_size": self.min_pilot_sample_size,
            "max_fallback_rate": self.max_fallback_rate,
            "max_wrong_user_guard_trigger": self.max_wrong_user_guard_trigger,
            "min_provider_health_rate": self.min_provider_health_rate,
            "max_p95_latency_ms": self.max_p95_latency_ms,
            "min_quality_signal": self.min_quality_signal,
            "min_pilot_rounds": self.min_pilot_rounds,
            "rollback_fallback_rate": self.rollback_fallback_rate,
            "rollback_p95_latency_ms": self.rollback_p95_latency_ms,
            "rollback_min_provider_health_rate": self.rollback_min_provider_health_rate,
        }


class PilotRegistry:
    """Registry for pilot scenarios.
    
    Capability Owner: OpenEmotion
    
    Manages:
    - Pilot candidate scenarios
    - Active pilot scenarios
    - Promoted scenarios (to whitelist)
    """
    
    # Production whitelist (fixed, not managed here)
    PRODUCTION_WHITELIST = [
        "memory_search_hard_query",
        "narrative_recall_ambiguous_query",
        "long_context_semantic_lookup",
    ]
    
    # Candidate scenarios eligible for pilot
    PILOT_CANDIDATES = [
        "complex_semantic_reasoning",
        "multi_turn_context_recall",
    ]
    
    def __init__(self, config: Optional[PilotConfig] = None):
        self.config = config or PilotConfig()
        self.pilot_scenarios: Dict[str, PilotScenario] = {}
        
        # Initialize candidates
        for scenario in self.PILOT_CANDIDATES:
            self.pilot_scenarios[scenario] = PilotScenario(
                scenario_name=scenario,
                status=ScenarioStatus.PILOT_CANDIDATE,
            )
    
    def activate_pilot(self, scenario_name: str) -> bool:
        """Activate a pilot scenario.
        
        Args:
            scenario_name: Scenario to activate
            
        Returns:
            True if activated successfully
        """
        if scenario_name not in self.PILOT_CANDIDATES:
            return False
        
        if scenario_name not in self.pilot_scenarios:
            self.pilot_scenarios[scenario_name] = PilotScenario(scenario_name=scenario_name)
        
        scenario = self.pilot_scenarios[scenario_name]
        if scenario.status != ScenarioStatus.PILOT_CANDIDATE:
            return False
        
        scenario.status = ScenarioStatus.PILOT_ACTIVE
        scenario.pilot_start_time = time.time()
        return True
    
    def deactivate_pilot(self, scenario_name: str) -> bool:
        """Deactivate a pilot scenario.
        
        Args:
            scenario_name: Scenario to deactivate
            
        Returns:
            True if deactivated successfully
        """
        if scenario_name not in self.pilot_scenarios:
            return False
        
        scenario = self.pilot_scenarios[scenario_name]
        if scenario.status != ScenarioStatus.PILOT_ACTIVE:
            return False
        
        scenario.status = ScenarioStatus.ROLLED_BACK
        return True
    
    def promote_pilot(self, scenario_name: str) -> bool:
        """Promote a pilot scenario to whitelist.
        
        Note: This doesn't actually modify the whitelist,
        just marks the scenario as promoted.
        
        Args:
            scenario_name: Scenario to promote
            
        Returns:
            True if promoted successfully
        """
        if scenario_name not in self.pilot_scenarios:
            return False
        
        scenario = self.pilot_scenarios[scenario_name]
        if scenario.status != ScenarioStatus.PILOT_ACTIVE:
            return False
        
        scenario.status = ScenarioStatus.PROMOTED
        return True
    
    def record_pilot_observation(
        self,
        scenario_name: str,
        success: bool,
        latency_ms: float,
        fallback: bool = False,
        wrong_user_trigger: bool = False,
        quality_signal: Optional[float] = None,
        provider_healthy: bool = True,
    ) -> None:
        """Record an observation for a pilot scenario."""
        if scenario_name not in self.pilot_scenarios:
            self.pilot_scenarios[scenario_name] = PilotScenario(scenario_name=scenario_name)
        
        scenario = self.pilot_scenarios[scenario_name]
        scenario.request_count += 1
        scenario.pilot_sample_size += 1
        
        if success:
            scenario.success_count += 1
        if fallback:
            scenario.fallback_count += 1
        if wrong_user_trigger:
            scenario.wrong_user_guard_trigger_count += 1
        
        scenario.latencies.append(latency_ms)
        
        if quality_signal is not None:
            scenario.quality_signal_samples.append(quality_signal)
        
        scenario.provider_health_total += 1
        if provider_healthy:
            scenario.provider_health_success += 1
    
    def increment_pilot_round(self, scenario_name: str) -> None:
        """Increment pilot round counter."""
        if scenario_name in self.pilot_scenarios:
            self.pilot_scenarios[scenario_name].pilot_rounds += 1
    
    def get_active_pilot_scenarios(self) -> List[str]:
        """Get currently active pilot scenarios."""
        return [
            name for name, scenario in self.pilot_scenarios.items()
            if scenario.status == ScenarioStatus.PILOT_ACTIVE
        ]
    
    def get_pilot_candidates(self) -> List[str]:
        """Get scenarios eligible for pilot."""
        return self.PILOT_CANDIDATES.copy()
    
    def get_production_whitelist(self) -> List[str]:
        """Get production whitelist (fixed)."""
        return self.PRODUCTION_WHITELIST.copy()
    
    def get_pilot_metrics(self, scenario_name: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a pilot scenario."""
        if scenario_name not in self.pilot_scenarios:
            return None
        return self.pilot_scenarios[scenario_name].to_dict()
    
    def get_all_pilot_metrics(self) -> Dict[str, Any]:
        """Get metrics for all pilot scenarios."""
        return {
            "config": self.config.to_dict(),
            "production_whitelist": self.PRODUCTION_WHITELIST,
            "pilot_candidates": self.PILOT_CANDIDATES,
            "active_pilots": self.get_active_pilot_scenarios(),
            "scenarios": {
                name: scenario.to_dict()
                for name, scenario in self.pilot_scenarios.items()
            },
        }
    
    def export(self, path: Optional[str] = None) -> str:
        """Export pilot registry data."""
        data = {
            "timestamp": datetime.now().isoformat(),
            **self.get_all_pilot_metrics(),
        }
        
        output_path = Path(path) if path else None
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(f"pilot_registry_{timestamp}.json")
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        
        return str(output_path)
