#!/usr/bin/env python3
"""
MVP-10 Replay Engine

Replay a previous run deterministically:
- Load events from JSONL
- Compare outcomes with original
- Verify determinism
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.loop_mvp10 import LoopMVP10, run_mvp10
from emotiond.science.ledger import Ledger


def load_run(run_id: str, artifacts_dir: str = "artifacts/mvp10") -> List[Dict[str, Any]]:
    """Load events from a previous run."""
    ledger = Ledger(artifacts_dir=artifacts_dir)
    return ledger.load_run(run_id)


def load_summary(run_id: str, artifacts_dir: str = "artifacts/mvp10") -> Dict[str, Any]:
    """Load summary metadata for a previous run when available."""
    summary_path = Path(artifacts_dir) / f"summary_{run_id}.json"
    if not summary_path.exists():
        return {}
    return json.loads(summary_path.read_text(encoding="utf-8"))


def extract_run_params(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract run parameters from events."""
    if not events:
        return {}

    first_event = events[0]
    return {
        "seed": first_event.get("seed", 0),
        "run_id": first_event.get("run_id", ""),
        "initial_goals": [],  # Will be extracted from candidates
    }


def extract_goals(events: List[Dict[str, Any]], summary: Optional[Dict[str, Any]] = None) -> List[str]:
    """Extract original goals with summary-first fallback."""
    if summary:
        summary_goals = summary.get("goals", [])
        if isinstance(summary_goals, list) and summary_goals:
            return [str(goal) for goal in summary_goals]

    goals: List[str] = []
    for event in events:
        candidates = event.get("candidates", [])
        for candidate in candidates:
            meta = candidate.get("meta", {})
            goal = meta.get("goal") if isinstance(meta, dict) else None
            if goal and goal not in goals:
                goals.append(goal)

        chosen_focus = event.get("chosen_focus")
        if chosen_focus and chosen_focus not in goals:
            goals.append(chosen_focus)

    return goals


def compare_event_streams(
    original_events: List[Dict[str, Any]],
    replay_events: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Compare deterministic fields while ignoring expected run metadata drift."""
    mismatches: List[Dict[str, Any]] = []

    if len(original_events) != len(replay_events):
        mismatches.append(
            {
                "tick": None,
                "field": "event_count",
                "original": len(original_events),
                "replay": len(replay_events),
            }
        )

    keys_to_compare = ("chosen_focus", "chosen_intent", "action", "outcome")
    for tick_index, (original_event, replay_event) in enumerate(zip(original_events, replay_events)):
        for key in keys_to_compare:
            original_value = original_event.get(key)
            replay_value = replay_event.get(key)
            if original_value != replay_value:
                mismatches.append(
                    {
                        "tick": tick_index,
                        "field": key,
                        "original": original_value,
                        "replay": replay_value,
                    }
                )

    return mismatches


def replay_run(
    run_id: str,
    artifacts_dir: str = "artifacts/mvp10",
    verbose: bool = False,
) -> Dict[str, Any]:
    """Replay a run and verify determinism."""
    # Load original events
    original_events = load_run(run_id, artifacts_dir)

    if not original_events:
        return {"error": f"No events found for run {run_id}"}

    # Extract parameters
    params = extract_run_params(original_events)
    summary = load_summary(run_id, artifacts_dir)
    seed = summary.get("seed", params["seed"])

    if verbose:
        print(f"Replaying run {run_id} with seed {seed}")
        print(f"Original events: {len(original_events)}")

    goals = extract_goals(original_events, summary)

    if verbose:
        print(f"Goals: {goals}")

    # Replay the run
    loop = LoopMVP10(seed=seed, artifacts_dir=artifacts_dir, use_mock_planner=True)
    new_run_id = loop.start(goals=goals)

    if verbose:
        print(f"New run ID: {new_run_id}")

    try:
        for _ in original_events:
            loop.tick()
    except Exception as exc:
        return {
            "original_run_id": run_id,
            "replay_run_id": new_run_id,
            "original_events": len(original_events),
            "replay_events": 0,
            "mismatches": [
                {
                    "tick": loop.ticks_executed,
                    "field": "error",
                    "original": "success",
                    "replay": str(exc),
                }
            ],
            "deterministic": False,
            "summary": None,
        }

    replay_summary = loop.stop()
    replay_events = load_run(new_run_id, artifacts_dir)
    mismatches = compare_event_streams(original_events, replay_events)

    return {
        "original_run_id": run_id,
        "replay_run_id": new_run_id,
        "original_events": len(original_events),
        "replay_events": len(replay_events),
        "mismatches": mismatches,
        "deterministic": len(mismatches) == 0,
        "summary": replay_summary,
    }


def compare_runs(
    run_id1: str,
    run_id2: str,
    artifacts_dir: str = "artifacts/mvp10",
) -> Dict[str, Any]:
    """Compare two runs for equality."""
    events1 = load_run(run_id1, artifacts_dir)
    events2 = load_run(run_id2, artifacts_dir)
    differences = compare_event_streams(events1, events2)

    return {
        "run_id1": run_id1,
        "run_id2": run_id2,
        "events1": len(events1),
        "events2": len(events2),
        "differences": differences,
        "equal": len(differences) == 0,
    }


def main():
    parser = argparse.ArgumentParser(description="MVP-10 Replay Engine")
    parser.add_argument("run_id", help="Run ID to replay")
    parser.add_argument("--artifacts-dir", default="artifacts/mvp10", help="Artifacts directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--compare", help="Compare with another run ID")

    args = parser.parse_args()

    if args.compare:
        result = compare_runs(args.run_id, args.compare, args.artifacts_dir)
    else:
        result = replay_run(args.run_id, args.artifacts_dir, args.verbose)

    print(json.dumps(result, indent=2))

    # Exit with error if not deterministic
    if not result.get("deterministic", result.get("equal", False)):
        sys.exit(1)


if __name__ == "__main__":
    main()
