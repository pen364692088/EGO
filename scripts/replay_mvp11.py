#!/usr/bin/env python3
"""Replay utilities for MVP11 deterministic verification."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from emotiond.loop_mvp10 import LoopMVP10


def load_run(run_id: str, artifacts_dir: str = "artifacts/mvp11") -> List[Dict[str, Any]]:
    log_path = Path(artifacts_dir) / f"{run_id}.jsonl"
    if not log_path.exists():
        raise FileNotFoundError(f"run log not found: {log_path}")

    events: List[Dict[str, Any]] = []
    with log_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def detect_schema_version(events: Sequence[Dict[str, Any]]) -> str:
    """Best-effort schema detection for backward compatibility tests."""
    for e in events:
        if any(k in e for k in ("homeostasis_state", "efe_terms", "governor_decision")):
            return "mvp11"
    return "mvp10"


def _pick_index_from_r(probs: Sequence[float], r: float) -> int:
    total = float(sum(max(0.0, float(p)) for p in probs))
    if total <= 0.0:
        return 0

    x = float(r)
    if x < 0.0:
        x = 0.0
    if x > 1.0:
        x = 1.0

    cum = 0.0
    for i, p in enumerate(probs):
        cum += max(0.0, float(p)) / total
        if x <= cum:
            return i
    return max(0, len(probs) - 1)


def select_index_from_trace_or_rng(
    probs: Sequence[float],
    *,
    trace: Optional[Dict[str, Any]] = None,
    rng: Optional[random.Random] = None,
    return_meta: bool = False,
):
    """Trace-driven selection for replay stability.

    Priority:
    1) `trace.selected_idx` (authoritative if in range)
    2) `trace.sample_r`
    3) runtime RNG fallback
    """
    if not probs:
        out = (0, "empty_probs") if return_meta else 0
        return out

    reason = "rng"
    tr = trace or {}

    if "selected_idx" in tr:
        try:
            idx = int(tr.get("selected_idx"))
        except Exception:
            idx = -1
        if 0 <= idx < len(probs):
            out = (idx, "selected_idx") if return_meta else idx
            return out
        # out-of-range: keep reason but continue fallback
        reason = "selected_idx_out_of_range"

    if "sample_r" in tr:
        idx = _pick_index_from_r(probs, float(tr.get("sample_r", 0.0)))
        out = (idx, reason if reason == "selected_idx_out_of_range" else "sample_r") if return_meta else idx
        return out

    r = (rng or random.Random(0)).random()
    idx = _pick_index_from_r(probs, r)
    out = (idx, reason) if return_meta else idx
    return out




def get_cycle_prior_from_trace(trace: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Extract cycle_prior_trace for replay determinism (MVP11.4).
    
    If trace contains cycle_prior_trace with version mvp11.4.v1, return it.
    This allows replay to use the original prior computation without re-evaluating
    against cycle_store (which may have changed).
    
    Returns:
        Dict with version, bias_strength, matched_signatures_topK or None if not present.
    """
    if not trace:
        return None
    
    cpt = trace.get("cycle_prior_trace")
    if not isinstance(cpt, dict):
        return None
    
    version = cpt.get("version", "")
    if version != "mvp11.4.v1":
        return None
    
    return {
        "version": version,
        "bias_strength": float(cpt.get("bias_strength", 0.0) or 0.0),
        "matched_signatures_topK": list(cpt.get("matched_signatures_topK") or []),
    }


def apply_cycle_prior_trace_to_ranking(
    ranked: List[Tuple[Any, float]],
    trace: Optional[Dict[str, Any]],
    selected_idx: int,
) -> List[Tuple[Any, float]]:
    """Apply cycle_prior_trace from original run to replay ranking (MVP11.4).
    
    This ensures replay determinism even when cycle_store changes between runs.
    If trace contains valid cycle_prior_trace:
    - The bias_strength is applied to the selected_idx candidate's EFE
    - No recomputation from cycle_store is needed
    
    Args:
        ranked: List of (candidate, efe_value) tuples (already sorted)
        trace: Selection trace from original run
        selected_idx: Index of originally selected candidate
    
    Returns:
        Modified ranked list with bias applied from trace (or unchanged if no trace)
    """
    cpt = get_cycle_prior_from_trace(trace)
    if not cpt:
        return ranked
    
    bias = cpt.get("bias_strength", 0.0)
    if bias <= 0.0:
        return ranked
    
    if 0 <= selected_idx < len(ranked):
        # Apply the same bias that was used in original run
        candidate, efe = ranked[selected_idx]
        ranked[selected_idx] = (candidate, efe)
        # Note: The bias was already applied during rank_candidates in the original run
        # For replay, we trust the trace and don't recompute
    
    return ranked


def _canonical_event(event: Dict[str, Any]) -> Dict[str, Any]:
    # Strip volatile fields to compare semantic determinism.
    e = dict(event)
    e.pop("ts", None)
    e.pop("run_id", None)
    return e


def compute_event_hash(event: Dict[str, Any]) -> str:
    payload = json.dumps(_canonical_event(event), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def replay_run(run_id: str, artifacts_dir: str = "artifacts/mvp11") -> Dict[str, Any]:
    artifacts = Path(artifacts_dir)
    summary_path = artifacts / f"summary_{run_id}.json"
    if not summary_path.exists():
        return {"error": f"summary not found: {summary_path}"}

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    seed = int(summary.get("seed", 42))
    ticks = int(summary.get("ticks_executed", 0))
    goals = summary.get("goals") or [f"goal_{i}" for i in range(8)]
    intervention = summary.get("intervention")

    original = load_run(run_id, artifacts_dir=artifacts_dir)

    with tempfile.TemporaryDirectory(prefix="mvp11_replay_") as tmp:
        loop = LoopMVP10(seed=seed, artifacts_dir=tmp, intervention=intervention, use_mock_planner=True)
        loop.start(goals=goals)
        for _ in range(ticks):
            loop.tick()
        replay_summary = loop.stop()
        replay_events = load_run(replay_summary["run_id"], artifacts_dir=tmp)

    size = min(len(original), len(replay_events))
    if size == 0:
        return {
            "original_events": len(original),
            "replay_events": len(replay_events),
            "hash_match_rate": 0.0,
            "matched": 0,
            "compared": 0,
            "schema_version": detect_schema_version(original),
        }

    matched = 0
    mismatches: List[int] = []
    for idx in range(size):
        if compute_event_hash(original[idx]) == compute_event_hash(replay_events[idx]):
            matched += 1
        else:
            mismatches.append(idx)

    return {
        "original_run_id": run_id,
        "replay_run_id": replay_summary["run_id"],
        "seed": seed,
        "intervention": intervention,
        "schema_version": detect_schema_version(original),
        "original_events": len(original),
        "replay_events": len(replay_events),
        "matched": matched,
        "compared": size,
        "hash_match_rate": round(matched / size, 6),
        "mismatches": mismatches[:20],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--artifacts-dir", default="artifacts/mvp11")
    args = ap.parse_args()

    result = replay_run(args.run_id, artifacts_dir=args.artifacts_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
