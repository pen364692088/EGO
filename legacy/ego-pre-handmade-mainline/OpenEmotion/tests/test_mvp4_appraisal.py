"""
MVP-4 D2: Appraisal Engine Tests

Tests for the 5-dimensional appraisal system.
"""
import pytest
import os
import sys

# Set test environment
os.environ["EMOTIOND_DISABLE_CORE"] = "0"
os.environ["EMOTIOND_DB_PATH"] = ":memory:"

from emotiond.models import Event
from emotiond.appraisal import (
    appraise_event,
    AppraisalResult,
    AppraisalContext,
    create_context_from_state,
    compute_goal_progress,
    compute_expectation_violation,
    compute_controllability,
    compute_social_threat,
    compute_novelty,
    EVENT_APPRAISAL_SIGNATURES
)
from emotiond.state import AffectState, MoodState, BondState


class TestAppraisalResult:
    """Tests for AppraisalResult model."""
    
    def test_default_values(self):
        """Test default appraisal result values."""
        result = AppraisalResult()
        assert result.goal_progress == 0.0
        assert result.expectation_violation == 0.0
        assert result.controllability == 0.5
        assert result.social_threat == 0.0
        assert result.novelty == 0.0
        assert result.emotion_label == "neutral"
        assert result.intensity == 0.0
        assert isinstance(result.reasoning, list)
    
    def test_valid_ranges(self):
        """Test that values are validated within ranges."""
        # Valid values should work
        result = AppraisalResult(goal_progress=0.5, expectation_violation=0.3)
        assert result.goal_progress == 0.5
        
        # Boundary values should work
        result = AppraisalResult(goal_progress=1.0, expectation_violation=1.0)
        assert result.goal_progress == 1.0
        
        result = AppraisalResult(goal_progress=-1.0)
        assert result.goal_progress == -1.0
        
        # Values outside range should raise validation error
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AppraisalResult(goal_progress=2.0)


class TestComputeGoalProgress:
    """Tests for goal_progress dimension computation."""
    
    def test_base_value_from_subtype(self):
        """Test that base value is derived from event subtype."""
        event = Event(
            type="world_event",
            actor="user",
            target="assistant",
            meta={"subtype": "care"}
        )
        context = AppraisalContext()
        value, reason = compute_goal_progress(event, context, 0.4)
        assert value >= 0.3  # Care should be positive
    
    def test_promise_break_negative(self):
        """Test that promise break results in negative goal progress."""
        event = Event(
            type="user_message",
            actor="user",
            target="assistant",
            text="算了"
        )
        context = AppraisalContext(
            promise_state={"broken": True, "made": True}
        )
        value, reason = compute_goal_progress(event, context, 0.0)
        assert value < 0
        assert "promise" in reason.lower() or "blocked" in reason.lower()
    
    def test_agreement_positive(self):
        """Test that agreement results in positive goal progress."""
        event = Event(
            type="user_message",
            actor="user",
            target="assistant",
            text="好的，没问题"
        )
        context = AppraisalContext()
        value, reason = compute_goal_progress(event, context, 0.0)
        assert value > 0
    
    def test_dismissive_negative(self):
        """Test that dismissive language results in negative goal progress."""
        event = Event(
            type="user_message",
            actor="user",
            target="assistant",
            text="算了，不用了"
        )
        context = AppraisalContext()
        value, reason = compute_goal_progress(event, context, 0.0)
        assert value < 0
    
    def test_cold_treatment_duration(self):
        """Test that cold treatment duration affects goal progress."""
        event = Event(
            type="user_message",
            actor="user",
            target="assistant",
            text="好"
        )
        
        # Short cold treatment
        context_short = AppraisalContext(cold_treatment_duration=600)  # 10 min
        value_short, _ = compute_goal_progress(event, context_short, 0.0)
        
        # Long cold treatment
        context_long = AppraisalContext(cold_treatment_duration=7200)  # 2 hours
        value_long, _ = compute_goal_progress(event, context_long, 0.0)
        
        # Longer cold treatment should amplify relief
        assert value_long >= value_short


class TestComputeExpectationViolation:
    """Tests for expectation_violation dimension computation."""
    
    def test_promise_break_high_violation(self):
        """Test that promise break results in high expectation violation."""
        event = Event(
            type="user_message",
            actor="user",
            target="assistant",
            text="算了"
        )
        context = AppraisalContext(
            promise_state={"broken": True}
        )
        value, reason = compute_expectation_violation(event, context, 0.0)
        assert value > 0.5
    
    def test_broken_commitment_language(self):
        """Test that broken commitment language increases violation."""
        event = Event(
            type="user_message",
            actor="user",
            target="assistant",
            text="本来答应好的，但是算了"
        )
        context = AppraisalContext()
        value, reason = compute_expectation_violation(event, context, 0.0)
        assert value > 0.3
    
    def test_high_bond_unexpected_rejection(self):
        """Test that rejection from high bond is more unexpected."""
        event = Event(
            type="user_message",
            actor="user",
            target="assistant",
            text="算了"
        )
        
        # High bond context
        context_high_bond = AppraisalContext(
            bond={"bond": 0.8, "trust": 0.7, "grudge": 0.0}
        )
        value_high, _ = compute_expectation_violation(event, context_high_bond, 0.0)
        
        # Low bond context
        context_low_bond = AppraisalContext(
            bond={"bond": 0.1, "trust": 0.2, "grudge": 0.3}
        )
        value_low, _ = compute_expectation_violation(event, context_low_bond, 0.0)
        
        # High bond should result in more violation
        assert value_high >= value_low
    
    def test_low_trust_reduces_expectation(self):
        """Test that low trust reduces expectation of good behavior."""
        event = Event(
            type="world_event",
            actor="user",
            target="assistant",
            meta={"subtype": "rejection"}
        )
        context = AppraisalContext(
            bond={"trust": 0.1}
        )
        value, reason = compute_expectation_violation(event, context, 0.5)
        assert "trust" in reason.lower() or value < 0.5


class TestComputeControllability:
    """Tests for controllability dimension computation."""
    
    def test_user_message_moderate_control(self):
        """Test that user messages have moderate controllability."""
        event = Event(
            type="user_message",
            actor="user",
            target="assistant",
            text="hello"
        )
        context = AppraisalContext()
        value, reason = compute_controllability(event, context, 0.5)
        assert value >= 0.4
        assert "control" in reason.lower()
    
    def test_assistant_reply_high_control(self):
        """Test that assistant replies have high controllability."""
        event = Event(
            type="assistant_reply",
            actor="assistant",
            target="user",
            text="I understand"
        )
        context = AppraisalContext()
        value, reason = compute_controllability(event, context, 0.5)
        assert value >= 0.7
    
    def test_time_passed_zero_control(self):
        """Test that time_passed events have zero controllability."""
        event = Event(
            type="world_event",
            actor="system",
            target="assistant",
            meta={"subtype": "time_passed", "seconds": 60}
        )
        context = AppraisalContext()
        value, reason = compute_controllability(event, context, 0.5)
        assert value == 0.0
    
    def test_betrayal_low_control(self):
        """Test that betrayal events have low controllability."""
        event = Event(
            type="world_event",
            actor="user",
            target="assistant",
            meta={"subtype": "betrayal"}
        )
        context = AppraisalContext()
        value, reason = compute_controllability(event, context, 0.5)
        assert value <= 0.4


class TestComputeSocialThreat:
    """Tests for social_threat dimension computation."""
    
    def test_betrayal_high_threat(self):
        """Test that betrayal events have high social threat."""
        event = Event(
            type="world_event",
            actor="user",
            target="assistant",
            meta={"subtype": "betrayal"}
        )
        context = AppraisalContext()
        value, reason = compute_social_threat(event, context, 0.9)
        assert value >= 0.7
    
    def test_cold_treatment_threat(self):
        """Test that cold treatment duration increases threat."""
        event = Event(
            type="user_message",
            actor="user",
            target="assistant",
            text="算了"
        )
        
        # Long cold treatment
        context = AppraisalContext(cold_treatment_duration=7200)  # 2 hours
        value, reason = compute_social_threat(event, context, 0.0)
        assert value > 0.5
    
    def test_high_threat_language(self):
        """Test that high threat language increases social threat."""
        event = Event(
            type="user_message",
            actor="user",
            target="assistant",
            text="我讨厌你，我们结束吧"
        )
        context = AppraisalContext()
        value, reason = compute_social_threat(event, context, 0.0)
        assert value >= 0.7
    
    def test_high_bond_amplifies_threat(self):
        """Test that high bond amplifies perceived threat."""
        event = Event(
            type="user_message",
            actor="user",
            target="assistant",
            text="算了"
        )
        
        # High bond context
        context_high_bond = AppraisalContext(
            bond={"bond": 0.8, "trust": 0.7, "grudge": 0.0}
        )
        value_high, _ = compute_social_threat(event, context_high_bond, 0.3)
        
        # Low bond context
        context_low_bond = AppraisalContext(
            bond={"bond": 0.1, "trust": 0.2, "grudge": 0.0}
        )
        value_low, _ = compute_social_threat(event, context_low_bond, 0.3)
        
        assert value_high >= value_low


class TestComputeNovelty:
    """Tests for novelty dimension computation."""
    
    def test_novel_event_type(self):
        """Test that novel event types have high novelty."""
        event = Event(
            type="world_event",
            actor="user",
            target="assistant",
            meta={"subtype": "care"}
        )
        context = AppraisalContext(
            event_history=[
                {"subtype": "rejection"},
                {"subtype": "ignored"},
                {"subtype": "rejection"},
            ]
        )
        value, reason = compute_novelty(event, context, 0.0)
        assert value >= 0.4
    
    def test_repetitive_pattern_low_novelty(self):
        """Test that repetitive patterns have low novelty."""
        event = Event(
            type="world_event",
            actor="user",
            target="assistant",
            meta={"subtype": "ignored"}
        )
        context = AppraisalContext(
            event_history=[
                {"subtype": "ignored"},
                {"subtype": "ignored"},
                {"subtype": "ignored"},
                {"subtype": "ignored"},
            ]
        )
        value, reason = compute_novelty(event, context, 0.5)
        assert value <= 0.2
    
    def test_explicit_novelty_language(self):
        """Test that explicit novelty language increases novelty."""
        event = Event(
            type="user_message",
            actor="user",
            target="assistant",
            text="没想到会这样！真是个惊喜"
        )
        context = AppraisalContext()
        value, reason = compute_novelty(event, context, 0.0)
        assert value >= 0.5
    
    def test_repetitive_language(self):
        """Test that repetitive language reduces novelty."""
        event = Event(
            type="user_message",
            actor="user",
            target="assistant",
            text="又是这样，每次都一样"
        )
        context = AppraisalContext()
        value, reason = compute_novelty(event, context, 0.5)
        assert value <= 0.3


class TestAppraiseEvent:
    """Tests for the main appraise_event function."""
    
    def test_basic_appraisal(self):
        """Test basic event appraisal."""
        event = Event(
            type="world_event",
            actor="user",
            target="assistant",
            meta={"subtype": "care"}
        )
        result = appraise_event(event)
        
        assert isinstance(result, AppraisalResult)
        assert result.goal_progress >= 0
        assert result.expectation_violation >= 0
        assert result.controllability >= 0
        assert result.social_threat >= 0
        assert result.novelty >= 0
        assert len(result.reasoning) > 0
    
    def test_appraisal_with_context(self):
        """Test appraisal with full context."""
        event = Event(
            type="user_message",
            actor="user",
            target="assistant",
            text="算了"
        )
        
        affect = AffectState(valence=-0.3, arousal=0.5, anger=0.3)
        mood = MoodState(valence=-0.1, arousal=0.3)
        bond = BondState(target="user", bond=0.5, trust=0.4, grudge=0.2)
        
        result = appraise_event(event, affect=affect, mood=mood, bond=bond)
        
        assert isinstance(result, AppraisalResult)
        # Should have valid appraisal dimensions
        assert -1 <= result.goal_progress <= 1
        assert 0 <= result.expectation_violation <= 1
    
    def test_care_event_positive(self):
        """Test that care events result in positive appraisal."""
        event = Event(
            type="world_event",
            actor="user",
            target="assistant",
            meta={"subtype": "care"}
        )
        result = appraise_event(event)
        
        assert result.goal_progress > 0
        assert result.social_threat < 0.5
        # Emotion should be positive or low arousal
        assert result.emotion_label in ["joy", "neutral", "curiosity", "boredom"]
    
    def test_betrayal_event_negative(self):
        """Test that betrayal events result in negative appraisal."""
        event = Event(
            type="world_event",
            actor="user",
            target="assistant",
            meta={"subtype": "betrayal"}
        )
        result = appraise_event(event)
        
        assert result.goal_progress < 0
        assert result.expectation_violation > 0.5
        assert result.social_threat > 0.5
    
    def test_scenario_suanle_with_promise(self):
        """
        Scenario test: "算了" with promise break.
        Should result in negative goal_progress and high expectation_violation.
        """
        event = Event(
            type="user_message",
            actor="user",
            target="assistant",
            text="算了"
        )
        context = AppraisalContext(
            promise_state={"broken": True, "made": True}
        )
        result = appraise_event(event, context=context)
        
        assert result.goal_progress < 0
        assert result.expectation_violation > 0.5
    
    def test_scenario_suanle_without_promise(self):
        """
        Scenario test: "算了" without promise.
        Should be less severe than with promise.
        """
        event = Event(
            type="user_message",
            actor="user",
            target="assistant",
            text="算了"
        )
        context = AppraisalContext()
        result = appraise_event(event, context=context)
        
        # Without promise, should still be negative but less so
        assert result.goal_progress < 0
        # Compare with promise break scenario
        result_with_promise = appraise_event(
            event,
            context=AppraisalContext(promise_state={"broken": True})
        )
        assert result.expectation_violation < result_with_promise.expectation_violation
    
    def test_scenario_suanle_after_cold_treatment(self):
        """
        Scenario test: "算了" after long cold treatment.
        Should result in high social_threat and more negative appraisal.
        """
        event = Event(
            type="user_message",
            actor="user",
            target="assistant",
            text="算了"
        )
        context = AppraisalContext(cold_treatment_duration=7200)  # 2 hours
        result = appraise_event(event, context=context)
        
        assert result.social_threat > 0.3
        assert result.goal_progress < 0
    
    def test_observed_delta_computation(self):
        """Test that observed_delta is computed correctly."""
        event = Event(
            type="world_event",
            actor="user",
            target="assistant",
            meta={"subtype": "care"}
        )
        result = appraise_event(event)
        
        assert "safety" in result.observed_delta
        assert "energy" in result.observed_delta
        # Care should improve both
        assert result.observed_delta["safety"] > 0


class TestEventAppraisalSignatures:
    """Tests for event subtype appraisal signatures."""
    
    def test_care_signature(self):
        """Test care event signature."""
        sig = EVENT_APPRAISAL_SIGNATURES["care"]
        assert sig["goal_progress"] > 0
        assert sig["expectation_violation"] == 0
        assert sig["social_threat"] == 0
    
    def test_betrayal_signature(self):
        """Test betrayal event signature."""
        sig = EVENT_APPRAISAL_SIGNATURES["betrayal"]
        assert sig["goal_progress"] < 0
        assert sig["expectation_violation"] > 0.5
        assert sig["social_threat"] > 0.5
    
    def test_rejection_signature(self):
        """Test rejection event signature."""
        sig = EVENT_APPRAISAL_SIGNATURES["rejection"]
        assert sig["goal_progress"] < 0
        assert sig["social_threat"] > 0.5
    
    def test_time_passed_signature(self):
        """Test time_passed event signature."""
        sig = EVENT_APPRAISAL_SIGNATURES["time_passed"]
        assert sig["controllability"] == 1.0  # Time is fully uncontrollable


class TestCreateContextFromState:
    """Tests for context creation helper."""
    
    def test_create_context_with_states(self):
        """Test creating context with all state components."""
        affect = AffectState(valence=0.5, arousal=0.3)
        mood = MoodState(valence=0.2)
        bond = BondState(target="user", bond=0.7, trust=0.5, grudge=0.1)
        
        context = create_context_from_state(
            affect=affect,
            mood=mood,
            bond=bond,
            cold_treatment_duration=3600
        )
        
        assert context.affect is not None
        assert context.mood is not None
        assert context.bond is not None
        assert context.cold_treatment_duration == 3600
    
    def test_create_context_none_states(self):
        """Test creating context with no states."""
        context = create_context_from_state()
        
        assert context.affect is None
        assert context.mood is None
        assert context.bond is None
        assert context.cold_treatment_duration == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
