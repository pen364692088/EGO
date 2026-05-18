"""
Tests for MVP-4 D5: Meta-cognition System for Reflection and Clarification

Tests:
1. Trigger Tests
   - Test: uncertainty=0.8 -> triggers meta-cognition
   - Test: uncertainty=0.5 -> no trigger
   - Test: 3 consecutive prediction_errors -> triggers
   - Test: near-threshold betrayal event -> triggers

2. Action Tests
   - Test: high uncertainty -> ask_clarify action
   - Test: prediction error streak -> reflect action
   - Test: near-threshold event -> slow_down action

3. Integration Tests
   - Test: meta-cognition modifies final decision
   - Test: clarification appears in response
   - Test: tone softened when slow_down triggered

4. Sustainability Tests
   - Test: meta-cognition not triggered too frequently
   - Test: meta-cognition not triggered on confident decisions
   - Test: meta-cognition triggers consistently in uncertain situations
"""
import pytest
import pytest_asyncio
import os
import sys
import time
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.meta_cognition import (
    MetaCognitionAction,
    MetaCognitionTrigger,
    MetaCognitionEngine,
    MetaCognitionTracker,
    get_meta_cognition_engine,
    reset_meta_cognition_engine,
    apply_meta_cognition_to_decision,
    soften_decision_tone,
    get_meta_cognition_tracker
)


# ============================================================================
# Fixtures
# ============================================================================

@dataclass
class MockEmotionState:
    """Mock emotion state for testing."""
    valence: float = 0.0
    arousal: float = 0.3
    uncertainty: float = 0.5
    prediction_error: float = 0.0
    anger: float = 0.0
    sadness: float = 0.0
    anxiety: float = 0.0
    joy: float = 0.0
    loneliness: float = 0.0
    social_safety: float = 0.6
    energy: float = 0.7


@pytest.fixture
def default_state():
    """Create a default emotion state."""
    return MockEmotionState()


@pytest.fixture
def uncertain_state():
    """Create a state with high uncertainty."""
    return MockEmotionState(uncertainty=0.8)


@pytest.fixture
def volatile_state():
    """Create a volatile emotional state."""
    return MockEmotionState(
        valence=-0.4,
        arousal=0.6,
        anger=0.4,
        uncertainty=0.6
    )


@pytest.fixture
def trigger():
    """Create a default trigger."""
    return MetaCognitionTrigger()


@pytest.fixture
def engine():
    """Create a default engine."""
    return MetaCognitionEngine()


@pytest.fixture
def context_with_errors():
    """Create context with prediction errors."""
    return {
        "consecutive_prediction_errors": 4,
        "recent_events": [],
        "relationship": {"bond": 0.3, "grudge": 0.2, "trust": 0.5}
    }


@pytest.fixture
def context_with_near_threshold():
    """Create context with near-threshold grudge."""
    return {
        "consecutive_prediction_errors": 0,
        "recent_events": [],
        "relationship": {"bond": 0.2, "grudge": 0.48, "trust": 0.25}
    }


# ============================================================================
# 1. Trigger Tests
# ============================================================================

class TestMetaCognitionTrigger:
    """Test trigger detection."""
    
    def test_uncertainty_08_triggers(self, trigger):
        """Test: uncertainty=0.8 -> triggers meta-cognition."""
        state = MockEmotionState(uncertainty=0.8)
        context = {"consecutive_prediction_errors": 0}
        
        should_trigger, reason = trigger.should_trigger(state, context)
        
        assert should_trigger is True
        assert "uncertainty" in reason.lower()
        assert "0.8" in reason
    
    def test_uncertainty_05_no_trigger(self, trigger):
        """Test: uncertainty=0.5 -> no trigger."""
        state = MockEmotionState(uncertainty=0.5)
        context = {"consecutive_prediction_errors": 0}
        
        should_trigger, reason = trigger.should_trigger(state, context)
        
        assert should_trigger is False
        assert reason == ""
    
    def test_3_consecutive_errors_triggers(self, trigger):
        """Test: 3 consecutive prediction_errors -> triggers."""
        state = MockEmotionState(uncertainty=0.5)
        context = {"consecutive_prediction_errors": 3}
        
        should_trigger, reason = trigger.should_trigger(state, context)
        
        assert should_trigger is True
        assert "prediction error" in reason.lower()
    
    def test_2_consecutive_errors_no_trigger(self, trigger):
        """Test: 2 consecutive prediction_errors -> no trigger."""
        state = MockEmotionState(uncertainty=0.5)
        context = {"consecutive_prediction_errors": 2}
        
        should_trigger, reason = trigger.should_trigger(state, context)
        
        assert should_trigger is False
    
    def test_near_threshold_betrayal_triggers(self, trigger):
        """Test: near-threshold betrayal event -> triggers."""
        state = MockEmotionState(uncertainty=0.5)
        context = {
            "consecutive_prediction_errors": 0,
            "recent_events": [
                {"meta": {"subtype": "betrayal"}}
            ],
            "relationship": {"grudge": 0.2, "trust": 0.5}
        }
        
        should_trigger, reason = trigger.should_trigger(state, context)
        
        assert should_trigger is True
        assert "betrayal" in reason.lower()
    
    def test_near_threshold_grudge_triggers(self, trigger):
        """Test: high grudge with low trust -> triggers."""
        state = MockEmotionState(uncertainty=0.5)
        context = {
            "consecutive_prediction_errors": 0,
            "recent_events": [],
            "relationship": {"grudge": 0.48, "trust": 0.2}
        }
        
        should_trigger, reason = trigger.should_trigger(state, context)
        
        assert should_trigger is True
        assert "grudge" in reason.lower() or "trust" in reason.lower()
    
    def test_volatile_state_triggers(self, trigger):
        """Test: volatile emotional state -> triggers."""
        state = MockEmotionState(
            valence=-0.4,
            arousal=0.6,
            anger=0.4,
            uncertainty=0.5
        )
        context = {
            "consecutive_prediction_errors": 0,
            "recent_events": [],
            "relationship": {"grudge": 0.2, "trust": 0.5}
        }
        
        should_trigger, reason = trigger.should_trigger(state, context)
        
        assert should_trigger is True
        assert "volatile" in reason.lower()
    
    def test_custom_thresholds(self):
        """Test: custom thresholds work correctly."""
        trigger = MetaCognitionTrigger(
            uncertainty_threshold=0.5,
            min_prediction_error_streak=2
        )
        
        # Should trigger at lower threshold
        state = MockEmotionState(uncertainty=0.6)
        context = {"consecutive_prediction_errors": 0}
        
        should_trigger, reason = trigger.should_trigger(state, context)
        assert should_trigger is True
        
        # Should trigger with fewer errors
        state = MockEmotionState(uncertainty=0.3)
        context = {"consecutive_prediction_errors": 2}
        
        should_trigger, reason = trigger.should_trigger(state, context)
        assert should_trigger is True


# ============================================================================
# 2. Action Tests
# ============================================================================

class TestMetaCognitionAction:
    """Test MetaCognitionAction model."""
    
    def test_action_creation(self):
        """Test basic action creation."""
        action = MetaCognitionAction(
            action_type="ask_clarify",
            reason="High uncertainty",
            suggested_response="Let me make sure I understand...",
            intensity=0.8
        )
        
        assert action.action_type == "ask_clarify"
        assert action.reason == "High uncertainty"
        assert action.intensity == 0.8
        assert action.trigger_source == "unknown"
    
    def test_action_default_intensity(self):
        """Test default intensity is 0.5."""
        action = MetaCognitionAction(
            action_type="reflect",
            reason="Test",
            suggested_response="Test"
        )
        
        assert action.intensity == 0.5
    
    def test_action_intensity_validation(self):
        """Test intensity is clamped to [0, 1]."""
        # Should work with valid values
        action = MetaCognitionAction(
            action_type="slow_down",
            reason="Test",
            suggested_response="Test",
            intensity=0.0
        )
        assert action.intensity == 0.0
        
        action = MetaCognitionAction(
            action_type="slow_down",
            reason="Test",
            suggested_response="Test",
            intensity=1.0
        )
        assert action.intensity == 1.0


class TestMetaCognitionEngine:
    """Test MetaCognitionEngine."""
    
    def test_high_uncertainty_ask_clarify(self, engine):
        """Test: high uncertainty -> ask_clarify action."""
        state = MockEmotionState(uncertainty=0.8)
        context = {"consecutive_prediction_errors": 0}
        
        action = engine.evaluate(state, context)
        
        assert action is not None
        assert action.action_type == "ask_clarify"
        assert action.trigger_source == "uncertainty"
    
    def test_prediction_error_streak_reflect(self, engine):
        """Test: prediction error streak -> reflect action."""
        state = MockEmotionState(uncertainty=0.5)
        context = {"consecutive_prediction_errors": 3}
        
        action = engine.evaluate(state, context)
        
        assert action is not None
        assert action.action_type == "reflect"
        assert action.trigger_source == "prediction_error"
    
    def test_near_threshold_slow_down(self, engine):
        """Test: near-threshold event -> slow_down action."""
        state = MockEmotionState(
            valence=-0.4,
            arousal=0.6,
            anger=0.4,
            uncertainty=0.5
        )
        context = {
            "consecutive_prediction_errors": 0,
            "recent_events": [],
            "relationship": {"grudge": 0.2, "trust": 0.5}
        }
        
        action = engine.evaluate(state, context)
        
        assert action is not None
        assert action.action_type == "slow_down"
        assert action.trigger_source == "proximity"
    
    def test_no_trigger_returns_none(self, engine):
        """Test: no trigger condition -> returns None."""
        state = MockEmotionState(uncertainty=0.5)
        context = {"consecutive_prediction_errors": 0}
        
        action = engine.evaluate(state, context)
        
        assert action is None
    
    def test_rate_limiting(self, engine):
        """Test: rate limiting prevents rapid re-triggering."""
        state = MockEmotionState(uncertainty=0.8)
        context = {"consecutive_prediction_errors": 0}
        
        # First trigger should work
        action1 = engine.evaluate(state, context)
        assert action1 is not None
        
        # Immediate second trigger should be rate-limited
        action2 = engine.evaluate(state, context)
        assert action2 is None
        
        # After waiting, should trigger again
        engine._last_trigger_time = 0
        action3 = engine.evaluate(state, context)
        assert action3 is not None
    
    def test_generate_clarification_zh(self, engine):
        """Test: generate clarification in Chinese."""
        context = {"language": "zh"}
        
        clarification = engine.generate_clarification(context)
        
        assert clarification is not None
        assert len(clarification) > 0
        # Should contain Chinese characters
        assert any('\u4e00' <= c <= '\u9fff' for c in clarification)
    
    def test_generate_clarification_en(self):
        """Test: generate clarification in English."""
        engine = MetaCognitionEngine(language="en")
        context = {"language": "en"}
        
        clarification = engine.generate_clarification(context)
        
        assert clarification is not None
        assert len(clarification) > 0
        # Should contain English words
        assert any(c.isalpha() and ord(c) < 128 for c in clarification)
    
    def test_generate_reflection(self, engine):
        """Test: generate internal reflection."""
        state = MockEmotionState(valence=-0.4)
        
        reflection = engine.generate_reflection(state)
        
        assert reflection is not None
        assert len(reflection) > 0
    
    def test_soften_tone_chinese(self, engine):
        """Test: soften Chinese tone."""
        text = "肯定是这样"
        softened = engine.soften_tone(text)
        
        assert "肯定" not in softened
        assert "可能" in softened
    
    def test_soften_tone_english(self, engine):
        """Test: soften English tone."""
        text = "This is definitely correct"
        softened = engine.soften_tone(text)
        
        assert "definitely" not in softened.lower()
        assert "probably" in softened.lower()
    
    def test_prediction_error_tracking(self, engine):
        """Test: prediction error history tracking."""
        # Add errors above threshold
        engine.update_prediction_error_history(0.4)
        engine.update_prediction_error_history(0.35)
        engine.update_prediction_error_history(0.32)
        
        # Should count consecutive errors above threshold 0.3
        count = engine.get_consecutive_prediction_errors(threshold=0.3)
        assert count == 3
        
        # Add below threshold - resets the streak
        engine.update_prediction_error_history(0.2)
        count = engine.get_consecutive_prediction_errors(threshold=0.3)
        assert count == 0


# ============================================================================
# 3. Integration Tests
# ============================================================================

class TestMetaCognitionIntegration:
    """Test integration with decision pipeline."""
    
    def test_modifies_final_decision(self):
        """Test: meta-cognition modifies final decision."""
        decision = {
            "tone": "cold",
            "explanation": ["Initial explanation"],
            "key_points": ["Point 1"]
        }
        
        meta_action = MetaCognitionAction(
            action_type="slow_down",
            reason="Near-threshold event",
            suggested_response="Applying caution",
            intensity=0.7
        )
        
        modified = apply_meta_cognition_to_decision(decision, meta_action)
        
        assert "meta_action" in modified
        assert modified["tone"] == "neutral"  # Should be softened
        assert modified["caution_applied"] is True
    
    def test_clarification_in_response(self):
        """Test: clarification appears in response."""
        decision = {
            "tone": "warm",
            "explanation": ["Initial explanation"],
            "key_points": ["Point 1"]
        }
        
        meta_action = MetaCognitionAction(
            action_type="ask_clarify",
            reason="High uncertainty",
            suggested_response="Let me make sure I understand...",
            intensity=0.8
        )
        
        modified = apply_meta_cognition_to_decision(decision, meta_action)
        
        assert "meta_action" in modified
        assert modified["needs_clarification"] is True
        # Check if any explanation contains the clarification
        explanation_text = " ".join(modified["explanation"])
        assert "Let me make sure I understand" in explanation_text
    
    def test_reflection_in_explanation(self):
        """Test: reflection added to explanation."""
        decision = {
            "tone": "soft",
            "explanation": ["Initial explanation"],
            "key_points": ["Point 1"]
        }
        
        meta_action = MetaCognitionAction(
            action_type="reflect",
            reason="Prediction errors",
            suggested_response="Let me reconsider this situation...",
            intensity=0.6
        )
        
        modified = apply_meta_cognition_to_decision(decision, meta_action)
        
        assert "internal_reflection" in modified
        assert "reconsider" in modified["internal_reflection"].lower()
    
    def test_tone_softened_when_slow_down(self):
        """Test: tone softened when slow_down triggered."""
        # Test various tones
        assert soften_decision_tone("confident") == "cautious"
        assert soften_decision_tone("assertive") == "tentative"
        assert soften_decision_tone("certain") == "uncertain"
        assert soften_decision_tone("cold") == "neutral"
        
        # Soft tones should be preserved
        assert soften_decision_tone("warm") == "warm"
        assert soften_decision_tone("soft") == "soft"
    
    def test_full_pipeline_integration(self, engine):
        """Test: full pipeline from trigger to modified decision."""
        # Create uncertain state
        state = MockEmotionState(uncertainty=0.85)
        context = {"consecutive_prediction_errors": 0}
        
        # Get action
        action = engine.evaluate(state, context)
        
        assert action is not None
        assert action.action_type == "ask_clarify"
        
        # Apply to decision
        decision = {
            "tone": "warm",
            "explanation": ["I think you should do this"],
            "key_points": ["Point 1", "Point 2"]
        }
        
        modified = apply_meta_cognition_to_decision(decision, action)
        
        assert "meta_action" in modified
        assert modified["needs_clarification"] is True


# ============================================================================
# 4. Sustainability Tests
# ============================================================================

class TestMetaCognitionSustainability:
    """Test sustainability of meta-cognition triggering."""
    
    def test_not_triggered_too_frequently(self, engine):
        """Test: meta-cognition not triggered too frequently."""
        tracker = MetaCognitionTracker()
        
        # Simulate many evaluations with low uncertainty (should not trigger)
        for _ in range(100):
            state = MockEmotionState(uncertainty=0.3)
            context = {"consecutive_prediction_errors": 0}
            should_trigger, reason = engine.trigger.should_trigger(state, context)
            tracker.record_evaluation(should_trigger, state.uncertainty, reason)
        
        # Trigger rate should be low
        assert tracker.get_trigger_rate() < 0.1  # Less than 10%
        assert tracker.is_triggering_sustainable()
    
    def test_not_triggered_on_confident_decisions(self, engine):
        """Test: meta-cognition not triggered on confident decisions."""
        # Low uncertainty = confident decision
        state = MockEmotionState(uncertainty=0.2)
        context = {"consecutive_prediction_errors": 0}
        
        action = engine.evaluate(state, context)
        
        assert action is None
    
    def test_triggers_consistently_in_uncertain_situations(self, engine):
        """Test: meta-cognition triggers consistently in uncertain situations."""
        tracker = MetaCognitionTracker()
        
        # Reset rate limiting
        engine._last_trigger_time = 0
        
        # Simulate many evaluations with high uncertainty (should trigger)
        trigger_count = 0
        for i in range(10):
            state = MockEmotionState(uncertainty=0.85)
            context = {"consecutive_prediction_errors": 0}
            
            # Reset rate limit each time for this test
            engine._last_trigger_time = 0
            
            should_trigger, reason = engine.trigger.should_trigger(state, context)
            tracker.record_evaluation(should_trigger, state.uncertainty, reason)
            
            if should_trigger:
                trigger_count += 1
        
        # Should trigger every time for high uncertainty
        assert trigger_count == 10
        assert tracker.get_trigger_rate() == 1.0
    
    def test_trigger_rate_calculation(self):
        """Test: trigger rate is calculated correctly."""
        tracker = MetaCognitionTracker()
        
        # Record 10 evaluations: 3 triggers
        for i in range(10):
            tracker.record_evaluation(i < 3, 0.5 + i * 0.05)
        
        assert tracker.total_evaluations == 10
        assert tracker.total_triggers == 3
        assert tracker.get_trigger_rate() == 0.3
    
    def test_sustainability_threshold(self):
        """Test: sustainability threshold works correctly."""
        tracker = MetaCognitionTracker()
        
        # 20% trigger rate - should be sustainable
        for i in range(10):
            tracker.record_evaluation(i < 2, 0.5)
        
        assert tracker.is_triggering_sustainable(max_rate=0.3)
        
        # 40% trigger rate - should not be sustainable
        tracker2 = MetaCognitionTracker()
        for i in range(10):
            tracker2.record_evaluation(i < 4, 0.5)
        
        assert not tracker2.is_triggering_sustainable(max_rate=0.3)
    
    def test_statistics_tracking(self):
        """Test: statistics are tracked correctly."""
        tracker = MetaCognitionTracker()
        
        for i in range(5):
            tracker.record_evaluation(i % 2 == 0, 0.5 + i * 0.1, f"reason_{i}")
        
        stats = tracker.get_statistics()
        
        assert stats["total_evaluations"] == 5
        assert stats["total_triggers"] == 3  # 0, 2, 4
        assert "trigger_rate" in stats
        assert "is_sustainable" in stats
        assert len(stats["recent_triggers"]) == 5


# ============================================================================
# 5. Global Instance Tests
# ============================================================================

class TestGlobalInstances:
    """Test global instance management."""
    
    def test_get_engine_creates_instance(self):
        """Test: get_meta_cognition_engine creates instance."""
        reset_meta_cognition_engine()
        
        engine = get_meta_cognition_engine()
        
        assert engine is not None
        assert isinstance(engine, MetaCognitionEngine)
    
    def test_reset_engine(self):
        """Test: reset_meta_cognition_engine clears instance."""
        engine1 = get_meta_cognition_engine()
        reset_meta_cognition_engine()
        engine2 = get_meta_cognition_engine()
        
        # Should be different instances
        assert engine1 is not engine2
    
    def test_get_tracker(self):
        """Test: get_meta_cognition_tracker works."""
        tracker = get_meta_cognition_tracker()
        
        assert tracker is not None
        assert isinstance(tracker, MetaCognitionTracker)


# ============================================================================
# 6. Edge Case Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_context(self, engine):
        """Test: empty context doesn't crash."""
        state = MockEmotionState(uncertainty=0.8)
        context = {}
        
        # Should handle gracefully
        action = engine.evaluate(state, context)
        
        assert action is not None  # Should still trigger on uncertainty
    
    def test_missing_state_attributes(self, trigger):
        """Test: missing state attributes handled gracefully."""
        # Create a minimal mock
        state = Mock()
        state.uncertainty = 0.8
        # Other attributes missing
        
        context = {"consecutive_prediction_errors": 0}
        
        # Should not crash
        should_trigger, reason = trigger.should_trigger(state, context)
        
        assert should_trigger is True
    
    def test_negative_values(self, engine):
        """Test: negative values handled correctly."""
        state = MockEmotionState(
            valence=-0.9,
            arousal=-0.5,
            uncertainty=0.5
        )
        context = {"consecutive_prediction_errors": 0}
        
        # Should not crash
        action = engine.evaluate(state, context)
        
        # Should not trigger (uncertainty is moderate)
        assert action is None
    
    def test_extreme_values(self, engine):
        """Test: extreme values handled correctly."""
        state = MockEmotionState(uncertainty=1.0)
        context = {"consecutive_prediction_errors": 10}
        
        action = engine.evaluate(state, context)
        
        assert action is not None
        assert action.intensity <= 1.0  # Should be clamped
    
    def test_concurrent_triggers(self, engine):
        """Test: multiple trigger conditions handled."""
        # Both high uncertainty AND prediction errors
        state = MockEmotionState(uncertainty=0.85)
        context = {"consecutive_prediction_errors": 5}
        
        engine._last_trigger_time = 0
        action = engine.evaluate(state, context)
        
        assert action is not None
        # Should prioritize uncertainty (ask_clarify) over errors (reflect)
        assert action.action_type == "ask_clarify"
    
    def test_decision_without_explanation(self):
        """Test: decision without explanation field handled."""
        decision = {"tone": "cold"}
        
        meta_action = MetaCognitionAction(
            action_type="reflect",
            reason="Test",
            suggested_response="Test reflection"
        )
        
        # Should not crash
        modified = apply_meta_cognition_to_decision(decision, meta_action)
        
        assert "meta_action" in modified
    
    def test_decision_without_key_points(self):
        """Test: decision without key_points handled."""
        decision = {"tone": "confident", "explanation": []}
        
        meta_action = MetaCognitionAction(
            action_type="slow_down",
            reason="Test",
            suggested_response="Test"
        )
        
        # Should not crash
        modified = apply_meta_cognition_to_decision(decision, meta_action)
        
        assert modified["tone"] == "cautious"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
