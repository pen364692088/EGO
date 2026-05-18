#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_ROOT = ROOT / "OpenEmotion" / "artifacts" / "mvp12"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate MVP12 controlled observation reports into a single stability summary."
    )
    parser.add_argument("--artifacts-root", default=str(ARTIFACTS_ROOT))
    parser.add_argument("--min-reports", type=int, default=3)
    parser.add_argument("--min-direct-real-windows", type=int, default=3)
    parser.add_argument("--min-span-hours", type=float, default=12.0)
    return parser.parse_args()


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def discover_reports(artifacts_root: Path) -> List[Dict[str, Any]]:
    reports: List[Dict[str, Any]] = []
    for report_path in sorted(artifacts_root.glob("controlled_*/controlled_observation_report.json")):
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        payload["report_path"] = str(report_path)
        payload["report_dir"] = str(report_path.parent)
        reports.append(payload)
    reports.sort(key=lambda item: item.get("generated_at") or "")
    return reports


def build_index_entries(reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for report in reports:
        entries.append(
            {
                "generated_at": report.get("generated_at"),
                "report_dir": report.get("report_dir"),
                "verification_level": report.get("verification_level"),
                "completion_class": report.get("completion_class"),
                "total_cycles": int(report.get("total_cycles") or 0),
                "direct_real_cycles": int(report.get("direct_real_cycles") or 0),
                "direct_real_window_count": int(report.get("direct_real_window_count") or 0),
                "governance_violation_count": int(report.get("governance_violation_count") or 0),
                "replay_consistent": bool(report.get("replay_consistent")),
                "unique_candidate_hash_sets": int(report.get("unique_candidate_hash_sets") or 0),
            }
        )
    return entries


def build_aggregate_summary(
    reports: List[Dict[str, Any]],
    *,
    min_reports: int,
    min_direct_real_windows: int,
    min_span_hours: float,
) -> Dict[str, Any]:
    entries = build_index_entries(reports)
    timestamps = [item for item in (_parse_iso8601(entry.get("generated_at")) for entry in entries) if item is not None]
    first_seen = min(timestamps) if timestamps else None
    last_seen = max(timestamps) if timestamps else None
    span_hours = 0.0
    if first_seen and last_seen:
        span_hours = max((last_seen - first_seen).total_seconds() / 3600.0, 0.0)

    total_reports = len(entries)
    direct_real_reports = sum(1 for entry in entries if entry["direct_real_cycles"] > 0)
    direct_real_cycles_total = sum(entry["direct_real_cycles"] for entry in entries)
    direct_real_windows_total = sum(entry["direct_real_window_count"] for entry in entries)
    governance_violation_total = sum(entry["governance_violation_count"] for entry in entries)
    replay_consistent_all = bool(entries) and all(entry["replay_consistent"] for entry in entries)
    unique_report_dates = sorted({str(entry.get("generated_at") or "")[:10] for entry in entries if entry.get("generated_at")})

    checks = {
        "min_reports": total_reports >= min_reports,
        "min_direct_real_windows": direct_real_windows_total >= min_direct_real_windows,
        "governance_violation_zero": governance_violation_total == 0,
        "replay_consistent_all": replay_consistent_all,
        "min_span_hours": span_hours >= min_span_hours,
    }

    return {
        "generated_at": datetime.now().isoformat(),
        "artifacts_root": str(ARTIFACTS_ROOT),
        "report_count": total_reports,
        "direct_real_report_count": direct_real_reports,
        "direct_real_cycles_total": direct_real_cycles_total,
        "direct_real_window_count_total": direct_real_windows_total,
        "governance_violation_total": governance_violation_total,
        "replay_consistent_all": replay_consistent_all,
        "unique_report_dates": unique_report_dates,
        "first_report_at": first_seen.isoformat() if first_seen else None,
        "last_report_at": last_seen.isoformat() if last_seen else None,
        "span_hours": round(span_hours, 3),
        "thresholds": {
            "min_reports": min_reports,
            "min_direct_real_windows": min_direct_real_windows,
            "min_span_hours": min_span_hours,
        },
        "stability_gate": {
            "status": "pass" if all(checks.values()) else "hold",
            "checks": checks,
        },
        "reports": entries,
    }


def render_markdown(summary: Dict[str, Any]) -> str:
    gate = summary["stability_gate"]
    checks = gate["checks"]
    lines = [
        "# MVP12 Controlled Observation Aggregate",
        "",
        f"- generated_at: `{summary['generated_at']}`",
        f"- artifacts_root: `{summary['artifacts_root']}`",
        f"- report_count: `{summary['report_count']}`",
        f"- direct_real_report_count: `{summary['direct_real_report_count']}`",
        f"- direct_real_cycles_total: `{summary['direct_real_cycles_total']}`",
        f"- direct_real_window_count_total: `{summary['direct_real_window_count_total']}`",
        f"- governance_violation_total: `{summary['governance_violation_total']}`",
        f"- replay_consistent_all: `{summary['replay_consistent_all']}`",
        f"- span_hours: `{summary['span_hours']}`",
        f"- gate_status: `{gate['status']}`",
        "",
        "## Gate Checks",
        "",
        f"- [{'x' if checks['min_reports'] else ' '}] min_reports",
        f"- [{'x' if checks['min_direct_real_windows'] else ' '}] min_direct_real_windows",
        f"- [{'x' if checks['governance_violation_zero'] else ' '}] governance_violation_zero",
        f"- [{'x' if checks['replay_consistent_all'] else ' '}] replay_consistent_all",
        f"- [{'x' if checks['min_span_hours'] else ' '}] min_span_hours",
        "",
        "## Reports",
        "",
    ]
    for report in summary["reports"]:
        lines.extend(
            [
                f"### {Path(report['report_dir']).name}",
                f"- generated_at: `{report['generated_at']}`",
                f"- direct_real_cycles: `{report['direct_real_cycles']}`",
                f"- direct_real_window_count: `{report['direct_real_window_count']}`",
                f"- governance_violation_count: `{report['governance_violation_count']}`",
                f"- replay_consistent: `{report['replay_consistent']}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Interpretation",
            "",
            "- This aggregate is for controlled observation only.",
            "- `pass` means the current controlled evidence thresholds are met.",
            "- It still does not imply live reply or execution authority handoff.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(artifacts_root: Path, summary: Dict[str, Any]) -> Dict[str, Path]:
    index_path = artifacts_root / "observation_index.jsonl"
    aggregate_json = artifacts_root / "controlled_observation_aggregate_current.json"
    aggregate_md = artifacts_root / "controlled_observation_aggregate_current.md"

    index_lines = [json.dumps(report, ensure_ascii=False) for report in summary["reports"]]
    index_path.write_text("\n".join(index_lines) + ("\n" if index_lines else ""), encoding="utf-8")
    aggregate_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    aggregate_md.write_text(render_markdown(summary), encoding="utf-8")
    return {
        "index_path": index_path,
        "aggregate_json": aggregate_json,
        "aggregate_md": aggregate_md,
    }


def main() -> int:
    args = parse_args()
    artifacts_root = Path(args.artifacts_root)
    reports = discover_reports(artifacts_root)
    summary = build_aggregate_summary(
        reports,
        min_reports=args.min_reports,
        min_direct_real_windows=args.min_direct_real_windows,
        min_span_hours=args.min_span_hours,
    )
    outputs = write_outputs(artifacts_root, summary)
    summary["outputs"] = {key: str(value) for key, value in outputs.items()}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
