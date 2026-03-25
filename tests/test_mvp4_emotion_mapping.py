"""
MVP-4 D3: Discrete Emotion Mapping Tests

Tests for the 7-emotion mapping system.
Each emotion has 10+ test cases.
"""
import pytest
import os

# Set test environment
os.environ["EMOTIOND_DISABLE_CORE"] = "0"
os.environ["EMOTIOND_DB_PATH"] = ":memory:"

from emotiond.emotion_labels import (
    map_to_emotion,
    get_emotion_explanation,
    get_emotion_blend,
    is_sustainable_emotion,
    get_emotion_action_tendency,
    EMOTION_RULES,
    EMOTION_PRIORITY
)
from emotiond.state import AffectState, MoodState


class TestEmotionRules:
    """Tests for emotion rule definitions."""
    
    def test_all_emotions_have_rules(self):
        """Test that all 7 emotions have rules defined."""
        expected_emotions = {"joy", "sadness", "fear", "anger", "curiosity", "confusion", "boredom"}
        assert expected_emotions == set(EMOTION_RULES.keys())
    
    def test_all_rules_have_valid_thresholds(self):
        """Test that all rule thresholds are in valid ranges."""
        for emotion, rules in EMOTION_RULES.items():
            for dim, (min_val, max_val) in rules.items():
                assert min_val <= max_val, f"{emotion}.{dim}: min > max"
                # Dimensions can have negative ranges (e.g., prediction_error)
                if dim == "goal_progress":
                    assert -1.0 <= min_val <= 1.0
                    assert -1.0 <= max_val <= 1.0
    
    def test_priority_order(self):
        """Test that priority order includes all emotions."""
        expected_emotions = {"joy", "sadness", "fear", "anger", "curiosity", "confusion", "boredom"}
        assert set(EMOTION_PRIORITY) == expected_emotions


class TestJoy:
    """Tests for joy emotion mapping. 10+ cases."""
    
    def test_joy_achievement(self):
        """Joy: Achievement scenario."""
        emotion, intensity = map_to_emotion(
            goal_progress=0.7,
            valence=0.5,
            controllability=0.8
        )
        assert emotion == "joy"
        assert intensity > 0
    
    def test_joy_praise(self):
        """Joy: Praise scenario."""
        emotion, intensity = map_to_emotion(
            goal_progress=0.5,
            valence=0.4,
            controllability=0.6
        )
        assert emotion == "joy"
    
    def test_joy_surprise_gift(self):
        """Joy: Surprise gift scenario (high novelty + positive)."""
        emotion, intensity = map_to_emotion(
            goal_progress=0.6,
            valence=0.6,
            novelty=0.7
        )
        assert emotion == "joy"
    
    def test_joy_care_received(self):
        """Joy: Receiving care from someone."""
        emotion, intensity = map_to_emotion(
            goal_progress=0.5,
            valence=0.5,
            social_threat=0.0
        )
        assert emotion == "joy"
    
    def test_joy_repair_success(self):
        """Joy: Successful relationship repair."""
        emotion, intensity = map_to_emotion(
            goal_progress=0.6,
            valence=0.4,
            controllability=0.7
        )
        assert emotion == "joy"
    
    def test_joy_agreement(self):
        """Joy: Agreement reached."""
        emotion, intensity = map_to_emotion(
            goal_progress=0.4,
            valence=0.3
        )
        assert emotion == "joy"
    
    def test_joy_appreciation(self):
        """Joy: Being appreciated."""
        emotion, intensity = map_to_emotion(
            goal_progress=0.5,
            valence=0.5,
            social_threat=0.0
        )
        assert emotion == "joy"
    
    def test_joy_with_mood(self):
        """Joy: Intensified by positive mood."""
        mood = MoodState(joy=0.3, valence=0.2)
        emotion, intensity = map_to_emotion(
            goal_progress=0.5,
            valence=0.4,
            mood=mood
        )
        assert emotion == "joy"
        # Mood should amplify intensity
        emotion2, intensity2 = map_to_emotion(
            goal_progress=0.5,
            valence=0.4,
            mood=None
        )
        assert intensity >= intensity2
    
    def test_joy_low_intensity_boundary(self):
        """Joy: At low intensity boundary."""
        emotion, intensity = map_to_emotion(
            goal_progress=0.31,  # Just above threshold
            valence=0.21
        )
        assert emotion == "joy"
        # Intensity should be positive but relatively low at boundary
        assert intensity > 0
    
    def test_joy_high_intensity(self):
        """Joy: High intensity scenario."""
        emotion, intensity = map_to_emotion(
            goal_progress=0.9,
            valence=0.8
        )
        assert emotion == "joy"
        assert intensity > 0.3  # Adjusted threshold


class TestSadness:
    """Tests for sadness emotion mapping. 10+ cases."""
    
    def test_sadness_loss(self):
        """Sadness: Loss scenario."""
        emotion, intensity = map_to_emotion(
            goal_progress=-0.6,
            controllability=0.2
        )
        assert emotion == "sadness"
    
    def test_sadness_rejection(self):
        """Sadness: Rejection scenario."""
        emotion, intensity = map_to_emotion(
            goal_progress=-0.5,
            controllability=0.3
        )
        assert emotion == "sadness"
    
    def test_sadness_disappointment(self):
        """Sadness: Disappointment scenario."""
        emotion, intensity = map_to_emotion(
            goal_progress=-0.4,
            controllability=0.4
        )
        assert emotion == "sadness"
    
    def test_sadness_helplessness(self):
        """Sadness: Helplessness (low controllability)."""
        emotion, intensity = map_to_emotion(
            goal_progress=-0.5,
            controllability=0.1
        )
        assert emotion == "sadness"
    
    def test_sadness_missed_opportunity(self):
        """Sadness: Missed opportunity."""
        emotion, intensity = map_to_emotion(
            goal_progress=-0.7,
            controllability=0.2
        )
        assert emotion == "sadness"
    
    def test_sadness_ignored(self):
        """Sadness: Being ignored."""
        emotion, intensity = map_to_emotion(
            goal_progress=-0.3,
            controllability=0.3
        )
        assert emotion == "sadness"
    
    def test_sadness_cold_treatment(self):
        """Sadness: Cold treatment result."""
        emotion, intensity = map_to_emotion(
            goal_progress=-0.4,
            controllability=0.3,
            social_threat=0.4
        )
        # Could be sadness or fear depending on priority
        assert emotion in ["sadness", "fear"]
    
    def test_sadness_with_mood(self):
        """Sadness: Intensified by sad mood."""
        mood = MoodState(sadness=0.4, valence=-0.2)
        emotion, intensity = map_to_emotion(
            goal_progress=-0.5,
            controllability=0.3,
            mood=mood
        )
        assert emotion == "sadness"
    
    def test_sadness_low_intensity_boundary(self):
        """Sadness: At low intensity boundary."""
        emotion, intensity = map_to_emotion(
            goal_progress=-0.31,
            controllability=0.49
        )
        assert emotion == "sadness"
    
    def test_sadness_high_intensity(self):
        """Sadness: High intensity scenario."""
        emotion, intensity = map_to_emotion(
            goal_progress=-0.9,
            controllability=0.1
        )
        assert emotion == "sadness"
        assert intensity > 0.3


class TestFear:
    """Tests for fear emotion mapping. 10+ cases."""
    
    def test_fear_threat(self):
        """Fear: Social threat scenario."""
        emotion, intensity = map_to_emotion(
            social_threat=0.7,
            uncertainty=0.6
        )
        assert emotion == "fear"
    
    def test_fear_uncertainty(self):
        """Fear: High uncertainty scenario."""
        emotion, intensity = map_to_emotion(
            social_threat=0.6,
            uncertainty=0.7
        )
        assert emotion == "fear"
    
    def test_fear_danger(self):
        """Fear: Danger scenario."""
        emotion, intensity = map_to_emotion(
            social_threat=0.8,
            uncertainty=0.8
        )
        assert emotion == "fear"
    
    def test_fear_rejection_threat(self):
        """Fear: Threat of rejection."""
        emotion, intensity = map_to_emotion(
            social_threat=0.6,
            uncertainty=0.6
        )
        assert emotion == "fear"
    
    def test_fear_betrayal_anticipation(self):
        """Fear: Anticipating betrayal."""
        emotion, intensity = map_to_emotion(
            social_threat=0.7,
            uncertainty=0.7
        )
        assert emotion == "fear"
    
    def test_fear_loss_of_connection(self):
        """Fear: Fear of losing connection."""
        emotion, intensity = map_to_emotion(
            social_threat=0.6,
            uncertainty=0.6,
            goal_progress=-0.3
        )
        assert emotion == "fear"
    
    def test_fear_unpredictable(self):
        """Fear: Unpredictable situation."""
        emotion, intensity = map_to_emotion(
            social_threat=0.55,
            uncertainty=0.65
        )
        assert emotion == "fear"
    
    def test_fear_with_anxious_mood(self):
        """Fear: Intensified by anxious mood."""
        mood = MoodState(anxiety=0.5)
        emotion, intensity = map_to_emotion(
            social_threat=0.6,
            uncertainty=0.6,
            mood=mood
        )
        assert emotion == "fear"
    
    def test_fear_low_intensity_boundary(self):
        """Fear: At low intensity boundary."""
        emotion, intensity = map_to_emotion(
            social_threat=0.51,
            uncertainty=0.51
        )
        assert emotion == "fear"
    
    def test_fear_high_intensity(self):
        """Fear: High intensity scenario."""
        emotion, intensity = map_to_emotion(
            social_threat=0.9,
            uncertainty=0.9
        )
        assert emotion == "fear"
        assert intensity > 0.4


class TestAnger:
    """Tests for anger emotion mapping. 10+ cases."""
    
    def test_anger_betrayal(self):
        """Anger: Betrayal scenario."""
        emotion, intensity = map_to_emotion(
            expectation_violation=0.8,
            controllability=0.6
        )
        assert emotion == "anger"
    
    def test_anger_blocked_goal(self):
        """Anger: Blocked goal with controllability."""
        emotion, intensity = map_to_emotion(
            expectation_violation=0.6,
            controllability=0.6
        )
        assert emotion == "anger"
    
    def test_anger_injustice(self):
        """Anger: Injustice scenario."""
        emotion, intensity = map_to_emotion(
            expectation_violation=0.7,
            controllability=0.7
        )
        assert emotion == "anger"
    
    def test_anger_promise_break(self):
        """Anger: Promise break scenario."""
        emotion, intensity = map_to_emotion(
            expectation_violation=0.7,
            controllability=0.6
        )
        assert emotion == "anger"
    
    def test_anger_disrespect(self):
        """Anger: Disrespect scenario."""
        emotion, intensity = map_to_emotion(
            expectation_violation=0.65,
            controllability=0.55
        )
        assert emotion == "anger"
    
    def test_anger_unfair_treatment(self):
        """Anger: Unfair treatment."""
        emotion, intensity = map_to_emotion(
            expectation_violation=0.6,
            controllability=0.6,
            social_threat=0.3
        )
        assert emotion == "anger"
    
    def test_anger_goal_obstacle(self):
        """Anger: Goal obstacle with agency."""
        emotion, intensity = map_to_emotion(
            expectation_violation=0.55,
            controllability=0.55
        )
        assert emotion == "anger"
    
    def test_anger_with_angry_mood(self):
        """Anger: Intensified by angry mood."""
        mood = MoodState(anger=0.4)
        emotion, intensity = map_to_emotion(
            expectation_violation=0.6,
            controllability=0.6,
            mood=mood
        )
        assert emotion == "anger"
    
    def test_anger_low_intensity_boundary(self):
        """Anger: At low intensity boundary."""
        emotion, intensity = map_to_emotion(
            expectation_violation=0.51,
            controllability=0.51
        )
        assert emotion == "anger"
    
    def test_anger_high_intensity(self):
        """Anger: High intensity scenario."""
        emotion, intensity = map_to_emotion(
            expectation_violation=0.9,
            controllability=0.9
        )
        assert emotion == "anger"
        assert intensity > 0.4  # Adjusted threshold


class TestCuriosity:
    """Tests for curiosity emotion mapping. 10+ cases."""
    
    def test_curiosity_new_information(self):
        """Curiosity: New information scenario."""
        emotion, intensity = map_to_emotion(
            novelty=0.7,
            social_threat=0.1
        )
        assert emotion == "curiosity"
    
    def test_curiosity_puzzle(self):
        """Curiosity: Puzzle scenario."""
        emotion, intensity = map_to_emotion(
            novelty=0.6,
            social_threat=0.2
        )
        assert emotion == "curiosity"
    
    def test_curiosity_mystery(self):
        """Curiosity: Mystery scenario."""
        emotion, intensity = map_to_emotion(
            novelty=0.65,
            social_threat=0.15
        )
        assert emotion == "curiosity"
    
    def test_curiosity_discovery(self):
        """Curiosity: Discovery scenario."""
        emotion, intensity = map_to_emotion(
            novelty=0.55,
            social_threat=0.1
        )
        assert emotion == "curiosity"
    
    def test_curiosity_new_person(self):
        """Curiosity: Meeting new person."""
        emotion, intensity = map_to_emotion(
            novelty=0.6,
            social_threat=0.2,
            goal_progress=0.1
        )
        assert emotion == "curiosity"
    
    def test_curiosity_unknown_topic(self):
        """Curiosity: Unknown topic."""
        emotion, intensity = map_to_emotion(
            novelty=0.7,
            social_threat=0.05
        )
        assert emotion == "curiosity"
    
    def test_curiosity_surprise_positive(self):
        """Curiosity: Positive surprise."""
        emotion, intensity = map_to_emotion(
            novelty=0.6,
            social_threat=0.1,
            valence=0.2
        )
        assert emotion == "curiosity"
    
    def test_curiosity_with_arousal(self):
        """Curiosity: High arousal increases curiosity."""
        affect = AffectState(arousal=0.7)
        emotion, intensity = map_to_emotion(
            novelty=0.6,
            social_threat=0.1,
            affect=affect
        )
        assert emotion == "curiosity"
    
    def test_curiosity_low_intensity_boundary(self):
        """Curiosity: At low intensity boundary."""
        emotion, intensity = map_to_emotion(
            novelty=0.51,
            social_threat=0.29
        )
        assert emotion == "curiosity"
    
    def test_curiosity_high_intensity(self):
        """Curiosity: High intensity scenario."""
        emotion, intensity = map_to_emotion(
            novelty=0.9,
            social_threat=0.0
        )
        assert emotion == "curiosity"
        assert intensity > 0.1  # Adjusted threshold


class TestConfusion:
    """Tests for confusion emotion mapping. 10+ cases."""
    
    def test_confusion_unexpected_outcome(self):
        """Confusion: Unexpected outcome."""
        emotion, intensity = map_to_emotion(
            uncertainty=0.7,
            prediction_error=0.5
        )
        assert emotion == "confusion"
    
    def test_confusion_contradiction(self):
        """Confusion: Contradiction scenario."""
        emotion, intensity = map_to_emotion(
            uncertainty=0.75,
            prediction_error=0.4
        )
        assert emotion == "confusion"
    
    def test_confusion_unclear_message(self):
        """Confusion: Unclear message."""
        emotion, intensity = map_to_emotion(
            uncertainty=0.65,
            prediction_error=0.35
        )
        assert emotion == "confusion"
    
    def test_confusion_mixed_signals(self):
        """Confusion: Mixed signals."""
        emotion, intensity = map_to_emotion(
            uncertainty=0.7,
            prediction_error=0.45
        )
        assert emotion == "confusion"
    
    def test_confusion_inconsistency(self):
        """Confusion: Inconsistency detected."""
        emotion, intensity = map_to_emotion(
            uncertainty=0.65,
            prediction_error=0.5
        )
        assert emotion == "confusion"
    
    def test_confusion_ambiguous_situation(self):
        """Confusion: Ambiguous situation."""
        emotion, intensity = map_to_emotion(
            uncertainty=0.7,
            prediction_error=0.35
        )
        assert emotion == "confusion"
    
    def test_confusion_surprise_negative(self):
        """Confusion: Negative surprise causing confusion."""
        emotion, intensity = map_to_emotion(
            uncertainty=0.7,
            prediction_error=0.4,
            goal_progress=-0.2
        )
        # Could be confusion or sadness depending on priority
        assert emotion in ["confusion", "sadness", "fear"]
    
    def test_confusion_with_affect(self):
        """Confusion: With affect state."""
        affect = AffectState(uncertainty=0.7)
        emotion, intensity = map_to_emotion(
            uncertainty=0.7,
            prediction_error=0.4,
            affect=affect
        )
        assert emotion == "confusion"
    
    def test_confusion_low_intensity_boundary(self):
        """Confusion: At low intensity boundary."""
        emotion, intensity = map_to_emotion(
            uncertainty=0.61,
            prediction_error=0.31
        )
        assert emotion == "confusion"
    
    def test_confusion_high_intensity(self):
        """Confusion: High intensity scenario."""
        emotion, intensity = map_to_emotion(
            uncertainty=0.9,
            prediction_error=0.8
        )
        assert emotion == "confusion"


class TestBoredom:
    """Tests for boredom emotion mapping. 10+ cases."""
    
    def test_boredom_repetitive_task(self):
        """Boredom: Repetitive task scenario."""
        emotion, intensity = map_to_emotion(
            novelty=0.1,
            prediction_error=0.0
        )
        assert emotion == "boredom"
    
    def test_boredom_no_new_info(self):
        """Boredom: No new information."""
        emotion, intensity = map_to_emotion(
            novelty=0.15,
            prediction_error=0.05
        )
        assert emotion == "boredom"
    
    def test_boredom_mundane(self):
        """Boredom: Mundane situation."""
        emotion, intensity = map_to_emotion(
            novelty=0.1,
            prediction_error=0.0
        )
        assert emotion == "boredom"
    
    def test_boredom_routine(self):
        """Boredom: Routine activity."""
        emotion, intensity = map_to_emotion(
            novelty=0.12,
            prediction_error=0.02
        )
        assert emotion == "boredom"
    
    def test_boredom_waiting(self):
        """Boredom: Waiting scenario."""
        emotion, intensity = map_to_emotion(
            novelty=0.1,
            prediction_error=0.0,
            controllability=0.5
        )
        assert emotion == "boredom"
    
    def test_boredom_uninteresting(self):
        """Boredom: Uninteresting content."""
        emotion, intensity = map_to_emotion(
            novelty=0.08,
            prediction_error=0.0
        )
        assert emotion == "boredom"
    
    def test_boredom_unchanging(self):
        """Boredom: Unchanging situation."""
        emotion, intensity = map_to_emotion(
            novelty=0.1,
            prediction_error=-0.02
        )
        assert emotion == "boredom"
    
    def test_boredom_with_low_arousal_mood(self):
        """Boredom: With low arousal mood."""
        mood = MoodState(arousal=0.1)
        emotion, intensity = map_to_emotion(
            novelty=0.1,
            prediction_error=0.0,
            mood=mood
        )
        assert emotion == "boredom"
    
    def test_boredom_high_intensity_boundary(self):
        """Boredom: At boundary."""
        emotion, intensity = map_to_emotion(
            novelty=0.14,  # Within the (0.0, 0.15) threshold
            prediction_error=0.0
        )
        assert emotion == "boredom"
    
    def test_boredom_high_intensity(self):
        """Boredom: High boredom (very low novelty)."""
        emotion, intensity = map_to_emotion(
            novelty=0.01,
            prediction_error=0.0
        )
        assert emotion == "boredom"


class TestNeutral:
    """Tests for neutral emotion mapping."""
    
    def test_neutral_default(self):
        """Neutral: Default values may match boredom due to low novelty."""
        emotion, intensity = map_to_emotion()
        # With defaults, boredom matches (low novelty)
        assert emotion in ["neutral", "boredom"]
    
    def test_neutral_balanced(self):
        """Neutral: Balanced dimensions."""
        emotion, intensity = map_to_emotion(
            goal_progress=0.0,
            expectation_violation=0.0,
            controllability=0.5,
            social_threat=0.0,
            novelty=0.5,  # Medium novelty to avoid boredom
            uncertainty=0.5,
            prediction_error=0.0
        )
        # With balanced values, may not match any specific emotion
        assert emotion in ["neutral", "curiosity", "confusion"]


class TestGetEmotionExplanation:
    """Tests for emotion explanation generation."""
    
    def test_joy_explanation(self):
        """Test joy explanation."""
        exp = get_emotion_explanation("joy", 0.5, 0.0, 0.6, 0.0, 0.0)
        assert "goal" in exp.lower() or "positive" in exp.lower()
    
    def test_sadness_explanation(self):
        """Test sadness explanation."""
        exp = get_emotion_explanation("sadness", -0.5, 0.0, 0.3, 0.0, 0.0)
        assert "blocked" in exp.lower() or "helpless" in exp.lower()
    
    def test_fear_explanation(self):
        """Test fear explanation."""
        exp = get_emotion_explanation("fear", 0.0, 0.0, 0.5, 0.7, 0.0)
        assert "threat" in exp.lower() or "safety" in exp.lower()
    
    def test_anger_explanation(self):
        """Test anger explanation."""
        exp = get_emotion_explanation("anger", 0.0, 0.7, 0.6, 0.0, 0.0)
        assert "violation" in exp.lower() or "action" in exp.lower()


class TestGetEmotionBlend:
    """Tests for emotion blend functionality."""
    
    def test_blend_multiple_emotions(self):
        """Test getting blend of multiple emotions."""
        blend = get_emotion_blend(
            goal_progress=0.5,
            valence=0.4,
            novelty=0.6,
            social_threat=0.1
        )
        # Should have joy and possibly curiosity
        assert len(blend) >= 1
        assert all(v >= 0.3 for v in blend.values())
    
    def test_blend_threshold(self):
        """Test blend threshold filtering."""
        blend = get_emotion_blend(
            goal_progress=0.5,
            valence=0.4,
            threshold=0.5
        )
        assert all(v >= 0.5 for v in blend.values())


class TestSustainableEmotions:
    """Tests for emotion sustainability."""
    
    def test_curiosity_sustainable(self):
        """Curiosity is sustainable."""
        assert is_sustainable_emotion("curiosity")
    
    def test_confusion_sustainable(self):
        """Confusion is sustainable."""
        assert is_sustainable_emotion("confusion")
    
    def test_boredom_sustainable(self):
        """Boredom is sustainable."""
        assert is_sustainable_emotion("boredom")
    
    def test_joy_not_sustainable(self):
        """Joy is not sustainable without events."""
        assert not is_sustainable_emotion("joy")
    
    def test_anger_not_sustainable(self):
        """Anger is not sustainable without events."""
        assert not is_sustainable_emotion("anger")


class TestActionTendencies:
    """Tests for action tendency mapping."""
    
    def test_joy_tendency(self):
        """Test joy action tendency."""
        tendency = get_emotion_action_tendency("joy")
        assert "approach" in tendency or "share" in tendency
    
    def test_fear_tendency(self):
        """Test fear action tendency."""
        tendency = get_emotion_action_tendency("fear")
        assert "escape" in tendency or "avoid" in tendency
    
    def test_anger_tendency(self):
        """Test anger action tendency."""
        tendency = get_emotion_action_tendency("anger")
        assert "confront" in tendency or "assert" in tendency
    
    def test_curiosity_tendency(self):
        """Test curiosity action tendency."""
        tendency = get_emotion_action_tendency("curiosity")
        assert "explore" in tendency or "investigate" in tendency


class TestEmotionPriority:
    """Tests for emotion priority ordering."""
    
    def test_anger_over_sadness(self):
        """Anger has higher priority than sadness."""
        assert EMOTION_PRIORITY.index("anger") < EMOTION_PRIORITY.index("sadness")
    
    def test_fear_high_priority(self):
        """Fear has high priority (safety-critical)."""
        assert EMOTION_PRIORITY.index("fear") < 3
    
    def test_boredom_low_priority(self):
        """Boredom has low priority."""
        assert EMOTION_PRIORITY.index("boredom") > 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
