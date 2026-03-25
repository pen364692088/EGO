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
    seed = params["seed"]
    
    if verbose:
        print(f"Replaying run {run_id} with seed {seed}")
        print(f"Original events: {len(original_events)}")
    
    # Extract goals from first event
    goals = []
    for event in original_events:
        candidates = event.get("candidates", [])
        for c in candidates:
            # Check for goal in meta
            meta = c.get("meta", {})
            if meta and "goal" in meta:
                goal = meta["goal"]
                if goal not in goals:
                    goals.append(goal)
            # Also check if candidate type is "goal" and use id as goal
            elif c.get("type") == "goal":
                goal_from_id = c.get("id", "").replace("goal_", "")
                if goal_from_id and goal_from_id not in goals:
                    # Use chosen_focus from event as the actual goal
                    pass
    
    # If no goals extracted from candidates, use chosen_focus from first event
    if not goals and original_events:
        first_focus = original_events[0].get("chosen_focus")
        if first_focus:
            goals.append(first_focus)
    
    if verbose:
        print(f"Goals: {goals}")
    
    # Replay the run
    loop = LoopMVP10(seed=seed, artifacts_dir=artifacts_dir, use_mock_planner=True)
    loop.state.goals = goals.copy()
    
    # Start the run
    new_run_id = loop.start(goals=goals)
    
    if verbose:
        print(f"New run ID: {new_run_id}")
    
    # Replay tick by tick
    mismatches = []
    new_events = []
    
    for i, original_event in enumerate(original_events):
        try:
            result = loop.tick()
            
            # Get the logged event
            if loop.ledger.events:
                new_event = loop.ledger.events[-1]
                new_events.append(new_event.to_dict())
                
                # Compare key fields
                if original_event.get("chosen_focus") != new_event.chosen_focus:
                    mismatches.append({
                        "tick": i,
                        "field": "chosen_focus",
                        "original": original_event.get("chosen_focus"),
                        "replay": new_event.chosen_focus,
                    })
                
                if original_event.get("chosen_intent") != new_event.chosen_intent:
                    mismatches.append({
                        "tick": i,
                        "field": "chosen_intent",
                        "original": original_event.get("chosen_intent"),
                        "replay": new_event.chosen_intent,
                    })
                
                if verbose:
                    print(f"Tick {i}: focus={new_event.chosen_focus}, outcome={new_event.outcome.status}")
        
        except Exception as e:
            mismatches.append({
                "tick": i,
                "field": "error",
                "original": "success",
                "replay": str(e),
            })
            break
    
    # Stop the run
    summary = loop.stop()
    
    return {
        "original_run_id": run_id,
        "replay_run_id": new_run_id,
        "original_events": len(original_events),
        "replay_events": len(new_events),
        "mismatches": mismatches,
        "deterministic": len(mismatches) == 0,
        "summary": summary,
    }


def compare_runs(
    run_id1: str,
    run_id2: str,
    artifacts_dir: str = "artifacts/mvp10",
) -> Dict[str, Any]:
    """Compare two runs for equality."""
    events1 = load_run(run_id1, artifacts_dir)
    events2 = load_run(run_id2, artifacts_dir)
    
    differences = []
    
    for i, (e1, e2) in enumerate(zip(events1, events2)):
        for key in ["chosen_focus", "chosen_intent", "action", "outcome"]:
            v1 = e1.get(key)
            v2 = e2.get(key)
            if v1 != v2:
                differences.append({
                    "tick": i,
                    "key": key,
                    "value1": v1,
                    "value2": v2,
                })
    
    return {
        "run_id1": run_id1,
        "run_id2": run_id2,
        "events1": len(events1),
        "events2": len(events2),
        "differences": differences,
        "equal": len(differences) == 0 and len(events1) == len(events2),
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
