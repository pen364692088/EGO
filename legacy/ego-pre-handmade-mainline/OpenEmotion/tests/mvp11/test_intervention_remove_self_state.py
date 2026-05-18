"""
MVP11-T16: Test Remove Self State Intervention

Tests for remove_self_state intervention where self-state (self-model)
is set to constant/null.

This intervention is used to test causal pathways:
- remove_self_state -> self-referential influence removed
- Tests self-model effect on decision-making
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch

from emotiond.science.interventions import (
    InterventionType,
    InterventionManager,
    RemoveSelfStateIntervention,
    create_remove_self_state_intervention,
    run_with_self_state_removed,
)


class TestRemoveSelfStateIntervention:
    """Tests for remove_self_state intervention."""
    
    def test_intervention_type_registered(self):
        """REMOVE_SELF_STATE is a valid intervention type."""
        assert InterventionType.REMOVE_SELF_STATE.value == "remove_self_state"
    
    def test_intervention_manager_detects_self_state_removed(self):
        """InterventionManager correctly detects removed self state."""
        manager = InterventionManager()
        
        # Initially not removed
        assert not manager.is_self_state_removed()
        
        # Enable the intervention
        manager.enable(InterventionType.REMOVE_SELF_STATE)
        
        # Now removed
        assert manager.is_self_state_removed()
    
    def test_remove_self_state_class_creation(self):
        """RemoveSelfStateIntervention can be created."""
        intervention = RemoveSelfStateIntervention()
        assert intervention.is_active()
    
    def test_remove_self_state_with_constant_state(self):
        """RemoveSelfStateIntervention can use custom constant state."""
        constant_state = {
            "energy": 0.5,
            "safety": 0.5,
            "certainty": 0.5,
            "autonomy": 0.5,
        }
        intervention = RemoveSelfStateIntervention(constant_state=constant_state)
        
        assert intervention.is_active()
        assert intervention.get_constant_state() == constant_state
    
    def test_remove_self_state_default_is_empty(self):
        """RemoveSelfStateIntervention defaults to empty/null state."""
        intervention = RemoveSelfStateIntervention()
        
        state = intervention.get_constant_state()
        
        # Default is empty dict (null/removed)
        assert state == {}
    
    def test_remove_self_state_applied_in_apply_intervention(self):
        """REMOVE_SELF_STATE is applied in apply_intervention()."""
        manager = InterventionManager()
        manager.enable(InterventionType.REMOVE_SELF_STATE)
        
        result = manager.apply_intervention(valence=0.5)
        
        assert result.get("self_state_removed") is True
        assert "remove_self_state" in result.get("interventions_applied", [])
    
    def test_remove_self_state_replaces_self_model(self):
        """Self-model is replaced with constant state."""
        constant_state = {"energy": 0.5, "safety": 0.5}
        intervention = RemoveSelfStateIntervention(constant_state=constant_state)
        
        # Full self-model with varied values
        self_model = {
            "energy": 0.8,
            "safety": 0.3,
            "certainty": 0.9,
            "autonomy": 0.4,
            "affiliation": 0.7,
        }
        
        result = intervention.apply_to_self_model(self_model)
        
        # Should return constant state, not original
        assert result == constant_state
    
    def test_remove_self_state_allows_normal_when_inactive(self):
        """When not active, self-model is unchanged."""
        intervention = RemoveSelfStateIntervention()
        intervention.manager.disable(InterventionType.REMOVE_SELF_STATE)
        
        assert not intervention.is_active()
        
        self_model = {"energy": 0.8, "safety": 0.3}
        
        result = intervention.apply_to_self_model(self_model)
        
        # Should return original
        assert result == self_model
    
    def test_remove_self_state_affects_hot_state(self):
        """Self-state removal affects HOT (Higher-Order Thought) state."""
        intervention = RemoveSelfStateIntervention()
        
        hot_state = {
            "conflict_bias": 0.3,
            "control_penalty": 0.2,
            "self_energy": 0.5,
            "self_safety": 0.6,
            "self_certainty": 0.7,
        }
        
        result = intervention.apply_to_hot_state(hot_state)
        
        # Self-referential fields should be nullified
        assert result["self_state_removed"] is True
        assert "self_energy" in result
        assert "self_safety" in result
    
    def test_remove_self_state_affects_arbitration(self):
        """Self-state removal affects workspace arbitration."""
        intervention = RemoveSelfStateIntervention()
        
        arbitration_state = {
            "valence": 0.5,
            "uncertainty": 0.3,
            "self_state": {"energy": 0.8, "safety": 0.4},
            "candidates": [],
        }
        
        result = intervention.apply_to_arbitration(arbitration_state)
        
        assert result["self_reference_blocked"] is True
        assert result["self_state"] == intervention.get_constant_state()
    
    def test_factory_function(self):
        """Factory function creates valid intervention."""
        constant_state = {"energy": 0.5, "safety": 0.5}
        intervention = create_remove_self_state_intervention(
            constant_state=constant_state,
            reason="test_causal"
        )
        
        assert intervention.is_active()
        assert intervention.to_dict()["is_active"] is True
        assert intervention.get_constant_state() == constant_state


class TestRemoveSelfStateInterventionComparison:
    """Integration tests comparing self-state present vs removed modes."""
    
    def test_comparison_shows_no_self_influence(self):
        """RemoveSelfStateIntervention shows no self-referential influence."""
        intervention = RemoveSelfStateIntervention()
        
        def run_func(scenario, self_state_removed=False, **kwargs):
            if self_state_removed:
                return {
                    "selected_action": "self_agnostic_action",
                    "reflected": False,
                }
            else:
                return {
                    "selected_action": "self_referential_action",
                    "reflected": True,
                }
        
        result = intervention.run_comparison(
            run_func,
            scenarios=["conflict", "uncertainty"]
        )
        
        assert "scenarios" in result
        assert result["intervention"] == "remove_self_state"
        assert result["separation"]["conflict"]["with_self_reflection"] is True
        assert result["separation"]["conflict"]["without_self_reflection"] is False
    
    def test_comparison_with_other_interventions(self):
        """Remove self-state can be combined with other interventions."""
        manager = InterventionManager()
        
        manager.enable(InterventionType.REMOVE_SELF_STATE)
        manager.enable(InterventionType.OPEN_LOOP)
        
        assert manager.is_self_state_removed()
        assert manager.is_open_loop()
        
        result = manager.apply_intervention(valence=0.5)
        assert "remove_self_state" in result.get("interventions_applied", [])
        assert "open_loop" in result.get("interventions_applied", [])
    
    def test_remove_self_state_and_disable_hot_together(self):
        """Remove self-state and disable HOT can both be active."""
        manager = InterventionManager()
        
        manager.enable(InterventionType.REMOVE_SELF_STATE)
        manager.enable(InterventionType.DISABLE_HOT)
        
        assert manager.is_self_state_removed()
        assert manager.is_hot_disabled()


class TestRemoveSelfStateInterventionEdgeCases:
    """Edge case tests for remove_self_state intervention."""
    
    def test_remove_self_state_without_constant_state(self):
        """RemoveSelfStateIntervention works without explicit state."""
        intervention = RemoveSelfStateIntervention(constant_state=None)
        
        assert intervention.is_active()
        assert intervention.get_constant_state() == {}
    
    def test_remove_self_state_with_empty_dict(self):
        """Empty dict means null/removed state."""
        intervention = RemoveSelfStateIntervention(constant_state={})
        
        self_model = {"energy": 0.9, "safety": 0.8}
        result = intervention.apply_to_self_model(self_model)
        
        assert result == {}
    
    def test_remove_self_state_multiple_enable_disable_cycles(self):
        """Intervention can be enabled/disabled multiple times."""
        manager = InterventionManager()
        
        for _ in range(3):
            manager.enable(InterventionType.REMOVE_SELF_STATE)
            assert manager.is_self_state_removed()
            
            manager.disable(InterventionType.REMOVE_SELF_STATE)
            assert not manager.is_self_state_removed()
    
    def test_remove_self_state_intervention_history_tracking(self):
        """Intervention history is tracked correctly."""
        manager = InterventionManager()
        
        result = manager.enable(InterventionType.REMOVE_SELF_STATE)
        assert result.success
        assert result.intervention_type == InterventionType.REMOVE_SELF_STATE
        
        result = manager.disable(InterventionType.REMOVE_SELF_STATE)
        assert result.success
        
        history = manager.get_history()
        assert len(history) == 2
    
    def test_remove_self_state_clear_all(self):
        """clear_all removes remove_self_state intervention."""
        manager = InterventionManager()
        
        manager.enable(InterventionType.REMOVE_SELF_STATE)
        manager.enable(InterventionType.FREEZE_PRECISION)
        
        manager.clear_all()
        
        assert not manager.is_self_state_removed()
        assert not manager.is_precision_frozen()
    
    def test_remove_self_state_to_dict_serialization(self):
        """RemoveSelfStateIntervention serializes correctly."""
        constant_state = {"energy": 0.5, "safety": 0.5}
        intervention = RemoveSelfStateIntervention(constant_state=constant_state)
        
        data = intervention.to_dict()
        
        assert data["is_active"] is True
        assert data["constant_state"] == constant_state
        assert "enabled_at" in data
    
    def test_run_with_self_state_removed_helper(self):
        """run_with_self_state_removed helper function works."""
        def simple_run(self_state_removed=False, **kwargs):
            return {"removed": self_state_removed}
        
        result = run_with_self_state_removed(simple_run)
        
        assert result["result"]["removed"] is True
        assert "intervention" in result
    
    def test_remove_self_state_with_partial_constant(self):
        """RemoveSelfStateIntervention handles partial constant states."""
        # Only some dimensions specified
        partial_state = {"energy": 0.5}
        
        intervention = RemoveSelfStateIntervention(constant_state=partial_state)
        
        self_model = {
            "energy": 0.8,
            "safety": 0.3,
            "certainty": 0.9,
        }
        
        result = intervention.apply_to_self_model(self_model)
        
        # Should return the partial constant
        assert result == partial_state
    
    def test_get_constant_self_state_from_manager(self):
        """InterventionManager.get_constant_self_state returns correct value."""
        manager = InterventionManager()
        
        constant_state = {"energy": 0.6, "safety": 0.6}
        manager.enable(
            InterventionType.REMOVE_SELF_STATE,
            params={"constant_state": constant_state}
        )
        
        result = manager.get_constant_self_state()
        
        assert result == constant_state
    
    def test_get_constant_self_state_when_not_active(self):
        """InterventionManager.get_constant_self_state returns None if not active."""
        manager = InterventionManager()
        
        result = manager.get_constant_self_state()
        
        assert result is None
