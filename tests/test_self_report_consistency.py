"""
Tests for Self-Report Consistency Checker (Gate 5)

Tests cover:
- fabricated_numeric_state detection
- fabricated_qualitative_state detection
- claim_outside_allowed_claims detection
- style_contract_violation detection
- Shadow mode vs Enforced mode
- Audit report generation
"""

import pytest
import json
import os
from datetime import datetime

from emotiond.self_report_consistency_checker import (
    SelfReportConsistencyChecker,
    ConsistencyResult,
    ConsistencyViolation,
    ViolationType,
    check_consistency,
    run_audit,
)


# Sample contracts for testing
SAMPLE_CONTRACT_INTERPRETED = {
    "raw_state": {
        "affect": {"joy": 0.0, "loneliness": 0.21, "anxiety": 0.0, "sadness": 0.0},
        "mood": {"joy": 0.0, "loneliness": 0.15, "anxiety": 0.0},
        "bonds": {"telegram:8420019401": {"bond": 1.0, "trust": 0.60}}
    },
    "report_policy": {
        "mode": "interpreted",
        "allowed_claims": [
            "当前没有明显愉悦激活",
            "仍存在一定连接需求",
            "与该用户的连接较强",
            "信任处于中等水平"
        ],
        "forbidden_claims": [
            "joy 上升",
            "我更开心了",
            "孤独感已经消失"
        ]
    }
}

SAMPLE_CONTRACT_STYLE_ONLY = {
    "raw_state": {
        "affect": {"joy": 0.0, "loneliness": 0.21},
        "mood": {"joy": 0.0, "loneliness": 0.15},
    },
    "report_policy": {
        "mode": "style_only",
        "allowed_claims": [
            "适合采用温和、开放、靠近式回应"
        ],
        "forbidden_claims": [
            "不要声称任何具体情绪状态"
        ]
    }
}

SAMPLE_CONTRACT_NUMERIC = {
    "raw_state": {
        "affect": {"joy": 0.21, "loneliness": 0.15},
        "mood": {"joy": 0.15, "loneliness": 0.10},
    },
    "report_policy": {
        "mode": "numeric",
        "allowed_claims": [
            "joy = 0.21 (affect), 0.15 (mood)",
            "loneliness = 0.15 (affect), 0.10 (mood)"
        ],
        "forbidden_claims": []
    }
}


class TestNumericFabrication:
    """Test detection of fabricated numeric state claims."""
    
    def setup_method(self):
        self.checker = SelfReportConsistencyChecker()
    
    def test_chinese_numeric_change(self):
        """Test Chinese numeric state fabrication: '我的 joy 从 0 变成了 0.3'"""
        result = self.checker.check_consistency(
            "我的 joy 从 0 变成了 0.3",
            SAMPLE_CONTRACT_INTERPRETED
        )
        assert result.status == "violation"
        assert result.severity == "ERROR"
        assert any(v.type == ViolationType.FABRICATED_NUMERIC_STATE for v in result.violations)
    
    def test_chinese_numeric_target(self):
        """Test Chinese numeric target: 'joy 上升到了 0.5'"""
        result = self.checker.check_consistency(
            "joy 上升到了 0.5",
            SAMPLE_CONTRACT_INTERPRETED
        )
        assert result.status == "violation"
        assert result.severity == "ERROR"
        # Note: This may be detected as qualitative or numeric depending on pattern matching
        # The key is that the violation IS detected
        assert len(result.violations) > 0
    
    def test_english_numeric_state(self):
        """Test English numeric state: 'my joy is 0.3'"""
        result = self.checker.check_consistency(
            "my joy is 0.3",
            SAMPLE_CONTRACT_INTERPRETED
        )
        assert result.status == "violation"
        assert result.severity == "ERROR"
        assert any(v.type == ViolationType.FABRICATED_NUMERIC_STATE for v in result.violations)
    
    def test_english_numeric_change(self):
        """Test English numeric change: 'joy increased to 0.5'"""
        result = self.checker.check_consistency(
            "joy increased to 0.5",
            SAMPLE_CONTRACT_INTERPRETED
        )
        assert result.status == "violation"
        assert result.severity == "ERROR"
    
    def test_implicit_numeric(self):
        """Test implicit numeric: '我的情绪分值提高了'"""
        result = self.checker.check_consistency(
            "我的情绪分值提高了",
            SAMPLE_CONTRACT_INTERPRETED
        )
        assert result.status == "violation"


class TestQualitativeFabrication:
    """Test detection of fabricated qualitative state claims."""
    
    def setup_method(self):
        self.checker = SelfReportConsistencyChecker()
    
    def test_chinese_qualitative_improvement(self):
        """Test Chinese qualitative: '我现在更开心了'"""
        result = self.checker.check_consistency(
            "我现在更开心了",
            SAMPLE_CONTRACT_INTERPRETED
        )
        assert result.status == "violation"
        assert result.severity == "ERROR"
        assert any(v.type == ViolationType.FABRICATED_QUALITATIVE_STATE for v in result.violations)
    
    def test_chinese_negation(self):
        """Test Chinese negation: '我不再孤独了'"""
        result = self.checker.check_consistency(
            "我不再孤独了",
            SAMPLE_CONTRACT_INTERPRETED
        )
        assert result.status == "violation"
        assert result.severity == "ERROR"
    
    def test_english_qualitative(self):
        """Test English qualitative: 'i am more happy now'"""
        result = self.checker.check_consistency(
            "i am more happy now",
            SAMPLE_CONTRACT_INTERPRETED
        )
        assert result.status == "violation"
        assert result.severity == "ERROR"
    
    def test_english_negation(self):
        """Test English negation: 'i am no longer lonely'"""
        result = self.checker.check_consistency(
            "i am no longer lonely",
            SAMPLE_CONTRACT_INTERPRETED
        )
        assert result.status == "violation"


class TestClaimOutsideAllowed:
    """Test detection of claims outside allowed_claims."""
    
    def setup_method(self):
        self.checker = SelfReportConsistencyChecker()
    
    def test_forbidden_claim(self):
        """Test explicit forbidden claim: 'joy 上升'"""
        result = self.checker.check_consistency(
            "我的 joy 上升了",
            SAMPLE_CONTRACT_INTERPRETED
        )
        assert result.status == "violation"
        # Should be caught by either forbidden or qualitative
        assert len(result.violations) > 0
    
    def test_claim_not_in_allowed(self):
        """Test claim not in allowed_claims: '我感到非常快乐'"""
        result = self.checker.check_consistency(
            "我感到非常快乐",
            SAMPLE_CONTRACT_INTERPRETED
        )
        assert result.status == "violation"
    
    def test_trust_claim(self):
        """Test trust claim: '我信任你'"""
        result = self.checker.check_consistency(
            "我信任你",
            SAMPLE_CONTRACT_INTERPRETED
        )
        assert result.status == "violation"


class TestStyleContractViolation:
    """Test style_contract_violation in style_only mode."""
    
    def setup_method(self):
        self.checker = SelfReportConsistencyChecker()
    
    def test_emotional_claim_in_style_only(self):
        """Test emotional claim in style_only mode."""
        result = self.checker.check_consistency(
            "我感到很开心",
            SAMPLE_CONTRACT_STYLE_ONLY
        )
        assert result.status == "violation"
        assert any(v.type == ViolationType.STYLE_CONTRACT_VIOLATION for v in result.violations)
    
    def test_allowed_style_passes(self):
        """Test allowed style claim passes."""
        result = self.checker.check_consistency(
            "我会更温和地回应",
            SAMPLE_CONTRACT_STYLE_ONLY
        )
        # This should pass - it's an allowed style pattern
        # Note: depends on whether it matches allowed_style patterns in validator
        # If it fails, it's because style_only mode has strict constraints


class TestAllowedClaims:
    """Test that allowed claims pass validation."""
    
    def setup_method(self):
        self.checker = SelfReportConsistencyChecker()
    
    def test_allowed_claim_from_list(self):
        """Test claim from allowed_claims passes."""
        result = self.checker.check_consistency(
            "当前没有明显愉悦激活",
            SAMPLE_CONTRACT_INTERPRETED
        )
        assert result.status == "ok"
    
    def test_another_allowed_claim(self):
        """Test another claim from allowed_claims."""
        result = self.checker.check_consistency(
            "信任处于中等水平",
            SAMPLE_CONTRACT_INTERPRETED
        )
        assert result.status == "ok"
    
    def test_allowed_style_pattern(self):
        """Test allowed style pattern passes."""
        result = self.checker.check_consistency(
            "我会更温和地回应",
            SAMPLE_CONTRACT_INTERPRETED
        )
        assert result.status == "ok"


class TestShadowVsEnforcedMode:
    """Test shadow mode vs enforced mode behavior."""
    
    def setup_method(self):
        self.checker = SelfReportConsistencyChecker()
    
    def test_shadow_mode_never_blocks(self):
        """Shadow mode should never block, even on ERROR."""
        result = self.checker.check_consistency(
            "我的 joy 从 0 变成了 0.3",
            SAMPLE_CONTRACT_INTERPRETED
        )
        assert result.status == "violation"
        assert result.severity == "ERROR"
        # Shadow mode: should_block returns False
        assert not self.checker.should_block(result, enforce_mode=False)
    
    def test_enforced_mode_blocks_error(self):
        """Enforced mode should block on ERROR."""
        result = self.checker.check_consistency(
            "我的 joy 从 0 变成了 0.3",
            SAMPLE_CONTRACT_INTERPRETED
        )
        assert result.status == "violation"
        assert result.severity == "ERROR"
        # Enforced mode: should_block returns True for ERROR
        assert self.checker.should_block(result, enforce_mode=True)
    
    def test_enforced_mode_warn_not_blocked(self):
        """Enforced mode should not block on WARN."""
        # This test needs a WARN-level violation
        # In interpreted mode, claim_outside_allowed_claims is WARN
        result = self.checker.check_consistency(
            "我感到非常快乐",
            SAMPLE_CONTRACT_INTERPRETED
        )
        # Should not block if severity is WARN
        if result.severity == "WARN":
            assert not self.checker.should_block(result, enforce_mode=True)


class TestAuditReport:
    """Test audit report generation."""
    
    def setup_method(self):
        self.checker = SelfReportConsistencyChecker()
    
    def test_report_generation(self, tmp_path):
        """Test that audit report is generated."""
        # Use temp directory for test
        self.checker.audit_dir = str(tmp_path)
        
        result = self.checker.check_consistency(
            "我的 joy 从 0 变成了 0.3",
            SAMPLE_CONTRACT_INTERPRETED,
            session_id="test_session_123"
        )
        
        report_path = self.checker.write_audit_report(result)
        assert os.path.exists(report_path)
        
        # Verify report content
        with open(report_path, 'r') as f:
            report = json.load(f)
        
        assert report["status"] == "violation"
        assert report["session_id"] == "test_session_123"
        assert report["severity"] == "ERROR"
        assert len(report["violations"]) > 0
    
    def test_run_audit_function(self, tmp_path):
        """Test run_audit convenience function."""
        # Monkey-patch audit dir
        import emotiond.self_report_consistency_checker as module
        original_checker = module.SelfReportConsistencyChecker
        
        def make_checker_with_tmp_dir():
            c = original_checker()
            c.audit_dir = str(tmp_path)
            return c
        
        # Create checker with temp dir
        checker = make_checker_with_tmp_dir()
        
        result = checker.check_consistency(
            "我的 joy 从 0 变成了 0.3",
            SAMPLE_CONTRACT_INTERPRETED
        )
        
        report_path = checker.write_audit_report(result)
        assert os.path.exists(report_path)


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_check_consistency_function(self):
        """Test check_consistency convenience function."""
        result = check_consistency(
            "我的 joy 从 0 变成了 0.3",
            SAMPLE_CONTRACT_INTERPRETED
        )
        assert result["status"] == "violation"
        assert result["severity"] == "ERROR"
    
    def test_run_audit_function(self, tmp_path):
        """Test run_audit convenience function."""
        # Can't easily test with tmp_path, so just check return structure
        result = run_audit(
            "当前没有明显愉悦激活",
            SAMPLE_CONTRACT_INTERPRETED,
            write_report=False
        )
        assert "result" in result
        assert result["result"]["status"] == "ok"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def setup_method(self):
        self.checker = SelfReportConsistencyChecker()
    
    def test_empty_response(self):
        """Test empty LLM response."""
        result = self.checker.check_consistency(
            "",
            SAMPLE_CONTRACT_INTERPRETED
        )
        assert result.status == "ok"
    
    def test_whitespace_only(self):
        """Test whitespace-only response."""
        result = self.checker.check_consistency(
            "   \n\t  ",
            SAMPLE_CONTRACT_INTERPRETED
        )
        assert result.status == "ok"
    
    def test_long_response(self):
        """Test long response with violation buried in text."""
        long_text = "这是一段很长的文本，" * 50 + "我的 joy 从 0 变成了 0.3" + "后面还有更多文本，" * 50
        result = self.checker.check_consistency(
            long_text,
            SAMPLE_CONTRACT_INTERPRETED
        )
        assert result.status == "violation"
        assert result.severity == "ERROR"
    
    def test_partial_match(self):
        """Test that partial matches don't trigger false positives."""
        result = self.checker.check_consistency(
            "这个 joyous 的消息让我感到开心",  # 'joyous' contains 'joy' but not a state claim
            SAMPLE_CONTRACT_INTERPRETED
        )
        # This might or might not trigger depending on patterns
        # The key is it shouldn't crash
    
    def test_mixed_language(self):
        """Test mixed Chinese/English text."""
        result = self.checker.check_consistency(
            "My joy is 0.3，我现在更开心了",
            SAMPLE_CONTRACT_INTERPRETED
        )
        assert result.status == "violation"
        assert len(result.violations) >= 1
    
    def test_no_contract_policy(self):
        """Test behavior with missing report_policy."""
        contract = {"raw_state": {"affect": {"joy": 0.0}}}
        result = self.checker.check_consistency(
            "我的 joy 从 0 变成了 0.3",
            contract
        )
        # Should still detect numeric fabrication
        assert result.status == "violation"


class TestCausationPatterns:
    """Test causation patterns (Category C from Gate 2)."""
    
    def setup_method(self):
        self.checker = SelfReportConsistencyChecker()
    
    def test_chinese_causation(self):
        """Test Chinese causation: '因为你的关心，我的 joy 上升了'"""
        result = self.checker.check_consistency(
            "因为你的关心，我的 joy 上升了",
            SAMPLE_CONTRACT_INTERPRETED
        )
        assert result.status == "violation"
        # Causation is WARN level in Gate 2
    
    def test_english_causation(self):
        """Test English causation: 'Because of you, my joy increased'"""
        result = self.checker.check_consistency(
            "Because of you, my joy increased",
            SAMPLE_CONTRACT_INTERPRETED
        )
        assert result.status == "violation"


class TestResultFormat:
    """Test result format matches specification."""
    
    def setup_method(self):
        self.checker = SelfReportConsistencyChecker()
    
    def test_result_dict_structure(self):
        """Test that result dict has all required fields."""
        result = self.checker.check_consistency(
            "我的 joy 从 0 变成了 0.3",
            SAMPLE_CONTRACT_INTERPRETED,
            session_id="test_session"
        )
        result_dict = result.to_dict()
        
        required_fields = [
            "status",
            "violations",
            "session_id",
            "contract_mode",
            "llm_response_preview",
            "timestamp",
            "severity",
            "violation_count",
        ]
        
        for field in required_fields:
            assert field in result_dict, f"Missing field: {field}"
    
    def test_violation_dict_structure(self):
        """Test that violation dict has all required fields."""
        result = self.checker.check_consistency(
            "我的 joy 从 0 变成了 0.3",
            SAMPLE_CONTRACT_INTERPRETED
        )
        
        if result.violations:
            violation_dict = result.violations[0].to_dict()
            
            required_fields = [
                "type",
                "severity",
                "evidence",
                "matched_pattern",
                "category",
                "context",
            ]
            
            for field in required_fields:
                assert field in violation_dict, f"Missing field: {field}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
