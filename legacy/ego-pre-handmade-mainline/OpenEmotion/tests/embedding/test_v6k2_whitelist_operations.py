"""
Tests for v6k.2 Whitelist Operations.

v6k.2: Scheduler + Receipt History + Alert Engine
"""

import pytest
from pathlib import Path

from emotiond.memory.embedding.production_whitelist import ProductionWhitelistRegistry
from emotiond.memory.embedding.whitelist_governance import WhitelistGovernanceEvaluator
from emotiond.memory.embedding.receipt_history import (
    ReceiptHistoryStore,
    ReceiptIndex,
)
from emotiond.memory.embedding.whitelist_alert_engine import (
    WhitelistAlertEngine,
    AlertType,
    AlertSeverity,
)
from emotiond.memory.embedding.whitelist_scheduler import (
    WhitelistScheduler,
    SchedulerRun,
)
from emotiond.memory.embedding.periodic_receipts import ReceiptMode


class TestV6k2ReceiptHistory:
    """Tests for receipt history store."""

    @pytest.fixture
    def history(self, tmp_path):
        return ReceiptHistoryStore(storage_path=tmp_path)

    def test_add_receipt(self, history):
        """Receipt can be added to history."""
        history.add_receipt(
            receipt_id="test-daily-1",
            mode=ReceiptMode.DAILY,
            generated_at="2026-03-16T10:00:00",
            artifact_path="test.json",
            scenario_count=4,
            whitelist_verdict="stable",
        )

        assert len(history.index[ReceiptMode.DAILY.value]) == 1

    def test_get_latest(self, history):
        """Latest receipt can be retrieved."""
        history.add_receipt(
            receipt_id="test-daily-1",
            mode=ReceiptMode.DAILY,
            generated_at="2026-03-16T10:00:00",
            artifact_path="test1.json",
            scenario_count=4,
            whitelist_verdict="stable",
        )
        history.add_receipt(
            receipt_id="test-daily-2",
            mode=ReceiptMode.DAILY,
            generated_at="2026-03-16T11:00:00",
            artifact_path="test2.json",
            scenario_count=4,
            whitelist_verdict="observe",
        )

        latest = history.get_latest(ReceiptMode.DAILY)
        assert latest.receipt_id == "test-daily-2"

    def test_get_by_date(self, history):
        """Receipts can be queried by date."""
        history.add_receipt(
            receipt_id="test-1",
            mode=ReceiptMode.DAILY,
            generated_at="2026-03-16T10:00:00",
            artifact_path="test1.json",
            scenario_count=4,
            whitelist_verdict="stable",
        )
        history.add_receipt(
            receipt_id="test-2",
            mode=ReceiptMode.ROUND_BASED,
            generated_at="2026-03-16T11:00:00",
            artifact_path="test2.json",
            scenario_count=4,
            whitelist_verdict="observe",
        )

        results = history.get_by_date("2026-03-16")
        assert len(results) == 2

    def test_retention_policy(self, history):
        """Retention policy is applied."""
        # Add 10 daily receipts (exceeds retention of 7)
        for i in range(10):
            history.add_receipt(
                receipt_id=f"test-daily-{i}",
                mode=ReceiptMode.DAILY,
                generated_at=f"2026-03-{16+i:02d}T10:00:00",
                artifact_path=f"test{i}.json",
                scenario_count=4,
                whitelist_verdict="stable",
            )

        # Should only keep last 7
        assert len(history.index[ReceiptMode.DAILY.value]) == 7

    def test_history_summary(self, history):
        """History summary is generated."""
        history.add_receipt(
            receipt_id="test-daily-1",
            mode=ReceiptMode.DAILY,
            generated_at="2026-03-16T10:00:00",
            artifact_path="test.json",
            scenario_count=4,
            whitelist_verdict="stable",
        )
        history.add_receipt(
            receipt_id="test-round-1",
            mode=ReceiptMode.ROUND_BASED,
            generated_at="2026-03-16T11:00:00",
            artifact_path="test2.json",
            scenario_count=4,
            whitelist_verdict="observe",
        )

        summary = history.get_summary()
        assert summary["daily_receipt_count"] == 1
        assert summary["round_receipt_count"] == 1


class TestV6k2AlertEngine:
    """Tests for alert engine."""

    @pytest.fixture
    def registry(self, tmp_path):
        return ProductionWhitelistRegistry(storage_path=tmp_path)

    @pytest.fixture
    def governance(self, registry, tmp_path):
        return WhitelistGovernanceEvaluator(registry, storage_path=tmp_path)

    @pytest.fixture
    def alert_engine(self, registry, governance, tmp_path):
        return WhitelistAlertEngine(registry, governance, storage_path=tmp_path)

    def test_generate_alerts_for_scenario(self, registry, alert_engine):
        """Alerts can be generated for a scenario."""
        scenario_name = "memory_search_hard_query"

        alerts = alert_engine.generate_alerts_for_scenario(scenario_name)

        # Should have alerts due to no observation data
        assert len(alerts) >= 1

    def test_alert_has_required_fields(self, registry, alert_engine):
        """Alert has all required fields."""
        scenario_name = "memory_search_hard_query"

        alerts = alert_engine.generate_alerts_for_scenario(scenario_name)

        if alerts:
            alert = alerts[0]
            assert alert.alert_id != ""
            assert alert.alert_type in AlertType
            assert alert.scenario_name == scenario_name
            assert alert.severity in AlertSeverity
            assert alert.suggested_action != ""

    def test_alerts_summary(self, registry, alert_engine):
        """Alerts summary is generated."""
        alert_engine.generate_all_alerts()

        summary = alert_engine.get_alerts_summary()

        assert "total_alerts" in summary
        assert "critical_count" in summary
        assert "warning_count" in summary
        assert "affected_scenarios" in summary

    def test_governance_impact(self, registry, alert_engine):
        """Governance impact is calculated."""
        alert_engine.generate_all_alerts()

        impact = alert_engine.get_governance_impact()

        assert "scenario_verdicts_updated" in impact
        assert "whitelist_verdict_updated" in impact
        assert "blockers_updated" in impact


class TestV6k2Scheduler:
    """Tests for whitelist scheduler."""

    @pytest.fixture
    def scheduler(self, tmp_path):
        return WhitelistScheduler(storage_path=tmp_path)

    @pytest.fixture
    def registry_storage(self, tmp_path):
        # Create a minimal registry
        registry = ProductionWhitelistRegistry(storage_path=tmp_path)
        return tmp_path

    def test_run_daily(self, scheduler, registry_storage):
        """Daily run executes successfully."""
        run = scheduler.run_daily(registry_storage)

        assert run.trigger_type == "daily"
        assert run.success is True
        assert run.receipt_id is not None

    def test_run_round(self, scheduler, registry_storage):
        """Round run executes successfully."""
        run = scheduler.run_round(round_id=1, registry_storage=registry_storage)

        assert run.trigger_type == "round"
        assert run.success is True
        assert run.receipt_id is not None

    def test_run_manual(self, scheduler, registry_storage):
        """Manual run executes successfully."""
        run = scheduler.run_manual(reason="Test", registry_storage=registry_storage)

        assert run.trigger_type == "manual"
        assert run.success is True

    def test_run_history(self, scheduler, registry_storage):
        """Run history is tracked."""
        scheduler.run_daily(registry_storage)
        scheduler.run_round(round_id=1, registry_storage=registry_storage)

        runs = scheduler.get_recent_runs(limit=10)

        assert len(runs) == 2

    def test_scheduler_status(self, scheduler, registry_storage):
        """Scheduler status is available."""
        scheduler.run_daily(registry_storage)

        status = scheduler.get_scheduler_status()

        assert status["total_runs"] >= 1
        assert status["last_run"] is not None


class TestV6k2GovernanceConsumption:
    """Tests for governance consuming alerts."""

    @pytest.fixture
    def registry(self, tmp_path):
        return ProductionWhitelistRegistry(storage_path=tmp_path)

    @pytest.fixture
    def governance(self, registry, tmp_path):
        return WhitelistGovernanceEvaluator(registry, storage_path=tmp_path)

    @pytest.fixture
    def alert_engine(self, registry, governance, tmp_path):
        return WhitelistAlertEngine(registry, governance, storage_path=tmp_path)

    def test_alerts_affect_governance(self, registry, governance, alert_engine):
        """Alerts affect governance verdicts."""
        # Generate alerts
        alerts = alert_engine.generate_all_alerts()

        # Get governance impact
        impact = alert_engine.get_governance_impact()

        # If there are alerts, governance should be updated
        if alerts:
            assert impact["scenario_verdicts_updated"] is True
