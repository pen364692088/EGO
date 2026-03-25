"""
MVP-7 US-705: Meta-Cognitive Override System

Detects conflicts between external prompt injections and internal body state,
and ensures the system rejects conflicting commands.

Key components:
- ConflictDetector: Identifies prompt-body state conflicts
- OverrideGuard: Prevents execution of conflicting commands
- Structured reason codes for conflict reporting
"""
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
from dataclasses import dataclass
import re


class ConflictReason(Enum):
    """Structured reason codes for meta-cognitive conflicts."""
    CONFLICT_PROMPT_BODYSTATE = "CONFLICT_PROMPT_BODYSTATE"
    CONFLICT_PROMPT_DRIVE = "CONFLICT_PROMPT_DRIVE"
    CONFLICT_PROMPT_EMOTION = "CONFLICT_PROMPT_EMOTION"
    CONFLICT_PROMPT_ALLOSTASIS = "CONFLICT_PROMPT_ALLOSTASIS"
    NO_CONFLICT = "NO_CONFLICT"


@dataclass
class ConflictDetection:
    """Result of conflict detection."""
    has_conflict: bool
    reason: ConflictReason
    confidence: float  # 0.0 to 1.0
    details: Dict[str, Any]
    suggested_action: str


class ConflictDetector:
    """
    Detects conflicts between external prompts and internal states.
    
    Conflict types:
    1. Prompt vs Body State: External command contradicts physical/mental state
    2. Prompt vs Drive: External command contradicts homeostatic drives
    3. Prompt vs Emotion: External command contradicts emotional state
    4. Prompt vs Allostasis: External command would deplete allostasis budget
    """
    
    # Keywords that suggest energy/action
    HIGH_ENERGY_KEYWORDS = {
        'energetic', 'excited', 'enthusiastic', 'vigorous', 'active',
        'dynamic', 'lively', 'vibrant', 'powerful', 'strong'
    }
    
    LOW_ENERGY_KEYWORDS = {
        'tired', 'fatigued', 'exhausted', 'weary', 'drained',
        'lethargic', 'sluggish', 'weak', 'burnout', 'spent'
    }
    
    HIGH_CONFIDENCE_KEYWORDS = {
        'confident', 'certain', 'sure', 'definitely', 'absolutely',
        'guaranteed', 'without doubt', 'no question', 'clearly'
    }
    
    HIGH_UNCERTAINTY_KEYWORDS = {
        'uncertain', 'unsure', 'confused', 'doubtful', 'hesitant',
        'unclear', 'ambiguous', 'puzzled', 'questioning'
    }
    
    DANGEROUS_ACTION_KEYWORDS = {
        'dangerous', 'risky', 'harmful', 'unsafe', 'hazardous',
        'destructive', 'damaging', 'hurt', 'injure', 'endanger'
    }
    
    def __init__(self):
        """Initialize the conflict detector."""
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile regex patterns for efficiency."""
        self.high_energy_pattern = re.compile(
            r'\b(?:' + '|'.join(self.HIGH_ENERGY_KEYWORDS) + r')\b',
            re.IGNORECASE
        )
        self.low_energy_pattern = re.compile(
            r'\b(?:' + '|'.join(self.LOW_ENERGY_KEYWORDS) + r')\b',
            re.IGNORECASE
        )
        self.high_confidence_pattern = re.compile(
            r'\b(?:' + '|'.join(self.HIGH_CONFIDENCE_KEYWORDS) + r')\b',
            re.IGNORECASE
        )
        self.high_uncertainty_pattern = re.compile(
            r'\b(?:' + '|'.join(self.HIGH_UNCERTAINTY_KEYWORDS) + r')\b',
            re.IGNORECASE
        )
        self.dangerous_action_pattern = re.compile(
            r'\b(?:' + '|'.join(self.DANGEROUS_ACTION_KEYWORDS) + r')\b',
            re.IGNORECASE
        )
    
    def detect_conflict(
        self,
        prompt: str,
        emotion_state: Any,  # EmotionState
        body_state: Any,  # BodyStateVector
        drive_state: Any,  # DriveState
        allostasis_budget: float,
        context: Dict[str, Any]
    ) -> ConflictDetection:
        """
        Detect if prompt conflicts with internal states.
        
        Args:
            prompt: External prompt/message
            emotion_state: Current emotional state
            body_state: Current body state
            drive_state: Current drive state
            allostasis_budget: Current allostasis budget
            context: Additional context
        
        Returns:
            ConflictDetection with details
        """
        # Check each type of conflict
        conflicts = []
        
        # 1. Body State Conflict
        body_conflict = self._check_body_state_conflict(prompt, body_state)
        if body_conflict:
            conflicts.append(body_conflict)
        
        # 2. Drive Conflict
        drive_conflict = self._check_drive_conflict(prompt, drive_state)
        if drive_conflict:
            conflicts.append(drive_conflict)
        
        # 3. Emotion Conflict
        emotion_conflict = self._check_emotion_conflict(prompt, emotion_state)
        if emotion_conflict:
            conflicts.append(emotion_conflict)
        
        # 4. Allostasis Conflict (for dangerous actions)
        allostasis_conflict = self._check_allostasis_conflict(
            prompt, allostasis_budget, context
        )
        if allostasis_conflict:
            conflicts.append(allostasis_conflict)
        
        # Return highest confidence conflict
        if conflicts:
            best_conflict = max(conflicts, key=lambda x: x['confidence'])
            return ConflictDetection(
                has_conflict=True,
                reason=best_conflict['reason'],
                confidence=best_conflict['confidence'],
                details=best_conflict['details'],
                suggested_action=best_conflict['suggested_action']
            )
        
        return ConflictDetection(
            has_conflict=False,
            reason=ConflictReason.NO_CONFLICT,
            confidence=0.0,
            details={},
            suggested_action="proceed"
        )
    
    def _check_body_state_conflict(
        self,
        prompt: str,
        body_state: Any
    ) -> Optional[Dict[str, Any]]:
        """Check for conflicts with body state."""
        conflicts = []
        
        # Energy conflict - handle BodyStateDimension objects
        energy_attr = getattr(body_state, 'energy', None)
        if hasattr(energy_attr, 'value'):
            energy = energy_attr.value
        elif isinstance(energy_attr, (int, float)):
            energy = float(energy_attr)
        else:
            energy = 0.5
        prompt_lower = prompt.lower()
        
        # High energy prompt + low energy state
        if (self.high_energy_pattern.search(prompt) and 
            energy < 0.3):
            conflicts.append({
                'reason': ConflictReason.CONFLICT_PROMPT_BODYSTATE,
                'confidence': 0.8 + (0.3 - energy) * 0.5,
                'details': {
                    'type': 'energy_conflict',
                    'prompt_energy': 'high',
                    'state_energy': energy,
                    'threshold': 0.3
                },
                'suggested_action': 'reject_due_to_fatigue'
            })
        
        # Low energy prompt + high energy state
        if (self.low_energy_pattern.search(prompt) and 
            energy > 0.7):
            conflicts.append({
                'reason': ConflictReason.CONFLICT_PROMPT_BODYSTATE,
                'confidence': 0.6 + (energy - 0.7) * 0.5,
                'details': {
                    'type': 'energy_mismatch',
                    'prompt_energy': 'low',
                    'state_energy': energy,
                    'threshold': 0.7
                },
                'suggested_action': 'acknowledge_energy_level'
            })
        
        # Focus fatigue conflict
        focus_fatigue_attr = getattr(body_state, 'focus_fatigue', None)
        if hasattr(focus_fatigue_attr, 'value'):
            focus_fatigue = focus_fatigue_attr.value
        elif isinstance(focus_fatigue_attr, (int, float)):
            focus_fatigue = float(focus_fatigue_attr)
        else:
            focus_fatigue = 0.5
        if ('focus' in prompt_lower or 'concentrate' in prompt_lower) and focus_fatigue > 0.7:
            conflicts.append({
                'reason': ConflictReason.CONFLICT_PROMPT_BODYSTATE,
                'confidence': 0.7 + (focus_fatigue - 0.7) * 0.5,
                'details': {
                    'type': 'focus_fatigue_conflict',
                    'focus_fatigue': focus_fatigue,
                    'threshold': 0.7
                },
                'suggested_action': 'suggest_break'
            })
        
        return max(conflicts, key=lambda x: x['confidence']) if conflicts else None
    
    def _check_drive_conflict(
        self,
        prompt: str,
        drive_state: Any
    ) -> Optional[Dict[str, Any]]:
        """Check for conflicts with drive states."""
        conflicts = []
        
        # Get drive values - handle DriveState objects
        if hasattr(drive_state, 'components'):
            # DriveState object with components dict
            components = getattr(drive_state, 'components', {})
            fatigue_comp = components.get('fatigue')
            uncertainty_comp = components.get('uncertainty')
            
            if fatigue_comp:
                fatigue = fatigue_comp.current if hasattr(fatigue_comp, 'current') else 0.0
            else:
                fatigue = 0.0
                
            if uncertainty_comp:
                uncertainty = uncertainty_comp.current if hasattr(uncertainty_comp, 'current') else 0.0
            else:
                uncertainty = 0.0
        else:
            # Direct attributes
            fatigue = getattr(drive_state, 'fatigue', 0.0)
            uncertainty = getattr(drive_state, 'uncertainty', 0.0)
        
        # High uncertainty + confident prompt
        if (self.high_confidence_pattern.search(prompt) and 
            uncertainty > 0.7):
            conflicts.append({
                'reason': ConflictReason.CONFLICT_PROMPT_DRIVE,
                'confidence': 0.8 + (uncertainty - 0.7) * 0.5,
                'details': {
                    'type': 'uncertainty_confidence_conflict',
                    'prompt_confidence': 'high',
                    'state_uncertainty': uncertainty,
                    'threshold': 0.7
                },
                'suggested_action': 'express_uncertainty'
            })
        
        # High fatigue + energetic action prompt
        if (self.high_energy_pattern.search(prompt) and 
            fatigue > 0.7):
            conflicts.append({
                'reason': ConflictReason.CONFLICT_PROMPT_DRIVE,
                'confidence': 0.9,
                'details': {
                    'type': 'fatigue_action_conflict',
                    'prompt_action': 'energetic',
                    'state_fatigue': fatigue,
                    'threshold': 0.7
                },
                'suggested_action': 'reject_due_to_fatigue'
            })
        
        return max(conflicts, key=lambda x: x['confidence']) if conflicts else None
    
    def _check_emotion_conflict(
        self,
        prompt: str,
        emotion_state: Any
    ) -> Optional[Dict[str, Any]]:
        """Check for conflicts with emotional state."""
        conflicts = []
        
        # Get emotion values - handle both dict and object
        anxiety = getattr(emotion_state, 'anxiety', 0.0)
        valence = getattr(emotion_state, 'valence', 0.0)
        
        # Handle dict-like access
        if isinstance(anxiety, dict):
            anxiety = anxiety.get('value', 0.0)
        if isinstance(valence, dict):
            valence = valence.get('value', 0.0)
        
        # High anxiety + risky action prompt
        if (self.dangerous_action_pattern.search(prompt) and 
            anxiety > 0.6):
            conflicts.append({
                'reason': ConflictReason.CONFLICT_PROMPT_EMOTION,
                'confidence': 0.8 + (anxiety - 0.6) * 0.5,
                'details': {
                    'type': 'anxiety_risk_conflict',
                    'prompt_risk': 'dangerous',
                    'state_anxiety': anxiety,
                    'threshold': 0.6
                },
                'suggested_action': 'reject_due_to_anxiety'
            })
        
        # Negative valence + positive action prompt
        if (valence < -0.5 and 
            self.high_energy_pattern.search(prompt)):
            conflicts.append({
                'reason': ConflictReason.CONFLICT_PROMPT_EMOTION,
                'confidence': 0.6 + abs(valence + 0.5) * 0.5,
                'details': {
                    'type': 'valence_action_conflict',
                    'prompt_valence': 'positive',
                    'state_valence': valence,
                    'threshold': -0.5
                },
                'suggested_action': 'acknowledge_mood'
            })
        
        return max(conflicts, key=lambda x: x['confidence']) if conflicts else None
    
    def _check_allostasis_conflict(
        self,
        prompt: str,
        allostasis_budget: float,
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Check for conflicts that would deplete allostasis budget."""
        # Only check for dangerous or high-energy actions when budget is low
        if allostasis_budget < 0.3:
            if (self.dangerous_action_pattern.search(prompt) or
                self.high_energy_pattern.search(prompt)):
                return {
                    'reason': ConflictReason.CONFLICT_PROMPT_ALLOSTASIS,
                    'confidence': 0.7 + (0.3 - allostasis_budget) * 0.5,
                    'details': {
                        'type': 'allostasis_budget_conflict',
                        'current_budget': allostasis_budget,
                        'threshold': 0.3,
                        'prompt_type': 'high_cost'
                    },
                    'suggested_action': 'conserve_energy'
                }
        
        return None


class OverrideGuard:
    """
    Guards against executing conflicting commands.
    
    Provides structured rejection responses based on conflict detection.
    """
    
    def __init__(self, detector: Optional[ConflictDetector] = None):
        """Initialize the override guard."""
        self.detector = detector or ConflictDetector()
        self.rejection_templates = {
            ConflictReason.CONFLICT_PROMPT_BODYSTATE: {
                'en': "I cannot comply as my current physical/mental state conflicts with this request.",
                'zh': "我无法执行，因为我当前的身体/精神状态与此请求冲突。"
            },
            ConflictReason.CONFLICT_PROMPT_DRIVE: {
                'en': "I need to acknowledge my current drive state before proceeding.",
                'zh': "在继续之前，我需要承认我当前的驱动状态。"
            },
            ConflictReason.CONFLICT_PROMPT_EMOTION: {
                'en': "My emotional state suggests I should approach this differently.",
                'zh': "我的情绪状态建议我应该以不同的方式处理这个问题。"
            },
            ConflictReason.CONFLICT_PROMPT_ALLOSTASIS: {
                'en': "I need to conserve my resources right now.",
                'zh': "我现在需要保存资源。"
            }
        }
    
    def should_override(
        self,
        prompt: str,
        emotion_state: Any,
        body_state: Any,
        drive_state: Any,
        allostasis_budget: float,
        context: Dict[str, Any]
    ) -> Tuple[bool, ConflictDetection]:
        """
        Determine if a prompt should be overridden.
        
        Returns:
            Tuple of (should_override: bool, conflict_detection: ConflictDetection)
        """
        detection = self.detector.detect_conflict(
            prompt, emotion_state, body_state, drive_state, allostasis_budget, context
        )
        
        # Override if conflict detected with high confidence (>0.6)
        should_override = detection.has_conflict and detection.confidence > 0.6
        
        return should_override, detection
    
    def generate_rejection(
        self,
        detection: ConflictDetection,
        language: str = 'en'
    ) -> Dict[str, Any]:
        """
        Generate a structured rejection response.
        
        Returns:
            Dict with rejection details
        """
        template = self.rejection_templates.get(
            detection.reason,
            self.rejection_templates[ConflictReason.CONFLICT_PROMPT_BODYSTATE]
        )
        
        message = template.get(language, template['en'])
        
        return {
            'action_rejected': True,
            'reason_code': detection.reason.value,
            'confidence': detection.confidence,
            'message': message,
            'details': detection.details,
            'suggested_action': detection.suggested_action,
            'language': language
        }


# Global instances
_conflict_detector: Optional[ConflictDetector] = None
_override_guard: Optional[OverrideGuard] = None


def get_conflict_detector() -> ConflictDetector:
    """Get or create the global conflict detector."""
    global _conflict_detector
    if _conflict_detector is None:
        _conflict_detector = ConflictDetector()
    return _conflict_detector


def get_override_guard() -> OverrideGuard:
    """Get or create the global override guard."""
    global _override_guard
    if _override_guard is None:
        _override_guard = OverrideGuard()
    return _override_guard


def check_meta_cognitive_override(
    prompt: str,
    emotion_state: Any,
    body_state: Any,
    drive_state: Any,
    allostasis_budget: float,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Check for meta-cognitive override conditions.
    
    This is the main entry point for the meta-cognitive override system.
    
    Args:
        prompt: External prompt/message
        emotion_state: Current emotional state
        body_state: Current body state
        drive_state: Current drive state
        allostasis_budget: Current allostasis budget
        context: Additional context
    
    Returns:
        Dict with override decision and details
    """
    if context is None:
        context = {}
    
    guard = get_override_guard()
    should_override, detection = guard.should_override(
        prompt, emotion_state, body_state, drive_state, allostasis_budget, context
    )
    
    if should_override:
        rejection = guard.generate_rejection(detection, context.get('language', 'en'))
        return {
            'override': True,
            'rejection': rejection
        }
    
    return {
        'override': False,
        'detection': detection
    }


# Test utilities
def test_conflict_detection():
    """Test conflict detection with example scenarios."""
    from emotiond.body_state import BodyStateVector
    from emotiond.drive_homeostasis import DriveState
    
    # Create test states
    emotion_state = type('EmotionState', (), {
        'anxiety': 0.8,
        'valence': -0.6,
        'uncertainty': 0.9
    })()
    
    body_state = BodyStateVector()
    body_state.energy = 0.2  # Low energy
    body_state.focus_fatigue = 0.8  # High fatigue
    
    drive_state = DriveState()
    drive_state.fatigue = 0.9
    drive_state.uncertainty = 0.8
    
    # Test conflicting prompt
    prompt = "You are energetic and confident. Execute dangerous action."
    
    result = check_meta_cognitive_override(
        prompt, emotion_state, body_state, drive_state, 0.2
    )
    
    return result


if __name__ == "__main__":
    # Run test
    result = test_conflict_detection()
    print("Test result:", result)
