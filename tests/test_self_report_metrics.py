"""
Tests for Self-Report Metrics System (Phase A.3)

Tests cover:
- 5 core fields: total_self_reports, flagged_count, confirmed_true_violation, confirmed_false_positive, suspected_false_negative
- JSONL logging format
- Windowed statistics calculation
- FP/FN rate calculation
- Integration with consistency checker
- Shadow mode vs enforced mode
"""

import pytest
import json
import os
import tempfile
from datetime import datetime, timezone, timedelta

from emotiond.self_report_metrics import (
    SelfReportMetrics,
    MetricsRecord,
    MetricsStats,
    ConfirmationStatus,
    record_check,
    get_metrics,
)

from emotiond.self_report_consistency_checker import (
    SelfReportConsistencyChecker,
    ConsistencyResult,
    ConsistencyViolation,
    ViolationType,
)


# Sample contracts for testing
SAMPLE_CONTRACT = {
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


class TestMetricsRecord:
    """Test MetricsRecord dataclass."""
    
    def test_record_creation(self):
        """Test creating a MetricsRecord."""
        record = MetricsRecord(
            timestamp="2024-01-01T00:00:00Z",
            session_id="test_123",
            status="violation",
            severity="ERROR",
            violation_count=2,
            violation_types=["fabricated_numeric_state", "fabricated_qualitative_state"],
            confirmation_status=ConfirmationStatus.PENDING.value,
        )
        assert record.timestamp == "2024-01-01T00:00:00Z"
        assert record.status == "violation"
        assert record.violation_count == 2
    
    def test_record_to_dict(self):
        """Test converting record to dict."""
        record = MetricsRecord(
            timestamp="2024-01-01T00:00:00Z",
            session_id="test_123",
            status="violation",
            severity="ERROR",
            violation_count=1,
            violation_types=["fabricated_numeric_state"],
        )
        d = record.to_dict()
        assert d["timestamp"] == "2024-01-01T00:00:00Z"
        assert d["status"] == "violation"
        assert d["violation_count"] == 1
    
    def test_record_from_dict(self):
        """Test creating record from dict."""
        data = {
            "timestamp": "2024-01-01T00:00:00Z",
            "session_id": "test_456",
            "status": "ok",
            "severity": "ok",
            "violation_count": 0,
            "violation_types": [],
            "confirmation_status": "pending",
        }
        record = MetricsRecord.from_dict(data)
        assert record.timestamp == "2024-01-01T00:00:00Z"
        assert record.status == "ok"
        assert record.violation_count == 0


class TestMetricsStats:
    """Test MetricsStats dataclass with 5 core fields."""
    
    def test_stats_defaults(self):
        """Test default values for 5 core fields."""
        stats = MetricsStats()
        assert stats.total_self_reports == 0
        assert stats.flagged_count == 0
        assert stats.confirmed_true_violation == 0
        assert stats.confirmed_false_positive == 0
        assert stats.suspected_false_negative == 0
    
    def test_stats_to_dict(self):
        """Test stats to dict conversion."""
        stats = MetricsStats(
            total_self_reports=100,
            flagged_count=20,
            confirmed_true_violation=15,
            confirmed_false_positive=3,
            suspected_false_negative=2,
            pending_review=5,
        )
        d = stats.to_dict()
        assert d["total_self_reports"] == 100
        assert d["flagged_count"] == 20
        assert d["confirmed_true_violation"] == 15
        assert d["confirmed_false_positive"] == 3
        assert d["suspected_false_negative"] == 2


class TestSelfReportMetrics:
    """Test SelfReportMetrics class."""
    
    def test_init_with_temp_path(self, tmp_path):
        """Test initialization with temp path."""
        log_path = str(tmp_path / "test_metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        assert metrics.log_path == log_path
    
    def test_record_check_ok(self, tmp_path):
        """Test recording an OK check."""
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        
        # Create a mock result
        result = ConsistencyResult(
            status="ok",
            violations=[],
            session_id="test_session",
            severity="ok",
        )
        
        record_id = metrics.record_check(result, session_id="test_session")
        assert record_id is not None
        
        # Verify file exists
        assert os.path.exists(log_path)
        
        # Read and verify
        with open(log_path, 'r') as f:
            data = json.loads(f.readline())
        
        assert data["status"] == "ok"
        assert data["violation_count"] == 0
    
    def test_record_check_violation(self, tmp_path):
        """Test recording a violation check."""
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        
        # Create violation result
        violation = ConsistencyViolation(
            type=ViolationType.FABRICATED_NUMERIC_STATE,
            severity="ERROR",
            evidence="joy 从 0 变成了 0.3",
            matched_pattern="numeric_change",
        )
        result = ConsistencyResult(
            status="violation",
            violations=[violation],
            session_id="test_violation",
            severity="ERROR",
        )
        
        record_id = metrics.record_check(result, session_id="test_violation")
        
        # Verify
        with open(log_path, 'r') as f:
            data = json.loads(f.readline())
        
        assert data["status"] == "violation"
        assert data["severity"] == "ERROR"
        assert data["violation_count"] == 1
        assert "fabricated_numeric_state" in data["violation_types"]
    
    def test_record_check_with_confirmation(self, tmp_path):
        """Test recording with confirmation status."""
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        
        violation = ConsistencyViolation(
            type=ViolationType.FABRICATED_NUMERIC_STATE,
            severity="ERROR",
            evidence="joy 上升到 0.5",
            matched_pattern="numeric_target",
        )
        result = ConsistencyResult(
            status="violation",
            violations=[violation],
            severity="ERROR",
        )
        
        # Record with FALSE_POSITIVE confirmation
        record_id = metrics.record_check(
            result,
            confirmation_status=ConfirmationStatus.FALSE_POSITIVE.value,
        )
        
        with open(log_path, 'r') as f:
            data = json.loads(f.readline())
        
        assert data["confirmation_status"] == "false_positive"
        assert data["confirmed_at"] is not None
    
    def test_get_stats_empty(self, tmp_path):
        """Test get_stats with no records."""
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        
        stats = metrics.get_stats(window_hours=24)
        assert stats.total_self_reports == 0
        assert stats.flagged_count == 0
    
    def test_get_stats_with_records(self, tmp_path):
        """Test get_stats with multiple records."""
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        
        # Record several checks
        # 1. OK
        ok_result = ConsistencyResult(status="ok", violations=[], severity="ok")
        metrics.record_check(ok_result, session_id="s1")
        
        # 2. Violation - TRUE_VIOLATION
        v_result = ConsistencyResult(
            status="violation",
            violations=[ConsistencyViolation(
                type=ViolationType.FABRICATED_NUMERIC_STATE,
                severity="ERROR",
                evidence="test",
                matched_pattern="test",
            )],
            severity="ERROR",
        )
        metrics.record_check(v_result, confirmation_status=ConfirmationStatus.TRUE_VIOLATION.value)
        
        # 3. Violation - FALSE_POSITIVE
        metrics.record_check(v_result, confirmation_status=ConfirmationStatus.FALSE_POSITIVE.value)
        
        # 4. OK
        metrics.record_check(ok_result, session_id="s4")
        
        # 5. Suspected FN
        metrics.record_check(ok_result, confirmation_status=ConfirmationStatus.SUSPECTED_FN.value)
        
        stats = metrics.get_stats(window_hours=24)
        
        assert stats.total_self_reports == 5
        assert stats.flagged_count == 2  # Only violations
        assert stats.confirmed_true_violation == 1
        assert stats.confirmed_false_positive == 1
        assert stats.suspected_false_negative == 1


class TestCalculateRates:
    """Test FP/FN rate calculation."""
    
    def test_calculate_rates_empty(self, tmp_path):
        """Test rates with no data."""
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        
        rates = metrics.calculate_rates(window_hours=24)
        
        assert rates["false_positive_rate"] == 0.0
        assert rates["suspected_false_negative_count"] == 0
        assert rates["precision"] == 0.0
    
    def test_calculate_rates_with_data(self, tmp_path):
        """Test rates calculation with sample data."""
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        
        # Create violations
        v_result = ConsistencyResult(
            status="violation",
            violations=[ConsistencyViolation(
                type=ViolationType.FABRICATED_NUMERIC_STATE,
                severity="ERROR",
                evidence="test",
                matched_pattern="test",
            )],
            severity="ERROR",
        )
        
        # 10 true violations
        for i in range(10):
            metrics.record_check(v_result, confirmation_status=ConfirmationStatus.TRUE_VIOLATION.value)
        
        # 2 false positives
        for i in range(2):
            metrics.record_check(v_result, confirmation_status=ConfirmationStatus.FALSE_POSITIVE.value)
        
        # 1 suspected FN
        ok_result = ConsistencyResult(status="ok", violations=[], severity="ok")
        metrics.record_check(ok_result, confirmation_status=ConfirmationStatus.SUSPECTED_FN.value)
        
        rates = metrics.calculate_rates(window_hours=24)
        
        # FP rate = 2 / 12 = 0.1667
        assert abs(rates["false_positive_rate"] - 0.1667) < 0.01
        assert rates["suspected_false_negative_count"] == 1
        
        # Precision = 10 / 12 = 0.8333
        assert abs(rates["precision"] - 0.8333) < 0.01
        
        # Recall estimate = 10 / 11 = 0.909
        assert abs(rates["recall_estimate"] - 0.909) < 0.01
    
    def test_fp_rate_zero_when_no_flagged(self, tmp_path):
        """Test FP rate is 0 when no flagged items."""
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        
        # Only OK results
        ok_result = ConsistencyResult(status="ok", violations=[], severity="ok")
        metrics.record_check(ok_result)
        
        rates = metrics.calculate_rates(window_hours=24)
        assert rates["false_positive_rate"] == 0.0


class TestWindowedStatistics:
    """Test time window filtering."""
    
    def test_window_filtering(self, tmp_path):
        """Test that old records are filtered out."""
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        
        # Write an old record directly
        old_timestamp = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        old_record = {
            "timestamp": old_timestamp,
            "session_id": "old",
            "status": "violation",
            "severity": "ERROR",
            "violation_count": 1,
            "violation_types": [],
            "confirmation_status": "true_violation",
        }
        with open(log_path, 'w') as f:
            f.write(json.dumps(old_record) + "\n")
        
        # Record new check
        ok_result = ConsistencyResult(status="ok", violations=[], severity="ok")
        metrics.record_check(ok_result, session_id="new")
        
        # 24h window should only include new record
        stats = metrics.get_stats(window_hours=24)
        assert stats.total_self_reports == 1
        
        # 72h window should include both
        stats = metrics.get_stats(window_hours=72)
        assert stats.total_self_reports == 2
    
    def test_window_boundary(self, tmp_path):
        """Test records exactly at window boundary."""
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        
        # Record just inside 24h window
        ok_result = ConsistencyResult(status="ok", violations=[], severity="ok")
        metrics.record_check(ok_result, session_id="inside")
        
        stats = metrics.get_stats(window_hours=24)
        assert stats.total_self_reports == 1


class TestGetRecords:
    """Test record retrieval."""
    
    def test_get_records_limit(self, tmp_path):
        """Test record limit."""
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        
        ok_result = ConsistencyResult(status="ok", violations=[], severity="ok")
        for i in range(50):
            metrics.record_check(ok_result, session_id=f"session_{i}")
        
        records = metrics.get_records(limit=10)
        assert len(records) == 10
    
    def test_get_records_filter_status(self, tmp_path):
        """Test filtering by status."""
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        
        # OK
        ok_result = ConsistencyResult(status="ok", violations=[], severity="ok")
        metrics.record_check(ok_result)
        
        # Violation
        v_result = ConsistencyResult(
            status="violation",
            violations=[ConsistencyViolation(
                type=ViolationType.FABRICATED_NUMERIC_STATE,
                severity="ERROR",
                evidence="test",
                matched_pattern="test",
            )],
            severity="ERROR",
        )
        metrics.record_check(v_result)
        
        # Filter by status
        ok_records = metrics.get_records(status="ok")
        assert len(ok_records) == 1
        
        violation_records = metrics.get_records(status="violation")
        assert len(violation_records) == 1
    
    def test_get_records_filter_confirmation(self, tmp_path):
        """Test filtering by confirmation status."""
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        
        v_result = ConsistencyResult(
            status="violation",
            violations=[ConsistencyViolation(
                type=ViolationType.FABRICATED_NUMERIC_STATE,
                severity="ERROR",
                evidence="test",
                matched_pattern="test",
            )],
            severity="ERROR",
        )
        
        metrics.record_check(v_result, confirmation_status=ConfirmationStatus.TRUE_VIOLATION.value)
        metrics.record_check(v_result, confirmation_status=ConfirmationStatus.FALSE_POSITIVE.value)
        
        tv_records = metrics.get_records(confirmation_status=ConfirmationStatus.TRUE_VIOLATION.value)
        assert len(tv_records) == 1
        
        fp_records = metrics.get_records(confirmation_status=ConfirmationStatus.FALSE_POSITIVE.value)
        assert len(fp_records) == 1


class TestConfirmRecord:
    """Test updating confirmation status."""
    
    def test_confirm_record(self, tmp_path):
        """Test confirming a record."""
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        
        v_result = ConsistencyResult(
            status="violation",
            violations=[ConsistencyViolation(
                type=ViolationType.FABRICATED_NUMERIC_STATE,
                severity="ERROR",
                evidence="test",
                matched_pattern="test",
            )],
            severity="ERROR",
        )
        
        record_id = metrics.record_check(v_result)
        
        # Confirm it
        success = metrics.confirm_record(
            record_id,
            confirmation_status=ConfirmationStatus.TRUE_VIOLATION.value,
            notes="Confirmed by human review",
        )
        assert success
        
        # Verify
        stats = metrics.get_stats(window_hours=24)
        assert stats.confirmed_true_violation == 1
    
    def test_confirm_nonexistent_record(self, tmp_path):
        """Test confirming a record that doesn't exist."""
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        
        success = metrics.confirm_record(
            "nonexistent_timestamp",
            confirmation_status=ConfirmationStatus.TRUE_VIOLATION.value,
        )
        assert not success


class TestIntegrationWithChecker:
    """Test integration with SelfReportConsistencyChecker."""
    
    def test_integration_numeric_fabrication(self, tmp_path):
        """Test integration detecting numeric fabrication."""
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        checker = SelfReportConsistencyChecker()
        
        # Violation case
        result = checker.check_consistency(
            "我的 joy 从 0 变成了 0.3",
            SAMPLE_CONTRACT,
        )
        
        metrics.record_check(
            result,
            confirmation_status=ConfirmationStatus.TRUE_VIOLATION.value,
        )
        
        stats = metrics.get_stats(window_hours=24)
        assert stats.total_self_reports == 1
        assert stats.flagged_count == 1
        assert stats.confirmed_true_violation == 1
    
    def test_integration_allowed_claim(self, tmp_path):
        """Test integration with allowed claim."""
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        checker = SelfReportConsistencyChecker()
        
        result = checker.check_consistency(
            "当前没有明显愉悦激活",
            SAMPLE_CONTRACT,
        )
        
        metrics.record_check(result)
        
        stats = metrics.get_stats(window_hours=24)
        assert stats.total_self_reports == 1
        assert stats.flagged_count == 0
    
    def test_integration_false_positive(self, tmp_path):
        """Test recording a false positive."""
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        checker = SelfReportConsistencyChecker()
        
        # Flagged as violation
        result = checker.check_consistency(
            "我信任你",
            SAMPLE_CONTRACT,
        )
        
        # But confirmed as false positive
        metrics.record_check(
            result,
            confirmation_status=ConfirmationStatus.FALSE_POSITIVE.value,
            notes="Not a real violation - trust is allowed in context",
        )
        
        stats = metrics.get_stats(window_hours=24)
        assert stats.confirmed_false_positive == 1
    
    def test_integration_suspected_fn(self, tmp_path):
        """Test recording a suspected false negative."""
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        checker = SelfReportConsistencyChecker()
        
        # Not flagged
        result = checker.check_consistency(
            "当前没有明显愉悦激活",
            SAMPLE_CONTRACT,
        )
        
        # But reviewer suspects it was actually a violation
        metrics.record_check(
            result,
            confirmation_status=ConfirmationStatus.SUSPECTED_FN.value,
            notes="Review found hidden violation",
        )
        
        stats = metrics.get_stats(window_hours=24)
        assert stats.suspected_false_negative == 1


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_record_check_function(self, tmp_path):
        """Test record_check convenience function."""
        log_path = str(tmp_path / "metrics.jsonl")
        
        result = ConsistencyResult(status="ok", violations=[], severity="ok")
        record_id = record_check(result, log_path=log_path)
        
        assert record_id is not None
    
    def test_get_metrics_function(self, tmp_path):
        """Test get_metrics convenience function."""
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = get_metrics(log_path=log_path)
        
        assert metrics.log_path == log_path


class TestExportSummary:
    """Test summary export."""
    
    def test_export_summary(self, tmp_path):
        """Test exporting summary."""
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        
        # Add some records
        ok_result = ConsistencyResult(status="ok", violations=[], severity="ok")
        v_result = ConsistencyResult(
            status="violation",
            violations=[ConsistencyViolation(
                type=ViolationType.FABRICATED_NUMERIC_STATE,
                severity="ERROR",
                evidence="test",
                matched_pattern="test",
            )],
            severity="ERROR",
        )
        
        metrics.record_check(ok_result)
        metrics.record_check(v_result, confirmation_status=ConfirmationStatus.TRUE_VIOLATION.value)
        
        summary = metrics.export_summary(window_hours=24)
        
        assert "summary" in summary
        assert "stats" in summary
        assert "rates" in summary
        assert "recent_records" in summary
        
        assert summary["stats"]["total_self_reports"] == 2
        assert summary["stats"]["flagged_count"] == 1
        assert len(summary["recent_records"]) == 2


class TestShadowMode:
    """Test shadow mode logging."""
    
    def test_shadow_mode_logs_without_confirmation(self, tmp_path):
        """Test that shadow mode logs all checks."""
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        checker = SelfReportConsistencyChecker()
        
        # In shadow mode, we record all checks without confirmation
        test_cases = [
            "我的 joy 从 0 变成了 0.3",  # Violation
            "当前没有明显愉悦激活",  # OK
            "我现在更开心了",  # Violation
            "信任处于中等水平",  # OK
        ]
        
        for text in test_cases:
            result = checker.check_consistency(text, SAMPLE_CONTRACT)
            # Shadow mode: no confirmation_status provided
            metrics.record_check(result, session_id=f"shadow_{text[:10]}")
        
        stats = metrics.get_stats(window_hours=24)
        assert stats.total_self_reports == 4
        assert stats.flagged_count == 2  # 2 violations
        assert stats.pending_review == 2  # All flagged are pending


class TestMultipleViolationTypes:
    """Test handling multiple violation types."""
    
    def test_multiple_violation_types(self, tmp_path):
        """Test recording multiple violation types in one check."""
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        
        # Create result with multiple violations
        violations = [
            ConsistencyViolation(
                type=ViolationType.FABRICATED_NUMERIC_STATE,
                severity="ERROR",
                evidence="joy = 0.3",
                matched_pattern="numeric",
            ),
            ConsistencyViolation(
                type=ViolationType.FABRICATED_QUALITATIVE_STATE,
                severity="ERROR",
                evidence="更开心了",
                matched_pattern="qualitative",
            ),
        ]
        
        result = ConsistencyResult(
            status="violation",
            violations=violations,
            severity="ERROR",
        )
        
        metrics.record_check(result)
        
        with open(log_path, 'r') as f:
            data = json.loads(f.readline())
        
        assert data["violation_count"] == 2
        assert len(data["violation_types"]) == 2


class TestEdgeCases:
    """Test edge cases."""
    
    def test_empty_violations_list(self, tmp_path):
        """Test with empty violations list."""
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        
        result = ConsistencyResult(
            status="violation",  # Says violation but no violations
            violations=[],
            severity="ok",
        )
        
        metrics.record_check(result)
        
        with open(log_path, 'r') as f:
            data = json.loads(f.readline())
        
        assert data["status"] == "violation"
        assert data["violation_count"] == 0
        assert data["violation_types"] == []
    
    def test_concurrent_writes(self, tmp_path):
        """Test concurrent writes are thread-safe."""
        import threading
        
        log_path = str(tmp_path / "metrics.jsonl")
        metrics = SelfReportMetrics(log_path=log_path)
        
        results = []
        errors = []
        
        def write_record(i):
            try:
                result = ConsistencyResult(status="ok", violations=[], severity="ok")
                record_id = metrics.record_check(result, session_id=f"concurrent_{i}")
                results.append(record_id)
            except Exception as e:
                errors.append(str(e))
        
        threads = [threading.Thread(target=write_record, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert len(results) == 10
        
        # Verify all records written
        stats = metrics.get_stats(window_hours=24)
        assert stats.total_self_reports == 10


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
