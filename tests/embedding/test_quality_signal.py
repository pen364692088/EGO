"""
Tests for Quality Signal (v6f).

Validates:
- Signal computation
- Signal interpretability
- Signal sources
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from emotiond.memory.embedding.quality_signal import (
    QualitySignalCalculator,
    QualitySignalResult,
    QualitySignalSource,
    compute_quality_gain_signal,
)


class TestQualitySignalSources:
    """Test quality signal source enum."""
    
    def test_shadow_compare_exists(self):
        """SHADOW_COMPARE should exist."""
        assert QualitySignalSource.SHADOW_COMPARE.value == "shadow_compare"
    
    def test_downstream_proxy_exists(self):
        """DOWNSTREAM_PROXY should exist."""
        assert QualitySignalSource.DOWNSTREAM_PROXY.value == "downstream_proxy"
    
    def test_offline_replay_exists(self):
        """OFFLINE_REPLAY should exist."""
        assert QualitySignalSource.OFFLINE_REPLAY.value == "offline_replay"
    
    def test_placeholder_exists(self):
        """PLACEHOLDER should exist."""
        assert QualitySignalSource.PLACEHOLDER.value == "placeholder"


class TestShadowCompareSignal:
    """Test shadow comparison signal."""
    
    def test_no_overlap_high_signal(self):
        """No overlap should produce high signal."""
        calculator = QualitySignalCalculator()
        
        ollama_results = ["a", "b", "c", "d", "e"]
        tfidf_results = ["v", "w", "x", "y", "z"]
        
        result = calculator.compute_shadow_compare_signal(
            ollama_top_k=ollama_results,
            tfidf_top_k=tfidf_results,
            k=5,
        )
        
        assert result.source == QualitySignalSource.SHADOW_COMPARE
        assert result.interpretable is True
        assert result.signal_value == 1.0  # No overlap
    
    def test_full_overlap_low_signal(self):
        """Full overlap should produce low signal."""
        calculator = QualitySignalCalculator()
        
        results = ["a", "b", "c", "d", "e"]
        
        result = calculator.compute_shadow_compare_signal(
            ollama_top_k=results,
            tfidf_top_k=results,
            k=5,
        )
        
        assert result.source == QualitySignalSource.SHADOW_COMPARE
        assert result.interpretable is True
        assert result.signal_value == 0.0  # Full overlap
    
    def test_partial_overlap(self):
        """Partial overlap should produce moderate signal."""
        calculator = QualitySignalCalculator()
        
        ollama_results = ["a", "b", "c", "d", "e"]
        tfidf_results = ["a", "b", "x", "y", "z"]
        
        result = calculator.compute_shadow_compare_signal(
            ollama_top_k=ollama_results,
            tfidf_top_k=tfidf_results,
            k=5,
        )
        
        assert result.interpretable is True
        assert 0 < result.signal_value < 1


class TestDownstreamProxySignal:
    """Test downstream proxy signal."""
    
    def test_high_acceptance_positive_signal(self):
        """High acceptance should produce positive signal."""
        calculator = QualitySignalCalculator()
        
        result = calculator.compute_downstream_proxy_signal(
            acceptance_rate=0.9,
            rerank_consistency=0.85,
        )
        
        assert result.source == QualitySignalSource.DOWNSTREAM_PROXY
        assert result.interpretable is True
        assert result.signal_value >= 0
    
    def test_low_acceptance_lower_signal(self):
        """Low acceptance should produce lower signal."""
        calculator = QualitySignalCalculator()
        
        result = calculator.compute_downstream_proxy_signal(
            acceptance_rate=0.5,
            rerank_consistency=0.5,
        )
        
        assert result.interpretable is True


class TestOfflineReplaySignal:
    """Test offline replay signal."""
    
    def test_improvement_over_baseline(self):
        """Improvement over baseline should produce positive signal."""
        calculator = QualitySignalCalculator()
        
        result = calculator.compute_offline_replay_signal(
            hit_at_1=0.6,
            hit_at_3=0.9,
            baseline_hit_at_1=0.4,
            baseline_hit_at_3=0.8,
        )
        
        assert result.source == QualitySignalSource.OFFLINE_REPLAY
        assert result.interpretable is True
        assert result.signal_value > 0
    
    def test_regression_negative_signal(self):
        """Regression should produce negative signal."""
        calculator = QualitySignalCalculator()
        
        result = calculator.compute_offline_replay_signal(
            hit_at_1=0.3,
            hit_at_3=0.7,
            baseline_hit_at_1=0.4,
            baseline_hit_at_3=0.8,
        )
        
        assert result.interpretable is True
        assert result.signal_value < 0


class TestPlaceholderSignal:
    """Test placeholder signal."""
    
    def test_placeholder_not_interpretable(self):
        """Placeholder should not be interpretable."""
        calculator = QualitySignalCalculator()
        
        result = calculator.compute_placeholder_signal(
            reason="Test placeholder"
        )
        
        assert result.source == QualitySignalSource.PLACEHOLDER
        assert result.interpretable is False
        assert result.confidence == 0.0
    
    def test_placeholder_default_value(self):
        """Placeholder should use default value."""
        calculator = QualitySignalCalculator()
        
        result = calculator.compute_placeholder_signal(
            default_value=0.5,
            reason="Test"
        )
        
        assert result.signal_value == 0.5


class TestSignalInterpretability:
    """Test signal interpretability rules."""
    
    def test_shadow_is_interpretable(self):
        """Shadow compare should be interpretable."""
        calculator = QualitySignalCalculator()
        
        result = calculator.compute_shadow_compare_signal(
            ollama_top_k=["a", "b"],
            tfidf_top_k=["c", "d"],
        )
        
        assert result.interpretable is True
    
    def test_placeholder_not_interpretable(self):
        """Placeholder should not be interpretable."""
        calculator = QualitySignalCalculator()
        
        result = calculator.compute_placeholder_signal()
        
        assert result.interpretable is False


class TestExplainQualitySignal:
    """Test signal explanation."""
    
    def test_explain_positive_signal(self):
        """Should explain positive signal."""
        calculator = QualitySignalCalculator()
        
        result = calculator.compute_offline_replay_signal(
            hit_at_1=0.7,
            hit_at_3=0.95,
        )
        
        explanation = calculator.explain_quality_signal(result)
        
        assert "Strong positive signal" in explanation or "Positive signal" in explanation
        assert "offline_replay" in explanation
    
    def test_explain_non_interpretable(self):
        """Should explain non-interpretable signal."""
        calculator = QualitySignalCalculator()
        
        result = calculator.compute_placeholder_signal(
            reason="No data available"
        )
        
        explanation = calculator.explain_quality_signal(result)
        
        assert "NOT interpretable" in explanation
        assert "No data available" in explanation


class TestConvenienceFunction:
    """Test convenience function."""
    
    def test_compute_shadow(self):
        """Should compute shadow signal."""
        result = compute_quality_gain_signal(
            source="shadow",
            ollama_top_k=["a"],
            tfidf_top_k=["b"],
        )
        
        assert result.source == QualitySignalSource.SHADOW_COMPARE
    
    def test_compute_proxy(self):
        """Should compute proxy signal."""
        result = compute_quality_gain_signal(
            source="proxy",
            acceptance_rate=0.8,
            rerank_consistency=0.8,
        )
        
        assert result.source == QualitySignalSource.DOWNSTREAM_PROXY
    
    def test_compute_placeholder(self):
        """Should compute placeholder signal."""
        result = compute_quality_gain_signal(
            source="placeholder",
            reason="Test",
        )
        
        assert result.source == QualitySignalSource.PLACEHOLDER
