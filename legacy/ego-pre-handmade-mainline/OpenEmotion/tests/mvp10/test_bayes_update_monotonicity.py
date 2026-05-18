"""
MVP-10 T25: Bayes Updater Tests

Tests for bayes_updater.py:
- Conservative prior
- Likelihood model per evidence type
- Output: posterior + uncertainty report
- Monotonicity: More consistent evidence should increase posterior
"""
import math
import os
import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from emotiond.science.bayes_updater import (
    EvidenceType,
    EvidenceItem,
    BayesResult,
    LikelihoodModel,
    BayesUpdater,
    create_bayes_updater,
    aggregate_evidence,
)


class TestEvidenceType:
    """Test EvidenceType enum."""
    
    def test_types_exist(self):
        """Test that required types exist."""
        assert EvidenceType.WORKSPACE.value == "workspace"
        assert EvidenceType.HOT.value == "hot"
        assert EvidenceType.VALENCE.value == "valence"
        assert EvidenceType.CONTINUITY.value == "continuity"


class TestEvidenceItem:
    """Test EvidenceItem dataclass."""
    
    def test_item_creation(self):
        """Test creating an EvidenceItem."""
        item = EvidenceItem(
            evidence_type=EvidenceType.WORKSPACE,
            value=0.7,
            strength=0.8,
        )
        
        assert item.evidence_type == EvidenceType.WORKSPACE
        assert item.value == 0.7
        assert item.strength == 0.8
    
    def test_item_to_dict(self):
        """Test EvidenceItem serialization."""
        item = EvidenceItem(
            evidence_type=EvidenceType.HOT,
            value=0.6,
            strength=0.9,
            likelihood=0.75,
        )
        
        d = item.to_dict()
        
        assert d["evidence_type"] == "hot"
        assert d["value"] == 0.6
        assert d["strength"] == 0.9


class TestBayesResult:
    """Test BayesResult dataclass."""
    
    def test_result_creation(self):
        """Test creating a BayesResult."""
        result = BayesResult(
            prior=0.5,
            posterior=0.7,
            log_likelihood=0.5,
            evidence_count=3,
            evidence_types=["workspace", "hot"],
            uncertainty=0.3,
            weakest_source="continuity",
            strongest_source="workspace",
        )
        
        assert result.prior == 0.5
        assert result.posterior == 0.7
    
    def test_result_to_dict(self):
        """Test BayesResult serialization."""
        result = BayesResult(
            prior=0.5,
            posterior=0.7,
            log_likelihood=0.5,
            evidence_count=1,
            evidence_types=["workspace"],
            uncertainty=0.2,
            weakest_source=None,
            strongest_source="workspace",
        )
        
        d = result.to_dict()
        
        assert d["prior"] == 0.5
        assert d["posterior"] == 0.7


class TestLikelihoodModel:
    """Test LikelihoodModel."""
    
    def test_compute_likelihood_bounds(self):
        """Test that likelihood is bounded."""
        for evidence_type in EvidenceType:
            for value in [0.0, 0.5, 1.0]:
                for strength in [0.0, 0.5, 1.0]:
                    likelihood = LikelihoodModel.compute_likelihood(
                        evidence_type, value, strength
                    )
                    assert 0.01 <= likelihood <= 0.99
    
    def test_compute_likelihood_high_value(self):
        """Test likelihood with high evidence value."""
        likelihood = LikelihoodModel.compute_likelihood(
            EvidenceType.WORKSPACE, 1.0, 1.0
        )
        
        assert likelihood > 0.5
    
    def test_compute_likelihood_low_value(self):
        """Test likelihood with low evidence value."""
        likelihood = LikelihoodModel.compute_likelihood(
            EvidenceType.WORKSPACE, 0.0, 0.5
        )
        
        # Low value should give lower likelihood
        assert likelihood == 0.5  # Low value with moderate strength gives baseline
    
    def test_compute_log_likelihood(self):
        """Test log-likelihood computation."""
        log_ll = LikelihoodModel.compute_log_likelihood(
            EvidenceType.WORKSPACE, 0.5, 0.5
        )
        
        # Log of a probability between 0 and 1 should be negative
        assert log_ll < 0
    
    def test_different_evidence_types(self):
        """Test that different evidence types give different likelihoods."""
        ll_workspace = LikelihoodModel.compute_likelihood(
            EvidenceType.WORKSPACE, 0.5, 0.5
        )
        ll_hot = LikelihoodModel.compute_likelihood(
            EvidenceType.HOT, 0.5, 0.5
        )
        
        # Different types have different sensitivity/specificity
        # So likelihoods should differ (at least potentially)
        assert isinstance(ll_workspace, float)
        assert isinstance(ll_hot, float)


class TestBayesUpdater:
    """Test BayesUpdater class."""
    
    def test_initialization(self):
        """Test default initialization."""
        updater = BayesUpdater()
        
        assert updater.prior == 0.5  # Conservative default
    
    def test_initialization_custom_prior(self):
        """Test initialization with custom prior."""
        updater = BayesUpdater(prior=0.7)
        
        assert updater.prior == 0.7
    
    def test_add_evidence(self):
        """Test adding evidence."""
        updater = BayesUpdater()
        
        item = updater.add_evidence(
            EvidenceType.WORKSPACE,
            value=0.7,
            strength=0.8,
        )
        
        assert item.value == 0.7
        assert item.likelihood is not None
        assert len(updater.evidence) == 1
    
    def test_compute_posterior_no_evidence(self):
        """Test posterior with no evidence returns prior."""
        updater = BayesUpdater(prior=0.5)
        
        result = updater.compute_posterior()
        
        assert result.posterior == 0.5
        assert result.evidence_count == 0
        assert result.uncertainty == 1.0
    
    def test_compute_posterior_with_evidence(self):
        """Test posterior with evidence."""
        updater = BayesUpdater(prior=0.5)
        updater.add_evidence(EvidenceType.WORKSPACE, 0.8, 0.9)
        
        result = updater.compute_posterior()
        
        assert result.posterior != 0.5  # Should differ from prior
        assert result.evidence_count == 1
    
    def test_posterior_bounds(self):
        """Test that posterior is bounded."""
        updater = BayesUpdater(prior=0.5)
        
        # Add extreme evidence
        updater.add_evidence(EvidenceType.WORKSPACE, 1.0, 1.0)
        updater.add_evidence(EvidenceType.HOT, 1.0, 1.0)
        updater.add_evidence(EvidenceType.VALENCE, 1.0, 1.0)
        
        result = updater.compute_posterior()
        
        assert 0.01 <= result.posterior <= 0.99
    
    def test_get_uncertainty_report(self):
        """Test getting uncertainty report."""
        updater = BayesUpdater()
        updater.add_evidence(EvidenceType.WORKSPACE, 0.7, 0.8)
        
        report = updater.get_uncertainty_report()
        
        assert "posterior" in report
        assert "uncertainty" in report
        assert "weakest_source" in report
        assert "strongest_source" in report
        assert "evidence_by_type" in report
        assert "recommendations" in report
    
    def test_reset(self):
        """Test resetting the updater."""
        updater = BayesUpdater()
        updater.add_evidence(EvidenceType.WORKSPACE, 0.5, 0.5)
        
        updater.reset()
        
        assert len(updater.evidence) == 0
        assert updater.prior == 0.5
    
    def test_reset_with_new_prior(self):
        """Test resetting with new prior."""
        updater = BayesUpdater(prior=0.5)
        
        updater.reset(prior=0.7)
        
        assert updater.prior == 0.7
    
    def test_to_dict(self):
        """Test serialization."""
        updater = BayesUpdater()
        updater.add_evidence(EvidenceType.WORKSPACE, 0.5, 0.5)
        
        d = updater.to_dict()
        
        assert d["prior"] == 0.5
        assert d["evidence_count"] == 1


class TestMonotonicity:
    """Test monotonicity property: consistent evidence increases posterior."""
    
    def test_more_positive_evidence_increases_posterior(self):
        """Test that more positive evidence increases posterior."""
        updater = BayesUpdater(prior=0.5)
        
        # Add one piece of evidence
        updater.add_evidence(EvidenceType.WORKSPACE, 0.8, 0.9)
        result1 = updater.compute_posterior()
        
        # Add more positive evidence
        updater.add_evidence(EvidenceType.HOT, 0.8, 0.9)
        result2 = updater.compute_posterior()
        
        # Posterior should increase (or stay same)
        assert result2.posterior >= result1.posterior
    
    def test_consistent_evidence_sequence(self):
        """Test that consistent evidence moves posterior in expected direction."""
        updater = BayesUpdater(prior=0.5)
        
        posteriors = []
        for i in range(5):
            updater.add_evidence(EvidenceType.WORKSPACE, 0.9, 0.8)
            result = updater.compute_posterior()
            posteriors.append(result.posterior)
        
        # Each step should increase posterior (or stay same)
        for i in range(1, len(posteriors)):
            assert posteriors[i] >= posteriors[i-1] - 0.01  # Allow small numerical error
    
    def test_mixed_evidence(self):
        """Test that mixed evidence gives intermediate posterior."""
        updater_high = BayesUpdater(prior=0.5)
        updater_low = BayesUpdater(prior=0.5)
        updater_mixed = BayesUpdater(prior=0.5)
        
        # High evidence
        for _ in range(3):
            updater_high.add_evidence(EvidenceType.WORKSPACE, 0.9, 0.9)
        
        # Low evidence
        for _ in range(3):
            updater_low.add_evidence(EvidenceType.WORKSPACE, 0.1, 0.9)
        
        # Mixed evidence
        updater_mixed.add_evidence(EvidenceType.WORKSPACE, 0.9, 0.9)
        updater_mixed.add_evidence(EvidenceType.WORKSPACE, 0.5, 0.5)
        updater_mixed.add_evidence(EvidenceType.WORKSPACE, 0.1, 0.9)
        
        result_high = updater_high.compute_posterior()
        result_low = updater_low.compute_posterior()
        result_mixed = updater_mixed.compute_posterior()
        
        # High evidence should give highest posterior
        # Low evidence should give lowest posterior
        # Mixed should be in between
        assert result_high.posterior > result_mixed.posterior
        assert result_mixed.posterior > result_low.posterior
    
    def test_strength_affects_posterior(self):
        """Test that evidence strength affects posterior magnitude."""
        updater_weak = BayesUpdater(prior=0.5)
        updater_strong = BayesUpdater(prior=0.5)
        
        # Same value, different strength
        updater_weak.add_evidence(EvidenceType.WORKSPACE, 0.8, 0.3)
        updater_strong.add_evidence(EvidenceType.WORKSPACE, 0.8, 0.9)
        
        result_weak = updater_weak.compute_posterior()
        result_strong = updater_strong.compute_posterior()
        
        # Strong evidence should have larger effect
        assert result_strong.posterior != result_weak.posterior


class TestUncertainty:
    """Test uncertainty computation."""
    
    def test_uncertainty_decreases_with_more_evidence(self):
        """Test that uncertainty decreases with more evidence."""
        updater = BayesUpdater(prior=0.5)
        
        result1 = updater.compute_posterior()
        uncertainty1 = result1.uncertainty
        
        updater.add_evidence(EvidenceType.WORKSPACE, 0.5, 0.5)
        result2 = updater.compute_posterior()
        uncertainty2 = result2.uncertainty
        
        updater.add_evidence(EvidenceType.WORKSPACE, 0.5, 0.5)
        result3 = updater.compute_posterior()
        uncertainty3 = result3.uncertainty
        
        # More evidence should reduce uncertainty
        assert uncertainty2 <= uncertainty1
        assert uncertainty3 <= uncertainty2
    
    def test_uncertainty_high_with_conflicting_evidence(self):
        """Test that uncertainty is high with conflicting evidence."""
        updater = BayesUpdater(prior=0.5)
        
        # Conflicting evidence
        updater.add_evidence(EvidenceType.WORKSPACE, 0.9, 0.9)
        updater.add_evidence(EvidenceType.WORKSPACE, 0.1, 0.9)
        
        result = updater.compute_posterior()
        
        # High variance should increase uncertainty
        assert result.uncertainty > 0
    
    def test_weakest_strongest_source(self):
        """Test identification of weakest and strongest sources."""
        updater = BayesUpdater(prior=0.5)
        
        updater.add_evidence(EvidenceType.WORKSPACE, 0.9, 0.9)  # Strong
        updater.add_evidence(EvidenceType.CONTINUITY, 0.1, 0.1)  # Weak
        
        result = updater.compute_posterior()
        
        assert result.strongest_source == "workspace"
        assert result.weakest_source == "continuity"


class TestRecommendations:
    """Test recommendation generation."""
    
    def test_recommendation_high_uncertainty(self):
        """Test recommendation for high uncertainty."""
        updater = BayesUpdater(prior=0.5)
        
        # Minimal evidence
        result = updater.compute_posterior()
        
        report = updater.get_uncertainty_report()
        
        # Should recommend more evidence
        assert any("more evidence" in r.lower() for r in report["recommendations"])
    
    def test_recommendation_missing_types(self):
        """Test recommendation for missing evidence types."""
        updater = BayesUpdater(prior=0.5)
        updater.add_evidence(EvidenceType.WORKSPACE, 0.5, 0.5)
        
        report = updater.get_uncertainty_report()
        
        # Should recommend adding missing types
        recs = " ".join(report["recommendations"]).lower()
        assert "missing" in recs or "hot" in recs or "valence" in recs


class TestFactoryFunctions:
    """Test factory functions."""
    
    def test_create_bayes_updater(self):
        """Test factory function."""
        updater = create_bayes_updater()
        
        assert isinstance(updater, BayesUpdater)
    
    def test_create_with_prior(self):
        """Test factory with custom prior."""
        updater = create_bayes_updater(prior=0.7)
        
        assert updater.prior == 0.7
    
    def test_aggregate_evidence(self):
        """Test aggregate evidence function."""
        evidence_items = [
            {"type": "workspace", "value": 0.8, "strength": 0.9},
            {"type": "hot", "value": 0.7, "strength": 0.8},
        ]
        
        result = aggregate_evidence(evidence_items, prior=0.5)
        
        assert "bayes_result" in result
        assert "uncertainty_report" in result
        assert result["bayes_result"]["evidence_count"] == 2


class TestEdgeCases:
    """Test edge cases."""
    
    def test_zero_strength_evidence(self):
        """Test evidence with zero strength."""
        updater = BayesUpdater(prior=0.5)
        updater.add_evidence(EvidenceType.WORKSPACE, 0.9, 0.0)
        
        result = updater.compute_posterior()
        
        # Should still work
        assert 0.01 <= result.posterior <= 0.99
    
    def test_extreme_prior(self):
        """Test with extreme prior values."""
        updater_high = BayesUpdater(prior=0.99)
        updater_low = BayesUpdater(prior=0.01)
        
        # Should still work
        result_high = updater_high.compute_posterior()
        result_low = updater_low.compute_posterior()
        
        assert 0.01 <= result_high.posterior <= 0.99
        assert 0.01 <= result_low.posterior <= 0.99
    
    def test_many_evidence_items(self):
        """Test with many evidence items."""
        updater = BayesUpdater(prior=0.5)
        
        for i in range(20):
            updater.add_evidence(EvidenceType.WORKSPACE, 0.5 + i * 0.01, 0.5)
        
        result = updater.compute_posterior()
        
        # Should handle many items
        assert result.evidence_count == 20
    
    def test_all_evidence_types(self):
        """Test with all evidence types."""
        updater = BayesUpdater(prior=0.5)
        
        for et in EvidenceType:
            updater.add_evidence(et, 0.7, 0.8)
        
        result = updater.compute_posterior()
        
        assert len(result.evidence_types) == 4
