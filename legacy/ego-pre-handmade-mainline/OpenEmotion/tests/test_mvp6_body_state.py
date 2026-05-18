"""
MVP-6 D1: Virtual Body State Vector Tests

Tests for:
- BodyStateDimension: value+uncertainty+last_updated
- BodyStateVector: 5 dimensions (energy, safety_stress, social_need, novelty_need, focus_fatigue)
- time_passed dynamics with configurable recovery constants
- Compatibility with existing energy_budget
- Update ranges, clamps, recovery/regression
- Cross-target ownership semantics
"""
import pytest
import time
import math
from dataclasses import dataclass

# Import body state module
from emotiond.body_state import (
    RecoveryDynamics,
    BodyStateDimension,
    BodyStateVector,
    get_body_state,
    set_body_state,
    reset_body_state,
    _global_body_state,
)


# ============================================================================
# BodyStateDimension Tests
# ============================================================================

class TestBodyStateDimension:
    """Tests for BodyStateDimension class"""
    
    def test_default_initialization(self):
        """Test default values on initialization"""
        dim = BodyStateDimension()
        assert dim.value == 0.5
        assert dim.uncertainty == 0.5
        assert dim.last_updated <= time.time()
        assert dim.recovery_rate == 0.001
        assert dim.regression_rate == 0.0005
        assert dim.baseline == 0.5
    
    def test_custom_initialization(self):
        """Test custom values on initialization"""
        from emotiond.body_state import RecoveryDynamics
        dim = BodyStateDimension(
            value=0.7,
            uncertainty=0.3,
            recovery_dynamics=RecoveryDynamics(recovery_rate=0.002, decay_rate=0.001),
            baseline=0.6
        )
        assert dim.value == 0.7
        assert dim.uncertainty == 0.3
        assert dim.recovery_rate == 0.002
        assert dim.decay_rate == 0.001
        assert dim.baseline == 0.6
    
    def test_clamp_on_initialization(self):
        """Test that values are clamped to [0, 1] on initialization"""
        dim = BodyStateDimension(value=1.5, uncertainty=-0.2)
        assert dim.value == 1.0
        assert dim.uncertainty == 0.0
    
    def test_update_positive_delta(self):
        """Test update with positive delta"""
        dim = BodyStateDimension(value=0.5)
        dim.update(0.2)
        assert dim.value == 0.7
        assert dim.uncertainty < 0.5  # Uncertainty should decrease
    
    def test_update_negative_delta(self):
        """Test update with negative delta"""
        dim = BodyStateDimension(value=0.5)
        dim.update(-0.2)
        assert dim.value == 0.3
    
    def test_update_clamps_upper(self):
        """Test that update clamps value to max 1.0"""
        dim = BodyStateDimension(value=0.9)
        dim.update(0.2)
        assert dim.value == 1.0
    
    def test_update_clamps_lower(self):
        """Test that update clamps value to min 0.0"""
        dim = BodyStateDimension(value=0.1)
        dim.update(-0.2)
        assert dim.value == 0.0
    
    def test_update_uncertainty_reduction(self):
        """Test that update reduces uncertainty"""
        dim = BodyStateDimension(uncertainty=0.8)
        dim.update(0.1)
        assert dim.uncertainty == 0.75  # 0.8 - 0.05
    
    def test_update_uncertainty_floor(self):
        """Test that uncertainty respects observation_uncertainty floor"""
        dim = BodyStateDimension(uncertainty=0.1)
        dim.update(0.1, observation_uncertainty=0.15)
        assert dim.uncertainty == 0.15  # Should not go below observation_uncertainty
    
    def test_set_value(self):
        """Test set_value method"""
        dim = BodyStateDimension()
        dim.set_value(0.8)
        assert dim.value == 0.8
    
    def test_set_value_with_uncertainty(self):
        """Test set_value with uncertainty"""
        dim = BodyStateDimension()
        dim.set_value(0.8, uncertainty=0.2)
        assert dim.value == 0.8
        assert dim.uncertainty == 0.2
    
    def test_apply_time_passed_recovery(self):
        """Test recovery when value is below baseline"""
        dim = BodyStateDimension(value=0.3, baseline=0.5, recovery_dynamics=RecoveryDynamics(recovery_rate=0.01))
        dim.apply_time_passed(10)  # 10 seconds
        assert dim.value > 0.3  # Should recover toward baseline
        assert dim.value <= 0.5  # Should not exceed baseline
    
    def test_apply_time_passed_regression(self):
        """Test regression when value is above baseline"""
        dim = BodyStateDimension(value=0.8, baseline=0.5, recovery_dynamics=RecoveryDynamics(decay_rate=0.01))
        dim.apply_time_passed(10)  # 10 seconds
        assert dim.value < 0.8  # Should regress toward baseline
        assert dim.value >= 0.5  # Should not go below baseline
    
    def test_apply_time_passed_uncertainty_growth(self):
        """Test that uncertainty grows over time"""
        dim = BodyStateDimension(uncertainty=0.1)
        dim.apply_time_passed(100)  # 100 seconds
        assert dim.uncertainty > 0.1  # Should grow
    
    def test_apply_time_passed_no_change_at_baseline(self):
        """Test that value stays at baseline"""
        dim = BodyStateDimension(value=0.5, baseline=0.5)
        dim.apply_time_passed(100)
        assert dim.value == 0.5
    
    def test_to_dict(self):
        """Test serialization to dict"""
        dim = BodyStateDimension(value=0.7, uncertainty=0.3)
        data = dim.to_dict()
        assert data["value"] == 0.7
        assert data["uncertainty"] == 0.3
        assert "last_updated" in data
        assert "recovery_dynamics" in data
    
    def test_from_dict(self):
        """Test deserialization from dict"""
        data = {
            "value": 0.8,
            "uncertainty": 0.2,
            "last_updated": time.time(),
            "recovery_dynamics": {
                "recovery_rate": 0.002,
                "decay_rate": 0.001,
                "half_life_seconds": 600.0
            },
            "baseline": 0.6
        }
        dim = BodyStateDimension.from_dict(data)
        assert dim.value == 0.8
        assert dim.uncertainty == 0.2
        assert dim.recovery_rate == 0.002
    
    def test_chaining(self):
        """Test method chaining"""
        dim = BodyStateDimension()
        result = dim.update(0.1).set_value(0.8).apply_time_passed(1)
        assert result is dim
        assert dim.value == pytest.approx(0.8, rel=1e-3)


# ============================================================================
# BodyStateVector Tests
# ============================================================================

class TestBodyStateVector:
    """Tests for BodyStateVector class"""
    
    def test_default_initialization(self):
        """Test default values for all 5 dimensions"""
        bsv = BodyStateVector()
        # Energy: baseline 0.7
        assert bsv.energy.value == 0.7
        assert bsv.energy.baseline == 0.7
        # Safety_stress: baseline 0.6
        assert bsv.safety_stress.value == 0.6
        assert bsv.safety_stress.baseline == 0.6
        # Social_need: baseline 0.5
        assert bsv.social_need.value == 0.5
        assert bsv.social_need.baseline == 0.5
        # Novelty_need: baseline 0.5
        assert bsv.novelty_need.value == 0.5
        assert bsv.novelty_need.baseline == 0.5
        # Focus_fatigue: baseline 0.3
        assert bsv.focus_fatigue.value == 0.3
        assert bsv.focus_fatigue.baseline == 0.3
    
    def test_custom_initialization(self):
        """Test custom dimension initialization"""
        energy = BodyStateDimension(value=0.9, uncertainty=0.1)
        bsv = BodyStateVector(energy=energy)
        assert bsv.energy.value == 0.9
        assert bsv.energy.uncertainty == 0.1
    
    def test_apply_time_passed_all_dimensions(self):
        """Test time dynamics on all dimensions"""
        bsv = BodyStateVector()
        # Set values away from baselines
        bsv.energy.value = 0.3  # Below baseline 0.7
        bsv.safety_stress.value = 0.2  # Below baseline 0.6
        bsv.focus_fatigue.value = 0.8  # Above baseline 0.3
        
        bsv.apply_time_passed(100)
        
        assert bsv.energy.value > 0.3  # Recovered
        assert bsv.safety_stress.value > 0.2  # Recovered
        assert bsv.focus_fatigue.value < 0.8  # Regressed
    
    def test_update_from_event_user_message(self):
        """Test update from user_message event"""
        bsv = BodyStateVector()
        initial_energy = bsv.energy.value
        initial_focus = bsv.focus_fatigue.value
        
        trace = bsv.update_from_event("user_message")
        deltas = trace["global_body_delta"]
        
        assert deltas["energy"] < 0  # Energy decreases
        assert deltas["focus_fatigue"] > 0  # Fatigue increases
        assert deltas["social_need"] < 0  # Social need decreases
        assert bsv.energy.value < initial_energy
        assert bsv.focus_fatigue.value > initial_focus
    
    def test_update_from_event_assistant_reply(self):
        """Test update from assistant_reply event"""
        bsv = BodyStateVector()
        initial_energy = bsv.energy.value
        
        trace = bsv.update_from_event("assistant_reply")
        deltas = trace["global_body_delta"]
        
        assert deltas["energy"] < 0
        assert deltas["focus_fatigue"] > 0
        assert bsv.energy.value < initial_energy
    
    def test_update_from_event_world_event_care(self):
        """Test update from world_event with care subtype"""
        bsv = BodyStateVector()
        initial_safety = bsv.safety_stress.value
        initial_energy = bsv.energy.value
        
        trace = bsv.update_from_event("world_event", "care")
        deltas = trace["global_body_delta"]
        
        assert deltas["safety_stress"] > 0
        assert deltas["energy"] > 0
        assert bsv.safety_stress.value > initial_safety
        assert bsv.energy.value > initial_energy
    
    def test_update_from_event_world_event_rejection(self):
        """Test update from world_event with rejection subtype"""
        bsv = BodyStateVector()
        initial_safety = bsv.safety_stress.value
        
        trace = bsv.update_from_event("world_event", "rejection")
        deltas = trace["global_body_delta"]
        
        assert deltas["safety_stress"] < 0
        assert bsv.safety_stress.value < initial_safety
    
    def test_update_from_event_world_event_betrayal(self):
        """Test update from world_event with betrayal subtype"""
        bsv = BodyStateVector()
        initial_safety = bsv.safety_stress.value
        initial_energy = bsv.energy.value
        
        trace = bsv.update_from_event("world_event", "betrayal")
        deltas = trace["global_body_delta"]
        
        assert deltas["safety_stress"] < 0
        assert deltas["energy"] < 0
        assert bsv.safety_stress.value < initial_safety
        assert bsv.energy.value < initial_energy
    
    def test_update_from_event_world_event_time_passed(self):
        """Test update from world_event with time_passed subtype"""
        bsv = BodyStateVector()
        bsv.energy.value = 0.3  # Below baseline
        
        deltas = bsv.update_from_event("world_event", "time_passed", {"seconds": 100})
        
        # Energy should recover due to time_passed
        assert bsv.energy.value > 0.3
    
    def test_update_from_event_unknown_subtype(self):
        """Test update with unknown subtype returns zero deltas"""
        bsv = BodyStateVector()
        trace = bsv.update_from_event("world_event", "unknown_subtype")
        deltas = trace["global_body_delta"]
        
        assert all(v == 0 for v in deltas.values())
    
    def test_get_energy_budget_factor(self):
        """Test energy budget factor calculation"""
        bsv = BodyStateVector()
        bsv.energy.value = 0.25  # 25% energy
        budget = bsv.get_energy_budget_factor()
        assert budget == pytest.approx(0.5, abs=0.01)  # sqrt(0.25) = 0.5
    
    def test_get_energy_budget_factor_full(self):
        """Test energy budget factor at full energy"""
        bsv = BodyStateVector()
        bsv.energy.value = 1.0
        budget = bsv.get_energy_budget_factor()
        assert budget == 1.0
    
    def test_get_energy_budget_factor_empty(self):
        """Test energy budget factor at zero energy"""
        bsv = BodyStateVector()
        bsv.energy.value = 0.0
        budget = bsv.get_energy_budget_factor()
        assert budget == 0.0
    
    def test_get_summary(self):
        """Test get_summary method"""
        bsv = BodyStateVector()
        summary = bsv.get_summary()
        
        assert "energy" in summary
        assert "safety_stress" in summary
        assert "social_need" in summary
        assert "novelty_need" in summary
        assert "focus_fatigue" in summary
        assert summary["energy"] == 0.7
    
    def test_get_uncertainties(self):
        """Test get_uncertainties method"""
        bsv = BodyStateVector()
        uncertainties = bsv.get_uncertainties()
        
        assert "energy" in uncertainties
        assert "safety_stress" in uncertainties
        assert all(0 <= u <= 1 for u in uncertainties.values())
    
    def test_to_dict(self):
        """Test serialization to dict"""
        bsv = BodyStateVector()
        data = bsv.to_dict()
        
        assert "energy" in data
        assert "safety_stress" in data
        assert "social_need" in data
        assert "novelty_need" in data
        assert "focus_fatigue" in data
        assert "value" in data["energy"]
    
    def test_from_dict(self):
        """Test deserialization from dict"""
        bsv = BodyStateVector()
        bsv.energy.value = 0.8
        bsv.safety_stress.value = 0.7
        
        data = bsv.to_dict()
        bsv2 = BodyStateVector.from_dict(data)
        
        assert bsv2.energy.value == 0.8
        assert bsv2.safety_stress.value == 0.7
    
    def test_clone(self):
        """Test clone method"""
        bsv = BodyStateVector()
        bsv.energy.value = 0.9
        
        clone = bsv.clone()
        assert clone.energy.value == 0.9
        
        # Modify clone should not affect original
        clone.energy.value = 0.5
        assert bsv.energy.value == 0.9
    
    def test_post_init_dict_conversion(self):
        """Test that dict dimensions are converted to objects"""
        data = {
            "energy": {"value": 0.8, "uncertainty": 0.2, "last_updated": time.time()},
            "safety_stress": {"value": 0.7, "uncertainty": 0.3, "last_updated": time.time()},
            "social_need": {"value": 0.6, "uncertainty": 0.4, "last_updated": time.time()},
            "novelty_need": {"value": 0.5, "uncertainty": 0.5, "last_updated": time.time()},
            "focus_fatigue": {"value": 0.4, "uncertainty": 0.4, "last_updated": time.time()},
        }
        bsv = BodyStateVector(**data)
        assert isinstance(bsv.energy, BodyStateDimension)
        assert bsv.energy.value == 0.8


# ============================================================================
# Global State Management Tests
# ============================================================================

class TestGlobalStateManagement:
    """Tests for global body state management functions"""
    
    def test_get_body_state_creates_default(self):
        """Test that get_body_state creates default if none exists"""
        # Reset global state
        global _global_body_state
        import emotiond.body_state as bs
        bs._global_body_state = None
        
        bsv = get_body_state()
        assert isinstance(bsv, BodyStateVector)
        assert bsv.energy.value == 0.7
    
    def test_set_body_state(self):
        """Test set_body_state function"""
        new_bsv = BodyStateVector()
        new_bsv.energy.value = 0.9
        
        set_body_state(new_bsv)
        retrieved = get_body_state()
        
        assert retrieved.energy.value == 0.9
    
    def test_reset_body_state(self):
        """Test reset_body_state function"""
        # Modify global state
        bsv = get_body_state()
        bsv.energy.value = 0.2
        
        # Reset
        reset_bsv = reset_body_state()
        
        assert reset_bsv.energy.value == 0.7
        retrieved = get_body_state()
        assert retrieved.energy.value == 0.7


# ============================================================================
# Integration Tests with EmotionState
# ============================================================================

class TestEmotionStateIntegration:
    """Tests for integration with EmotionState"""
    
    def test_emotion_state_has_body_state(self):
        """Test that EmotionState has body_state attribute"""
        from emotiond.core import EmotionState
        es = EmotionState()
        assert hasattr(es, "body_state")
        assert isinstance(es.body_state, BodyStateVector)
    
    def test_energy_sync_from_body_state(self):
        """Test that legacy energy syncs from body_state"""
        from emotiond.core import EmotionState
        es = EmotionState()
        es.body_state.energy.value = 0.5
        es.energy = es.body_state.energy.value
        assert es.energy == 0.5
    
    def test_regulation_budget_derived_from_body_state(self):
        """Test that regulation_budget is derived from body_state energy"""
        from emotiond.core import EmotionState
        es = EmotionState()
        es.body_state.energy.value = 0.25
        budget = es.body_state.get_energy_budget_factor()
        assert budget == pytest.approx(0.5, abs=0.01)


# ============================================================================
# Recovery and Regression Tests
# ============================================================================

class TestRecoveryRegression:
    """Tests for recovery and regression dynamics"""
    
    def test_energy_recovery_rate(self):
        """Test energy recovery rate configuration"""
        dim = BodyStateDimension(
            value=0.3,
            baseline=0.7,
            recovery_dynamics=RecoveryDynamics(recovery_rate=0.001)
        )
        dim.apply_time_passed(1000)  # 1000 seconds
        expected_recovery = 0.3 + (0.001 * 1000)  # 1.3, clamped to 0.7
        assert dim.value == 0.7  # Should reach baseline
    
    def test_focus_fatigue_regression_rate(self):
        """Test focus fatigue regression rate"""
        dim = BodyStateDimension(
            value=0.8,
            baseline=0.3,
            recovery_dynamics=RecoveryDynamics(decay_rate=0.001)
        )
        dim.apply_time_passed(100)  # 100 seconds
        expected = 0.8 - (0.001 * 100)  # 0.7
        assert dim.value == pytest.approx(expected, abs=0.01)
    
    def test_different_recovery_rates_per_dimension(self):
        """Test that different dimensions have different recovery rates"""
        bsv = BodyStateVector()
        
        # Energy recovers faster than novelty
        assert bsv.energy.recovery_rate > bsv.novelty_need.recovery_rate
        
        # Focus recovers faster than energy
        assert bsv.focus_fatigue.recovery_rate > bsv.energy.recovery_rate


# ============================================================================
# Clamp and Range Tests
# ============================================================================

class TestClampsAndRanges:
    """Tests for value clamping and valid ranges"""
    
    def test_value_clamped_upper(self):
        """Test value clamped to 1.0 maximum"""
        dim = BodyStateDimension(value=1.5)
        assert dim.value == 1.0
    
    def test_value_clamped_lower(self):
        """Test value clamped to 0.0 minimum"""
        dim = BodyStateDimension(value=-0.5)
        assert dim.value == 0.0
    
    def test_uncertainty_clamped_upper(self):
        """Test uncertainty clamped to 1.0 maximum"""
        dim = BodyStateDimension(uncertainty=1.5)
        assert dim.uncertainty == 1.0
    
    def test_uncertainty_clamped_lower(self):
        """Test uncertainty clamped to 0.0 minimum"""
        dim = BodyStateDimension(uncertainty=-0.5)
        assert dim.uncertainty == 0.0
    
    def test_update_respects_clamps(self):
        """Test that update respects value clamps"""
        dim = BodyStateDimension(value=0.95)
        dim.update(0.2)  # Would go to 1.15
        assert dim.value == 1.0
        
        dim2 = BodyStateDimension(value=0.05)
        dim2.update(-0.2)  # Would go to -0.15
        assert dim2.value == 0.0


# ============================================================================
# Stability Tests
# ============================================================================

class TestStability:
    """Tests for numerical stability"""
    
    def test_many_updates_stability(self):
        """Test stability after many updates"""
        dim = BodyStateDimension(value=0.5)
        for _ in range(1000):
            dim.update(0.01)
            dim.update(-0.01)
        assert 0 <= dim.value <= 1
        assert 0 <= dim.uncertainty <= 1
    
    def test_long_time_passed_stability(self):
        """Test stability with very long time passed"""
        dim = BodyStateDimension(value=0.1, baseline=0.5, recovery_dynamics=RecoveryDynamics(recovery_rate=0.001))
        dim.apply_time_passed(1000000)  # Very long time
        assert dim.value == 0.5  # Should reach baseline, not overflow
    
    def test_extreme_values_handling(self):
        """Test handling of extreme values"""
        dim = BodyStateDimension(value=0.0001, uncertainty=0.9999)
        dim.apply_time_passed(1)
        assert 0 <= dim.value <= 1
        assert 0 <= dim.uncertainty <= 1


# ============================================================================
# Cross-Target Ownership Tests
# ============================================================================

class TestCrossTargetOwnership:
    """Tests for cross-target ownership semantics"""
    
    def test_body_state_is_per_agent(self):
        """Test that body state is per-agent, not per-target"""
        bsv1 = BodyStateVector()
        bsv2 = BodyStateVector()
        
        bsv1.energy.value = 0.3
        bsv2.energy.value = 0.8
        
        # Changes to one should not affect the other
        assert bsv1.energy.value == 0.3
        assert bsv2.energy.value == 0.8
    
    def test_clone_independence(self):
        """Test that cloned body states are independent"""
        original = BodyStateVector()
        original.energy.value = 0.5
        
        clone = original.clone()
        clone.energy.value = 0.9
        
        assert original.energy.value == 0.5
        assert clone.energy.value == 0.9
    
    def test_from_dict_creates_independent_copy(self):
        """Test that from_dict creates independent copy"""
        original = BodyStateVector()
        original.energy.value = 0.6
        
        data = original.to_dict()
        copy = BodyStateVector.from_dict(data)
        
        copy.energy.value = 0.9
        assert original.energy.value == 0.6


# ============================================================================
# Serialization Tests
# ============================================================================

class TestSerialization:
    """Tests for serialization/deserialization"""
    
    def test_full_round_trip(self):
        """Test full round-trip serialization"""
        original = BodyStateVector()
        original.energy.value = 0.85
        original.safety_stress.value = 0.75
        original.social_need.value = 0.65
        original.novelty_need.value = 0.55
        original.focus_fatigue.value = 0.45
        
        data = original.to_dict()
        restored = BodyStateVector.from_dict(data)
        
        assert restored.energy.value == 0.85
        assert restored.safety_stress.value == 0.75
        assert restored.social_need.value == 0.65
        assert restored.novelty_need.value == 0.55
        assert restored.focus_fatigue.value == 0.45
    
    def test_serialization_preserves_config(self):
        """Test that serialization preserves configuration"""
        dim = BodyStateDimension(
            value=0.7,
            recovery_dynamics=RecoveryDynamics(recovery_rate=0.002, decay_rate=0.001),
            baseline=0.6
        )
        
        data = dim.to_dict()
        restored = BodyStateDimension.from_dict(data)
        
        assert restored.recovery_rate == 0.002
        assert restored.decay_rate == 0.001
        assert restored.baseline == 0.6


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases"""
    
    def test_zero_time_passed(self):
        """Test with zero time passed"""
        dim = BodyStateDimension(value=0.5)
        dim.apply_time_passed(0)
        assert dim.value == 0.5
    
    def test_negative_delta_update(self):
        """Test update with large negative delta"""
        dim = BodyStateDimension(value=0.5)
        dim.update(-10)  # Would go to -9.5
        assert dim.value == 0.0  # Clamped
    
    def test_positive_delta_overflow(self):
        """Test update with large positive delta"""
        dim = BodyStateDimension(value=0.5)
        dim.update(10)  # Would go to 10.5
        assert dim.value == 1.0  # Clamped
    
    def test_none_meta_handling(self):
        """Test handling of None meta"""
        bsv = BodyStateVector()
        deltas = bsv.update_from_event("world_event", "time_passed", None)
        # Should not raise exception
        assert isinstance(deltas, dict)
    
    def test_empty_meta_handling(self):
        """Test handling of empty meta"""
        bsv = BodyStateVector()
        deltas = bsv.update_from_event("world_event", "time_passed", {})
        # Should use default seconds=60
        assert isinstance(deltas, dict)


# ============================================================================
# Configuration Tests
# ============================================================================

class TestConfiguration:
    """Tests for configuration integration"""
    
    def test_config_recovery_rates(self):
        """Test that config recovery rates are used"""
        from emotiond.config import (
            BODY_STATE_ENERGY_RECOVERY,
            BODY_STATE_SAFETY_RECOVERY,
            BODY_STATE_FOCUS_RECOVERY,
        )
        
        # Verify config values are positive
        assert BODY_STATE_ENERGY_RECOVERY > 0
        assert BODY_STATE_SAFETY_RECOVERY > 0
        assert BODY_STATE_FOCUS_RECOVERY > 0
    
    def test_config_baselines(self):
        """Test that config baselines are in valid range"""
        from emotiond.config import (
            BODY_STATE_ENERGY_BASELINE,
            BODY_STATE_SAFETY_BASELINE,
            BODY_STATE_FOCUS_BASELINE,
        )
        
        assert 0 <= BODY_STATE_ENERGY_BASELINE <= 1
        assert 0 <= BODY_STATE_SAFETY_BASELINE <= 1
        assert 0 <= BODY_STATE_FOCUS_BASELINE <= 1


# ============================================================================
# Compatibility Tests
# ============================================================================

class TestEnergyBudgetCompatibility:
    """Tests for backward compatibility with energy_budget"""
    
    def test_energy_budget_derived_correctly(self):
        """Test that energy budget is correctly derived from body state"""
        bsv = BodyStateVector()
        
        # At default energy 0.7, budget should be sqrt(0.7) ≈ 0.84
        budget = bsv.get_energy_budget_factor()
        assert budget == pytest.approx(0.836, abs=0.01)
    
    def test_legacy_energy_interface(self):
        """Test that legacy energy interface still works"""
        from emotiond.core import EmotionState
        es = EmotionState()
        
        # Legacy energy should be accessible
        assert hasattr(es, "energy")
        assert 0 <= es.energy <= 1
    
    def test_body_state_energy_matches_legacy(self):
        """Test that body_state energy and legacy energy stay in sync"""
        from emotiond.core import EmotionState
        es = EmotionState()
        
        # They should match initially
        assert es.energy == es.body_state.energy.value


# Run the tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
