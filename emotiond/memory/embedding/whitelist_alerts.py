"""
Whitelist Alerts.

Alert and escalation hooks for whitelist governance.
Capability Owner: OpenEmotion

v6k: Alert & Escalation Hooks for Whitelist Governance
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .production_whitelist import ProductionWhitelistRegistry
from .whitelist_governance import (
    WhitelistGovernanceEvaluator,
    ScenarioVerdict,
)


class AlertType(str, Enum):
    """Types of whitelist alerts."""
    PROVIDER_HEALTH_DROP = "provider_health_drop"
    LATENCY_REGRESSION = "latency_regression"
    FALLBACK_SPIKE = "fallback_spike"
    WRONG_USER_GUARD_TRIGGER = "wrong_user_guard_trigger"
    QUALITY_SIGNAL_REGRESSION = "quality_signal_regression"
    DEMOTION_CANDIDATE = "demotion_candidate"
    ROLLBACK_CANDIDATE = "rollback_candidate"


class AlertSeverity(str, Enum):
    """Severity levels for alerts."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class WhitelistAlert:
    """Alert for a whitelist scenario."""
    alert_id: str
    alert_type: AlertType
    severity: AlertSeverity
    scenario_name: str
    message: str
    current_value: Any
    threshold: Any
    timestamp: float
    acknowledged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "scenario_name": self.scenario_name,
            "message": self.message,
            "current_value": self.current_value,
            "threshold": self.threshold,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "acknowledged": self.acknowledged,
        }


@dataclass
class AlertSummary:
    """Summary of alerts for the whitelist."""
    total_alerts: int
    critical_count: int
    warning_count: int
    info_count: int
    affected_scenarios: List[str]
    alerts_by_type: Dict[str, int]
    alerts_by_scenario: Dict[str, int]
    unacknowledged_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_alerts": self.total_alerts,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "affected_scenarios": self.affected_scenarios,
            "alerts_by_type": self.alerts_by_type,
            "alerts_by_scenario": self.alerts_by_scenario,
            "unacknowledged_count": self.unacknowledged_count,
        }


class WhitelistAlertManager:
    """
    Manages alerts for whitelist governance.
    
    v6k specific:
    - Detects stability issues
    - Generates structured alerts
    - Tracks alert history
    - Provides escalation hooks
    """

    # Alert thresholds
    WARNING_FALLBACK_RATE = 0.05  # 5%
    CRITICAL_FALLBACK_RATE = 0.10  # 10%
    WARNING_P95_LATENCY_MS = 100
    CRITICAL_P95_LATENCY_MS = 300
    WARNING_PROVIDER_HEALTH_RATE = 0.98  # 98%
    CRITICAL_PROVIDER_HEALTH_RATE = 0.95  # 95%
    CRITICAL_WRONG_USER_GUARD = 0

    def __init__(
        self,
        registry: ProductionWhitelistRegistry,
        governance_evaluator: WhitelistGovernanceEvaluator,
        storage_path: Optional[Path] = None,
    ):
        self.registry = registry
        self.governance = governance_evaluator
        self.storage_path = storage_path or Path("artifacts/eval/v6k")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.alerts: List[WhitelistAlert] = []
        self._load_alerts()

    def _load_alerts(self) -> None:
        """Load existing alerts from storage."""
        alerts_file = self.storage_path / "alerts_history.json"
        if alerts_file.exists():
            try:
                data = json.loads(alerts_file.read_text())
                self.alerts = [
                    WhitelistAlert(
                        alert_id=a.get("alert_id", ""),
                        alert_type=AlertType(a.get("alert_type", "fallback_spike")),
                        severity=AlertSeverity(a.get("severity", "warning")),
                        scenario_name=a.get("scenario_name", ""),
                        message=a.get("message", ""),
                        current_value=a.get("current_value"),
                        threshold=a.get("threshold"),
                        timestamp=a.get("timestamp", time.time()),
                        acknowledged=a.get("acknowledged", False),
                    )
                    for a in data.get("alerts", [])
                ]
            except Exception:
                pass

    def _save_alerts(self) -> None:
        """Save alerts to storage."""
        alerts_file = self.storage_path / "alerts_history.json"
        data = {
            "alerts": [a.to_dict() for a in self.alerts[-500:]],  # Keep last 500
        }
        alerts_file.write_text(json.dumps(data, indent=2))

    def _generate_alert_id(self, alert_type: AlertType, scenario_name: str) -> str:
        """Generate unique alert ID."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"alert-{alert_type.value}-{scenario_name}-{timestamp}"

    def check_scenario_alerts(self, scenario_name: str) -> List[WhitelistAlert]:
        """
        Check for alerts on a specific scenario.
        
        Args:
            scenario_name: Scenario to check
            
        Returns:
            List of generated alerts
        """
        alerts = []

        if scenario_name not in self.registry.scenarios:
            return alerts

        state = self.governance.evaluate_scenario(scenario_name)

        # Check wrong_user_guard (critical)
        if state.wrong_user_guard_trigger_count > self.CRITICAL_WRONG_USER_GUARD:
            alert = WhitelistAlert(
                alert_id=self._generate_alert_id(AlertType.WRONG_USER_GUARD_TRIGGER, scenario_name),
                alert_type=AlertType.WRONG_USER_GUARD_TRIGGER,
                severity=AlertSeverity.CRITICAL,
                scenario_name=scenario_name,
                message=f"Wrong user guard triggered {state.wrong_user_guard_trigger_count} times",
                current_value=state.wrong_user_guard_trigger_count,
                threshold=self.CRITICAL_WRONG_USER_GUARD,
                timestamp=time.time(),
            )
            alerts.append(alert)

        # Check fallback rate
        if state.fallback_rate > self.CRITICAL_FALLBACK_RATE:
            alert = WhitelistAlert(
                alert_id=self._generate_alert_id(AlertType.FALLBACK_SPIKE, scenario_name),
                alert_type=AlertType.FALLBACK_SPIKE,
                severity=AlertSeverity.CRITICAL,
                scenario_name=scenario_name,
                message=f"Fallback rate {state.fallback_rate:.1%} exceeds critical threshold",
                current_value=state.fallback_rate,
                threshold=self.CRITICAL_FALLBACK_RATE,
                timestamp=time.time(),
            )
            alerts.append(alert)
        elif state.fallback_rate > self.WARNING_FALLBACK_RATE:
            alert = WhitelistAlert(
                alert_id=self._generate_alert_id(AlertType.FALLBACK_SPIKE, scenario_name),
                alert_type=AlertType.FALLBACK_SPIKE,
                severity=AlertSeverity.WARNING,
                scenario_name=scenario_name,
                message=f"Fallback rate {state.fallback_rate:.1%} exceeds warning threshold",
                current_value=state.fallback_rate,
                threshold=self.WARNING_FALLBACK_RATE,
                timestamp=time.time(),
            )
            alerts.append(alert)

        # Check latency
        if state.p95_latency_ms > self.CRITICAL_P95_LATENCY_MS:
            alert = WhitelistAlert(
                alert_id=self._generate_alert_id(AlertType.LATENCY_REGRESSION, scenario_name),
                alert_type=AlertType.LATENCY_REGRESSION,
                severity=AlertSeverity.CRITICAL,
                scenario_name=scenario_name,
                message=f"P95 latency {state.p95_latency_ms:.0f}ms exceeds critical threshold",
                current_value=state.p95_latency_ms,
                threshold=self.CRITICAL_P95_LATENCY_MS,
                timestamp=time.time(),
            )
            alerts.append(alert)
        elif state.p95_latency_ms > self.WARNING_P95_LATENCY_MS:
            alert = WhitelistAlert(
                alert_id=self._generate_alert_id(AlertType.LATENCY_REGRESSION, scenario_name),
                alert_type=AlertType.LATENCY_REGRESSION,
                severity=AlertSeverity.WARNING,
                scenario_name=scenario_name,
                message=f"P95 latency {state.p95_latency_ms:.0f}ms exceeds warning threshold",
                current_value=state.p95_latency_ms,
                threshold=self.WARNING_P95_LATENCY_MS,
                timestamp=time.time(),
            )
            alerts.append(alert)

        # Check provider health
        if state.provider_health_rate < self.CRITICAL_PROVIDER_HEALTH_RATE:
            alert = WhitelistAlert(
                alert_id=self._generate_alert_id(AlertType.PROVIDER_HEALTH_DROP, scenario_name),
                alert_type=AlertType.PROVIDER_HEALTH_DROP,
                severity=AlertSeverity.CRITICAL,
                scenario_name=scenario_name,
                message=f"Provider health {state.provider_health_rate:.1%} below critical threshold",
                current_value=state.provider_health_rate,
                threshold=self.CRITICAL_PROVIDER_HEALTH_RATE,
                timestamp=time.time(),
            )
            alerts.append(alert)
        elif state.provider_health_rate < self.WARNING_PROVIDER_HEALTH_RATE:
            alert = WhitelistAlert(
                alert_id=self._generate_alert_id(AlertType.PROVIDER_HEALTH_DROP, scenario_name),
                alert_type=AlertType.PROVIDER_HEALTH_DROP,
                severity=AlertSeverity.WARNING,
                scenario_name=scenario_name,
                message=f"Provider health {state.provider_health_rate:.1%} below warning threshold",
                current_value=state.provider_health_rate,
                threshold=self.WARNING_PROVIDER_HEALTH_RATE,
                timestamp=time.time(),
            )
            alerts.append(alert)

        # Check verdict-based alerts
        if state.verdict == ScenarioVerdict.DEMOTE_CANDIDATE:
            alert = WhitelistAlert(
                alert_id=self._generate_alert_id(AlertType.DEMOTION_CANDIDATE, scenario_name),
                alert_type=AlertType.DEMOTION_CANDIDATE,
                severity=AlertSeverity.WARNING,
                scenario_name=scenario_name,
                message=f"Scenario is a demotion candidate: {', '.join(state.blockers)}",
                current_value=state.verdict.value,
                threshold="healthy",
                timestamp=time.time(),
            )
            alerts.append(alert)
        elif state.verdict == ScenarioVerdict.ROLLBACK_CANDIDATE:
            alert = WhitelistAlert(
                alert_id=self._generate_alert_id(AlertType.ROLLBACK_CANDIDATE, scenario_name),
                alert_type=AlertType.ROLLBACK_CANDIDATE,
                severity=AlertSeverity.CRITICAL,
                scenario_name=scenario_name,
                message=f"Scenario is a rollback candidate: {', '.join(state.blockers)}",
                current_value=state.verdict.value,
                threshold="healthy",
                timestamp=time.time(),
            )
            alerts.append(alert)

        # Add alerts to history
        self.alerts.extend(alerts)
        self._save_alerts()

        return alerts

    def check_all_alerts(self) -> List[WhitelistAlert]:
        """
        Check for alerts on all production whitelist scenarios.
        
        Returns:
            List of all generated alerts
        """
        all_alerts = []
        promoted_scenarios = self.registry.get_production_whitelist()

        for scenario_name in promoted_scenarios:
            alerts = self.check_scenario_alerts(scenario_name)
            all_alerts.extend(alerts)

        return all_alerts

    def get_alert_summary(self) -> AlertSummary:
        """Get summary of current alerts."""
        recent_alerts = self.alerts[-100:]  # Last 100 alerts

        critical = sum(1 for a in recent_alerts if a.severity == AlertSeverity.CRITICAL)
        warning = sum(1 for a in recent_alerts if a.severity == AlertSeverity.WARNING)
        info = sum(1 for a in recent_alerts if a.severity == AlertSeverity.INFO)

        affected = list(set(a.scenario_name for a in recent_alerts))

        by_type: Dict[str, int] = {}
        for alert in recent_alerts:
            by_type[alert.alert_type.value] = by_type.get(alert.alert_type.value, 0) + 1

        by_scenario: Dict[str, int] = {}
        for alert in recent_alerts:
            by_scenario[alert.scenario_name] = by_scenario.get(alert.scenario_name, 0) + 1

        unacknowledged = sum(1 for a in recent_alerts if not a.acknowledged)

        return AlertSummary(
            total_alerts=len(recent_alerts),
            critical_count=critical,
            warning_count=warning,
            info_count=info,
            affected_scenarios=affected,
            alerts_by_type=by_type,
            alerts_by_scenario=by_scenario,
            unacknowledged_count=unacknowledged,
        )

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                self._save_alerts()
                return True
        return False

    def save_alert_summary(self) -> Path:
        """Save alert summary to file."""
        summary = self.get_alert_summary()
        summary_file = self.storage_path / "whitelist_alert_summary.json"
        summary_file.write_text(json.dumps(summary.to_dict(), indent=2))
        return summary_file
