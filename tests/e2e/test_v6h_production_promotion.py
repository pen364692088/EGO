"""
E2E Tests for v6h Production Whitelist Promotion.

v6h: Production Whitelist Promotion + Post-Promotion Observation
"""

import json
import pytest
from pathlib import Path

from emotiond.memory.embedding.production_whitelist import (
    ProductionWhitelistRegistry,
    WhitelistStatus,
)
from emotiond.memory.embedding.post_promotion_guard import (
    PostPromotionGuard,
    GuardAction,
)


class TestV6hProductionPromotion:
    """E2E tests for v6h production promotion flow."""

    @pytest.fixture
    def registry(self, tmp_path):
        return ProductionWhitelistRegistry(storage_path=tmp_path)

    @pytest.fixture
    def guard(self, registry, tmp_path):
        guard = PostPromotionGuard(registry)
        guard.storage_path = tmp_path
        return guard

    def test_complete_promotion_flow(self, registry, guard):
        """
        Complete flow: pilot -> promote -> observe -> stable.
        """
        # 1. Initial state: 3 scenarios in production whitelist
        initial_whitelist = registry.get_production_whitelist()
        assert len(initial_whitelist) == 3
        assert "complex_semantic_reasoning" not in initial_whitelist

        # 2. Promote complex_semantic_reasoning
        receipt = registry.promote_scenario(
            scenario_name="complex_semantic_reasoning",
            approval_basis="Pilot evaluation: 40 requests, 0% fallback, 78ms p95 latency, verdict=promote",
            promotion_commit="v6h-test",
            observation_window_days=14,
            observation_window_rounds=10,
        )
        
        assert receipt.promoted_scenario == "complex_semantic_reasoning"
        assert receipt.new_state == "promoted"
        
        # 3. Verify promotion
        assert registry.is_in_production_whitelist("complex_semantic_reasoning")
        updated_whitelist = registry.get_production_whitelist()
        assert len(updated_whitelist) == 4
        assert "complex_semantic_reasoning" in updated_whitelist

        # 4. Run observation rounds
        for round_num in range(1, 6):
            observations = [
                {"success": True, "latency_ms": 60 + i, "quality_signal": 0.4 + i * 0.01}
                for i in range(20)
            ]
            decision = guard.run_observation_round("complex_semantic_reasoning", observations)
            
            assert decision.action == GuardAction.NONE

        # 5. Verify stable state
        report = registry.get_observation_report("complex_semantic_reasoning")
        assert report["request_count"] == 100
        assert report["fallback_rate"] == 0.0
        assert report["observation_rounds"] == 5
        assert report["rollback_needed"] is None

    def test_promotion_with_rollback(self, registry, guard):
        """
        Flow: pilot -> promote -> observe -> detect issue -> rollback.
        """
        # 1. Promote scenario
        registry.promote_scenario(
            scenario_name="complex_semantic_reasoning",
            approval_basis="Test",
            promotion_commit="test",
        )
        
        assert registry.is_in_production_whitelist("complex_semantic_reasoning")

        # 2. Run some healthy observations
        for _ in range(10):
            guard.observe("complex_semantic_reasoning", True, 60, quality_signal=0.4)

        # 3. Trigger critical issue: wrong_user_guard
        decision = guard.observe(
            "complex_semantic_reasoning",
            success=True,
            latency_ms=60,
            wrong_user_guard=True,
        )
        
        # 4. Verify rollback triggered
        assert decision.action == GuardAction.ROLLBACK
        assert "wrong_user_guard" in decision.reason
        
        # 5. Verify scenario removed from whitelist
        assert not registry.is_in_production_whitelist("complex_semantic_reasoning")
        assert registry.scenarios["complex_semantic_reasoning"].status == WhitelistStatus.ROLLED_BACK

    def test_promotion_with_demotion(self, registry, guard):
        """
        Flow: pilot -> promote -> observe -> degrade -> demote.
        """
        # 1. Promote scenario
        registry.promote_scenario(
            scenario_name="complex_semantic_reasoning",
            approval_basis="Test",
            promotion_commit="test",
        )

        # 2. Build baseline with healthy observations
        for i in range(40):
            guard.observe("complex_semantic_reasoning", True, 60, fallback=False)

        # 3. Add fallbacks to reach >10% rate
        last_demotion = None
        for i in range(10):
            decision = guard.observe("complex_semantic_reasoning", True, 60, fallback=True)
            if decision.action == GuardAction.DEMOTE:
                last_demotion = decision

        # 4. Verify demotion triggered
        assert last_demotion is not None
        assert registry.scenarios["complex_semantic_reasoning"].status == WhitelistStatus.DEMOTED

    def test_promotion_receipt_persistence(self, registry, guard, tmp_path):
        """Promotion receipt is saved and can be loaded."""
        # 1. Promote with receipt
        receipt = registry.promote_scenario(
            scenario_name="complex_semantic_reasoning",
            approval_basis="Test persistence",
            promotion_commit="persist-test",
            observation_window_days=14,
            observation_window_rounds=10,
        )
        
        # 2. Load new registry from same path
        new_registry = ProductionWhitelistRegistry(storage_path=tmp_path)
        
        # 3. Verify receipt loaded
        assert len(new_registry.promotion_history) == 1
        assert new_registry.promotion_history[0].promoted_scenario == "complex_semantic_reasoning"
        assert new_registry.promotion_history[0].promotion_commit == "persist-test"

    def test_promotion_receipt_file(self, registry, tmp_path):
        """Promotion receipt is saved to JSON file."""
        receipt = registry.promote_scenario(
            scenario_name="complex_semantic_reasoning",
            approval_basis="Test file",
            promotion_commit="file-test",
        )
        
        # Check receipt file exists
        receipt_file = tmp_path / "promotion_receipt.json"
        assert receipt_file.exists()
        
        # Load and verify
        saved_receipt = json.loads(receipt_file.read_text())
        assert saved_receipt["promoted_scenario"] == "complex_semantic_reasoning"
        assert saved_receipt["promotion_commit"] == "file-test"

    def test_existing_whitelist_preserved(self, registry):
        """Promoting new scenario doesn't affect existing whitelist."""
        # Get initial whitelist
        initial = registry.get_production_whitelist()
        assert "memory_search_hard_query" in initial
        
        # Promote new scenario
        registry.promote_scenario(
            scenario_name="complex_semantic_reasoning",
            approval_basis="Test",
            promotion_commit="test",
        )
        
        # Verify existing scenarios still present
        updated = registry.get_production_whitelist()
        assert "memory_search_hard_query" in updated
        assert "narrative_recall_ambiguous_query" in updated
        assert "long_context_semantic_lookup" in updated
        assert "complex_semantic_reasoning" in updated

    def test_post_promotion_report_generation(self, registry, guard):
        """Post-promotion report is generated correctly."""
        registry.promote_scenario(
            scenario_name="complex_semantic_reasoning",
            approval_basis="Test",
            promotion_commit="test",
        )
        
        # Run observations
        for i in range(50):
            guard.observe(
                "complex_semantic_reasoning",
                success=True,
                latency_ms=60 + i,
                quality_signal=0.3 + i * 0.005,
            )
        
        # Get report
        report = guard.get_guard_report()
        
        assert "complex_semantic_reasoning" in report["scenario_reports"]
        scenario_report = report["scenario_reports"]["complex_semantic_reasoning"]
        assert scenario_report["request_count"] == 50
        assert scenario_report["fallback_rate"] == 0.0
        assert "promotion_receipt" in scenario_report

    def test_observation_round_tracking(self, registry, guard):
        """Observation rounds are tracked correctly."""
        registry.promote_scenario(
            scenario_name="complex_semantic_reasoning",
            approval_basis="Test",
            promotion_commit="test",
        )
        
        # Run multiple rounds
        for _ in range(3):
            observations = [{"success": True, "latency_ms": 60} for _ in range(10)]
            guard.run_observation_round("complex_semantic_reasoning", observations)
        
        # Check rounds tracked
        scenario = registry.scenarios["complex_semantic_reasoning"]
        assert scenario.observation_rounds == 3


class TestV6hGuardBehavior:
    """Test guard behavior for v6h."""

    @pytest.fixture
    def registry(self, tmp_path):
        return ProductionWhitelistRegistry(storage_path=tmp_path)

    @pytest.fixture
    def guard(self, registry, tmp_path):
        guard = PostPromotionGuard(registry)
        guard.storage_path = tmp_path
        return guard

    def test_demotion_supported(self, registry, guard):
        """Guard supports demotion."""
        report = guard.get_guard_report()
        assert report["demotion_supported"] is True

    def test_rollback_supported(self, registry, guard):
        """Guard supports rollback."""
        report = guard.get_guard_report()
        assert report["rollback_supported"] is True

    def test_multiple_promoted_scenarios(self, registry, guard):
        """Guard handles multiple promoted scenarios."""
        # Promote two scenarios
        registry.promote_scenario("scenario_a", "Test", "test")
        registry.promote_scenario("scenario_b", "Test", "test")
        
        # Record observations for both
        guard.observe("scenario_a", True, 50)
        guard.observe("scenario_b", True, 50)
        
        # Get report
        report = guard.get_guard_report()
        
        assert "scenario_a" in report["promoted_scenarios"]
        assert "scenario_b" in report["promoted_scenarios"]
        # 3 initial + 2 promoted = 5 scenarios in whitelist
        assert len(report["promoted_scenarios"]) == 5
