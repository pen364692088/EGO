"""
E2E Tests for v6g Promotion Review.

Validates complete review flow with provenance.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from emotiond.memory.embedding.promotion_review import (
    PromotionReviewer,
    ReviewVerdict,
)
from emotiond.memory.embedding.quality_signal_provenance import (
    QualitySignalProvenanceBuilder,
    compute_shadow_compare_provenance,
)
from emotiond.memory.embedding.pilot_registry import PilotRegistry


class TestCompleteReviewFlow:
    """Test complete promotion review flow."""
    
    def test_valid_promotion_flow(self):
        """Valid provenance should allow promotion."""
        registry = PilotRegistry()
        registry.activate_pilot("complex_semantic_reasoning")
        
        # Collect pilot data
        for _ in range(50):
            registry.record_pilot_observation(
                scenario_name="complex_semantic_reasoning",
                success=True,
                latency_ms=50.0,
                quality_signal=0.4,
            )
        registry.increment_pilot_round("complex_semantic_reasoning")
        registry.increment_pilot_round("complex_semantic_reasoning")
        
        # Build provenance
        provenance = QualitySignalProvenanceBuilder().with_shadow_compare(
            signal_value=0.4,
            sample_count=50,
            batch_ref="pilot_rounds_1_2",
        ).build()
        
        # Review
        reviewer = PromotionReviewer(registry)
        review = reviewer.review_pilot_promotion(
            "complex_semantic_reasoning",
            quality_signal_provenance=provenance,
        )
        
        assert review.verdict == ReviewVerdict.PROMOTE
        assert review.quality_signal_provenance.sample_count_used == 50
        assert "50" in review.quality_signal_provenance.explanation
    
    def test_invalid_provenance_flow(self):
        """Invalid provenance should block promotion."""
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
        
        # Invalid provenance (placeholder)
        provenance = QualitySignalProvenanceBuilder().with_placeholder(
            "No computation performed"
        ).build()
        
        reviewer = PromotionReviewer(registry)
        review = reviewer.review_pilot_promotion(
            "complex_semantic_reasoning",
            quality_signal_provenance=provenance,
        )
        
        assert review.verdict == ReviewVerdict.KEEP_PILOT


class TestV6gContradictionFix:
    """Test v6g fix for the v6f contradiction."""
    
    def test_sample_count_explanation_consistency(self):
        """sample_count and explanation must be consistent."""
        # This is what v6f produced (bad):
        # {
        #   "signal_value": 0.4,
        #   "sample_count_used": 40,
        #   "explanation": "Computed from 0 samples"  # WRONG!
        # }
        
        # v6g fix: use builder which enforces consistency
        provenance = QualitySignalProvenanceBuilder().with_shadow_compare(
            signal_value=0.4,
            sample_count=40,
        ).build()
        
        # Now they match
        assert provenance.sample_count_used == 40
        assert "40" in provenance.explanation
        assert provenance.is_valid_for_promotion() is True
    
    def test_review_detects_inconsistency(self):
        """Review should detect inconsistency."""
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
        
        # Build then corrupt
        provenance = QualitySignalProvenanceBuilder().with_shadow_compare(
            signal_value=0.4,
            sample_count=40,
        ).build()
        
        # Corrupt the explanation (simulating v6f bug)
        provenance.explanation = "Computed from 0 samples"
        
        reviewer = PromotionReviewer(registry)
        review = reviewer.review_pilot_promotion(
            "complex_semantic_reasoning",
            quality_signal_provenance=provenance,
        )
        
        # v6g should detect and block
        assert review.verdict == ReviewVerdict.KEEP_PILOT
        assert any("explanation_mismatch" in b.category or "consistency" in b.category for b in review.blockers)


class TestShadowCompareProvenance:
    """Test shadow compare provenance computation."""
    
    def test_compute_with_real_samples(self):
        """Should compute provenance with real samples."""
        # Simulate 40 shadow comparisons
        ollama_results = [["a", "b", "c"] for _ in range(40)]
        tfidf_results = [["x", "y", "z"] for _ in range(40)]
        
        provenance = compute_shadow_compare_provenance(
            ollama_top_k_results=ollama_results,
            tfidf_top_k_results=tfidf_results,
            k=3,
            batch_ref="pilot_complex_semantic_reasoning_rounds_1_2",
        )
        
        assert provenance.source.value == "shadow_compare"
        assert provenance.sample_count_used == 40
        assert "40" in provenance.explanation
        assert provenance.baseline_provider == "tfidf"
        assert provenance.candidate_provider == "ollama"
        assert provenance.is_valid_for_promotion() is True
    
    def test_compute_with_no_samples(self):
        """Should return placeholder with no samples."""
        provenance = compute_shadow_compare_provenance(
            ollama_top_k_results=[],
            tfidf_top_k_results=[],
        )
        
        assert provenance.source.value == "placeholder"
        assert provenance.interpretable is False
        assert provenance.is_valid_for_promotion() is False


class TestPromotionEvidenceChain:
    """Test complete evidence chain for promotion."""
    
    def test_complete_evidence_chain(self):
        """Promotion requires complete evidence chain."""
        registry = PilotRegistry()
        registry.activate_pilot("complex_semantic_reasoning")
        
        # Step 1: Collect pilot data
        for _ in range(50):
            registry.record_pilot_observation(
                scenario_name="complex_semantic_reasoning",
                success=True,
                latency_ms=50.0,
                quality_signal=0.4,
            )
        registry.increment_pilot_round("complex_semantic_reasoning")
        registry.increment_pilot_round("complex_semantic_reasoning")
        
        # Step 2: Compute quality signal with provenance
        provenance = QualitySignalProvenanceBuilder().with_shadow_compare(
            signal_value=0.4,
            sample_count=50,
            batch_ref="pilot_complex_semantic_reasoning_2026_03_16",
        ).build()
        
        # Step 3: Validate provenance
        assert provenance.is_valid_for_promotion() is True
        assert len(provenance.validate_consistency()) == 0
        
        # Step 4: Review promotion
        reviewer = PromotionReviewer(registry)
        review = reviewer.review_pilot_promotion(
            "complex_semantic_reasoning",
            quality_signal_provenance=provenance,
        )
        
        # Step 5: Verify verdict
        assert review.verdict == ReviewVerdict.PROMOTE
        
        # Step 6: Verify evidence chain
        assert review.quality_signal_provenance.signal_value == 0.4
        assert review.quality_signal_provenance.sample_count_used == 50
        assert "50" in review.quality_signal_provenance.explanation
        assert review.quality_signal_provenance.is_valid_for_promotion() is True
