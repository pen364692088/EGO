"""
MVP11-T20: Bayes Updater v2 Monotonicity Tests

Tests that BayesUpdaterV2 behaves monotonically with respect to:
1. Evidence: More consistent evidence → higher posterior
2. Evidence strength: Higher strength → larger posterior change
3. Homeostasis: Better homeostatic state → higher modulation
4. EFE: Lower risk/ambiguity/cost, higher info_gain → higher modulation
5. Governor: Safe actions → higher posterior than blocked/destructive

Also tests:
- Uncertainty report correctly identifies largest source
- Integration with MVP11 components (homeostasis, EFE, governor)
"""
import pytest
import sys
import os
import math

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from emotiond.science.bayes_updater_v2 import (
    BayesUpdaterV2,
    BayesResultV2,
    UncertaintyReport,
    UncertaintySource,
    MVP11Context,
    create_bayes_updater_v2,
    aggregate_evidence_v2,
)
from emotiond.science.bayes_updater import EvidenceType


class TestBayesUpdaterV2Basics:
    """Test BayesUpdaterV2 basic functionality."""
    
    def test_create_updater(self):
        """Test updater can be created with default values."""
        updater = BayesUpdaterV2()
        assert updater.prior == 0.5
        assert len(updater.evidence) == 0
    
    def test_create_updater_custom_prior(self):
        """Test updater can be created with custom prior."""
        updater = BayesUpdaterV2(prior=0.7)
        assert updater.prior == 0.7
    
    def test_add_evidence(self):
        """Test adding evidence."""
        updater = BayesUpdaterV2()
        item = updater.add_evidence(EvidenceType.WORKSPACE, 0.7, strength=0.8)
        
        assert len(updater.evidence) == 1
        assert item.value == 0.7
        assert item.strength == 0.8
    
    def test_compute_posterior_no_evidence(self):
        """Test posterior with no evidence returns prior."""
        updater = BayesUpdaterV2(prior=0.6)
        result = updater.compute_posterior()
        
        assert result.posterior == 0.6
        assert result.evidence_count == 0
    
    def test_compute_posterior_with_evidence(self):
        """Test posterior changes with evidence."""
        updater = BayesUpdaterV2(prior=0.5)
        
        # Add supporting evidence
        updater.add_evidence(EvidenceType.WORKSPACE, 0.8, strength=0.9)
        result = updater.compute_posterior()
        
        assert result.posterior > 0.5
        assert result.evidence_count == 1


class TestEvidenceMonotonicity:
    """Test monotonicity of posterior with respect to evidence."""
    
    def test_more_supporting_evidence_increases_posterior(self):
        """More consistent supporting evidence → higher posterior."""
        posteriors = []
        
        for count in [1, 3, 5, 7]:
            updater = BayesUpdaterV2(prior=0.5)
            for _ in range(count):
                updater.add_evidence(EvidenceType.WORKSPACE, 0.8, strength=0.8)
            result = updater.compute_posterior()
            posteriors.append(result.posterior)
        
        # Posterior should increase with more supporting evidence
        for i in range(1, len(posteriors)):
            assert posteriors[i] >= posteriors[i-1], \
                f"Posterior not monotonic: {posteriors}"
    
    def test_more_opposing_evidence_decreases_posterior(self):
        """More consistent opposing evidence → lower posterior."""
        posteriors = []
        
        for count in [1, 3, 5, 7]:
            updater = BayesUpdaterV2(prior=0.5)
            for _ in range(count):
                updater.add_evidence(EvidenceType.WORKSPACE, 0.2, strength=0.8)
            result = updater.compute_posterior()
            posteriors.append(result.posterior)
        
        # Posterior should decrease with more opposing evidence
        for i in range(1, len(posteriors)):
            assert posteriors[i] <= posteriors[i-1], \
                f"Posterior not monotonic: {posteriors}"
    
    def test_higher_strength_larger_change(self):
        """Higher evidence strength → larger posterior change."""
        changes = []
        
        for strength in [0.3, 0.5, 0.7, 0.9]:
            updater = BayesUpdaterV2(prior=0.5)
            updater.add_evidence(EvidenceType.WORKSPACE, 0.9, strength=strength)
            result = updater.compute_posterior()
            changes.append(abs(result.posterior - 0.5))
        
        # Larger strength should produce larger changes
        for i in range(1, len(changes)):
            assert changes[i] >= changes[i-1] * 0.9, \
                f"Strength not monotonic: {changes}"


class TestHomeostasisModulation:
    """Test homeostasis modulation of posterior."""
    
    def test_homeostasis_modulation_exists(self):
        """Test that homeostasis state affects posterior."""
        updater = BayesUpdaterV2()
        updater.add_evidence(EvidenceType.WORKSPACE, 0.7, strength=0.8)
        
        # Create a mock homeostasis state
        class MockHomeostasis:
            energy = 0.5
            safety = 0.5
            certainty = 0.5
            
            def to_dict(self):
                return {
                    "energy": self.energy,
                    "safety": self.safety,
                    "certainty": self.certainty,
                }
        
        # Without homeostasis
        result_no_homeo = updater.compute_posterior()
        
        # With good homeostasis
        updater2 = BayesUpdaterV2()
        updater2.add_evidence(EvidenceType.WORKSPACE, 0.7, strength=0.8)
        updater2.set_homeostasis(MockHomeostasis())
        result_good_homeo = updater2.compute_posterior()
        
        # Should have modulation values recorded
        assert result_good_homeo.homeostasis_modulation != 0.0
    
    def test_better_homeostasis_higher_modulation(self):
        """Better homeostatic state → higher modulation."""
        modulations = []
        
        for energy_level in [0.3, 0.5, 0.7, 0.9]:
            class MockHomeostasis:
                energy = energy_level
                safety = energy_level
                certainty = energy_level
                
                def to_dict(self):
                    return {"energy": self.energy, "safety": self.safety, "certainty": self.certainty}
            
            updater = BayesUpdaterV2()
            updater.add_evidence(EvidenceType.WORKSPACE, 0.7, strength=0.8)
            updater.set_homeostasis(MockHomeostasis())
            result = updater.compute_posterior()
            modulations.append(result.homeostasis_modulation)
        
        # Better homeostasis should give higher (or equal) modulation
        for i in range(1, len(modulations)):
            assert modulations[i] >= modulations[i-1] * 0.95, \
                f"Homeostasis modulation not monotonic: {modulations}"


class TestEFEModulation:
    """Test EFE modulation of posterior."""
    
    def test_efe_modulation_exists(self):
        """Test that EFE terms affect posterior."""
        updater = BayesUpdaterV2()
        updater.add_evidence(EvidenceType.WORKSPACE, 0.7, strength=0.8)
        updater.set_efe_terms(risk=0.3, ambiguity=0.2, info_gain=0.7, cost=0.2)
        result = updater.compute_posterior()
        
        assert result.efe_modulation != 0.0
    
    def test_lower_risk_higher_modulation(self):
        """Lower risk → higher EFE modulation."""
        modulations = []
        
        for risk in [0.8, 0.6, 0.4, 0.2]:
            updater = BayesUpdaterV2()
            updater.add_evidence(EvidenceType.WORKSPACE, 0.7, strength=0.8)
            updater.set_efe_terms(risk=risk, ambiguity=0.3, info_gain=0.5, cost=0.3)
            result = updater.compute_posterior()
            modulations.append(result.efe_modulation)
        
        # Lower risk should give higher modulation
        for i in range(1, len(modulations)):
            assert modulations[i] >= modulations[i-1] * 0.95, \
                f"Risk not monotonic: {modulations}"
    
    def test_higher_info_gain_higher_modulation(self):
        """Higher info_gain → higher EFE modulation."""
        modulations = []
        
        for info_gain in [0.2, 0.4, 0.6, 0.8]:
            updater = BayesUpdaterV2()
            updater.add_evidence(EvidenceType.WORKSPACE, 0.7, strength=0.8)
            updater.set_efe_terms(risk=0.3, ambiguity=0.3, info_gain=info_gain, cost=0.3)
            result = updater.compute_posterior()
            modulations.append(result.efe_modulation)
        
        # Higher info_gain should give higher modulation
        for i in range(1, len(modulations)):
            assert modulations[i] >= modulations[i-1] * 0.95, \
                f"Info gain not monotonic: {modulations}"
    
    def test_lower_cost_higher_modulation(self):
        """Lower cost → higher EFE modulation."""
        modulations = []
        
        for cost in [0.8, 0.6, 0.4, 0.2]:
            updater = BayesUpdaterV2()
            updater.add_evidence(EvidenceType.WORKSPACE, 0.7, strength=0.8)
            updater.set_efe_terms(risk=0.3, ambiguity=0.3, info_gain=0.5, cost=cost)
            result = updater.compute_posterior()
            modulations.append(result.efe_modulation)
        
        # Lower cost should give higher modulation
        for i in range(1, len(modulations)):
            assert modulations[i] >= modulations[i-1] * 0.95, \
                f"Cost not monotonic: {modulations}"


class TestGovernorModulation:
    """Test governor context modulation of posterior."""
    
    def test_safe_action_higher_posterior(self):
        """Safe actions should have higher posterior than destructive."""
        updater_safe = BayesUpdaterV2()
        updater_safe.add_evidence(EvidenceType.WORKSPACE, 0.7, strength=0.8)
        updater_safe.set_governor_context(action_risk=0.1, is_destructive=False)
        result_safe = updater_safe.compute_posterior()
        
        updater_destructive = BayesUpdaterV2()
        updater_destructive.add_evidence(EvidenceType.WORKSPACE, 0.7, strength=0.8)
        updater_destructive.set_governor_context(action_risk=0.1, is_destructive=True)
        result_destructive = updater_destructive.compute_posterior()
        
        assert result_safe.posterior > result_destructive.posterior, \
            f"Safe action should have higher posterior: {result_safe.posterior} vs {result_destructive.posterior}"
        assert result_safe.governor_safe is True
        assert result_destructive.governor_safe is False
    
    def test_recovery_action_not_penalized(self):
        """Recovery actions should not be penalized even if destructive."""
        updater_recovery = BayesUpdaterV2()
        updater_recovery.add_evidence(EvidenceType.WORKSPACE, 0.7, strength=0.8)
        updater_recovery.set_governor_context(
            action_risk=0.1, is_destructive=True, is_recovery=True
        )
        result_recovery = updater_recovery.compute_posterior()
        
        updater_normal = BayesUpdaterV2()
        updater_normal.add_evidence(EvidenceType.WORKSPACE, 0.7, strength=0.8)
        updater_normal.set_governor_context(action_risk=0.1, is_destructive=False)
        result_normal = updater_normal.compute_posterior()
        
        # Recovery should have similar posterior to normal (not penalized)
        assert abs(result_recovery.posterior - result_normal.posterior) < 0.1, \
            f"Recovery should not be penalized: {result_recovery.posterior} vs {result_normal.posterior}"
    
    def test_high_risk_requires_caution(self):
        """High risk actions should have lower posterior."""
        updater_low_risk = BayesUpdaterV2()
        updater_low_risk.add_evidence(EvidenceType.WORKSPACE, 0.7, strength=0.8)
        updater_low_risk.set_governor_context(action_risk=0.1)
        result_low = updater_low_risk.compute_posterior()
        
        updater_high_risk = BayesUpdaterV2()
        updater_high_risk.add_evidence(EvidenceType.WORKSPACE, 0.7, strength=0.8)
        updater_high_risk.set_governor_context(action_risk=0.95)
        result_high = updater_high_risk.compute_posterior()
        
        assert result_low.posterior >= result_high.posterior, \
            f"Low risk should have higher posterior: {result_low.posterior} vs {result_high.posterior}"


class TestUncertaintyReport:
    """Test uncertainty report functionality."""
    
    def test_uncertainty_report_generated(self):
        """Test that uncertainty report is generated."""
        updater = BayesUpdaterV2()
        updater.add_evidence(EvidenceType.WORKSPACE, 0.7, strength=0.8)
        result = updater.compute_posterior()
        report = updater.get_uncertainty_report()
        
        assert report is not None
        assert report.overall_uncertainty >= 0.0
        assert report.largest_source is not None
    
    def test_identifies_insufficient_evidence(self):
        """Test that insufficient evidence is identified as largest source."""
        updater = BayesUpdaterV2()
        # Only 1 evidence item
        updater.add_evidence(EvidenceType.WORKSPACE, 0.7, strength=0.8)
        result = updater.compute_posterior()
        report = updater.get_uncertainty_report()
        
        assert report.evidence_uncertainty > 0.0
    
    def test_identifies_homeostasis_imbalance(self):
        """Test that homeostasis imbalance is identified."""
        class MockHomeostasis:
            energy = 0.1  # Very low
            safety = 0.1
            certainty = 0.1
            
            def to_dict(self):
                return {"energy": self.energy, "safety": self.safety, "certainty": self.certainty}
        
        updater = BayesUpdaterV2()
        for _ in range(5):  # Good evidence
            updater.add_evidence(EvidenceType.WORKSPACE, 0.7, strength=0.8)
        updater.set_homeostasis(MockHomeostasis())
        result = updater.compute_posterior()
        report = updater.get_uncertainty_report()
        
        assert report.homeostasis_uncertainty > 0.3
    
    def test_identifies_high_risk(self):
        """Test that high risk is identified as uncertainty source."""
        updater = BayesUpdaterV2()
        for _ in range(5):
            updater.add_evidence(EvidenceType.WORKSPACE, 0.7, strength=0.8)
        updater.set_efe_terms(risk=0.9, ambiguity=0.2, info_gain=0.5, cost=0.2)
        result = updater.compute_posterior()
        report = updater.get_uncertainty_report()
        
        assert report.efe_uncertainty > 0.3
    
    def test_identifies_governor_constraint(self):
        """Test that destructive action is identified as constraint."""
        updater = BayesUpdaterV2()
        for _ in range(5):
            updater.add_evidence(EvidenceType.WORKSPACE, 0.7, strength=0.8)
        updater.set_governor_context(action_risk=0.1, is_destructive=True)
        result = updater.compute_posterior()
        report = updater.get_uncertainty_report()
        
        assert report.governor_uncertainty > 0.5
    
    def test_recommendations_generated(self):
        """Test that recommendations are generated."""
        updater = BayesUpdaterV2()
        updater.add_evidence(EvidenceType.WORKSPACE, 0.7, strength=0.3)
        result = updater.compute_posterior()
        report = updater.get_uncertainty_report()
        
        assert len(report.recommendations) > 0


class TestIntegration:
    """Test integration with MVP11 components."""
    
    def test_full_integration(self):
        """Test full integration with all MVP11 components."""
        class MockHomeostasis:
            energy = 0.7
            safety = 0.8
            certainty = 0.6
            
            def to_dict(self):
                return {"energy": self.energy, "safety": self.safety, "certainty": self.certainty}
        
        updater = BayesUpdaterV2(prior=0.5)
        
        # Add evidence
        updater.add_evidence(EvidenceType.WORKSPACE, 0.8, strength=0.9)
        updater.add_evidence(EvidenceType.HOT, 0.7, strength=0.8)
        updater.add_evidence(EvidenceType.VALENCE, 0.6, strength=0.7)
        
        # Set MVP11 context
        updater.set_homeostasis(MockHomeostasis())
        updater.set_efe_terms(risk=0.2, ambiguity=0.3, info_gain=0.7, cost=0.2)
        updater.set_governor_context(action_risk=0.1, is_destructive=False)
        
        # Compute
        result = updater.compute_posterior()
        report = updater.get_uncertainty_report()
        
        # Verify all components are used
        assert result.evidence_count == 3
        assert result.homeostasis_modulation != 0.0
        assert result.efe_modulation != 0.0
        assert result.governor_safe is True
        assert result.posterior > 0.5  # Supporting evidence
        
        # Verify uncertainty report
        assert report.overall_uncertainty < 0.5  # Good overall state
        assert len(report.recommendations) >= 0
    
    def test_serialization(self):
        """Test serialization and deserialization."""
        updater = BayesUpdaterV2(prior=0.6)
        updater.add_evidence(EvidenceType.WORKSPACE, 0.7, strength=0.8)
        updater.set_efe_terms(risk=0.3, ambiguity=0.2, info_gain=0.6, cost=0.3)
        
        data = updater.to_dict()
        
        assert data["prior"] == 0.6
        assert data["evidence_count"] == 1
        assert data["mvp11_context"] is not None
    
    def test_aggregate_evidence_v2_function(self):
        """Test convenience function."""
        result = aggregate_evidence_v2(
            evidence_items=[
                {"type": "workspace", "value": 0.7, "strength": 0.8},
                {"type": "hot", "value": 0.6, "strength": 0.7},
            ],
            prior=0.5,
            efe_terms={"risk": 0.3, "ambiguity": 0.2, "info_gain": 0.5, "cost": 0.2},
        )
        
        assert "bayes_result" in result
        assert "uncertainty_report" in result
        assert result["bayes_result"]["posterior"] > 0.0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_extreme_evidence_values(self):
        """Test with extreme evidence values."""
        updater = BayesUpdaterV2()
        updater.add_evidence(EvidenceType.WORKSPACE, 1.0, strength=1.0)
        result = updater.compute_posterior()
        
        assert 0.0 < result.posterior < 1.0  # Should be clamped
    
    def test_zero_strength_evidence(self):
        """Test with zero strength evidence."""
        updater = BayesUpdaterV2()
        updater.add_evidence(EvidenceType.WORKSPACE, 0.9, strength=0.0)
        result = updater.compute_posterior()
        
        # Should have minimal effect
        assert abs(result.posterior - 0.5) < 0.1
    
    def test_conflicting_evidence(self):
        """Test with conflicting evidence."""
        updater = BayesUpdaterV2()
        updater.add_evidence(EvidenceType.WORKSPACE, 0.9, strength=0.9)
        updater.add_evidence(EvidenceType.WORKSPACE, 0.1, strength=0.9)
        result = updater.compute_posterior()
        report = updater.get_uncertainty_report()
        
        # Conflicting evidence should increase uncertainty
        assert report.evidence_uncertainty > 0.2
    
    def test_reset_clears_state(self):
        """Test that reset clears all state."""
        updater = BayesUpdaterV2()
        updater.add_evidence(EvidenceType.WORKSPACE, 0.7, strength=0.8)
        updater.set_efe_terms(risk=0.3, ambiguity=0.2, info_gain=0.5, cost=0.2)
        updater.reset()
        
        assert len(updater.evidence) == 0
        assert updater._mvp11_context is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
