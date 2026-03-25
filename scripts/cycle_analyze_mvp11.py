#!/usr/bin/env python3
"""Analyze cycle-closure structure from MVP11 run logs."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from emotiond.science.cycle import compute_cycle_candidates, compute_cycle_metrics, render_cycle_markdown
from emotiond.science.cycle_store import build_consolidated_cycles, save_cycle_store
from emotiond.science.concentration import compute_concentration, render_concentration_markdown


def load_events(path: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def _detect_seed(events: List[Dict[str, Any]]) -> int | None:
    for e in events:
        seed = e.get("seed")
        if isinstance(seed, int):
            return seed
    return None


def _detect_scenario(events: List[Dict[str, Any]]) -> str:
    for e in events:
        sid = e.get("scenario_id") or (e.get("cycle_bucket") or {}).get("scenario_id")
        if sid:
            return str(sid)
    return "global"


def analyze_run(
    run_id: str,
    artifacts_dir: Path,
    *,
    top_k: int,
    min_count: int,
    min_order_invariance: float,
    min_return_time_p50: float,
    max_return_time_p50: float,
    cycle_memory_path: Path,
    cycle_memory_max_entries: int,
    concentration_window: int = 100,
) -> Dict[str, Any]:
    log_path = artifacts_dir / f"{run_id}.jsonl"
    if not log_path.exists():
        raise FileNotFoundError(f"run log not found: {log_path}")

    events = load_events(log_path)
    metrics = compute_cycle_metrics(events)
    candidates = compute_cycle_candidates(
        events,
        top_k=top_k,
        min_count=min_count,
        min_order_invariance=min_order_invariance,
        min_return_time_p50=min_return_time_p50,
        max_return_time_p50=max_return_time_p50,
    )
    metrics["cycle_candidates_topK"] = candidates

    # Compute concentration metrics
    concentration_metrics = compute_concentration(events, rolling_window=concentration_window)

    run_dir = artifacts_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    json_path = run_dir / "cycle_report.json"
    md_path = run_dir / "cycle_report.md"
    concentration_json_path = run_dir / "concentration_report.json"
    concentration_md_path = run_dir / "concentration_report.md"

    sanity = metrics.get("sanity") or {}
    seed = _detect_seed(events)
    scenario_id = _detect_scenario(events)

    consolidation: Dict[str, Any]
    if sanity.get("status") == "OK":
        consolidated = build_consolidated_cycles(
            run_id=run_id,
            candidates=candidates,
            seed=seed,
            scenario_id=scenario_id,
            schema_version="mvp11.3.v1",
        )
        store_payload = save_cycle_store(
            consolidated,
            cycle_memory_path,
            run_id=run_id,
            sanity=sanity,
            source_report=str(json_path),
            max_entries=cycle_memory_max_entries,
        )
        consolidation = {
            "status": "written",
            "count": store_payload.get("count", 0),
            "path": str(cycle_memory_path),
            "evicted_entries": store_payload.get("evicted_entries", 0),
            "max_entries": store_payload.get("max_entries", cycle_memory_max_entries),
        }
    else:
        store_payload = save_cycle_store(
            [],
            cycle_memory_path,
            run_id=run_id,
            sanity=sanity,
            source_report=str(json_path),
            max_entries=cycle_memory_max_entries,
        )
        consolidation = {
            "status": "skipped_sanity_warn",
            "count": 0,
            "path": str(cycle_memory_path),
            "reason": "sanity.status != OK",
            "sanity": sanity,
            "store_count": store_payload.get("count", 0),
            "evicted_entries": store_payload.get("evicted_entries", 0),
            "max_entries": store_payload.get("max_entries", cycle_memory_max_entries),
        }

    report = {
        "run_id": run_id,
        "events": len(events),
        "source": str(log_path),
        "metrics": metrics,
        "sanity": sanity,
        "cycle_candidates_topK": candidates,
        "consolidation": consolidation,
        "ts": time.time(),
    }

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_cycle_markdown(run_id, metrics), encoding="utf-8")

    # Write concentration reports
    concentration_report = {
        "run_id": run_id,
        "events": len(events),
        "source": str(log_path),
        "concentration": concentration_metrics,
        "ts": time.time(),
    }
    concentration_json_path.write_text(
        json.dumps(concentration_report, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    concentration_md_path.write_text(
        render_concentration_markdown(concentration_metrics),
        encoding="utf-8"
    )

    return {
        "run_id": run_id,
        "report": report,
        "concentration_report": concentration_report,
        "paths": {
            "json": str(json_path),
            "md": str(md_path),
            "cycle_memory": str(cycle_memory_path),
            "concentration_json": str(concentration_json_path),
            "concentration_md": str(concentration_md_path),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--input", default=None, help="Direct path to <run_id>.jsonl")
    ap.add_argument("--artifacts-dir", default="artifacts/mvp11")

    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--min-count", type=int, default=3)
    ap.add_argument("--min-order-invariance", type=float, default=0.7)
    ap.add_argument("--min-return-time-p50", type=float, default=2.0)
    ap.add_argument("--max-return-time-p50", type=float, default=512.0)
    ap.add_argument("--cycle-memory-path", default="artifacts/mvp11/cycle_memory.json")
    ap.add_argument("--cycle-memory-max-entries", type=int, default=10000)
    ap.add_argument("--concentration-window", type=int, default=100, choices=[50, 100],
                    help="Rolling window for concentration metrics (50 or 100)")

    args = ap.parse_args()

    artifacts = Path(args.artifacts_dir)

    if args.input:
        log_path = Path(args.input)
        if not log_path.exists():
            raise SystemExit(f"input log not found: {log_path}")
        run_id = log_path.stem
        artifacts = log_path.parent
    else:
        if not args.run_id:
            raise SystemExit("--run-id required when --input is not set")
        run_id = args.run_id

    out = analyze_run(
        run_id,
        artifacts,
        top_k=args.top_k,
        min_count=args.min_count,
        min_order_invariance=args.min_order_invariance,
        min_return_time_p50=args.min_return_time_p50,
        max_return_time_p50=args.max_return_time_p50,
        cycle_memory_path=Path(args.cycle_memory_path),
        cycle_memory_max_entries=args.cycle_memory_max_entries,
        concentration_window=args.concentration_window,
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
