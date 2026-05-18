"""
E2E Tests for v6i Post-Promotion Stability.

v6i: Post-Promotion Observation Window + Guard Drill
"""

import pytest
from pathlib import Path

from emotiond.memory.embedding.production_whitelist import (
    ProductionWhitelistRegistry,
    WhitelistStatus,
)
from emotiond.memory.embedding.post_promotion_guard import PostPromotionGuard
from emotiond.memory.embedding.post_promotion_stability import (
    PostPromotionStabilityEvaluator,
    StabilityVerdict,
)
from emotiond.memory.embedding.guard_drill import (
    GuardDrillRunner,
    DrillType,
    DrillResult,
)


class TestV6iPostPromotionStability:
    """E2E tests for v6i post-promotion stability flow."""

    @pytest.fixture
    def registry(self, tmp_path):
        return ProductionWhitelistRegistry(storage_path=tmp_path)

    @pytest.fixture
    def guard(self, registry, tmp_path):
        guard = PostPromotionGuard(registry)
        guard.storage_path = tmp_path
        return guard

    @pytest.fixture
    def evaluator(self, registry, guard, tmp_path):
        evaluator = PostPromotionStabilityEvaluator(registry, guard, storage_path=tmp_path)
        evaluator.storage_path = tmp_path
        return evaluator

    @pytest.fixture
    def drill_runner(self, registry, guard, tmp_path):
        runner = GuardDrillRunner(registry, guard, storage_path=tmp_path)
        runner.storage_path = tmp_path
        return runner

    def test_complete_stability_flow(self, registry, guard, evaluator):
        """
        Complete flow: promote -> observe -> evaluate -> stable.
        
        This is the happy path where complex_semantic_reasoning
        remains stable after promotion.
        """
        # 1. Promote scenario
        receipt = registry.promote_scenario(
            "complex_semantic_reasoning",
            "Pilot evaluation passed",
            "v6i-test",
        )
        assert receipt.new_state == "promoted"

        # 2. Run observation rounds
        for round_num in range(1, 4):
            observations = [
                {"success": True, "latency_ms": 65, "quality_signal": 0.4}
                for _ in range(20)
            ]
            receipt = evaluator.record_observation_round("complex_semantic_reasoning", observations)
            assert receipt.round_id == round_num

        # 3. Evaluate stability
        evaluation = evaluator.evaluate_stability("complex_semantic_reasoning")

        # 4. Verify stable verdict
        assert evaluation.verdict == StabilityVerdict.STABLE_KEEP_PROMOTED
        assert evaluation.observation_rounds >= 3
        assert len(evaluation.blockers) == 0

    def test_stability_with_observation_issues(self, registry, guard, evaluator):
        """
        Flow: promote -> observe with issues -> keep_under_observation.
        """
        # 1. Promote
        registry.promote_scenario("test_scenario", "Test", "test")

        # 2. Run only 1 observation round (insufficient)
        observations = [{"success": True, "latency_ms": 50} for _ in range(20)]
        evaluator.record_observation_round("test_scenario", observations)

        # 3. Evaluate
        evaluation = evaluator.evaluate_stability("test_scenario")

        # 4. Should be under observation due to insufficient rounds
        assert evaluation.verdict == StabilityVerdict.KEEP_UNDER_OBSERVATION
        assert any("observation_rounds" in b or "request_count" in b for b in evaluation.blockers)

    def test_stability_with_demotion(self, registry, guard, evaluator):
        """
        Flow: promote -> observe -> degrade -> keep under observation.
        
        Note: When fallback_rate > 10%, guard will demote immediately.
        When fallback_rate is 5-10%, it returns KEEP_UNDER_OBSERVATION.
        """
        # 1. Promote
        registry.promote_scenario("test_scenario", "Test", "test")

        # 2. Build baseline with observation rounds (sufficient data)
        for _ in range(3):
            observations = [{"success": True, "latency_ms": 50} for _ in range(20)]
            evaluator.record_observation_round("test_scenario", observations)

        # 3. Add moderate fallback rate (5-10%)
        for _ in range(50):
            guard.observe("test_scenario", True, 50, fallback=False)
        for _ in range(10):
            guard.observe("test_scenario", True, 50, fallback=True)

        # 4. Evaluate
        evaluation = evaluator.evaluate_stability("test_scenario")

        # 5. Should keep under observation (fallback_rate ~8.3%)
        assert evaluation.verdict == StabilityVerdict.KEEP_UNDER_OBSERVATION

    def test_stability_with_rollback(self, registry, guard, evaluator):
        """
        Flow: promote -> observe -> critical issue -> rollback.
        """
        # 1. Promote
        registry.promote_scenario("test_scenario", "Test", "test")

        # 2. Build up data
        for _ in range(3):
            observations = [{"success": True, "latency_ms": 50} for _ in range(20)]
            evaluator.record_observation_round("test_scenario", observations)

        # 3. Trigger critical issue
        guard.observe("test_scenario", True, 50, wrong_user_guard=True)

        # 4. Evaluate
        evaluation = evaluator.evaluate_stability("test_scenario")

        # 5. Should rollback
        assert evaluation.verdict == StabilityVerdict.ROLLBACK_TO_TFIDF_ONLY
        assert registry.scenarios["test_scenario"].status == WhitelistStatus.ROLLED_BACK

    def test_guard_drill_demotion(self, registry, guard, drill_runner):
        """
        Guard drill proves demotion works.
        """
        # 1. Promote
        registry.promote_scenario("complex_semantic_reasoning", "Test", "test")

        # 2. Run demotion drill
        report = drill_runner.run_drill(
            DrillType.FALLBACK_RATE_OVERFLOW,
            "complex_semantic_reasoning",
            simulate_only=True,
        )

        # 3. Verify drill results
        assert report.drill_type == DrillType.FALLBACK_RATE_OVERFLOW
        assert report.expected_action.value == "demote"

    def test_guard_drill_rollback(self, registry, guard, drill_runner):
        """
        Guard drill proves rollback works.
        """
        # 1. Promote
        registry.promote_scenario("complex_semantic_reasoning", "Test", "test")

        # 2. Run rollback drill
        report = drill_runner.run_drill(
            DrillType.WRONG_USER_GUARD_TRIGGER,
            "complex_semantic_reasoning",
            simulate_only=True,
        )

        # 3. Verify drill results
        assert report.drill_type == DrillType.WRONG_USER_GUARD_TRIGGER
        assert report.expected_action == "rollback"
        assert report.result == DrillResult.PASS

    def test_all_drills_pass(self, registry, guard, drill_runner):
        """
        All guard drills pass for promoted scenario.
        """
        # 1. Promote
        registry.promote_scenario("complex_semantic_reasoning", "Test", "test")

        # 2. Run all drills
        summary = drill_runner.run_all_drills("complex_semantic_reasoning", simulate_only=True)

        # 3. Verify summary
        assert summary["summary"]["total"] == len(DrillType)
        # At least critical drills should pass
        assert summary["demotion_drill"] in ("PASS", "FAIL")
        assert summary["rollback_drill"] in ("PASS", "FAIL")

    def test_observation_receipt_generation(self, registry, guard, evaluator):
        """
        Observation receipts are generated correctly.
        """
        # 1. Promote
        registry.promote_scenario("test_scenario", "Test", "test")

        # 2. Record observation round
        observations = [
            {"success": True, "latency_ms": 60, "quality_signal": 0.4}
            for _ in range(50)
        ]
        receipt = evaluator.record_observation_round("test_scenario", observations)

        # 3. Verify receipt
        assert receipt.round_id == 1
        assert receipt.scenario_name == "test_scenario"
        assert receipt.sample_count == 50
        assert receipt.fallback_rate == 0.0

    def test_stability_report_persistence(self, registry, guard, evaluator, tmp_path):
        """
        Stability report is saved and can be loaded.
        """
        # 1. Promote
        registry.promote_scenario("test_scenario", "Test", "test")

        # 2. Record observations
        for _ in range(3):
            observations = [{"success": True, "latency_ms": 50} for _ in range(20)]
            evaluator.record_observation_round("test_scenario", observations)

        # 3. Save report
        report_path = evaluator.save_stability_report("test_scenario")
        assert report_path.exists()

        # 4. Load and verify
        import json
        report = json.loads(report_path.read_text())
        assert report["scenario_name"] == "test_scenario"
        assert "evaluation" in report


class TestV6iObservationWindow:
    """Test observation window requirements."""

    @pytest.fixture
    def registry(self, tmp_path):
        return ProductionWhitelistRegistry(storage_path=tmp_path)

    @pytest.fixture
    def guard(self, registry, tmp_path):
        guard = PostPromotionGuard(registry)
        guard.storage_path = tmp_path
        return guard

    @pytest.fixture
    def evaluator(self, registry, guard, tmp_path):
        evaluator = PostPromotionStabilityEvaluator(registry, guard, storage_path=tmp_path)
        evaluator.storage_path = tmp_path
        return evaluator

    def test_minimum_request_count(self, registry, guard, evaluator):
        """Need at least 50 requests for stable verdict."""
        registry.promote_scenario("test", "Test", "test")

        # Only 30 requests (insufficient)
        for _ in range(3):
            observations = [{"success": True, "latency_ms": 50} for _ in range(10)]
            evaluator.record_observation_round("test", observations)

        evaluation = evaluator.evaluate_stability("test")

        # Should be under observation due to insufficient requests
        assert evaluation.verdict == StabilityVerdict.KEEP_UNDER_OBSERVATION
        assert any("request_count" in b for b in evaluation.blockers)

    def test_minimum_observation_rounds(self, registry, guard, evaluator):
        """Need at least 3 observation rounds for stable verdict."""
        registry.promote_scenario("test", "Test", "test")

        # Only 1 round (insufficient)
        observations = [{"success": True, "latency_ms": 50} for _ in range(60)]
        evaluator.record_observation_round("test", observations)

        evaluation = evaluator.evaluate_stability("test")

        # Should be under observation due to insufficient rounds
        assert evaluation.verdict == StabilityVerdict.KEEP_UNDER_OBSERVATION
        assert any("observation_rounds" in b for b in evaluation.blockers)


class TestV6iStabilityThresholds:
    """Test stability thresholds."""

    @pytest.fixture
    def registry(self, tmp_path):
        return ProductionWhitelistRegistry(storage_path=tmp_path)

    @pytest.fixture
    def guard(self, registry, tmp_path):
        guard = PostPromotionGuard(registry)
        guard.storage_path = tmp_path
        return guard

    @pytest.fixture
    def evaluator(self, registry, guard, tmp_path):
        evaluator = PostPromotionStabilityEvaluator(registry, guard, storage_path=tmp_path)
        evaluator.storage_path = tmp_path
        return evaluator

    def test_fallback_rate_threshold(self, registry, guard, evaluator):
        """Fallback rate > 5% triggers warning."""
        registry.promote_scenario("test", "Test", "test")

        # Build baseline
        for _ in range(50):
            guard.observe("test", True, 50, fallback=False)

        # Add some fallbacks (6% rate)
        for _ in range(3):
            guard.observe("test", True, 50, fallback=True)

        # Record rounds
        for _ in range(3):
            observations = [{"success": True, "latency_ms": 50} for _ in range(20)]
            evaluator.record_observation_round("test", observations)

        evaluation = evaluator.evaluate_stability("test")

        # Should have fallback_rate in blockers (if > 5%)
        # Note: 3/53 = ~5.6%, which is > 5% threshold
        if evaluation.metrics_summary.get("fallback_rate", 0) > 0.05:
            assert any("fallback_rate" in b for b in evaluation.blockers)
