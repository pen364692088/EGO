"""
Whitelist Alert Engine.

Generates structured alerts for whitelist governance.
Capability Owner: OpenEmotion

v6k.2: Alert Engine + Governance Consumption
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
    WhitelistVerdict,
)


class AlertType(str, Enum):
    """Types of whitelist alerts."""
    INSUFFICIENT_OBSERVATION_DATA = "insufficient_observation_data"
    FALLBACK_SPIKE = "fallback_spike"
    WRONG_USER_GUARD_TRIGGER = "wrong_user_guard_trigger"
    PROVIDER_HEALTH_DROP = "provider_health_drop"
    LATENCY_REGRESSION = "latency_regression"
    QUALITY_SIGNAL_REGRESSION = "quality_signal_regression"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class WhitelistAlertV2:
    """Structured alert for whitelist governance."""
    alert_id: str
    alert_type: AlertType
    scenario_name: str
    severity: AlertSeverity
    triggered_at: str
    source_metric: str
    threshold: Any
    observed_value: Any
    suggested_action: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type.value,
            "scenario_name": self.scenario_name,
            "severity": self.severity.value,
            "triggered_at": self.triggered_at,
            "source_metric": self.source_metric,
            "threshold": self.threshold,
            "observed_value": self.observed_value,
            "suggested_action": self.suggested_action,
            "timestamp": self.timestamp,
        }


class WhitelistAlertEngine:
    """
    Generates structured alerts for whitelist governance.

    v6k.2 specific:
    - Alert generation with structured schema
    - Governance consumption
    - Alert summary for verdict updates
    """

    # Warning thresholds
    WARNING_FALLBACK_RATE = 0.05
    WARNING_P95_LATENCY_MS = 100
    WARNING_PROVIDER_HEALTH_RATE = 0.98

    # Critical thresholds
    CRITICAL_FALLBACK_RATE = 0.10
    CRITICAL_WRONG_USER_GUARD = 0
    CRITICAL_PROVIDER_HEALTH_RATE = 0.95
    CRITICAL_P95_LATENCY_MS = 300
    CRITICAL_QUALITY_SIGNAL = 0.0

    def __init__(
        self,
        registry: ProductionWhitelistRegistry,
        governance: WhitelistGovernanceEvaluator,
        storage_path: Optional[Path] = None,
    ):
        self.registry = registry
        self.governance = governance
        self.storage_path = storage_path or Path("artifacts/eval/v6k_2")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.alerts: List[WhitelistAlertV2] = []
        self._load_alerts()

    def _load_alerts(self) -> None:
        """Load existing alerts."""
        alerts_file = self.storage_path / "whitelist_alerts.json"
        if alerts_file.exists():
            try:
                data = json.loads(alerts_file.read_text())
                self.alerts = [
                    WhitelistAlertV2(
                        alert_id=a.get("alert_id", ""),
                        alert_type=AlertType(a.get("alert_type", "fallback_spike")),
                        scenario_name=a.get("scenario_name", ""),
                        severity=AlertSeverity(a.get("severity", "warning")),
                        triggered_at=a.get("triggered_at", ""),
                        source_metric=a.get("source_metric", ""),
                        threshold=a.get("threshold"),
                        observed_value=a.get("observed_value"),
                        suggested_action=a.get("suggested_action", ""),
                        timestamp=a.get("timestamp", time.time()),
                    )
                    for a in data.get("alerts", [])
                ]
            except Exception:
                pass

    def _save_alerts(self) -> None:
        """Save alerts to storage."""
        alerts_file = self.storage_path / "whitelist_alerts.json"
        data = {
            "alerts": [a.to_dict() for a in self.alerts[-500:]],
            "generated_at": datetime.now().isoformat(),
        }
        alerts_file.write_text(json.dumps(data, indent=2))

    def _generate_alert_id(self, alert_type: AlertType, scenario_name: str) -> str:
        """Generate unique alert ID."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"alert-{alert_type.value}-{scenario_name}-{timestamp}"

    def generate_alerts_for_scenario(self, scenario_name: str) -> List[WhitelistAlertV2]:
        """Generate alerts for a specific scenario."""
        alerts = []

        if scenario_name not in self.registry.scenarios:
            return alerts

        state = self.governance.evaluate_scenario(scenario_name)
        now = datetime.now().isoformat()

        # BOOTSTRAP state: no observation data. Keep it non-critical, but emit
        # a structured warning so governance/reporting can track missing evidence.
        if state.verdict.value == "bootstrap":
            alert = WhitelistAlertV2(
                alert_id=self._generate_alert_id(AlertType.INSUFFICIENT_OBSERVATION_DATA, scenario_name),
                alert_type=AlertType.INSUFFICIENT_OBSERVATION_DATA,
                scenario_name=scenario_name,
                severity=AlertSeverity.WARNING,
                triggered_at=now,
                source_metric="request_count",
                threshold=1,
                observed_value=state.request_count,
                suggested_action="Collect observation data before promoting governance decisions",
            )
            alerts.append(alert)
            self.alerts.extend(alerts)
            self._save_alerts()
            return alerts

        # Check fallback_spike (critical)
        if state.fallback_rate > self.CRITICAL_FALLBACK_RATE:
            alert = WhitelistAlertV2(
                alert_id=self._generate_alert_id(AlertType.FALLBACK_SPIKE, scenario_name),
                alert_type=AlertType.FALLBACK_SPIKE,
                scenario_name=scenario_name,
                severity=AlertSeverity.CRITICAL,
                triggered_at=now,
                source_metric="fallback_rate",
                threshold=self.CRITICAL_FALLBACK_RATE,
                observed_value=state.fallback_rate,
                suggested_action="Consider demoting scenario to pilot for investigation",
            )
            alerts.append(alert)

        # Check fallback_spike (warning)
        elif state.fallback_rate > self.WARNING_FALLBACK_RATE:
            alert = WhitelistAlertV2(
                alert_id=self._generate_alert_id(AlertType.FALLBACK_SPIKE, scenario_name),
                alert_type=AlertType.FALLBACK_SPIKE,
                scenario_name=scenario_name,
                severity=AlertSeverity.WARNING,
                triggered_at=now,
                source_metric="fallback_rate",
                threshold=self.WARNING_FALLBACK_RATE,
                observed_value=state.fallback_rate,
                suggested_action="Monitor fallback rate closely",
            )
            alerts.append(alert)

        # Check wrong_user_guard_trigger (critical)
        if state.wrong_user_guard_trigger_count > self.CRITICAL_WRONG_USER_GUARD:
            alert = WhitelistAlertV2(
                alert_id=self._generate_alert_id(AlertType.WRONG_USER_GUARD_TRIGGER, scenario_name),
                alert_type=AlertType.WRONG_USER_GUARD_TRIGGER,
                scenario_name=scenario_name,
                severity=AlertSeverity.CRITICAL,
                triggered_at=now,
                source_metric="wrong_user_guard_trigger_count",
                threshold=self.CRITICAL_WRONG_USER_GUARD,
                observed_value=state.wrong_user_guard_trigger_count,
                suggested_action="Immediate rollback recommended",
            )
            alerts.append(alert)

        # Check provider_health_drop (critical)
        if state.provider_health_rate < self.CRITICAL_PROVIDER_HEALTH_RATE:
            alert = WhitelistAlertV2(
                alert_id=self._generate_alert_id(AlertType.PROVIDER_HEALTH_DROP, scenario_name),
                alert_type=AlertType.PROVIDER_HEALTH_DROP,
                scenario_name=scenario_name,
                severity=AlertSeverity.CRITICAL,
                triggered_at=now,
                source_metric="provider_health_rate",
                threshold=self.CRITICAL_PROVIDER_HEALTH_RATE,
                observed_value=state.provider_health_rate,
                suggested_action="Investigate provider health, consider demotion",
            )
            alerts.append(alert)

        # Check provider_health_drop (warning)
        elif state.provider_health_rate < self.WARNING_PROVIDER_HEALTH_RATE:
            alert = WhitelistAlertV2(
                alert_id=self._generate_alert_id(AlertType.PROVIDER_HEALTH_DROP, scenario_name),
                alert_type=AlertType.PROVIDER_HEALTH_DROP,
                scenario_name=scenario_name,
                severity=AlertSeverity.WARNING,
                triggered_at=now,
                source_metric="provider_health_rate",
                threshold=self.WARNING_PROVIDER_HEALTH_RATE,
                observed_value=state.provider_health_rate,
                suggested_action="Monitor provider health",
            )
            alerts.append(alert)

        # Check latency_regression (critical)
        if state.p95_latency_ms > self.CRITICAL_P95_LATENCY_MS:
            alert = WhitelistAlertV2(
                alert_id=self._generate_alert_id(AlertType.LATENCY_REGRESSION, scenario_name),
                alert_type=AlertType.LATENCY_REGRESSION,
                scenario_name=scenario_name,
                severity=AlertSeverity.CRITICAL,
                triggered_at=now,
                source_metric="p95_latency_ms",
                threshold=self.CRITICAL_P95_LATENCY_MS,
                observed_value=state.p95_latency_ms,
                suggested_action="Investigate latency issues, consider demotion",
            )
            alerts.append(alert)

        # Check latency_regression (warning)
        elif state.p95_latency_ms > self.WARNING_P95_LATENCY_MS:
            alert = WhitelistAlertV2(
                alert_id=self._generate_alert_id(AlertType.LATENCY_REGRESSION, scenario_name),
                alert_type=AlertType.LATENCY_REGRESSION,
                scenario_name=scenario_name,
                severity=AlertSeverity.WARNING,
                triggered_at=now,
                source_metric="p95_latency_ms",
                threshold=self.WARNING_P95_LATENCY_MS,
                observed_value=state.p95_latency_ms,
                suggested_action="Monitor latency trends",
            )
            alerts.append(alert)

        # Check quality_signal_regression (critical)
        if state.quality_gain_signal <= self.CRITICAL_QUALITY_SIGNAL:
            alert = WhitelistAlertV2(
                alert_id=self._generate_alert_id(AlertType.QUALITY_SIGNAL_REGRESSION, scenario_name),
                alert_type=AlertType.QUALITY_SIGNAL_REGRESSION,
                scenario_name=scenario_name,
                severity=AlertSeverity.CRITICAL,
                triggered_at=now,
                source_metric="quality_gain_signal",
                threshold=self.CRITICAL_QUALITY_SIGNAL,
                observed_value=state.quality_gain_signal,
                suggested_action="Investigate quality signal, may need demotion",
            )
            alerts.append(alert)

        self.alerts.extend(alerts)
        self._save_alerts()

        return alerts

    def generate_all_alerts(self) -> List[WhitelistAlertV2]:
        """Generate alerts for all whitelist scenarios."""
        all_alerts = []
        promoted_scenarios = self.registry.get_production_whitelist()

        for scenario_name in promoted_scenarios:
            alerts = self.generate_alerts_for_scenario(scenario_name)
            all_alerts.extend(alerts)

        return all_alerts

    def get_alerts_summary(self) -> Dict[str, Any]:
        """Get summary of current alerts."""
        recent_alerts = self.alerts[-100:]

        critical = [a for a in recent_alerts if a.severity == AlertSeverity.CRITICAL]
        warning = [a for a in recent_alerts if a.severity == AlertSeverity.WARNING]

        alert_types: Dict[str, int] = {}
        for alert in recent_alerts:
            alert_types[alert.alert_type.value] = alert_types.get(alert.alert_type.value, 0) + 1

        affected_scenarios = list(set(a.scenario_name for a in recent_alerts))

        return {
            "total_alerts": len(recent_alerts),
            "critical_count": len(critical),
            "warning_count": len(warning),
            "alert_types": alert_types,
            "affected_scenarios": affected_scenarios,
            "generated_at": datetime.now().isoformat(),
        }

    def get_governance_impact(self) -> Dict[str, Any]:
        """Get governance impact from alerts."""
        summary = self.get_alerts_summary()

        # Determine impact on governance
        has_critical = summary["critical_count"] > 0
        has_warning = summary["warning_count"] > 0

        impact = {
            "scenario_verdicts_updated": has_critical or has_warning,
            "whitelist_verdict_updated": has_critical,
            "blockers_updated": has_critical or has_warning,
            "expansion_readiness_updated": has_critical,
            "reason": None,
        }

        if has_critical:
            impact["reason"] = "Critical alerts detected, governance verdicts updated"
        elif has_warning:
            impact["reason"] = "Warning alerts detected, scenario verdicts updated"
        else:
            impact["reason"] = "No alerts, governance stable"

        return impact

    def save_alert_summary(self) -> Path:
        """Save alert summary to file."""
        summary = self.get_alerts_summary()
        summary["governance_impact"] = self.get_governance_impact()

        summary_file = self.storage_path / "whitelist_alert_summary.json"
        summary_file.write_text(json.dumps(summary, indent=2))
        return summary_file
