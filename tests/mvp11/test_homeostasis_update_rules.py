"""
Tests for MVP11-T04: Homeostasis Module update rules.
"""

import pytest
from datetime import datetime
import sys
import os

# Add emotiond to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'emotiond'))

from homeostasis import (
    HomeostasisState,
    HomeostasisManager,
    DEFAULT_SETPOINTS,
    OUTCOME_EFFECTS,
    RECOVERY_ACTIONS,
    huber_loss,
    create_manager_from_event,
    compute_homeostasis_hash,
)


class TestHomeostasisState:
    """Test HomeostasisState dataclass."""
    
    def test_default_values(self):
        """Test default initialization."""
        state = HomeostasisState()
        assert state.energy == 0.5
        assert state.safety == 0.5
        assert state.affiliation == 0.5
        assert state.certainty == 0.5
        assert state.autonomy == 0.5
        assert state.fairness == 0.5
    
    def test_custom_values(self):
        """Test custom initialization."""
        state = HomeostasisState(energy=0.8, safety=0.9, affiliation=0.3)
        assert state.energy == 0.8
        assert state.safety == 0.9
        assert state.affiliation == 0.3
    
    def test_clamping_high_values(self):
        """Test that values above 1.0 are clamped."""
        state = HomeostasisState(energy=1.5, safety=2.0)
        assert state.energy == 1.0
        assert state.safety == 1.0
    
    def test_clamping_low_values(self):
        """Test that values below 0.0 are clamped."""
        state = HomeostasisState(energy=-0.5, safety=-1.0)
        assert state.energy == 0.0
        assert state.safety == 0.0
    
    def test_to_dict(self):
        """Test serialization to dict."""
        state = HomeostasisState(energy=0.7, safety=0.8)
        d = state.to_dict()
        
        assert d["energy"] == 0.7
        assert d["safety"] == 0.8
        assert len(d) == 6
    
    def test_from_dict(self):
        """Test deserialization from dict."""
        d = {"energy": 0.6, "safety": 0.7, "affiliation": 0.4}
        state = HomeostasisState.from_dict(d)
        
        assert state.energy == 0.6
        assert state.safety == 0.7
        assert state.affiliation == 0.4
        # Missing keys default to 0.5
        assert state.certainty == 0.5
        assert state.autonomy == 0.5
        assert state.fairness == 0.5


class TestHomeostasisManager:
    """Test HomeostasisManager class."""
    
    def test_initialization(self):
        """Test manager initialization."""
        manager = HomeostasisManager()
        
        assert manager.state.energy == 0.5
        assert manager.stress_threshold == 0.3
        assert len(manager._history) == 0
    
    def test_custom_initial_state(self):
        """Test initialization with custom state."""
        initial = HomeostasisState(energy=0.8, safety=0.9)
        manager = HomeostasisManager(initial_state=initial)
        
        assert manager.state.energy == 0.8
        assert manager.state.safety == 0.9
    
    def test_update_from_outcome_success(self):
        """Test update from successful outcome."""
        manager = HomeostasisManager()
        initial_energy = manager.state.energy
        
        manager.update_from_outcome({"status": "success"})
        
        assert manager.state.energy > initial_energy
        assert manager.state.certainty > 0.5
    
    def test_update_from_outcome_fail(self):
        """Test update from failed outcome."""
        manager = HomeostasisManager()
        initial_energy = manager.state.energy
        
        manager.update_from_outcome({"status": "fail"})
        
        assert manager.state.energy < initial_energy
        assert manager.state.certainty < 0.5
    
    def test_update_from_outcome_partial(self):
        """Test update from partial outcome."""
        manager = HomeostasisManager()
        initial_energy = manager.state.energy
        
        manager.update_from_outcome({"status": "partial"})
        
        assert manager.state.energy < initial_energy
    
    def test_update_with_reason(self):
        """Test update with specific reason."""
        manager = HomeostasisManager()
        
        manager.update_from_outcome({"status": "fail", "reason": "rejected"})
        
        # Should decrease affiliation based on OUTCOME_EFFECTS
        assert manager.state.affiliation < 0.5
    
    def test_update_unfair_decreases_fairness(self):
        """Test that unfair outcome decreases fairness."""
        manager = HomeostasisManager()
        
        manager.update_from_outcome({"status": "fail", "reason": "unfair"})
        
        assert manager.state.fairness < 0.4  # Significant drop
    
    def test_history_tracking(self):
        """Test that updates are tracked in history."""
        manager = HomeostasisManager()
        
        manager.update_from_outcome({"status": "success"})
        manager.update_from_outcome({"status": "fail"})
        
        history = manager.get_history()
        assert len(history) == 2
        assert history[0]["outcome"]["status"] == "success"
        assert history[1]["outcome"]["status"] == "fail"


class TestDeviation:
    """Test deviation computation."""
    
    def test_get_deviation_neutral(self):
        """Test deviation at neutral state."""
        manager = HomeostasisManager()
        
        # Default setpoints prefer higher than 0.5 for most dimensions
        deviation = manager.get_deviation()
        
        # Most dimensions should show negative deviation (below setpoint)
        assert deviation["energy"] < 0  # 0.5 - 0.75 = -0.25
        assert deviation["safety"] < 0
    
    def test_get_deviation_at_setpoint(self):
        """Test deviation when at setpoint."""
        state = HomeostasisState(
            energy=DEFAULT_SETPOINTS["energy"],
            safety=DEFAULT_SETPOINTS["safety"],
            affiliation=DEFAULT_SETPOINTS["affiliation"],
            certainty=DEFAULT_SETPOINTS["certainty"],
            autonomy=DEFAULT_SETPOINTS["autonomy"],
            fairness=DEFAULT_SETPOINTS["fairness"]
        )
        manager = HomeostasisManager(initial_state=state)
        
        deviation = manager.get_deviation()
        
        for dim, dev in deviation.items():
            assert abs(dev) < 0.001  # Should be near zero
    
    def test_get_overall_error(self):
        """Test overall error computation."""
        manager = HomeostasisManager()
        error = manager.get_overall_error()
        
        assert error >= 0
        
        # At default state, should have positive error
        assert error > 0
        
        # At setpoints, should have near-zero error
        state = HomeostasisState(
            energy=DEFAULT_SETPOINTS["energy"],
            safety=DEFAULT_SETPOINTS["safety"],
            affiliation=DEFAULT_SETPOINTS["affiliation"],
            certainty=DEFAULT_SETPOINTS["certainty"],
            autonomy=DEFAULT_SETPOINTS["autonomy"],
            fairness=DEFAULT_SETPOINTS["fairness"]
        )
        manager_at_setpoint = HomeostasisManager(initial_state=state)
        error_at_setpoint = manager_at_setpoint.get_overall_error()
        
        assert error_at_setpoint < error


class TestSignal:
    """Test signal generation."""
    
    def test_signal_structure(self):
        """Test that signal has required fields."""
        manager = HomeostasisManager()
        signal = manager.signal()
        
        assert "state" in signal
        assert "deviation" in signal
        assert "stressed_dimensions" in signal
        assert "urgency" in signal
        assert "recommendations" in signal
        assert "timestamp" in signal
    
    def test_signal_no_stress(self):
        """Test signal when not stressed."""
        # Set state at setpoints
        state = HomeostasisState(
            energy=DEFAULT_SETPOINTS["energy"],
            safety=DEFAULT_SETPOINTS["safety"],
            affiliation=DEFAULT_SETPOINTS["affiliation"],
            certainty=DEFAULT_SETPOINTS["certainty"],
            autonomy=DEFAULT_SETPOINTS["autonomy"],
            fairness=DEFAULT_SETPOINTS["fairness"]
        )
        manager = HomeostasisManager(initial_state=state)
        signal = manager.signal()
        
        assert len(signal["stressed_dimensions"]) == 0
        assert signal["urgency"] == 0
    
    def test_signal_with_stress(self):
        """Test signal when stressed."""
        state = HomeostasisState(energy=0.2, safety=0.2)  # Very low
        manager = HomeostasisManager(initial_state=state)
        signal = manager.signal()
        
        assert len(signal["stressed_dimensions"]) > 0
        assert signal["urgency"] > 0
    
    def test_signal_state_matches_manager(self):
        """Test that signal state matches manager state."""
        manager = HomeostasisManager()
        manager.state.energy = 0.8
        
        signal = manager.signal()
        
        assert signal["state"]["energy"] == 0.8


class TestRecoveryCandidates:
    """Test recovery candidate generation."""
    
    def test_no_candidates_when_not_stressed(self):
        """Test no candidates when all dimensions are healthy."""
        state = HomeostasisState(
            energy=DEFAULT_SETPOINTS["energy"],
            safety=DEFAULT_SETPOINTS["safety"],
            affiliation=DEFAULT_SETPOINTS["affiliation"],
            certainty=DEFAULT_SETPOINTS["certainty"],
            autonomy=DEFAULT_SETPOINTS["autonomy"],
            fairness=DEFAULT_SETPOINTS["fairness"]
        )
        manager = HomeostasisManager(initial_state=state)
        
        candidates = manager.get_recovery_candidates()
        
        assert len(candidates) == 0
    
    def test_candidates_when_stressed(self):
        """Test candidates generated when stressed."""
        state = HomeostasisState(energy=0.2)  # Very low energy
        manager = HomeostasisManager(initial_state=state)
        
        candidates = manager.get_recovery_candidates()
        
        assert len(candidates) > 0
        # Should suggest energy-related recovery actions
        energy_candidates = [c for c in candidates if c["dimension"] == "energy"]
        assert len(energy_candidates) > 0
    
    def test_candidates_sorted_by_ratio(self):
        """Test that candidates are sorted by benefit/cost ratio."""
        state = HomeostasisState(energy=0.1, safety=0.1)
        manager = HomeostasisManager(initial_state=state)
        
        candidates = manager.get_recovery_candidates()
        
        if len(candidates) > 1:
            for i in range(len(candidates) - 1):
                assert candidates[i]["ratio"] >= candidates[i + 1]["ratio"]
    
    def test_candidate_structure(self):
        """Test that candidates have required fields."""
        state = HomeostasisState(energy=0.1)
        manager = HomeostasisManager(initial_state=state)
        
        candidates = manager.get_recovery_candidates()
        
        if candidates:
            candidate = candidates[0]
            assert "dimension" in candidate
            assert "action" in candidate
            assert "expected_benefit" in candidate
            assert "cost" in candidate
            assert "ratio" in candidate
            assert "priority" in candidate


class TestOutcomeEffects:
    """Test specific outcome effect rules."""
    
    def test_success_goal_achieved_boosts_multiple(self):
        """Test goal_achieved success boosts multiple dimensions."""
        manager = HomeostasisManager()
        
        manager.update_from_outcome({"status": "success", "reason": "goal_achieved"})
        
        # Should boost energy, safety, certainty, autonomy
        assert manager.state.energy > 0.5
        assert manager.state.safety > 0.5
        assert manager.state.certainty > 0.5
        assert manager.state.autonomy > 0.5
    
    def test_collaboration_boosts_affiliation(self):
        """Test collaboration success boosts affiliation."""
        manager = HomeostasisManager()
        
        manager.update_from_outcome({"status": "success", "reason": "collaboration"})
        
        assert manager.state.affiliation > 0.5
        assert manager.state.fairness > 0.5
    
    def test_blocked_reduces_autonomy(self):
        """Test blocked failure reduces autonomy."""
        manager = HomeostasisManager()
        
        manager.update_from_outcome({"status": "fail", "reason": "blocked"})
        
        assert manager.state.autonomy < 0.5
        assert manager.state.safety < 0.5
    
    def test_rejected_reduces_affiliation(self):
        """Test rejected failure reduces affiliation."""
        manager = HomeostasisManager()
        
        manager.update_from_outcome({"status": "fail", "reason": "rejected"})
        
        assert manager.state.affiliation < 0.5
        assert manager.state.fairness < 0.5
    
    def test_resource_exhausted_reduces_energy(self):
        """Test resource_exhausted failure reduces energy."""
        manager = HomeostasisManager()
        
        manager.update_from_outcome({"status": "fail", "reason": "resource_exhausted"})
        
        assert manager.state.energy < 0.4  # Significant drop
        assert manager.state.autonomy < 0.5


class TestDecay:
    """Test natural decay functionality."""
    
    def test_energy_decays(self):
        """Test that energy decays over time."""
        manager = HomeostasisManager(decay_rate=0.05)
        manager.state.energy = 0.8
        
        manager.apply_decay()
        
        assert manager.state.energy < 0.8
    
    def test_safety_drifts_to_neutral(self):
        """Test that safety drifts toward neutral."""
        manager = HomeostasisManager(decay_rate=0.1)
        manager.state.safety = 0.8  # Above neutral
        
        manager.apply_decay()
        
        # Should drift down toward 0.5
        assert manager.state.safety < 0.8
    
    def test_low_values_drift_up(self):
        """Test that values below neutral drift up."""
        manager = HomeostasisManager(decay_rate=0.1)
        manager.state.affiliation = 0.3  # Below neutral
        
        manager.apply_decay()
        
        # Should drift up toward 0.5
        assert manager.state.affiliation > 0.3


class TestHuberLoss:
    """Test Huber loss function."""
    
    def test_small_deviation_quadratic(self):
        """Test small deviation uses quadratic loss."""
        loss = huber_loss(0.05, delta=0.1)
        expected = 0.5 * 0.05 ** 2
        assert abs(loss - expected) < 0.0001
    
    def test_large_deviation_linear(self):
        """Test large deviation uses linear loss."""
        loss = huber_loss(0.5, delta=0.1)
        expected = 0.1 * (0.5 - 0.5 * 0.1)
        assert abs(loss - expected) < 0.0001
    
    def test_zero_deviation(self):
        """Test zero deviation gives zero loss."""
        loss = huber_loss(0.0)
        assert loss == 0.0
    
    def test_negative_deviation(self):
        """Test negative deviation (same magnitude as positive)."""
        loss_pos = huber_loss(0.5)
        loss_neg = huber_loss(-0.5)
        assert loss_pos == loss_neg


class TestCreateManagerFromEvent:
    """Test event-based manager creation."""
    
    def test_from_event_with_state(self):
        """Test creating manager from event with homeostasis_state."""
        event = {
            "tick_id": 1,
            "homeostasis_state": {
                "energy": 0.7,
                "safety": 0.8,
                "affiliation": 0.5,
                "certainty": 0.6,
                "autonomy": 0.4,
                "fairness": 0.5
            }
        }
        
        manager = create_manager_from_event(event)
        
        assert manager.state.energy == 0.7
        assert manager.state.safety == 0.8
        assert manager.state.certainty == 0.6
    
    def test_from_event_without_state(self):
        """Test creating manager from event without homeostasis_state."""
        event = {"tick_id": 1}
        
        manager = create_manager_from_event(event)
        
        # Should use defaults
        assert manager.state.energy == 0.5
        assert manager.state.safety == 0.5


class TestComputeHash:
    """Test state hash computation."""
    
    def test_same_state_same_hash(self):
        """Test that same state produces same hash."""
        state1 = HomeostasisState(energy=0.7, safety=0.8)
        state2 = HomeostasisState(energy=0.7, safety=0.8)
        
        hash1 = compute_homeostasis_hash(state1)
        hash2 = compute_homeostasis_hash(state2)
        
        assert hash1 == hash2
    
    def test_different_state_different_hash(self):
        """Test that different states produce different hashes."""
        state1 = HomeostasisState(energy=0.7)
        state2 = HomeostasisState(energy=0.8)
        
        hash1 = compute_homeostasis_hash(state1)
        hash2 = compute_homeostasis_hash(state2)
        
        assert hash1 != hash2
    
    def test_hash_length(self):
        """Test hash is 16 characters."""
        state = HomeostasisState()
        h = compute_homeostasis_hash(state)
        
        assert len(h) == 16


class TestReset:
    """Test manager reset functionality."""
    
    def test_reset_clears_state(self):
        """Test reset clears state to defaults."""
        manager = HomeostasisManager()
        manager.state.energy = 0.8
        
        manager.reset()
        
        assert manager.state.energy == 0.5
    
    def test_reset_clears_history(self):
        """Test reset clears history."""
        manager = HomeostasisManager()
        manager.update_from_outcome({"status": "success"})
        
        manager.reset()
        
        assert len(manager._history) == 0
    
    def test_reset_with_custom_state(self):
        """Test reset with custom initial state."""
        manager = HomeostasisManager()
        new_state = HomeostasisState(energy=0.9)
        
        manager.reset(initial_state=new_state)
        
        assert manager.state.energy == 0.9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
