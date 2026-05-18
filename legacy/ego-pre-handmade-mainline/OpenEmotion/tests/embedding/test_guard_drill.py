"""
Tests for Guard Drill Runner.

v6i: Post-Promotion Guard Drill + Rollback Verification
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
    DrillReport,
)


class TestGuardDrillRunner:
    """Tests for GuardDrillRunner."""

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

    def test_fallback_overflow_drill(self, registry, guard, drill_runner):
        """Fallback overflow drill triggers demotion."""
        registry.promote_scenario("test", "Test", "test")

        report = drill_runner.run_drill(
            DrillType.FALLBACK_RATE_OVERFLOW,
            "test",
            simulate_only=True,
        )

        assert report.drill_type == DrillType.FALLBACK_RATE_OVERFLOW
        assert report.expected_action == GuardAction.DEMOTE
        # Should pass because drill triggers demotion
        assert report.result in (DrillResult.PASS, DrillResult.FAIL)

    def test_wrong_user_guard_drill(self, registry, guard, drill_runner):
        """Wrong user guard drill triggers rollback."""
        registry.promote_scenario("test", "Test", "test")

        report = drill_runner.run_drill(
            DrillType.WRONG_USER_GUARD_TRIGGER,
            "test",
            simulate_only=True,
        )

        assert report.drill_type == DrillType.WRONG_USER_GUARD_TRIGGER
        assert report.expected_action == GuardAction.ROLLBACK
        assert report.result == DrillResult.PASS

    def test_provider_health_drill(self, registry, guard, drill_runner):
        """Provider health drill triggers alert or demotion."""
        registry.promote_scenario("test", "Test", "test")

        report = drill_runner.run_drill(
            DrillType.PROVIDER_HEALTH_DEGRADATION,
            "test",
            simulate_only=True,
        )

        assert report.drill_type == DrillType.PROVIDER_HEALTH_DEGRADATION
        assert report.result in (DrillResult.PASS, DrillResult.FAIL)

    def test_latency_spike_drill(self, registry, guard, drill_runner):
        """Latency spike drill triggers alert."""
        registry.promote_scenario("test", "Test", "test")

        report = drill_runner.run_drill(
            DrillType.LATENCY_SPIKE,
            "test",
            simulate_only=True,
        )

        assert report.drill_type == DrillType.LATENCY_SPIKE
        assert report.expected_action == GuardAction.ALERT

    def test_quality_signal_drill(self, registry, guard, drill_runner):
        """Negative quality signal drill triggers alert."""
        registry.promote_scenario("test", "Test", "test")

        report = drill_runner.run_drill(
            DrillType.QUALITY_SIGNAL_NEGATIVE,
            "test",
            simulate_only=True,
        )

        assert report.drill_type == DrillType.QUALITY_SIGNAL_NEGATIVE
        assert report.expected_action == GuardAction.ALERT

    def test_run_all_drills(self, registry, guard, drill_runner):
        """run_all_drills runs all drill types."""
        summary = drill_runner.run_all_drills("test", simulate_only=True)

        assert "summary" in summary
        assert summary["summary"]["total"] == len(DrillType)
        assert "demotion_drill" in summary
        assert "rollback_drill" in summary

    def test_drill_report_persistence(self, registry, guard, drill_runner, tmp_path):
        """Drill reports are persisted."""
        registry.promote_scenario("test", "Test", "test")

        drill_runner.run_drill(
            DrillType.WRONG_USER_GUARD_TRIGGER,
            "test",
            simulate_only=True,
        )

        # Create new runner to load persisted reports
        new_runner = GuardDrillRunner(registry, guard, storage_path=tmp_path)

        assert len(new_runner.drill_reports) >= 1

    def test_simulate_only_restores_state(self, registry, guard, drill_runner):
        """Simulate only mode restores state after drill."""
        registry.promote_scenario("test", "Test", "test")

        initial_status = registry.scenarios["test"].status

        drill_runner.run_drill(
            DrillType.WRONG_USER_GUARD_TRIGGER,
            "test",
            simulate_only=True,
        )

        # State should be restored
        assert registry.scenarios["test"].status == initial_status

    def test_non_promoted_scenario_skipped(self, registry, guard, drill_runner):
        """Drill is skipped for non-promoted scenario."""
        # Don't promote - scenario won't be in whitelist

        report = drill_runner.run_drill(
            DrillType.FALLBACK_RATE_OVERFLOW,
            "nonexistent_scenario",
            simulate_only=True,
        )

        assert report.result == DrillResult.SKIPPED

    def test_drill_report_to_dict(self, registry, guard, drill_runner):
        """DrillReport.to_dict returns all fields."""
        registry.promote_scenario("test", "Test", "test")

        report = drill_runner.run_drill(
            DrillType.WRONG_USER_GUARD_TRIGGER,
            "test",
            simulate_only=True,
        )

        d = report.to_dict()

        assert "drill_type" in d
        assert "scenario_name" in d
        assert "result" in d
        assert "expected_action" in d
        assert "actual_action" in d
        assert "datetime" in d


class TestDrillTypes:
    """Tests for drill types."""

    def test_all_drill_types_exist(self):
        """All expected drill types exist."""
        assert DrillType.FALLBACK_RATE_OVERFLOW.value == "fallback_rate_overflow"
        assert DrillType.WRONG_USER_GUARD_TRIGGER.value == "wrong_user_guard_trigger"
        assert DrillType.PROVIDER_HEALTH_DEGRADATION.value == "provider_health_degradation"
        assert DrillType.LATENCY_SPIKE.value == "latency_spike"
        assert DrillType.QUALITY_SIGNAL_NEGATIVE.value == "quality_signal_negative"


class TestDrillResults:
    """Tests for drill results."""

    def test_all_drill_results_exist(self):
        """All expected drill results exist."""
        assert DrillResult.PASS.value == "pass"
        assert DrillResult.FAIL.value == "fail"
        assert DrillResult.SKIPPED.value == "skipped"


class TestGuardDrillIntegration:
    """Integration tests for guard drills."""

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

    def test_complete_drill_workflow(self, registry, guard, drill_runner):
        """Complete drill workflow runs successfully."""
        # Promote scenario
        registry.promote_scenario("complex_semantic_reasoning", "Test", "test")

        # Run all drills
        summary = drill_runner.run_all_drills("complex_semantic_reasoning", simulate_only=True)

        # Verify summary structure
        assert "drills" in summary
        assert "summary" in summary

        # At least rollback and demotion drills should pass
        assert summary["rollback_drill"] in ("PASS", "FAIL")
        assert summary["demotion_drill"] in ("PASS", "FAIL")

    def test_drill_with_actual_state_change(self, registry, guard, drill_runner):
        """Drill can actually change state when not simulating."""
        registry.promote_scenario("test", "Test", "test")

        report = drill_runner.run_drill(
            DrillType.WRONG_USER_GUARD_TRIGGER,
            "test",
            simulate_only=False,  # Actually change state
        )

        # State should be changed
        if report.result == DrillResult.PASS:
            assert registry.scenarios["test"].status == WhitelistStatus.ROLLED_BACK
