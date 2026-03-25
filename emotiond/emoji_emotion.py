"""
Emoji-Emotion Mapping Module

Provides:
- Basic emoji emotion scores from EmoTag dataset
- Context-aware emotion adjustment
- User-specific learning
- Integration with emotiond world_event
"""

import csv
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import emoji  # pip install emoji

logger = logging.getLogger("emotiond.emoji_emotion")

# EmoTag 8 emotions to emotiond mapping
EMOTAG_EMOTIONS = ["anger", "anticipation", "disgust", "fear", "joy", "sadness", "surprise", "trust"]

# emotiond emotion dimensions
EMOTIOND_EMOTIONS = ["joy", "sadness", "anger", "anxiety", "loneliness"]

# Mapping from EmoTag to emotiond emotions
# EmoTag -> emotiond (weight)
EMOTAG_TO_EMOTIOND = {
    "joy": {"joy": 1.0, "sadness": -0.3, "anger": -0.2},
    "sadness": {"sadness": 1.0, "joy": -0.3, "loneliness": 0.5},
    "anger": {"anger": 1.0, "joy": -0.4},
    "fear": {"anxiety": 0.8, "sadness": 0.3},
    "disgust": {"anger": 0.5, "sadness": 0.3},
    "anticipation": {"joy": 0.3, "anxiety": 0.2},
    "surprise": {"joy": 0.2, "anxiety": 0.3},
    "trust": {"joy": 0.3, "loneliness": -0.2},
}


@dataclass
class EmojiEmotionScore:
    """Emoji emotion score from EmoTag dataset."""
    unicode: str
    emoji: str
    name: str
    anger: float
    anticipation: float
    disgust: float
    fear: float
    joy: float
    sadness: float
    surprise: float
    trust: float
    
    def to_dict(self) -> Dict:
        return {
            "unicode": self.unicode,
            "emoji": self.emoji,
            "name": self.name,
            "anger": self.anger,
            "anticipation": self.anticipation,
            "disgust": self.disgust,
            "fear": self.fear,
            "joy": self.joy,
            "sadness": self.sadness,
            "surprise": self.surprise,
            "trust": self.trust,
        }
    
    def get_dominant_emotion(self) -> Tuple[str, float]:
        """Get the dominant emotion and its score."""
        emotions = {
            "anger": self.anger,
            "anticipation": self.anticipation,
            "disgust": self.disgust,
            "fear": self.fear,
            "joy": self.joy,
            "sadness": self.sadness,
            "surprise": self.surprise,
            "trust": self.trust,
        }
        dominant = max(emotions, key=emotions.get)
        return dominant, emotions[dominant]
    
    def to_emotiond_vector(self) -> Dict[str, float]:
        """Convert EmoTag scores to emotiond emotion vector."""
        result = {e: 0.0 for e in EMOTIOND_EMOTIONS}
        
        for emotag_emotion, score in [
            ("anger", self.anger),
            ("anticipation", self.anticipation),
            ("disgust", self.disgust),
            ("fear", self.fear),
            ("joy", self.joy),
            ("sadness", self.sadness),
            ("surprise", self.surprise),
            ("trust", self.trust),
        ]:
            if score > 0:
                mapping = EMOTAG_TO_EMOTIOND.get(emotag_emotion, {})
                for emotiond_emotion, weight in mapping.items():
                    result[emotiond_emotion] += score * weight
        
        # Clamp to [0, 1]
        for k in result:
            result[k] = max(0.0, min(1.0, result[k]))
        
        return result


class EmojiEmotionMapper:
    """Maps emojis to emotion scores with context awareness."""
    
    def __init__(self, data_path: Optional[Path] = None):
        self.data_path = data_path or Path(__file__).parent.parent / "data" / "emoji" / "EmoTag1200-scores.csv"
        self.emoji_scores: Dict[str, EmojiEmotionScore] = {}
        self._load_data()
    
    def _load_data(self):
        """Load EmoTag dataset."""
        if not self.data_path.exists():
            logger.warning(f"Emoji emotion data not found: {self.data_path}")
            return
        
        with open(self.data_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                score = EmojiEmotionScore(
                    unicode=row["unicode"],
                    emoji=row["emoji"],
                    name=row["name"],
                    anger=float(row["anger"]),
                    anticipation=float(row["anticipation"]),
                    disgust=float(row["disgust"]),
                    fear=float(row["fear"]),
                    joy=float(row["joy"]),
                    sadness=float(row["sadness"]),
                    surprise=float(row["surprise"]),
                    trust=float(row["trust"]),
                )
                self.emoji_scores[score.emoji] = score
        
        logger.info(f"Loaded {len(self.emoji_scores)} emoji emotion scores")
    
    def extract_emojis(self, text: str) -> List[str]:
        """Extract emojis from text."""
        return [char for char in text if char in emoji.EMOJI_DATA]
    
    def get_emoji_score(self, emoji_char: str) -> Optional[EmojiEmotionScore]:
        """Get emotion score for an emoji."""
        return self.emoji_scores.get(emoji_char)
    
    def analyze_text(
        self, 
        text: str, 
        context: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict:
        """
        Analyze text and extract emoji-based emotion vector.
        
        Args:
            text: The text to analyze
            context: Optional context for context-aware analysis
            user_id: Optional user ID for personalized analysis
            
        Returns:
            Dict with emoji_emotions, aggregated_emotiond_vector, and metadata
        """
        emojis = self.extract_emojis(text)
        
        if not emojis:
            return {
                "emojis": [],
                "emoji_emotions": [],
                "aggregated_vector": {e: 0.0 for e in EMOTIOND_EMOTIONS},
                "dominant_emotion": None,
                "confidence": 0.0,
            }
        
        emoji_emotions = []
        aggregated = {e: 0.0 for e in EMOTIOND_EMOTIONS}
        
        for emj in emojis:
            score = self.get_emoji_score(emj)
            if score:
                emotiond_vec = score.to_emotiond_vector()
                dominant, dom_score = score.get_dominant_emotion()
                
                emoji_emotions.append({
                    "emoji": emj,
                    "name": score.name,
                    "emotag_scores": score.to_dict(),
                    "emotiond_vector": emotiond_vec,
                    "dominant_emotag": dominant,
                    "dominant_score": dom_score,
                })
                
                # Aggregate
                for k, v in emotiond_vec.items():
                    aggregated[k] += v
        
        # Average
        if emojis:
            for k in aggregated:
                aggregated[k] /= len(emojis)
        
        # Find dominant
        dominant_emotion = max(aggregated, key=aggregated.get) if any(aggregated.values()) else None
        confidence = aggregated[dominant_emotion] if dominant_emotion else 0.0
        
        return {
            "emojis": emojis,
            "emoji_emotions": emoji_emotions,
            "aggregated_vector": aggregated,
            "dominant_emotion": dominant_emotion,
            "confidence": confidence,
        }
    
    def to_world_event(
        self,
        text: str,
        actor: str,
        target: str,
        context: Optional[str] = None,
        threshold: float = 0.3,
        adjusted_vector: Optional[Dict] = None,
        context_multiplier: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Convert text with emojis to a world_event dict.
        
        Args:
            text: The text containing emojis
            actor: Who sent the message
            target: Who received the message
            context: Optional context
            threshold: Minimum confidence to generate event
            adjusted_vector: Context-adjusted emotion vector
            context_multiplier: Context multipliers applied
            
        Returns:
            world_event dict or None if no significant emoji emotion
        """
        analysis = self.analyze_text(text)
        
        # Use adjusted vector if provided
        emotiond_vec = adjusted_vector if adjusted_vector else analysis["aggregated_vector"]
        
        # Find dominant emotion from adjusted vector (use absolute value)
        if emotiond_vec:
            dominant = max(emotiond_vec, key=lambda k: abs(emotiond_vec[k]))
            confidence = abs(emotiond_vec.get(dominant, 0))
        else:
            dominant = None
            confidence = 0
        
        if confidence < threshold:
            return None
        
        # Map to world_event subtype based on adjusted emotions
        # Handle sarcasm (negative joy)
        if emotiond_vec.get("joy", 0) < 0:
            # Sarcasm detected - map to negative emotion
            if emotiond_vec.get("anger", 0) > 0.3:
                subtype = "betrayal"
            else:
                subtype = "rejection"
        elif emotiond_vec.get("anger", 0) > 0.5:
            subtype = "betrayal"  # High impact
        elif emotiond_vec.get("sadness", 0) > 0.5:
            subtype = "rejection"
        elif emotiond_vec.get("joy", 0) > 0.3:
            subtype = "care"
        else:
            subtype = "ignored"
        
        # Calculate intensity from absolute values
        intensity = min(1.0, confidence * 1.5)
        
        return {
            "type": "world_event",
            "actor": actor,
            "target": target,
            "meta": {
                "subtype": subtype,
                "seconds": 30,
                "intensity": intensity,
                "emoji_source": analysis["emojis"],
                "emotiond_vector": emotiond_vec,
                "context_multiplier": context_multiplier,
                "original_text_preview": text[:100],
            }
        }

# Singleton instance
_mapper: Optional[EmojiEmotionMapper] = None

def get_emoji_mapper() -> EmojiEmotionMapper:
    """Get or create the singleton EmojiEmotionMapper."""
    global _mapper
    if _mapper is None:
        _mapper = EmojiEmotionMapper()
    return _mapper


if __name__ == "__main__":
    # Test
    mapper = get_emoji_mapper()
    
    test_texts = [
        "你好！很高兴见到你 😄",
        "哈哈，真有趣 😂",
        "好难过啊 😢",
        "你太过分了！😠",
        "不错 👍",
        "差评 👎",
    ]
    
    print("=== Emoji Emotion Analysis ===\n")
    for text in test_texts:
        result = mapper.analyze_text(text)
        print(f"Text: {text}")
        print(f"  Emojis: {result['emojis']}")
        print(f"  Dominant: {result['dominant_emotion']} ({result['confidence']:.2f})")
        print(f"  Vector: {result['aggregated_vector']}")
        print()


class ContextAwareEmojiAnalyzer:
    """
    Context-aware emoji emotion analyzer using LLM.
    
    Handles cases where the same emoji has different meanings:
    - "You're so smart! 😄" → genuine joy
    - "Oh sure, you're always right 😄" → sarcasm
    """
    
    def __init__(self, base_mapper: EmojiEmotionMapper):
        self.mapper = base_mapper
        self.llm_client = None  # Will be set by integration
    
    def analyze_with_context(
        self,
        text: str,
        conversation_history: Optional[List[str]] = None,
        relationship_context: Optional[Dict] = None,
        use_llm: bool = False
    ) -> Dict:
        """
        Analyze emoji emotions with context awareness.
        
        Args:
            text: Current text with emojis
            conversation_history: Previous messages in conversation
            relationship_context: Bond/trust with the other person
            use_llm: Whether to use LLM for context analysis
            
        Returns:
            Enhanced emotion analysis with context adjustments
        """
        # Base analysis
        base_result = self.mapper.analyze_text(text)
        
        if not base_result["emojis"]:
            return base_result
        
        # Context adjustments
        context_multiplier = self._compute_context_multiplier(
            text, conversation_history, relationship_context
        )
        
        # Adjust emotiond vector
        adjusted_vector = {}
        for emotion, value in base_result["aggregated_vector"].items():
            adjusted_vector[emotion] = value * context_multiplier.get(emotion, 1.0)
        
        base_result["aggregated_vector"] = adjusted_vector
        base_result["context_adjusted"] = True
        base_result["context_multiplier"] = context_multiplier
        
        return base_result
    
    def _compute_context_multiplier(
        self,
        text: str,
        history: Optional[List[str]],
        relationship: Optional[Dict]
    ) -> Dict[str, float]:
        """
        Compute emotion multipliers based on context.
        
        Returns multipliers for each emotion dimension.
        """
        multipliers = {e: 1.0 for e in EMOTIOND_EMOTIONS}
        
        # Sarcasm detection heuristics
        sarcasm_signals = [
            "呵呵", "哈哈", "哦", "嗯嗯", "行吧", "算了",
            "你开心就好", "随便", "无所谓"
        ]
        
        text_lower = text.lower()
        has_sarcasm_signal = any(s in text for s in sarcasm_signals)
        
        if has_sarcasm_signal:
            # Sarcasm flips positive emotions
            multipliers["joy"] *= -0.5  # Turn joy negative
            multipliers["anger"] *= 1.5  # Amplify hidden anger
            multipliers["sadness"] *= 1.3
        
        # Relationship context
        if relationship:
            bond = relationship.get("bond", 0.5)
            trust = relationship.get("trust", 0.5)
            
            # Low trust amplifies negative emotions
            if trust < 0.3:
                multipliers["anger"] *= 1.3
                multipliers["anxiety"] *= 1.2
            
            # High bond amplifies positive emotions
            if bond > 0.7:
                multipliers["joy"] *= 1.2
                multipliers["sadness"] *= 0.8  # More forgiving
        
        return multipliers
    
    def analyze_with_llm(
        self,
        text: str,
        conversation_context: str,
        model: str = "gpt-4"
    ) -> Dict:
        """
        Use LLM for deeper context analysis.
        
        This is a placeholder for LLM integration.
        In production, would call OpenAI/Anthropic API.
        """
        # Placeholder - would call LLM API
        # For now, use heuristics
        return self.analyze_with_context(
            text,
            conversation_history=[conversation_context],
            use_llm=False
        )


class EmojiLearningStore:
    """
    Store and learn from emoji usage patterns.
    
    Tracks:
    - User's typical emoji usage
    - Context → emotion mappings
    - Corrections and feedback
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path(__file__).parent.parent / "data" / "emoji_learning.db"
        self._init_db()
    
    def _init_db(self):
        """Initialize the learning database."""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS emoji_context_samples (
                id INTEGER PRIMARY KEY,
                emoji TEXT NOT NULL,
                text_context TEXT,
                detected_emotion TEXT,
                detected_intensity REAL,
                user_correction TEXT,
                corrected_emotion TEXT,
                corrected_intensity REAL,
                user_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_emoji_patterns (
                id INTEGER PRIMARY KEY,
                user_id TEXT NOT NULL,
                emoji TEXT NOT NULL,
                avg_joy REAL DEFAULT 0,
                avg_sadness REAL DEFAULT 0,
                avg_anger REAL DEFAULT 0,
                avg_anxiety REAL DEFAULT 0,
                usage_count INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, emoji)
            )
        """)
        conn.commit()
        conn.close()
    
    def record_usage(
        self,
        user_id: str,
        emoji: str,
        text_context: str,
        detected_emotion: str,
        detected_intensity: float
    ):
        """Record an emoji usage for learning."""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO emoji_context_samples 
            (emoji, text_context, detected_emotion, detected_intensity, user_id)
            VALUES (?, ?, ?, ?, ?)
        """, (emoji, text_context, detected_emotion, detected_intensity, user_id))
        
        # Update user pattern
        conn.execute("""
            INSERT INTO user_emoji_patterns (user_id, emoji, usage_count)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, emoji) DO UPDATE SET
                usage_count = usage_count + 1,
                last_updated = CURRENT_TIMESTAMP
        """, (user_id, emoji))
        
        conn.commit()
        conn.close()
    
    def record_correction(
        self,
        user_id: str,
        emoji: str,
        text_context: str,
        detected_emotion: str,
        corrected_emotion: str,
        corrected_intensity: float
    ):
        """Record a user correction for learning."""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            UPDATE emoji_context_samples 
            SET user_correction = 'yes',
                corrected_emotion = ?,
                corrected_intensity = ?
            WHERE emoji = ? AND text_context = ? AND user_id = ?
            ORDER BY created_at DESC LIMIT 1
        """, (corrected_emotion, corrected_intensity, emoji, text_context, user_id))
        conn.commit()
        conn.close()
    
    def get_user_pattern(self, user_id: str, emoji: str) -> Optional[Dict]:
        """Get learned pattern for a user's emoji usage."""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT avg_joy, avg_sadness, avg_anger, avg_anxiety, usage_count
            FROM user_emoji_patterns
            WHERE user_id = ? AND emoji = ?
        """, (user_id, emoji))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "joy": row[0],
                "sadness": row[1],
                "anger": row[2],
                "anxiety": row[3],
                "usage_count": row[4],
            }
        return None


# Convenience function for integration
def analyze_message_emojis(
    text: str,
    actor: str,
    target: str,
    conversation_history: Optional[List[str]] = None,
    relationship: Optional[Dict] = None,
    user_id: Optional[str] = None
) -> Tuple[Dict, Optional[Dict]]:
    """
    Analyze message and return emotion analysis + world_event if significant.
    
    Args:
        text: Message text
        actor: Message sender
        target: Message recipient
        conversation_history: Previous messages
        relationship: Relationship context (bond, trust, etc.)
        user_id: User ID for personalized learning
        
    Returns:
        Tuple of (analysis_result, world_event or None)
    """
    mapper = get_emoji_mapper()
    analyzer = ContextAwareEmojiAnalyzer(mapper)
    learner = EmojiLearningStore()
    
    # Context-aware analysis
    result = analyzer.analyze_with_context(
        text,
        conversation_history=conversation_history,
        relationship_context=relationship
    )
    
    # Record for learning
    if user_id and result["emojis"]:
        for emj in result["emojis"]:
            learner.record_usage(
                user_id=user_id,
                emoji=emj,
                text_context=text[:200],
                detected_emotion=result["dominant_emotion"] or "neutral",
                detected_intensity=result["confidence"]
            )
    
    # Generate world_event if significant (with adjusted vector)
    world_event = mapper.to_world_event(
        text=text,
        actor=actor,
        target=target,
        threshold=0.3,
        adjusted_vector=result.get("aggregated_vector"),
        context_multiplier=result.get("context_multiplier")
    )
    
    return result, world_event


if __name__ == "__main__":
    # Test context-aware analysis
    print("\n=== Context-Aware Analysis ===\n")
    
    mapper = get_emoji_mapper()
    analyzer = ContextAwareEmojiAnalyzer(mapper)
    
    test_cases = [
        ("You're so smart! 😄", {"bond": 0.8, "trust": 0.7}),
        ("Oh sure, you're always right 😄", {"bond": 0.3, "trust": 0.2}),
        ("呵呵，好的 😄", {"bond": 0.5, "trust": 0.4}),
        ("不错！继续加油 👍", {"bond": 0.9, "trust": 0.8}),
    ]
    
    for text, relationship in test_cases:
        result = analyzer.analyze_with_context(text, relationship_context=relationship)
        print(f"Text: {text}")
        print(f"  Relationship: bond={relationship.get('bond', 0):.1f}, trust={relationship.get('trust', 0):.1f}")
        print(f"  Dominant: {result['dominant_emotion']} ({result['confidence']:.2f})")
        if result.get("context_adjusted"):
            print(f"  Context multiplier: {result['context_multiplier']}")
        print()
