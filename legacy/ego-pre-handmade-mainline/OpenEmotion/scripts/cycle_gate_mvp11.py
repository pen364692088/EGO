#!/usr/bin/env python3
"""Evaluate MVP11.3 cycle gates (Gate-1/2/3) from profile artifacts."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List


def _load_json(path: str | None) -> Dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"missing file: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _gate1(profile: Dict[str, Any], min_ok_rate: float) -> Dict[str, Any]:
    p = profile.get("profile") or {}
    ok_rate = float(p.get("sanity_ok_coverage", 0.0) or 0.0)
    counts = p.get("sanity_status_counts") or {}

    return {
        "name": "Gate-1 Sanity OK Coverage",
        "target": f"sanity_ok_coverage >= {min_ok_rate}",
        "observed": ok_rate,
        "status_counts": counts,
        "pass": ok_rate >= min_ok_rate,
    }


def _gate2(effects: Dict[str, Any]) -> Dict[str, Any]:
    if not effects:
        return {
            "name": "Gate-2 Intervention Direction Stability",
            "target": "structural_assertions all pass",
            "observed": "missing effects input",
            "pass": False,
            "reason": "effects_json_required",
        }

    rows: List[Dict[str, Any]] = effects.get("structural_assertions") or []
    if not rows:
        return {
            "name": "Gate-2 Intervention Direction Stability",
            "target": "structural_assertions all pass",
            "observed": "no assertions",
            "pass": False,
            "reason": "empty_assertions",
        }

    passed = sum(1 for r in rows if bool(r.get("pass")))
    total = len(rows)
    ratio = passed / total if total else 0.0

    return {
        "name": "Gate-2 Intervention Direction Stability",
        "target": "assertion pass ratio == 1.0",
        "observed": ratio,
        "passed": passed,
        "total": total,
        "pass": passed == total,
    }


def _gate3(ab_report: Dict[str, Any], *, require_gate3: bool, max_governor_delta: float, max_drift_delta: float) -> Dict[str, Any]:
    if not require_gate3:
        return {
            "name": "Gate-3 Main KPI Non-Degradation",
            "target": "C3 ON/OFF AB (skipped when C3 disabled)",
            "observed": "SKIPPED_C3_OFF",
            "pass": True,
            "skipped": True,
        }

    if not ab_report:
        return {
            "name": "Gate-3 Main KPI Non-Degradation",
            "target": "task_success_delta>=0 and governor/homeostasis not degraded",
            "observed": "missing ab report",
            "pass": False,
            "reason": "ab_report_required",
        }

    task_success_delta = float(ab_report.get("task_success_delta", 0.0) or 0.0)
    governor_delta = float(ab_report.get("governor_block_rate_delta", 0.0) or 0.0)
    drift_delta = float(ab_report.get("homeostasis_drift_mean_delta", 0.0) or 0.0)

    ok = task_success_delta >= 0.0 and governor_delta <= max_governor_delta and drift_delta <= max_drift_delta

    return {
        "name": "Gate-3 Main KPI Non-Degradation",
        "target": {
            "task_success_delta": ">= 0",
            "governor_block_rate_delta": f"<= {max_governor_delta}",
            "homeostasis_drift_mean_delta": f"<= {max_drift_delta}",
        },
        "observed": {
            "task_success_delta": task_success_delta,
            "governor_block_rate_delta": governor_delta,
            "homeostasis_drift_mean_delta": drift_delta,
        },
        "pass": ok,
    }


def _render_md(payload: Dict[str, Any]) -> str:
    lines = [
        "# MVP11.3 Cycle Gate Report",
        "",
        f"- overall_pass: `{payload.get('overall_pass')}`",
        f"- ts: `{payload.get('ts')}`",
        "",
    ]

    for g in payload.get("gates", []):
        icon = "✅" if g.get("pass") else "❌"
        lines.extend(
            [
                f"## {icon} {g.get('name')}",
                "",
                f"- target: `{g.get('target')}`",
                f"- observed: `{g.get('observed')}`",
                f"- pass: `{g.get('pass')}`",
                "",
            ]
        )

    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--effects", default=None)
    ap.add_argument("--ab-report", default=None)
    ap.add_argument("--output", default="artifacts/mvp11/profiles/cycle_gate_report.json")
    ap.add_argument("--markdown", default="artifacts/mvp11/profiles/cycle_gate_report.md")
    ap.add_argument("--min-sanity-ok-rate", type=float, default=0.99)
    ap.add_argument("--require-gate3", type=int, default=0)
    ap.add_argument("--max-governor-delta", type=float, default=0.01)
    ap.add_argument("--max-drift-delta", type=float, default=0.01)
    args = ap.parse_args()

    profile = _load_json(args.profile)
    effects = _load_json(args.effects)
    ab_report = _load_json(args.ab_report)

    gates = [
        _gate1(profile, args.min_sanity_ok_rate),
        _gate2(effects),
        _gate3(
            ab_report,
            require_gate3=bool(args.require_gate3),
            max_governor_delta=args.max_governor_delta,
            max_drift_delta=args.max_drift_delta,
        ),
    ]

    overall_pass = all(bool(g.get("pass")) for g in gates)

    payload = {
        "schema_version": "mvp11.cycle_gate.v1",
        "ts": time.time(),
        "overall_pass": overall_pass,
        "gates": gates,
        "inputs": {
            "profile": args.profile,
            "effects": args.effects,
            "ab_report": args.ab_report,
        },
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = Path(args.markdown)
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(_render_md(payload), encoding="utf-8")

    print(json.dumps({"output": str(out), "overall_pass": overall_pass}, ensure_ascii=False, indent=2))
    if not overall_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
