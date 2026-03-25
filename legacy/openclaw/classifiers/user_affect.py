"""
User Affect Classifier v0

Classifies user message text into affect dimensions:
- valence: -1.0 (negative) to 1.0 (positive)
- arousal: 0.0 (calm) to 1.0 (excited/agitated)
- confidence: 0.0 to 1.0 (classification certainty)

Key principles:
- Low confidence (<0.55): output neutral/uncertain style
- Affect NEVER triggers high-impact events (betrayal/rejection)
- Only used for tone modulation, not decision changes
"""

import re
from dataclasses import dataclass
from typing import List, Tuple, Optional
import json


@dataclass
class UserAffect:
    """Represents the affective state detected from user message."""
    valence: float  # -1.0 to 1.0
    arousal: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    evidence: List[str]
    
    def __post_init__(self):
        """Validate ranges after initialization."""
        self.valence = max(-1.0, min(1.0, self.valence))
        self.arousal = max(0.0, min(1.0, self.arousal))
        self.confidence = max(0.0, min(1.0, self.confidence))
        self.evidence = self.evidence[:3]  # Max 3 evidence items
    
    def is_low_confidence(self) -> bool:
        """Check if confidence is below threshold for uncertain handling."""
        return self.confidence < 0.55
    
    def to_dict(self) -> dict:
        """Convert to dictionary matching schema."""
        return {
            "valence": round(self.valence, 2),
            "arousal": round(self.arousal, 2),
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class UserAffectClassifier:
    """
    Heuristic-based user affect classifier.
    
    Uses pattern matching on text to estimate:
    - Valence: positive vs negative sentiment
    - Arousal: energy level (calm vs excited)
    - Confidence: certainty of classification
    """
    
    # Thresholds
    LOW_CONFIDENCE_THRESHOLD = 0.55
    
    # Positive patterns (valence > 0)
    POSITIVE_WORDS = {
        'thanks', 'thank', 'great', 'awesome', 'amazing', 'wonderful',
        'love', 'happy', 'glad', 'excited', 'perfect', 'excellent',
        'fantastic', 'brilliant', 'nice', 'good', 'appreciate', 'helpful',
        'cool', 'wow', 'yay', 'haha', 'lol', 'hehe', '😊', '😄', '👍',
        'please', 'yes', 'sure', 'ok', 'okay', 'alright', 'fine'
    }
    
    # Negative patterns (valence < 0)
    NEGATIVE_WORDS = {
        'sorry', 'bad', 'terrible', 'awful', 'hate', 'angry', 'frustrated',
        'annoyed', 'upset', 'disappointed', 'sad', 'worried', 'concerned',
        'problem', 'issue', 'error', 'wrong', 'fail', 'failed', 'broken',
        'stupid', 'dumb', 'useless', 'waste', 'never', 'don\'t', "don't",
        'no', 'not', 'can\'t', "can't", 'won\'t', "won't", 'ugh', 'meh',
        '😡', '😠', '😞', '😢', '😭', '👎'
    }
    
    # High arousal indicators
    HIGH_AROUSAL_PATTERNS = [
        r'[!?]{2,}',  # Multiple punctuation
        r'[A-Z]{3,}',  # All caps words
        r'!+$',  # Exclamation at end
        r'\?+$',  # Question marks at end
        r'(haha|lol|lmao|rofl){2,}',  # Repeated laughter
        r'(so|very|really|super|extremely)\s+\w+',  # Intensifiers
    ]
    
    # Low arousal indicators
    LOW_AROUSAL_PATTERNS = [
        r'^\.+$',  # Just dots
        r'^\.\.\.+$',  # Ellipsis
        r'^(ok|okay|k|fine|sure|yeah|yep|nope|nah)\.?$',  # One-word responses
        r'^(hm+|mm+|uh+h?|um+)\.?$',  # Hesitation sounds
    ]
    
    # Sarcasm/irony indicators (reduces confidence)
    SARCASM_INDICATORS = [
        r'"[^"]*"',  # Quoted text (could be sarcastic)
        r'``[^``]*``',  # Code blocks
        r'(^|\s)/[sr](\s|$)',  # /s or /r sarcasm markers
        r'sure\.+\s*(but|however|though)',
        r'right\.+',
        r'oh\s+(really|sure|great|wonderful)',
        r'yeah\s+right',
        r'as\s+if',
    ]
    
    # Busy/cold response patterns
    BUSY_COLD_PATTERNS = [
        r'^(busy|gtg|gotta go|leaving|ttyl|brb|afk)',
        r'^(later|bye|cya|see\s*ya)',
        r'^(k|ok|okay)\.?$',  # Short acknowledgement
        r'^\.+$',  # Just dots
        r'^(fine|whatever)\.?$',  # Dismissive
    ]
    
    def __init__(self):
        """Initialize the classifier."""
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile regex patterns for efficiency."""
        self._high_arousal_re = [re.compile(p, re.IGNORECASE) for p in self.HIGH_AROUSAL_PATTERNS]
        self._low_arousal_re = [re.compile(p, re.IGNORECASE) for p in self.LOW_AROUSAL_PATTERNS]
        self._sarcasm_re = [re.compile(p, re.IGNORECASE) for p in self.SARCASM_INDICATORS]
        self._busy_cold_re = [re.compile(p, re.IGNORECASE) for p in self.BUSY_COLD_PATTERNS]
    
    def classify(self, text: str) -> UserAffect:
        """
        Classify user message text into affect dimensions.
        
        Args:
            text: User message text to classify
            
        Returns:
            UserAffect object with valence, arousal, confidence, and evidence
        """
        if not text or not text.strip():
            return UserAffect(
                valence=0.0,
                arousal=0.0,
                confidence=0.3,
                evidence=["empty or whitespace message"]
            )
        
        text = text.strip()
        evidence: List[str] = []
        
        # Calculate base scores
        valence_score, valence_evidence = self._calculate_valence(text)
        arousal_score, arousal_evidence = self._calculate_arousal(text)
        confidence_score = 0.6  # Base confidence
        
        # Adjust confidence based on signal strength
        evidence.extend(valence_evidence[:2])
        evidence.extend(arousal_evidence[:1])
        
        # Check for sarcasm (reduces confidence)
        sarcasm_detected, sarcasm_evidence = self._detect_sarcasm(text)
        if sarcasm_detected:
            confidence_score -= 0.25
            evidence.append(sarcasm_evidence)
        
        # Check for busy/cold responses (specific handling)
        is_busy_cold, busy_evidence = self._detect_busy_cold(text)
        if is_busy_cold:
            arousal_score = min(arousal_score, 0.3)  # Low arousal for busy/cold
            evidence.append(busy_evidence)
        
        # Adjust confidence based on text length (shorter = less signal)
        if len(text) < 5:
            confidence_score -= 0.2
        elif len(text) < 15:
            confidence_score -= 0.1
        
        # Adjust confidence based on mixed signals
        if abs(valence_score) < 0.2:
            confidence_score -= 0.15
            if not evidence:
                evidence.append("neutral sentiment detected")
        
        # Clamp confidence
        confidence_score = max(0.1, min(1.0, confidence_score))
        
        # If low confidence, adjust valence toward neutral
        if confidence_score < self.LOW_CONFIDENCE_THRESHOLD:
            valence_score *= 0.5  # Pull toward neutral
            evidence.append("low confidence - using conservative estimate")
        
        return UserAffect(
            valence=valence_score,
            arousal=arousal_score,
            confidence=confidence_score,
            evidence=evidence[:3]
        )
    
    def _calculate_valence(self, text: str) -> Tuple[float, List[str]]:
        """Calculate valence score and collect evidence."""
        text_lower = text.lower()
        words = set(re.findall(r'\b\w+\b', text_lower))
        
        # Check for emojis
        has_positive_emoji = any(e in text for e in ['😊', '😄', '👍', '😀', '😁', '🙂', '🎉', '❤️', '💕'])
        has_negative_emoji = any(e in text for e in ['😡', '😠', '😞', '😢', '😭', '👎', '😤', '💔'])
        
        positive_count = len(words & self.POSITIVE_WORDS)
        negative_count = len(words & self.NEGATIVE_WORDS)
        
        # Add emoji counts
        if has_positive_emoji:
            positive_count += 1
        if has_negative_emoji:
            negative_count += 1
        
        evidence = []
        
        # Calculate base valence
        total = positive_count + negative_count
        if total == 0:
            return 0.0, ["no clear sentiment signals"]
        
        valence = (positive_count - negative_count) / max(total, 1)
        
        # Scale based on signal strength
        valence = valence * min(1.0, total / 3)  # More signals = more extreme
        
        # Collect evidence
        if positive_count > negative_count:
            evidence.append(f"positive signals: {positive_count}")
        elif negative_count > positive_count:
            evidence.append(f"negative signals: {negative_count}")
        else:
            evidence.append("mixed sentiment signals")
        
        return valence, evidence
    
    def _calculate_arousal(self, text: str) -> Tuple[float, List[str]]:
        """Calculate arousal score and collect evidence."""
        arousal = 0.3  # Base arousal
        evidence = []
        
        # Check high arousal patterns
        high_matches = sum(1 for pattern in self._high_arousal_re if pattern.search(text))
        if high_matches > 0:
            arousal += 0.2 * high_matches
            evidence.append("high energy indicators present")
        
        # Check low arousal patterns
        low_matches = sum(1 for pattern in self._low_arousal_re if pattern.search(text))
        if low_matches > 0:
            arousal -= 0.15 * low_matches
            evidence.append("low energy indicators present")
        
        # Check for exclamation marks
        exclamation_count = text.count('!')
        if exclamation_count >= 3:
            arousal += 0.3
            evidence.append("multiple exclamation marks")
        elif exclamation_count >= 1:
            arousal += 0.1
        
        # Check for question marks
        question_count = text.count('?')
        if question_count >= 2:
            arousal += 0.15
        
        # Check for all caps words
        caps_words = re.findall(r'\b[A-Z]{2,}\b', text)
        if len(caps_words) > 0:
            arousal += 0.2
            evidence.append("caps lock usage detected")
        
        return max(0.0, min(1.0, arousal)), evidence
    
    def _detect_sarcasm(self, text: str) -> Tuple[bool, str]:
        """Detect potential sarcasm/irony."""
        for pattern in self._sarcasm_re:
            if pattern.search(text):
                return True, "possible sarcasm/irony detected"
        return False, ""
    
    def _detect_busy_cold(self, text: str) -> Tuple[bool, str]:
        """Detect busy or cold response patterns."""
        for pattern in self._busy_cold_re:
            if pattern.search(text):
                return True, "busy/cold response pattern"
        return False, ""
    
    def validate_schema(self, affect: UserAffect) -> bool:
        """Validate that affect matches the schema requirements."""
        d = affect.to_dict()
        
        # Check required fields
        required = ['valence', 'arousal', 'confidence', 'evidence']
        if not all(k in d for k in required):
            return False
        
        # Check ranges
        if not -1.0 <= d['valence'] <= 1.0:
            return False
        if not 0.0 <= d['arousal'] <= 1.0:
            return False
        if not 0.0 <= d['confidence'] <= 1.0:
            return False
        
        # Check evidence
        if not isinstance(d['evidence'], list):
            return False
        if len(d['evidence']) > 3:
            return False
        for item in d['evidence']:
            if not isinstance(item, str) or len(item) > 160:
                return False
        
        return True


# Convenience function
def classify_user_affect(text: str) -> UserAffect:
    """
    Classify user message text into affect dimensions.
    
    Args:
        text: User message text to classify
        
    Returns:
        UserAffect object with valence, arousal, confidence, and evidence
    """
    classifier = UserAffectClassifier()
    return classifier.classify(text)


# For integration with emotiond
def get_affect_for_emotiond(text: str) -> dict:
    """
    Get affect classification formatted for emotiond API.
    
    This function is designed to be called from the emotiond-bridge hook
    to pass affect information to emotiond for tone modulation.
    
    Args:
        text: User message text
        
    Returns:
        Dict matching user_affect.schema.json
    """
    affect = classify_user_affect(text)
    return affect.to_dict()
