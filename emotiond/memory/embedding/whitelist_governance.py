"""
Whitelist Governance.

Unified governance for production whitelist scenarios.
Capability Owner: OpenEmotion

v6k: Whitelist Governance + Periodic Receipts + Unified Verdicts
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .production_whitelist import ProductionWhitelistRegistry, WhitelistStatus
from .post_promotion_guard import PostPromotionGuard


class ScenarioVerdict(str, Enum):
    """Verdict for a single scenario."""
    HEALTHY = "healthy"
    OBSERVE = "observe"
    BOOTSTRAP = "bootstrap"  # Insufficient data, not a failure
    DEMOTE_CANDIDATE = "demote_candidate"
    ROLLBACK_CANDIDATE = "rollback_candidate"


class WhitelistVerdict(str, Enum):
    """Verdict for the entire whitelist."""
    STABLE = "stable"
    OBSERVE = "observe"
    EXPANSION_BLOCKED = "expansion_blocked"
    EXPANSION_READY_CANDIDATE = "expansion_ready_candidate"


class ExpansionReadiness(str, Enum):
    """Readiness for whitelist expansion."""
    READY = "ready"
    NOT_READY = "not_ready"
    BLOCKED = "blocked"


@dataclass
class ScenarioGovernanceState:
    """Governance state for a single scenario."""
    scenario_name: str
    request_count: int = 0
    success_count: int = 0
    fallback_rate: float = 0.0
    p95_latency_ms: float = 0.0
    wrong_user_guard_trigger_count: int = 0
    provider_health_rate: float = 1.0
    quality_gain_signal: float = 0.0
    verdict: ScenarioVerdict = ScenarioVerdict.HEALTHY
    blockers: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "request_count": self.request_count,
            "success_count": self.success_count,
            "fallback_rate": self.fallback_rate,
            "p95_latency_ms": self.p95_latency_ms,
            "wrong_user_guard_trigger_count": self.wrong_user_guard_trigger_count,
            "provider_health_rate": self.provider_health_rate,
            "quality_gain_signal": self.quality_gain_signal,
            "verdict": self.verdict.value,
            "blockers": self.blockers,
        }


@dataclass
class WhitelistGovernanceSummary:
    """Governance summary for the entire whitelist."""
    active_scenario_count: int = 0
    healthy_scenario_count: int = 0
    observe_scenario_count: int = 0
    demote_candidate_count: int = 0
    rollback_candidate_count: int = 0
    whitelist_verdict: WhitelistVerdict = WhitelistVerdict.STABLE
    expansion_readiness: ExpansionReadiness = ExpansionReadiness.NOT_READY
    blockers: List[str] = field(default_factory=list)
    rationale: str = ""
    scenario_states: List[ScenarioGovernanceState] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_scenario_count": self.active_scenario_count,
            "healthy_scenario_count": self.healthy_scenario_count,
            "observe_scenario_count": self.observe_scenario_count,
            "demote_candidate_count": self.demote_candidate_count,
            "rollback_candidate_count": self.rollback_candidate_count,
            "whitelist_verdict": self.whitelist_verdict.value,
            "expansion_readiness": self.expansion_readiness.value,
            "blockers": self.blockers,
            "rationale": self.rationale,
            "scenario_states": [s.to_dict() for s in self.scenario_states],
        }


class WhitelistGovernanceEvaluator:
    """
    Unified governance evaluator for production whitelist.
    
    v6k specific:
    - Evaluates all production whitelist scenarios
    - Outputs scenario-level and whitelist-level verdicts
    - Determines expansion readiness
    - Provides structured governance summary
    """

    # Scenario-level healthy thresholds
    HEALTHY_MAX_FALLBACK_RATE = 0.05  # 5%
    HEALTHY_MAX_P95_LATENCY_MS = 100
    HEALTHY_MAX_WRONG_USER_GUARD = 0
    HEALTHY_MIN_PROVIDER_HEALTH_RATE = 0.98  # 98%
    HEALTHY_MIN_QUALITY_SIGNAL = 0.0

    # Demotion thresholds
    DEMOTE_FALLBACK_RATE = 0.10  # 10%
    DEMOTE_PROVIDER_HEALTH_RATE = 0.95  # 95%

    def __init__(
        self,
        registry: ProductionWhitelistRegistry,
        storage_path: Optional[Path] = None,
    ):
        self.registry = registry
        self.storage_path = storage_path or Path("artifacts/eval/v6k")
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def evaluate_scenario(self, scenario_name: str) -> ScenarioGovernanceState:
        """
        Evaluate governance state for a single scenario.
        
        Args:
            scenario_name: Scenario to evaluate
            
        Returns:
            ScenarioGovernanceState with verdict
        """
        if scenario_name not in self.registry.scenarios:
            return ScenarioGovernanceState(
                scenario_name=scenario_name,
                verdict=ScenarioVerdict.ROLLBACK_CANDIDATE,
                blockers=["Scenario not in registry"],
            )

        scenario = self.registry.scenarios[scenario_name]
        report = self.registry.get_observation_report(scenario_name)

        state = ScenarioGovernanceState(
            scenario_name=scenario_name,
            request_count=report.get("request_count", 0),
            success_count=report.get("success_count", 0),
            fallback_rate=report.get("fallback_rate", 0),
            p95_latency_ms=report.get("p95_latency_ms", 0),
            wrong_user_guard_trigger_count=report.get("wrong_user_guard_trigger_count", 0),
            provider_health_rate=report.get("provider_health_rate", 1.0),
            quality_gain_signal=report.get("avg_quality_signal", 0),
        )

        blockers = []

        # If no data, return BOOTSTRAP (insufficient data, not a failure)
        if state.request_count == 0:
            state.verdict = ScenarioVerdict.BOOTSTRAP
            state.blockers = ["Insufficient observation data (request_count = 0) - BOOTSTRAP state"]
            return state

        # Check rollback conditions (critical)
        if state.wrong_user_guard_trigger_count > 0:
            state.verdict = ScenarioVerdict.ROLLBACK_CANDIDATE
            blockers.append(f"wrong_user_guard_trigger_count ({state.wrong_user_guard_trigger_count}) > 0")
            state.blockers = blockers
            return state

        # Check demotion conditions
        if state.fallback_rate > self.DEMOTE_FALLBACK_RATE:
            state.verdict = ScenarioVerdict.DEMOTE_CANDIDATE
            blockers.append(f"fallback_rate ({state.fallback_rate:.1%}) > {self.DEMOTE_FALLBACK_RATE:.0%}")
            state.blockers = blockers
            return state

        if state.provider_health_rate < self.DEMOTE_PROVIDER_HEALTH_RATE:
            state.verdict = ScenarioVerdict.DEMOTE_CANDIDATE
            blockers.append(f"provider_health_rate ({state.provider_health_rate:.1%}) < {self.DEMOTE_PROVIDER_HEALTH_RATE:.0%}")
            state.blockers = blockers
            return state

        # Check healthy conditions
        if state.fallback_rate > self.HEALTHY_MAX_FALLBACK_RATE:
            blockers.append(f"fallback_rate ({state.fallback_rate:.1%}) > {self.HEALTHY_MAX_FALLBACK_RATE:.0%}")

        if state.p95_latency_ms > self.HEALTHY_MAX_P95_LATENCY_MS:
            blockers.append(f"p95_latency_ms ({state.p95_latency_ms:.0f}) > {self.HEALTHY_MAX_P95_LATENCY_MS}")

        if state.provider_health_rate < self.HEALTHY_MIN_PROVIDER_HEALTH_RATE:
            blockers.append(f"provider_health_rate ({state.provider_health_rate:.1%}) < {self.HEALTHY_MIN_PROVIDER_HEALTH_RATE:.0%}")

        if state.quality_gain_signal <= self.HEALTHY_MIN_QUALITY_SIGNAL:
            blockers.append(f"quality_gain_signal ({state.quality_gain_signal:.2f}) <= {self.HEALTHY_MIN_QUALITY_SIGNAL}")

        # Determine verdict
        if blockers:
            state.verdict = ScenarioVerdict.OBSERVE
            state.blockers = blockers
        else:
            state.verdict = ScenarioVerdict.HEALTHY
            state.blockers = []

        return state

    def evaluate_whitelist(self) -> WhitelistGovernanceSummary:
        """
        Evaluate governance state for the entire whitelist.
        
        Returns:
            WhitelistGovernanceSummary with verdicts
        """
        promoted_scenarios = self.registry.get_production_whitelist()

        scenario_states = []
        for scenario_name in promoted_scenarios:
            state = self.evaluate_scenario(scenario_name)
            scenario_states.append(state)

        # Count by verdict
        healthy_count = sum(1 for s in scenario_states if s.verdict == ScenarioVerdict.HEALTHY)
        observe_count = sum(1 for s in scenario_states if s.verdict == ScenarioVerdict.OBSERVE)
        demote_count = sum(1 for s in scenario_states if s.verdict == ScenarioVerdict.DEMOTE_CANDIDATE)
        rollback_count = sum(1 for s in scenario_states if s.verdict == ScenarioVerdict.ROLLBACK_CANDIDATE)

        summary = WhitelistGovernanceSummary(
            active_scenario_count=len(promoted_scenarios),
            healthy_scenario_count=healthy_count,
            observe_scenario_count=observe_count,
            demote_candidate_count=demote_count,
            rollback_candidate_count=rollback_count,
            scenario_states=scenario_states,
        )

        # Determine whitelist verdict
        if rollback_count > 0:
            summary.whitelist_verdict = WhitelistVerdict.EXPANSION_BLOCKED
            summary.expansion_readiness = ExpansionReadiness.BLOCKED
            summary.blockers = [f"{rollback_count} scenario(s) are rollback candidates"]
            summary.rationale = "Critical issues detected, expansion blocked"
        elif demote_count > 0:
            summary.whitelist_verdict = WhitelistVerdict.OBSERVE
            summary.expansion_readiness = ExpansionReadiness.NOT_READY
            summary.blockers = [f"{demote_count} scenario(s) are demote candidates"]
            summary.rationale = "Stability issues detected, expansion not ready"
        elif observe_count > len(promoted_scenarios) * 0.25:  # More than 25% in observe
            summary.whitelist_verdict = WhitelistVerdict.OBSERVE
            summary.expansion_readiness = ExpansionReadiness.NOT_READY
            summary.blockers = [f"{observe_count} scenario(s) need observation"]
            summary.rationale = "Too many scenarios under observation"
        elif healthy_count == len(promoted_scenarios):
            summary.whitelist_verdict = WhitelistVerdict.STABLE
            summary.expansion_readiness = ExpansionReadiness.READY
            summary.rationale = "All scenarios healthy, expansion ready"
        else:
            summary.whitelist_verdict = WhitelistVerdict.STABLE
            summary.expansion_readiness = ExpansionReadiness.NOT_READY
            summary.rationale = "Most scenarios stable, but not ready for expansion"

        return summary

    def generate_governance_report(self) -> Dict[str, Any]:
        """Generate full governance report."""
        summary = self.evaluate_whitelist()
        snapshot = {
            "active_scenarios": self.registry.get_production_whitelist(),
            "promoted_scenarios": [
                name for name, s in self.registry.scenarios.items()
                if s.status == WhitelistStatus.PROMOTED
            ],
            "scenario_count": len(self.registry.get_production_whitelist()),
        }

        return {
            "snapshot": snapshot,
            "governance": summary.to_dict(),
            "generated_at": datetime.now().isoformat(),
            "generated_timestamp": time.time(),
        }

    def save_governance_report(self) -> Path:
        """Save governance report to file."""
        report = self.generate_governance_report()
        report_file = self.storage_path / "whitelist_governance_summary.json"
        report_file.write_text(json.dumps(report, indent=2))
        return report_file
