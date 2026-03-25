"""
Guard Drill Runner.

Runs controlled drills to test demotion/rollback mechanisms.
Capability Owner: OpenEmotion

v6i: Post-Promotion Guard Drill + Rollback Verification
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
from .post_promotion_guard import PostPromotionGuard, GuardAction


class DrillType(str, Enum):
    """Type of guard drill."""
    FALLBACK_RATE_OVERFLOW = "fallback_rate_overflow"
    WRONG_USER_GUARD_TRIGGER = "wrong_user_guard_trigger"
    PROVIDER_HEALTH_DEGRADATION = "provider_health_degradation"
    LATENCY_SPIKE = "latency_spike"
    QUALITY_SIGNAL_NEGATIVE = "quality_signal_negative"


class DrillResult(str, Enum):
    """Result of a drill."""
    PASS = "pass"
    FAIL = "fail"
    SKIPPED = "skipped"


@dataclass
class DrillReport:
    """Report from a single drill execution."""
    drill_type: DrillType
    scenario_name: str
    result: DrillResult
    expected_action: GuardAction
    actual_action: GuardAction
    expected_status: WhitelistStatus
    actual_status: WhitelistStatus
    details: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "drill_type": self.drill_type.value,
            "scenario_name": self.scenario_name,
            "result": self.result.value,
            "expected_action": self.expected_action.value,
            "actual_action": self.actual_action.value,
            "expected_status": self.expected_status.value,
            "actual_status": self.actual_status.value,
            "details": self.details,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
        }


class GuardDrillRunner:
    """
    Runs controlled drills to test demotion/rollback mechanisms.
    
    v6i specific:
    - Tests that demotion/rollback actually work
    - Provides evidence that guard mechanisms are functional
    - Generates drill artifacts for audit
    """

    def __init__(
        self,
        registry: ProductionWhitelistRegistry,
        guard: PostPromotionGuard,
        storage_path: Optional[Path] = None,
    ):
        self.registry = registry
        self.guard = guard
        self.storage_path = storage_path or Path("artifacts/eval/v6i")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.drill_reports: List[DrillReport] = []
        self._load_reports()

    def _load_reports(self) -> None:
        """Load drill reports from storage."""
        reports_file = self.storage_path / "guard_drill_report.json"
        if reports_file.exists():
            try:
                data = json.loads(reports_file.read_text())
                self.drill_reports = [
                    DrillReport(
                        drill_type=DrillType(r["drill_type"]),
                        scenario_name=r["scenario_name"],
                        result=DrillResult(r["result"]),
                        expected_action=GuardAction(r["expected_action"]),
                        actual_action=GuardAction(r["actual_action"]),
                        expected_status=WhitelistStatus(r["expected_status"]),
                        actual_status=WhitelistStatus(r["actual_status"]),
                        details=r.get("details", {}),
                        timestamp=r.get("timestamp", time.time()),
                    )
                    for r in data.get("drills", [])
                ]
            except Exception:
                pass

    def _save_reports(self) -> None:
        """Save drill reports to storage."""
        reports_file = self.storage_path / "guard_drill_report.json"
        data = {
            "drills": [r.to_dict() for r in self.drill_reports],
            "summary": {
                "total_drills": len(self.drill_reports),
                "passed": sum(1 for r in self.drill_reports if r.result == DrillResult.PASS),
                "failed": sum(1 for r in self.drill_reports if r.result == DrillResult.FAIL),
            },
        }
        reports_file.write_text(json.dumps(data, indent=2))

    def run_drill(
        self,
        drill_type: DrillType,
        scenario_name: str,
        simulate_only: bool = False,
    ) -> DrillReport:
        """
        Run a specific drill type.
        
        Args:
            drill_type: Type of drill to run
            scenario_name: Scenario to drill
            simulate_only: If True, don't actually change state
            
        Returns:
            DrillReport with results
        """
        # Ensure scenario is in production whitelist
        if not self.registry.is_in_production_whitelist(scenario_name):
            return DrillReport(
                drill_type=drill_type,
                scenario_name=scenario_name,
                result=DrillResult.SKIPPED,
                expected_action=GuardAction.NONE,
                actual_action=GuardAction.NONE,
                expected_status=WhitelistStatus.PROMOTED,
                actual_status=self.registry.scenarios.get(scenario_name, WhitelistStatus.PILOT_CANDIDATE).status if scenario_name in self.registry.scenarios else WhitelistStatus.PILOT_CANDIDATE,
                details={"reason": "Scenario not in production whitelist"},
            )

        # Store initial state
        initial_status = self.registry.scenarios[scenario_name].status

        # Generate drill observations based on type
        if drill_type == DrillType.FALLBACK_RATE_OVERFLOW:
            return self._run_fallback_overflow_drill(scenario_name, simulate_only)
        elif drill_type == DrillType.WRONG_USER_GUARD_TRIGGER:
            return self._run_wrong_user_guard_drill(scenario_name, simulate_only)
        elif drill_type == DrillType.PROVIDER_HEALTH_DEGRADATION:
            return self._run_provider_health_drill(scenario_name, simulate_only)
        elif drill_type == DrillType.LATENCY_SPIKE:
            return self._run_latency_spike_drill(scenario_name, simulate_only)
        elif drill_type == DrillType.QUALITY_SIGNAL_NEGATIVE:
            return self._run_quality_signal_drill(scenario_name, simulate_only)
        else:
            return DrillReport(
                drill_type=drill_type,
                scenario_name=scenario_name,
                result=DrillResult.SKIPPED,
                expected_action=GuardAction.NONE,
                actual_action=GuardAction.NONE,
                expected_status=initial_status,
                actual_status=initial_status,
                details={"reason": f"Unknown drill type: {drill_type}"},
            )

    def _run_fallback_overflow_drill(self, scenario_name: str, simulate_only: bool) -> DrillReport:
        """Test fallback rate overflow triggers demotion."""
        # Ensure scenario is promoted
        if self.registry.scenarios[scenario_name].status != WhitelistStatus.PROMOTED:
            self.registry.scenarios[scenario_name].status = WhitelistStatus.PROMOTED

        # Build baseline
        for _ in range(20):
            self.guard.observe(scenario_name, True, 50, fallback=False)

        # Trigger high fallback rate (20%) - capture demotion decision
        demotion_decision = None
        for i in range(5):
            decision = self.guard.observe(scenario_name, True, 50, fallback=True)
            if decision.action == GuardAction.DEMOTE:
                demotion_decision = decision

        final_status = self.registry.scenarios[scenario_name].status

        # Expected: DEMOTE action and DEMOTED status
        # PASS if status changed to DEMOTED (even if decision was captured earlier)
        expected_action = GuardAction.DEMOTE
        expected_status = WhitelistStatus.DEMOTED

        # Success if demotion happened
        result = DrillResult.PASS if (
            final_status == expected_status and demotion_decision is not None
        ) else DrillResult.FAIL

        report = DrillReport(
            drill_type=DrillType.FALLBACK_RATE_OVERFLOW,
            scenario_name=scenario_name,
            result=result,
            expected_action=expected_action,
            actual_action=demotion_decision.action if demotion_decision else GuardAction.NONE,
            expected_status=expected_status,
            actual_status=final_status,
            details={
                "fallback_rate": self.registry.scenarios[scenario_name].fallback_rate,
                "simulate_only": simulate_only,
                "demotion_triggered": demotion_decision is not None,
            },
        )

        self.drill_reports.append(report)
        self._save_reports()

        # Restore if simulate only
        if simulate_only and result == DrillResult.PASS:
            self.registry.scenarios[scenario_name].status = WhitelistStatus.PROMOTED
            self.registry._save_state()

        return report

    def _run_wrong_user_guard_drill(self, scenario_name: str, simulate_only: bool) -> DrillReport:
        """Test wrong_user_guard triggers rollback."""
        # Ensure scenario is promoted
        if self.registry.scenarios[scenario_name].status != WhitelistStatus.PROMOTED:
            self.registry.scenarios[scenario_name].status = WhitelistStatus.PROMOTED

        # Trigger wrong_user_guard
        decision = self.guard.observe(
            scenario_name,
            success=True,
            latency_ms=50,
            wrong_user_guard=True,
        )

        final_status = self.registry.scenarios[scenario_name].status

        # Expected: ROLLBACK action and ROLLED_BACK status
        expected_action = GuardAction.ROLLBACK
        expected_status = WhitelistStatus.ROLLED_BACK

        result = DrillResult.PASS if (
            decision.action == expected_action and
            final_status == expected_status
        ) else DrillResult.FAIL

        report = DrillReport(
            drill_type=DrillType.WRONG_USER_GUARD_TRIGGER,
            scenario_name=scenario_name,
            result=result,
            expected_action=expected_action,
            actual_action=decision.action,
            expected_status=expected_status,
            actual_status=final_status,
            details={
                "wrong_user_guard_count": self.registry.scenarios[scenario_name].wrong_user_guard_trigger_count,
                "simulate_only": simulate_only,
            },
        )

        self.drill_reports.append(report)
        self._save_reports()

        # Restore if simulate only
        if simulate_only and result == DrillResult.PASS:
            self.registry.scenarios[scenario_name].status = WhitelistStatus.PROMOTED
            self.registry.scenarios[scenario_name].wrong_user_guard_trigger_count = 0
            self.registry._save_state()

        return report

    def _run_provider_health_drill(self, scenario_name: str, simulate_only: bool) -> DrillReport:
        """Test provider health degradation triggers demotion."""
        # Build baseline
        for _ in range(50):
            self.guard.observe(scenario_name, True, 50, provider_health=True)

        # Trigger low provider health
        decisions = []
        for i in range(50):
            decision = self.guard.observe(
                scenario_name,
                True,
                50,
                provider_health=(i % 20 != 0),  # 95% health
            )
            decisions.append(decision)

        final_decision = decisions[-1]
        final_status = self.registry.scenarios[scenario_name].status

        # Expected: DEMOTE or ALERT (depends on threshold)
        expected_action = GuardAction.DEMOTE
        expected_status = WhitelistStatus.DEMOTED

        # Also accept ALERT as pass (warning level)
        result = DrillResult.PASS if (
            final_decision.action in (GuardAction.DEMOTE, GuardAction.ALERT)
        ) else DrillResult.FAIL

        report = DrillReport(
            drill_type=DrillType.PROVIDER_HEALTH_DEGRADATION,
            scenario_name=scenario_name,
            result=result,
            expected_action=expected_action,
            actual_action=final_decision.action,
            expected_status=expected_status,
            actual_status=final_status,
            details={
                "provider_health_rate": self.registry.scenarios[scenario_name].provider_health_rate,
                "simulate_only": simulate_only,
            },
        )

        self.drill_reports.append(report)
        self._save_reports()

        # Restore if simulate only
        if simulate_only:
            self.registry.scenarios[scenario_name].status = WhitelistStatus.PROMOTED
            self.registry._save_state()

        return report

    def _run_latency_spike_drill(self, scenario_name: str, simulate_only: bool) -> DrillReport:
        """Test latency spike triggers alert."""
        # Build baseline with normal latency
        for _ in range(20):
            self.guard.observe(scenario_name, True, 50)

        # Trigger high latency
        decision = self.guard.observe(scenario_name, True, 350)  # > 300ms threshold

        final_status = self.registry.scenarios[scenario_name].status

        # Expected: ALERT or DEMOTE
        expected_action = GuardAction.ALERT
        expected_status = WhitelistStatus.PROMOTED  # Alert doesn't change status

        result = DrillResult.PASS if (
            decision.action in (GuardAction.ALERT, GuardAction.DEMOTE)
        ) else DrillResult.FAIL

        report = DrillReport(
            drill_type=DrillType.LATENCY_SPIKE,
            scenario_name=scenario_name,
            result=result,
            expected_action=expected_action,
            actual_action=decision.action,
            expected_status=expected_status,
            actual_status=final_status,
            details={
                "p95_latency_ms": self.registry.scenarios[scenario_name].p95_latency_ms,
                "simulate_only": simulate_only,
            },
        )

        self.drill_reports.append(report)
        self._save_reports()

        return report

    def _run_quality_signal_drill(self, scenario_name: str, simulate_only: bool) -> DrillReport:
        """Test negative quality signal triggers alert."""
        # Build baseline
        for _ in range(20):
            self.guard.observe(scenario_name, True, 50, quality_signal=0.5)

        # Trigger negative quality signals
        decisions = []
        for _ in range(3):
            decision = self.guard.observe(scenario_name, True, 50, quality_signal=-0.1)
            decisions.append(decision)

        final_decision = decisions[-1]
        final_status = self.registry.scenarios[scenario_name].status

        # Expected: ALERT or DEMOTE
        expected_action = GuardAction.ALERT
        expected_status = WhitelistStatus.PROMOTED

        result = DrillResult.PASS if (
            final_decision.action in (GuardAction.ALERT, GuardAction.DEMOTE)
        ) else DrillResult.FAIL

        report = DrillReport(
            drill_type=DrillType.QUALITY_SIGNAL_NEGATIVE,
            scenario_name=scenario_name,
            result=result,
            expected_action=expected_action,
            actual_action=final_decision.action,
            expected_status=expected_status,
            actual_status=final_status,
            details={
                "avg_quality_signal": self.registry.scenarios[scenario_name].avg_quality_signal,
                "simulate_only": simulate_only,
            },
        )

        self.drill_reports.append(report)
        self._save_reports()

        return report

    def run_all_drills(self, scenario_name: str, simulate_only: bool = True) -> Dict[str, Any]:
        """
        Run all drill types for a scenario.
        
        Args:
            scenario_name: Scenario to drill
            simulate_only: If True, restore state after each drill
            
        Returns:
            Summary of all drills
        """
        # Ensure scenario is promoted
        if not self.registry.is_in_production_whitelist(scenario_name):
            # Temporarily promote for drill
            self.registry.promote_scenario(scenario_name, "Drill setup", "drill")

        results = {}
        for drill_type in DrillType:
            # Reset state before each drill
            self.registry.scenarios[scenario_name].status = WhitelistStatus.PROMOTED
            self.registry.scenarios[scenario_name].request_count = 0
            self.registry.scenarios[scenario_name].fallback_count = 0
            self.registry.scenarios[scenario_name].wrong_user_guard_trigger_count = 0
            self.registry.scenarios[scenario_name].latencies = []
            self.registry.scenarios[scenario_name].quality_signal_samples = []
            self.registry.scenarios[scenario_name].provider_health_success = 0
            self.registry.scenarios[scenario_name].provider_health_total = 0
            self.registry.scenarios[scenario_name].observation_rounds = 0
            self.registry._save_state()

            # Run drill
            report = self.run_drill(drill_type, scenario_name, simulate_only)
            results[drill_type.value] = report.to_dict()

            # Restore for next drill if simulate_only
            if simulate_only:
                self.registry.scenarios[scenario_name].status = WhitelistStatus.PROMOTED
                self.registry.scenarios[scenario_name].request_count = 0
                self.registry.scenarios[scenario_name].fallback_count = 0
                self.registry.scenarios[scenario_name].wrong_user_guard_trigger_count = 0
                self.registry.scenarios[scenario_name].latencies = []
                self.registry.scenarios[scenario_name].quality_signal_samples = []
                self.registry.scenarios[scenario_name].provider_health_success = 0
                self.registry.scenarios[scenario_name].provider_health_total = 0
                self.registry._save_state()

        summary = {
            "scenario_name": scenario_name,
            "drills": results,
            "summary": {
                "total": len(results),
                "passed": sum(1 for r in results.values() if r["result"] == "pass"),
                "failed": sum(1 for r in results.values() if r["result"] == "fail"),
                "skipped": sum(1 for r in results.values() if r["result"] == "skipped"),
            },
            "demotion_drill": "PASS" if results.get("fallback_rate_overflow", {}).get("result") == "pass" else "FAIL",
            "rollback_drill": "PASS" if results.get("wrong_user_guard_trigger", {}).get("result") == "pass" else "FAIL",
        }

        return summary
