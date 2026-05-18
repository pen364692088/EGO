"""
MVP11-T16: Test Precision Effect Interventions

Tests for freeze_precision and disable_info_gain interventions.

These interventions are used to test causal pathways:
- freeze_precision -> precision weights frozen, no context adaptation
- disable_info_gain -> info_gain_weight = 0, no exploration bonus
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch

from emotiond.science.interventions import (
    InterventionType,
    InterventionManager,
    FreezePrecisionIntervention,
    DisableInfoGainIntervention,
    create_freeze_precision_intervention,
    create_disable_info_gain_intervention,
    run_with_precision_frozen,
    run_with_info_gain_disabled,
)


class TestFreezePrecisionIntervention:
    """Tests for freeze_precision intervention."""
    
    def test_intervention_type_registered(self):
        """FREEZE_PRECISION is a valid intervention type."""
        assert InterventionType.FREEZE_PRECISION.value == "freeze_precision"
    
    def test_intervention_manager_detects_frozen_precision(self):
        """InterventionManager correctly detects frozen precision."""
        manager = InterventionManager()
        
        # Initially not frozen
        assert not manager.is_precision_frozen()
        
        # Enable the intervention
        manager.enable(InterventionType.FREEZE_PRECISION, params={"precision_weights": {"w_external": 0.5}})
        
        # Now frozen
        assert manager.is_precision_frozen()
    
    def test_freeze_precision_class_creation(self):
        """FreezePrecisionIntervention can be created."""
        intervention = FreezePrecisionIntervention()
        assert intervention.is_active()
    
    def test_freeze_precision_with_custom_weights(self):
        """FreezePrecisionIntervention can freeze specific weights."""
        custom_weights = {
            "w_external": 0.6,
            "w_internal": 0.25,
            "w_memory": 0.15,
            "w_action": 0.7,
            "w_explore": 0.2,
        }
        intervention = FreezePrecisionIntervention(precision_weights=custom_weights)
        
        frozen = intervention.get_frozen_precision()
        assert frozen == custom_weights
    
    def test_freeze_precision_default_weights(self):
        """FreezePrecisionIntervention has default weights if not specified."""
        intervention = FreezePrecisionIntervention()
        
        frozen = intervention.get_frozen_precision()
        assert "w_external" in frozen
        assert "w_internal" in frozen
        assert "w_memory" in frozen
        assert "w_action" in frozen
        assert "w_explore" in frozen
    
    def test_freeze_precision_applied_in_apply_intervention(self):
        """FREEZE_PRECISION is applied in apply_intervention()."""
        manager = InterventionManager()
        manager.enable(InterventionType.FREEZE_PRECISION)
        
        result = manager.apply_intervention(valence=0.5)
        
        assert result.get("precision_frozen") is True
        assert "freeze_precision" in result.get("interventions_applied", [])
    
    def test_freeze_precision_bypasses_dynamic_computation(self):
        """Frozen precision bypasses dynamic weight computation."""
        intervention = FreezePrecisionIntervention()
        
        # Mock precision controller
        mock_controller = Mock()
        mock_controller.compute_weights.return_value = (
            Mock(to_dict=lambda: {"w_external": 0.9, "w_internal": 0.05, "w_memory": 0.05}),
            ["dynamic reasoning"]
        )
        
        # Mock context
        mock_context = Mock()
        
        # Apply intervention
        result = intervention.apply_to_precision_controller(mock_controller, mock_context)
        
        # Should return frozen weights, not computed
        assert result["frozen"] is True
        assert result["weights"] == intervention.get_frozen_precision()
        assert "frozen" in result["reasoning"][0].lower()
    
    def test_freeze_precision_allows_computation_when_inactive(self):
        """When not active, precision computation proceeds normally."""
        intervention = FreezePrecisionIntervention()
        intervention.manager.disable(InterventionType.FREEZE_PRECISION)
        
        assert not intervention.is_active()
        
        # Mock precision controller
        mock_controller = Mock()
        expected_weights = {"w_external": 0.9, "w_internal": 0.05, "w_memory": 0.05}
        mock_controller.compute_weights.return_value = (
            Mock(to_dict=lambda: expected_weights),
            ["dynamic reasoning"]
        )
        
        mock_context = Mock()
        result = intervention.apply_to_precision_controller(mock_controller, mock_context)
        
        # Should compute normally
        assert result["frozen"] is False
        mock_controller.compute_weights.assert_called_once_with(mock_context)
    
    def test_factory_function(self):
        """Factory function creates valid intervention."""
        custom_weights = {"w_external": 0.5, "w_internal": 0.3, "w_memory": 0.2}
        intervention = create_freeze_precision_intervention(
            precision_weights=custom_weights,
            reason="test_causal"
        )
        
        assert intervention.is_active()
        assert intervention.to_dict()["is_active"] is True
        assert intervention.get_frozen_precision() == custom_weights


class TestDisableInfoGainIntervention:
    """Tests for disable_info_gain intervention."""
    
    def test_intervention_type_registered(self):
        """DISABLE_INFO_GAIN is a valid intervention type."""
        assert InterventionType.DISABLE_INFO_GAIN.value == "disable_info_gain"
    
    def test_intervention_manager_detects_disabled_info_gain(self):
        """InterventionManager correctly detects disabled info gain."""
        manager = InterventionManager()
        
        # Initially not disabled
        assert not manager.is_info_gain_disabled()
        
        # Enable the intervention
        manager.enable(InterventionType.DISABLE_INFO_GAIN)
        
        # Now disabled
        assert manager.is_info_gain_disabled()
    
    def test_disable_info_gain_class_creation(self):
        """DisableInfoGainIntervention can be created."""
        intervention = DisableInfoGainIntervention()
        assert intervention.is_active()
    
    def test_disable_info_gain_sets_weight_to_zero(self):
        """DisableInfoGainIntervention sets info_gain_weight to 0."""
        intervention = DisableInfoGainIntervention()
        
        policy_params = {
            "risk_weight": 1.0,
            "ambiguity_weight": 1.0,
            "info_gain_weight": 1.5,  # Normal value
            "cost_weight": 1.0,
        }
        
        modified = intervention.apply_to_policy_params(policy_params)
        
        assert modified["info_gain_weight"] == 0.0
        assert modified["risk_weight"] == 1.0  # Unchanged
    
    def test_disable_info_gain_applied_in_apply_intervention(self):
        """DISABLE_INFO_GAIN is applied in apply_intervention()."""
        manager = InterventionManager()
        manager.enable(InterventionType.DISABLE_INFO_GAIN)
        
        result = manager.apply_intervention(valence=0.5)
        
        assert result.get("info_gain_disabled") is True
        assert result.get("info_gain_weight") == 0.0
        assert "disable_info_gain" in result.get("interventions_applied", [])
    
    def test_disable_info_gain_affects_efe_computation(self):
        """Disabled info_gain affects EFE computation."""
        intervention = DisableInfoGainIntervention()
        
        # Mock EFE terms
        mock_efe = Mock()
        mock_efe.compute_efe = lambda params: (
            params.get("risk_weight", 1.0) * 0.5 +
            params.get("ambiguity_weight", 1.0) * 0.5 -
            params.get("info_gain_weight", 1.0) * 0.5 +
            params.get("cost_weight", 1.0) * 0.5
        )
        
        policy_params = {
            "risk_weight": 1.0,
            "ambiguity_weight": 1.0,
            "info_gain_weight": 1.5,
            "cost_weight": 1.0,
        }
        
        # Normal computation
        normal_efe = mock_efe.compute_efe(policy_params)
        
        # With intervention
        result = intervention.apply_to_efe_computation(mock_efe, policy_params)
        
        assert result["disabled"] is True
        assert result["info_gain_weight"] == 0.0
        # EFE should be higher (worse) without info_gain reduction
        assert result["efe_value"] > normal_efe
    
    def test_disable_info_gain_allows_normal_when_inactive(self):
        """When not active, EFE computation proceeds normally."""
        intervention = DisableInfoGainIntervention()
        intervention.manager.disable(InterventionType.DISABLE_INFO_GAIN)
        
        assert not intervention.is_active()
        
        policy_params = {"info_gain_weight": 1.5}
        
        result = intervention.apply_to_policy_params(policy_params)
        
        # Should not modify
        assert result["info_gain_weight"] == 1.5
    
    def test_factory_function(self):
        """Factory function creates valid intervention."""
        intervention = create_disable_info_gain_intervention(reason="test_causal")
        
        assert intervention.is_active()
        assert intervention.to_dict()["is_active"] is True


class TestPrecisionEffectInterventionComparison:
    """Integration tests comparing enabled vs disabled/frozen states."""
    
    def test_freeze_precision_comparison(self):
        """FreezePrecisionIntervention shows reduced context adaptation."""
        intervention = FreezePrecisionIntervention()
        
        # Define a simple run function
        def run_func(scenario, precision_frozen=False, **kwargs):
            # Simulate: without freeze, weights adapt to scenario
            if precision_frozen:
                return {
                    "primary_source": "external",
                    "selected_action": "approach",
                    "precision_weights": kwargs.get("precision_weights", {}),
                }
            else:
                # Adaptive: different scenarios get different weights
                if scenario == "high_threat":
                    return {
                        "primary_source": "internal",
                        "selected_action": "withdraw",
                        "precision_weights": {"w_external": 0.2, "w_internal": 0.5},
                    }
                else:
                    return {
                        "primary_source": "external",
                        "selected_action": "approach",
                        "precision_weights": {"w_external": 0.5, "w_internal": 0.2},
                    }
        
        result = intervention.run_comparison(
            run_func,
            scenarios=["high_threat", "low_threat"]
        )
        
        assert "scenarios" in result
        assert len(result["scenarios"]) == 2
        assert result["intervention"] == "freeze_precision"
    
    def test_disable_info_gain_comparison(self):
        """DisableInfoGainIntervention shows reduced exploration."""
        intervention = DisableInfoGainIntervention()
        
        def run_func(scenario, info_gain_disabled=False, **kwargs):
            if info_gain_disabled:
                return {
                    "selected_action": "exploit",
                    "explored": False,
                }
            else:
                return {
                    "selected_action": "explore",
                    "explored": True,
                }
        
        result = intervention.run_comparison(
            run_func,
            scenarios=["uncertain", "ambiguous"]
        )
        
        assert "scenarios" in result
        assert result["intervention"] == "disable_info_gain"
        # With info_gain disabled, should show less exploration
        assert result["separation"]["uncertain"]["enabled_explored"] is True
        assert result["separation"]["uncertain"]["disabled_explored"] is False
    
    def test_both_interventions_can_be_active(self):
        """Both freeze_precision and disable_info_gain can be active."""
        manager = InterventionManager()
        
        # Enable both
        manager.enable(InterventionType.FREEZE_PRECISION)
        manager.enable(InterventionType.DISABLE_INFO_GAIN)
        
        # Both should be detected
        assert manager.is_precision_frozen()
        assert manager.is_info_gain_disabled()
        
        # apply_intervention should mark both
        result = manager.apply_intervention(valence=0.5)
        assert "freeze_precision" in result.get("interventions_applied", [])
        assert "disable_info_gain" in result.get("interventions_applied", [])


class TestPrecisionEffectInterventionEdgeCases:
    """Edge case tests for precision effect interventions."""
    
    def test_freeze_precision_without_weights(self):
        """FreezePrecisionIntervention works without explicit weights."""
        intervention = FreezePrecisionIntervention(precision_weights=None)
        
        assert intervention.is_active()
        assert intervention.get_frozen_precision() is not None
    
    def test_disable_info_gain_multiple_enable_disable_cycles(self):
        """Interventions can be enabled/disabled multiple times."""
        manager = InterventionManager()
        
        for _ in range(3):
            manager.enable(InterventionType.FREEZE_PRECISION)
            assert manager.is_precision_frozen()
            
            manager.disable(InterventionType.FREEZE_PRECISION)
            assert not manager.is_precision_frozen()
    
    def test_intervention_history_tracking(self):
        """Intervention history is tracked correctly."""
        manager = InterventionManager()
        
        # Enable
        result = manager.enable(InterventionType.DISABLE_INFO_GAIN)
        assert result.success
        assert result.intervention_type == InterventionType.DISABLE_INFO_GAIN
        
        # Disable
        result = manager.disable(InterventionType.DISABLE_INFO_GAIN)
        assert result.success
        
        # Check history
        history = manager.get_history()
        assert len(history) == 2
    
    def test_intervention_clear_all(self):
        """clear_all removes all interventions including precision ones."""
        manager = InterventionManager()
        
        manager.enable(InterventionType.FREEZE_PRECISION)
        manager.enable(InterventionType.DISABLE_INFO_GAIN)
        manager.enable(InterventionType.DISABLE_HOT)
        
        manager.clear_all()
        
        assert not manager.is_precision_frozen()
        assert not manager.is_info_gain_disabled()
        assert not manager.is_hot_disabled()
    
    def test_run_with_precision_frozen_helper(self):
        """run_with_precision_frozen helper function works."""
        def simple_run(precision_frozen=False, **kwargs):
            return {"frozen": precision_frozen}
        
        result = run_with_precision_frozen(simple_run)
        
        assert result["result"]["frozen"] is True
        assert "intervention" in result
    
    def test_run_with_info_gain_disabled_helper(self):
        """run_with_info_gain_disabled helper function works."""
        def simple_run(info_gain_disabled=False, **kwargs):
            return {"disabled": info_gain_disabled}
        
        result = run_with_info_gain_disabled(simple_run)
        
        assert result["result"]["disabled"] is True
        assert "intervention" in result
