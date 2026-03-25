"""
Tests for Post-Promotion Stability Evaluator.

v6i: Post-Promotion Observation + Stability Verdict
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
    ObservationRoundReceipt,
    StabilityEvaluation,
)


class TestPostPromotionStabilityEvaluator:
    """Tests for PostPromotionStabilityEvaluator."""

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

    def test_record_observation_round(self, registry, guard, evaluator):
        """record_observation_round creates receipt."""
        registry.promote_scenario("test", "Test", "test")

        observations = [{"success": True, "latency_ms": 50} for _ in range(20)]
        receipt = evaluator.record_observation_round("test", observations)

        assert receipt.round_id == 1
        assert receipt.scenario_name == "test"
        assert receipt.sample_count == 20

    def test_multiple_observation_rounds(self, registry, guard, evaluator):
        """Multiple rounds are tracked."""
        registry.promote_scenario("test", "Test", "test")

        for i in range(3):
            observations = [{"success": True, "latency_ms": 50} for _ in range(20)]
            receipt = evaluator.record_observation_round("test", observations)
            assert receipt.round_id == i + 1

        assert len(evaluator.round_receipts) == 3

    def test_evaluate_stability_insufficient_data(self, registry, guard, evaluator):
        """evaluate_stability returns KEEP_UNDER_OBSERVATION when data insufficient."""
        registry.promote_scenario("test", "Test", "test")

        # No observations yet
        evaluation = evaluator.evaluate_stability("test")

        assert evaluation.verdict == StabilityVerdict.KEEP_UNDER_OBSERVATION
        assert any("request_count" in b for b in evaluation.blockers)

    def test_evaluate_stability_stable(self, registry, guard, evaluator):
        """evaluate_stability returns STABLE_KEEP_PROMOTED when criteria met."""
        registry.promote_scenario("test", "Test", "test")

        # Run 3 observation rounds with 20 samples each = 60 total
        for _ in range(3):
            observations = [
                {"success": True, "latency_ms": 60, "quality_signal": 0.4}
                for _ in range(20)
            ]
            evaluator.record_observation_round("test", observations)

        evaluation = evaluator.evaluate_stability("test")

        assert evaluation.verdict == StabilityVerdict.STABLE_KEEP_PROMOTED
        assert len(evaluation.blockers) == 0

    def test_evaluate_stability_wrong_user_guard(self, registry, guard, evaluator):
        """evaluate_stability returns ROLLBACK for wrong_user_guard."""
        registry.promote_scenario("test", "Test", "test")

        # Build up some data (sufficient for stable check)
        for _ in range(3):
            observations = [{"success": True, "latency_ms": 50} for _ in range(20)]
            evaluator.record_observation_round("test", observations)

        # Trigger wrong_user_guard
        guard.observe("test", True, 50, wrong_user_guard=True)

        evaluation = evaluator.evaluate_stability("test")

        assert evaluation.verdict == StabilityVerdict.ROLLBACK_TO_TFIDF_ONLY
        # Check that blockers contain information about the issue
        assert len(evaluation.blockers) > 0

    def test_evaluate_stability_high_fallback(self, registry, guard, evaluator):
        """evaluate_stability returns KEEP_UNDER_OBSERVATION for moderate fallback rate."""
        registry.promote_scenario("test", "Test", "test")

        # Build baseline with enough data for stable check
        for _ in range(3):
            observations = [{"success": True, "latency_ms": 50} for _ in range(20)]
            evaluator.record_observation_round("test", observations)

        # Add moderate fallback rate (5-10%, triggers warning but not demotion)
        for _ in range(50):
            guard.observe("test", True, 50, fallback=False)
        for _ in range(10):
            guard.observe("test", True, 50, fallback=True)

        evaluation = evaluator.evaluate_stability("test")

        # 10/120 = 8.3% - between 5% warning and 10% demotion
        # Should be KEEP_UNDER_OBSERVATION with fallback_rate blocker
        assert evaluation.verdict == StabilityVerdict.KEEP_UNDER_OBSERVATION
        assert any("fallback_rate" in b for b in evaluation.blockers)

    def test_get_stability_report(self, registry, guard, evaluator):
        """get_stability_report returns complete report."""
        registry.promote_scenario("test", "Test", "test")

        observations = [{"success": True, "latency_ms": 50} for _ in range(20)]
        evaluator.record_observation_round("test", observations)

        report = evaluator.get_stability_report("test")

        assert "scenario_name" in report
        assert "evaluation" in report
        assert "round_receipts" in report
        assert report["total_rounds"] == 1

    def test_round_receipt_persistence(self, registry, guard, evaluator, tmp_path):
        """Round receipts are persisted."""
        registry.promote_scenario("test", "Test", "test")

        observations = [{"success": True, "latency_ms": 50} for _ in range(20)]
        evaluator.record_observation_round("test", observations)

        # Create new evaluator to load persisted receipts
        new_evaluator = PostPromotionStabilityEvaluator(
            registry, guard, storage_path=tmp_path
        )

        assert len(new_evaluator.round_receipts) == 1
        assert new_evaluator.round_receipts[0].scenario_name == "test"


class TestObservationRoundReceipt:
    """Tests for ObservationRoundReceipt."""

    def test_to_dict(self):
        """to_dict returns all fields."""
        receipt = ObservationRoundReceipt(
            round_id=1,
            scenario_name="test",
            sample_count=20,
            fallback_rate=0.05,
            p95_latency_ms=75.0,
            wrong_user_guard_trigger_count=0,
            provider_health_rate=0.99,
            quality_gain_signal=0.4,
            guard_status="none",
            timestamp=1234567890.0,
        )

        d = receipt.to_dict()

        assert d["round_id"] == 1
        assert d["scenario_name"] == "test"
        assert d["sample_count"] == 20
        assert d["fallback_rate"] == 0.05
        assert "datetime" in d


class TestStabilityEvaluation:
    """Tests for StabilityEvaluation."""

    def test_to_dict(self):
        """to_dict returns all fields."""
        evaluation = StabilityEvaluation(
            scenario_name="test",
            verdict=StabilityVerdict.STABLE_KEEP_PROMOTED,
            blockers=[],
            rationale="All criteria met",
            next_allowed_action="Continue monitoring",
            metrics_summary={"request_count": 100},
            observation_rounds=5,
            timestamp=1234567890.0,
        )

        d = evaluation.to_dict()

        assert d["scenario_name"] == "test"
        assert d["verdict"] == "stable_keep_promoted"
        assert d["blockers"] == []
        assert "datetime" in d


class TestStabilityVerdict:
    """Tests for StabilityVerdict enum."""

    def test_all_verdicts_exist(self):
        """All expected verdicts exist."""
        assert StabilityVerdict.STABLE_KEEP_PROMOTED.value == "stable_keep_promoted"
        assert StabilityVerdict.KEEP_UNDER_OBSERVATION.value == "keep_under_observation"
        assert StabilityVerdict.DEMOTE_TO_PILOT.value == "demote_to_pilot"
        assert StabilityVerdict.ROLLBACK_TO_TFIDF_ONLY.value == "rollback_to_tfidf_only"
