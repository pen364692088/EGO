#!/usr/bin/env python3
"""
Test suite for User Affect Classifier v0

Tests cover:
- Emoji usage
- Sarcasm/irony detection
- Busy/cold responses
- Positive/negative sentiment
- Low confidence edge cases
- Schema compliance
- Range validation
- Low confidence isolation from high-impact events
"""

import pytest
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrations.openclaw.classifiers.user_affect import (
    UserAffectClassifier,
    UserAffect,
    classify_user_affect,
    get_affect_for_emotiond
)


class TestUserAffectSchema:
    """Test schema compliance and validation."""
    
    def test_schema_required_fields(self):
        """Test that all required fields are present."""
        affect = classify_user_affect("Hello!")
        d = affect.to_dict()
        
        assert "valence" in d, "valence is required"
        assert "arousal" in d, "arousal is required"
        assert "confidence" in d, "confidence is required"
        assert "evidence" in d, "evidence is required"
    
    def test_valence_range(self):
        """Test that valence is always in valid range."""
        classifier = UserAffectClassifier()
        
        # Test various inputs
        test_cases = [
            "I love this so much!!!!",
            "This is terrible and I hate it.",
            "Normal message.",
            "",  # Empty
            "a",  # Single char
            "😊😊😊",  # Only emojis
            "no " * 100,  # Long negative
        ]
        
        for text in test_cases:
            affect = classifier.classify(text)
            assert -1.0 <= affect.valence <= 1.0, f"valence out of range for: {text[:20]}"
    
    def test_arousal_range(self):
        """Test that arousal is always in valid range."""
        classifier = UserAffectClassifier()
        
        test_cases = [
            "Calm message.",
            "WOW THIS IS AMAZING!!!",
            "...",
            "k",
        ]
        
        for text in test_cases:
            affect = classifier.classify(text)
            assert 0.0 <= affect.arousal <= 1.0, f"arousal out of range for: {text}"
    
    def test_confidence_range(self):
        """Test that confidence is always in valid range."""
        classifier = UserAffectClassifier()
        
        test_cases = ["Any message", "", "Short"]
        
        for text in test_cases:
            affect = classifier.classify(text)
            assert 0.0 <= affect.confidence <= 1.0, f"confidence out of range for: {text}"
    
    def test_evidence_max_items(self):
        """Test that evidence array has max 3 items."""
        classifier = UserAffectClassifier()
        affect = classifier.classify("This is great! I love it! Thanks! Wonderful!")
        
        assert len(affect.evidence) <= 3, "evidence should have max 3 items"
    
    def test_schema_validation_method(self):
        """Test the schema validation method."""
        classifier = UserAffectClassifier()
        
        # Valid affect
        valid = UserAffect(valence=0.5, arousal=0.3, confidence=0.7, evidence=["test"])
        assert classifier.validate_schema(valid), "Valid affect should pass validation"
        
        # Invalid valence (out of range)
        invalid_valence = UserAffect(valence=2.0, arousal=0.3, confidence=0.7, evidence=["test"])
        # Note: __post_init__ clamps values, so this should still pass
        assert classifier.validate_schema(invalid_valence), "Clamped affect should pass validation"


class TestEmojiUsage:
    """Test emoji-based affect classification."""
    
    def test_positive_emoji_detection(self):
        """Test that positive emojis increase valence."""
        classifier = UserAffectClassifier()
        
        no_emoji = classifier.classify("Thanks")
        with_emoji = classifier.classify("Thanks 😊")
        
        assert with_emoji.valence > no_emoji.valence, "Positive emoji should increase valence"
    
    def test_negative_emoji_detection(self):
        """Test that negative emojis decrease valence."""
        classifier = UserAffectClassifier()
        
        no_emoji = classifier.classify("Okay")
        with_emoji = classifier.classify("Okay 😡")
        
        assert with_emoji.valence < no_emoji.valence, "Negative emoji should decrease valence"
    
    def test_multiple_positive_emojis(self):
        """Test multiple positive emojis compound effect."""
        classifier = UserAffectClassifier()
        
        single = classifier.classify("Thanks 😊")
        multiple = classifier.classify("Thanks 😊 😄 👍")
        
        assert multiple.valence >= single.valence, "Multiple emojis should compound or maintain effect"
    
    def test_emoji_with_exclamation(self):
        """Test emoji combined with exclamation increases arousal."""
        classifier = UserAffectClassifier()
        
        calm = classifier.classify("Thanks 😊")
        excited = classifier.classify("Thanks! 😊")
        
        assert excited.arousal >= calm.arousal, "Exclamation should increase arousal"


class TestSarcasmIrony:
    """Test sarcasm and irony detection."""
    
    def test_quoted_sarcastic_text(self):
        """Test that quoted text reduces confidence (possible sarcasm)."""
        classifier = UserAffectClassifier()
        
        normal = classifier.classify("That's great")
        quoted = classifier.classify('"That\'s great"')
        
        # Quoted text might indicate sarcasm, reducing confidence
        assert quoted.confidence <= normal.confidence + 0.1, \
            "Quoted text should not increase confidence significantly"
    
    def test_sarcasm_marker(self):
        """Test /s sarcasm marker reduces confidence."""
        classifier = UserAffectClassifier()
        
        normal = classifier.classify("That's just wonderful")
        sarcastic = classifier.classify("That's just wonderful /s")
        
        assert sarcastic.confidence < normal.confidence, "/s should reduce confidence"
    
    def test_sure_but_pattern(self):
        """Test 'sure... but' pattern as potential sarcasm."""
        classifier = UserAffectClassifier()
        
        sincere = classifier.classify("Sure, I'll help")
        possibly_sarcastic = classifier.classify("Sure... but that's not what I meant")
        
        assert possibly_sarcastic.confidence < sincere.confidence, \
            "'sure... but' pattern should reduce confidence"
    
    def test_oh_sure_pattern(self):
        """Test 'oh sure/great' as potential sarcasm."""
        classifier = UserAffectClassifier()
        
        sincere = classifier.classify("Sure, great idea!")
        sarcastic = classifier.classify("Oh sure, great idea...")
        
        assert sarcastic.confidence < sincere.confidence, \
            "'Oh sure' pattern should reduce confidence"


class TestBusyColdResponses:
    """Test busy and cold response patterns."""
    
    def test_busy_indicators(self):
        """Test busy indicators produce low arousal."""
        classifier = UserAffectClassifier()
        
        busy_responses = ["busy", "gtg", "gotta go", "leaving now", "ttyl", "brb"]
        
        for response in busy_responses:
            affect = classifier.classify(response)
            assert affect.arousal <= 0.5, f"Busy response '{response}' should have low arousal"
    
    def test_single_word_responses(self):
        """Test single word responses have specific handling."""
        classifier = UserAffectClassifier()
        
        short_responses = ["k", "ok", "okay", "fine", "sure", "yeah"]
        
        for response in short_responses:
            affect = classifier.classify(response)
            assert affect.arousal <= 0.4, f"Short response '{response}' should have low arousal"
            assert affect.confidence < 0.7, f"Short response '{response}' should have lower confidence"
    
    def test_dismissive_responses(self):
        """Test dismissive responses."""
        classifier = UserAffectClassifier()
        
        dismissive = classifier.classify("whatever")
        assert dismissive.valence <= 0.0, "Dismissive should be neutral or negative"
    
    def test_dots_only(self):
        """Test dots-only response."""
        classifier = UserAffectClassifier()
        
        dots = classifier.classify("...")
        assert dots.arousal <= 0.2, "Dots only should have very low arousal"
        assert dots.confidence < 0.6, "Dots only should have low confidence"


class TestPositiveNegativeSentiment:
    """Test positive and negative sentiment detection."""
    
    def test_clear_positive(self):
        """Test clearly positive message."""
        affect = classify_user_affect("I love this! It's amazing and wonderful!")
        
        assert affect.valence > 0.3, "Clear positive should have positive valence"
        assert "positive" in " ".join(affect.evidence).lower() or affect.valence > 0, \
            "Evidence should reflect positive sentiment"
    
    def test_clear_negative(self):
        """Test clearly negative message."""
        affect = classify_user_affect("This is terrible! I hate it so much!")
        
        assert affect.valence < -0.2, "Clear negative should have negative valence"
    
    def test_mixed_sentiment(self):
        """Test mixed sentiment reduces confidence."""
        classifier = UserAffectClassifier()
        
        clear = classifier.classify("I love this!")
        mixed = classifier.classify("I love this but hate that")
        
        # Mixed should have lower confidence or more neutral valence
        assert abs(mixed.valence) < abs(clear.valence) or mixed.confidence < clear.confidence, \
            "Mixed sentiment should result in less extreme classification"
    
    def test_neutral_message(self):
        """Test neutral message."""
        affect = classify_user_affect("The meeting is at 3pm.")
        
        assert abs(affect.valence) < 0.3, "Neutral message should have near-zero valence"
    
    def test_thank_you_variations(self):
        """Test thank you variations are positive."""
        variations = ["thanks", "thank you", "thanks!", "thank you so much"]
        
        for v in variations:
            affect = classify_user_affect(v)
            assert affect.valence >= 0.0, f"'{v}' should be neutral or positive"


class TestLowConfidenceEdgeCases:
    """Test low confidence handling and edge cases."""
    
    def test_empty_message(self):
        """Test empty message handling."""
        affect = classify_user_affect("")
        
        assert affect.valence == 0.0, "Empty message should have neutral valence"
        assert affect.confidence < 0.5, "Empty message should have low confidence"
        assert affect.is_low_confidence(), "Empty message should be marked as low confidence"
    
    def test_whitespace_only(self):
        """Test whitespace-only message."""
        affect = classify_user_affect("   ")
        
        assert affect.valence == 0.0, "Whitespace should have neutral valence"
        assert affect.is_low_confidence(), "Whitespace should be low confidence"
    
    def test_very_short_message(self):
        """Test very short message."""
        affect = classify_user_affect("hi")
        
        assert affect.confidence < 0.7, "Very short message should have reduced confidence"
    
    def test_low_confidence_threshold(self):
        """Test that low confidence is correctly identified."""
        classifier = UserAffectClassifier()
        
        # Create an affect with low confidence
        low_conf = UserAffect(valence=0.5, arousal=0.3, confidence=0.4, evidence=["test"])
        
        assert low_conf.is_low_confidence(), "0.4 confidence should be below threshold"
        
        # Create an affect with high confidence
        high_conf = UserAffect(valence=0.5, arousal=0.3, confidence=0.7, evidence=["test"])
        
        assert not high_conf.is_low_confidence(), "0.7 confidence should be above threshold"
    
    def test_low_confidence_pulls_valence_neutral(self):
        """Test that low confidence pulls valence toward neutral."""
        classifier = UserAffectClassifier()
        
        # Very short ambiguous text should have low confidence
        affect = classifier.classify("ok")
        
        if affect.is_low_confidence():
            assert abs(affect.valence) < 0.4, \
                "Low confidence should have valence pulled toward neutral"


class TestLowConfidenceIsolation:
    """Test that low confidence never triggers high-impact events."""
    
    def test_low_confidence_never_extreme(self):
        """Test that low confidence results don't have extreme valence."""
        classifier = UserAffectClassifier()
        
        # Force low confidence scenarios
        low_conf_texts = ["", "...", "k", "hmm", "um"]
        
        for text in low_conf_texts:
            affect = classifier.classify(text)
            if affect.is_low_confidence():
                # Low confidence should never have extreme valence
                assert abs(affect.valence) < 0.7, \
                    f"Low confidence should not have extreme valence: {text}"
    
    def test_affect_metadata_no_high_impact(self):
        """Test that affect output has no high-impact flags."""
        affect = get_affect_for_emotiond("Any message")
        
        # Affect should never contain high-impact indicators
        assert "is_high_impact" not in affect, "Affect should not have high-impact flag"
        assert "should_send" not in affect, "Affect should not have send control"
        assert "fallback" not in affect, "Affect should not have fallback control"
    
    def test_affect_never_triggers_betrayal_rejection(self):
        """Test that affect output can never indicate betrayal/rejection."""
        classifier = UserAffectClassifier()
        
        # Even with very negative text, affect should not trigger high-impact events
        negative_texts = [
            "I hate you",
            "You betrayed me",
            "I reject your offer",
            "This is a betrayal",
        ]
        
        for text in negative_texts:
            affect = classifier.classify(text)
            d = affect.to_dict()
            
            # Affect should only contain valence/arousal/confidence/evidence
            # No subtype or event trigger fields
            assert "subtype" not in d, "Affect should not have subtype field"
            assert "is_high_impact" not in d, "Affect should not have is_high_impact"


class TestAffectIntegration:
    """Test integration with emotiond API."""
    
    def test_get_affect_for_emotiond_format(self):
        """Test that get_affect_for_emotiond returns correct format."""
        result = get_affect_for_emotiond("Hello!")
        
        assert isinstance(result, dict), "Should return dict"
        assert "valence" in result
        assert "arousal" in result
        assert "confidence" in result
        assert "evidence" in result
    
    def test_json_serialization(self):
        """Test JSON serialization of affect."""
        affect = classify_user_affect("Test message")
        
        json_str = affect.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["valence"] == affect.valence
        assert parsed["arousal"] == affect.arousal
        assert parsed["confidence"] == affect.confidence
    
    def test_schema_file_exists(self):
        """Test that schema file exists and is valid JSON."""
        schema_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "integrations/openclaw/schemas/user_affect.schema.json"
        )
        
        assert os.path.exists(schema_path), "Schema file should exist"
        
        with open(schema_path) as f:
            schema = json.load(f)
        
        assert "properties" in schema
        assert "valence" in schema["properties"]
        assert "arousal" in schema["properties"]
        assert "confidence" in schema["properties"]
        assert "evidence" in schema["properties"]


class TestAdditionalEdgeCases:
    """Additional edge case tests."""
    
    def test_repeated_punctuation(self):
        """Test repeated punctuation increases arousal."""
        classifier = UserAffectClassifier()
        
        normal = classifier.classify("Wow")
        excited = classifier.classify("Wow!!!")
        
        assert excited.arousal > normal.arousal, "Repeated ! should increase arousal"
    
    def test_all_caps(self):
        """Test all caps increases arousal."""
        classifier = UserAffectClassifier()
        
        normal = classifier.classify("hello")
        caps = classifier.classify("HELLO")
        
        assert caps.arousal >= normal.arousal, "All caps should increase or maintain arousal"
    
    def test_question_marks(self):
        """Test question marks affect arousal."""
        classifier = UserAffectClassifier()
        
        statement = classifier.classify("What")
        question = classifier.classify("What??")
        
        assert question.arousal >= statement.arousal, "Question marks should increase arousal"
    
    def test_very_long_message(self):
        """Test very long message handling."""
        long_text = "This is a great day! " * 50
        affect = classify_user_affect(long_text)
        
        # Should still produce valid output
        assert -1.0 <= affect.valence <= 1.0
        assert 0.0 <= affect.arousal <= 1.0
        assert 0.0 <= affect.confidence <= 1.0
    
    def test_special_characters(self):
        """Test message with special characters."""
        affect = classify_user_affect("Hello @user #tag $100 %50 &more *star*")
        
        # Should handle without error
        assert isinstance(affect.valence, float)
        assert isinstance(affect.arousal, float)
    
    def test_unicode_handling(self):
        """Test unicode text handling."""
        affect = classify_user_affect("你好世界 Привет мир")
        
        # Should handle unicode without error
        assert isinstance(affect.valence, float)
        assert isinstance(affect.evidence, list)
    
    def test_code_snippet(self):
        """Test code snippet in message."""
        affect = classify_user_affect("```python\nprint('hello')\n```")
        
        # Should handle code blocks
        assert isinstance(affect.confidence, float)


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
