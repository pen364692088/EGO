"""
Post-Promotion Guard.

Monitors promoted scenarios and triggers demotion/rollback when thresholds violated.
Capability Owner: OpenEmotion

v6h: Post-Promotion Observation + Auto-Demotion Guard
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .production_whitelist import (
    ProductionWhitelistRegistry,
    WhitelistStatus,
    PromotionReceipt,
)


class GuardAction(str, Enum):
    """Actions the guard can take."""
    NONE = "none"
    ALERT = "alert"
    DEMOTE = "demote"
    ROLLBACK = "rollback"


@dataclass
class GuardDecision:
    """Decision from the guard."""
    scenario_name: str
    action: GuardAction
    reason: Optional[str]
    metrics_snapshot: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "action": self.action.value,
            "reason": self.reason,
            "metrics_snapshot": self.metrics_snapshot,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
        }


class PostPromotionGuard:
    """
    Monitors promoted scenarios and triggers actions when thresholds violated.
    
    v6h specific:
    - Observes complex_semantic_reasoning after promotion
    - Tracks fallback_rate, latency, wrong_user_guard, quality_signal
    - Auto-demotes or alerts when thresholds violated
    """

    # Observation thresholds (v6h defaults)
    DEFAULT_THRESHOLDS = {
        # Must maintain
        "max_wrong_user_guard_trigger_count": 0,
        "max_fallback_rate": 0.10,  # 10%
        "min_provider_health_rate": 0.95,  # 95%
        "max_p95_latency_ms": 300,

        # Quality signal
        "min_quality_signal": 0.0,
        "min_quality_signal_rounds": 2,  # consecutive rounds below threshold triggers action
    }

    def __init__(
        self,
        registry: ProductionWhitelistRegistry,
        storage_path: Optional[Path] = None,
    ):
        self.registry = registry
        self.storage_path = storage_path or Path("artifacts/eval/v6h")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.decisions: List[GuardDecision] = []
        self._load_decisions()

    def _load_decisions(self) -> None:
        """Load guard decisions from storage."""
        decisions_file = self.storage_path / "guard_decisions.json"
        if decisions_file.exists():
            try:
                data = json.loads(decisions_file.read_text())
                self.decisions = [
                    GuardDecision(
                        scenario_name=d["scenario_name"],
                        action=GuardAction(d["action"]),
                        reason=d.get("reason"),
                        metrics_snapshot=d.get("metrics_snapshot", {}),
                        timestamp=d.get("timestamp", time.time()),
                    )
                    for d in data.get("decisions", [])
                ]
            except Exception:
                pass

    def _save_decisions(self) -> None:
        """Save guard decisions to storage."""
        decisions_file = self.storage_path / "guard_decisions.json"
        data = {
            "decisions": [d.to_dict() for d in self.decisions[-100:]],  # Keep last 100
        }
        decisions_file.write_text(json.dumps(data, indent=2))

    def observe(
        self,
        scenario_name: str,
        success: bool,
        latency_ms: float,
        fallback: bool = False,
        wrong_user_guard: bool = False,
        provider_health: bool = True,
        quality_signal: Optional[float] = None,
    ) -> GuardDecision:
        """
        Record observation and check if action needed.
        
        Args:
            scenario_name: Scenario being observed
            success: Whether request succeeded
            latency_ms: Latency in milliseconds
            fallback: Whether fallback was triggered
            wrong_user_guard: Whether wrong user guard triggered
            provider_health: Whether provider was healthy
            quality_signal: Quality signal value
            
        Returns:
            GuardDecision indicating if action needed
        """
        # Record observation in registry
        self.registry.record_observation(
            scenario_name=scenario_name,
            success=success,
            latency_ms=latency_ms,
            fallback=fallback,
            wrong_user_guard=wrong_user_guard,
            provider_health=provider_health,
            quality_signal=quality_signal,
        )

        # Get updated metrics
        report = self.registry.get_observation_report(scenario_name)
        if not report:
            return GuardDecision(
                scenario_name=scenario_name,
                action=GuardAction.NONE,
                reason="Scenario not in registry",
                metrics_snapshot={},
            )
        
        # Check if scenario is still promoted
        if report.get("status") != "promoted":
            return GuardDecision(
                scenario_name=scenario_name,
                action=GuardAction.NONE,
                reason=f"Scenario is {report.get('status')}, not promoted",
                metrics_snapshot=report,
            )

        # Check for rollback needed
        rollback_reason = self.registry.check_rollback_needed(scenario_name)

        if rollback_reason:
            # Determine action severity
            if "wrong_user_guard" in rollback_reason:
                # Critical - immediate rollback
                action = GuardAction.ROLLBACK
                self.registry.rollback_scenario(scenario_name, rollback_reason)
            elif report.get("fallback_rate", 0) > 0.10:
                # High fallback rate - demote
                action = GuardAction.DEMOTE
                self.registry.demote_scenario(scenario_name, rollback_reason)
            elif report.get("provider_health_rate", 1) < 0.95:
                # Low provider health - demote
                action = GuardAction.DEMOTE
                self.registry.demote_scenario(scenario_name, rollback_reason)
            else:
                # Other issues - alert
                action = GuardAction.ALERT

            decision = GuardDecision(
                scenario_name=scenario_name,
                action=action,
                reason=rollback_reason,
                metrics_snapshot=report,
            )
            self.decisions.append(decision)
            self._save_decisions()

            return decision

        # Check for warning conditions
        warnings = []
        if report.get("fallback_rate", 0) > 0.05:
            warnings.append(f"fallback_rate ({report['fallback_rate']:.1%}) > 5%")
        if report.get("p95_latency_ms", 0) > 100:
            warnings.append(f"p95_latency ({report['p95_latency_ms']:.0f}ms) > 100ms")
        if report.get("provider_health_rate", 1) < 0.98:
            warnings.append(f"provider_health_rate ({report['provider_health_rate']:.1%}) < 98%")

        if warnings:
            decision = GuardDecision(
                scenario_name=scenario_name,
                action=GuardAction.ALERT,
                reason="; ".join(warnings),
                metrics_snapshot=report,
            )
            self.decisions.append(decision)
            self._save_decisions()
            return decision

        return GuardDecision(
            scenario_name=scenario_name,
            action=GuardAction.NONE,
            reason=None,
            metrics_snapshot=report,
        )

    def get_guard_report(self) -> Dict[str, Any]:
        """Get overall guard report."""
        promoted_scenarios = self.registry.get_production_whitelist()

        scenario_reports = {}
        for scenario_name in promoted_scenarios:
            report = self.registry.get_observation_report(scenario_name)
            if report and report.get("status") == "promoted":
                scenario_reports[scenario_name] = report

        recent_decisions = [
            d.to_dict() for d in self.decisions[-10:]
            if d.action != GuardAction.NONE
        ]

        return {
            "timestamp": time.time(),
            "datetime": datetime.now().isoformat(),
            "promoted_scenarios": promoted_scenarios,
            "scenario_reports": scenario_reports,
            "recent_actions": recent_decisions,
            "demotion_supported": True,
            "rollback_supported": True,
        }

    def run_observation_round(
        self,
        scenario_name: str,
        observations: List[Dict[str, Any]],
    ) -> GuardDecision:
        """
        Run a batch of observations for a scenario.
        
        Args:
            scenario_name: Scenario to observe
            observations: List of observation dicts with keys:
                - success: bool
                - latency_ms: float
                - fallback: bool (default False)
                - wrong_user_guard: bool (default False)
                - provider_health: bool (default True)
                - quality_signal: float (optional)
                
        Returns:
            Final GuardDecision for the round
        """
        final_decision = GuardDecision(
            scenario_name=scenario_name,
            action=GuardAction.NONE,
            reason=None,
            metrics_snapshot={},
        )

        for obs in observations:
            decision = self.observe(
                scenario_name=scenario_name,
                success=obs.get("success", True),
                latency_ms=obs.get("latency_ms", 0),
                fallback=obs.get("fallback", False),
                wrong_user_guard=obs.get("wrong_user_guard", False),
                provider_health=obs.get("provider_health", True),
                quality_signal=obs.get("quality_signal"),
            )
            if decision.action != GuardAction.NONE:
                final_decision = decision

        # Increment observation rounds
        if scenario_name in self.registry.scenarios:
            self.registry.scenarios[scenario_name].observation_rounds += 1
            self.registry._save_state()

        return final_decision
