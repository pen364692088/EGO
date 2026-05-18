"""
Tests for Production Whitelist Registry.

v6h: Production Whitelist Promotion
"""

import pytest
from pathlib import Path

from emotiond.memory.embedding.production_whitelist import (
    ProductionWhitelistRegistry,
    WhitelistStatus,
    PromotionReceipt,
)


class TestProductionWhitelistRegistry:
    """Tests for ProductionWhitelistRegistry."""

    def test_registry_initialization(self, tmp_path):
        """Registry initializes with default production whitelist."""
        registry = ProductionWhitelistRegistry(storage_path=tmp_path)
        
        assert "memory_search_hard_query" in registry.scenarios
        assert registry.is_in_production_whitelist("memory_search_hard_query")
        assert registry.is_in_production_whitelist("narrative_recall_ambiguous_query")
        assert registry.is_in_production_whitelist("long_context_semantic_lookup")

    def test_get_production_whitelist(self, tmp_path):
        """get_production_whitelist returns promoted scenarios."""
        registry = ProductionWhitelistRegistry(storage_path=tmp_path)
        
        whitelist = registry.get_production_whitelist()
        assert len(whitelist) == 3
        assert "memory_search_hard_query" in whitelist

    def test_promote_scenario(self, tmp_path):
        """promote_scenario creates receipt and updates status."""
        registry = ProductionWhitelistRegistry(storage_path=tmp_path)
        
        receipt = registry.promote_scenario(
            scenario_name="complex_semantic_reasoning",
            approval_basis="Pilot evaluation passed",
            promotion_commit="abc123",
            observation_window_days=14,
            observation_window_rounds=10,
        )
        
        assert receipt.promoted_scenario == "complex_semantic_reasoning"
        assert receipt.previous_state in ("pilot_candidate", "pilot_active")
        assert receipt.new_state == "promoted"
        assert receipt.observation_window_days == 14
        assert registry.is_in_production_whitelist("complex_semantic_reasoning")

    def test_promotion_receipt_generated(self, tmp_path):
        """Promotion generates receipt with required fields."""
        registry = ProductionWhitelistRegistry(storage_path=tmp_path)
        
        receipt = registry.promote_scenario(
            scenario_name="test_scenario",
            approval_basis="Test approval",
            promotion_commit="test123",
        )
        
        receipt_dict = receipt.to_dict()
        assert "promoted_scenario" in receipt_dict
        assert "previous_state" in receipt_dict
        assert "new_state" in receipt_dict
        assert "approval_basis" in receipt_dict
        assert "promotion_timestamp" in receipt_dict
        assert "rollback_thresholds" in receipt_dict

    def test_demote_scenario(self, tmp_path):
        """demote_scenario changes status to demoted."""
        registry = ProductionWhitelistRegistry(storage_path=tmp_path)
        
        registry.promote_scenario(
            scenario_name="test_scenario",
            approval_basis="Test",
            promotion_commit="test",
        )
        
        result = registry.demote_scenario("test_scenario", "High fallback rate")
        assert result is True
        assert registry.scenarios["test_scenario"].status == WhitelistStatus.DEMOTED
        assert not registry.is_in_production_whitelist("test_scenario")

    def test_rollback_scenario(self, tmp_path):
        """rollback_scenario changes status to rolled_back."""
        registry = ProductionWhitelistRegistry(storage_path=tmp_path)
        
        registry.promote_scenario(
            scenario_name="test_scenario",
            approval_basis="Test",
            promotion_commit="test",
        )
        
        result = registry.rollback_scenario("test_scenario", "Critical issue")
        assert result is True
        assert registry.scenarios["test_scenario"].status == WhitelistStatus.ROLLED_BACK

    def test_record_observation(self, tmp_path):
        """record_observation updates metrics."""
        registry = ProductionWhitelistRegistry(storage_path=tmp_path)
        
        registry.promote_scenario(
            scenario_name="test_scenario",
            approval_basis="Test",
            promotion_commit="test",
        )
        
        registry.record_observation(
            scenario_name="test_scenario",
            success=True,
            latency_ms=50,
            fallback=False,
            wrong_user_guard=False,
            provider_health=True,
            quality_signal=0.5,
        )
        
        scenario = registry.scenarios["test_scenario"]
        assert scenario.request_count == 1
        assert scenario.success_count == 1
        assert scenario.fallback_count == 0
        assert len(scenario.latencies) == 1
        assert len(scenario.quality_signal_samples) == 1

    def test_check_rollback_needed_no_issue(self, tmp_path):
        """check_rollback_needed returns None when healthy."""
        registry = ProductionWhitelistRegistry(storage_path=tmp_path)
        
        registry.promote_scenario(
            scenario_name="test_scenario",
            approval_basis="Test",
            promotion_commit="test",
        )
        
        for _ in range(10):
            registry.record_observation(
                scenario_name="test_scenario",
                success=True,
                latency_ms=50,
                fallback=False,
                wrong_user_guard=False,
                provider_health=True,
                quality_signal=0.5,
            )
        
        reason = registry.check_rollback_needed("test_scenario")
        assert reason is None

    def test_check_rollback_needed_wrong_user_guard(self, tmp_path):
        """check_rollback_needed detects wrong_user_guard violations."""
        registry = ProductionWhitelistRegistry(storage_path=tmp_path)
        
        registry.promote_scenario(
            scenario_name="test_scenario",
            approval_basis="Test",
            promotion_commit="test",
        )
        
        registry.record_observation(
            scenario_name="test_scenario",
            success=True,
            latency_ms=50,
            wrong_user_guard=True,
        )
        
        reason = registry.check_rollback_needed("test_scenario")
        assert reason is not None
        assert "wrong_user_guard" in reason

    def test_check_rollback_needed_high_fallback_rate(self, tmp_path):
        """check_rollback_needed detects high fallback rate."""
        registry = ProductionWhitelistRegistry(storage_path=tmp_path)
        
        registry.promote_scenario(
            scenario_name="test_scenario",
            approval_basis="Test",
            promotion_commit="test",
        )
        
        # Record 25 observations with 20% fallback rate (5 fallbacks out of 25)
        for i in range(25):
            registry.record_observation(
                scenario_name="test_scenario",
                success=True,
                latency_ms=50,
                fallback=(i % 5 == 0),  # 5 fallbacks = 20%
            )
        
        reason = registry.check_rollback_needed("test_scenario")
        assert reason is not None
        assert "fallback_rate" in reason

    def test_get_observation_report(self, tmp_path):
        """get_observation_report returns complete report."""
        registry = ProductionWhitelistRegistry(storage_path=tmp_path)
        
        registry.promote_scenario(
            scenario_name="test_scenario",
            approval_basis="Test",
            promotion_commit="test",
        )
        
        for _ in range(10):
            registry.record_observation(
                scenario_name="test_scenario",
                success=True,
                latency_ms=50,
                quality_signal=0.4,
            )
        
        report = registry.get_observation_report("test_scenario")
        
        assert report["scenario_name"] == "test_scenario"
        assert report["request_count"] == 10
        assert report["fallback_rate"] == 0.0
        assert report["rollback_needed"] is None

    def test_promotion_history(self, tmp_path):
        """promotion_history tracks all promotions."""
        registry = ProductionWhitelistRegistry(storage_path=tmp_path)
        
        registry.promote_scenario(
            scenario_name="scenario1",
            approval_basis="Test 1",
            promotion_commit="commit1",
        )
        
        registry.promote_scenario(
            scenario_name="scenario2",
            approval_basis="Test 2",
            promotion_commit="commit2",
        )
        
        assert len(registry.promotion_history) == 2
        assert registry.promotion_history[0].promoted_scenario == "scenario1"
        assert registry.promotion_history[1].promoted_scenario == "scenario2"

    def test_promotion_receipt_persistence(self, tmp_path):
        """Promotion receipt is saved and can be loaded."""
        registry = ProductionWhitelistRegistry(storage_path=tmp_path)
        
        registry.promote_scenario(
            scenario_name="test_scenario",
            approval_basis="Test persistence",
            promotion_commit="persist-test",
        )
        
        # Load new registry from same path
        new_registry = ProductionWhitelistRegistry(storage_path=tmp_path)
        
        assert len(new_registry.promotion_history) == 1
        assert new_registry.promotion_history[0].promoted_scenario == "test_scenario"


class TestPromotionReceipt:
    """Tests for PromotionReceipt."""

    def test_to_dict(self):
        """to_dict returns all fields."""
        receipt = PromotionReceipt(
            promoted_scenario="test",
            previous_state="pilot_active",
            new_state="promoted",
            approval_basis="Test approval",
            promotion_commit="abc123",
            promotion_timestamp=1234567890.0,
            observation_window_days=14,
            observation_window_rounds=10,
            rollback_thresholds={"max_fallback_rate": 0.1},
        )
        
        d = receipt.to_dict()
        
        assert d["promoted_scenario"] == "test"
        assert d["previous_state"] == "pilot_active"
        assert d["new_state"] == "promoted"
        assert d["approval_basis"] == "Test approval"
        assert d["promotion_commit"] == "abc123"
        assert "promotion_datetime" in d
        assert d["observation_window_days"] == 14
        assert d["rollback_thresholds"]["max_fallback_rate"] == 0.1
