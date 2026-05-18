"""
MVP11-T16: Test Open Loop Intervention

Tests for open_loop intervention where actions don't affect
future observations or costs.

This intervention is used to test causal pathways:
- open_loop -> actions don't affect future state
- Tests action-consequence learning
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch

from emotiond.science.interventions import (
    InterventionType,
    InterventionManager,
    OpenLoopIntervention,
    create_open_loop_intervention,
    run_with_open_loop,
)


class TestOpenLoopIntervention:
    """Tests for open_loop intervention."""
    
    def test_intervention_type_registered(self):
        """OPEN_LOOP is a valid intervention type."""
        assert InterventionType.OPEN_LOOP.value == "open_loop"
    
    def test_intervention_manager_detects_open_loop(self):
        """InterventionManager correctly detects open loop mode."""
        manager = InterventionManager()
        
        # Initially not active
        assert not manager.is_open_loop()
        
        # Enable the intervention
        manager.enable(InterventionType.OPEN_LOOP)
        
        # Now active
        assert manager.is_open_loop()
    
    def test_open_loop_class_creation(self):
        """OpenLoopIntervention can be created."""
        intervention = OpenLoopIntervention()
        assert intervention.is_active()
    
    def test_open_loop_with_constant_outcome(self):
        """OpenLoopIntervention can use custom constant outcome."""
        constant_outcome = {
            "status": "neutral",
            "reward": 0.0,
            "state_change": None,
        }
        intervention = OpenLoopIntervention(constant_outcome=constant_outcome)
        
        assert intervention.is_active()
    
    def test_open_loop_default_outcome(self):
        """OpenLoopIntervention has default outcome if not specified."""
        intervention = OpenLoopIntervention()
        
        result = intervention.simulate_open_loop(
            action={"type": "approach"},
            intended_outcome={"status": "success", "reward": 1.0},
        )
        
        # Should return default constant outcome
        assert "status" in result
    
    def test_open_loop_applied_in_apply_intervention(self):
        """OPEN_LOOP is applied in apply_intervention()."""
        manager = InterventionManager()
        manager.enable(InterventionType.OPEN_LOOP)
        
        result = manager.apply_intervention(valence=0.5)
        
        assert result.get("open_loop") is True
        assert "open_loop" in result.get("interventions_applied", [])
    
    def test_open_loop_returns_constant_outcome(self):
        """Open loop mode returns constant outcome regardless of action."""
        constant_outcome = {"status": "neutral", "reward": 0.0}
        intervention = OpenLoopIntervention(constant_outcome=constant_outcome)
        
        # Try different actions
        actions = [
            {"type": "approach"},
            {"type": "withdraw"},
            {"type": "attack"},
        ]
        
        intended_outcomes = [
            {"status": "success", "reward": 1.0},
            {"status": "safe", "reward": 0.5},
            {"status": "risky", "reward": -0.5},
        ]
        
        for action, intended in zip(actions, intended_outcomes):
            result = intervention.simulate_open_loop(action, intended)
            
            # Should return constant outcome, not intended
            assert result["status"] == "neutral"
            assert result["reward"] == 0.0
    
    def test_open_loop_allows_normal_when_inactive(self):
        """When not active, intended outcome is returned."""
        intervention = OpenLoopIntervention()
        intervention.manager.disable(InterventionType.OPEN_LOOP)
        
        assert not intervention.is_active()
        
        action = {"type": "approach"}
        intended = {"status": "success", "reward": 1.0}
        
        result = intervention.simulate_open_loop(action, intended)
        
        # Should return intended outcome
        assert result == intended
    
    def test_open_loop_tracks_action_history(self):
        """OpenLoopIntervention tracks history of actions."""
        intervention = OpenLoopIntervention()
        
        # Simulate multiple actions
        for i in range(3):
            intervention.simulate_open_loop(
                action={"type": f"action_{i}"},
                intended_outcome={"status": "success", "reward": i},
            )
        
        history = intervention.get_action_history()
        
        assert len(history) == 3
        assert history[0]["action"]["type"] == "action_0"
        assert history[2]["action"]["type"] == "action_2"
    
    def test_open_loop_state_update_blocked(self):
        """State update is blocked in open loop mode."""
        intervention = OpenLoopIntervention()
        
        initial_state = {"energy": 0.5, "safety": 0.6}
        action = {"type": "costly_action", "cost": 0.2}
        
        result = intervention.apply_to_state_update(initial_state, action)
        
        # State should be unchanged
        assert result == initial_state
    
    def test_open_loop_efe_cost_reduced(self):
        """EFE cost is reduced in open loop mode (no compounding)."""
        intervention = OpenLoopIntervention()
        
        # Mock EFE terms
        mock_efe = Mock()
        mock_efe.risk = 0.5
        mock_efe.ambiguity = 0.3
        mock_efe.info_gain = 0.4
        mock_efe.cost = 0.8
        
        action = {"type": "expensive_action"}
        
        result = intervention.compute_efe_open_loop(mock_efe, action)
        
        assert result["open_loop"] is True
        assert result["original_cost"] == 0.8
        assert result["modified_cost"] < 0.8  # Reduced in open loop
    
    def test_factory_function(self):
        """Factory function creates valid intervention."""
        constant_outcome = {"status": "test", "reward": 0.5}
        intervention = create_open_loop_intervention(
            constant_outcome=constant_outcome,
            reason="test_causal"
        )
        
        assert intervention.is_active()
        assert intervention.to_dict()["is_active"] is True


class TestOpenLoopInterventionComparison:
    """Integration tests comparing closed vs open loop modes."""
    
    def test_comparison_shows_no_action_effect(self):
        """OpenLoopIntervention shows actions don't affect outcomes."""
        intervention = OpenLoopIntervention()
        
        def run_func(scenario, open_loop=False, **kwargs):
            if open_loop:
                return {
                    "selected_action": "same_action",
                    "state_changes": 0,
                    "outcome": "neutral",
                }
            else:
                return {
                    "selected_action": "context_dependent_action",
                    "state_changes": 2,
                    "outcome": "varied",
                }
        
        result = intervention.run_comparison(
            run_func,
            scenarios=["scenario_a", "scenario_b"]
        )
        
        assert "scenarios" in result
        assert result["intervention"] == "open_loop"
        assert result["separation"]["scenario_a"]["closed_state_changes"] == 2
        assert result["separation"]["scenario_a"]["open_state_changes"] == 0
    
    def test_comparison_with_other_interventions(self):
        """Open loop can be combined with other interventions."""
        manager = InterventionManager()
        
        manager.enable(InterventionType.OPEN_LOOP)
        manager.enable(InterventionType.DISABLE_HOT)
        
        assert manager.is_open_loop()
        assert manager.is_hot_disabled()
        
        result = manager.apply_intervention(valence=0.5)
        assert "open_loop" in result.get("interventions_applied", [])
        assert "disable_hot" in result.get("interventions_applied", [])


class TestOpenLoopInterventionEdgeCases:
    """Edge case tests for open_loop intervention."""
    
    def test_open_loop_without_constant_outcome(self):
        """OpenLoopIntervention works without explicit outcome."""
        intervention = OpenLoopIntervention(constant_outcome=None)
        
        assert intervention.is_active()
        
        result = intervention.simulate_open_loop(
            action={"type": "test"},
            intended_outcome={"status": "success"},
        )
        
        assert "status" in result  # Has default
    
    def test_open_loop_multiple_enable_disable_cycles(self):
        """Intervention can be enabled/disabled multiple times."""
        manager = InterventionManager()
        
        for _ in range(3):
            manager.enable(InterventionType.OPEN_LOOP)
            assert manager.is_open_loop()
            
            manager.disable(InterventionType.OPEN_LOOP)
            assert not manager.is_open_loop()
    
    def test_open_loop_intervention_history_tracking(self):
        """Intervention history is tracked correctly."""
        manager = InterventionManager()
        
        result = manager.enable(InterventionType.OPEN_LOOP)
        assert result.success
        assert result.intervention_type == InterventionType.OPEN_LOOP
        
        result = manager.disable(InterventionType.OPEN_LOOP)
        assert result.success
        
        history = manager.get_history()
        assert len(history) == 2
    
    def test_open_loop_clear_all(self):
        """clear_all removes open_loop intervention."""
        manager = InterventionManager()
        
        manager.enable(InterventionType.OPEN_LOOP)
        manager.enable(InterventionType.FREEZE_PRECISION)
        
        manager.clear_all()
        
        assert not manager.is_open_loop()
        assert not manager.is_precision_frozen()
    
    def test_open_loop_to_dict_serialization(self):
        """OpenLoopIntervention serializes correctly."""
        intervention = OpenLoopIntervention(
            constant_outcome={"status": "test", "reward": 0.5}
        )
        
        # Simulate some actions
        intervention.simulate_open_loop(
            action={"type": "test"},
            intended_outcome={"status": "intended"},
        )
        
        data = intervention.to_dict()
        
        assert data["is_active"] is True
        assert data["constant_outcome"]["status"] == "test"
        assert data["action_count"] == 1
    
    def test_run_with_open_loop_helper(self):
        """run_with_open_loop helper function works."""
        def simple_run(open_loop=False, **kwargs):
            return {"open_loop": open_loop}
        
        result = run_with_open_loop(simple_run)
        
        assert result["result"]["open_loop"] is True
        assert "intervention" in result
    
    def test_open_loop_with_complex_outcome(self):
        """OpenLoopIntervention handles complex constant outcomes."""
        complex_outcome = {
            "status": "success",
            "reward": 0.8,
            "side_effects": [],
            "state_delta": {},
            "metadata": {"reason": "open_loop_simulation"},
        }
        
        intervention = OpenLoopIntervention(constant_outcome=complex_outcome)
        
        result = intervention.simulate_open_loop(
            action={"type": "complex_action"},
            intended_outcome={"status": "different", "reward": -0.5},
        )
        
        assert result["status"] == "success"
        assert result["reward"] == 0.8
        assert "metadata" in result
