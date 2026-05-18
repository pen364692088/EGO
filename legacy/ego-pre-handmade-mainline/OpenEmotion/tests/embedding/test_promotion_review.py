"""
Tests for Promotion Review (v6g).

Validates:
- Review verdicts
- Provenance validation
- Promotion blocking
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from emotiond.memory.embedding.promotion_review import (
    PromotionReviewer,
    PromotionReview,
    ReviewVerdict,
    ReviewBlocker,
)
from emotiond.memory.embedding.quality_signal_provenance import (
    QualitySignalProvenanceBuilder,
    SignalSource,
)
from emotiond.memory.embedding.pilot_registry import (
    PilotRegistry,
    PilotConfig,
)


class TestReviewVerdict:
    """Test review verdict enum."""
    
    def test_promote_exists(self):
        assert ReviewVerdict.PROMOTE.value == "promote"
    
    def test_keep_pilot_exists(self):
        assert ReviewVerdict.KEEP_PILOT.value == "keep_pilot"
    
    def test_rollback_exists(self):
        assert ReviewVerdict.ROLLBACK.value == "rollback"


class TestProvenanceValidation:
    """Test provenance validation in review."""
    
    def test_no_provenance_blocks_promotion(self):
        """Missing provenance should block promotion."""
        registry = PilotRegistry()
        registry.activate_pilot("complex_semantic_reasoning")
        
        # Add metrics
        for _ in range(50):
            registry.record_pilot_observation(
                scenario_name="complex_semantic_reasoning",
                success=True,
                latency_ms=50.0,
            )
        registry.increment_pilot_round("complex_semantic_reasoning")
        registry.increment_pilot_round("complex_semantic_reasoning")
        
        reviewer = PromotionReviewer(registry)
        review = reviewer.review_pilot_promotion(
            "complex_semantic_reasoning",
            quality_signal_provenance=None,  # Missing!
        )
        
        assert review.verdict == ReviewVerdict.KEEP_PILOT
        assert any(b.category == "provenance_missing" for b in review.blockers)
    
    def test_not_interpretable_blocks_promotion(self):
        """Non-interpretable provenance should block promotion."""
        registry = PilotRegistry()
        registry.activate_pilot("complex_semantic_reasoning")
        
        for _ in range(50):
            registry.record_pilot_observation(
                scenario_name="complex_semantic_reasoning",
                success=True,
                latency_ms=50.0,
            )
        registry.increment_pilot_round("complex_semantic_reasoning")
        registry.increment_pilot_round("complex_semantic_reasoning")
        
        provenance = QualitySignalProvenanceBuilder().with_placeholder(
            "No computation"
        ).build()
        
        reviewer = PromotionReviewer(registry)
        review = reviewer.review_pilot_promotion(
            "complex_semantic_reasoning",
            quality_signal_provenance=provenance,
        )
        
        assert review.verdict == ReviewVerdict.KEEP_PILOT
        assert any(b.category == "not_interpretable" for b in review.blockers)
    
    def test_zero_samples_blocks_promotion(self):
        """Zero sample count should block promotion."""
        registry = PilotRegistry()
        registry.activate_pilot("complex_semantic_reasoning")
        
        for _ in range(50):
            registry.record_pilot_observation(
                scenario_name="complex_semantic_reasoning",
                success=True,
                latency_ms=50.0,
            )
        registry.increment_pilot_round("complex_semantic_reasoning")
        registry.increment_pilot_round("complex_semantic_reasoning")
        
        # Build provenance with sample_count=0 (invalid)
        provenance = QualitySignalProvenanceBuilder().build()
        provenance.sample_count_used = 0  # Force invalid state
        
        reviewer = PromotionReviewer(registry)
        review = reviewer.review_pilot_promotion(
            "complex_semantic_reasoning",
            quality_signal_provenance=provenance,
        )
        
        assert review.verdict == ReviewVerdict.KEEP_PILOT
    
    def test_valid_provenance_allows_promotion(self):
        """Valid provenance should allow promotion."""
        registry = PilotRegistry()
        registry.activate_pilot("complex_semantic_reasoning")
        
        # Add metrics
        for _ in range(50):
            registry.record_pilot_observation(
                scenario_name="complex_semantic_reasoning",
                success=True,
                latency_ms=50.0,
                quality_signal=0.4,
            )
        registry.increment_pilot_round("complex_semantic_reasoning")
        registry.increment_pilot_round("complex_semantic_reasoning")
        
        # Valid provenance
        provenance = QualitySignalProvenanceBuilder().with_shadow_compare(
            signal_value=0.4,
            sample_count=50,
        ).build()
        
        reviewer = PromotionReviewer(registry)
        review = reviewer.review_pilot_promotion(
            "complex_semantic_reasoning",
            quality_signal_provenance=provenance,
        )
        
        assert review.verdict == ReviewVerdict.PROMOTE


class TestRollbackConditions:
    """Test rollback conditions."""
    
    def test_high_fallback_triggers_rollback(self):
        """High fallback should trigger rollback."""
        registry = PilotRegistry()
        registry.activate_pilot("complex_semantic_reasoning")
        
        for _ in range(50):
            registry.record_pilot_observation(
                scenario_name="complex_semantic_reasoning",
                success=True,
                latency_ms=50.0,
                fallback=True,  # All fallbacks
            )
        
        provenance = QualitySignalProvenanceBuilder().with_shadow_compare(
            signal_value=0.4,
            sample_count=50,
        ).build()
        
        reviewer = PromotionReviewer(registry)
        review = reviewer.review_pilot_promotion(
            "complex_semantic_reasoning",
            quality_signal_provenance=provenance,
        )
        
        assert review.verdict == ReviewVerdict.ROLLBACK


class TestV6gFix:
    """Test v6g fix for v6f issue."""
    
    def test_explanation_mismatch_detected(self):
        """Explanation mismatch should be detected."""
        provenance = QualitySignalProvenanceBuilder().with_shadow_compare(
            signal_value=0.4,
            sample_count=40,
        ).build()
        
        # Now force a mismatch
        provenance.explanation = "Computed from 0 samples"  # Contradiction!
        
        registry = PilotRegistry()
        registry.activate_pilot("complex_semantic_reasoning")
        
        for _ in range(50):
            registry.record_pilot_observation(
                scenario_name="complex_semantic_reasoning",
                success=True,
                latency_ms=50.0,
            )
        registry.increment_pilot_round("complex_semantic_reasoning")
        registry.increment_pilot_round("complex_semantic_reasoning")
        
        reviewer = PromotionReviewer(registry)
        review = reviewer.review_pilot_promotion(
            "complex_semantic_reasoning",
            quality_signal_provenance=provenance,
        )
        
        # v6g should detect the mismatch and block
        assert review.verdict == ReviewVerdict.KEEP_PILOT
        assert any("explanation_mismatch" in b.category or "consistency" in b.category for b in review.blockers)


class TestReviewExplanation:
    """Test review explanation."""
    
    def test_explain_review(self):
        """Should generate explanation."""
        registry = PilotRegistry()
        registry.activate_pilot("complex_semantic_reasoning")
        
        for _ in range(50):
            registry.record_pilot_observation(
                scenario_name="complex_semantic_reasoning",
                success=True,
                latency_ms=50.0,
            )
        registry.increment_pilot_round("complex_semantic_reasoning")
        registry.increment_pilot_round("complex_semantic_reasoning")
        
        provenance = QualitySignalProvenanceBuilder().with_shadow_compare(
            signal_value=0.4,
            sample_count=50,
        ).build()
        
        reviewer = PromotionReviewer(registry)
        review = reviewer.review_pilot_promotion(
            "complex_semantic_reasoning",
            quality_signal_provenance=provenance,
        )
        
        explanation = reviewer.explain_review(review)
        
        assert "PROMOTE" in explanation
        assert "50" in explanation  # sample count
        assert "shadow_compare" in explanation
