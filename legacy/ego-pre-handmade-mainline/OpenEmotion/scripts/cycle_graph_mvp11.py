#!/usr/bin/env python3
"""Build deterministic CycleGraph artifacts for MVP11.4."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from emotiond.science.cycle_graph import build_cycle_graph, save_cycle_graph


def _load_events(path: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    return events


def _infer_run_id(run_path: Path) -> str:
    # supports:
    # - artifacts/mvp11/<run_id>.jsonl
    # - artifacts/mvp11/<run_id>/run.jsonl
    if run_path.stem == "run" and run_path.parent.name:
        return run_path.parent.name
    return run_path.stem


def _resolve_run_paths(args: argparse.Namespace) -> List[Path]:
    paths: List[Path] = []
    if args.run:
        rp = Path(args.run)
        if not rp.exists():
            raise SystemExit(f"run file not found: {rp}")
        paths.append(rp)
    elif args.runs_dir:
        base = Path(args.runs_dir)
        if not base.exists():
            raise SystemExit(f"runs dir not found: {base}")
        # deterministic ordering
        top_level = sorted(base.glob("*.jsonl"))
        nested = sorted(base.glob("*/run.jsonl"))
        paths.extend(top_level)
        for p in nested:
            if p not in paths:
                paths.append(p)
    else:
        raise SystemExit("--run or --runs-dir is required")
    return paths


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=None, help="Path to run log jsonl")
    ap.add_argument("--runs-dir", default=None, help="Directory containing run logs")
    ap.add_argument("--artifacts-dir", default="artifacts/mvp11")
    ap.add_argument("--max-nodes", type=int, default=256)
    ap.add_argument("--max-edges", type=int, default=2048)
    ap.add_argument("--merge-global", action="store_true", help="Also build merged artifacts/mvp11/cycle_graph.json")
    args = ap.parse_args()

    run_paths = _resolve_run_paths(args)
    artifacts_dir = Path(args.artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    outputs: Dict[str, str] = {}
    merged_events: List[Dict[str, Any]] = []

    for run_path in run_paths:
        run_id = _infer_run_id(run_path)
        events = _load_events(run_path)
        graph = build_cycle_graph(events, max_nodes=args.max_nodes, max_edges=args.max_edges)
        run_out = artifacts_dir / run_id / "cycle_graph.json"
        save_cycle_graph(graph, run_out)
        outputs[run_id] = str(run_out)
        merged_events.extend(events)

    global_out = None
    if args.merge_global:
        merged_graph = build_cycle_graph(merged_events, max_nodes=args.max_nodes, max_edges=args.max_edges)
        global_out = artifacts_dir / "cycle_graph.json"
        save_cycle_graph(merged_graph, global_out)

    print(
        json.dumps(
            {
                "runs": [str(p) for p in run_paths],
                "outputs": outputs,
                "global_output": str(global_out) if global_out else None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
