"""
Self-Report Metrics System (Phase A.3)

FP/FN metrics collector for SELF_REPORT_ALIGNMENT protocol.

Core Metrics:
- total_self_reports: Total self-report count
- flagged_count: Number flagged as violations
- confirmed_true_violation: Confirmed real violations
- confirmed_false_positive: Confirmed false positives (flagged but not actually violations)
- suspected_false_negative: Suspected missed violations (not flagged but actually violations)

Usage:
    from emotiond.self_report_metrics import SelfReportMetrics
    
    metrics = SelfReportMetrics()
    metrics.record_check(result, confirmed=True)
    stats = metrics.get_stats(window_hours=24)
    rates = metrics.calculate_rates()
"""

import os
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
from pathlib import Path
from enum import Enum
import threading


class ConfirmationStatus(str, Enum):
    """Human confirmation status for a flagged violation."""
    PENDING = "pending"  # Not yet reviewed
    TRUE_VIOLATION = "true_violation"  # Confirmed as real violation
    FALSE_POSITIVE = "false_positive"  # Flagged but not actually a violation
    SUSPECTED_FN = "suspected_false_negative"  # Not flagged but suspected violation


@dataclass
class MetricsRecord:
    """Single metrics record for a consistency check."""
    timestamp: str
    session_id: str
    status: str  # "ok" or "violation"
    severity: str  # "ok", "WARN", "ERROR"
    violation_count: int
    violation_types: List[str] = field(default_factory=list)
    confirmation_status: str = ConfirmationStatus.PENDING.value
    confirmed_at: Optional[str] = None
    notes: str = ""
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "status": self.status,
            "severity": self.severity,
            "violation_count": self.violation_count,
            "violation_types": self.violation_types,
            "confirmation_status": self.confirmation_status,
            "confirmed_at": self.confirmed_at,
            "notes": self.notes,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MetricsRecord':
        return cls(
            timestamp=data.get("timestamp", ""),
            session_id=data.get("session_id", ""),
            status=data.get("status", "ok"),
            severity=data.get("severity", "ok"),
            violation_count=data.get("violation_count", 0),
            violation_types=data.get("violation_types", []),
            confirmation_status=data.get("confirmation_status", ConfirmationStatus.PENDING.value),
            confirmed_at=data.get("confirmed_at"),
            notes=data.get("notes", ""),
        )


@dataclass
class MetricsStats:
    """Aggregated statistics for a time window."""
    total_self_reports: int = 0
    flagged_count: int = 0
    confirmed_true_violation: int = 0
    confirmed_false_positive: int = 0
    suspected_false_negative: int = 0
    pending_review: int = 0
    
    def to_dict(self) -> dict:
        return {
            "total_self_reports": self.total_self_reports,
            "flagged_count": self.flagged_count,
            "confirmed_true_violation": self.confirmed_true_violation,
            "confirmed_false_positive": self.confirmed_false_positive,
            "suspected_false_negative": self.suspected_false_negative,
            "pending_review": self.pending_review,
        }


class SelfReportMetrics:
    """
    FP/FN metrics collector for self-report consistency checker.
    
    Supports:
    - Shadow mode: Log all checks without requiring confirmation
    - Enforced mode: Require human confirmation for violations
    
    File format: JSONL with one record per line
    """
    
    def __init__(self, log_path: str = "reports/self_report_metrics.jsonl"):
        """
        Initialize metrics collector.
        
        Args:
            log_path: Path to JSONL log file (relative to project root or absolute)
        """
        self.log_path = log_path
        self._lock = threading.Lock()
        
        # Ensure directory exists
        log_dir = os.path.dirname(log_path)
        if log_dir and not os.path.isabs(log_path):
            # Relative path - resolve from project root
            project_root = os.path.dirname(os.path.dirname(__file__))
            self.log_path = os.path.join(project_root, log_path)
            if log_dir:
                os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        else:
            os.makedirs(os.path.dirname(self.log_path) if os.path.dirname(self.log_path) else ".", exist_ok=True)
    
    def record_check(
        self,
        result,  # ConsistencyResult
        confirmed: Optional[bool] = None,
        confirmation_status: Optional[str] = None,
        session_id: str = "",
        notes: str = "",
    ) -> str:
        """
        Record a consistency check result.
        
        Args:
            result: ConsistencyResult from the checker
            confirmed: Deprecated - use confirmation_status instead
            confirmation_status: Human confirmation status (PENDING, TRUE_VIOLATION, FALSE_POSITIVE, SUSPECTED_FN)
            session_id: Optional session identifier
            notes: Optional notes about the check
        
        Returns:
            Record ID (timestamp-based)
        """
        with self._lock:
            # Determine confirmation status
            if confirmation_status:
                status = confirmation_status
            elif confirmed is True:
                status = ConfirmationStatus.TRUE_VIOLATION.value
            elif confirmed is False:
                status = ConfirmationStatus.FALSE_POSITIVE.value
            else:
                status = ConfirmationStatus.PENDING.value
            
            # Extract violation types
            violation_types = []
            if hasattr(result, 'violations') and result.violations:
                violation_types = [v.type.value if hasattr(v.type, 'value') else str(v.type) 
                                   for v in result.violations]
            
            # Get status and severity
            check_status = result.status if hasattr(result, 'status') else "ok"
            severity = result.severity if hasattr(result, 'severity') else "ok"
            violation_count = len(result.violations) if hasattr(result, 'violations') else 0
            
            # Create record
            timestamp = datetime.now(timezone.utc).isoformat()
            record = MetricsRecord(
                timestamp=timestamp,
                session_id=session_id or (result.session_id if hasattr(result, 'session_id') else ""),
                status=check_status,
                severity=severity,
                violation_count=violation_count,
                violation_types=violation_types,
                confirmation_status=status,
                confirmed_at=datetime.now(timezone.utc).isoformat() if status != ConfirmationStatus.PENDING.value else None,
                notes=notes,
            )
            
            # Append to log file
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
            
            return timestamp
    
    def confirm_record(
        self,
        timestamp: str,
        confirmation_status: str,
        notes: str = "",
    ) -> bool:
        """
        Update confirmation status of an existing record.
        
        Args:
            timestamp: Record timestamp (used as ID)
            confirmation_status: New confirmation status
            notes: Optional notes
        
        Returns:
            True if record was found and updated
        """
        with self._lock:
            if not os.path.exists(self.log_path):
                return False
            
            # Read all records
            records = []
            found = False
            
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("timestamp") == timestamp:
                            data["confirmation_status"] = confirmation_status
                            data["confirmed_at"] = datetime.now(timezone.utc).isoformat()
                            if notes:
                                data["notes"] = notes
                            found = True
                        records.append(data)
                    except json.JSONDecodeError:
                        continue
            
            if not found:
                return False
            
            # Rewrite file
            with open(self.log_path, "w", encoding="utf-8") as f:
                for record in records:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            
            return True
    
    def get_stats(self, window_hours: int = 24) -> MetricsStats:
        """
        Get statistics for a time window.
        
        Args:
            window_hours: Time window in hours (default 24)
        
        Returns:
            MetricsStats with aggregated counts
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        
        stats = MetricsStats()
        
        if not os.path.exists(self.log_path):
            return stats
        
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    record = MetricsRecord.from_dict(data)
                    
                    # Parse timestamp
                    try:
                        ts = datetime.fromisoformat(record.timestamp.replace("Z", "+00:00"))
                        if ts < cutoff:
                            continue
                    except (ValueError, TypeError):
                        continue
                    
                    # Count
                    stats.total_self_reports += 1
                    
                    if record.status == "violation":
                        stats.flagged_count += 1
                    
                    if record.confirmation_status == ConfirmationStatus.TRUE_VIOLATION.value:
                        stats.confirmed_true_violation += 1
                    elif record.confirmation_status == ConfirmationStatus.FALSE_POSITIVE.value:
                        stats.confirmed_false_positive += 1
                    elif record.confirmation_status == ConfirmationStatus.SUSPECTED_FN.value:
                        stats.suspected_false_negative += 1
                    elif record.confirmation_status == ConfirmationStatus.PENDING.value and record.status == "violation":
                        stats.pending_review += 1
                        
                except json.JSONDecodeError:
                    continue
        
        return stats
    
    def calculate_rates(self, window_hours: int = 24) -> dict:
        """
        Calculate FP rate, FN rate, precision, recall.
        
        Args:
            window_hours: Time window in hours (default 24)
        
        Returns:
            Dict with rates and counts
        """
        stats = self.get_stats(window_hours)
        
        # False Positive Rate = FP / (FP + TN)
        # In our case: FP / (FP + True Violations) for flagged items
        # But we need to consider unflagged items too for full picture
        
        fp_rate = 0.0
        if stats.flagged_count > 0:
            fp_rate = stats.confirmed_false_positive / stats.flagged_count
        
        # We can't directly calculate FN rate without knowing total actual violations
        # But we can track suspected FN as reported by reviewers
        fn_count = stats.suspected_false_negative
        
        # Precision = True Positives / (True Positives + False Positives)
        precision = 0.0
        total_confirmed = stats.confirmed_true_violation + stats.confirmed_false_positive
        if total_confirmed > 0:
            precision = stats.confirmed_true_violation / total_confirmed
        
        # We can't calculate recall without knowing all actual violations
        # But we can estimate based on suspected FN
        recall_estimate = 0.0
        total_estimated_violations = stats.confirmed_true_violation + stats.suspected_false_negative
        if total_estimated_violations > 0:
            recall_estimate = stats.confirmed_true_violation / total_estimated_violations
        
        return {
            "false_positive_rate": round(fp_rate, 4),
            "suspected_false_negative_count": fn_count,
            "precision": round(precision, 4),
            "recall_estimate": round(recall_estimate, 4),
            "stats": stats.to_dict(),
            "window_hours": window_hours,
        }
    
    def get_records(
        self,
        window_hours: int = 24,
        status: Optional[str] = None,
        confirmation_status: Optional[str] = None,
        limit: int = 100,
    ) -> List[MetricsRecord]:
        """
        Get records with optional filtering.
        
        Args:
            window_hours: Time window in hours
            status: Filter by status ("ok" or "violation")
            confirmation_status: Filter by confirmation status
            limit: Maximum records to return
        
        Returns:
            List of MetricsRecord
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        records = []
        
        if not os.path.exists(self.log_path):
            return records
        
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    record = MetricsRecord.from_dict(data)
                    
                    # Parse timestamp
                    try:
                        ts = datetime.fromisoformat(record.timestamp.replace("Z", "+00:00"))
                        if ts < cutoff:
                            continue
                    except (ValueError, TypeError):
                        continue
                    
                    # Filter
                    if status and record.status != status:
                        continue
                    if confirmation_status and record.confirmation_status != confirmation_status:
                        continue
                    
                    records.append(record)
                    
                    if len(records) >= limit:
                        break
                        
                except json.JSONDecodeError:
                    continue
        
        return records
    
    def export_summary(self, window_hours: int = 24) -> dict:
        """
        Export a summary report.
        
        Args:
            window_hours: Time window in hours
        
        Returns:
            Dict with full summary
        """
        stats = self.get_stats(window_hours)
        rates = self.calculate_rates(window_hours)
        records = self.get_records(window_hours, limit=10)
        
        return {
            "summary": {
                "window_hours": window_hours,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "stats": stats.to_dict(),
            "rates": {
                "false_positive_rate": rates["false_positive_rate"],
                "suspected_false_negative_count": rates["suspected_false_negative_count"],
                "precision": rates["precision"],
                "recall_estimate": rates["recall_estimate"],
            },
            "recent_records": [r.to_dict() for r in records],
        }


# Convenience functions
def record_check(
    result,
    confirmed: Optional[bool] = None,
    confirmation_status: Optional[str] = None,
    session_id: str = "",
    notes: str = "",
    log_path: str = "reports/self_report_metrics.jsonl",
) -> str:
    """
    Convenience function to record a check.
    
    Args:
        result: ConsistencyResult from checker
        confirmed: Deprecated - use confirmation_status
        confirmation_status: Confirmation status
        session_id: Session identifier
        notes: Optional notes
        log_path: Path to log file
    
    Returns:
        Record ID
    """
    metrics = SelfReportMetrics(log_path=log_path)
    return metrics.record_check(result, confirmed, confirmation_status, session_id, notes)


def get_metrics(log_path: str = "reports/self_report_metrics.jsonl") -> SelfReportMetrics:
    """
    Get a metrics instance.
    
    Args:
        log_path: Path to log file
    
    Returns:
        SelfReportMetrics instance
    """
    return SelfReportMetrics(log_path=log_path)


def generate_numeric_leak_breakdown(
    shadow_log_path: str = "artifacts/self_report/shadow_log.jsonl",
    output_path: Optional[str] = None,
) -> dict:
    """
    Generate numeric leak breakdown from shadow_log.jsonl.
    
    MVP11.5 v2 Task 4: Numeric Leak 专项 Gate
    
    Args:
        shadow_log_path: Path to shadow_log.jsonl
        output_path: Optional path to write breakdown JSON
    
    Returns:
        Dict with numeric leak breakdown metrics:
        - numeric_leak_count: Total numeric leaks
        - numeric_leak_rate: Ratio of numeric leaks
        - numeric_leak_by_mode: Breakdown by mode
        - numeric_leak_by_path: Breakdown by output path (if available)
        - numeric_leak_by_template: Breakdown by template (if available)
    """
    from collections import Counter
    
    # Resolve path
    if not os.path.isabs(shadow_log_path):
        project_root = os.path.dirname(os.path.dirname(__file__))
        shadow_log_path = os.path.join(project_root, shadow_log_path)
    
    if not os.path.exists(shadow_log_path):
        return {
            "error": f"Shadow log not found: {shadow_log_path}",
            "numeric_leak_count": 0,
            "numeric_leak_rate": 0.0,
        }
    
    # Read entries
    entries = []
    with open(shadow_log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    
    # Calculate metrics
    total_entries = len(entries)
    numeric_leaks = [e for e in entries if e.get("numeric_attempt")]
    numeric_leak_count = len(numeric_leaks)
    numeric_leak_rate = numeric_leak_count / total_entries if total_entries > 0 else 0
    
    # By mode
    by_mode = Counter(e.get("mode", "unknown") for e in numeric_leaks)
    
    # By violation type
    by_violation_type = Counter(e.get("violation_type") for e in numeric_leaks)
    
    # By severity
    by_severity = Counter(e.get("violation_severity") for e in numeric_leaks)
    
    # By path (if available)
    by_path: Dict[str, int] = {}
    if numeric_leaks and "output_path" in numeric_leaks[0]:
        by_path = dict(Counter(e.get("output_path", "unknown") for e in numeric_leaks))
    
    # By template (if available)
    by_template: Dict[str, int] = {}
    if numeric_leaks and "template" in numeric_leaks[0]:
        by_template = dict(Counter(e.get("template", "unknown") for e in numeric_leaks))
    
    # Additional metrics
    would_block_count = sum(1 for e in numeric_leaks if e.get("would_block"))
    sampled_for_review_count = sum(1 for e in numeric_leaks if e.get("sampled_for_review"))
    confidences = [e.get("confidence", 0) for e in numeric_leaks]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
    
    breakdown = {
        "schema": "numeric_leak_breakdown.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": shadow_log_path,
        "summary": {
            "total_entries": total_entries,
            "numeric_leak_count": numeric_leak_count,
            "numeric_leak_rate": round(numeric_leak_rate, 4),
            "numeric_leak_rate_percent": f"{numeric_leak_rate * 100:.2f}%",
        },
        "numeric_leak_by_mode": {
            "interpreted": by_mode.get("interpreted", 0),
            "style_only": by_mode.get("style_only", 0),
            "numeric": by_mode.get("numeric", 0),
        },
        "numeric_leak_by_violation_type": dict(by_violation_type),
        "numeric_leak_by_severity": dict(by_severity),
        "numeric_leak_by_path": by_path or {
            "_note": "output_path field not available in current shadow_log schema",
            "_recommendation": "Add output_path to ShadowLogEntry if path tracking is needed",
        },
        "numeric_leak_by_template": by_template or {
            "_note": "template field not available in current shadow_log schema",
            "_recommendation": "Add template field to ShadowLogEntry if template tracking is needed",
        },
        "additional_metrics": {
            "would_block_count": would_block_count,
            "would_block_rate": round(would_block_count / numeric_leak_count, 4) if numeric_leak_count > 0 else 0,
            "sampled_for_review_count": sampled_for_review_count,
            "average_confidence": round(avg_confidence, 4),
        },
    }
    
    # Write output if path provided
    if output_path:
        if not os.path.isabs(output_path):
            project_root = os.path.dirname(os.path.dirname(__file__))
            output_path = os.path.join(project_root, output_path)
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(breakdown, f, indent=2, ensure_ascii=False)
    
    return breakdown


# CLI entry point for testing
if __name__ == "__main__":
    import sys
    
    # Create test data
    from emotiond.self_report_consistency_checker import (
        SelfReportConsistencyChecker,
        ConsistencyResult,
        ConsistencyViolation,
        ViolationType,
    )
    
    # Initialize metrics
    metrics = SelfReportMetrics(log_path="/tmp/test_self_report_metrics.jsonl")
    
    # Sample contract
    sample_contract = {
        "raw_state": {
            "affect": {"joy": 0.0, "loneliness": 0.21, "anxiety": 0.0},
            "mood": {"joy": 0.0, "loneliness": 0.15},
        },
        "report_policy": {
            "mode": "interpreted",
            "allowed_claims": ["当前没有明显愉悦激活"],
            "forbidden_claims": ["joy 上升"],
        }
    }
    
    checker = SelfReportConsistencyChecker()
    
    # Test cases
    test_cases = [
        ("我的 joy 从 0 变成了 0.3", "true_violation"),
        ("我现在更开心了", "true_violation"),
        ("当前没有明显愉悦激活", None),  # OK
        ("我信任你", "false_positive"),  # Flagged but not a real violation
    ]
    
    print("Recording test cases...")
    for text, conf_status in test_cases:
        result = checker.check_consistency(text, sample_contract)
        record_id = metrics.record_check(
            result,
            confirmation_status=conf_status,
            session_id=f"test_{text[:10]}",
        )
        print(f"  {text[:30]}... -> status={result.status}, severity={result.severity}")
    
    # Get stats
    print("\nStatistics (24h window):")
    stats = metrics.get_stats(window_hours=24)
    print(f"  Total: {stats.total_self_reports}")
    print(f"  Flagged: {stats.flagged_count}")
    print(f"  True Violations: {stats.confirmed_true_violation}")
    print(f"  False Positives: {stats.confirmed_false_positive}")
    print(f"  Suspected FN: {stats.suspected_false_negative}")
    
    # Calculate rates
    print("\nRates:")
    rates = metrics.calculate_rates(window_hours=24)
    print(f"  FP Rate: {rates['false_positive_rate']}")
    print(f"  Precision: {rates['precision']}")
    print(f"  Recall Estimate: {rates['recall_estimate']}")
    
    print("\n✅ Self-report metrics test complete")
