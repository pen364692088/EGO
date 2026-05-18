"""
Tests for v6k.2a Alert → Governance Consistency.

Ensures alerts are correctly reflected in governance consumption.
"""

import pytest
from pathlib import Path
import json

from emotiond.memory.embedding.production_whitelist import ProductionWhitelistRegistry
from emotiond.memory.embedding.whitelist_governance import WhitelistGovernanceEvaluator
from emotiond.memory.embedding.whitelist_alert_engine import (
    WhitelistAlertEngine,
    AlertType,
    AlertSeverity,
)
from emotiond.memory.embedding.whitelist_operations_reporter import (
    WhitelistOperationsReporter,
    GovernanceConsumption,
)


class TestV6k2aAlertGovernanceConsistency:
    """Tests for alert → governance consistency."""

    @pytest.fixture
    def reporter(self, tmp_path):
        return WhitelistOperationsReporter(storage_path=tmp_path)

    def test_critical_alert_updates_governance(self, reporter):
        """Critical alerts MUST update governance verdicts."""
        # Create alerts with critical severity
        alerts = [
            {
                "alert_id": "alert-critical-1",
                "alert_type": "provider_health_drop",
                "scenario_name": "memory_search_hard_query",
                "severity": "critical",
                "triggered_at": "2026-03-16T20:00:00",
                "source_metric": "provider_health_rate",
                "threshold": 0.95,
                "observed_value": 0.0,
                "suggested_action": "Investigate",
            }
        ]
        
        alerts_file = reporter.storage_path / "whitelist_alerts.json"
        alerts_file.write_text(json.dumps({"alerts": alerts, "generated_at": "2026-03-16T20:00:00"}))

        summary = reporter.get_alerts_summary()
        consumption = reporter.get_governance_consumption(summary)

        assert summary["critical_count"] == 1
        assert consumption.whitelist_verdict_updated is True
        assert consumption.expansion_readiness_updated is True

    def test_warning_alert_does_not_update_whitelist_verdict(self, reporter):
        """Warning alerts should NOT update whitelist verdict."""
        alerts = [
            {
                "alert_id": "alert-warning-1",
                "alert_type": "latency_regression",
                "scenario_name": "memory_search_hard_query",
                "severity": "warning",
                "triggered_at": "2026-03-16T20:00:00",
                "source_metric": "p95_latency_ms",
                "threshold": 100,
                "observed_value": 150,
                "suggested_action": "Monitor",
            }
        ]
        
        alerts_file = reporter.storage_path / "whitelist_alerts.json"
        alerts_file.write_text(json.dumps({"alerts": alerts, "generated_at": "2026-03-16T20:00:00"}))

        summary = reporter.get_alerts_summary()
        consumption = reporter.get_governance_consumption(summary)

        assert summary["warning_count"] == 1
        assert summary["critical_count"] == 0
        assert consumption.whitelist_verdict_updated is False
        assert consumption.scenario_verdicts_updated is True

    def test_mixed_alerts_treats_as_critical(self, reporter):
        """If both critical and warning exist, treat as critical."""
        alerts = [
            {
                "alert_id": "alert-critical-1",
                "alert_type": "provider_health_drop",
                "scenario_name": "memory_search_hard_query",
                "severity": "critical",
                "triggered_at": "2026-03-16T20:00:00",
                "source_metric": "provider_health_rate",
                "threshold": 0.95,
                "observed_value": 0.0,
                "suggested_action": "Investigate",
            },
            {
                "alert_id": "alert-warning-1",
                "alert_type": "latency_regression",
                "scenario_name": "narrative_recall_ambiguous_query",
                "severity": "warning",
                "triggered_at": "2026-03-16T20:00:00",
                "source_metric": "p95_latency_ms",
                "threshold": 100,
                "observed_value": 150,
                "suggested_action": "Monitor",
            }
        ]
        
        alerts_file = reporter.storage_path / "whitelist_alerts.json"
        alerts_file.write_text(json.dumps({"alerts": alerts, "generated_at": "2026-03-16T20:00:00"}))

        summary = reporter.get_alerts_summary()
        consumption = reporter.get_governance_consumption(summary)

        assert summary["critical_count"] == 1
        assert summary["warning_count"] == 1
        # Critical takes precedence
        assert consumption.whitelist_verdict_updated is True
        assert consumption.expansion_readiness_updated is True

    def test_no_alerts_no_governance_change(self, reporter):
        """No alerts means no governance changes."""
        alerts_file = reporter.storage_path / "whitelist_alerts.json"
        alerts_file.write_text(json.dumps({"alerts": [], "generated_at": "2026-03-16T20:00:00"}))

        summary = reporter.get_alerts_summary()
        consumption = reporter.get_governance_consumption(summary)

        assert summary["critical_count"] == 0
        assert summary["warning_count"] == 0
        assert consumption.scenario_verdicts_updated is False
        assert consumption.whitelist_verdict_updated is False

    def test_report_consistency_check(self, reporter):
        """Report consistency check passes when alerts match governance."""
        alerts = [
            {
                "alert_id": "alert-critical-1",
                "alert_type": "provider_health_drop",
                "scenario_name": "memory_search_hard_query",
                "severity": "critical",
                "triggered_at": "2026-03-16T20:00:00",
                "source_metric": "provider_health_rate",
                "threshold": 0.95,
                "observed_value": 0.0,
                "suggested_action": "Investigate",
            }
        ]
        
        alerts_file = reporter.storage_path / "whitelist_alerts.json"
        alerts_file.write_text(json.dumps({"alerts": alerts, "generated_at": "2026-03-16T20:00:00"}))

        report_path = reporter.save_consistency_report()
        consistency = json.loads(report_path.read_text())

        assert consistency["consistency_checks"]["alerts_match_summary"] is True
        assert consistency["consistency_checks"]["summary_match_governance"] is True
        assert consistency["consistency_checks"]["critical_triggers_verdict_update"] is True


class TestV6k2aSchedulerEvidence:
    """Tests for scheduler evidence."""

    @pytest.fixture
    def storage(self, tmp_path):
        return tmp_path

    def test_scheduler_evidence_generated(self, storage):
        """Scheduler evidence is generated with required fields."""
        evidence = {
            "scheduler_type": "cron",
            "config_file": "/etc/crontab (user crontab)",
            "trigger_time": "2026-03-16T20:00:00",
            "trigger_type": "daily",
            "script_path": "/path/to/script.sh",
            "schedule": "0 3 * * *",
            "evidence_valid": True,
        }

        evidence_file = storage / "scheduler_evidence.json"
        evidence_file.write_text(json.dumps(evidence, indent=2))

        loaded = json.loads(evidence_file.read_text())

        assert loaded["scheduler_type"] == "cron"
        assert loaded["evidence_valid"] is True

    def test_round_scheduler_evidence(self, storage):
        """Round scheduler evidence includes round_id."""
        evidence = {
            "scheduler_type": "cron",
            "trigger_type": "round",
            "round_id": "2026031620",
            "trigger_time": "2026-03-16T20:00:00",
            "evidence_valid": True,
        }

        evidence_file = storage / "scheduler_evidence_round.json"
        evidence_file.write_text(json.dumps(evidence, indent=2))

        loaded = json.loads(evidence_file.read_text())

        assert loaded["trigger_type"] == "round"
        assert loaded["round_id"] == "2026031620"


class TestV6k2aOperationsReport:
    """Tests for operations report generation."""

    @pytest.fixture
    def reporter(self, tmp_path):
        return WhitelistOperationsReporter(storage_path=tmp_path)

    def test_report_generated(self, reporter):
        """Operations report is generated."""
        # Create minimal artifacts
        alerts_file = reporter.storage_path / "whitelist_alerts.json"
        alerts_file.write_text(json.dumps({"alerts": [], "generated_at": "2026-03-16T20:00:00"}))

        runs_file = reporter.storage_path / "scheduler_runs.json"
        runs_file.write_text(json.dumps({"runs": [], "generated_at": "2026-03-16T20:00:00"}))

        report = reporter.generate_operations_report()

        assert "# v6k.2a: Whitelist Operations Report" in report
        assert "Governance Consumption" in report

    def test_report_includes_severity_breakdown(self, reporter):
        """Report includes correct severity breakdown."""
        alerts = [
            {
                "alert_id": "alert-critical-1",
                "alert_type": "provider_health_drop",
                "scenario_name": "test_scenario",
                "severity": "critical",
                "triggered_at": "2026-03-16T20:00:00",
                "source_metric": "test",
                "threshold": 0.95,
                "observed_value": 0.0,
                "suggested_action": "Test",
            }
        ]
        
        alerts_file = reporter.storage_path / "whitelist_alerts.json"
        alerts_file.write_text(json.dumps({"alerts": alerts, "generated_at": "2026-03-16T20:00:00"}))

        report = reporter.generate_operations_report()

        assert "critical (1)" in report
