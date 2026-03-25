"""
Tests for Quality Signal Provenance (v6g).

Validates:
- Provenance consistency
- Promotion validation
- Evidence chain integrity
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from emotiond.memory.embedding.quality_signal_provenance import (
    QualitySignalProvenance,
    QualitySignalProvenanceBuilder,
    SignalSource,
    ComputationMethod,
    compute_shadow_compare_provenance,
)


class TestSignalSource:
    """Test signal source enum."""
    
    def test_shadow_compare_exists(self):
        assert SignalSource.SHADOW_COMPARE.value == "shadow_compare"
    
    def test_placeholder_exists(self):
        assert SignalSource.PLACEHOLDER.value == "placeholder"


class TestQualitySignalProvenanceBuilder:
    """Test provenance builder."""
    
    def test_build_shadow_compare(self):
        """Should build shadow compare provenance."""
        provenance = QualitySignalProvenanceBuilder().with_shadow_compare(
            signal_value=0.4,
            sample_count=40,
            baseline_provider="tfidf",
            candidate_provider="ollama",
        ).build()
        
        assert provenance.signal_value == 0.4
        assert provenance.source == SignalSource.SHADOW_COMPARE
        assert provenance.interpretable is True
        assert provenance.sample_count_used == 40
        assert "40" in provenance.explanation
    
    def test_build_placeholder(self):
        """Should build placeholder provenance."""
        provenance = QualitySignalProvenanceBuilder().with_placeholder(
            reason="No samples"
        ).build()
        
        assert provenance.source == SignalSource.PLACEHOLDER
        assert provenance.interpretable is False
        assert provenance.sample_count_used == 0
    
    def test_build_downstream_proxy(self):
        """Should build downstream proxy provenance."""
        provenance = QualitySignalProvenanceBuilder().with_downstream_proxy(
            signal_value=0.3,
            sample_count=50,
            acceptance_rate=0.8,
            rerank_consistency=0.85,
        ).build()
        
        assert provenance.source == SignalSource.DOWNSTREAM_PROXY
        assert provenance.sample_count_used == 50
        assert "50" in provenance.explanation
    
    def test_build_offline_replay(self):
        """Should build offline replay provenance."""
        provenance = QualitySignalProvenanceBuilder().with_offline_replay(
            signal_value=0.2,
            sample_count=30,
            hit_at_1=0.6,
            hit_at_3=0.9,
        ).build()
        
        assert provenance.source == SignalSource.OFFLINE_REPLAY
        assert provenance.sample_count_used == 30


class TestProvenanceConsistency:
    """Test provenance consistency validation."""
    
    def test_valid_provenance_no_errors(self):
        """Valid provenance should have no errors."""
        provenance = QualitySignalProvenanceBuilder().with_shadow_compare(
            signal_value=0.4,
            sample_count=40,
        ).build()
        
        errors = provenance.validate_consistency()
        assert len(errors) == 0
    
    def test_interpretable_with_zero_samples_fails(self):
        """Interpretable with sample_count=0 should fail."""
        provenance = QualitySignalProvenance(
            signal_value=0.4,
            source=SignalSource.SHADOW_COMPARE,
            interpretable=True,
            confidence=0.7,
            sample_count_used=0,  # Invalid!
        )
        
        errors = provenance.validate_consistency()
        assert len(errors) > 0
        assert any("sample_count_used=0" in e for e in errors)
    
    def test_explanation_mismatch_fails(self):
        """Explanation not matching sample count should fail."""
        provenance = QualitySignalProvenance(
            signal_value=0.4,
            source=SignalSource.SHADOW_COMPARE,
            interpretable=True,
            confidence=0.7,
            sample_count_used=40,
            explanation="Computed from 0 samples",  # Mismatch!
        )
        
        errors = provenance.validate_consistency()
        assert len(errors) > 0
    
    def test_shadow_compare_requires_providers(self):
        """Shadow compare without providers should fail."""
        provenance = QualitySignalProvenance(
            signal_value=0.4,
            source=SignalSource.SHADOW_COMPARE,
            interpretable=True,
            confidence=0.7,
            sample_count_used=40,
            explanation="Computed from 40 samples",
            baseline_provider="",  # Missing
            candidate_provider="",  # Missing
        )
        
        errors = provenance.validate_consistency()
        assert any("requires baseline_provider" in e for e in errors)


class TestPromotionValidation:
    """Test promotion validation."""
    
    def test_valid_provenance_allows_promotion(self):
        """Valid provenance should allow promotion."""
        provenance = QualitySignalProvenanceBuilder().with_shadow_compare(
            signal_value=0.4,
            sample_count=40,
        ).build()
        
        assert provenance.is_valid_for_promotion() is True
    
    def test_not_interpretable_blocks_promotion(self):
        """Non-interpretable should block promotion."""
        provenance = QualitySignalProvenanceBuilder().with_placeholder(
            reason="No samples"
        ).build()
        
        assert provenance.is_valid_for_promotion() is False
    
    def test_zero_samples_blocks_promotion(self):
        """Zero samples should block promotion."""
        provenance = QualitySignalProvenance(
            signal_value=0.4,
            source=SignalSource.SHADOW_COMPARE,
            interpretable=True,
            confidence=0.7,
            sample_count_used=0,
        )
        
        assert provenance.is_valid_for_promotion() is False
    
    def test_consistency_errors_block_promotion(self):
        """Consistency errors should block promotion."""
        provenance = QualitySignalProvenance(
            signal_value=0.4,
            source=SignalSource.SHADOW_COMPARE,
            interpretable=True,
            confidence=0.7,
            sample_count_used=40,
            explanation="Wrong explanation",  # Mismatch
        )
        
        assert provenance.is_valid_for_promotion() is False


class TestComputeShadowCompareProvenance:
    """Test shadow compare provenance computation."""
    
    def test_no_samples_returns_placeholder(self):
        """No samples should return placeholder."""
        provenance = compute_shadow_compare_provenance(
            ollama_top_k_results=[],
            tfidf_top_k_results=[],
        )
        
        assert provenance.source == SignalSource.PLACEHOLDER
        assert provenance.interpretable is False
    
    def test_with_samples_returns_valid(self):
        """With samples should return valid provenance."""
        ollama_results = [["a", "b", "c"] for _ in range(10)]
        tfidf_results = [["x", "y", "z"] for _ in range(10)]
        
        provenance = compute_shadow_compare_provenance(
            ollama_top_k_results=ollama_results,
            tfidf_top_k_results=tfidf_results,
            k=3,
        )
        
        assert provenance.source == SignalSource.SHADOW_COMPARE
        assert provenance.interpretable is True
        assert provenance.sample_count_used == 10
        assert "10" in provenance.explanation
        assert provenance.baseline_provider == "tfidf"
        assert provenance.candidate_provider == "ollama"


class TestProvenanceToDict:
    """Test provenance serialization."""
    
    def test_to_dict_includes_all_fields(self):
        """to_dict should include all fields."""
        provenance = QualitySignalProvenanceBuilder().with_shadow_compare(
            signal_value=0.4,
            sample_count=40,
            batch_ref="test_batch",
        ).build()
        
        d = provenance.to_dict()
        
        assert "signal_value" in d
        assert "source" in d
        assert "interpretable" in d
        assert "sample_count_used" in d
        assert "computation_method" in d
        assert "explanation" in d
        assert "valid_for_promotion" in d
        assert "validation_errors" in d
    
    def test_to_dict_shows_validation_errors(self):
        """to_dict should show validation errors."""
        provenance = QualitySignalProvenance(
            signal_value=0.4,
            source=SignalSource.SHADOW_COMPARE,
            interpretable=True,
            confidence=0.7,
            sample_count_used=0,  # Invalid
        )
        
        d = provenance.to_dict()
        
        assert len(d["validation_errors"]) > 0
        assert d["valid_for_promotion"] is False


class TestV6gFix:
    """Test the v6g fix for v6f issue."""
    
    def test_fix_v6f_issue(self):
        """v6f issue: interpretable=True with sample_count=0 should be fixed."""
        # v6f bug would allow this:
        # provenance = QualitySignalResult(
        #     signal_value=0.4,
        #     source=QualitySignalSource.SHADOW_COMPARE,
        #     interpretable=True,
        #     explanation="Computed from 0 samples"  # Contradiction!
        # )
        
        # v6g fix: use builder which enforces consistency
        provenance = QualitySignalProvenanceBuilder().with_shadow_compare(
            signal_value=0.4,
            sample_count=40,
        ).build()
        
        # Now sample_count_used matches explanation
        assert provenance.sample_count_used == 40
        assert "40" in provenance.explanation
        assert provenance.is_valid_for_promotion() is True
    
    def test_contradiction_detected(self):
        """Contradiction between sample_count and explanation should be detected."""
        provenance = QualitySignalProvenance(
            signal_value=0.4,
            source=SignalSource.SHADOW_COMPARE,
            interpretable=True,
            confidence=0.7,
            sample_count_used=40,
            explanation="Computed from 0 samples",  # Contradiction!
        )
        
        errors = provenance.validate_consistency()
        
        # v6g should detect this
        assert any("inconsistent" in e.lower() or "doesn't mention" in e.lower() for e in errors)
