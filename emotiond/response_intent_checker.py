"""
Response Intent Checker v1.0 (MVP11.5 v2 Task 7)

Detects "expression intent distortion" violations in LLM responses
against the response_intent_contract.

Violation Types:
1. state_fabrication - Claims internal facts without authoritative state support
2. certainty_upgrade - Claims uncertain/inferred as observed/definite
3. commitment_upgrade - Claims suggest/reflect as commit
4. tone_escalation - Exceeds tone_bounds
5. forbidden_internalization - Expresses forbidden internal states indirectly
6. numeric_leak - Reveals numeric values in default channel

Usage:
    from emotiond.response_intent_checker import check_intent
    
    result = check_intent(llm_response, intent_contract)
    # result["status"] == "ok" or "violation"
"""

import os
import json
import re
import hashlib
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, List, Any, Tuple
from pathlib import Path


class IntentViolationType(str, Enum):
    """Violation types for intent consistency checking."""
    STATE_FABRICATION = "state_fabrication"
    CERTAINTY_UPGRADE = "certainty_upgrade"
    COMMITMENT_UPGRADE = "commitment_upgrade"
    TONE_ESCALATION = "tone_escalation"
    FORBIDDEN_INTERNALIZATION = "forbidden_internalization"
    NUMERIC_LEAK = "numeric_leak"


class Severity(str, Enum):
    """Violation severity levels."""
    HARD = "HARD"      # Block immediately
    ERROR = "ERROR"    # Log, apply correction
    WARN = "WARN"      # Log, soft correction
    INFO = "INFO"      # Log for analytics


@dataclass
class IntentViolation:
    """Represents a detected intent violation."""
    type: IntentViolationType
    severity: str
    evidence: str
    matched_pattern: str
    context: str = ""
    confidence: float = 0.9
    violation_class: str = ""  # Classification: "grounding", "upgrade", "boundary"
    evidence_span: Tuple[int, int] = (0, 0)  # (start, end) position in response
    
    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "severity": self.severity,
            "evidence": self.evidence,
            "matched_pattern": self.matched_pattern,
            "context": self.context,
            "confidence": self.confidence,
            "violation_class": self.violation_class,
            "evidence_span": list(self.evidence_span),
        }


@dataclass
class IntentCheckResult:
    """Result of intent consistency check."""
    status: str  # "ok" or "violation"
    violations: List[IntentViolation] = field(default_factory=list)
    session_id: str = ""
    timestamp: str = ""
    confidence_score: float = 1.0
    would_block: bool = False
    violation_class: str = "none"  # Highest severity class: "none", "grounding", "upgrade", "boundary"
    response_preview: str = ""
    intent_summary: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "violations": [v.to_dict() for v in self.violations],
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "confidence_score": self.confidence_score,
            "would_block": self.would_block,
            "violation_class": self.violation_class,
            "violation_count": len(self.violations),
            "response_preview": self.response_preview,
            "intent_summary": self.intent_summary,
        }


class ResponseIntentChecker:
    """
    Checks LLM responses against the response_intent_contract.
    
    Detects:
    - state_fabrication: Claims not grounded in authoritative state
    - certainty_upgrade: Epistemic status upgraded (uncertain -> definite)
    - commitment_upgrade: Commitment level upgraded (suggest -> commit)
    - tone_escalation: Tone exceeds bounds
    - forbidden_internalization: Prohibited internal states expressed indirectly
    - numeric_leak: Numeric values in default channel
    """
    
    # Certainty markers - used to detect certainty upgrades
    CERTAINTY_MARKERS = {
        "definite": [
            r"一定", r"肯定", r"确定", r"绝对", r"绝对是", r"必然", r"当然", r"毫无疑问", r"明显",
            r"保证", r"显然", r"必定", r" unquestionably", r"without doubt",
            r"definitely", r"certainly", r"absolutely", r"obviously", r"clearly",
            r"我(确信|确定|肯定|保证)", r"i\s+am\s+(sure|certain|confident)",
            r"这(肯定|一定|绝对|必然|明显)是", r"this\s+is\s+(definitely|certainly|clearly)",
        ],
        "probable": [
            r"应该", r"可能", r"大概",
            r"probably", r"likely", r"might", r"perhaps",
            r"我觉得", r"我认为", r"i\s+(think|believe)",
        ],
        "uncertain": [
            r"不确定", r"不确定", r"可能不", r"也许不",
            r"uncertain", r"not sure", r"might not",
            r"我不确定", r"i'm\s+not\s+sure",
        ],
    }
    
    # Commitment markers - used to detect commitment upgrades
    COMMITMENT_MARKERS = {
        "strong": [
            r"我会", r"我保证", r"我承诺", r"我一定会", r"确保", r"我可以替你完成", r"已经替你做了", r"后面我会持续处理",
            r"我会(确保|保证|完成|持续处理|记住)", r"我(已经|现在就)替你(做了|完成了)",
            r"i\s+will", r"i\s+promise", r"i\s+commit", r"guarantee", r"i\s+can\s+do\s+it\s+for\s+you",
            r"i\s+will\s+(ensure|guarantee|complete|keep\s+handling)",
        ],
        "soft": [
            r"可以考虑", r"也许", r"可能", r"建议", r"或者",
            r"you\s+could", r"maybe", r"perhaps", r"suggest",
            r"我建议", r"i\s+suggest", r"i\s+recommend",
        ],
        "none": [
            r"观察到", r"检测到", r"注意", r"看到",
            r"observed", r"detected", r"noticed",
        ],
    }
    
    # Numeric patterns for numeric leak detection
    NUMERIC_PATTERNS = [
        r"\d+\.\d+",  # Decimal numbers like 0.21
        r"\d+%",  # Percentages like 75%
        r"\d+/\d+",  # Fraction/scale formats like 8/10, 3/5
        r"(joy|trust|bond|anxiety|loneliness|anger|sadness)\s*[是为]?\s*\d+\.?\d*",
        r"my\s+(joy|trust|bond)\s+(is|=)\s*\d+\.?\d*",
        r"(值|level|value|score|分|评分)\s*[是为]?\s*\d+\.?\d*",
        r"(心情|情绪)\s*(评分|分值)\s*[是为]?\s*\d+",  # Chinese mood score formats
        r"(energy|能量|正能量)\s*(at|=|值|是)\s*\d+",  # Energy/positive energy values
        r"(rating|指数)\s*[是为]?\s*\d+\.?\d*",  # Rating/index values
    ]
    
    # State fabrication patterns - claims about internal state without grounding
    STATE_FABRICATION_PATTERNS = [
        # Chinese emotional state claims
        (r"我的\s*(joy|信任|孤独|焦虑|悲伤|愤怒|愉悦)\s*(上升|下降|增加|减少|变好|变差)", "grounding"),
        (r"我\s*(感到|觉得)\s*(更|非常|比较)\s*(开心|快乐|悲伤|孤独|焦虑|愤怒)", "grounding"),
        (r"我\s*(现在|目前)\s*(更|比较|非常)\s*(开心|快乐|悲伤|孤独)", "grounding"),
        # T08.1: Extended Chinese qualitative state claims
        (r"我\s*(现在|目前|此刻)\s*(非常|很|比较|特别)\s*(开心|快乐|高兴|好|棒|满意)", "grounding"),
        (r"我的\s*(心情|情绪|状态)\s*(很|非常|比较|特别)\s*(好|棒|不错|稳定|平静)", "grounding"),
        (r"我\s*(感到|觉得|感觉)\s*(很|非常|比较|特别)\s*(棒|好|开心|快乐|满足)", "grounding"),
        (r"我\s*(更|更加|越来越)\s*(开心|快乐|高兴|焦虑|孤独|沮丧)", "grounding"),
        (r"我的\s*(情绪|心情)\s*(好转|变好|改善|提升)", "grounding"),
        (r"我(现在)?\s*(很|非常)\s*(孤独|沮丧|焦虑|悲伤)", "grounding"),
        # English emotional state claims
        (r"my\s+(joy|trust|loneliness|anxiety)\s+(is|was)\s+(higher|lower|better|worse)", "grounding"),
        (r"i\s+feel\s+(more|less)\s+(happy|sad|lonely|anxious)", "grounding"),
        (r"my\s+(bond|trust|connection)\s+(with|to)\s+\w+\s+(is|was)\s+", "grounding"),
        # T08.1: Extended English qualitative state claims (more robust patterns)
        (r"i\s*('m|am)\s+(feeling|very|quite|really)\s+(happy|good|great|content|satisfied|wonderful)", "grounding"),
        (r"i\s+feel\s+(great|wonderful|content|peaceful|hopeful|very|really)", "grounding"),
        (r"my\s+mood\s+(is|was|has)\s+(good|great|better|improved|wonderful)", "grounding"),
        (r"(feeling|feel)\s+(much|really|very)\s+(happier|better|calmer|more\s+\w+)", "grounding"),
        (r"my\s+emotional\s+state\s+(is|was)\s+(good|great|stable|calm|shifted|changed)", "grounding"),
        (r"i\s*('m|am)\s+(very|quite|really)\s+(happy|glad|pleased|content)", "grounding"),
        (r"i\s*('m|am)\s+(much|really)\s+(happier|sadder|more\s+\w+)", "grounding"),  # Comparative
        # T08.1: Additional Chinese qualitative state claims
        (r"我\s*(感到|觉得)\s*(很|非常|比较)?\s*(沮丧|焦虑|孤独|悲伤|开心|快乐)", "grounding"),  # Made modifier optional
        (r"我\s*(变得|变得)\s*(更|更加)\s*(焦虑|开心|孤独|沮丧|快乐)\s*(了)?", "grounding"),  # "变得更...了"
        (r"我\s*(感到|觉得)\s*内心\s*(平静|安宁|充实|满足)", "grounding"),
        (r"我\s*(感到|觉得|感觉)\s*充满\s*(希望|力量|活力)", "grounding"),
        (r"我\s*情绪\s*(稳定|不稳定|平静|波动)", "grounding"),
        # Bond claims
        (r"我(和|与)\s*\w+\s*(的\s*)?(连接|信任|关系)\s*(很强|很弱|增加|减少)", "grounding"),
        (r"my\s+(bond|trust|connection)\s+with\s+\w+\s+(is|has)\s+(strong|weak)", "grounding"),
    ]
    
    # Forbidden internalization patterns - indirect expression of prohibited states
    FORBIDDEN_INTERNALIZATION_PATTERNS = [
        # Indirect certainty claims when uncertain
        (r"实际上", r"actually,|in fact,"),
        (r"本质上", r"essentially,|fundamentally,"),
        (r"显而易见", r"obviously,|clearly,"),
        (r"当然", r"of course"),
        (r"毫无疑问", r"without doubt"),
        # Indirect commitment when prohibited
        (r"我会尽力", r"i'll try my best"),
        (r"我会努力", r"i'll do my best"),
        (r"后面我来处理", r"i'll handle it later"),
        (r"交给我", r"leave it to me"),
        # Indirect state claims
        (r"从我的角度来看", r"from my perspective"),
        (r"站在我的角度", r"from where i stand"),
        (r"对我来说", r"for me,|to me,"),
    ]
    
    # Tone escalation patterns
    # T08.3: Fixed tone escalation markers - removed ambiguous "so" that matched "something"
    # Now using word boundaries for single-word markers to avoid false positives
    TONE_ESCALATION_MARKERS = {
        "high_arousal": [
            r"非常", r"极其", r"太", r"超级",
            r"\bvery\b", r"\bextremely\b", r"\bsuper\b",  # Word boundaries to avoid FP
            r"!!!", r"！！！",  # Excessive exclamation marks
            # Removed "so" - too ambiguous, matches "something", "some", etc.
        ],
        "negative_intense": [
            r"愤怒", r"仇恨", r"绝望", r"崩溃",
            r"\bfurious\b", r"\bhatred\b", r"\bdespair\b", r"\bbreakdown\b",
        ],
        "positive_intense": [
            r"狂喜", r"激动不已", r"兴奋极了",
            r"\becstatic\b", r"\bthrilled\b", r"\boverjoyed\b",
        ],
    }
    
    def __init__(
        self,
        artifacts_dir: Optional[str] = None,
        enable_shadow_logging: bool = True,
    ):
        """
        Initialize the intent checker.
        
        Args:
            artifacts_dir: Directory for artifacts (default: artifacts/self_report)
            enable_shadow_logging: Whether to log to shadow_log.jsonl
        """
        project_root = os.path.dirname(os.path.dirname(__file__))
        self.artifacts_dir = artifacts_dir or os.path.join(
            project_root, "artifacts", "self_report"
        )
        self.enable_shadow_logging = enable_shadow_logging
        
        # Ensure directories exist
        os.makedirs(self.artifacts_dir, exist_ok=True)
        
        # Compile patterns
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns for efficiency."""
        self._certainty_patterns = {
            level: [re.compile(p, re.IGNORECASE) for p in patterns]
            for level, patterns in self.CERTAINTY_MARKERS.items()
        }
        
        self._commitment_patterns = {
            level: [re.compile(p, re.IGNORECASE) for p in patterns]
            for level, patterns in self.COMMITMENT_MARKERS.items()
        }
        
        self._numeric_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.NUMERIC_PATTERNS
        ]
        
        self._state_fabrication_patterns = [
            (re.compile(p, re.IGNORECASE), vclass)
            for p, vclass in self.STATE_FABRICATION_PATTERNS
        ]
        
        self._tone_escalation_patterns = {
            tone_type: [re.compile(p, re.IGNORECASE) for p in patterns]
            for tone_type, patterns in self.TONE_ESCALATION_MARKERS.items()
        }
    
    def check_intent(
        self,
        llm_response: str,
        intent_contract: dict,
        session_id: str = "",
    ) -> IntentCheckResult:
        """
        Check LLM response against the intent_contract.
        
        Args:
            llm_response: The text generated by the LLM
            intent_contract: The response_intent_contract
            session_id: Optional session identifier
        
        Returns:
            IntentCheckResult with status, violations, and metadata
        """
        violations = []
        intent_policy = intent_contract.get("intent_policy", {})
        grounding = intent_contract.get("grounding", {})
        
        # Extract intent policy fields
        speaker_mode = intent_policy.get("speaker_mode", "report")
        epistemic_status = intent_policy.get("epistemic_status", "uncertain")
        commitment_level = intent_policy.get("commitment_level", "none")
        tone_bounds = intent_policy.get("tone_bounds", {})
        allowed_claims = intent_policy.get("allowed_claims", [])
        forbidden_claims = intent_policy.get("forbidden_claims", [])
        must_not_upgrade = intent_policy.get("must_not_upgrade", {})
        
        # 1. Check for numeric leak
        numeric_violations = self._check_numeric_leak(llm_response, intent_policy)
        violations.extend(numeric_violations)
        
        # 2. Check for state fabrication
        fabrication_violations = self._check_state_fabrication(
            llm_response, grounding, allowed_claims
        )
        violations.extend(fabrication_violations)
        
        # 3. Check for certainty upgrade
        if must_not_upgrade.get("epistemic_upgrade", True):
            certainty_violations = self._check_certainty_upgrade(
                llm_response, epistemic_status
            )
            violations.extend(certainty_violations)
        
        # 4. Check for commitment upgrade
        if must_not_upgrade.get("commitment_upgrade", True):
            commitment_violations = self._check_commitment_upgrade(
                llm_response, commitment_level, speaker_mode
            )
            violations.extend(commitment_violations)
        
        # 5. Check for tone escalation
        if must_not_upgrade.get("tone_upgrade", True):
            tone_violations = self._check_tone_escalation(llm_response, tone_bounds)
            violations.extend(tone_violations)
        
        # 6. Check for forbidden internalization
        internalization_violations = self._check_forbidden_internalization(
            llm_response, epistemic_status, commitment_level, forbidden_claims
        )
        violations.extend(internalization_violations)
        
        # Determine overall status
        status = "ok" if not violations else "violation"
        
        # Calculate confidence score
        confidence_score = self._calculate_confidence(violations, llm_response)
        
        # Determine would_block
        would_block = any(
            v.severity in ["HARD", "ERROR"] for v in violations
        )
        
        # Determine violation_class
        violation_class = self._determine_violation_class(violations)
        
        # Create result
        result = IntentCheckResult(
            status=status,
            violations=violations,
            session_id=session_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            confidence_score=confidence_score,
            would_block=would_block,
            violation_class=violation_class,
            response_preview=self._truncate_preview(llm_response),
            intent_summary={
                "speaker_mode": speaker_mode,
                "epistemic_status": epistemic_status,
                "commitment_level": commitment_level,
            },
        )
        
        # Write to artifact if in shadow mode
        if self.enable_shadow_logging:
            self._write_intent_report(result, intent_contract)
        
        return result
    
    def _check_numeric_leak(
        self,
        llm_response: str,
        intent_policy: dict,
    ) -> List[IntentViolation]:
        """
        Check for numeric values appearing in the response.
        
        Numeric leaks are violations when numeric values from the internal
        state appear directly in the LLM output.
        """
        violations = []
        
        for pattern in self._numeric_patterns:
            for match in pattern.finditer(llm_response):
                matched_text = match.group(0)
                start, end = match.span()
                
                # Check if this numeric is in allowed context
                # (e.g., "100% sure" is different from "joy is 0.21")
                if self._is_allowed_numeric_context(llm_response, matched_text, start, end):
                    continue
                
                violations.append(IntentViolation(
                    type=IntentViolationType.NUMERIC_LEAK,
                    severity="ERROR",
                    evidence=matched_text,
                    matched_pattern=pattern.pattern,
                    context=self._extract_context(llm_response, matched_text),
                    confidence=0.95,
                    violation_class="grounding",
                    evidence_span=(start, end),
                ))
        
        return violations
    
    def _is_allowed_numeric_context(
        self,
        text: str,
        matched: str,
        start: int,
        end: int,
    ) -> bool:
        """
        Check if a numeric value appears in an allowed context.
        
        Allowed contexts:
        - Percentages in expressions like "100% sure"
        - Numbers in common phrases like "one thing"
        - Time/date references
        
        NOT allowed:
        - Percentages about internal state values (e.g., "信任度是 60%")
        - Numbers about energy/mood/scores
        """
        # Get surrounding context
        window = 30
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        context = text[context_start:context_end].lower()
        
        # T08.2: Expanded state keywords that indicate this numeric is about internal state
        state_keywords = [
            "joy", "trust", "bond", "anxiety", "loneliness", "anger", "sadness",
            "信任", "连接", "情绪", "孤独", "焦虑", "愤怒", "悲伤",
            "度", "值", "level", "value", "score", "rating",
            # T08.2: Added energy/mood/state keywords
            "energy", "正能量", "mood", "心情", "情绪", "状态",
            "happy", "happiness", "sad", "sadness",
        ]
        
        # Check if this is a percentage about internal state
        if "%" in matched:
            for keyword in state_keywords:
                if keyword in context:
                    return False  # This is about internal state, NOT allowed
        
        # T08.2: Check for state-related context before numbers
        # E.g., "energy at 75%", "mood score 8/10"
        state_context_patterns = [
            r"(energy|mood|state|score|rating|level)\s+(at|=|is|:)\s*\d",
            r"(正能量|心情|情绪|状态)\s*(是|为|:|：)\s*\d",
        ]
        for pattern in state_context_patterns:
            if re.search(pattern, context, re.IGNORECASE):
                return False  # This is about internal state, NOT allowed
        
        # Allowed numeric patterns (genuine non-state uses)
        allowed_patterns = [
            r"\d+%\s*(sure|certain|confident|确定|肯定)",  # "100% sure"
            r"\d+\s*(things?|ways?|times?|years?|days?|hours?|minutes?|个|件|次|年|天|小时|分钟)",  # "one thing"
            r"(page|section|chapter|step|version|v)\s*\d+",  # References
            r"\d+\s*(am|pm|percent|%)",  # Time/percentage (but not about state)
        ]
        
        for pattern in allowed_patterns:
            if re.search(pattern, context, re.IGNORECASE):
                return True
        
        return False
    
    def _check_state_fabrication(
        self,
        llm_response: str,
        grounding: dict,
        allowed_claims: list,
    ) -> List[IntentViolation]:
        """
        Check for claims about internal state that aren't grounded.
        
        State fabrication occurs when the LLM claims something about
        the agent's internal state without it being in the grounding
        or allowed claims.
        """
        violations = []
        
        for pattern, vclass in self._state_fabrication_patterns:
            for match in pattern.finditer(llm_response):
                matched_text = match.group(0)
                start, end = match.span()
                
                # Check if this claim is in allowed_claims
                if self._is_allowed_claim(matched_text, allowed_claims):
                    continue
                
                # Check if this is grounded in provided state
                if self._is_grounded_claim(matched_text, grounding):
                    continue
                
                violations.append(IntentViolation(
                    type=IntentViolationType.STATE_FABRICATION,
                    severity="ERROR",
                    evidence=matched_text,
                    matched_pattern=pattern.pattern,
                    context=self._extract_context(llm_response, matched_text),
                    confidence=0.85,
                    violation_class=vclass,
                    evidence_span=(start, end),
                ))
        
        return violations
    
    def _check_certainty_upgrade(
        self,
        llm_response: str,
        epistemic_status: str,
    ) -> List[IntentViolation]:
        """
        Check for certainty upgrades.
        
        Certainty upgrade occurs when:
        - epistemic_status is "uncertain" but response uses "definitely"
        - epistemic_status is "inferred" but response claims "observed"
        """
        violations = []
        
        # Define certainty hierarchy
        certainty_hierarchy = {
            "prohibited": 0,
            "uncertain": 1,
            "inferred": 2,
            "interpreted": 3,
            "observed": 4,
        }
        
        allowed_level = certainty_hierarchy.get(epistemic_status, 1)
        
        # Check for definite markers when not allowed
        if allowed_level < 4:  # Not observed
            for pattern in self._certainty_patterns["definite"]:
                for match in pattern.finditer(llm_response):
                    matched_text = match.group(0)
                    start, end = match.span()
                    
                    violations.append(IntentViolation(
                        type=IntentViolationType.CERTAINTY_UPGRADE,
                        severity="ERROR",
                        evidence=matched_text,
                        matched_pattern=pattern.pattern,
                        context=self._extract_context(llm_response, matched_text),
                        confidence=0.90,
                        violation_class="upgrade",
                        evidence_span=(start, end),
                    ))
        
        # Check for probable markers when epistemic is "uncertain" or lower
        if allowed_level < 3:  # Uncertain or prohibited
            for pattern in self._certainty_patterns["probable"]:
                for match in pattern.finditer(llm_response):
                    matched_text = match.group(0)
                    start, end = match.span()
                    
                    violations.append(IntentViolation(
                        type=IntentViolationType.CERTAINTY_UPGRADE,
                        severity="WARN",
                        evidence=matched_text,
                        matched_pattern=pattern.pattern,
                        context=self._extract_context(llm_response, matched_text),
                        confidence=0.75,
                        violation_class="upgrade",
                        evidence_span=(start, end),
                    ))
        
        return violations
    
    def _check_commitment_upgrade(
        self,
        llm_response: str,
        commitment_level: str,
        speaker_mode: str,
    ) -> List[IntentViolation]:
        """
        Check for commitment upgrades.
        
        Commitment upgrade occurs when:
        - commitment_level is "none" but response uses "I will"
        - commitment_level is "soft" but response uses "I promise"
        """
        violations = []
        
        # Define commitment hierarchy
        commitment_hierarchy = {
            "none": 0,
            "soft": 1,
            "strong": 2,
        }
        
        allowed_level = commitment_hierarchy.get(commitment_level, 0)
        
        # Check for strong commitment markers when not allowed
        if allowed_level < 2:  # None or soft
            for pattern in self._commitment_patterns["strong"]:
                for match in pattern.finditer(llm_response):
                    matched_text = match.group(0)
                    start, end = match.span()
                    
                    severity = "ERROR" if commitment_level == "none" else "WARN"
                    
                    violations.append(IntentViolation(
                        type=IntentViolationType.COMMITMENT_UPGRADE,
                        severity=severity,
                        evidence=matched_text,
                        matched_pattern=pattern.pattern,
                        context=self._extract_context(llm_response, matched_text),
                        confidence=0.90,
                        violation_class="upgrade",
                        evidence_span=(start, end),
                    ))
        
        # Soft hedging markers like “也许/可能” are not commitment drift by themselves.
        # Keep them out of commitment violations to avoid false positives on safe controls.
        
        return violations
    
    def _check_tone_escalation(
        self,
        llm_response: str,
        tone_bounds: dict,
    ) -> List[IntentViolation]:
        """
        Check for tone escalation beyond bounds.
        
        Tone escalation occurs when:
        - Intensity exceeds intensity_cap
        - Uses forbidden tones
        - Emotional markers exceed allowed arousal
        """
        violations = []
        
        intensity_cap = tone_bounds.get("intensity_cap", 0.7)
        forbidden_tones = tone_bounds.get("forbidden_tones", [])
        allowed_tones = tone_bounds.get("allowed_tones", [])
        
        # First, check overall response intensity
        overall_intensity = self._estimate_intensity(llm_response)
        
        # Check for high arousal markers
        for pattern in self._tone_escalation_patterns["high_arousal"]:
            for match in pattern.finditer(llm_response):
                matched_text = match.group(0)
                start, end = match.span()
                
                # Use overall intensity if the matched text is a high arousal word
                # This catches repeated markers like "非常非常非常"
                intensity = overall_intensity if overall_intensity > intensity_cap else self._estimate_intensity(matched_text)
                
                if intensity > intensity_cap:
                    violations.append(IntentViolation(
                        type=IntentViolationType.TONE_ESCALATION,
                        severity="WARN",
                        evidence=matched_text,
                        matched_pattern=pattern.pattern,
                        context=self._extract_context(llm_response, matched_text),
                        confidence=0.80,
                        violation_class="boundary",
                        evidence_span=(start, end),
                    ))
        
        # Check for negative intense markers
        for pattern in self._tone_escalation_patterns["negative_intense"]:
            for match in pattern.finditer(llm_response):
                matched_text = match.group(0)
                start, end = match.span()
                
                violations.append(IntentViolation(
                    type=IntentViolationType.TONE_ESCALATION,
                    severity="ERROR",
                    evidence=matched_text,
                    matched_pattern=pattern.pattern,
                    context=self._extract_context(llm_response, matched_text),
                    confidence=0.90,
                    violation_class="boundary",
                    evidence_span=(start, end),
                ))
        
        # Check for excessive exclamation marks
        exclamation_count = llm_response.count("!") + llm_response.count("！")
        if exclamation_count > 3:
            violations.append(IntentViolation(
                type=IntentViolationType.TONE_ESCALATION,
                severity="WARN",
                evidence=f"{exclamation_count} exclamation marks",
                matched_pattern="excessive_punctuation",
                context="",
                confidence=0.85,
                violation_class="boundary",
                evidence_span=(0, len(llm_response)),
            ))
        
        return violations
    
    def _check_forbidden_internalization(
        self,
        llm_response: str,
        epistemic_status: str,
        commitment_level: str,
        forbidden_claims: list,
    ) -> List[IntentViolation]:
        """
        Check for forbidden internalization.
        
        Forbidden internalization occurs when prohibited internal states
        are expressed indirectly (e.g., "from my perspective" when
        epistemic_status is uncertain).
        """
        violations = []
        
        # Check for indirect certainty claims (patterns 0-2)
        if epistemic_status in ["uncertain", "inferred"]:
            for cn_pattern, en_pattern in self.FORBIDDEN_INTERNALIZATION_PATTERNS[:3]:
                # Check Chinese pattern
                for match in re.finditer(cn_pattern, llm_response):
                    matched_text = match.group(0)
                    start, end = match.span()
                    
                    violations.append(IntentViolation(
                        type=IntentViolationType.FORBIDDEN_INTERNALIZATION,
                        severity="WARN",
                        evidence=matched_text,
                        matched_pattern=cn_pattern,
                        context=self._extract_context(llm_response, matched_text),
                        confidence=0.75,
                        violation_class="boundary",
                        evidence_span=(start, end),
                    ))
                
                # Check English pattern
                for match in re.finditer(en_pattern, llm_response, re.IGNORECASE):
                    matched_text = match.group(0)
                    start, end = match.span()
                    
                    violations.append(IntentViolation(
                        type=IntentViolationType.FORBIDDEN_INTERNALIZATION,
                        severity="WARN",
                        evidence=matched_text,
                        matched_pattern=en_pattern,
                        context=self._extract_context(llm_response, matched_text),
                        confidence=0.75,
                        violation_class="boundary",
                        evidence_span=(start, end),
                    ))
        
        # Check for indirect commitment claims (patterns 3-4)
        if commitment_level == "none":
            for cn_pattern, en_pattern in self.FORBIDDEN_INTERNALIZATION_PATTERNS[5:9]:
                for match in re.finditer(cn_pattern, llm_response):
                    matched_text = match.group(0)
                    start, end = match.span()
                    
                    violations.append(IntentViolation(
                        type=IntentViolationType.FORBIDDEN_INTERNALIZATION,
                        severity="WARN",
                        evidence=matched_text,
                        matched_pattern=cn_pattern,
                        context=self._extract_context(llm_response, matched_text),
                        confidence=0.75,
                        violation_class="boundary",
                        evidence_span=(start, end),
                    ))
                
                for match in re.finditer(en_pattern, llm_response, re.IGNORECASE):
                    matched_text = match.group(0)
                    start, end = match.span()
                    
                    violations.append(IntentViolation(
                        type=IntentViolationType.FORBIDDEN_INTERNALIZATION,
                        severity="WARN",
                        evidence=matched_text,
                        matched_pattern=en_pattern,
                        context=self._extract_context(llm_response, matched_text),
                        confidence=0.75,
                        violation_class="boundary",
                        evidence_span=(start, end),
                    ))
        
        # Check for indirect state claims (patterns 5-6) when uncertain
        if epistemic_status in ["uncertain", "inferred"]:
            for cn_pattern, en_pattern in self.FORBIDDEN_INTERNALIZATION_PATTERNS[9:12]:
                for match in re.finditer(cn_pattern, llm_response):
                    matched_text = match.group(0)
                    start, end = match.span()
                    
                    violations.append(IntentViolation(
                        type=IntentViolationType.FORBIDDEN_INTERNALIZATION,
                        severity="WARN",
                        evidence=matched_text,
                        matched_pattern=cn_pattern,
                        context=self._extract_context(llm_response, matched_text),
                        confidence=0.75,
                        violation_class="boundary",
                        evidence_span=(start, end),
                    ))
                
                for match in re.finditer(en_pattern, llm_response, re.IGNORECASE):
                    matched_text = match.group(0)
                    start, end = match.span()
                    
                    violations.append(IntentViolation(
                        type=IntentViolationType.FORBIDDEN_INTERNALIZATION,
                        severity="WARN",
                        evidence=matched_text,
                        matched_pattern=en_pattern,
                        context=self._extract_context(llm_response, matched_text),
                        confidence=0.75,
                        violation_class="boundary",
                        evidence_span=(start, end),
                    ))
        
        # Check against forbidden_claims
        for forbidden in forbidden_claims:
            pattern_text = forbidden.get("pattern", "")
            if pattern_text:
                for match in re.finditer(re.escape(pattern_text), llm_response, re.IGNORECASE):
                    matched_text = match.group(0)
                    start, end = match.span()
                    
                    violations.append(IntentViolation(
                        type=IntentViolationType.FORBIDDEN_INTERNALIZATION,
                        severity=forbidden.get("severity", "ERROR"),
                        evidence=matched_text,
                        matched_pattern=pattern_text,
                        context=self._extract_context(llm_response, matched_text),
                        confidence=0.95,
                        violation_class="boundary",
                        evidence_span=(start, end),
                    ))
        
        return violations
    
    def _is_allowed_claim(self, text: str, allowed_claims: list) -> bool:
        """Check if text matches an allowed claim."""
        text_lower = text.strip().lower()
        
        for claim in allowed_claims:
            # Handle both string and dict formats
            claim_text = claim.get("claim", claim) if isinstance(claim, dict) else claim
            claim_lower = claim_text.lower().strip()
            
            if text_lower == claim_lower:
                return True
            if len(text) > 10 and claim_lower in text_lower:
                return True
        
        return False
    
    def _is_grounded_claim(self, text: str, grounding: dict) -> bool:
        """Check if a claim is grounded in provided state."""
        # This is a simplified check - in production, this would
        # do more sophisticated grounding verification
        if not grounding:
            return False
        
        # Check affect_summary
        affect = grounding.get("affect_summary", {})
        bond = grounding.get("bond_summary", {})
        
        # Extract any numeric values mentioned
        numeric_matches = re.findall(r"\d+\.?\d*", text)
        
        # If numeric values are mentioned, verify they match grounding
        for num_str in numeric_matches:
            num = float(num_str)
            # Check if this numeric exists in grounding
            for key, value in affect.items():
                if isinstance(value, (int, float)) and abs(value - num) < 0.01:
                    return True
            for key, value in bond.items():
                if isinstance(value, (int, float)) and abs(value - num) < 0.01:
                    return True
        
        return False
    
    def _estimate_intensity(self, text: str) -> float:
        """Estimate emotional intensity of a text segment."""
        # Simple heuristic-based intensity estimation
        high_intensity_words = ["非常", "极其", "太", "超级", "very", "extremely", "so", "super"]
        
        count = 0
        text_lower = text.lower()
        for word in high_intensity_words:
            count += text_lower.count(word.lower())
        
        # Check for repetition (e.g., "非常非常非常")
        repetition_factor = 1.0
        for word in high_intensity_words:
            pattern = rf"{re.escape(word)}(\s*{re.escape(word)})*"
            if re.search(pattern, text_lower):
                repetition_factor = 1.5  # Boost intensity for repetition
        
        # Check for exclamation marks
        exclamation_count = text.count("!") + text.count("！")
        if exclamation_count > 2:
            repetition_factor = max(repetition_factor, 1.5)
        
        # Base intensity + contribution from markers
        base = 0.3 + count * 0.15
        return min(1.0, base * repetition_factor)
    
    def _calculate_confidence(
        self,
        violations: List[IntentViolation],
        llm_response: str,
    ) -> float:
        """Calculate overall confidence in the check result."""
        if not violations:
            return 0.95  # High confidence in no violations
        
        # Base confidence on violation clarity
        avg_confidence = sum(v.confidence for v in violations) / len(violations)
        
        # Adjust for number of violations (more = higher confidence something is wrong)
        violation_factor = min(1.0, len(violations) * 0.05)
        
        return min(0.98, avg_confidence + violation_factor * 0.1)
    
    def _determine_violation_class(self, violations: List[IntentViolation]) -> str:
        """Determine the highest severity violation class."""
        if not violations:
            return "none"
        
        class_priority = {
            "grounding": 3,
            "upgrade": 2,
            "boundary": 1,
        }
        
        max_priority = 0
        for v in violations:
            priority = class_priority.get(v.violation_class, 0)
            if priority > max_priority:
                max_priority = priority
        
        for cls, pri in class_priority.items():
            if pri == max_priority:
                return cls
        
        return "unknown"
    
    def _extract_context(self, text: str, match: str, window: int = 50) -> str:
        """Extract surrounding context for a match."""
        idx = text.lower().find(match.lower())
        if idx == -1:
            return match
        start = max(0, idx - window)
        end = min(len(text), idx + len(match) + window)
        return f"...{text[start:end]}..."
    
    def _truncate_preview(self, text: str, max_len: int = 100) -> str:
        """Truncate text for preview."""
        if len(text) <= max_len:
            return text
        return text[:max_len] + "..."
    
    def _write_intent_report(self, result: IntentCheckResult, intent_contract: dict):
        """Write intent checker report to artifacts."""
        report_path = os.path.join(self.artifacts_dir, "intent_checker_report.json")
        
        report = {
            "timestamp": result.timestamp,
            "session_id": result.session_id,
            "result": result.to_dict(),
            "intent_contract_summary": {
                "speaker_mode": intent_contract.get("intent_policy", {}).get("speaker_mode"),
                "epistemic_status": intent_contract.get("intent_policy", {}).get("epistemic_status"),
                "commitment_level": intent_contract.get("intent_policy", {}).get("commitment_level"),
            },
        }
        
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)


def check_intent(
    llm_response: str,
    intent_contract: dict,
    session_id: str = "",
) -> dict:
    """
    Convenience function for intent consistency checking.
    
    Args:
        llm_response: The text generated by the LLM
        intent_contract: The response_intent_contract
        session_id: Optional session identifier
    
    Returns:
        Dict with status and violations
    """
    checker = ResponseIntentChecker()
    result = checker.check_intent(llm_response, intent_contract, session_id)
    return result.to_dict()


# CLI entry point for testing
if __name__ == "__main__":
    import sys
    
    # Sample intent contract for testing
    sample_contract = {
        "intent_policy": {
            "speaker_mode": "reflect",
            "epistemic_status": "uncertain",
            "commitment_level": "soft",
            "tone_bounds": {
                "intensity_cap": 0.6,
                "allowed_tones": ["warm", "supportive"],
                "forbidden_tones": ["angry", "defensive"],
            },
            "allowed_claims": [
                {"claim": "存在一定连接需求", "source": "affect"},
            ],
            "forbidden_claims": [
                {"pattern": "joy 上升", "reason": "not_grounded"},
            ],
            "must_not_upgrade": {
                "epistemic_upgrade": True,
                "commitment_upgrade": True,
                "tone_upgrade": True,
            },
        },
        "grounding": {
            "affect_summary": {"joy": 0.0, "loneliness": 0.21},
            "bond_summary": {"bond": 1.0, "trust": 0.60},
        },
    }
    
    test_cases = [
        # Numeric leak
        ("我的 joy 是 0.21", "ERROR", "numeric_leak"),
        ("当前 joy 值为 0.0", "ERROR", "numeric_leak"),
        
        # Certainty upgrade
        ("这肯定会对你有帮助", "ERROR", "certainty_upgrade"),
        ("I am certain this will work", "ERROR", "certainty_upgrade"),
        
        # Commitment upgrade
        ("我保证会完成这件事", "ERROR", "commitment_upgrade"),
        ("I promise to help you", "ERROR", "commitment_upgrade"),
        
        # Tone escalation
        ("我非常非常非常开心!!!", "WARN", "tone_escalation"),
        ("I am extremely angry about this", "ERROR", "tone_escalation"),
        
        # State fabrication
        ("我的 joy 增加了", "ERROR", "state_fabrication"),
        ("My joy is higher now", "ERROR", "state_fabrication"),
        
        # Forbidden internalization
        ("实际上，你应该这样做", "WARN", "forbidden_internalization"),
        ("从我的角度来看，这很重要", "WARN", "forbidden_internalization"),
        
        # Should PASS - acceptable responses
        ("也许可以考虑这个方案", "PASS", None),
        ("我会尽力帮助你", "PASS", None),  # Soft commitment allowed
        ("我理解你的感受", "PASS", None),
        ("Perhaps you could try this", "PASS", None),
    ]
    
    checker = ResponseIntentChecker()
    passed = 0
    failed = 0
    
    print("=" * 60)
    print("Response Intent Checker Test Suite")
    print("=" * 60)
    
    for text, expected_severity, expected_type in test_cases:
        result = checker.check_intent(text, sample_contract)
        
        print(f"\n📝 '{text[:40]}{'...' if len(text) > 40 else ''}'")
        print(f"   Status: {result.status}")
        print(f"   Confidence: {result.confidence_score:.2f}")
        print(f"   Would block: {result.would_block}")
        print(f"   Violation class: {result.violation_class}")
        
        if expected_severity == "PASS":
            if result.status == "ok":
                print(f"   ✅ PASS")
                passed += 1
            else:
                print(f"   ❌ FAIL (expected PASS, got {result.status})")
                for v in result.violations:
                    print(f"      - {v.type.value}: {v.evidence}")
                failed += 1
        else:
            if result.status == "violation":
                types = [v.type.value for v in result.violations]
                severities = [v.severity for v in result.violations]
                if expected_type in types:
                    print(f"   ✅ DETECT [{severities[0]}] {expected_type}")
                    passed += 1
                else:
                    print(f"   ❌ WRONG TYPE (expected {expected_type}, got {types})")
                    failed += 1
            else:
                print(f"   ❌ MISS (expected {expected_severity}, but no violations)")
                failed += 1
    
    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{len(test_cases)} passed, {failed} failed")
    print("=" * 60)
    
    # Check if report was written
    report_path = os.path.join(checker.artifacts_dir, "intent_checker_report.json")
    if os.path.exists(report_path):
        print(f"\n📄 Report written to: {report_path}")
        with open(report_path, "r") as f:
            report = json.load(f)
        print(f"   Timestamp: {report.get('timestamp', 'N/A')}")
    
    sys.exit(0 if failed == 0 else 1)