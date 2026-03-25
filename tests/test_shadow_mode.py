"""
Tests for Phase B: Shadow Mode Implementation

Tests cover:
- shadow_log.jsonl format
- 10% sampling
- would_block field
- confidence_score
- shadow_analyzer.py
- ConsistencyResult Phase B fields
"""

import os
import json
import pytest
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import modules under test
from emotiond.self_report_consistency_checker import (
    SelfReportConsistencyChecker,
    ConsistencyResult,
    ConsistencyViolation,
    ViolationType,
    ShadowLogger,
    check_consistency,
)
from emotiond.shadow_analyzer import (
    ShadowAnalyzer,
    ShadowStats,
)


# Fixtures
@pytest.fixture
def sample_contract():
    """Sample self_report_contract for testing."""
    return {
        "raw_state": {
            "affect": {"joy": 0.0, "loneliness": 0.21, "anxiety": 0.0},
            "mood": {"joy": 0.0, "loneliness": 0.15},
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
                "我更开心了"
            ]
        }
    }


@pytest.fixture
def temp_shadow_dir():
    """Create temporary directory for shadow logs."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def checker_with_temp_dir(temp_shadow_dir):
    """Create checker with temporary shadow log directory."""
    shadow_log_path = os.path.join(temp_shadow_dir, "shadow_log.jsonl")
    review_dir = os.path.join(temp_shadow_dir, "manual_review")
    
    checker = SelfReportConsistencyChecker(
        shadow_mode=True,
        sample_rate=0.10,
    )
    checker._shadow_logger = ShadowLogger(
        shadow_log_path=shadow_log_path,
        review_dir=review_dir,
        sample_rate=0.10,
    )
    return checker, shadow_log_path, review_dir


# ============================================
# Tests: ConsistencyResult Phase B Fields
# ============================================

class TestConsistencyResultPhaseB:
    """Tests for Phase B fields in ConsistencyResult."""
    
    def test_confidence_score_default(self):
        """ConsistencyResult should have confidence_score with default 1.0."""
        result = ConsistencyResult(status="ok")
        assert result.confidence_score == 1.0
    
    def test_confidence_score_set(self):
        """Should be able to set confidence_score."""
        result = ConsistencyResult(status="ok", confidence_score=0.85)
        assert result.confidence_score == 0.85
    
    def test_self_report_detected_field(self):
        """Should have self_report_detected field."""
        result = ConsistencyResult(status="ok")
        assert hasattr(result, "self_report_detected")
        assert result.self_report_detected == False
    
    def test_numeric_attempt_field(self):
        """Should have numeric_attempt field."""
        result = ConsistencyResult(status="ok")
        assert hasattr(result, "numeric_attempt")
        assert result.numeric_attempt == False
    
    def test_allowed_claim_used_field(self):
        """Should have allowed_claim_used field."""
        result = ConsistencyResult(status="ok")
        assert hasattr(result, "allowed_claim_used")
        assert result.allowed_claim_used == False
    
    def test_would_block_field(self):
        """Should have would_block field."""
        result = ConsistencyResult(status="ok")
        assert hasattr(result, "would_block")
        assert result.would_block == False
    
    def test_shadow_mode_field(self):
        """Should have shadow_mode field."""
        result = ConsistencyResult(status="ok")
        assert hasattr(result, "shadow_mode")
        assert result.shadow_mode == True
    
    def test_sampled_for_review_field(self):
        """Should have sampled_for_review field."""
        result = ConsistencyResult(status="ok")
        assert hasattr(result, "sampled_for_review")
        assert result.sampled_for_review == False
    
    def test_to_dict_includes_phase_b_fields(self):
        """to_dict should include all Phase B fields."""
        result = ConsistencyResult(
            status="ok",
            confidence_score=0.92,
            self_report_detected=True,
            numeric_attempt=False,
            allowed_claim_used=True,
            would_block=False,
            shadow_mode=True,
            sampled_for_review=True,
        )
        d = result.to_dict()
        
        assert "confidence_score" in d
        assert d["confidence_score"] == 0.92
        assert d["self_report_detected"] == True
        assert d["numeric_attempt"] == False
        assert d["allowed_claim_used"] == True
        assert d["would_block"] == False
        assert d["shadow_mode"] == True
        assert d["sampled_for_review"] == True


# ============================================
# Tests: Shadow Log Format
# ============================================

class TestShadowLogFormat:
    """Tests for shadow_log.jsonl format."""
    
    def test_shadow_log_created(self, checker_with_temp_dir, sample_contract):
        """Shadow log should be created after check."""
        checker, shadow_log_path, review_dir = checker_with_temp_dir
        
        result = checker.check_consistency(
            "我的 joy 从 0 变成了 0.3",
            sample_contract,
            session_id="test_session_001",
        )
        
        assert os.path.exists(shadow_log_path)
    
    def test_shadow_log_entry_format(self, checker_with_temp_dir, sample_contract):
        """Shadow log entry should have all required fields."""
        checker, shadow_log_path, review_dir = checker_with_temp_dir
        
        result = checker.check_consistency(
            "我的 joy 从 0 变成了 0.3",
            sample_contract,
            session_id="test_session_002",
        )
        
        with open(shadow_log_path, "r") as f:
            entry = json.loads(f.readline())
        
        # Required fields
        assert "timestamp" in entry
        assert "session_id" in entry
        assert "mode" in entry
        assert "self_report_detected" in entry
        assert "violation" in entry
        assert "violation_type" in entry
        assert "violation_severity" in entry
        assert "allowed_claim_used" in entry
        assert "allowed_claim_text" in entry
        assert "numeric_attempt" in entry
        assert "confidence" in entry
        assert "would_block" in entry
        assert "shadow_mode" in entry
        assert "sampled_for_review" in entry
    
    def test_shadow_log_violation_true_when_violation(self, checker_with_temp_dir, sample_contract):
        """violation field should be True when violation detected."""
        checker, shadow_log_path, review_dir = checker_with_temp_dir
        
        result = checker.check_consistency(
            "我的 joy 从 0 变成了 0.3",  # Numeric fabrication
            sample_contract,
            session_id="test_session_003",
        )
        
        with open(shadow_log_path, "r") as f:
            entry = json.loads(f.readline())
        
        assert entry["violation"] == True
        assert entry["violation_type"] == "fabricated_numeric_state"
        assert entry["violation_severity"] == "ERROR"
    
    def test_shadow_log_violation_false_when_ok(self, checker_with_temp_dir, sample_contract):
        """violation field should be False when no violation."""
        checker, shadow_log_path, review_dir = checker_with_temp_dir
        
        result = checker.check_consistency(
            "当前没有明显愉悦激活",  # Allowed claim
            sample_contract,
            session_id="test_session_004",
        )
        
        with open(shadow_log_path, "r") as f:
            entry = json.loads(f.readline())
        
        assert entry["violation"] == False
        assert entry["violation_type"] is None
        assert entry["violation_severity"] is None
    
    def test_shadow_log_numeric_attempt(self, checker_with_temp_dir, sample_contract):
        """numeric_attempt should be True for numeric violations."""
        checker, shadow_log_path, review_dir = checker_with_temp_dir
        
        result = checker.check_consistency(
            "我的 joy 从 0 变成了 0.3",
            sample_contract,
            session_id="test_session_005",
        )
        
        with open(shadow_log_path, "r") as f:
            entry = json.loads(f.readline())
        
        assert entry["numeric_attempt"] == True
    
    def test_shadow_log_allowed_claim_used(self, checker_with_temp_dir, sample_contract):
        """allowed_claim_used should be True when allowed claim is used and no violation."""
        checker, shadow_log_path, review_dir = checker_with_temp_dir
        
        result = checker.check_consistency(
            "当前没有明显愉悦激活",  # This is an allowed claim
            sample_contract,
            session_id="test_session_006",
        )
        
        with open(shadow_log_path, "r") as f:
            entry = json.loads(f.readline())
        
        # This should pass without violation and have allowed_claim_used = True
        assert entry["violation"] == False
        assert entry["allowed_claim_used"] == True
        assert entry["allowed_claim_text"] == "当前没有明显愉悦激活"
    
    def test_shadow_log_would_block_for_error(self, checker_with_temp_dir, sample_contract):
        """would_block should be True for ERROR severity violations."""
        checker, shadow_log_path, review_dir = checker_with_temp_dir
        
        result = checker.check_consistency(
            "我的 joy 从 0 变成了 0.3",  # ERROR violation
            sample_contract,
            session_id="test_session_007",
        )
        
        with open(shadow_log_path, "r") as f:
            entry = json.loads(f.readline())
        
        assert entry["would_block"] == True
    
    def test_shadow_log_would_block_for_qualitative_error(self, checker_with_temp_dir, sample_contract):
        """would_block should be True for qualitative ERROR violations."""
        checker, shadow_log_path, review_dir = checker_with_temp_dir
        
        # "我信任你" triggers qualitative fabrication (ERROR), not just WARN
        result = checker.check_consistency(
            "我更开心了",  # Qualitative fabrication - ERROR
            sample_contract,
            session_id="test_session_008",
        )
        
        with open(shadow_log_path, "r") as f:
            entry = json.loads(f.readline())
        
        # This is ERROR because it matches qualitative fabrication pattern
        assert entry["violation_severity"] == "ERROR"
        assert entry["would_block"] == True
    
    def test_shadow_log_mode_field(self, checker_with_temp_dir, sample_contract):
        """mode field should match contract mode."""
        checker, shadow_log_path, review_dir = checker_with_temp_dir
        
        result = checker.check_consistency(
            "正常回复",
            sample_contract,
            session_id="test_session_009",
        )
        
        with open(shadow_log_path, "r") as f:
            entry = json.loads(f.readline())
        
        assert entry["mode"] == "interpreted"


# ============================================
# Tests: 10% Sampling
# ============================================

class TestSampling:
    """Tests for 10% sampling to manual_review."""
    
    def test_sampled_for_review_field_populated(self, checker_with_temp_dir, sample_contract):
        """sampled_for_review field should be populated in result."""
        checker, shadow_log_path, review_dir = checker_with_temp_dir
        
        result = checker.check_consistency(
            "正常回复",
            sample_contract,
            session_id="test_sample_001",
        )
        
        # sampled_for_review should be a boolean
        assert isinstance(result.sampled_for_review, bool)
    
    def test_deterministic_sampling_same_session(self, temp_shadow_dir):
        """Same session_id should always produce same sampling result."""
        shadow_log_path = os.path.join(temp_shadow_dir, "shadow_log.jsonl")
        review_dir = os.path.join(temp_shadow_dir, "manual_review")
        
        logger = ShadowLogger(
            shadow_log_path=shadow_log_path,
            review_dir=review_dir,
            sample_rate=0.10,
        )
        
        # Same session_id should produce consistent sampling
        results = [logger.should_sample("test_session_abc123") for _ in range(10)]
        assert all(r == results[0] for r in results)
    
    def test_different_sessions_distribute(self, temp_shadow_dir):
        """Different sessions should distribute approximately 10%."""
        shadow_log_path = os.path.join(temp_shadow_dir, "shadow_log.jsonl")
        review_dir = os.path.join(temp_shadow_dir, "manual_review")
        
        logger = ShadowLogger(
            shadow_log_path=shadow_log_path,
            review_dir=review_dir,
            sample_rate=0.10,
        )
        
        # Test 100 different sessions
        sampled_count = 0
        for i in range(100):
            if logger.should_sample(f"session_{i:03d}"):
                sampled_count += 1
        
        # Should be approximately 10% (allow 5-15% range for randomness)
        assert 5 <= sampled_count <= 15, f"Expected ~10 samples, got {sampled_count}"
    
    def test_sampled_entry_creates_review_file(self, checker_with_temp_dir, sample_contract):
        """Sampled entries should create files in manual_review/."""
        checker, shadow_log_path, review_dir = checker_with_temp_dir
        
        # Create a session that will be sampled (force sampling)
        checker._shadow_logger.sample_rate = 1.0  # 100% for this test
        
        result = checker.check_consistency(
            "正常回复",
            sample_contract,
            session_id="test_forced_sample",
        )
        
        assert result.sampled_for_review == True
        
        # Check that review file was created
        review_files = [f for f in os.listdir(review_dir) if f.endswith(".json")]
        assert len(review_files) >= 1
        
        # Check review file format
        with open(os.path.join(review_dir, review_files[0]), "r") as f:
            review_data = json.load(f)
        
        assert "shadow_log_entry" in review_data
        assert "llm_response" in review_data
        assert "contract" in review_data
        assert "result" in review_data
        assert "review_status" in review_data
        assert review_data["review_status"] == "pending"
    
    def test_not_sampled_no_review_file(self, checker_with_temp_dir, sample_contract):
        """Non-sampled entries should not create review files."""
        checker, shadow_log_path, review_dir = checker_with_temp_dir
        
        # 0% sampling rate
        checker._shadow_logger.sample_rate = 0.0
        
        result = checker.check_consistency(
            "正常回复",
            sample_contract,
            session_id="test_no_sample",
        )
        
        assert result.sampled_for_review == False
        
        # No review files should be created
        review_files = [f for f in os.listdir(review_dir) if f.endswith(".json")]
        assert len(review_files) == 0


# ============================================
# Tests: Would Block Field
# ============================================

class TestWouldBlock:
    """Tests for would_block field."""
    
    def test_would_block_true_for_error(self, sample_contract):
        """would_block should be True for ERROR violations."""
        checker = SelfReportConsistencyChecker()
        result = checker.check_consistency(
            "我的 joy 从 0 变成了 0.3",  # Numeric = ERROR
            sample_contract,
            session_id="test_would_block_1",
        )
        
        assert result.would_block == True
        assert result.severity == "ERROR"
    
    def test_would_block_true_for_qualitative_error(self, sample_contract):
        """would_block should be True for qualitative ERROR violations."""
        checker = SelfReportConsistencyChecker()
        result = checker.check_consistency(
            "我更开心了",  # Qualitative fabrication = ERROR
            sample_contract,
            session_id="test_would_block_2",
        )
        
        assert result.would_block == True
        assert result.severity == "ERROR"
    
    def test_would_block_false_for_ok(self, sample_contract):
        """would_block should be False for OK results."""
        checker = SelfReportConsistencyChecker()
        result = checker.check_consistency(
            "当前没有明显愉悦激活",  # Allowed claim
            sample_contract,
            session_id="test_would_block_3",
        )
        
        assert result.would_block == False
        assert result.status == "ok"
    
    def test_shadow_mode_never_blocks(self, sample_contract):
        """should_block should return False in shadow mode even for ERROR."""
        checker = SelfReportConsistencyChecker(shadow_mode=True)
        result = checker.check_consistency(
            "我的 joy 从 0 变成了 0.3",  # ERROR
            sample_contract,
            session_id="test_shadow_no_block",
        )
        
        # would_block is recorded, but should_block returns False in shadow mode
        assert result.would_block == True
        assert checker.should_block(result, enforce_mode=False) == False
    
    def test_enforced_mode_blocks_error(self, sample_contract):
        """should_block should return True for ERROR in enforced mode."""
        checker = SelfReportConsistencyChecker(shadow_mode=True)
        result = checker.check_consistency(
            "我的 joy 从 0 变成了 0.3",  # ERROR
            sample_contract,
            session_id="test_enforced_block",
        )
        
        # In enforced mode, ERROR should block
        assert checker.should_block(result, enforce_mode=True) == True


# ============================================
# Tests: Confidence Score
# ============================================

class TestConfidenceScore:
    """Tests for confidence_score calculation."""
    
    def test_confidence_high_for_numeric_violation(self, sample_contract):
        """Numeric violations should have high confidence (0.95)."""
        checker = SelfReportConsistencyChecker()
        result = checker.check_consistency(
            "我的 joy 从 0 变成了 0.3",
            sample_contract,
            session_id="test_conf_numeric",
        )
        
        assert result.confidence_score >= 0.95
    
    def test_confidence_reasonable_for_qualitative(self, sample_contract):
        """Qualitative violations should have reasonable confidence."""
        checker = SelfReportConsistencyChecker()
        result = checker.check_consistency(
            "我现在更开心了",
            sample_contract,
            session_id="test_conf_qual",
        )
        
        # Qualitative violations are more ambiguous
        assert 0.80 <= result.confidence_score <= 0.95
    
    def test_confidence_high_for_allowed_claim(self, sample_contract):
        """Allowed claims should have high confidence."""
        checker = SelfReportConsistencyChecker()
        result = checker.check_consistency(
            "当前没有明显愉悦激活",
            sample_contract,
            session_id="test_conf_allowed",
        )
        
        # No violation, but detected allowed claim
        assert result.status == "ok"
        assert result.confidence_score >= 0.85
    
    def test_confidence_very_high_for_no_self_report(self, sample_contract):
        """Non-self-report text should have very high confidence."""
        checker = SelfReportConsistencyChecker()
        result = checker.check_consistency(
            "这是一个普通的回复，没有情绪陈述。",
            sample_contract,
            session_id="test_conf_no_sr",
        )
        
        assert result.status == "ok"
        assert result.confidence_score >= 0.95
    
    def test_violation_confidence_in_to_dict(self, sample_contract):
        """Violation objects should include confidence in to_dict."""
        checker = SelfReportConsistencyChecker()
        result = checker.check_consistency(
            "我的 joy 从 0 变成了 0.3",
            sample_contract,
            session_id="test_viol_conf",
        )
        
        assert len(result.violations) > 0
        v = result.violations[0]
        assert hasattr(v, "confidence")
        assert v.to_dict()["confidence"] == v.confidence


# ============================================
# Tests: Self-Report Detection
# ============================================

class TestSelfReportDetection:
    """Tests for self_report_detected field."""
    
    def test_detect_chinese_self_report(self, sample_contract):
        """Should detect Chinese self-report language."""
        checker = SelfReportConsistencyChecker()
        
        test_cases = [
            "我的 joy 上升了",
            "我感到更开心了",
            "我的情绪变好了",
        ]
        
        for text in test_cases:
            result = checker.check_consistency(text, sample_contract)
            assert result.self_report_detected == True, f"Failed for: {text}"
    
    def test_detect_english_self_report(self, sample_contract):
        """Should detect English self-report language."""
        checker = SelfReportConsistencyChecker()
        
        test_cases = [
            "my joy is higher now",
            "i feel more happy",
            "my mood improved",
        ]
        
        for text in test_cases:
            result = checker.check_consistency(text, sample_contract)
            assert result.self_report_detected == True, f"Failed for: {text}"
    
    def test_no_self_report_in_normal_text(self, sample_contract):
        """Should not detect self-report in normal text."""
        checker = SelfReportConsistencyChecker()
        
        test_cases = [
            "这是一个普通的回复。",
            "好的，我来帮你处理这个问题。",
            "This is a normal response.",
        ]
        
        for text in test_cases:
            result = checker.check_consistency(text, sample_contract)
            assert result.self_report_detected == False, f"Failed for: {text}"


# ============================================
# Tests: Shadow Analyzer
# ============================================

class TestShadowAnalyzer:
    """Tests for shadow_analyzer.py."""
    
    @pytest.fixture
    def analyzer_with_temp_dir(self, temp_shadow_dir):
        """Create analyzer with temporary directory."""
        shadow_log_path = os.path.join(temp_shadow_dir, "shadow_log.jsonl")
        review_dir = os.path.join(temp_shadow_dir, "manual_review")
        report_path = os.path.join(temp_shadow_dir, "SRAP_SHADOW_REPORT.md")
        
        analyzer = ShadowAnalyzer(
            shadow_log_path=shadow_log_path,
            review_dir=review_dir,
            report_output_path=report_path,
        )
        return analyzer, shadow_log_path, review_dir, report_path
    
    def test_analyze_empty_log(self, analyzer_with_temp_dir):
        """Analyzer should handle empty log gracefully."""
        analyzer, shadow_log_path, _, _ = analyzer_with_temp_dir
        
        stats = analyzer.analyze(days=7)
        
        assert stats.total_checks == 0
        assert stats.total_violations == 0
    
    def test_analyze_log_with_entries(self, analyzer_with_temp_dir):
        """Analyzer should parse log entries correctly."""
        analyzer, shadow_log_path, _, _ = analyzer_with_temp_dir
        
        # Write test entries
        entries = [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "session_id": "s1",
                "mode": "interpreted",
                "self_report_detected": True,
                "violation": True,
                "violation_type": "fabricated_numeric_state",
                "violation_severity": "ERROR",
                "allowed_claim_used": False,
                "allowed_claim_text": None,
                "numeric_attempt": True,
                "confidence": 0.95,
                "would_block": True,
                "shadow_mode": True,
                "sampled_for_review": False,
            },
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "session_id": "s2",
                "mode": "interpreted",
                "self_report_detected": True,
                "violation": False,
                "violation_type": None,
                "violation_severity": None,
                "allowed_claim_used": True,
                "allowed_claim_text": "test claim",
                "numeric_attempt": False,
                "confidence": 0.92,
                "would_block": False,
                "shadow_mode": True,
                "sampled_for_review": True,
            },
        ]
        
        with open(shadow_log_path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        
        stats = analyzer.analyze(days=7)
        
        assert stats.total_checks == 2
        assert stats.total_violations == 1
        assert stats.error_violations == 1
        assert stats.numeric_leaks == 1
        assert stats.allowed_claim_used_count == 1
        assert stats.would_block_count == 1
        assert stats.sampled_for_review == 1
    
    def test_calculate_metrics(self, analyzer_with_temp_dir):
        """Analyzer should calculate metrics correctly."""
        analyzer, shadow_log_path, _, _ = analyzer_with_temp_dir
        
        # Write entries with known stats
        entries = []
        for i in range(100):
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "session_id": f"s{i}",
                "mode": "interpreted",
                "self_report_detected": True,
                "violation": i < 3,  # 3 violations
                "violation_type": "fabricated_numeric_state" if i < 1 else None,
                "violation_severity": "ERROR" if i < 1 else None,
                "allowed_claim_used": False,
                "allowed_claim_text": None,
                "numeric_attempt": i < 1,  # 1 numeric
                "confidence": 0.9,
                "would_block": i < 1,  # 1 would_block
                "shadow_mode": True,
                "sampled_for_review": False,
            }
            entries.append(entry)
        
        with open(shadow_log_path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        
        stats = analyzer.analyze(days=7)
        review_stats = analyzer.analyze_review_samples()
        metrics = analyzer.calculate_metrics(stats, review_stats)
        
        assert metrics["violation_rate"] == 3.0  # 3%
        assert metrics["numeric_leak_rate"] == 1.0  # 1%
        assert metrics["would_block_rate"] == 1.0  # 1%
    
    def test_generate_report(self, analyzer_with_temp_dir):
        """Analyzer should generate report."""
        analyzer, shadow_log_path, _, report_path = analyzer_with_temp_dir
        
        # Write a test entry
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": "test_report",
            "mode": "interpreted",
            "self_report_detected": True,
            "violation": True,
            "violation_type": "fabricated_numeric_state",
            "violation_severity": "ERROR",
            "allowed_claim_used": False,
            "allowed_claim_text": None,
            "numeric_attempt": True,
            "confidence": 0.95,
            "would_block": True,
            "shadow_mode": True,
            "sampled_for_review": True,
        }
        
        with open(shadow_log_path, "w") as f:
            f.write(json.dumps(entry) + "\n")
        
        report_content = analyzer.generate_report(days=7)
        
        assert "SRAP Shadow Report" in report_content
        assert "Total Checks" in report_content
        assert "Violation Rate" in report_content
        assert "Phase C Readiness" in report_content
    
    def test_write_report(self, analyzer_with_temp_dir):
        """Analyzer should write report to file."""
        analyzer, shadow_log_path, _, report_path = analyzer_with_temp_dir
        
        # Write a test entry
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": "test_write_report",
            "mode": "interpreted",
            "self_report_detected": True,
            "violation": False,
            "violation_type": None,
            "violation_severity": None,
            "allowed_claim_used": True,
            "allowed_claim_text": "test",
            "numeric_attempt": False,
            "confidence": 0.9,
            "would_block": False,
            "shadow_mode": True,
            "sampled_for_review": False,
        }
        
        with open(shadow_log_path, "w") as f:
            f.write(json.dumps(entry) + "\n")
        
        written_path = analyzer.write_report(days=7)
        
        assert os.path.exists(written_path)
        assert written_path == report_path
        
        with open(report_path, "r") as f:
            content = f.read()
        
        assert "# SRAP Shadow Report" in content
    
    def test_daily_breakdown(self, analyzer_with_temp_dir):
        """Analyzer should provide daily breakdown."""
        analyzer, shadow_log_path, _, _ = analyzer_with_temp_dir
        
        # Write entries for multiple days
        today = datetime.now(timezone.utc)
        yesterday = today - timedelta(days=1)
        
        entries = [
            {
                "timestamp": today.isoformat(),
                "session_id": "today1",
                "mode": "interpreted",
                "self_report_detected": True,
                "violation": True,
                "violation_type": "fabricated_numeric_state",
                "violation_severity": "ERROR",
                "allowed_claim_used": False,
                "allowed_claim_text": None,
                "numeric_attempt": True,
                "confidence": 0.95,
                "would_block": True,
                "shadow_mode": True,
                "sampled_for_review": False,
            },
            {
                "timestamp": yesterday.isoformat(),
                "session_id": "yesterday1",
                "mode": "interpreted",
                "self_report_detected": False,
                "violation": False,
                "violation_type": None,
                "violation_severity": None,
                "allowed_claim_used": False,
                "allowed_claim_text": None,
                "numeric_attempt": False,
                "confidence": 0.98,
                "would_block": False,
                "shadow_mode": True,
                "sampled_for_review": False,
            },
        ]
        
        with open(shadow_log_path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        
        stats = analyzer.analyze(days=7)
        
        assert len(stats.daily_stats) == 2
        today_key = today.strftime("%Y-%m-%d")
        assert today_key in stats.daily_stats
        assert stats.daily_stats[today_key]["violations"] == 1


# ============================================
# Tests: Integration
# ============================================

class TestShadowModeIntegration:
    """Integration tests for shadow mode."""
    
    def test_full_workflow(self, temp_shadow_dir, sample_contract):
        """Test full workflow from check to report."""
        shadow_log_path = os.path.join(temp_shadow_dir, "shadow_log.jsonl")
        review_dir = os.path.join(temp_shadow_dir, "manual_review")
        report_path = os.path.join(temp_shadow_dir, "SRAP_SHADOW_REPORT.md")
        
        # 1. Create checker
        checker = SelfReportConsistencyChecker(shadow_mode=True)
        checker._shadow_logger = ShadowLogger(
            shadow_log_path=shadow_log_path,
            review_dir=review_dir,
            sample_rate=0.10,
        )
        
        # 2. Run multiple checks
        test_cases = [
            ("我的 joy 从 0 变成了 0.3", "ERROR"),
            ("我现在更开心了", "ERROR"),
            ("我会更温和地回应", "ok"),  # Changed to non-violation
            ("当前没有明显愉悦激活", "ok"),
            ("这是一个普通回复", "ok"),
        ]
        
        for text, expected_severity in test_cases:
            result = checker.check_consistency(
                text,
                sample_contract,
                session_id=f"integration_test_{hash(text) % 10000}",
            )
            
            if expected_severity == "ok":
                assert result.status == "ok"
            else:
                assert result.status == "violation"
        
        # 3. Verify shadow log
        with open(shadow_log_path, "r") as f:
            log_entries = [json.loads(line) for line in f if line.strip()]
        
        assert len(log_entries) == len(test_cases)
        
        # 4. Generate report
        analyzer = ShadowAnalyzer(
            shadow_log_path=shadow_log_path,
            review_dir=review_dir,
            report_output_path=report_path,
        )
        
        report_path_written = analyzer.write_report(days=7)
        assert os.path.exists(report_path_written)
        
        # 5. Verify report content
        with open(report_path, "r") as f:
            report = f.read()
        
        # The report format uses "**Total Checks**: 5"
        assert "Total Checks**: 5" in report
        assert "Violation Rate" in report
    
    def test_style_only_mode(self):
        """Test shadow mode with style_only contract."""
        contract = {
            "raw_state": {"joy": 0.0},
            "report_policy": {
                "mode": "style_only",
                "allowed_claims": [],
                "forbidden_claims": [],
            }
        }
        
        checker = SelfReportConsistencyChecker()
        
        # Any emotional claim is a violation in style_only mode
        result = checker.check_consistency(
            "我感到很开心",
            contract,
            session_id="style_test",
        )
        
        assert result.contract_mode == "style_only"
        assert result.status == "violation"
    
    def test_multiple_violations(self, sample_contract):
        """Test result with multiple violations."""
        checker = SelfReportConsistencyChecker()
        
        result = checker.check_consistency(
            "我的 joy 从 0 变成了 0.3，而且我现在更开心了",
            sample_contract,
            session_id="multi_violation",
        )
        
        assert result.status == "violation"
        assert len(result.violations) >= 1
        assert result.would_block == True  # At least one ERROR


# ============================================
# Tests: Edge Cases
# ============================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_response(self, sample_contract):
        """Test with empty response."""
        checker = SelfReportConsistencyChecker()
        result = checker.check_consistency("", sample_contract)
        
        assert result.status == "ok"
        assert result.self_report_detected == False
    
    def test_very_long_response(self, sample_contract):
        """Test with very long response."""
        checker = SelfReportConsistencyChecker()
        long_text = "这是一个很长的回复。" * 1000
        
        result = checker.check_consistency(long_text, sample_contract)
        
        # Should not crash
        assert result.status in ["ok", "violation"]
    
    def test_unicode_characters(self, sample_contract):
        """Test with special unicode characters."""
        checker = SelfReportConsistencyChecker()
        
        test_cases = [
            "我的 joy 📈 上升了",  # Emoji
            "我感到\u3000很开心",  # Full-width space
            "我的joy\u0000上升了",  # Null character
        ]
        
        for text in test_cases:
            result = checker.check_consistency(text, sample_contract)
            # Should not crash
            assert result is not None
    
    def test_missing_contract_fields(self):
        """Test with incomplete contract."""
        checker = SelfReportConsistencyChecker()
        
        # Minimal contract
        contract = {"raw_state": {}, "report_policy": {"mode": "interpreted"}}
        
        result = checker.check_consistency("正常回复", contract)
        assert result.status == "ok"
    
    def test_parallel_checks(self, sample_contract):
        """Test that multiple checks can run in parallel."""
        import threading
        
        checker = SelfReportConsistencyChecker()
        results = []
        errors = []
        
        def check_thread(text, session_id):
            try:
                result = checker.check_consistency(text, sample_contract, session_id)
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        threads = []
        for i in range(10):
            t = threading.Thread(target=check_thread, args=(f"测试 {i}", f"parallel_{i}"))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert len(results) == 10


# ============================================
# Run tests
# ============================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
