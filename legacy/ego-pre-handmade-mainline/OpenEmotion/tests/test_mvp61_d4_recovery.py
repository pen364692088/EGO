"""
MVP-6.1 D4 Tests: Recovery Dynamics

Tests for:
- Parameterized recovery/decay rates per body dimension
- Half-life calculation for telemetry
- Collapse duration tracking
- Recovery telemetry fields (recovery_half_life_steps, collapse_duration)
- Recovery curve monotonicity and stability
- Parameter sensitivity (changes affect recovery)
"""
import pytest
import time
import math
from emotiond.body_state import (
    BodyStateDimension, BodyStateVector, RecoveryDynamics, RecoveryTelemetry,
    get_body_state, reset_body_state, set_dimension_recovery_params, get_recovery_diagnostics
)


class TestRecoveryDynamics:
    """Test parameterized recovery dynamics."""
    
    def test_recovery_dynamics_defaults(self):
        """RecoveryDynamics has sensible defaults."""
        rd = RecoveryDynamics()
        assert rd.recovery_rate == 0.001
        assert rd.decay_rate == 0.0005
        assert rd.half_life_seconds == 600.0
    
    def test_recovery_dynamics_custom_params(self):
        """RecoveryDynamics accepts custom parameters."""
        rd = RecoveryDynamics(
            recovery_rate=0.01,
            decay_rate=0.005,
            half_life_seconds=300.0
        )
        assert rd.recovery_rate == 0.01
        assert rd.decay_rate == 0.005
        assert rd.half_life_seconds == 300.0
    
    def test_half_life_steps_calculation(self):
        """Half-life in steps is calculated correctly."""
        rd = RecoveryDynamics(half_life_seconds=600.0)
        
        # With 1 second per step
        steps = rd.compute_half_life_steps(step_seconds=1.0)
        assert steps == 600.0
        
        # With 10 seconds per step
        steps = rd.compute_half_life_steps(step_seconds=10.0)
        assert steps == 60.0
    
    def test_half_life_serialization(self):
        """RecoveryDynamics serializes and deserializes correctly."""
        rd = RecoveryDynamics(recovery_rate=0.02, decay_rate=0.01, half_life_seconds=120.0)
        data = rd.to_dict()
        restored = RecoveryDynamics.from_dict(data)
        
        assert restored.recovery_rate == 0.02
        assert restored.decay_rate == 0.01
        assert restored.half_life_seconds == 120.0


class TestBodyStateDimensionRecovery:
    """Test recovery behavior in BodyStateDimension."""
    
    def test_dimension_has_recovery_dynamics(self):
        """BodyStateDimension has recovery_dynamics attribute."""
        dim = BodyStateDimension()
        assert hasattr(dim, 'recovery_dynamics')
        assert isinstance(dim.recovery_dynamics, RecoveryDynamics)
    
    def test_recovery_when_below_baseline(self):
        """Dimension recovers toward baseline when below it."""
        dim = BodyStateDimension(value=0.3, baseline=0.5, 
                                  recovery_dynamics=RecoveryDynamics(recovery_rate=0.01))
        
        # Apply time - should recover toward baseline
        dim.apply_time_passed(seconds=10)
        
        # Value should increase toward baseline
        assert dim.value > 0.3
        assert dim.value <= 0.5
    
    def test_decay_when_above_baseline(self):
        """Dimension decays toward baseline when above it."""
        dim = BodyStateDimension(value=0.8, baseline=0.5,
                                  recovery_dynamics=RecoveryDynamics(decay_rate=0.01))
        
        # Apply time - should decay toward baseline
        dim.apply_time_passed(seconds=10)
        
        # Value should decrease toward baseline
        assert dim.value < 0.8
        assert dim.value >= 0.5
    
    def test_recovery_monotonicity(self):
        """Recovery is monotonic (no oscillation)."""
        dim = BodyStateDimension(value=0.2, baseline=0.5,
                                  recovery_dynamics=RecoveryDynamics(recovery_rate=0.01))
        
        values = []
        for _ in range(100):
            dim.apply_time_passed(seconds=1)
            values.append(dim.value)
        
        # Check monotonic increase
        for i in range(1, len(values)):
            assert values[i] >= values[i-1] - 1e-9  # Allow tiny floating point errors
    
    def test_decay_monotonicity(self):
        """Decay is monotonic (no oscillation)."""
        dim = BodyStateDimension(value=0.9, baseline=0.5,
                                  recovery_dynamics=RecoveryDynamics(decay_rate=0.01))
        
        values = []
        for _ in range(100):
            dim.apply_time_passed(seconds=1)
            values.append(dim.value)
        
        # Check monotonic decrease
        for i in range(1, len(values)):
            assert values[i] <= values[i-1] + 1e-9  # Allow tiny floating point errors
    
    def test_recovery_stops_at_baseline(self):
        """Recovery stops at baseline, doesn't overshoot."""
        dim = BodyStateDimension(value=0.1, baseline=0.5,
                                  recovery_dynamics=RecoveryDynamics(recovery_rate=0.1))
        
        # Apply lots of time
        for _ in range(1000):
            dim.apply_time_passed(seconds=1)
        
        # Should be at or very close to baseline
        assert abs(dim.value - 0.5) < 0.01
    
    def test_half_life_calculation_from_dimension(self):
        """BodyStateDimension calculates half-life correctly."""
        dim = BodyStateDimension(
            recovery_dynamics=RecoveryDynamics(half_life_seconds=300.0)
        )
        
        half_life = dim.calculate_recovery_half_life_steps(step_seconds=1.0)
        assert half_life == 300.0
    
    def test_legacy_recovery_rate_alias(self):
        """Legacy recovery_rate property still works."""
        dim = BodyStateDimension()
        
        # Test getter
        assert dim.recovery_rate == dim.recovery_dynamics.recovery_rate
        
        # Test setter
        dim.recovery_rate = 0.02
        assert dim.recovery_dynamics.recovery_rate == 0.02
    
    def test_legacy_regression_rate_alias(self):
        """Legacy regression_rate property maps to decay_rate."""
        dim = BodyStateDimension()
        
        # Test getter
        assert dim.regression_rate == dim.recovery_dynamics.decay_rate
        
        # Test setter
        dim.regression_rate = 0.02
        assert dim.recovery_dynamics.decay_rate == 0.02
    
    def test_dimension_serialization_with_recovery(self):
        """BodyStateDimension with recovery dynamics serializes correctly."""
        dim = BodyStateDimension(
            value=0.6,
            baseline=0.5,
            recovery_dynamics=RecoveryDynamics(recovery_rate=0.02, decay_rate=0.01, half_life_seconds=120.0)
        )
        
        data = dim.to_dict()
        restored = BodyStateDimension.from_dict(data)
        
        assert restored.value == 0.6
        assert restored.baseline == 0.5
        assert restored.recovery_dynamics.recovery_rate == 0.02
        assert restored.recovery_dynamics.decay_rate == 0.01
        assert restored.recovery_dynamics.half_life_seconds == 120.0


class TestRecoveryTelemetry:
    """Test recovery telemetry tracking."""
    
    def test_telemetry_initialization(self):
        """RecoveryTelemetry initializes correctly."""
        tel = RecoveryTelemetry(dimension_name="energy")
        assert tel.dimension_name == "energy"
        assert tel.half_life_steps == 0.0
        assert tel.collapse_duration == 0
        assert not tel.is_collapsed
    
    def test_telemetry_records_steps(self):
        """RecoveryTelemetry records steps."""
        tel = RecoveryTelemetry(dimension_name="energy")
        
        tel.record_step(step=1, value=0.5)
        tel.record_step(step=2, value=0.4)
        
        assert len(tel.recovery_trajectory) == 2
        assert tel.recovery_trajectory[0] == (1, 0.5)
        assert tel.recovery_trajectory[1] == (2, 0.4)
    
    def test_telemetry_detects_collapse(self):
        """RecoveryTelemetry detects collapse below threshold."""
        tel = RecoveryTelemetry(dimension_name="energy")
        
        # Start normal
        tel.record_step(step=1, value=0.5, collapse_threshold=0.3)
        assert not tel.is_collapsed
        
        # Drop below threshold
        tel.record_step(step=2, value=0.2, collapse_threshold=0.3)
        assert tel.is_collapsed
        assert tel.collapse_start_step == 2
    
    def test_telemetry_tracks_collapse_duration(self):
        """RecoveryTelemetry tracks collapse duration."""
        tel = RecoveryTelemetry(dimension_name="energy")
        
        # Collapse for 3 steps
        tel.record_step(step=1, value=0.2, collapse_threshold=0.3)
        tel.record_step(step=2, value=0.2, collapse_threshold=0.3)
        tel.record_step(step=3, value=0.2, collapse_threshold=0.3)
        
        # Recover
        tel.record_step(step=4, value=0.5, collapse_threshold=0.3)
        
        assert tel.collapse_duration == 3  # Steps 1-3
        assert not tel.is_collapsed
    
    def test_telemetry_finalize_ongoing_collapse(self):
        """RecoveryTelemetry.finalize handles ongoing collapse."""
        tel = RecoveryTelemetry(dimension_name="energy")
        
        # Collapse
        tel.record_step(step=1, value=0.2, collapse_threshold=0.3)
        tel.record_step(step=2, value=0.2, collapse_threshold=0.3)
        
        # Still collapsed - finalize
        tel.finalize(final_step=5)
        
        assert tel.collapse_duration == 4  # Steps 1-4
        assert not tel.is_collapsed
    
    def test_telemetry_serialization(self):
        """RecoveryTelemetry serializes correctly."""
        tel = RecoveryTelemetry(dimension_name="energy", half_life_steps=100.0)
        tel.collapse_duration = 5
        
        data = tel.to_dict()
        
        assert data["dimension_name"] == "energy"
        assert data["half_life_steps"] == 100.0
        assert data["collapse_duration"] == 5


class TestBodyStateVectorRecovery:
    """Test recovery in BodyStateVector."""
    
    def test_body_state_has_recovery_telemetry(self):
        """BodyStateVector has recovery_telemetry."""
        body = BodyStateVector()
        assert hasattr(body, 'recovery_telemetry')
        assert "energy" in body.recovery_telemetry
        assert "safety_stress" in body.recovery_telemetry
    
    def test_body_state_dimensions_have_recovery_params(self):
        """All dimensions have parameterized recovery."""
        body = BodyStateVector()
        
        # Check each dimension has recovery_dynamics
        for dim_name in ["energy", "safety_stress", "social_need", "novelty_need", "focus_fatigue"]:
            dim = getattr(body, dim_name)
            assert hasattr(dim, 'recovery_dynamics')
            assert isinstance(dim.recovery_dynamics, RecoveryDynamics)
    
    def test_energy_recovery_params(self):
        """Energy has specific recovery parameters."""
        body = BodyStateVector()
        
        assert body.energy.baseline == 0.7
        assert body.energy.recovery_dynamics.recovery_rate == 0.001
        assert body.energy.recovery_dynamics.decay_rate == 0.0003
        assert body.energy.recovery_dynamics.half_life_seconds == 300.0
    
    def test_safety_stress_recovery_params(self):
        """Safety_stress has specific recovery parameters."""
        body = BodyStateVector()
        
        assert body.safety_stress.baseline == 0.6
        assert body.safety_stress.recovery_dynamics.recovery_rate == 0.0008
        assert body.safety_stress.recovery_dynamics.decay_rate == 0.0005
        assert body.safety_stress.recovery_dynamics.half_life_seconds == 600.0
    
    def test_focus_fatigue_recovery_params(self):
        """Focus_fatigue has specific recovery parameters."""
        body = BodyStateVector()
        
        assert body.focus_fatigue.baseline == 0.3
        assert body.focus_fatigue.recovery_dynamics.recovery_rate == 0.002
        assert body.focus_fatigue.recovery_dynamics.decay_rate == 0.001
        assert body.focus_fatigue.recovery_dynamics.half_life_seconds == 180.0
    
    def test_apply_time_passed_updates_telemetry(self):
        """apply_time_passed updates recovery telemetry."""
        body = BodyStateVector()
        body.energy.value = 0.2  # Low energy
        
        initial_step = body._step_counter
        body.apply_time_passed(seconds=10)
        
        assert body._step_counter == initial_step + 1
        assert len(body.recovery_telemetry["energy"].recovery_trajectory) > 0
    
    def test_get_recovery_half_life_steps(self):
        """get_recovery_half_life_steps returns values for all dimensions."""
        body = BodyStateVector()
        
        half_lives = body.get_recovery_half_life_steps()
        
        assert "energy" in half_lives
        assert "safety_stress" in half_lives
        assert "social_need" in half_lives
        assert "novelty_need" in half_lives
        assert "focus_fatigue" in half_lives
        
        # All should be positive
        for dim, hl in half_lives.items():
            assert hl > 0, f"{dim} half-life should be positive"
    
    def test_get_collapse_duration(self):
        """get_collapse_duration returns collapse durations."""
        body = BodyStateVector()
        
        # Simulate collapsed state
        body.energy.value = 0.2  # Below threshold
        for _ in range(5):
            body._update_recovery_telemetry()
        
        durations = body.get_collapse_duration()
        
        assert "energy" in durations
        # Energy was collapsed for 5 steps
        assert durations["energy"] >= 4
    
    def test_get_recovery_telemetry(self):
        """get_recovery_telemetry returns full telemetry."""
        body = BodyStateVector()
        
        telemetry = body.get_recovery_telemetry()
        
        assert "energy" in telemetry
        assert "half_life_steps" in telemetry["energy"]
        assert "collapse_duration" in telemetry["energy"]
    
    def test_recovery_parameter_sensitivity(self):
        """Different recovery rates produce different recovery speeds."""
        # Fast recovery
        body_fast = BodyStateVector()
        body_fast.energy.value = 0.2
        body_fast.energy.recovery_dynamics.recovery_rate = 0.1
        
        # Slow recovery
        body_slow = BodyStateVector()
        body_slow.energy.value = 0.2
        body_slow.energy.recovery_dynamics.recovery_rate = 0.001
        
        # Apply same time
        body_fast.apply_time_passed(seconds=10)
        body_slow.apply_time_passed(seconds=10)
        
        # Fast should recover more
        assert body_fast.energy.value > body_slow.energy.value


class TestRecoveryDiagnostics:
    """Test recovery diagnostics functions."""
    
    def test_set_dimension_recovery_params(self):
        """set_dimension_recovery_params updates parameters."""
        reset_body_state()
        
        set_dimension_recovery_params(
            dimension="energy",
            recovery_rate=0.05,
            decay_rate=0.02,
            half_life_seconds=200.0
        )
        
        body = get_body_state()
        assert body.energy.recovery_dynamics.recovery_rate == 0.05
        assert body.energy.recovery_dynamics.decay_rate == 0.02
        assert body.energy.recovery_dynamics.half_life_seconds == 200.0
    
    def test_set_dimension_recovery_params_partial(self):
        """set_dimension_recovery_params can update partial params."""
        reset_body_state()
        original_decay = get_body_state().energy.recovery_dynamics.decay_rate
        
        set_dimension_recovery_params(
            dimension="energy",
            recovery_rate=0.05
        )
        
        body = get_body_state()
        assert body.energy.recovery_dynamics.recovery_rate == 0.05
        assert body.energy.recovery_dynamics.decay_rate == original_decay  # Unchanged
    
    def test_set_dimension_recovery_params_invalid_dimension(self):
        """set_dimension_recovery_params raises on invalid dimension."""
        with pytest.raises(ValueError, match="Unknown dimension"):
            set_dimension_recovery_params(dimension="invalid_dim", recovery_rate=0.01)
    
    def test_get_recovery_diagnostics(self):
        """get_recovery_diagnostics returns comprehensive data."""
        reset_body_state()
        
        diagnostics = get_recovery_diagnostics()
        
        assert "recovery_half_life_steps" in diagnostics
        assert "collapse_duration" in diagnostics
        assert "telemetry" in diagnostics
        assert "current_values" in diagnostics
        assert "baselines" in diagnostics
        
        # Check all dimensions present
        for dim in ["energy", "safety_stress", "social_need", "novelty_need", "focus_fatigue"]:
            assert dim in diagnostics["recovery_half_life_steps"]
            assert dim in diagnostics["collapse_duration"]
            assert dim in diagnostics["current_values"]
            assert dim in diagnostics["baselines"]


class TestRecoveryNoOscillation:
    """Test that recovery doesn't oscillate."""
    
    def test_energy_recovery_no_oscillation(self):
        """Energy recovery is stable without oscillation."""
        body = BodyStateVector()
        body.energy.value = 0.1  # Very low
        
        values = []
        for _ in range(200):
            body.apply_time_passed(seconds=1)
            values.append(body.energy.value)
        
        # Should monotonically increase toward baseline
        for i in range(1, len(values)):
            assert values[i] >= values[i-1] - 1e-9
    
    def test_safety_stress_decay_no_oscillation(self):
        """Safety_stress decay is stable without oscillation."""
        body = BodyStateVector()
        body.safety_stress.value = 0.9  # Very high
        
        values = []
        for _ in range(200):
            body.apply_time_passed(seconds=1)
            values.append(body.safety_stress.value)
        
        # Should monotonically decrease toward baseline
        for i in range(1, len(values)):
            assert values[i] <= values[i-1] + 1e-9
    
    def test_focus_fatigue_recovery_no_oscillation(self):
        """Focus_fatigue recovery is stable without oscillation."""
        body = BodyStateVector()
        body.focus_fatigue.value = 0.8  # High fatigue
        baseline = body.focus_fatigue.baseline  # 0.3
        
        values = []
        for _ in range(200):
            body.apply_time_passed(seconds=1)
            values.append(body.focus_fatigue.value)
        
        # Should monotonically decrease toward baseline (0.3)
        for i in range(1, len(values)):
            assert values[i] <= values[i-1] + 1e-9


class TestRecoveryIntegration:
    """Integration tests for recovery dynamics."""
    
    def test_recovery_after_negative_events(self):
        """System recovers after negative events."""
        reset_body_state()
        body = get_body_state()
        
        # Apply negative events
        for _ in range(5):
            body.update_from_event("world_event", event_subtype="betrayal")
        
        # Energy should be depleted
        initial_energy = body.energy.value
        assert initial_energy < 0.7  # Below baseline
        
        # Apply recovery time
        for _ in range(100):
            body.apply_time_passed(seconds=1)
        
        # Energy should recover toward baseline
        assert body.energy.value > initial_energy
    
    def test_collapse_duration_tracking_integration(self):
        """Collapse duration is tracked across event sequence."""
        reset_body_state()
        body = get_body_state()
        
        # Deplete energy
        body.energy.value = 0.2  # Collapsed
        
        # Simulate steps
        for _ in range(10):
            body._update_recovery_telemetry()
        
        # Check collapse was tracked
        durations = body.get_collapse_duration()
        assert durations["energy"] >= 9
    
    def test_half_life_consistency(self):
        """Half-life is consistent with recovery rate."""
        body = BodyStateVector()
        
        # Set specific half-life
        body.energy.recovery_dynamics.half_life_seconds = 60.0
        
        # Calculate half-life in steps
        half_life_steps = body.energy.calculate_recovery_half_life_steps(step_seconds=1.0)
        
        assert half_life_steps == 60.0
    
    def test_serialization_preserves_recovery_params(self):
        """Serialization preserves recovery dynamics parameters."""
        body = BodyStateVector()
        body.energy.recovery_dynamics.recovery_rate = 0.05
        body.energy.recovery_dynamics.decay_rate = 0.02
        body.energy.recovery_dynamics.half_life_seconds = 150.0
        
        # Serialize and restore
        data = body.to_dict()
        restored = BodyStateVector.from_dict(data)
        
        assert restored.energy.recovery_dynamics.recovery_rate == 0.05
        assert restored.energy.recovery_dynamics.decay_rate == 0.02
        assert restored.energy.recovery_dynamics.half_life_seconds == 150.0


class TestRecoveryEvalFitness:
    """Test recovery metrics for eval/fitness integration."""
    
    def test_recovery_half_life_for_eval(self):
        """recovery_half_life_steps is available for eval scoring."""
        body = BodyStateVector()
        
        half_lives = body.get_recovery_half_life_steps()
        
        # Should be usable for fitness calculation
        avg_half_life = sum(half_lives.values()) / len(half_lives)
        assert avg_half_life > 0
    
    def test_collapse_duration_for_fitness(self):
        """collapse_duration is available for fitness calculation."""
        body = BodyStateVector()
        
        # Simulate some collapsed steps
        body.energy.value = 0.2
        for _ in range(5):
            body._update_recovery_telemetry()
        
        durations = body.get_collapse_duration()
        total_collapse = sum(durations.values())
        
        # Should be usable for fitness (lower is better)
        assert total_collapse >= 4
    
    def test_recovery_score_calculation(self):
        """Recovery score can be calculated from telemetry."""
        body = BodyStateVector()
        
        # Get telemetry
        telemetry = body.get_recovery_telemetry()
        
        # Calculate a recovery score (example)
        total_half_life = sum(t["half_life_steps"] for t in telemetry.values())
        total_collapse = sum(t["collapse_duration"] for t in telemetry.values())
        
        # Score: higher half-life (slower recovery) and more collapse = worse
        recovery_score = 1.0 / (1.0 + total_half_life * 0.001 + total_collapse * 0.1)
        
        assert 0 <= recovery_score <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
