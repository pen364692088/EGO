#!/usr/bin/env python3
"""Shadow Period Results Summarizer.

Aggregates 20-30 CI runs of hard gate results into a statistical report.

Input: Directory containing multiple `hard_gate_summary.json` or `hard_gate_one_liner.txt` files
Output: `shadow_period_summary.json` + `shadow_period_summary.md`

Content:
- ERROR/WARN count distribution
- WARN reason distribution (top1 exceeded, unique too low, sanity soft fail, etc.)
- Observed distribution per metric (mean/p95)
- Upgrade recommendation (can ERROR become hard block?)

Usage:
    # Summarize all hard gate results in a directory
    python scripts/summarize_shadow_results.py --input-dir reports/shadow_runs/

    # Specify output location
    python scripts/summarize_shadow_results.py \
        --input-dir reports/shadow_runs/ \
        --out-json reports/shadow_period_summary.json \
        --out-md reports/shadow_period_summary.md

    # With minimum run threshold
    python scripts/summarize_shadow_results.py \
        --input-dir reports/shadow_runs/ \
        --min-runs 10

One-Liner Format (hard_gate_one_liner.txt):
    ERROR:0|WARN:3|PASS:4|UNKNOWN:0|should_fail:false|ts:1772724703
    
    Or for individual gates:
    replay_hash_match:PASS|sanity_consecutive:PASS|concentration_consecutive:WARN:bias_high|bias_consecutive:PASS
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class GateResult:
    """Single gate result from a CI run."""
    gate_name: str
    status: str  # PASS, FAIL, WARN, ERROR, UNKNOWN, SKIP
    should_fail: bool
    reason: str = ""
    observed: Optional[float] = None
    threshold: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_name": self.gate_name,
            "status": self.status,
            "should_fail": self.should_fail,
            "reason": self.reason,
            "observed": self.observed,
            "threshold": self.threshold,
        }


@dataclass
class RunResult:
    """Single CI run result."""
    run_id: str
    ts: float
    source_file: str
    overall_status: str
    should_fail: bool
    gates: List[GateResult]
    entries_analyzed: int = 0
    mode: str = "shadow"
    
    @property
    def error_count(self) -> int:
        return sum(1 for g in self.gates if g.status == "ERROR")
    
    @property
    def warn_count(self) -> int:
        return sum(1 for g in self.gates if g.status == "WARN")
    
    @property
    def fail_count(self) -> int:
        return sum(1 for g in self.gates if g.status == "FAIL")
    
    @property
    def pass_count(self) -> int:
        return sum(1 for g in self.gates if g.status == "PASS")
    
    @property
    def unknown_count(self) -> int:
        return sum(1 for g in self.gates if g.status in ("UNKNOWN", "SKIP"))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "ts": self.ts,
            "source_file": self.source_file,
            "overall_status": self.overall_status,
            "should_fail": self.should_fail,
            "gates": [g.to_dict() for g in self.gates],
            "entries_analyzed": self.entries_analyzed,
            "mode": self.mode,
            "counts": {
                "error": self.error_count,
                "warn": self.warn_count,
                "fail": self.fail_count,
                "pass": self.pass_count,
                "unknown": self.unknown_count,
            },
        }


@dataclass
class MetricObservation:
    """Observed values for a single metric across runs."""
    gate_name: str
    metric_name: str  # "observed" or "threshold"
    values: List[float] = field(default_factory=list)
    
    def add(self, value: float) -> None:
        if value is not None:
            self.values.append(value)
    
    @property
    def count(self) -> int:
        return len(self.values)
    
    @property
    def mean(self) -> Optional[float]:
        if not self.values:
            return None
        return sum(self.values) / len(self.values)
    
    @property
    def min(self) -> Optional[float]:
        return min(self.values) if self.values else None
    
    @property
    def max(self) -> Optional[float]:
        return max(self.values) if self.values else None
    
    @property
    def p95(self) -> Optional[float]:
        if not self.values:
            return None
        sorted_vals = sorted(self.values)
        idx = int(len(sorted_vals) * 0.95)
        return sorted_vals[min(idx, len(sorted_vals) - 1)]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_name": self.gate_name,
            "metric_name": self.metric_name,
            "count": self.count,
            "mean": self.mean,
            "min": self.min,
            "max": self.max,
            "p95": self.p95,
        }


@dataclass
class UpgradeRecommendation:
    """Recommendation for upgrading a gate from WARN to hard block."""
    gate_name: str
    current_status: str  # "WARN" or "ERROR"
    recommendation: str  # "promote_to_block", "keep_warn", "insufficient_data"
    confidence: str  # "high", "medium", "low"
    rationale: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_name": self.gate_name,
            "current_status": self.current_status,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "evidence": self.evidence,
        }


@dataclass
class ShadowPeriodSummary:
    """Aggregated summary of shadow period results."""
    input_dir: str
    runs_analyzed: int
    runs_by_status: Dict[str, int]
    gate_status_distribution: Dict[str, Dict[str, int]]
    warn_reason_distribution: Dict[str, int]
    error_reason_distribution: Dict[str, int]
    metric_observations: Dict[str, MetricObservation]
    upgrade_recommendations: List[UpgradeRecommendation]
    run_details: List[RunResult]
    generated_at: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": "shadow_period_summary.v1",
            "generated_at": self.generated_at,
            "input_dir": self.input_dir,
            "runs_analyzed": self.runs_analyzed,
            "runs_by_status": self.runs_by_status,
            "gate_status_distribution": {
                k: v for k, v in self.gate_status_distribution.items()
            },
            "warn_reason_distribution": self.warn_reason_distribution,
            "error_reason_distribution": self.error_reason_distribution,
            "metric_observations": {
                k: v.to_dict() for k, v in self.metric_observations.items()
            },
            "upgrade_recommendations": [r.to_dict() for r in self.upgrade_recommendations],
            "run_details": [r.to_dict() for r in self.run_details],
        }


def parse_one_liner(content: str, filename: str) -> Optional[RunResult]:
    """Parse one-liner format: ERROR:0|WARN:3|PASS:4|UNKNOWN:0|should_fail:false|ts:123
    
    Alternative format:
    replay_hash_match:PASS|sanity_consecutive:WARN:reason|...
    """
    content = content.strip()
    if not content:
        return None
    
    # Try key:value format first
    parts = {}
    for part in content.split("|"):
        if ":" in part:
            key, val = part.split(":", 1)
            parts[key.strip()] = val.strip()
    
    # Extract basic counts
    error_count = int(parts.get("ERROR", parts.get("error", 0)))
    warn_count = int(parts.get("WARN", parts.get("warn", 0)))
    pass_count = int(parts.get("PASS", parts.get("pass", 0)))
    unknown_count = int(parts.get("UNKNOWN", parts.get("unknown", 0)))
    should_fail = parts.get("should_fail", "false").lower() == "true"
    ts = float(parts.get("ts", time.time()))
    
    # Check for gate-level details
    gates = []
    gate_names = ["replay_hash_match", "sanity_consecutive", "concentration_consecutive", "bias_consecutive"]
    
    for gate_name in gate_names:
        if gate_name in parts:
            gate_val = parts[gate_name]
            # Format: STATUS or STATUS:reason
            if ":" in gate_val:
                status, reason = gate_val.split(":", 1)
            else:
                status = gate_val
                reason = ""
            
            status = status.upper()
            gates.append(GateResult(
                gate_name=gate_name,
                status=status,
                should_fail=status == "FAIL",
                reason=reason,
            ))
    
    # If no gate-level details, create synthetic gates from counts
    if not gates:
        # Create placeholder gates based on counts
        if error_count > 0:
            gates.append(GateResult("unknown_gate", "ERROR", True, "error from one-liner"))
        for i in range(warn_count):
            gates.append(GateResult(f"warn_gate_{i}", "WARN", False, f"warning {i+1}"))
        for i in range(pass_count):
            gates.append(GateResult(f"pass_gate_{i}", "PASS", False))
    
    run_id = Path(filename).stem
    overall = "FAIL" if should_fail else "PASS"
    
    return RunResult(
        run_id=run_id,
        ts=ts,
        source_file=filename,
        overall_status=overall,
        should_fail=should_fail,
        gates=gates,
        mode="shadow",
    )


def parse_json_summary(data: Dict[str, Any], filename: str) -> Optional[RunResult]:
    """Parse hard_gate_summary.json or hard_gate_report.json format."""
    if not data:
        return None
    
    # Determine schema type
    schema = data.get("schema", data.get("schema_version", ""))
    
    # Extract gates
    gates = []
    gate_list = data.get("gates", [])
    
    for g in gate_list:
        gate_name = g.get("gate", g.get("gate_name", "unknown"))
        status = g.get("status", "UNKNOWN")
        should_fail = g.get("should_fail", False)
        reason = g.get("reason", "")
        
        # Extract observed value if available
        observed = g.get("observed", g.get("observed_value"))
        threshold = g.get("threshold", g.get("threshold_value"))
        
        # Try to parse numeric values
        if observed is not None:
            try:
                observed = float(observed)
            except (ValueError, TypeError):
                observed = None
        
        if threshold is not None:
            try:
                threshold = float(threshold)
            except (ValueError, TypeError):
                threshold = None
        
        gates.append(GateResult(
            gate_name=gate_name,
            status=status,
            should_fail=should_fail,
            reason=reason,
            observed=observed,
            threshold=threshold,
        ))
    
    # Extract metadata
    ts = data.get("ts", time.time())
    overall_status = data.get("overall_status", "UNKNOWN")
    should_fail = data.get("should_fail", False)
    entries_analyzed = data.get("entries_analyzed", 0)
    mode = data.get("mode", "shadow")
    
    run_id = Path(filename).stem
    
    return RunResult(
        run_id=run_id,
        ts=ts,
        source_file=filename,
        overall_status=overall_status,
        should_fail=should_fail,
        gates=gates,
        entries_analyzed=entries_analyzed,
        mode=mode,
    )


def load_run_results(input_dir: Path) -> List[RunResult]:
    """Load all run results from input directory."""
    results = []
    
    # Find all JSON files
    json_patterns = ["hard_gate_summary.json", "hard_gate_report.json", "*_summary.json", "*_report.json"]
    json_files = []
    
    for pattern in json_patterns:
        json_files.extend(input_dir.glob(pattern))
    
    # Also check subdirectories
    for f in input_dir.rglob("*.json"):
        if "hard_gate" in f.name or "summary" in f.name or "report" in f.name:
            json_files.append(f)
    
    # Deduplicate
    json_files = list(set(json_files))
    
    for json_file in json_files:
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            result = parse_json_summary(data, str(json_file))
            if result:
                results.append(result)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[WARN] Failed to parse {json_file}: {e}", file=sys.stderr, flush=True)
    
    # Find all one-liner files
    one_liner_patterns = ["hard_gate_one_liner.txt", "*_one_liner.txt", "one_liner.txt"]
    one_liner_files = []
    
    for pattern in one_liner_patterns:
        one_liner_files.extend(input_dir.glob(pattern))
    
    for f in input_dir.rglob("*.txt"):
        if "one_liner" in f.name:
            one_liner_files.append(f)
    
    # Deduplicate
    one_liner_files = list(set(one_liner_files))
    
    for one_liner_file in one_liner_files:
        try:
            content = one_liner_file.read_text(encoding="utf-8")
            result = parse_one_liner(content, str(one_liner_file))
            if result:
                results.append(result)
        except IOError as e:
            print(f"[WARN] Failed to read {one_liner_file}: {e}", file=sys.stderr, flush=True)
    
    # Sort by timestamp
    results.sort(key=lambda r: r.ts)
    
    return results


def extract_warn_reason(gate: GateResult) -> str:
    """Extract a standardized warn reason from a gate result."""
    reason = gate.reason.lower()
    gate_name = gate.gate_name
    
    # Standardized reason mapping
    if "top1" in reason or "concentration" in gate_name:
        if "exceed" in reason or ">" in reason:
            return "top1_exceeded"
        return "concentration_warn"
    
    if "unique" in reason:
        return "unique_too_low"
    
    if "sanity" in gate_name or "sanity" in reason:
        return "sanity_soft_fail"
    
    if "bias" in gate_name or "bias" in reason:
        return "bias_warn"
    
    if "hash" in reason or "replay" in gate_name:
        return "hash_mismatch"
    
    if "no entries" in reason or "no data" in reason:
        return "no_data"
    
    # Generic fallback
    return f"other:{gate_name}"


def extract_error_reason(gate: GateResult) -> str:
    """Extract a standardized error reason from a gate result."""
    reason = gate.reason.lower()
    gate_name = gate.gate_name
    
    if "hash" in reason or "replay" in gate_name:
        return "hash_mismatch_error"
    
    if "sanity" in gate_name:
        return "sanity_fail"
    
    if "concentration" in gate_name:
        return "concentration_fail"
    
    if "bias" in gate_name:
        return "bias_fail"
    
    return f"error:{gate_name}"


def compute_metric_observations(runs: List[RunResult]) -> Dict[str, MetricObservation]:
    """Compute metric observations across all runs."""
    observations: Dict[str, MetricObservation] = {}
    
    for run in runs:
        for gate in run.gates:
            # Track observed values
            if gate.observed is not None:
                key = f"{gate.gate_name}.observed"
                if key not in observations:
                    observations[key] = MetricObservation(gate.gate_name, "observed")
                observations[key].add(gate.observed)
            
            # Track threshold values
            if gate.threshold is not None:
                key = f"{gate.gate_name}.threshold"
                if key not in observations:
                    observations[key] = MetricObservation(gate.gate_name, "threshold")
                observations[key].add(gate.threshold)
    
    return observations


def compute_upgrade_recommendations(
    runs: List[RunResult],
    observations: Dict[str, MetricObservation],
) -> List[UpgradeRecommendation]:
    """Compute upgrade recommendations for gates with WARN/ERROR status."""
    recommendations = []
    
    # Group gates by name
    gate_results_by_name: Dict[str, List[GateResult]] = defaultdict(list)
    for run in runs:
        for gate in run.gates:
            gate_results_by_name[gate.gate_name].append(gate)
    
    for gate_name, gates in gate_results_by_name.items():
        # Count statuses
        warn_count = sum(1 for g in gates if g.status == "WARN")
        error_count = sum(1 for g in gates if g.status == "ERROR")
        fail_count = sum(1 for g in gates if g.status == "FAIL")
        total = len(gates)
        
        # Skip if no issues
        if warn_count == 0 and error_count == 0 and fail_count == 0:
            continue
        
        # Determine current status
        if fail_count > 0:
            current_status = "FAIL"
        elif error_count > 0:
            current_status = "ERROR"
        else:
            current_status = "WARN"
        
        # Compute failure rate
        issue_rate = (warn_count + error_count + fail_count) / total if total > 0 else 0
        
        # Get observed values
        obs_key = f"{gate_name}.observed"
        obs = observations.get(obs_key)
        
        # Decision logic
        if total < 10:
            recommendation = "insufficient_data"
            confidence = "low"
            rationale = f"Only {total} runs, need at least 10 for reliable recommendation"
        elif fail_count > 0:
            # Already a hard block
            recommendation = "already_blocked"
            confidence = "high"
            rationale = f"Gate already has {fail_count} FAIL status (hard block)"
        elif error_count > 0 and issue_rate > 0.3:
            # ERROR occurring frequently - consider promoting to hard block
            recommendation = "promote_to_block"
            confidence = "high" if issue_rate > 0.5 else "medium"
            rationale = f"ERROR in {error_count}/{total} runs ({issue_rate:.1%} issue rate)"
        elif warn_count > 0 and issue_rate > 0.5:
            # WARN very frequent - consider promoting
            recommendation = "promote_to_block"
            confidence = "medium"
            rationale = f"WARN in {warn_count}/{total} runs ({issue_rate:.1%} issue rate) - consider promoting"
        elif warn_count > 0:
            recommendation = "keep_warn"
            confidence = "high"
            rationale = f"WARN rate {issue_rate:.1%} is acceptable for monitoring"
        else:
            recommendation = "keep_warn"
            confidence = "medium"
            rationale = "No significant pattern detected"
        
        # Evidence
        evidence = {
            "total_runs": total,
            "warn_count": warn_count,
            "error_count": error_count,
            "fail_count": fail_count,
            "issue_rate": round(issue_rate, 4),
        }
        
        if obs:
            evidence["observed_mean"] = round(obs.mean, 4) if obs.mean else None
            evidence["observed_p95"] = round(obs.p95, 4) if obs.p95 else None
            evidence["observed_max"] = round(obs.max, 4) if obs.max else None
        
        recommendations.append(UpgradeRecommendation(
            gate_name=gate_name,
            current_status=current_status,
            recommendation=recommendation,
            confidence=confidence,
            rationale=rationale,
            evidence=evidence,
        ))
    
    return recommendations


def summarize_results(
    input_dir: Path,
    runs: List[RunResult],
) -> ShadowPeriodSummary:
    """Compute summary statistics from run results."""
    
    # Count runs by overall status
    runs_by_status = defaultdict(int)
    for run in runs:
        runs_by_status[run.overall_status] += 1
    
    # Gate status distribution
    gate_status_distribution: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for run in runs:
        for gate in run.gates:
            gate_status_distribution[gate.gate_name][gate.status] += 1
    
    # WARN reason distribution
    warn_reason_distribution: Dict[str, int] = defaultdict(int)
    for run in runs:
        for gate in run.gates:
            if gate.status == "WARN":
                reason = extract_warn_reason(gate)
                warn_reason_distribution[reason] += 1
    
    # ERROR reason distribution
    error_reason_distribution: Dict[str, int] = defaultdict(int)
    for run in runs:
        for gate in run.gates:
            if gate.status in ("ERROR", "FAIL"):
                reason = extract_error_reason(gate)
                error_reason_distribution[reason] += 1
    
    # Metric observations
    metric_observations = compute_metric_observations(runs)
    
    # Upgrade recommendations
    upgrade_recommendations = compute_upgrade_recommendations(runs, metric_observations)
    
    return ShadowPeriodSummary(
        input_dir=str(input_dir),
        runs_analyzed=len(runs),
        runs_by_status=dict(runs_by_status),
        gate_status_distribution={k: dict(v) for k, v in gate_status_distribution.items()},
        warn_reason_distribution=dict(warn_reason_distribution),
        error_reason_distribution=dict(error_reason_distribution),
        metric_observations=metric_observations,
        upgrade_recommendations=upgrade_recommendations,
        run_details=runs,
        generated_at=time.time(),
    )


def render_markdown(summary: ShadowPeriodSummary) -> str:
    """Render summary as markdown."""
    lines = [
        "# Shadow Period Summary Report",
        "",
        f"**Generated**: `{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(summary.generated_at))}`",
        f"**Input Directory**: `{summary.input_dir}`",
        f"**Runs Analyzed**: `{summary.runs_analyzed}`",
        "",
    ]
    
    # Runs by status
    lines.extend([
        "## Runs by Overall Status",
        "",
        "| Status | Count | Percentage |",
        "|--------|-------|------------|",
    ])
    
    total = summary.runs_analyzed
    for status, count in sorted(summary.runs_by_status.items(), key=lambda x: -x[1]):
        pct = f"{count/total*100:.1f}%" if total > 0 else "N/A"
        icon = "✅" if status == "PASS" else "🚨" if status in ("FAIL", "ERROR") else "⚠️"
        lines.append(f"| {icon} {status} | {count} | {pct} |")
    
    lines.append("")
    
    # Gate status distribution
    lines.extend([
        "## Gate Status Distribution",
        "",
        "| Gate | PASS | WARN | ERROR | FAIL | UNKNOWN |",
        "|------|------|------|-------|------|---------|",
    ])
    
    for gate_name, status_counts in sorted(summary.gate_status_distribution.items()):
        pass_c = status_counts.get("PASS", 0)
        warn_c = status_counts.get("WARN", 0)
        error_c = status_counts.get("ERROR", 0)
        fail_c = status_counts.get("FAIL", 0)
        unknown_c = status_counts.get("UNKNOWN", 0) + status_counts.get("SKIP", 0)
        lines.append(f"| {gate_name} | {pass_c} | {warn_c} | {error_c} | {fail_c} | {unknown_c} |")
    
    lines.append("")
    
    # WARN reason distribution
    if summary.warn_reason_distribution:
        lines.extend([
            "## WARN Reason Distribution",
            "",
            "| Reason | Count |",
            "|--------|-------|",
        ])
        
        for reason, count in sorted(summary.warn_reason_distribution.items(), key=lambda x: -x[1]):
            lines.append(f"| {reason} | {count} |")
        
        lines.append("")
    
    # ERROR reason distribution
    if summary.error_reason_distribution:
        lines.extend([
            "## ERROR Reason Distribution",
            "",
            "| Reason | Count |",
            "|--------|-------|",
        ])
        
        for reason, count in sorted(summary.error_reason_distribution.items(), key=lambda x: -x[1]):
            lines.append(f"| {reason} | {count} |")
        
        lines.append("")
    
    # Metric observations
    if summary.metric_observations:
        lines.extend([
            "## Metric Observations",
            "",
            "| Metric | Count | Mean | Min | Max | P95 |",
            "|--------|-------|------|-----|-----|-----|",
        ])
        
        for key, obs in sorted(summary.metric_observations.items()):
            mean_str = f"{obs.mean:.4f}" if obs.mean is not None else "N/A"
            min_str = f"{obs.min:.4f}" if obs.min is not None else "N/A"
            max_str = f"{obs.max:.4f}" if obs.max is not None else "N/A"
            p95_str = f"{obs.p95:.4f}" if obs.p95 is not None else "N/A"
            lines.append(f"| {key} | {obs.count} | {mean_str} | {min_str} | {max_str} | {p95_str} |")
        
        lines.append("")
    
    # Upgrade recommendations
    if summary.upgrade_recommendations:
        lines.extend([
            "## Upgrade Recommendations",
            "",
            "| Gate | Current | Recommendation | Confidence | Rationale |",
            "|------|---------|----------------|------------|-----------|",
        ])
        
        for rec in summary.upgrade_recommendations:
            rec_icon = "⬆️" if rec.recommendation == "promote_to_block" else "➖"
            lines.append(f"| {rec_icon} {rec.gate_name} | {rec.current_status} | {rec.recommendation} | {rec.confidence} | {rec.rationale} |")
        
        lines.append("")
        
        # Detailed recommendations
        lines.extend([
            "### Recommendation Details",
            "",
        ])
        
        for rec in summary.upgrade_recommendations:
            lines.append(f"#### {rec.gate_name}")
            lines.append("")
            lines.append(f"- **Current Status**: {rec.current_status}")
            lines.append(f"- **Recommendation**: {rec.recommendation}")
            lines.append(f"- **Confidence**: {rec.confidence}")
            lines.append(f"- **Rationale**: {rec.rationale}")
            
            if rec.evidence:
                lines.append("- **Evidence**:")
                for k, v in rec.evidence.items():
                    if v is not None:
                        lines.append(f"  - {k}: {v}")
            
            lines.append("")
    
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Summarize Shadow Period Hard Gate Results")
    ap.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing hard_gate_summary.json or hard_gate_one_liner.txt files",
    )
    ap.add_argument(
        "--out-json",
        default=None,
        help="Output JSON file (default: <input-dir>/shadow_period_summary.json)",
    )
    ap.add_argument(
        "--out-md",
        default=None,
        help="Output Markdown file (default: <input-dir>/shadow_period_summary.md)",
    )
    ap.add_argument(
        "--min-runs",
        type=int,
        default=5,
        help="Minimum number of runs required (default: 5, warn if below)",
    )
    ap.add_argument(
        "--include-details",
        action="store_true",
        help="Include individual run details in output JSON",
    )
    args = ap.parse_args()
    
    input_dir = Path(args.input_dir)
    
    if not input_dir.exists():
        print(f"[ERROR] Input directory does not exist: {input_dir}", file=sys.stderr, flush=True)
        sys.exit(1)
    
    if not input_dir.is_dir():
        print(f"[ERROR] Input path is not a directory: {input_dir}", file=sys.stderr, flush=True)
        sys.exit(1)
    
    # Load run results
    print(f"[INFO] Loading run results from: {input_dir}", flush=True)
    runs = load_run_results(input_dir)
    
    print(f"[INFO] Loaded {len(runs)} run results", flush=True)
    
    if len(runs) < args.min_runs:
        print(f"[WARN] Only {len(runs)} runs found, recommended minimum is {args.min_runs}", file=sys.stderr, flush=True)
    
    if not runs:
        print(f"[ERROR] No valid run results found in {input_dir}", file=sys.stderr, flush=True)
        sys.exit(1)
    
    # Compute summary
    summary = summarize_results(input_dir, runs)
    
    # Determine output paths
    out_json = Path(args.out_json) if args.out_json else input_dir / "shadow_period_summary.json"
    out_md = Path(args.out_md) if args.out_md else input_dir / "shadow_period_summary.md"
    
    # Prepare output data
    output_data = summary.to_dict()
    if not args.include_details:
        output_data.pop("run_details", None)
    
    # Write JSON
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(output_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[INFO] JSON summary written to: {out_json}", flush=True)
    
    # Write Markdown
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(summary), encoding="utf-8")
    print(f"[INFO] Markdown summary written to: {out_md}", flush=True)
    
    # Print summary to stdout
    print("\n" + "=" * 60, flush=True)
    print("Shadow Period Summary", flush=True)
    print("=" * 60, flush=True)
    print(f"Runs Analyzed:     {summary.runs_analyzed}", flush=True)
    print(f"Runs by Status:    {dict(summary.runs_by_status)}", flush=True)
    
    if summary.warn_reason_distribution:
        print(f"WARN Reasons:      {dict(summary.warn_reason_distribution)}", flush=True)
    
    if summary.error_reason_distribution:
        print(f"ERROR Reasons:     {dict(summary.error_reason_distribution)}", flush=True)
    
    promote_count = sum(1 for r in summary.upgrade_recommendations if r.recommendation == "promote_to_block")
    if promote_count > 0:
        print(f"\n⬆️  {promote_count} gate(s) recommended for promotion to hard block", flush=True)
    
    print("=" * 60 + "\n", flush=True)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
