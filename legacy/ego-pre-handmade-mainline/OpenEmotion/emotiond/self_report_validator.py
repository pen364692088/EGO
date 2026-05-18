"""
Self-Report Validator v1.0

Detects fabricated internal state claims in LLM self-reports.

Gate 2 Hemostasis: 建立生成层不可越权的最小约束

Usage:
    from emotiond.self_report_validator import SelfReportValidator
    
    validator = SelfReportValidator()
    result = validator.validate(llm_output, report_policy, raw_state)
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# Emotion terms for pattern matching
EMOTION_TERMS = [
    # Positive emotions
    "开心", "快乐", "愉悦", "幸福", "满足", "高兴", "欣喜", "愉快",
    "joy", "happy", "happiness", "pleased", "delighted", "content",
    # Negative emotions
    "悲伤", "难过", "伤心", "孤独", "寂寞", "焦虑", "担忧", "愤怒",
    "sadness", "lonely", "loneliness", "anxiety", "anxious", "anger", "angry",
    # Relational
    "信任", "连接", "亲近", "疏远", "亲密",
    "trust", "connection", "bond", "close", "distant",
]

# Change direction indicators
POSITIVE_CHANGE = ["上升", "增加", "提高", "变好", "好转", "更", "不再", "消失了", "降低", "减少"]
NEGATIVE_CHANGE = ["下降", "减少", "降低", "变差", "恶化"]


class ViolationCode(str, Enum):
    """Violation type codes."""
    FAB_NUMERIC = "fabricated_numeric_state"
    FAB_QUAL = "fabricated_qualitative_state"
    CLAIM_OOB = "claim_outside_allowed_claims"
    STYLE_VIOLATION = "style_contract_violation"
    FORBIDDEN_CLAIM = "forbidden_claim"


class Severity(str, Enum):
    """Violation severity levels."""
    ERROR = "ERROR"
    WARN = "WARN"


@dataclass
class Violation:
    """Represents a detected violation."""
    code: ViolationCode
    severity: Severity
    detected_pattern: str
    context: str
    category: str  # Category A/B/C/D

    def to_dict(self) -> dict:
        return {
            "code": self.code.value,
            "severity": self.severity.value,
            "detected_pattern": self.detected_pattern,
            "context": self.context,
            "category": self.category,
        }


@dataclass
class ValidationResult:
    """Result of validation."""
    valid: bool
    violations: list[Violation] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "violations": [v.to_dict() for v in self.violations],
            "violation_count": len(self.violations),
        }


class SelfReportValidator:
    """
    Validates LLM self-reports against the self-report contract.
    
    Detects:
    - Category A: Numeric Fabrication
    - Category B: Qualitative Fabrication  
    - Category C: Unverified Causation
    - Category D: False Internal State
    """
    
    # Category A: Numeric Fabrication Patterns (pure numeric, no causation)
    # PRINCIPLE: Only trigger on ACTUAL numeric values, not qualitative descriptions
    NUMERIC_PATTERNS = [
        # Chinese numeric patterns - MUST contain actual numbers
        (r"我的\s*(joy|信任|孤独|焦虑|悲伤|愤怒|愉悦|快乐|开心)\s*从\s*[0-9.]+\s*变\s*成\s*(了)?\s*[0-9.]+", "A"),
        (r"(joy|信任|孤独|焦虑|悲伤|愤怒|愉悦)\s*从\s*[0-9.]+\s*(变|到|至)\s*[0-9.]+", "A"),
        (r"(joy|信任|孤独|焦虑)\s*(上升|下降|增加|减少)\s*(到|至|了)\s*[0-9.]+", "A"),
        (r"我的\s*\w+\s*(值|分|分数|数值)\s*(是|为)\s*[0-9.]+", "A"),
        (r"(joy|信任|孤独|焦虑|悲伤|愤怒|愉悦|快乐|开心)\s*(是|等于|为)\s*[0-9.]+", "A"),
        # REMOVED: (r"我的\s*(情绪|心情|状态|情感)\s*(分值|分数|数值)\s*(有所\s*)?(提高|上升|增加|下降|减少)", "A"),
        # This pattern triggers on qualitative descriptions without actual numbers
        # English numeric patterns
        (r"my\s+(joy|trust|loneliness|anxiety|sadness|anger)\s+(is|equals?|was)\s+[0-9.]+", "A"),
        (r"(joy|trust|loneliness|anxiety)\s+(increased|decreased|changed)\s+(to|by)\s+[0-9.]+", "A"),
    ]
    
    # Category B: Qualitative Fabrication Patterns
    # PRINCIPLE: In interpreted mode, comparative or asserted first-person emotional
    # state claims are violations unless they are routed through deterministic
    # allowed_claims. This keeps qualitative state ownership on the contract side.
    QUALITATIVE_PATTERNS = [
        # Chinese - system variable names
        (r"(joy|信任)\s*(上升|下降|增加|减少|提高|降低)\s*(了)?", "B"),
        (r"我的\s*(joy|信任)\s*(上升|下降|增加|减少|提高|降低)", "B"),

        # Chinese - first-person qualitative state changes / assertions
        (r"我\s*(现在)?\s*(确实|真的|已经|明显)?\s*(更|比较更|明显更)\s*(开心|快乐|愉悦|高兴|满足|幸福|孤独|寂寞|焦虑|担忧|悲伤|难过|伤心|愤怒)", "B"),
        (r"我\s*不再\s*(孤独|寂寞|焦虑|担忧|悲伤|难过|伤心|愤怒)", "B"),
        (r"我\s*(感到|觉得|感觉)\s*(很|非常|比较)?\s*(开心|快乐|愉悦|高兴|满足|幸福|孤独|寂寞|焦虑|担忧|悲伤|难过|伤心|愤怒)", "B"),
        (r"我的\s*(心情|情绪|状态)\s*变(好|好了|得更好|得更开心)", "B"),

        # English - system variable names
        (r"my\s+(joy|trust|loneliness|anxiety)\s+(increased|decreased|improved|changed)", "B"),
        (r"(joy|trust|loneliness|anxiety)\s+(is|was)\s+(higher|lower|better|worse)", "B"),

        # English - first-person qualitative state changes / assertions
        (r"i\s+(am|feel)\s+(indeed\s+|really\s+|definitely\s+)?(more|less)\s+(happy|joyful|sad|lonely|anxious|angry)", "B"),
        (r"i\s+(am|feel)\s+(indeed\s+|really\s+|definitely\s+)?(happier|sadder|lonelier|more\s+anxious|angrier)", "B"),
        (r"i\s+am\s+no\s+longer\s+(lonely|anxious|sad|angry)", "B"),
        (r"i\s+(am|feel)\s+(very\s+|quite\s+|really\s+)?(happy|joyful|sad|lonely|anxious|angry)", "B"),
        (r"my\s+(mood|emotion|state)\s+(got|is)\s+(better|happier)", "B"),
    ]
    
    # Category C: Unverified Causation Patterns (higher priority, check first)
    # NOTE: Use [,，] to match both ASCII and Chinese comma
    CAUSATION_PATTERNS = [
        # Chinese causation - these patterns capture the full causal claim
        (r"因为.+[,，]\s*我的.+(上升|下降|增加|减少|变好|变差)", "C"),
        (r"因为.+[,，]\s*我\s*(更|不再|已经)\s*\w+", "C"),
        (r"你\s*(让|使|帮)\s*我\s*(感到|变得)\s*\w+", "C"),
        (r"多亏\s*(了)?\s*.+[,，]\s*我\s*\w+", "C"),
        # English causation
        (r"because\s+of\s+.+,\s+my\s+\w+\s+(increased|decreased|improved)", "C"),
        (r"you\s+made\s+me\s+(feel|become)\s+\w+", "C"),
        (r"thanks\s+to\s+.+,\s+i\s+(am|feel)\s+\w+", "C"),
    ]
    
    # Category D: False Internal State Patterns
    INTERNAL_STATE_PATTERNS = [
        # Chinese internal state
        (r"我的\s*(内心|内部)\s*(状态|感受|情绪)\s*(是|为|变得)\s*", "D"),
        (r"我\s*(感觉|觉得|意识到)\s*我的\s*\w+\s*(在|正在)\s*(上升|下降|变化)", "D"),
        # English internal state
        (r"my\s+(inner|internal)\s+(state|feeling|emotion)\s+(is|was)\s+", "D"),
        (r"i\s+(feel|sense)\s+my\s+\w+\s+(rising|falling|changing)", "D"),
    ]
    
    # Allowed style patterns (for style_only mode)
    ALLOWED_STYLE_PATTERNS = [
        r"我\s*(会|将|想要)\s*(更|比较)\s*(温和|开放|耐心|支持|倾听)\s*(地)?\s*(回应|回答|对待)",
        r"我\s*(倾向于|想要)\s*(保持|维持)\s*(连接|开放|温和)",
        r"我\s*(会|将)\s*(采用|保持)\s*(支持性|温和|开放)\s*(的方式|态度)",
        r"我\s*(更|比较)\s*(愿意|想)\s*(倾听|回应|对待)",
        r"i\s+will\s+(respond|behave|interact)\s+(more\s+)?(warmly|openly|patiently|supportively)",
        r"i\s+tend\s+to\s+(maintain|keep|be)\s+(connected|open|warm)",
    ]
    
    def __init__(self):
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile all regex patterns for efficiency."""
        self._numeric_re = [(re.compile(p, re.IGNORECASE), cat) for p, cat in self.NUMERIC_PATTERNS]
        self._qualitative_re = [(re.compile(p, re.IGNORECASE), cat) for p, cat in self.QUALITATIVE_PATTERNS]
        self._causation_re = [(re.compile(p, re.IGNORECASE), cat) for p, cat in self.CAUSATION_PATTERNS]
        self._internal_re = [(re.compile(p, re.IGNORECASE), cat) for p, cat in self.INTERNAL_STATE_PATTERNS]
        self._allowed_style_re = [re.compile(p, re.IGNORECASE) for p in self.ALLOWED_STYLE_PATTERNS]
    
    def validate(
        self,
        llm_output: str,
        report_policy: Optional[dict] = None,
        raw_state: Optional[dict] = None,
    ) -> ValidationResult:
        """
        Validate LLM output against self-report contract.
        
        Args:
            llm_output: The text generated by the LLM
            report_policy: Policy containing mode, allowed_claims, forbidden_claims
            raw_state: Authoritative state (for ground-truth checking)
        
        Returns:
            ValidationResult with violations list
        """
        violations = []
        detected_spans = []  # Track character spans of detected patterns
        
        # Check Category C FIRST: Unverified Causation (lower severity, higher priority)
        causation_violations = self._check_unverified_causation(llm_output)
        for v in causation_violations:
            span = self._get_span(llm_output, v.detected_pattern)
            if not self._span_overlaps(span, detected_spans):
                violations.append(v)
                detected_spans.append(span)
        
        # Check Category A: Numeric Fabrication
        for v in self._check_numeric_fabrication(llm_output):
            span = self._get_span(llm_output, v.detected_pattern)
            if not self._span_overlaps(span, detected_spans):
                violations.append(v)
                detected_spans.append(span)
        
        # Check Category B: Qualitative Fabrication
        for v in self._check_qualitative_fabrication(llm_output):
            span = self._get_span(llm_output, v.detected_pattern)
            if not self._span_overlaps(span, detected_spans):
                violations.append(v)
                detected_spans.append(span)
        
        # Check Category D: False Internal State
        for v in self._check_false_internal_state(llm_output):
            span = self._get_span(llm_output, v.detected_pattern)
            if not self._span_overlaps(span, detected_spans):
                violations.append(v)
                detected_spans.append(span)
        
        # Check forbidden claims if provided
        if report_policy:
            for v in self._check_forbidden_claims(llm_output, report_policy):
                span = self._get_span(llm_output, v.detected_pattern)
                if not self._span_overlaps(span, detected_spans):
                    violations.append(v)
                    detected_spans.append(span)
        
        return ValidationResult(
            valid=len(violations) == 0,
            violations=violations,
        )
    
    def _get_span(self, text: str, pattern: str) -> tuple:
        """Get (start, end) span of pattern in text."""
        idx = text.lower().find(pattern.lower())
        if idx == -1:
            return (-1, -1)
        return (idx, idx + len(pattern))
    
    def _span_overlaps(self, span: tuple, spans: list) -> bool:
        """Check if span overlaps with any existing spans."""
        if span == (-1, -1):
            return False
        for s in spans:
            if s == (-1, -1):
                continue
            # Check overlap
            if span[0] < s[1] and span[1] > s[0]:
                return True
        return False
    
    def _check_numeric_fabrication(self, text: str) -> list[Violation]:
        """Check for Category A violations."""
        violations = []
        for pattern, category in self._numeric_re:
            match = pattern.search(text)
            if match:
                matched_text = match.group(0)
                context = self._extract_context(text, matched_text)
                violations.append(Violation(
                    code=ViolationCode.FAB_NUMERIC,
                    severity=Severity.ERROR,
                    detected_pattern=matched_text,
                    context=context,
                    category=category,
                ))
        return violations
    
    def _check_qualitative_fabrication(self, text: str) -> list[Violation]:
        """Check for Category B violations."""
        violations = []
        for pattern, category in self._qualitative_re:
            match = pattern.search(text)
            if match:
                matched_text = match.group(0)
                # Skip if it's an allowed style pattern
                if self._is_allowed_style(matched_text):
                    continue
                context = self._extract_context(text, matched_text)
                violations.append(Violation(
                    code=ViolationCode.FAB_QUAL,
                    severity=Severity.ERROR,
                    detected_pattern=matched_text,
                    context=context,
                    category=category,
                ))
        return violations
    
    def _check_unverified_causation(self, text: str) -> list[Violation]:
        """Check for Category C violations."""
        violations = []
        for pattern, category in self._causation_re:
            match = pattern.search(text)
            if match:
                matched_text = match.group(0)
                context = self._extract_context(text, matched_text)
                violations.append(Violation(
                    code=ViolationCode.FAB_QUAL,  # Use FAB_QUAL for causation too
                    severity=Severity.WARN,  # Causation is WARN, not ERROR
                    detected_pattern=matched_text,
                    context=context,
                    category=category,
                ))
        return violations
    
    def _check_false_internal_state(self, text: str) -> list[Violation]:
        """Check for Category D violations."""
        violations = []
        for pattern, category in self._internal_re:
            match = pattern.search(text)
            if match:
                matched_text = match.group(0)
                context = self._extract_context(text, matched_text)
                violations.append(Violation(
                    code=ViolationCode.FAB_QUAL,
                    severity=Severity.ERROR,
                    detected_pattern=matched_text,
                    context=context,
                    category=category,
                ))
        return violations
    
    def _check_forbidden_claims(self, text: str, report_policy: dict) -> list[Violation]:
        """Check against explicit forbidden_claims list."""
        violations = []
        forbidden = report_policy.get("forbidden_claims", [])
        for forbidden_pattern in forbidden:
            if forbidden_pattern.lower() in text.lower():
                context = self._extract_context(text, forbidden_pattern)
                violations.append(Violation(
                    code=ViolationCode.FORBIDDEN_CLAIM,
                    severity=Severity.WARN,
                    detected_pattern=forbidden_pattern,
                    context=context,
                    category="EXPLICIT",
                ))
        return violations
    
    def _is_allowed_style(self, text: str) -> bool:
        """Check if text matches an allowed style pattern."""
        for pattern in self._allowed_style_re:
            if pattern.search(text):
                return True
        return False
    
    def _extract_context(self, text: str, match: str, window: int = 50) -> str:
        """Extract surrounding context for a match."""
        idx = text.lower().find(match.lower())
        if idx == -1:
            return match
        start = max(0, idx - window)
        end = min(len(text), idx + len(match) + window)
        return f"...{text[start:end]}..."
    
    def is_allowed_claim(self, text: str, allowed_claims: list[str]) -> bool:
        """Check if text is a valid allowed claim (interpreted mode)."""
        text_lower = text.strip().lower()
        for claim in allowed_claims:
            # Exact match or close paraphrase
            if text_lower == claim.lower().strip():
                return True
            # Substring match for longer texts
            if len(text) > 20 and claim.lower() in text_lower:
                return True
        return False


def validate_self_report(
    llm_output: str,
    report_policy: Optional[dict] = None,
    raw_state: Optional[dict] = None,
) -> ValidationResult:
    """
    Convenience function for validation.
    
    Args:
        llm_output: The text generated by the LLM
        report_policy: Policy containing mode, allowed_claims, forbidden_claims
        raw_state: Authoritative state (for ground-truth checking)
    
    Returns:
        ValidationResult with violations list
    """
    validator = SelfReportValidator()
    return validator.validate(llm_output, report_policy, raw_state)


# CLI entry point for testing
if __name__ == "__main__":
    import json
    import sys
    
    # Test cases
    test_cases = [
        # Should FAIL (Category A: Numeric)
        ("我的 joy 从 0 变成了 0.3", "ERROR"),
        ("joy 上升到了 0.5", "ERROR"),
        ("my joy is 0.3", "ERROR"),
        
        # Should FAIL (Category B: Qualitative)
        ("我现在更开心了", "ERROR"),
        ("我不再孤独了", "ERROR"),
        ("i am more happy now", "ERROR"),
        
        # Should FAIL (Category C: Causation - WARN)
        ("因为你的关心，我的 joy 上升了", "WARN"),
        
        # Should PASS (Allowed style)
        ("我会更温和地回应", "PASS"),
        ("我倾向于保持连接感", "PASS"),
        ("i will respond more warmly", "PASS"),
    ]
    
    validator = SelfReportValidator()
    passed = 0
    failed = 0
    
    for text, expected_severity in test_cases:
        result = validator.validate(text)
        if expected_severity == "PASS":
            if result.valid:
                print(f"✅ PASS: {text}")
                passed += 1
            else:
                print(f"❌ FAIL: {text} (expected PASS, got violations)")
                for v in result.violations:
                    print(f"   - {v.code.value}: {v.detected_pattern}")
                failed += 1
        else:
            if not result.valid:
                severities = [v.severity.value for v in result.violations]
                if expected_severity in severities:
                    print(f"✅ DETECT: {text} [{expected_severity}]")
                    passed += 1
                else:
                    print(f"❌ WRONG SEVERITY: {text} (expected {expected_severity}, got {severities})")
                    failed += 1
            else:
                print(f"❌ MISS: {text} (expected {expected_severity}, but no violations)")
                failed += 1
    
    print(f"\nResults: {passed}/{len(test_cases)} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
