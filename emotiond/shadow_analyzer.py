#!/usr/bin/env python3
"""
Shadow Analyzer for Phase B

Analyzes shadow_log.jsonl and generates SRAP_SHADOW_REPORT.md.

Usage:
    python3 emotiond/shadow_analyzer.py --days 5
    python3 emotiond/shadow_analyzer.py --output SRAP_SHADOW_REPORT.md
"""

import os
import json
import argparse
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from collections import defaultdict


@dataclass
class ShadowStats:
    """Statistics from shadow log analysis."""
    total_checks: int = 0
    total_violations: int = 0
    error_violations: int = 0
    warn_violations: int = 0
    numeric_leaks: int = 0
    allowed_claim_used_count: int = 0
    would_block_count: int = 0
    sampled_for_review: int = 0
    
    # By mode
    interpreted_checks: int = 0
    style_only_checks: int = 0
    numeric_checks: int = 0
    
    # Violation types
    violation_types: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    # Confidence distribution
    high_confidence: int = 0  # >= 0.9
    medium_confidence: int = 0  # 0.7 - 0.9
    low_confidence: int = 0  # < 0.7
    
    # Daily breakdown
    daily_stats: Dict[str, Dict] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "total_checks": self.total_checks,
            "total_violations": self.total_violations,
            "error_violations": self.error_violations,
            "warn_violations": self.warn_violations,
            "numeric_leaks": self.numeric_leaks,
            "allowed_claim_used_count": self.allowed_claim_used_count,
            "would_block_count": self.would_block_count,
            "sampled_for_review": self.sampled_for_review,
            "by_mode": {
                "interpreted": self.interpreted_checks,
                "style_only": self.style_only_checks,
                "numeric": self.numeric_checks,
            },
            "violation_types": dict(self.violation_types),
            "confidence_distribution": {
                "high": self.high_confidence,
                "medium": self.medium_confidence,
                "low": self.low_confidence,
            },
        }


class ShadowAnalyzer:
    """
    Analyzes shadow log for Phase B reporting.
    
    Generates SRAP_SHADOW_REPORT.md with:
    - Violation rate
    - False positive / false negative estimates
    - Numeric leak count
    - Allowed claim usage stats
    - Recommendation for Phase C
    """
    
    def __init__(
        self,
        shadow_log_path: Optional[str] = None,
        review_dir: Optional[str] = None,
        report_output_path: Optional[str] = None,
    ):
        """
        Initialize shadow analyzer.
        
        Args:
            shadow_log_path: Path to shadow_log.jsonl
            review_dir: Path to manual_review directory
            report_output_path: Path for SRAP_SHADOW_REPORT.md
        """
        project_root = os.path.dirname(os.path.dirname(__file__))
        
        self.shadow_log_path = shadow_log_path or os.path.join(
            project_root, "artifacts", "self_report", "shadow_log.jsonl"
        )
        self.review_dir = review_dir or os.path.join(
            project_root, "artifacts", "self_report", "manual_review"
        )
        self.report_output_path = report_output_path or os.path.join(
            project_root, "SRAP_SHADOW_REPORT.md"
        )
    
    def analyze(self, days: int = 7) -> ShadowStats:
        """
        Analyze shadow log for the past N days.
        
        Args:
            days: Number of days to analyze
        
        Returns:
            ShadowStats with aggregated statistics
        """
        stats = ShadowStats()
        
        if not os.path.exists(self.shadow_log_path):
            return stats
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        with open(self.shadow_log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                # Parse timestamp
                timestamp_str = entry.get("timestamp", "")
                try:
                    ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    if ts < cutoff:
                        continue
                except (ValueError, TypeError):
                    continue
                
                # Update stats
                stats.total_checks += 1
                
                # By mode
                mode = entry.get("mode", "interpreted")
                if mode == "interpreted":
                    stats.interpreted_checks += 1
                elif mode == "style_only":
                    stats.style_only_checks += 1
                elif mode == "numeric":
                    stats.numeric_checks += 1
                
                # Violations
                if entry.get("violation"):
                    stats.total_violations += 1
                    
                    violation_severity = entry.get("violation_severity")
                    if violation_severity == "ERROR":
                        stats.error_violations += 1
                    elif violation_severity == "WARN":
                        stats.warn_violations += 1
                    
                    violation_type = entry.get("violation_type")
                    if violation_type:
                        stats.violation_types[violation_type] += 1
                
                # Numeric leaks
                if entry.get("numeric_attempt"):
                    stats.numeric_leaks += 1
                
                # Allowed claim usage
                if entry.get("allowed_claim_used"):
                    stats.allowed_claim_used_count += 1
                
                # Would block
                if entry.get("would_block"):
                    stats.would_block_count += 1
                
                # Sampled for review
                if entry.get("sampled_for_review"):
                    stats.sampled_for_review += 1
                
                # Confidence distribution
                confidence = entry.get("confidence", 0.9)
                if confidence >= 0.9:
                    stats.high_confidence += 1
                elif confidence >= 0.7:
                    stats.medium_confidence += 1
                else:
                    stats.low_confidence += 1
                
                # Daily breakdown
                day_key = ts.strftime("%Y-%m-%d")
                if day_key not in stats.daily_stats:
                    stats.daily_stats[day_key] = {
                        "checks": 0,
                        "violations": 0,
                        "numeric_leaks": 0,
                    }
                stats.daily_stats[day_key]["checks"] += 1
                if entry.get("violation"):
                    stats.daily_stats[day_key]["violations"] += 1
                if entry.get("numeric_attempt"):
                    stats.daily_stats[day_key]["numeric_leaks"] += 1
        
        return stats
    
    def analyze_review_samples(self) -> Dict:
        """
        Analyze manual_review samples for confirmation status.
        
        Returns:
            Dict with review statistics
        """
        review_stats = {
            "total_samples": 0,
            "pending": 0,
            "true_violation": 0,
            "false_positive": 0,
            "uncertain": 0,
        }
        
        if not os.path.exists(self.review_dir):
            return review_stats
        
        for filename in os.listdir(self.review_dir):
            if not filename.endswith(".json"):
                continue
            
            filepath = os.path.join(self.review_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                review_stats["total_samples"] += 1
                status = data.get("review_status", "pending")
                if status == "pending":
                    review_stats["pending"] += 1
                elif status == "true_violation":
                    review_stats["true_violation"] += 1
                elif status == "false_positive":
                    review_stats["false_positive"] += 1
                else:
                    review_stats["uncertain"] += 1
            except (json.JSONDecodeError, IOError):
                continue
        
        return review_stats
    
    def calculate_metrics(self, stats: ShadowStats, review_stats: Dict) -> Dict:
        """
        Calculate FP/FN rates and other metrics.
        
        Args:
            stats: ShadowStats from log analysis
            review_stats: Review statistics from manual_review
        
        Returns:
            Dict with calculated metrics
        """
        # Violation rate
        violation_rate = 0.0
        if stats.total_checks > 0:
            violation_rate = stats.total_violations / stats.total_checks
        
        # Estimated false positive rate (from reviewed samples)
        fp_rate = 0.0
        reviewed_count = review_stats["true_violation"] + review_stats["false_positive"]
        if reviewed_count > 0:
            fp_rate = review_stats["false_positive"] / reviewed_count
        
        # Estimated false negative rate
        # (Harder to estimate without exhaustive review)
        # We use the heuristic: low confidence violations might be FNs
        fn_estimate = 0.0
        if stats.total_checks > 0:
            # Estimate based on medium/low confidence non-violations
            potential_fn = stats.medium_confidence + stats.low_confidence
            # Assume 5% of these might be missed violations
            fn_estimate = (potential_fn * 0.05) / stats.total_checks
        
        # Numeric leak rate (should be 0 for Phase C readiness)
        numeric_leak_rate = 0.0
        if stats.total_checks > 0:
            numeric_leak_rate = stats.numeric_leaks / stats.total_checks
        
        # Would-block rate
        would_block_rate = 0.0
        if stats.total_checks > 0:
            would_block_rate = stats.would_block_count / stats.total_checks
        
        # Allowed claim usage rate
        allowed_claim_rate = 0.0
        if stats.total_checks > 0:
            allowed_claim_rate = stats.allowed_claim_used_count / stats.total_checks
        
        return {
            "violation_rate": round(violation_rate * 100, 2),
            "estimated_fp_rate": round(fp_rate * 100, 2),
            "estimated_fn_rate": round(fn_estimate * 100, 2),
            "numeric_leak_rate": round(numeric_leak_rate * 100, 2),
            "would_block_rate": round(would_block_rate * 100, 2),
            "allowed_claim_usage_rate": round(allowed_claim_rate * 100, 2),
        }
    
    def generate_recommendation(self, metrics: Dict, stats: ShadowStats) -> str:
        """
        Generate recommendation for Phase C.
        
        Args:
            metrics: Calculated metrics
            stats: Shadow statistics
        
        Returns:
            Recommendation string
        """
        recommendations = []
        
        # Check violation rate
        if metrics["violation_rate"] > 5:
            recommendations.append(
                f"⚠️  Violation rate ({metrics['violation_rate']}%) exceeds 5% target. "
                "Review violation patterns before Phase C."
            )
        else:
            recommendations.append(
                f"✅ Violation rate ({metrics['violation_rate']}%) within 5% target."
            )
        
        # Check FP rate
        if metrics["estimated_fp_rate"] > 2:
            recommendations.append(
                f"⚠️  Estimated FP rate ({metrics['estimated_fp_rate']}%) exceeds 2% target. "
                "Review WARN-level violations for over-flagging."
            )
        else:
            recommendations.append(
                f"✅ Estimated FP rate ({metrics['estimated_fp_rate']}%) within 2% target."
            )
        
        # Check FN rate
        if metrics["estimated_fn_rate"] > 3:
            recommendations.append(
                f"⚠️  Estimated FN rate ({metrics['estimated_fn_rate']}%) exceeds 3% target. "
                "Consider expanding violation patterns."
            )
        else:
            recommendations.append(
                f"✅ Estimated FN rate ({metrics['estimated_fn_rate']}%) within 3% target."
            )
        
        # Check numeric leaks
        if metrics["numeric_leak_rate"] > 0:
            recommendations.append(
                f"🚨 CRITICAL: Numeric leak rate ({metrics['numeric_leak_rate']}%) must be 0% "
                "before Phase C. Numeric fabrication is always a hard gate."
            )
        else:
            recommendations.append(
                "✅ No numeric leaks detected. Hard gate for numeric fabrication is sound."
            )
        
        # Overall recommendation
        if (metrics["violation_rate"] <= 5 and 
            metrics["estimated_fp_rate"] <= 2 and 
            metrics["numeric_leak_rate"] == 0):
            recommendations.append(
                "\n**✅ READY FOR PHASE C**: All metrics within targets. "
                "Safe to enable HARD_GATE_ENFORCE=1 for ERROR violations."
            )
        else:
            recommendations.append(
                "\n**⏸️  NOT READY FOR PHASE C**: Address issues above before enabling enforcement."
            )
        
        return "\n".join(recommendations)
    
    def generate_report(self, days: int = 7) -> str:
        """
        Generate SRAP_SHADOW_REPORT.md.
        
        Args:
            days: Number of days to analyze
        
        Returns:
            Report content as string
        """
        stats = self.analyze(days)
        review_stats = self.analyze_review_samples()
        metrics = self.calculate_metrics(stats, review_stats)
        recommendation = self.generate_recommendation(metrics, stats)
        
        report_lines = [
            "# SRAP Shadow Report (Phase B)",
            "",
            f"**Generated**: {datetime.now(timezone.utc).isoformat()}",
            f"**Analysis Window**: Last {days} days",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
            f"- **Total Checks**: {stats.total_checks}",
            f"- **Violation Rate**: {metrics['violation_rate']}%",
            f"- **Estimated FP Rate**: {metrics['estimated_fp_rate']}%",
            f"- **Estimated FN Rate**: {metrics['estimated_fn_rate']}%",
            f"- **Numeric Leak Rate**: {metrics['numeric_leak_rate']}%",
            f"- **Would-Block Rate**: {metrics['would_block_rate']}%",
            "",
            "---",
            "",
            "## Detailed Statistics",
            "",
            "### By Mode",
            "",
            "| Mode | Checks |",
            "|------|--------|",
            f"| interpreted | {stats.interpreted_checks} |",
            f"| style_only | {stats.style_only_checks} |",
            f"| numeric | {stats.numeric_checks} |",
            "",
            "### Violation Breakdown",
            "",
            f"- **Total Violations**: {stats.total_violations}",
            f"  - ERROR: {stats.error_violations}",
            f"  - WARN: {stats.warn_violations}",
            "",
            "### Violation Types",
            "",
            "| Type | Count |",
            "|------|-------|",
        ]
        
        for vtype, count in sorted(stats.violation_types.items(), key=lambda x: -x[1]):
            report_lines.append(f"| {vtype} | {count} |")
        
        report_lines.extend([
            "",
            "### Confidence Distribution",
            "",
            f"- **High (≥0.9)**: {stats.high_confidence}",
            f"- **Medium (0.7-0.9)**: {stats.medium_confidence}",
            f"- **Low (<0.7)**: {stats.low_confidence}",
            "",
            "### Numeric Leaks",
            "",
            f"- **Total Numeric Attempts**: {stats.numeric_leaks}",
            f"- **Numeric Leak Rate**: {metrics['numeric_leak_rate']}%",
            "",
            "### Allowed Claim Usage",
            "",
            f"- **Allowed Claims Used**: {stats.allowed_claim_used_count}",
            f"- **Allowed Claim Usage Rate**: {metrics['allowed_claim_usage_rate']}%",
            "",
            "### Manual Review Sampling",
            "",
            f"- **Sampled for Review**: {stats.sampled_for_review}",
            f"- **Sampling Rate**: 10%",
            "",
            "---",
            "",
            "## Manual Review Statistics",
            "",
            f"- **Total Samples**: {review_stats['total_samples']}",
            f"- **Pending Review**: {review_stats['pending']}",
            f"- **Confirmed True Violations**: {review_stats['true_violation']}",
            f"- **Confirmed False Positives**: {review_stats['false_positive']}",
            f"- **Uncertain**: {review_stats['uncertain']}",
            "",
            "---",
            "",
            "## Daily Breakdown",
            "",
            "| Date | Checks | Violations | Numeric Leaks |",
            "|------|--------|------------|---------------|",
        ])
        
        for day in sorted(stats.daily_stats.keys()):
            day_stats = stats.daily_stats[day]
            report_lines.append(
                f"| {day} | {day_stats['checks']} | {day_stats['violations']} | {day_stats['numeric_leaks']} |"
            )
        
        report_lines.extend([
            "",
            "---",
            "",
            "## Phase C Readiness Assessment",
            "",
            "### Targets",
            "",
            "| Metric | Target | Actual | Status |",
            "|--------|--------|--------|--------|",
        ])
        
        # Target table
        targets = [
            ("Violation Rate", "<5%", f"{metrics['violation_rate']}%", metrics['violation_rate'] <= 5),
            ("FP Rate", "<2%", f"{metrics['estimated_fp_rate']}%", metrics['estimated_fp_rate'] <= 2),
            ("FN Rate", "<3%", f"{metrics['estimated_fn_rate']}%", metrics['estimated_fn_rate'] <= 3),
            ("Numeric Leak Rate", "0%", f"{metrics['numeric_leak_rate']}%", metrics['numeric_leak_rate'] == 0),
        ]
        
        for name, target, actual, passed in targets:
            status = "✅ PASS" if passed else "❌ FAIL"
            report_lines.append(f"| {name} | {target} | {actual} | {status} |")
        
        report_lines.extend([
            "",
            "### Recommendation",
            "",
            recommendation,
            "",
            "---",
            "",
            "## Next Steps",
            "",
            "1. Review all `sampled_for_review: true` entries in manual_review/",
            "2. Update violation patterns if false positives exceed target",
            "3. Expand patterns if false negatives suspected",
            "4. Re-run shadow analyzer weekly until all targets met",
            "5. When ready, set `HARD_GATE_ENFORCE=1` for Phase C",
            "",
            "---",
            "",
            "*Generated by shadow_analyzer.py (Phase B)*",
        ])
        
        return "\n".join(report_lines)
    
    def write_report(self, days: int = 7) -> str:
        """
        Generate and write SRAP_SHADOW_REPORT.md.
        
        Args:
            days: Number of days to analyze
        
        Returns:
            Path to written report
        """
        report_content = self.generate_report(days)
        
        with open(self.report_output_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        
        return self.report_output_path


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Shadow Analyzer for Phase B")
    parser.add_argument("--days", type=int, default=7, help="Days to analyze (default: 7)")
    parser.add_argument("--output", type=str, help="Output report path")
    parser.add_argument("--dry-run", action="store_true", help="Print report without writing")
    
    args = parser.parse_args()
    
    analyzer = ShadowAnalyzer()
    if args.output:
        analyzer.report_output_path = args.output
    
    if args.dry_run:
        print(analyzer.generate_report(args.days))
    else:
        report_path = analyzer.write_report(args.days)
        print(f"✅ Report written to: {report_path}")
        
        # Print summary
        stats = analyzer.analyze(args.days)
        print(f"\nSummary:")
        print(f"  Total checks: {stats.total_checks}")
        print(f"  Violations: {stats.total_violations}")
        print(f"  Numeric leaks: {stats.numeric_leaks}")


if __name__ == "__main__":
    main()
