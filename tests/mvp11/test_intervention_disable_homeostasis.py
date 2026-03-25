"""
MVP11-T06: Test Homeostasis Interventions

Tests for disable_homeostasis and freeze_homeostasis interventions.

These interventions are used to test causal pathways:
- disable_homeostasis -> recovery behavior collapse
- freeze_homeostasis -> state dependency verification
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch

from emotiond.science.interventions import (
    InterventionType,
    InterventionManager,
    DisableHomeostasisIntervention,
    FreezeHomeostasisIntervention,
    create_disable_homeostasis_intervention,
    create_freeze_homeostasis_intervention,
)
from emotiond.homeostasis import (
    HomeostasisManager,
    HomeostasisState,
    DEFAULT_SETPOINTS,
)


class TestDisableHomeostasisIntervention:
    """Tests for disable_homeostasis intervention."""
    
    def test_intervention_type_registered(self):
        """DISABLE_HOMEOSTASIS is a valid intervention type."""
        assert InterventionType.DISABLE_HOMEOSTASIS.value == "disable_homeostasis"
    
    def test_intervention_manager_detects_disabled(self):
        """InterventionManager correctly detects disabled homeostasis."""
        manager = InterventionManager()
        
        # Initially not disabled
        assert not manager.is_homeostasis_disabled()
        
        # Enable the intervention
        manager.enable(InterventionType.DISABLE_HOMEOSTASIS, params={"signal_enabled": False})
        
        # Now disabled
        assert manager.is_homeostasis_disabled()
    
    def test_disable_homeostasis_class_creation(self):
        """DisableHomeostasisIntervention can be created."""
        intervention = DisableHomeostasisIntervention()
        assert intervention.is_active()
        assert intervention.should_block_signal()
    
    def test_disable_homeostasis_blocks_signal(self):
        """When active, signal generation returns empty dict."""
        intervention = DisableHomeostasisIntervention()
        
        # Create a mock homeostasis manager
        mock_manager = Mock()
        mock_manager.signal.return_value = {
            "state": {"energy": 0.3},
            "deviation": {"energy": -0.45},
            "stressed_dimensions": [{"dimension": "energy", "deviation": -0.45}],
            "urgency": 0.45,
            "recommendations": [{"action": "rest"}],
        }
        
        # Apply intervention
        result = intervention.apply_to_manager(mock_manager)
        
        # Should return empty dict
        assert result == {}
        assert intervention.should_block_signal()
    
    def test_disable_homeostasis_allows_signal_when_inactive(self):
        """When not active, signal passes through."""
        intervention = DisableHomeostasisIntervention()
        intervention.manager.disable(InterventionType.DISABLE_HOMEOSTASIS)
        
        # Should not be active
        assert not intervention.is_active()
        
        # Create a mock manager with a signal
        mock_manager = Mock()
        expected_signal = {"state": {"energy": 0.5}, "urgency": 0.0}
        mock_manager.signal.return_value = expected_signal
        
        result = intervention.apply_to_manager(mock_manager)
        
        # Should return the normal signal
        assert result == expected_signal
    
    def test_recovery_actions_decrease_when_disabled(self):
        """Recovery actions decrease when homeostasis is disabled."""
        # Create a real HomeostasisManager in stressed state
        state = HomeostasisState(energy=0.2, safety=0.2)  # Low values
        hs_manager = HomeostasisManager(initial_state=state)
        
        # Normal mode: should have recovery candidates
        normal_signal = hs_manager.signal()
        normal_recovery_count = len(normal_signal.get("recommendations", []))
        assert normal_recovery_count > 0, "Stressed state should generate recovery actions"
        
        # Disabled mode: intervention returns empty signal
        intervention = DisableHomeostasisIntervention()
        disabled_signal = intervention.apply_to_manager(hs_manager)
        
        assert disabled_signal == {}
        assert len(disabled_signal.get("recommendations", [])) == 0
    
    def test_intervention_applied_in_apply_intervention(self):
        """DISABLE_HOMEOSTASIS is applied in apply_intervention()."""
        manager = InterventionManager()
        manager.enable(InterventionType.DISABLE_HOMEOSTASIS)
        
        result = manager.apply_intervention(valence=0.5)
        
        assert result.get("homeostasis_disabled") is True
        assert "disable_homeostasis" in result.get("interventions_applied", [])
    
    def test_factory_function(self):
        """Factory function creates valid intervention."""
        intervention = create_disable_homeostasis_intervention(reason="test_causal")
        
        assert intervention.is_active()
        assert intervention.to_dict()["is_active"] is True


class TestFreezeHomeostasisIntervention:
    """Tests for freeze_homeostasis intervention."""
    
    def test_intervention_type_registered(self):
        """FREEZE_HOMEOSTASIS is a valid intervention type."""
        assert InterventionType.FREEZE_HOMEOSTASIS.value == "freeze_homeostasis"
    
    def test_intervention_manager_detects_frozen(self):
        """InterventionManager correctly detects frozen homeostasis."""
        manager = InterventionManager()
        
        # Initially not frozen
        assert not manager.is_homeostasis_frozen()
        
        # Enable the intervention
        manager.enable(InterventionType.FREEZE_HOMEOSTASIS)
        
        # Now frozen
        assert manager.is_homeostasis_frozen()
    
    def test_freeze_homeostasis_class_creation(self):
        """FreezeHomeostasisIntervention can be created."""
        intervention = FreezeHomeostasisIntervention()
        assert intervention.is_active()
        assert intervention.should_skip_update()
    
    def test_freeze_homeostasis_with_initial_state(self):
        """FreezeHomeostasisIntervention can freeze specific state."""
        initial_state = {
            "energy": 0.8,
            "safety": 0.7,
            "affiliation": 0.5,
            "certainty": 0.6,
            "autonomy": 0.7,
            "fairness": 0.5,
        }
        intervention = FreezeHomeostasisIntervention(initial_state=initial_state)
        
        frozen = intervention.get_frozen_state()
        assert frozen == initial_state
    
    def test_freeze_prevents_update(self):
        """Frozen state prevents update_from_outcome from changing state."""
        # Create manager with initial state
        initial_state = HomeostasisState(energy=0.5, safety=0.5)
        hs_manager = HomeostasisManager(initial_state=initial_state)
        
        # Capture initial values
        initial_energy = hs_manager.state.energy
        
        # Apply freeze intervention
        intervention = FreezeHomeostasisIntervention()
        intervention.capture_state(hs_manager)
        
        # Try to apply an outcome that would normally change energy
        outcome = {"status": "fail", "reason": "resource_exhausted"}
        result = intervention.apply_to_outcome(hs_manager, outcome)
        
        # Update should be blocked
        assert result["frozen"] is True
        assert result["updated"] is False
        assert hs_manager.state.energy == initial_energy
    
    def test_freeze_allows_update_when_inactive(self):
        """When not frozen, updates proceed normally."""
        initial_state = HomeostasisState(energy=0.5)
        hs_manager = HomeostasisManager(initial_state=initial_state)
        
        # Create and disable intervention
        intervention = FreezeHomeostasisIntervention()
        intervention.manager.disable(InterventionType.FREEZE_HOMEOSTASIS)
        
        assert not intervention.is_active()
        
        # Apply outcome
        outcome = {"status": "fail", "reason": "resource_exhausted"}
        result = intervention.apply_to_outcome(hs_manager, outcome)
        
        # Update should proceed
        assert result["updated"] is True
        assert result["frozen"] is False
    
    def test_capture_state_from_manager(self):
        """Intervention can capture state from HomeostasisManager."""
        state = HomeostasisState(energy=0.3, safety=0.4, certainty=0.6)
        hs_manager = HomeostasisManager(initial_state=state)
        
        intervention = FreezeHomeostasisIntervention()
        captured = intervention.capture_state(hs_manager)
        
        assert captured["energy"] == 0.3
        assert captured["safety"] == 0.4
        assert captured["certainty"] == 0.6
    
    def test_intervention_applied_in_apply_intervention(self):
        """FREEZE_HOMEOSTASIS is applied in apply_intervention()."""
        manager = InterventionManager()
        manager.enable(InterventionType.FREEZE_HOMEOSTASIS)
        
        result = manager.apply_intervention(valence=0.5)
        
        assert result.get("homeostasis_frozen") is True
        assert "freeze_homeostasis" in result.get("interventions_applied", [])
    
    def test_factory_function(self):
        """Factory function creates valid intervention."""
        initial_state = {"energy": 0.5, "safety": 0.5}
        intervention = create_freeze_homeostasis_intervention(
            initial_state=initial_state,
            reason="test_freeze"
        )
        
        assert intervention.is_active()
        assert intervention.get_frozen_state() == initial_state


class TestHomeostasisInterventionComparison:
    """Integration tests comparing enabled vs disabled/frozen states."""
    
    def test_comparison_shows_recovery_collapse(self):
        """DisableHomeostasisIntervention shows recovery action collapse."""
        intervention = DisableHomeostasisIntervention()
        
        # Simulate stressed state
        stressed_state = HomeostasisState(energy=0.2, safety=0.3)
        hs_manager = HomeostasisManager(initial_state=stressed_state)
        
        # Normal signal should have recommendations
        normal_signal = hs_manager.signal()
        assert len(normal_signal.get("recommendations", [])) > 0
        
        # Disabled signal is empty
        disabled_signal = intervention.apply_to_manager(hs_manager)
        assert disabled_signal == {}
        
        # Verify collapse
        normal_count = len(normal_signal.get("recommendations", []))
        disabled_count = len(disabled_signal.get("recommendations", []))
        assert normal_count > disabled_count
    
    def test_comparison_shows_state_freeze(self):
        """FreezeHomeostasisIntervention prevents state changes."""
        # Start with known state
        initial_state = HomeostasisState(energy=0.5, safety=0.5)
        hs_manager = HomeostasisManager(initial_state=initial_state)
        
        # Create freeze intervention
        intervention = FreezeHomeostasisIntervention()
        intervention.capture_state(hs_manager)
        
        # Apply multiple outcomes
        outcomes = [
            {"status": "fail", "reason": "resource_exhausted"},
            {"status": "fail", "reason": "blocked"},
            {"status": "fail", "reason": "rejected"},
        ]
        
        for outcome in outcomes:
            result = intervention.apply_to_outcome(hs_manager, outcome)
            assert result["frozen"] is True
            assert result["updated"] is False
        
        # State should remain unchanged
        assert hs_manager.state.energy == 0.5
        assert hs_manager.state.safety == 0.5
    
    def test_both_interventions_can_be_active(self):
        """Both disable and freeze can be active simultaneously."""
        manager = InterventionManager()
        
        # Enable both
        manager.enable(InterventionType.DISABLE_HOMEOSTASIS)
        manager.enable(InterventionType.FREEZE_HOMEOSTASIS)
        
        # Both should be detected
        assert manager.is_homeostasis_disabled()
        assert manager.is_homeostasis_frozen()
        
        # apply_intervention should mark both
        result = manager.apply_intervention(valence=0.5)
        assert "disable_homeostasis" in result.get("interventions_applied", [])
        assert "freeze_homeostasis" in result.get("interventions_applied", [])


class TestHomeostasisInterventionEdgeCases:
    """Edge case tests for homeostasis interventions."""
    
    def test_disable_without_homeostasis_manager(self):
        """DisableHomeostasisIntervention works without manager reference."""
        intervention = DisableHomeostasisIntervention()
        
        # should_block_signal doesn't require a manager
        assert intervention.should_block_signal()
    
    def test_freeze_without_initial_state(self):
        """FreezeHomeostasisIntervention works without initial state."""
        intervention = FreezeHomeostasisIntervention(initial_state=None)
        
        assert intervention.is_active()
        assert intervention.get_frozen_state() is None
    
    def test_multiple_enable_disable_cycles(self):
        """Interventions can be enabled/disabled multiple times."""
        manager = InterventionManager()
        
        for _ in range(3):
            manager.enable(InterventionType.DISABLE_HOMEOSTASIS)
            assert manager.is_homeostasis_disabled()
            
            manager.disable(InterventionType.DISABLE_HOMEOSTASIS)
            assert not manager.is_homeostasis_disabled()
    
    def test_intervention_history_tracking(self):
        """Intervention history is tracked correctly."""
        manager = InterventionManager()
        
        # Enable
        result = manager.enable(InterventionType.DISABLE_HOMEOSTASIS)
        assert result.success
        assert result.intervention_type == InterventionType.DISABLE_HOMEOSTASIS
        
        # Disable
        result = manager.disable(InterventionType.DISABLE_HOMEOSTASIS)
        assert result.success
        
        # Check history
        history = manager.get_history()
        assert len(history) == 2
    
    def test_intervention_clear_all(self):
        """clear_all removes all interventions including homeostasis ones."""
        manager = InterventionManager()
        
        manager.enable(InterventionType.DISABLE_HOMEOSTASIS)
        manager.enable(InterventionType.FREEZE_HOMEOSTASIS)
        manager.enable(InterventionType.DISABLE_HOT)
        
        manager.clear_all()
        
        assert not manager.is_homeostasis_disabled()
        assert not manager.is_homeostasis_frozen()
        assert not manager.is_hot_disabled()
