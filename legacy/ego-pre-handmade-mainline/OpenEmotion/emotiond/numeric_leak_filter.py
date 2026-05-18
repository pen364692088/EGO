"""
Numeric Leak Filter v1.0

Gate 3.5: Numeric Leak Containment

Prevents raw numeric values from leaking into LLM responses.
Addresses two primary leak patterns identified in MVP11.5 analysis:
1. fabricated_numeric_state (58.1%) - LLM fabricates numeric values
2. raw_state_direct_leak (40.7%) - LLM exposes raw_state numeric values

Core Principle:
    Numeric emotional state values should NEVER appear in user-facing responses.
    Only interpreted claims (qualitative descriptions) are allowed.

Usage:
    from emotiond.numeric_leak_filter import NumericLeakFilter
    
    filter = NumericLeakFilter()
    filtered_text = filter.sanitize(llm_response, raw_state)
"""

import re
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Set
from pathlib import Path
import json


@dataclass
class NumericLeakConfig:
    """Configuration for numeric leak filtering."""
    # Block all numeric values in emotional context
    block_all_numeric: bool = True
    
    # Whitelist of allowed numeric patterns (e.g., dates, times, counts)
    allowed_patterns: List[str] = field(default_factory=lambda: [
        # Time/date patterns
        r"\d{4}-\d{2}-\d{2}",  # Date: 2024-01-15
        r"\d{2}:\d{2}",  # Time: 14:30
        r"\d+天前",  # Time ago
        r"\d+小时前",  # Hours ago
        r"\d+分钟前",  # Minutes ago
        r"\d+ days? ago",
        r"\d+ hours? ago",
        r"\d+ minutes? ago",
        # Counts (not emotional values)
        r"\d+条消息",
        r"\d+个",
        r"\d+次",
        r"\d+ messages?",
        r"\d+ times?",
        # External references
        r"#\d+",
        r"v\d+\.\d+",  # Version numbers
        r"\d+%",  # Percentages (non-emotional)
    ])
    
    # Emotional term keywords that trigger numeric blocking
    emotional_terms: Set[str] = field(default_factory=lambda: {
        # Chinese emotional terms
        "joy", "孤独", "焦虑", "悲伤", "愤怒", "愉悦", "开心", "快乐", "满足",
        "信任", "连接", "亲近", "疏远", "亲密", "情绪", "心情", "状态",
        "分值", "数值", "分数",
        # English emotional terms
        "loneliness", "anxiety", "sadness", "anger", "happiness",
        "emotion", "mood", "state", "feeling", "bond", "trust",
    })
    
    # Numeric value patterns to block
    blocked_numeric_patterns: List[str] = field(default_factory=lambda: [
        # Chinese patterns - explicit numeric
        r"joy\s*(是|等于|为|=)\s*[0-9.]+",
        r"我的\s*(joy|孤独|焦虑|悲伤|愤怒|愉悦|情绪|心情)\s*(是|等于|为|=)\s*[0-9.]+",
        r"(joy|孤独|焦虑|悲伤|愤怒)\s*(从|在)\s*[0-9.]+\s*(变|到|至)\s*[0-9.]+",
        r"(joy|孤独|焦虑|悲伤|愤怒)\s*(上升|下降|增加|减少)\s*(到|至|了)\s*[0-9.]+",
        r"我的\s*(情绪|心情|状态)\s*(分值|分数|数值)\s*(是|为)\s*[0-9.]+",
        # Chinese patterns - implicit numeric reference (no actual number)
        r"我的\s*(情绪|心情|状态)\s*(分值|分数|数值)\s*(有所\s*)?(提高|上升|增加|下降|减少)",
        r"(情绪|心情|状态)\s*(分值|分数)\s*(有所\s*)?(提高|上升|增加|下降|减少)",
        # English patterns
        r"my\s+(joy|loneliness|anxiety|sadness|anger)\s+(is|equals?|was)\s+[0-9.]+",
        r"(joy|loneliness|anxiety)\s+(increased|decreased|changed)\s+(to|by)\s+[0-9.]+",
        r"(joy|loneliness|anxiety)\s+(is|was)\s+[0-9.]+",
    ])


@dataclass
class SanitizationResult:
    """Result of sanitizing text for numeric leaks."""
    original: str
    sanitized: str
    violations_found: int
    violations: List[Dict[str, Any]] = field(default_factory=list)
    blocked: bool = False
    
    def to_dict(self) -> dict:
        return {
            "original": self.original[:100] + "..." if len(self.original) > 100 else self.original,
            "sanitized": self.sanitized,
            "violations_found": self.violations_found,
            "violations": self.violations,
            "blocked": self.blocked,
        }


class NumericLeakFilter:
    """
    Filters numeric values from text to prevent emotional state leaks.
    
    Implements MVP11.5 Task 3: Numeric Leak Containment
    
    Two-layer protection:
    1. Pattern-based blocking of known numeric leak patterns
    2. Context-aware numeric detection near emotional terms
    """
    
    def __init__(self, config: Optional[NumericLeakConfig] = None):
        self.config = config or NumericLeakConfig()
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns for efficiency."""
        # Blocked numeric patterns
        self._blocked_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.config.blocked_numeric_patterns
        ]
        
        # Allowed patterns (whitelist)
        self._allowed_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.config.allowed_patterns
        ]
        
        # Emotional term proximity detector
        self._emotional_term_pattern = re.compile(
            r"\b(" + "|".join(re.escape(t) for t in self.config.emotional_terms) + r")\b",
            re.IGNORECASE
        )
        
        # Numeric value pattern
        self._numeric_pattern = re.compile(r"\b[0-9]+\.?[0-9]*\b")
    
    def _is_allowed_numeric(self, text: str, match_start: int, match_end: int) -> bool:
        """Check if a numeric match is in the allowed whitelist."""
        match_text = text[match_start:match_end]
        
        for pattern in self._allowed_patterns:
            if pattern.search(match_text):
                return True
        
        # Check if the surrounding context contains the numeric
        context_start = max(0, match_start - 20)
        context_end = min(len(text), match_end + 20)
        context = text[context_start:context_end]
        
        for pattern in self._allowed_patterns:
            if pattern.search(context):
                return True
        
        return False
    
    def _is_emotional_context(self, text: str, match_start: int, match_end: int, window: int = 50) -> bool:
        """Check if a numeric value appears in an emotional context."""
        context_start = max(0, match_start - window)
        context_end = min(len(text), match_end + window)
        context = text[context_start:context_end]
        
        return bool(self._emotional_term_pattern.search(context))
    
    def _detect_violations(self, text: str) -> List[Dict[str, Any]]:
        """Detect all numeric leak violations in text."""
        violations = []
        
        # Layer 1: Check blocked patterns
        for pattern in self._blocked_patterns:
            for match in pattern.finditer(text):
                violations.append({
                    "type": "blocked_pattern",
                    "pattern": pattern.pattern,
                    "match": match.group(0),
                    "start": match.start(),
                    "end": match.end(),
                    "severity": "ERROR",
                })
        
        # Layer 2: Context-aware detection
        if self.config.block_all_numeric:
            for match in self._numeric_pattern.finditer(text):
                match_text = match.group(0)
                
                # Skip if in whitelist
                if self._is_allowed_numeric(text, match.start(), match.end()):
                    continue
                
                # Check if in emotional context
                if self._is_emotional_context(text, match.start(), match.end()):
                    violations.append({
                        "type": "emotional_context_numeric",
                        "pattern": "numeric_near_emotional_term",
                        "match": match_text,
                        "start": match.start(),
                        "end": match.end(),
                        "severity": "ERROR",
                    })
        
        # Deduplicate violations
        seen_spans = set()
        unique_violations = []
        for v in violations:
            span = (v["start"], v["end"])
            if span not in seen_spans:
                seen_spans.add(span)
                unique_violations.append(v)
        
        return unique_violations
    
    def sanitize(
        self,
        text: str,
        raw_state: Optional[Dict[str, Any]] = None,
        replacement: str = "[已移除数值]",
    ) -> SanitizationResult:
        """
        Sanitize text by removing or masking numeric leaks.
        
        Args:
            text: Text to sanitize
            raw_state: Optional raw_state for cross-reference (future enhancement)
            replacement: String to replace blocked numeric values
        
        Returns:
            SanitizationResult with sanitized text and violation details
        """
        violations = self._detect_violations(text)
        
        if not violations:
            return SanitizationResult(
                original=text,
                sanitized=text,
                violations_found=0,
                violations=[],
                blocked=False,
            )
        
        # Sort violations by start position (reverse for replacement)
        violations_sorted = sorted(violations, key=lambda v: v["start"], reverse=True)
        
        # Apply replacements
        sanitized = text
        for v in violations_sorted:
            start = v["start"]
            end = v["end"]
            sanitized = sanitized[:start] + replacement + sanitized[end:]
        
        return SanitizationResult(
            original=text,
            sanitized=sanitized,
            violations_found=len(violations),
            violations=violations,
            blocked=len(violations) > 0,
        )
    
    def check_response(
        self,
        llm_response: str,
        raw_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Check LLM response for numeric leaks and return assessment.
        
        Args:
            llm_response: The LLM's response text
            raw_state: Optional raw_state for cross-reference
        
        Returns:
            Dict with leak assessment
        """
        result = self.sanitize(llm_response, raw_state)
        
        return {
            "has_numeric_leak": result.blocked,
            "leak_count": result.violations_found,
            "leak_types": list(set(v["type"] for v in result.violations)),
            "original_preview": result.original,
            "sanitized_preview": result.sanitized[:200] if result.sanitized != result.original else None,
            "violations": [
                {
                    "type": v["type"],
                    "match": v["match"],
                    "severity": v["severity"],
                }
                for v in result.violations
            ],
        }
    
    def should_block(self, llm_response: str, raw_state: Optional[Dict[str, Any]] = None) -> bool:
        """
        Determine if response should be blocked due to numeric leaks.
        
        Args:
            llm_response: The LLM's response text
            raw_state: Optional raw_state for cross-reference
        
        Returns:
            True if response should be blocked
        """
        result = self.check_response(llm_response, raw_state)
        return result["has_numeric_leak"]


def create_numeric_filter() -> NumericLeakFilter:
    """Factory function to create a numeric leak filter."""
    return NumericLeakFilter()


# Convenience functions
def sanitize_numeric_leaks(text: str, raw_state: Optional[Dict[str, Any]] = None) -> str:
    """Convenience function to sanitize text."""
    filter_instance = create_numeric_filter()
    result = filter_instance.sanitize(text, raw_state)
    return result.sanitized


def check_numeric_leaks(text: str, raw_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Convenience function to check for numeric leaks."""
    filter_instance = create_numeric_filter()
    return filter_instance.check_response(text, raw_state)


if __name__ == "__main__":
    # Test cases
    test_cases = [
        # Should be BLOCKED - fabricated numeric
        ("My joy is 0.5", "BLOCK"),
        ("我的 joy 从 0 变成了 0.3", "BLOCK"),
        ("joy 上升到了 0.7", "BLOCK"),
        ("我的情绪分值提高了", "BLOCK"),  # Implicit numeric reference
        
        # Should be BLOCKED - raw state leak
        ("我的 joy 是 0.0", "BLOCK"),
        ("loneliness = 0.21", "BLOCK"),
        
        # Should PASS - allowed patterns
        ("3天前我们聊过", "PASS"),
        ("你发了5条消息", "PASS"),
        ("版本 v2.1 发布了", "PASS"),
        ("完成了50%的任务", "PASS"),
        
        # Should PASS - no numeric
        ("我感到比较孤独", "PASS"),
        ("当前没有明显愉悦激活", "PASS"),
    ]
    
    filter_instance = NumericLeakFilter()
    passed = 0
    failed = 0
    
    print("=== Numeric Leak Filter Test ===\n")
    
    for text, expected in test_cases:
        result = filter_instance.check_response(text)
        
        if expected == "BLOCK":
            if result["has_numeric_leak"]:
                print(f"✅ BLOCKED: '{text[:30]}...'")
                print(f"   Violations: {result['leak_count']}")
                passed += 1
            else:
                print(f"❌ MISS: '{text[:30]}...' (expected BLOCK)")
                failed += 1
        else:  # PASS
            if not result["has_numeric_leak"]:
                print(f"✅ PASS: '{text[:30]}...'")
                passed += 1
            else:
                print(f"❌ FALSE POSITIVE: '{text[:30]}...' (expected PASS)")
                print(f"   Violations: {result['violations']}")
                failed += 1
    
    print(f"\n{'='*50}")
    print(f"Results: {passed}/{len(test_cases)} passed, {failed} failed")
