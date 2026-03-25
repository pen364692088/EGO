"""
MVP-6.2 D3: Rhythm Scheduler Tests

≥25 tests covering:
- Rhythm action determination
- Patience calculation
- Body state impact calculation
- Signal processing
- Parameter tuning
- Integration with body state
"""
import pytest
import time
from typing import Dict, Any

# Import rhythm scheduler components
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from emotiond.rhythm_scheduler import (
    RhythmAction,
    RhythmSignal,
    RhythmParameters,
    RhythmDecision,
    RhythmScheduler,
    schedule_rhythm,
    schedule_rhythm_from_body_state,
    apply_rhythm_to_body_state,
    get_rhythm_scheduler,
    reset_rhythm_scheduler,
)


class TestRhythmAction:
    """Tests for RhythmAction enum."""
    
    def test_rhythm_action_values(self):
        """Test that all rhythm actions have correct values."""
        assert RhythmAction.RESPOND_NOW.value == "respond_now"
        assert RhythmAction.ASK_CLARIFY_THEN_WAIT.value == "ask_clarify_then_wait"
        assert RhythmAction.COOLDOWN.value == "cooldown"
    
    def test_rhythm_action_comparison(self):
        """Test rhythm action equality comparison."""
        assert RhythmAction.RESPOND_NOW == RhythmAction.RESPOND_NOW
        assert RhythmAction.RESPOND_NOW != RhythmAction.COOLDOWN


class TestRhythmSignal:
    """Tests for RhythmSignal dataclass."""
    
    def test_default_signal_values(self):
        """Test default signal values."""
        signal = RhythmSignal()
        assert signal.time_passed_seconds == 0.0
        assert signal.user_burst_count == 0
        assert signal.tool_failure_count == 0
        assert signal.tool_attempt_count == 0
        assert signal.energy == 0.5
        assert signal.focus_fatigue == 0.3
        assert signal.boredom == 0.0
        assert signal.curiosity == 0.0
        assert signal.safety_stress == 0.5
        assert signal.last_rhythm_action is None
    
    def test_signal_to_dict(self):
        """Test signal serialization to dict."""
        signal = RhythmSignal(
            time_passed_seconds=5.0,
            user_burst_count=3,
            energy=0.7,
            focus_fatigue=0.4,
        )
        d = signal.to_dict()
        assert d["time_passed_seconds"] == 5.0
        assert d["user_burst_count"] == 3
        assert d["energy"] == 0.7
        assert d["focus_fatigue"] == 0.4
    
    def test_signal_custom_values(self):
        """Test signal with custom values."""
        signal = RhythmSignal(
            time_passed_seconds=10.0,
            user_burst_count=5,
            tool_failure_count=2,
            tool_attempt_count=4,
            energy=0.3,
            focus_fatigue=0.8,
            boredom=0.4,
            curiosity=0.6,
            safety_stress=0.2,
            last_rhythm_action="respond_now",
        )
        assert signal.time_passed_seconds == 10.0
        assert signal.user_burst_count == 5
        assert signal.tool_failure_count == 2
        assert signal.tool_attempt_count == 4
        assert signal.energy == 0.3
        assert signal.focus_fatigue == 0.8
        assert signal.boredom == 0.4
        assert signal.curiosity == 0.6
        assert signal.safety_stress == 0.2
        assert signal.last_rhythm_action == "respond_now"


class TestRhythmParameters:
    """Tests for RhythmParameters dataclass."""
    
    def test_default_parameters(self):
        """Test default parameter values."""
        params = RhythmParameters()
        assert params.patience_base_seconds == 2.0
        assert params.patience_fatigue_factor == 0.5
        assert params.patience_energy_factor == 0.3
        assert params.burst_threshold == 3
        assert params.burst_cooldown_multiplier == 2.0
        assert params.tool_failure_threshold == 0.5
        assert params.tool_failure_cooldown_multiplier == 3.0
        assert params.focus_fatigue_respond_threshold == 0.7
        assert params.focus_fatigue_clarify_threshold == 0.85
        assert params.energy_respond_threshold == 0.3
        assert params.energy_clarify_threshold == 0.15
        assert params.safety_stress_respond_threshold == 0.3
        assert params.boredom_patience_reduction == 0.3
        assert params.curiosity_patience_increase == 0.2
        assert params.cooldown_duration_seconds == 5.0
    
    def test_parameters_to_dict(self):
        """Test parameters serialization."""
        params = RhythmParameters()
        d = params.to_dict()
        assert "patience_base_seconds" in d
        assert "burst_threshold" in d
        assert d["patience_base_seconds"] == 2.0
    
    def test_parameters_from_dict(self):
        """Test parameters deserialization."""
        data = {
            "patience_base_seconds": 3.0,
            "burst_threshold": 5,
            "focus_fatigue_respond_threshold": 0.6,
        }
        params = RhythmParameters.from_dict(data)
        assert params.patience_base_seconds == 3.0
        assert params.burst_threshold == 5
        assert params.focus_fatigue_respond_threshold == 0.6
        # Other values should use defaults
        assert params.patience_fatigue_factor == 0.5
    
    def test_parameters_partial_from_dict(self):
        """Test parameters from_dict with partial data."""
        data = {"patience_base_seconds": 1.5}
        params = RhythmParameters.from_dict(data)
        assert params.patience_base_seconds == 1.5
        assert params.burst_threshold == 3  # Default


class TestRhythmSchedulerBasic:
    """Basic tests for RhythmScheduler."""
    
    def setup_method(self):
        """Reset scheduler before each test."""
        reset_rhythm_scheduler()
    
    def test_scheduler_creation(self):
        """Test scheduler initialization."""
        scheduler = RhythmScheduler()
        assert scheduler is not None
        assert scheduler.parameters is not None
    
    def test_scheduler_with_custom_params(self):
        """Test scheduler with custom parameters."""
        params = RhythmParameters(patience_base_seconds=5.0)
        scheduler = RhythmScheduler(parameters=params)
        assert scheduler.parameters.patience_base_seconds == 5.0
    
    def test_schedule_normal_conditions(self):
        """Test scheduling under normal conditions."""
        scheduler = RhythmScheduler()
        signal = RhythmSignal(
            energy=0.7,
            focus_fatigue=0.3,
            safety_stress=0.6,
        )
        decision = scheduler.schedule(signal)
        assert decision.action == RhythmAction.RESPOND_NOW
        assert decision.confidence > 0.9
    
    def test_schedule_high_fatigue(self):
        """Test scheduling with high focus fatigue."""
        scheduler = RhythmScheduler()
        signal = RhythmSignal(
            energy=0.7,
            focus_fatigue=0.9,  # Above clarify threshold
            safety_stress=0.6,
        )
        decision = scheduler.schedule(signal)
        assert decision.action == RhythmAction.ASK_CLARIFY_THEN_WAIT
    
    def test_schedule_low_energy(self):
        """Test scheduling with low energy."""
        scheduler = RhythmScheduler()
        signal = RhythmSignal(
            energy=0.1,  # Below clarify threshold
            focus_fatigue=0.3,
            safety_stress=0.6,
        )
        decision = scheduler.schedule(signal)
        assert decision.action == RhythmAction.ASK_CLARIFY_THEN_WAIT
    
    def test_schedule_moderate_fatigue(self):
        """Test scheduling with moderate fatigue (cooldown)."""
        scheduler = RhythmScheduler()
        signal = RhythmSignal(
            energy=0.7,
            focus_fatigue=0.75,  # Above respond threshold, below clarify
            safety_stress=0.6,
        )
        decision = scheduler.schedule(signal)
        assert decision.action == RhythmAction.COOLDOWN
    
    def test_schedule_low_energy_cooldown(self):
        """Test scheduling with moderately low energy (cooldown)."""
        scheduler = RhythmScheduler()
        signal = RhythmSignal(
            energy=0.25,  # Below respond threshold, above clarify
            focus_fatigue=0.3,
            safety_stress=0.6,
        )
        decision = scheduler.schedule(signal)
        assert decision.action == RhythmAction.COOLDOWN
    
    def test_schedule_low_safety_stress(self):
        """Test scheduling with low safety/stress."""
        scheduler = RhythmScheduler()
        signal = RhythmSignal(
            energy=0.7,
            focus_fatigue=0.3,
            safety_stress=0.2,  # Below threshold
        )
        decision = scheduler.schedule(signal)
        assert decision.action == RhythmAction.COOLDOWN
    
    def test_schedule_user_burst(self):
        """Test scheduling during user burst."""
        scheduler = RhythmScheduler()
        signal = RhythmSignal(
            energy=0.7,
            focus_fatigue=0.3,
            safety_stress=0.6,
            user_burst_count=5,  # Above burst threshold
        )
        decision = scheduler.schedule(signal)
        assert decision.action == RhythmAction.COOLDOWN
    
    def test_schedule_high_tool_failure_rate(self):
        """Test scheduling with high tool failure rate."""
        scheduler = RhythmScheduler()
        signal = RhythmSignal(
            energy=0.7,
            focus_fatigue=0.3,
            safety_stress=0.6,
            tool_failure_count=3,
            tool_attempt_count=5,  # 60% failure rate
        )
        decision = scheduler.schedule(signal)
        assert decision.action == RhythmAction.COOLDOWN
    
    def test_schedule_zero_tool_attempts(self):
        """Test scheduling with zero tool attempts."""
        scheduler = RhythmScheduler()
        signal = RhythmSignal(
            energy=0.7,
            focus_fatigue=0.3,
            safety_stress=0.6,
            tool_failure_count=0,
            tool_attempt_count=0,
        )
        decision = scheduler.schedule(signal)
        # Should not trigger cooldown due to tool failures
        assert decision.action == RhythmAction.RESPOND_NOW
    
    def test_patience_calculation_base(self):
        """Test base patience calculation."""
        scheduler = RhythmScheduler()
        signal = RhythmSignal(
            energy=0.5,
            focus_fatigue=0.0,
        )
        decision = scheduler.schedule(signal)
        # Base patience is 2.0s with no modifiers
        assert decision.patience_required >= 0.1
    
    def test_patience_with_fatigue(self):
        """Test patience increases with fatigue."""
        scheduler = RhythmScheduler()
        signal_low_fatigue = RhythmSignal(energy=0.5, focus_fatigue=0.1)
        signal_high_fatigue = RhythmSignal(energy=0.5, focus_fatigue=0.8)
        
        decision_low = scheduler.schedule(signal_low_fatigue)
        decision_high = scheduler.schedule(signal_high_fatigue)
        
        # Higher fatigue should result in higher patience
        assert decision_high.patience_required > decision_low.patience_required
    
    def test_patience_with_low_energy(self):
        """Test patience increases with low energy."""
        scheduler = RhythmScheduler()
        signal_normal = RhythmSignal(energy=0.7, focus_fatigue=0.3)
        signal_low = RhythmSignal(energy=0.2, focus_fatigue=0.3)
        
        decision_normal = scheduler.schedule(signal_normal)
        decision_low = scheduler.schedule(signal_low)
        
        # Lower energy should result in higher patience
        assert decision_low.patience_required > decision_normal.patience_required
    
    def test_patience_with_burst(self):
        """Test patience increases during user burst."""
        scheduler = RhythmScheduler()
        signal_normal = RhythmSignal(energy=0.5, user_burst_count=1)
        signal_burst = RhythmSignal(energy=0.5, user_burst_count=5)
        
        decision_normal = scheduler.schedule(signal_normal)
        decision_burst = scheduler.schedule(signal_burst)
        
        # Burst should result in higher patience
        assert decision_burst.patience_required > decision_normal.patience_required
    
    def test_patience_with_boredom(self):
        """Test patience decreases with boredom."""
        scheduler = RhythmScheduler()
        signal_normal = RhythmSignal(energy=0.5, boredom=0.0)
        signal_bored = RhythmSignal(energy=0.5, boredom=0.8)
        
        decision_normal = scheduler.schedule(signal_normal)
        decision_bored = scheduler.schedule(signal_bored)
        
        # Boredom should reduce patience (respond faster)
        assert decision_bored.patience_required < decision_normal.patience_required
    
    def test_patience_with_curiosity(self):
        """Test patience increases with curiosity."""
        scheduler = RhythmScheduler()
        signal_normal = RhythmSignal(energy=0.5, curiosity=0.0)
        signal_curious = RhythmSignal(energy=0.5, curiosity=0.8)
        
        decision_normal = scheduler.schedule(signal_normal)
        decision_curious = scheduler.schedule(signal_curious)
        
        # Curiosity should increase patience (wait for more info)
        assert decision_curious.patience_required > decision_normal.patience_required


class TestRhythmBodyStateImpacts:
    """Tests for body state impact calculation."""
    
    def test_impacts_respond_now(self):
        """Test body state impacts for respond_now."""
        scheduler = RhythmScheduler()
        signal = RhythmSignal(energy=0.7, focus_fatigue=0.3)
        decision = scheduler.schedule(signal)
        
        assert decision.action == RhythmAction.RESPOND_NOW
        assert decision.body_state_impacts["energy"] < 0  # Costs energy
        assert decision.body_state_impacts["focus_fatigue"] > 0  # Increases fatigue
    
    def test_impacts_clarify(self):
        """Test body state impacts for ask_clarify_then_wait."""
        scheduler = RhythmScheduler()
        signal = RhythmSignal(energy=0.1, focus_fatigue=0.3)  # Low energy triggers clarify
        decision = scheduler.schedule(signal)
        
        assert decision.action == RhythmAction.ASK_CLARIFY_THEN_WAIT
        # Clarify is less costly than respond
        assert abs(decision.body_state_impacts["energy"]) <= 0.01
    
    def test_impacts_cooldown(self):
        """Test body state impacts for cooldown."""
        scheduler = RhythmScheduler()
        signal = RhythmSignal(energy=0.7, focus_fatigue=0.75)
        decision = scheduler.schedule(signal)
        
        assert decision.action == RhythmAction.COOLDOWN
        # Cooldown allows recovery
        assert decision.body_state_impacts["focus_fatigue"] < 0
        assert decision.body_state_impacts["energy"] > 0
    
    def test_impacts_burst_penalty(self):
        """Test additional fatigue during burst."""
        scheduler = RhythmScheduler()
        signal = RhythmSignal(energy=0.7, focus_fatigue=0.3, user_burst_count=3)
        decision = scheduler.schedule(signal)
        
        # Burst should add extra fatigue cost
        if decision.action == RhythmAction.RESPOND_NOW:
            assert decision.body_state_impacts["focus_fatigue"] > 0.02


class TestRhythmSchedulerHistory:
    """Tests for decision history tracking."""
    
    def setup_method(self):
        """Reset scheduler before each test."""
        reset_rhythm_scheduler()
    
    def test_decision_history_recorded(self):
        """Test that decisions are recorded in history."""
        scheduler = RhythmScheduler()
        signal = RhythmSignal()
        decision = scheduler.schedule(signal)
        
        history = scheduler.get_decision_history()
        assert len(history) == 1
        assert history[0].action == decision.action
    
    def test_decision_history_limit(self):
        """Test history limit enforcement."""
        scheduler = RhythmScheduler()
        
        # Make many decisions
        for i in range(150):
            signal = RhythmSignal(energy=0.5 + i * 0.001)
            scheduler.schedule(signal)
        
        history = scheduler.get_decision_history(limit=50)
        assert len(history) == 50
    
    def test_statistics_empty(self):
        """Test statistics with no history."""
        scheduler = RhythmScheduler()
        stats = scheduler.get_statistics()
        
        assert stats["total_decisions"] == 0
        assert stats["average_confidence"] == 0.0
    
    def test_statistics_with_decisions(self):
        """Test statistics calculation."""
        scheduler = RhythmScheduler()
        
        # Make several decisions
        for _ in range(5):
            signal = RhythmSignal()
            scheduler.schedule(signal)
        
        stats = scheduler.get_statistics()
        assert stats["total_decisions"] == 5
        assert stats["average_confidence"] > 0
        assert stats["average_patience"] > 0
    
    def test_statistics_action_distribution(self):
        """Test action distribution in statistics."""
        scheduler = RhythmScheduler()
        
        # Mix of decisions
        scheduler.schedule(RhythmSignal(energy=0.7, focus_fatigue=0.3))  # respond_now
        scheduler.schedule(RhythmSignal(energy=0.1, focus_fatigue=0.3))  # clarify
        scheduler.schedule(RhythmSignal(energy=0.7, focus_fatigue=0.3))  # respond_now
        
        stats = scheduler.get_statistics()
        assert "respond_now" in stats["action_distribution"]
        assert "ask_clarify_then_wait" in stats["action_distribution"]


class TestRhythmConvenienceFunctions:
    """Tests for convenience functions."""
    
    def setup_method(self):
        """Reset scheduler before each test."""
        reset_rhythm_scheduler()
    
    def test_schedule_rhythm_function(self):
        """Test schedule_rhythm convenience function."""
        decision = schedule_rhythm(
            energy=0.7,
            focus_fatigue=0.3,
            safety_stress=0.6,
        )
        assert decision.action == RhythmAction.RESPOND_NOW
    
    def test_schedule_rhythm_with_burst(self):
        """Test schedule_rhythm with burst."""
        decision = schedule_rhythm(
            energy=0.7,
            focus_fatigue=0.3,
            user_burst_count=5,
        )
        assert decision.action == RhythmAction.COOLDOWN
    
    def test_get_and_reset_scheduler(self):
        """Test get and reset scheduler functions."""
        scheduler1 = get_rhythm_scheduler()
        scheduler2 = get_rhythm_scheduler()
        assert scheduler1 is scheduler2
        
        reset_scheduler = reset_rhythm_scheduler()
        scheduler3 = get_rhythm_scheduler()
        assert scheduler3 is reset_scheduler
        assert scheduler3 is not scheduler1


class MockBodyStateDimension:
    """Mock body state dimension for testing."""
    def __init__(self, value: float = 0.5):
        self.value = value
    
    def update(self, delta: float):
        self.value = max(0.0, min(1.0, self.value + delta))


class MockBodyState:
    """Mock body state for testing."""
    def __init__(self, energy=0.5, focus_fatigue=0.3, safety_stress=0.5):
        self.energy = MockBodyStateDimension(energy)
        self.focus_fatigue = MockBodyStateDimension(focus_fatigue)
        self.safety_stress = MockBodyStateDimension(safety_stress)


class TestRhythmBodyStateIntegration:
    """Tests for body state integration."""
    
    def test_schedule_from_body_state(self):
        """Test scheduling from body state object."""
        body_state = MockBodyState(energy=0.7, focus_fatigue=0.3)
        decision = schedule_rhythm_from_body_state(body_state)
        assert decision.action == RhythmAction.RESPOND_NOW
    
    def test_schedule_from_body_state_high_fatigue(self):
        """Test scheduling from body state with high fatigue."""
        body_state = MockBodyState(energy=0.7, focus_fatigue=0.9)
        decision = schedule_rhythm_from_body_state(body_state)
        assert decision.action == RhythmAction.ASK_CLARIFY_THEN_WAIT
    
    def test_apply_rhythm_to_body_state(self):
        """Test applying rhythm decision to body state."""
        body_state = MockBodyState(energy=0.7, focus_fatigue=0.3)
        
        # Create a decision
        scheduler = RhythmScheduler()
        signal = RhythmSignal(energy=0.7, focus_fatigue=0.3)
        decision = scheduler.schedule(signal)
        
        initial_energy = body_state.energy.value
        initial_fatigue = body_state.focus_fatigue.value
        
        applied = apply_rhythm_to_body_state(body_state, decision)
        
        # Check that impacts were applied
        assert len(applied) > 0
        if "energy" in applied:
            assert body_state.energy.value != initial_energy
    
    def test_apply_rhythm_cooldown_recovery(self):
        """Test that cooldown allows body state recovery."""
        body_state = MockBodyState(energy=0.5, focus_fatigue=0.8)
        
        scheduler = RhythmScheduler()
        signal = RhythmSignal(energy=0.5, focus_fatigue=0.8)
        decision = scheduler.schedule(signal)
        
        if decision.action == RhythmAction.COOLDOWN:
            initial_fatigue = body_state.focus_fatigue.value
            apply_rhythm_to_body_state(body_state, decision)
            # Cooldown should reduce fatigue
            assert body_state.focus_fatigue.value < initial_fatigue


class TestRhythmEdgeCases:
    """Edge case tests."""
    
    def test_extreme_fatigue(self):
        """Test with extreme fatigue value."""
        scheduler = RhythmScheduler()
        signal = RhythmSignal(focus_fatigue=1.0)
        decision = scheduler.schedule(signal)
        assert decision.action == RhythmAction.ASK_CLARIFY_THEN_WAIT
    
    def test_zero_energy(self):
        """Test with zero energy."""
        scheduler = RhythmScheduler()
        signal = RhythmSignal(energy=0.0)
        decision = scheduler.schedule(signal)
        assert decision.action == RhythmAction.ASK_CLARIFY_THEN_WAIT
    
    def test_extreme_burst(self):
        """Test with extreme user burst."""
        scheduler = RhythmScheduler()
        signal = RhythmSignal(user_burst_count=100)
        decision = scheduler.schedule(signal)
        assert decision.action == RhythmAction.COOLDOWN
    
    def test_perfect_tool_failure(self):
        """Test with 100% tool failure rate."""
        scheduler = RhythmScheduler()
        signal = RhythmSignal(
            tool_failure_count=10,
            tool_attempt_count=10,
        )
        decision = scheduler.schedule(signal)
        assert decision.action == RhythmAction.COOLDOWN
    
    def test_boundary_thresholds(self):
        """Test at exact threshold boundaries."""
        scheduler = RhythmScheduler()
        
        # At exactly the threshold
        signal = RhythmSignal(
            focus_fatigue=0.7,  # Exactly at respond threshold
            energy=0.7,
        )
        decision = scheduler.schedule(signal)
        # Should trigger cooldown at or above threshold
        assert decision.action in [RhythmAction.COOLDOWN, RhythmAction.ASK_CLARIFY_THEN_WAIT]
    
    def test_multiple_conditions(self):
        """Test with multiple triggering conditions."""
        scheduler = RhythmScheduler()
        signal = RhythmSignal(
            energy=0.2,  # Low energy
            focus_fatigue=0.8,  # High fatigue
            safety_stress=0.1,  # Low safety
            user_burst_count=5,  # Burst
        )
        decision = scheduler.schedule(signal)
        # Should trigger some form of non-respond action
        assert decision.action != RhythmAction.RESPOND_NOW
        assert len(decision.reason.split(";")) >= 2  # Multiple reasons


class TestRhythmDecisionStructure:
    """Tests for decision data structure."""
    
    def test_decision_has_timestamp(self):
        """Test that decision has timestamp."""
        scheduler = RhythmScheduler()
        signal = RhythmSignal()
        decision = scheduler.schedule(signal)
        
        assert hasattr(decision, 'timestamp')
        assert decision.timestamp > 0
    
    def test_decision_to_dict(self):
        """Test decision serialization."""
        scheduler = RhythmScheduler()
        signal = RhythmSignal()
        decision = scheduler.schedule(signal)
        
        d = decision.to_dict()
        assert "action" in d
        assert "patience_required" in d
        assert "reason" in d
        assert "confidence" in d
        assert "body_state_impacts" in d
        assert "signal_snapshot" in d
        assert "parameters_snapshot" in d
        assert "timestamp" in d
    
    def test_decision_confidence_range(self):
        """Test that confidence is in valid range."""
        scheduler = RhythmScheduler()
        
        for _ in range(10):
            signal = RhythmSignal(
                energy=0.3 + 0.04 * _,
                focus_fatigue=0.2 + 0.07 * _,
            )
            decision = scheduler.schedule(signal)
            assert 0.0 <= decision.confidence <= 1.0
    
    def test_decision_reason_not_empty(self):
        """Test that decision reason is not empty."""
        scheduler = RhythmScheduler()
        signal = RhythmSignal()
        decision = scheduler.schedule(signal)
        
        assert decision.reason
        assert len(decision.reason) > 0


class TestRhythmParameterUpdates:
    """Tests for parameter updates."""
    
    def test_update_parameters(self):
        """Test updating scheduler parameters."""
        scheduler = RhythmScheduler()
        
        new_params = RhythmParameters(patience_base_seconds=10.0)
        scheduler.update_parameters(new_params)
        
        assert scheduler.parameters.patience_base_seconds == 10.0
    
    def test_parameter_update_affects_scheduling(self):
        """Test that parameter update affects subsequent scheduling."""
        scheduler = RhythmScheduler()
        
        # First decision with default params
        signal = RhythmSignal(energy=0.5, focus_fatigue=0.5)
        decision1 = scheduler.schedule(signal)
        
        # Update params to be more conservative
        new_params = RhythmParameters(
            focus_fatigue_respond_threshold=0.4,  # Lower threshold
        )
        scheduler.update_parameters(new_params)
        
        # Same signal should now trigger different action
        decision2 = scheduler.schedule(signal)
        
        # With lower threshold, should be more conservative
        if decision1.action == RhythmAction.RESPOND_NOW:
            assert decision2.action != RhythmAction.RESPOND_NOW


class TestRhythmSchedulerSerialization:
    """Tests for scheduler serialization."""
    
    def test_scheduler_to_dict(self):
        """Test scheduler serialization."""
        scheduler = RhythmScheduler()
        scheduler.schedule(RhythmSignal())
        
        d = scheduler.to_dict()
        assert "parameters" in d
        assert "statistics" in d
    
    def test_scheduler_dict_content(self):
        """Test scheduler dict content."""
        scheduler = RhythmScheduler()
        
        # Make some decisions
        for i in range(3):
            scheduler.schedule(RhythmSignal(energy=0.5 + i * 0.1))
        
        d = scheduler.to_dict()
        stats = d["statistics"]
        assert stats["total_decisions"] == 3


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
