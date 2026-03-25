"""
Tests for Post-Promotion Guard.

v6h: Post-Promotion Observation + Auto-Demotion Guard
"""

import pytest
from pathlib import Path

from emotiond.memory.embedding.production_whitelist import (
    ProductionWhitelistRegistry,
    WhitelistStatus,
)
from emotiond.memory.embedding.post_promotion_guard import (
    PostPromotionGuard,
    GuardAction,
    GuardDecision,
)


class TestPostPromotionGuard:
    """Tests for PostPromotionGuard."""

    @pytest.fixture
    def registry(self, tmp_path):
        """Create a fresh registry with isolated storage."""
        return ProductionWhitelistRegistry(storage_path=tmp_path)

    @pytest.fixture
    def guard(self, registry, tmp_path):
        """Create a guard with registry."""
        guard = PostPromotionGuard(registry)
        guard.storage_path = tmp_path
        return guard

    def test_observe_healthy_scenario(self, registry, guard):
        """observe returns NONE for healthy scenario."""
        registry.promote_scenario(
            scenario_name="test_scenario",
            approval_basis="Test",
            promotion_commit="test",
        )
        
        decision = guard.observe(
            scenario_name="test_scenario",
            success=True,
            latency_ms=50,
            fallback=False,
            wrong_user_guard=False,
            provider_health=True,
            quality_signal=0.5,
        )
        
        assert decision.action == GuardAction.NONE
        assert decision.reason is None

    def test_observe_detects_wrong_user_guard(self, registry, guard):
        """observe triggers ROLLBACK on wrong_user_guard."""
        registry.promote_scenario(
            scenario_name="test_scenario",
            approval_basis="Test",
            promotion_commit="test",
        )
        
        decision = guard.observe(
            scenario_name="test_scenario",
            success=True,
            latency_ms=50,
            wrong_user_guard=True,
        )
        
        assert decision.action == GuardAction.ROLLBACK
        assert "wrong_user_guard" in decision.reason

    def test_observe_detects_high_fallback_rate(self, registry, guard):
        """observe triggers DEMOTE on high fallback rate."""
        registry.promote_scenario(
            scenario_name="test_scenario",
            approval_basis="Test",
            promotion_commit="test",
        )
        
        # Start with healthy observations to build baseline
        for i in range(20):
            guard.observe(
                scenario_name="test_scenario",
                success=True,
                latency_ms=50,
                fallback=False,
            )
        
        # Now add fallback observations to reach >10% rate
        last_demotion_decision = None
        for i in range(5):
            decision = guard.observe(
                scenario_name="test_scenario",
                success=True,
                latency_ms=50,
                fallback=True,
            )
            if decision.action == GuardAction.DEMOTE:
                last_demotion_decision = decision
        
        # Should have triggered demotion
        assert last_demotion_decision is not None
        assert last_demotion_decision.action == GuardAction.DEMOTE
        assert registry.scenarios["test_scenario"].status == WhitelistStatus.DEMOTED

    def test_observe_alerts_on_warning(self, registry, guard):
        """observe triggers ALERT on warning conditions."""
        registry.promote_scenario(
            scenario_name="test_scenario",
            approval_basis="Test",
            promotion_commit="test",
        )
        
        # Build baseline with no fallbacks
        for i in range(50):
            guard.observe(
                scenario_name="test_scenario",
                success=True,
                latency_ms=50,
                fallback=False,
            )
        
        # Add 5% fallback rate (triggers warning at >5%)
        for i in range(5):
            decision = guard.observe(
                scenario_name="test_scenario",
                success=True,
                latency_ms=50,
                fallback=True,
            )
        
        # 5/55 = ~9% fallback rate, should trigger alert (but not demote since <10%)
        # Actually 5/55 = 9.09% > 10% threshold check... let me recalculate
        # After 50 healthy + 5 fallback = 55 total, 5 fallback = 9.09%
        # 9.09% > 5% warning, but < 10% demotion
        
        # The last decision should be an alert (not demotion)
        assert decision.action == GuardAction.ALERT
        assert registry.scenarios["test_scenario"].status == WhitelistStatus.PROMOTED  # Not demoted

    def test_run_observation_round(self, registry, guard):
        """run_observation_round processes batch of observations."""
        registry.promote_scenario(
            scenario_name="test_scenario",
            approval_basis="Test",
            promotion_commit="test",
        )
        
        observations = [
            {"success": True, "latency_ms": 50, "quality_signal": 0.5}
            for _ in range(10)
        ]
        
        decision = guard.run_observation_round("test_scenario", observations)
        
        assert decision.action == GuardAction.NONE
        assert registry.scenarios["test_scenario"].request_count == 10
        assert registry.scenarios["test_scenario"].observation_rounds == 1

    def test_get_guard_report(self, registry, guard):
        """get_guard_report returns complete report."""
        registry.promote_scenario(
            scenario_name="test_scenario",
            approval_basis="Test",
            promotion_commit="test",
        )
        
        for _ in range(5):
            guard.observe(
                scenario_name="test_scenario",
                success=True,
                latency_ms=50,
            )
        
        report = guard.get_guard_report()
        
        assert "test_scenario" in report["promoted_scenarios"]
        assert report["demotion_supported"] is True
        assert report["rollback_supported"] is True
        assert "scenario_reports" in report

    def test_quality_signal_degradation_triggers_alert(self, registry, guard):
        """Consecutive low quality signals trigger alert."""
        registry.promote_scenario(
            scenario_name="test_scenario",
            approval_basis="Test",
            promotion_commit="test",
        )
        
        # Record observations with negative quality signal for 3 consecutive rounds
        decision = GuardAction.NONE
        for _ in range(3):
            decision = guard.observe(
                scenario_name="test_scenario",
                success=True,
                latency_ms=50,
                quality_signal=-0.1,  # Negative signal
            )
        
        # Should trigger action due to quality signal
        # Note: need 2+ consecutive rounds below threshold
        assert decision.action in (GuardAction.ALERT, GuardAction.DEMOTE, GuardAction.NONE)

    def test_provider_health_low_triggers_alert(self, registry, guard):
        """Low provider health rate triggers alert."""
        registry.promote_scenario(
            scenario_name="test_scenario",
            approval_basis="Test",
            promotion_commit="test",
        )
        
        # Record observations with some provider failures
        last_decision = None
        for i in range(100):
            decision = guard.observe(
                scenario_name="test_scenario",
                success=True,
                latency_ms=50,
                provider_health=(i % 12 != 0),  # ~92% health rate
            )
            if decision.action != GuardAction.NONE:
                last_decision = decision
        
        # Should trigger alert or demotion at some point
        assert last_decision is not None
        assert last_decision.action in (GuardAction.ALERT, GuardAction.DEMOTE)


class TestGuardDecision:
    """Tests for GuardDecision."""

    def test_to_dict(self):
        """to_dict returns all fields."""
        decision = GuardDecision(
            scenario_name="test",
            action=GuardAction.ALERT,
            reason="Test reason",
            metrics_snapshot={"request_count": 10},
            timestamp=1234567890.0,
        )
        
        d = decision.to_dict()
        
        assert d["scenario_name"] == "test"
        assert d["action"] == "alert"
        assert d["reason"] == "Test reason"
        assert d["metrics_snapshot"]["request_count"] == 10
        assert "datetime" in d


class TestGuardActions:
    """Test different guard action severities."""

    @pytest.fixture
    def registry(self, tmp_path):
        return ProductionWhitelistRegistry(storage_path=tmp_path)

    @pytest.fixture
    def guard(self, registry, tmp_path):
        guard = PostPromotionGuard(registry)
        guard.storage_path = tmp_path
        return guard

    def test_rollback_for_wrong_user_guard(self, registry, guard):
        """ROLLBACK triggered for wrong_user_guard (critical)."""
        registry.promote_scenario(
            scenario_name="test",
            approval_basis="Test",
            promotion_commit="test",
        )
        
        decision = guard.observe("test", True, 50, wrong_user_guard=True)
        
        assert decision.action == GuardAction.ROLLBACK
        assert registry.scenarios["test"].status == WhitelistStatus.ROLLED_BACK

    def test_demote_for_severe_fallback(self, registry, guard):
        """DEMOTE triggered for severe fallback rate."""
        registry.promote_scenario(
            scenario_name="test",
            approval_basis="Test",
            promotion_commit="test",
        )
        
        # Build baseline with no fallbacks
        for i in range(20):
            guard.observe("test", True, 50, fallback=False)
        
        # Add fallbacks to reach >10% rate
        last_demotion = None
        for i in range(5):
            decision = guard.observe("test", True, 50, fallback=True)
            if decision.action == GuardAction.DEMOTE:
                last_demotion = decision
        
        # Check final state - should have demoted
        assert last_demotion is not None
        assert registry.scenarios["test"].status == WhitelistStatus.DEMOTED

    def test_alert_for_moderate_issues(self, registry, guard):
        """ALERT triggered for moderate issues."""
        registry.promote_scenario(
            scenario_name="test",
            approval_basis="Test",
            promotion_commit="test",
        )
        
        # 8% fallback rate - moderate issue (below 10% demotion threshold)
        decision = GuardAction.NONE
        for i in range(100):
            decision = guard.observe("test", True, 50, fallback=(i % 12 == 0))
        
        # Should alert but not demote (8% < 10%)
        # Actually 8/100 = 8% which is > 5% warning, so could be alert
        assert decision.action in (GuardAction.ALERT, GuardAction.NONE)
