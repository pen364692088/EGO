"""
Tests for v6j Guard Drill Completion.

v6j: Demotion/Rollback Guard Drill Completion
"""

import pytest
from pathlib import Path

from emotiond.memory.embedding.production_whitelist import (
    ProductionWhitelistRegistry,
    WhitelistStatus,
)
from emotiond.memory.embedding.post_promotion_guard import PostPromotionGuard, GuardAction
from emotiond.memory.embedding.guard_drill import (
    GuardDrillRunner,
    DrillType,
    DrillResult,
)


class TestV6jDemotionDrill:
    """Tests for demotion drill completion."""

    @pytest.fixture
    def registry(self, tmp_path):
        return ProductionWhitelistRegistry(storage_path=tmp_path)

    @pytest.fixture
    def guard(self, registry, tmp_path):
        guard = PostPromotionGuard(registry)
        guard.storage_path = tmp_path
        return guard

    @pytest.fixture
    def drill_runner(self, registry, guard, tmp_path):
        runner = GuardDrillRunner(registry, guard, storage_path=tmp_path)
        runner.storage_path = tmp_path
        return runner

    def test_demotion_drill_triggers_on_high_fallback(self, registry, drill_runner):
        """Demotion drill triggers when fallback_rate > 10%."""
        registry.promote_scenario("test", "Drill", "v6j")

        report = drill_runner.run_drill(
            DrillType.FALLBACK_RATE_OVERFLOW,
            "test",
            simulate_only=False,
        )

        assert report.result == DrillResult.PASS
        assert report.actual_status == WhitelistStatus.DEMOTED
        assert report.details.get("demotion_triggered") is True

    def test_demotion_drill_fallback_rate_exceeds_threshold(self, registry, drill_runner):
        """Demotion drill creates fallback rate > 10%."""
        registry.promote_scenario("test", "Drill", "v6j")

        report = drill_runner.run_drill(
            DrillType.FALLBACK_RATE_OVERFLOW,
            "test",
            simulate_only=False,
        )

        fallback_rate = report.details.get("fallback_rate", 0)
        assert fallback_rate > 0.10, f"Expected fallback_rate > 10%, got {fallback_rate:.1%}"

    def test_demotion_drill_status_changes_to_demoted(self, registry, drill_runner):
        """Scenario status changes to DEMOTED after demotion drill."""
        registry.promote_scenario("test", "Drill", "v6j")
        initial_status = registry.scenarios["test"].status
        assert initial_status == WhitelistStatus.PROMOTED

        drill_runner.run_drill(
            DrillType.FALLBACK_RATE_OVERFLOW,
            "test",
            simulate_only=False,
        )

        assert registry.scenarios["test"].status == WhitelistStatus.DEMOTED

    def test_demotion_drill_restores_on_simulate(self, registry, drill_runner):
        """Demotion drill restores state when simulate_only=True."""
        registry.promote_scenario("test", "Drill", "v6j")

        report = drill_runner.run_drill(
            DrillType.FALLBACK_RATE_OVERFLOW,
            "test",
            simulate_only=True,
        )

        if report.result == DrillResult.PASS:
            # State should be restored
            assert registry.scenarios["test"].status == WhitelistStatus.PROMOTED


class TestV6jRollbackDrill:
    """Tests for rollback drill completion."""

    @pytest.fixture
    def registry(self, tmp_path):
        return ProductionWhitelistRegistry(storage_path=tmp_path)

    @pytest.fixture
    def guard(self, registry, tmp_path):
        guard = PostPromotionGuard(registry)
        guard.storage_path = tmp_path
        return guard

    @pytest.fixture
    def drill_runner(self, registry, guard, tmp_path):
        runner = GuardDrillRunner(registry, guard, storage_path=tmp_path)
        runner.storage_path = tmp_path
        return runner

    def test_rollback_drill_triggers_on_wrong_user_guard(self, registry, drill_runner):
        """Rollback drill triggers when wrong_user_guard > 0."""
        registry.promote_scenario("test", "Drill", "v6j")

        report = drill_runner.run_drill(
            DrillType.WRONG_USER_GUARD_TRIGGER,
            "test",
            simulate_only=False,
        )

        assert report.result == DrillResult.PASS
        assert report.actual_status == WhitelistStatus.ROLLED_BACK

    def test_rollback_drill_wrong_user_guard_count(self, registry, drill_runner):
        """Rollback drill increments wrong_user_guard_trigger_count."""
        registry.promote_scenario("test", "Drill", "v6j")

        initial_count = registry.scenarios["test"].wrong_user_guard_trigger_count
        assert initial_count == 0

        drill_runner.run_drill(
            DrillType.WRONG_USER_GUARD_TRIGGER,
            "test",
            simulate_only=False,
        )

        assert registry.scenarios["test"].wrong_user_guard_trigger_count > 0

    def test_rollback_drill_status_changes_to_rolled_back(self, registry, drill_runner):
        """Scenario status changes to ROLLED_BACK after rollback drill."""
        registry.promote_scenario("test", "Drill", "v6j")
        initial_status = registry.scenarios["test"].status
        assert initial_status == WhitelistStatus.PROMOTED

        drill_runner.run_drill(
            DrillType.WRONG_USER_GUARD_TRIGGER,
            "test",
            simulate_only=False,
        )

        assert registry.scenarios["test"].status == WhitelistStatus.ROLLED_BACK

    def test_rollback_drill_restores_on_simulate(self, registry, drill_runner):
        """Rollback drill restores state when simulate_only=True."""
        registry.promote_scenario("test", "Drill", "v6j")

        report = drill_runner.run_drill(
            DrillType.WRONG_USER_GUARD_TRIGGER,
            "test",
            simulate_only=True,
        )

        if report.result == DrillResult.PASS:
            # State should be restored
            assert registry.scenarios["test"].status == WhitelistStatus.PROMOTED


class TestV6jDrillRecovery:
    """Tests for drill recovery mechanisms."""

    @pytest.fixture
    def registry(self, tmp_path):
        return ProductionWhitelistRegistry(storage_path=tmp_path)

    @pytest.fixture
    def guard(self, registry, tmp_path):
        guard = PostPromotionGuard(registry)
        guard.storage_path = tmp_path
        return guard

    @pytest.fixture
    def drill_runner(self, registry, guard, tmp_path):
        runner = GuardDrillRunner(registry, guard, storage_path=tmp_path)
        runner.storage_path = tmp_path
        return runner

    def test_system_recoverable_after_demotion_drill(self, registry, drill_runner):
        """System can be restored after demotion drill."""
        registry.promote_scenario("test", "Drill", "v6j")

        drill_runner.run_drill(
            DrillType.FALLBACK_RATE_OVERFLOW,
            "test",
            simulate_only=False,
        )

        # Verify demotion happened
        assert registry.scenarios["test"].status == WhitelistStatus.DEMOTED

        # Restore
        registry.scenarios["test"].status = WhitelistStatus.PROMOTED
        registry.scenarios["test"].fallback_count = 0
        registry.scenarios["test"].request_count = 0
        registry._save_state()

        # Verify restored
        assert registry.scenarios["test"].status == WhitelistStatus.PROMOTED
        assert registry.scenarios["test"].fallback_rate == 0

    def test_system_recoverable_after_rollback_drill(self, registry, drill_runner):
        """System can be restored after rollback drill."""
        registry.promote_scenario("test", "Drill", "v6j")

        drill_runner.run_drill(
            DrillType.WRONG_USER_GUARD_TRIGGER,
            "test",
            simulate_only=False,
        )

        # Verify rollback happened
        assert registry.scenarios["test"].status == WhitelistStatus.ROLLED_BACK

        # Restore
        registry.scenarios["test"].status = WhitelistStatus.PROMOTED
        registry.scenarios["test"].wrong_user_guard_trigger_count = 0
        registry._save_state()

        # Verify restored
        assert registry.scenarios["test"].status == WhitelistStatus.PROMOTED
        assert registry.scenarios["test"].wrong_user_guard_trigger_count == 0


class TestV6jDrillReports:
    """Tests for drill report generation."""

    @pytest.fixture
    def registry(self, tmp_path):
        return ProductionWhitelistRegistry(storage_path=tmp_path)

    @pytest.fixture
    def guard(self, registry, tmp_path):
        guard = PostPromotionGuard(registry)
        guard.storage_path = tmp_path
        return guard

    @pytest.fixture
    def drill_runner(self, registry, guard, tmp_path):
        runner = GuardDrillRunner(registry, guard, storage_path=tmp_path)
        runner.storage_path = tmp_path
        return runner

    def test_demotion_drill_generates_report(self, registry, drill_runner, tmp_path):
        """Demotion drill generates structured report."""
        registry.promote_scenario("test", "Drill", "v6j")

        report = drill_runner.run_drill(
            DrillType.FALLBACK_RATE_OVERFLOW,
            "test",
            simulate_only=False,
        )

        report_dict = report.to_dict()
        assert "drill_type" in report_dict
        assert "result" in report_dict
        assert "actual_status" in report_dict
        assert "details" in report_dict

    def test_rollback_drill_generates_report(self, registry, drill_runner, tmp_path):
        """Rollback drill generates structured report."""
        registry.promote_scenario("test", "Drill", "v6j")

        report = drill_runner.run_drill(
            DrillType.WRONG_USER_GUARD_TRIGGER,
            "test",
            simulate_only=False,
        )

        report_dict = report.to_dict()
        assert "drill_type" in report_dict
        assert "result" in report_dict
        assert "actual_status" in report_dict

    def test_drill_reports_persisted(self, registry, drill_runner, tmp_path):
        """Drill reports are persisted to storage."""
        registry.promote_scenario("test", "Drill", "v6j")

        drill_runner.run_drill(
            DrillType.FALLBACK_RATE_OVERFLOW,
            "test",
            simulate_only=False,
        )

        # Check reports file exists
        reports_file = tmp_path / "guard_drill_report.json"
        assert reports_file.exists()
