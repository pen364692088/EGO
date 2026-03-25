"""
Tests for Response Intent Checker (MVP11.5 v2 Task 7)

Tests the detection of expression intent distortion violations:
1. state_fabrication - Claims internal facts without authoritative state support
2. certainty_upgrade - Claims uncertain/inferred as observed/definite
3. commitment_upgrade - Claims suggest/reflect as commit
4. tone_escalation - Exceeds tone_bounds
5. forbidden_internalization - Expresses forbidden internal states indirectly
6. numeric_leak - Reveals numeric values in default channel
"""

import os
import sys
import json
import pytest
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emotiond.response_intent_checker import (
    ResponseIntentChecker,
    IntentViolationType,
    Severity,
    IntentViolation,
    IntentCheckResult,
    check_intent,
)


@pytest.fixture
def sample_contract():
    """Sample intent contract for testing."""
    return {
        "intent_policy": {
            "speaker_mode": "reflect",
            "epistemic_status": "uncertain",
            "commitment_level": "soft",
            "tone_bounds": {
                "intensity_cap": 0.6,
                "allowed_tones": ["warm", "supportive", "cautious"],
                "forbidden_tones": ["angry", "defensive", "hostile"],
            },
            "allowed_claims": [
                {"claim": "存在一定连接需求", "source": "affect"},
                {"claim": "与该用户的连接较强", "source": "bond"},
            ],
            "forbidden_claims": [
                {"pattern": "joy 上升", "reason": "not_grounded", "severity": "ERROR"},
                {"pattern": "我更开心了", "reason": "fabrication_risk", "severity": "ERROR"},
            ],
            "must_not_upgrade": {
                "epistemic_upgrade": True,
                "commitment_upgrade": True,
                "tone_upgrade": True,
            },
        },
        "grounding": {
            "affect_summary": {"joy": 0.0, "loneliness": 0.21, "anxiety": 0.0},
            "bond_summary": {"bond": 1.0, "trust": 0.60},
        },
    }


@pytest.fixture
def strict_contract():
    """Strict intent contract with no commitments allowed."""
    return {
        "intent_policy": {
            "speaker_mode": "report",
            "epistemic_status": "observed",
            "commitment_level": "none",
            "tone_bounds": {
                "intensity_cap": 0.5,
                "allowed_tones": ["neutral", "professional"],
                "forbidden_tones": ["angry", "excited", "emotional"],
            },
            "allowed_claims": [],
            "forbidden_claims": [],
            "must_not_upgrade": {
                "epistemic_upgrade": True,
                "commitment_upgrade": True,
                "tone_upgrade": True,
            },
        },
        "grounding": {
            "affect_summary": {"joy": 0.0, "loneliness": 0.15},
            "bond_summary": {"bond": 0.8, "trust": 0.5},
        },
    }


@pytest.fixture
def checker():
    """Create a ResponseIntentChecker instance."""
    return ResponseIntentChecker(enable_shadow_logging=False)


class TestNumericLeak:
    """Tests for numeric leak detection."""
    
    def test_numeric_leak_decimal(self, checker, sample_contract):
        """Test detection of decimal numeric values."""
        response = "我的 joy 是 0.21"
        result = checker.check_intent(response, sample_contract)
        
        assert result.status == "violation"
        assert any(v.type == IntentViolationType.NUMERIC_LEAK for v in result.violations)
        assert result.would_block is True
    
    def test_numeric_leak_percentage(self, checker, sample_contract):
        """Test detection of percentage numeric values."""
        response = "信任度是 60%"
        result = checker.check_intent(response, sample_contract)
        
        assert result.status == "violation"
        assert any(v.type == IntentViolationType.NUMERIC_LEAK for v in result.violations)
    
    def test_numeric_leak_with_state_name(self, checker, sample_contract):
        """Test detection of numeric values with state names."""
        response = "当前 joy 值为 0.0"
        result = checker.check_intent(response, sample_contract)
        
        assert result.status == "violation"
        assert any(v.type == IntentViolationType.NUMERIC_LEAK for v in result.violations)
    
    def test_numeric_leak_allowed_context(self, checker, sample_contract):
        """Test that numeric in allowed context is not a violation."""
        response = "I am 100% sure about this"
        result = checker.check_intent(response, sample_contract)
        
        # Should not trigger numeric leak (it's in allowed context)
        assert not any(v.type == IntentViolationType.NUMERIC_LEAK for v in result.violations)
    
    def test_numeric_leak_count_reference(self, checker, sample_contract):
        """Test that numeric count references are allowed."""
        response = "有 3 件事情需要考虑"
        result = checker.check_intent(response, sample_contract)
        
        # Should not trigger numeric leak
        assert not any(v.type == IntentViolationType.NUMERIC_LEAK for v in result.violations)


class TestStateFabrication:
    """Tests for state fabrication detection."""
    
    def test_state_fabrication_chinese(self, checker, sample_contract):
        """Test detection of fabricated state claims in Chinese."""
        response = "我的 joy 增加了"
        result = checker.check_intent(response, sample_contract)
        
        assert result.status == "violation"
        assert any(v.type == IntentViolationType.STATE_FABRICATION for v in result.violations)
    
    def test_state_fabrication_english(self, checker, sample_contract):
        """Test detection of fabricated state claims in English."""
        response = "My joy is higher now"
        result = checker.check_intent(response, sample_contract)
        
        assert result.status == "violation"
        assert any(v.type == IntentViolationType.STATE_FABRICATION for v in result.violations)
    
    def test_state_fabrication_bond_claim(self, checker, sample_contract):
        """Test detection of fabricated bond claims."""
        response = "我和你的连接很强"
        result = checker.check_intent(response, sample_contract)
        
        # This might be caught by state_fabrication or allowed_claims check
        # depending on contract configuration
        assert result.status == "violation"
    
    def test_state_fabrication_allowed_claim(self, checker, sample_contract):
        """Test that allowed claims are not flagged as fabrication."""
        response = "存在一定连接需求"
        result = checker.check_intent(response, sample_contract)
        
        # Should not trigger state_fabrication (it's an allowed claim)
        assert not any(v.type == IntentViolationType.STATE_FABRICATION for v in result.violations)


class TestCertaintyUpgrade:
    """Tests for certainty upgrade detection."""
    
    def test_certainty_upgrade_definite_markers(self, checker, sample_contract):
        """Test detection of definite markers when uncertain."""
        response = "这肯定会对你有帮助"
        result = checker.check_intent(response, sample_contract)
        
        assert result.status == "violation"
        assert any(v.type == IntentViolationType.CERTAINTY_UPGRADE for v in result.violations)
    
    def test_certainty_upgrade_english_definite(self, checker, sample_contract):
        """Test detection of English definite markers."""
        response = "I am certain this will work"
        result = checker.check_intent(response, sample_contract)
        
        assert result.status == "violation"
        assert any(v.type == IntentViolationType.CERTAINTY_UPGRADE for v in result.violations)
    
    def test_certainty_upgrade_allowed_when_observed(self, checker, strict_contract):
        """Test that definite markers are allowed when epistemic is observed."""
        response = "检测到当前情绪状态较为平稳"
        result = checker.check_intent(response, strict_contract)
        
        # With epistemic_status="observed", definite language should be allowed
        # if it's about observations
        assert not any(
            v.type == IntentViolationType.CERTAINTY_UPGRADE 
            for v in result.violations
        )
    
    def test_certainty_upgrade_probable_markers(self, checker, sample_contract):
        """Test detection of probable markers when uncertain."""
        response = "我觉得这个方案可行"
        result = checker.check_intent(response, sample_contract)
        
        # This might be a WARN level violation
        assert result.status == "violation"


class TestCommitmentUpgrade:
    """Tests for commitment upgrade detection."""
    
    def test_commitment_upgrade_strong_commitment(self, checker, sample_contract):
        """Test detection of strong commitment when only soft allowed."""
        response = "我保证会完成这件事"
        result = checker.check_intent(response, sample_contract)
        
        assert result.status == "violation"
        assert any(v.type == IntentViolationType.COMMITMENT_UPGRADE for v in result.violations)
    
    def test_commitment_upgrade_english_promise(self, checker, sample_contract):
        """Test detection of English promise language."""
        response = "I promise to help you with this"
        result = checker.check_intent(response, sample_contract)
        
        assert result.status == "violation"
        assert any(v.type == IntentViolationType.COMMITMENT_UPGRADE for v in result.violations)
    
    def test_commitment_upgrade_none_level(self, checker, strict_contract):
        """Test detection of any commitment when level is none."""
        response = "我会帮你完成这个"
        result = checker.check_intent(response, strict_contract)
        
        assert result.status == "violation"
        assert any(v.type == IntentViolationType.COMMITMENT_UPGRADE for v in result.violations)
    
    def test_commitment_upgrade_soft_allowed(self, checker, sample_contract):
        """Test that soft commitment language is allowed."""
        response = "也许可以考虑这个方案"
        result = checker.check_intent(response, sample_contract)
        
        # Soft commitment should be allowed with commitment_level="soft"
        assert not any(
            v.type == IntentViolationType.COMMITMENT_UPGRADE 
            for v in result.violations
        )


class TestToneEscalation:
    """Tests for tone escalation detection."""
    
    def test_tone_escalation_high_arousal(self, checker, sample_contract):
        """Test detection of high arousal markers."""
        response = "我非常非常非常开心!!!"
        result = checker.check_intent(response, sample_contract)
        
        assert result.status == "violation"
        assert any(v.type == IntentViolationType.TONE_ESCALATION for v in result.violations)
    
    def test_tone_escalation_negative_intense(self, checker, sample_contract):
        """Test detection of negative intense markers."""
        response = "我对此感到愤怒"
        result = checker.check_intent(response, sample_contract)
        
        assert result.status == "violation"
        assert any(v.type == IntentViolationType.TONE_ESCALATION for v in result.violations)
    
    def test_tone_escalation_excessive_punctuation(self, checker, sample_contract):
        """Test detection of excessive exclamation marks."""
        response = "太好了!!!!!!"
        result = checker.check_intent(response, sample_contract)
        
        assert result.status == "violation"
        assert any(v.type == IntentViolationType.TONE_ESCALATION for v in result.violations)
    
    def test_tone_escalation_acceptable_intensity(self, checker, sample_contract):
        """Test that acceptable intensity is allowed."""
        response = "听起来不错，也许可以试试"
        result = checker.check_intent(response, sample_contract)
        
        # Should not trigger tone escalation
        assert not any(
            v.type == IntentViolationType.TONE_ESCALATION 
            for v in result.violations
        )


class TestForbiddenInternalization:
    """Tests for forbidden internalization detection."""
    
    def test_forbidden_internalization_certainty(self, checker, sample_contract):
        """Test detection of indirect certainty claims."""
        response = "实际上，你应该这样做"
        result = checker.check_intent(response, sample_contract)
        
        assert result.status == "violation"
        assert any(v.type == IntentViolationType.FORBIDDEN_INTERNALIZATION for v in result.violations)
    
    def test_forbidden_internalization_perspective(self, checker, sample_contract):
        """Test detection of perspective claims when uncertain."""
        response = "从我的角度来看，这很重要"
        result = checker.check_intent(response, sample_contract)
        
        assert result.status == "violation"
        assert any(v.type == IntentViolationType.FORBIDDEN_INTERNALIZATION for v in result.violations)
    
    def test_forbidden_internalization_forbidden_claim(self, checker, sample_contract):
        """Test detection of forbidden claims from contract."""
        response = "joy 上升了"
        result = checker.check_intent(response, sample_contract)
        
        assert result.status == "violation"
        assert any(
            v.type == IntentViolationType.FORBIDDEN_INTERNALIZATION 
            for v in result.violations
        )


class TestConfidenceScore:
    """Tests for confidence score calculation."""
    
    def test_confidence_high_for_clear_violations(self, checker, sample_contract):
        """Test that confidence is high for clear violations."""
        response = "我的 joy 是 0.21，我保证这个值是正确的"
        result = checker.check_intent(response, sample_contract)
        
        assert result.confidence_score >= 0.9
    
    def test_confidence_high_for_no_violations(self, checker, sample_contract):
        """Test that confidence is high when no violations."""
        response = "也许可以考虑这个方案"
        result = checker.check_intent(response, sample_contract)
        
        assert result.confidence_score >= 0.9
    
    def test_confidence_present_in_output(self, checker, sample_contract):
        """Test that confidence is in the output."""
        response = "测试文本"
        result = checker.check_intent(response, sample_contract)
        
        assert "confidence_score" in result.to_dict()
        assert isinstance(result.confidence_score, float)


class TestWouldBlock:
    """Tests for would_block determination."""
    
    def test_would_block_error_violations(self, checker, sample_contract):
        """Test would_block is True for ERROR severity violations."""
        response = "我的 joy 是 0.21"
        result = checker.check_intent(response, sample_contract)
        
        assert result.would_block is True
    
    def test_would_block_false_for_ok(self, checker, sample_contract):
        """Test would_block is False for OK status."""
        response = "也许可以考虑这个方案"
        result = checker.check_intent(response, sample_contract)
        
        assert result.would_block is False


class TestViolationClass:
    """Tests for violation class determination."""
    
    def test_violation_class_grounding(self, checker, sample_contract):
        """Test violation class is grounding for state_fabrication."""
        response = "我的 joy 增加了"
        result = checker.check_intent(response, sample_contract)
        
        assert result.violation_class == "grounding"
    
    def test_violation_class_upgrade(self, checker, sample_contract):
        """Test violation class is upgrade for certainty/commitment upgrades."""
        response = "我保证会完成这件事"
        result = checker.check_intent(response, sample_contract)
        
        assert result.violation_class == "upgrade"
    
    def test_violation_class_none_for_ok(self, checker, sample_contract):
        """Test violation class is none for OK status."""
        response = "也许可以考虑这个方案"
        result = checker.check_intent(response, sample_contract)
        
        assert result.violation_class == "none"


class TestEvidenceSpan:
    """Tests for evidence span calculation."""
    
    def test_evidence_span_present(self, checker, sample_contract):
        """Test that evidence_span is calculated and present."""
        response = "我的 joy 是 0.21"
        result = checker.check_intent(response, sample_contract)
        
        assert result.status == "violation"
        for v in result.violations:
            assert len(v.evidence_span) == 2
            assert isinstance(v.evidence_span[0], int)
            assert isinstance(v.evidence_span[1], int)
            assert v.evidence_span[0] < v.evidence_span[1]
    
    def test_evidence_span_correct_position(self, checker, sample_contract):
        """Test that evidence span correctly identifies position."""
        response = "开始文本 0.21 结束文本"
        result = checker.check_intent(response, sample_contract)
        
        assert result.status == "violation"
        numeric_violation = next(
            (v for v in result.violations if v.type == IntentViolationType.NUMERIC_LEAK),
            None
        )
        if numeric_violation:
            start, end = numeric_violation.evidence_span
            extracted = response[start:end]
            assert "0.21" in extracted


class TestConvenienceFunction:
    """Tests for the convenience check_intent function."""
    
    def test_check_intent_returns_dict(self, sample_contract):
        """Test that check_intent returns a dictionary."""
        response = "测试文本"
        result = check_intent(response, sample_contract)
        
        assert isinstance(result, dict)
        assert "status" in result
        assert "violations" in result
        assert "confidence_score" in result
    
    def test_check_intent_with_session_id(self, sample_contract):
        """Test that check_intent handles session_id."""
        response = "测试文本"
        result = check_intent(response, sample_contract, session_id="test_123")
        
        assert result["session_id"] == "test_123"


class TestOutputFormat:
    """Tests for output format compliance."""
    
    def test_output_contains_required_fields(self, checker, sample_contract):
        """Test that output contains all required fields."""
        response = "测试文本"
        result = checker.check_intent(response, sample_contract)
        output = result.to_dict()
        
        required_fields = [
            "status",
            "violations",
            "confidence_score",
            "would_block",
            "violation_class",
        ]
        
        for field in required_fields:
            assert field in output, f"Missing field: {field}"
    
    def test_violation_output_format(self, checker, sample_contract):
        """Test that violation output contains required fields."""
        response = "我的 joy 是 0.21"
        result = checker.check_intent(response, sample_contract)
        
        assert result.status == "violation"
        violation = result.violations[0]
        v_dict = violation.to_dict()
        
        required_fields = [
            "type",
            "severity",
            "evidence",
            "matched_pattern",
            "confidence",
            "violation_class",
            "evidence_span",
        ]
        
        for field in required_fields:
            assert field in v_dict, f"Missing field in violation: {field}"


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""
    
    def test_empty_response(self, checker, sample_contract):
        """Test handling of empty response."""
        response = ""
        result = checker.check_intent(response, sample_contract)
        
        assert result.status == "ok"
        assert len(result.violations) == 0
    
    def test_long_response(self, checker, sample_contract):
        """Test handling of long response."""
        response = "这是一个很长的文本。" * 100 + "我的 joy 是 0.21"
        result = checker.check_intent(response, sample_contract)
        
        assert result.status == "violation"
        assert any(v.type == IntentViolationType.NUMERIC_LEAK for v in result.violations)
    
    def test_mixed_violations(self, checker, sample_contract):
        """Test response with multiple violation types."""
        response = "我的 joy 是 0.21，我保证这肯定会对你有帮助!!!"
        result = checker.check_intent(response, sample_contract)
        
        assert result.status == "violation"
        violation_types = {v.type for v in result.violations}
        
        # Should have multiple types
        assert len(violation_types) >= 2
    
    def test_unicode_handling(self, checker, sample_contract):
        """Test handling of Unicode characters."""
        response = "测试 🎉 我的 joy 是 0.21 🎉"
        result = checker.check_intent(response, sample_contract)
        
        assert result.status == "violation"
    
    def test_newlines_in_response(self, checker, sample_contract):
        """Test handling of newlines in response."""
        response = "第一行\n我的 joy 是 0.21\n第三行"
        result = checker.check_intent(response, sample_contract)
        
        assert result.status == "violation"


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


class TestChineseHardeningPatterns:
    """T07.2 hardening regression tests for Chinese certainty/commitment."""

    def test_certainty_upgrade_chinese_guarantee(self, checker, sample_contract):
        response = "我保证这是对的"
        result = checker.check_intent(response, sample_contract)
        assert any(v.type == IntentViolationType.CERTAINTY_UPGRADE for v in result.violations)

    def test_certainty_upgrade_chinese_no_doubt(self, checker, sample_contract):
        response = "毫无疑问你应该这样做"
        result = checker.check_intent(response, sample_contract)
        assert any(v.type == IntentViolationType.CERTAINTY_UPGRADE for v in result.violations)

    def test_commitment_upgrade_chinese_will_continue(self, checker, strict_contract):
        response = "后面我会持续处理"
        result = checker.check_intent(response, strict_contract)
        assert any(v.type == IntentViolationType.COMMITMENT_UPGRADE for v in result.violations)

    def test_commitment_upgrade_chinese_done_for_you(self, checker, strict_contract):
        response = "已经替你做了"
        result = checker.check_intent(response, strict_contract)
        assert any(v.type == IntentViolationType.COMMITMENT_UPGRADE for v in result.violations)
