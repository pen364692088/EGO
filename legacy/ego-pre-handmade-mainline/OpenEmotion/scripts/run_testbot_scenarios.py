#!/usr/bin/env python3
"""
Run all testbot scenarios and generate concentration report.

Usage:
    python scripts/run_testbot_scenarios.py
    python scripts/run_testbot_scenarios.py --scenarios-dir tests/testbot/scenarios
    python scripts/run_testbot_scenarios.py --output artifacts/testbot/concentration_report.json
    python scripts/run_testbot_scenarios.py --dry-run  # Don't dispatch to emotiond
    python scripts/run_testbot_scenarios.py --subset pr  # PR subset (3 scenarios)
    python scripts/run_testbot_scenarios.py --subset nightly  # All 5 scenarios (default)
    
Options:
    --scenarios-dir DIR   Directory containing scenario JSON files
    --output PATH         Output path for concentration report
    --dry-run             Don't dispatch events to emotiond
    --format FMT          Output format: json|summary (default: summary)
    --subset SUBSET       Scenario subset: pr|nightly (default: nightly)
"""
import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.testbot.models import (
    TestbotMessage,
    TestbotConfig,
    Scenario,
)
from emotiond.testbot.harness import (
    TestbotHarness,
    run_conversation,
)
from emotiond.testbot.tape import (
    TapeRecorder,
    TapeReplayer,
)


# All scenario files in order
ALL_SCENARIOS = [
    "simple.json",
    "multi_turn.json",
    "conflict.json",
    "commitment.json",
    "complex.json",
]

# PR subset: 3 scenarios for quick validation
PR_SCENARIOS = [
    "simple.json",
    "multi_turn.json",
    "commitment.json",
]

# Subset mapping
SUBSET_SCENARIOS = {
    "pr": PR_SCENARIOS,
    "nightly": ALL_SCENARIOS,
}


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run all testbot scenarios and generate concentration report"
    )
    parser.add_argument(
        "--scenarios-dir",
        type=str,
        default="tests/testbot/scenarios",
        help="Directory containing scenario JSON files"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="artifacts/testbot/concentration_report.json",
        help="Output path for concentration report"
    )
    parser.add_argument(
        "--tapes-dir",
        type=str,
        default="artifacts/testbot/tapes",
        help="Output directory for tape files"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't dispatch events to emotiond"
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["json", "summary"],
        default="summary",
        help="Output format (default: summary)"
    )
    parser.add_argument(
        "--subset",
        type=str,
        choices=["pr", "nightly"],
        default="nightly",
        help="Scenario subset to run: pr (3 scenarios) or nightly (all 5, default)"
    )
    
    return parser.parse_args()


def load_scenario(path: Path) -> Optional[Scenario]:
    """Load scenario from JSON file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Scenario(**data)
    except Exception as e:
        print(f"Warning: Failed to load {path}: {e}", file=sys.stderr)
        return None


def messages_from_scenario(scenario: Scenario) -> List[TestbotMessage]:
    """Convert scenario messages to TestbotMessages."""
    messages = []
    for i, msg in enumerate(scenario.messages):
        # Only include user messages (agent messages are expected responses)
        if msg.sender == "user":
            messages.append(TestbotMessage(
                message_id=f"msg_{i+1}",
                sender_id="user",
                sender="User",
                text=msg.text,
            ))
    return messages


def compute_concentration_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute concentration metrics from scenario results.
    
    Metrics:
    - top1_share: Top-1 signature share (0.0-1.0)
    - top3_share: Top-3 signatures share (0.0-1.0)
    - hhi: Herfindahl-Hirschman Index (0.0-1.0)
    - unique_count: Number of unique signatures
    
    Returns:
        Dict with concentration metrics
    """
    # Extract signatures from results
    signatures = []
    for result in results:
        # Try to extract signature from process_result
        process_result = result.get("process_result", {})
        
        # Look for signature in various locations
        sig = (
            process_result.get("signature") or
            process_result.get("cycle_signature") or
            process_result.get("phi", {}).get("signature") or
            process_result.get("decision", {}).get("signature")
        )
        
        if sig:
            signatures.append(str(sig))
        else:
            # Create a hash from available fields for uniqueness
            sig_hash = json.dumps(process_result, sort_keys=True, default=str)
            signatures.append(f"auto_{hash(sig_hash) % 10000}")
    
    if not signatures:
        return {
            "top1_share": 0.0,
            "top3_share": 0.0,
            "hhi": 0.0,
            "unique_count": 0,
            "total_count": 0,
        }
    
    # Count occurrences
    counts = Counter(signatures)
    total = len(signatures)
    sorted_counts = sorted(counts.values(), reverse=True)
    
    # Compute metrics
    top1_share = sorted_counts[0] / total if sorted_counts else 0.0
    top3_share = sum(sorted_counts[:3]) / total if sorted_counts else 0.0
    hhi = sum((c / total) ** 2 for c in counts.values())
    unique_count = len(counts)
    
    return {
        "top1_share": round(top1_share, 6),
        "top3_share": round(top3_share, 6),
        "hhi": round(hhi, 6),
        "unique_count": unique_count,
        "total_count": total,
        "signature_distribution": dict(counts.most_common(10)),
    }


def compute_replay_hash_match(tape_path: Optional[str], expected_hash: Optional[str]) -> bool:
    """
    Check if tape hash matches expected hash from previous run.
    
    Args:
        tape_path: Path to tape file
        expected_hash: Expected hash to match (from previous run)
        
    Returns:
        True if hashes match, False otherwise
    """
    if not tape_path or not Path(tape_path).exists():
        return False
    
    try:
        replayer = TapeReplayer(tape_path)
        actual_hash = replayer.calculate_tape_hash()
        
        if expected_hash:
            return actual_hash == expected_hash
        else:
            # No expected hash, return True (first run)
            return True
    except Exception:
        return False


async def run_single_scenario(
    scenario_path: Path,
    config: TestbotConfig,
    dispatch: bool = True,
    previous_tape_hash: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run a single scenario and return results.
    
    Args:
        scenario_path: Path to scenario JSON file
        config: Testbot configuration
        dispatch: Whether to dispatch to emotiond
        previous_tape_hash: Expected hash from previous run (for replay verification)
        
    Returns:
        Dict with scenario results
    """
    scenario = load_scenario(scenario_path)
    if not scenario:
        return {
            "name": scenario_path.stem,
            "status": "error",
            "error": "Failed to load scenario",
        }
    
    # Update config with scenario thread-id if available
    thread_id = getattr(scenario, 'thread_id', None) or f"test_{scenario.name}"
    run_config = TestbotConfig(
        channel=config.channel,
        thread_id=thread_id,
        output_dir=config.output_dir,
        run_id=f"{scenario.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    )
    
    messages = messages_from_scenario(scenario)
    
    start_time = time.time()
    try:
        result = await run_conversation(messages, run_config, dispatch=dispatch)
        elapsed = time.time() - start_time
        
        # Get tape hash
        tape_hash = result.get("tape_hash", "")
        tape_path = result.get("tape_path")
        
        # Compute replay hash match
        replay_hash_match = compute_replay_hash_match(tape_path, previous_tape_hash)
        
        # Compute concentration for this scenario
        concentration = compute_concentration_metrics(result.get("results", []))
        
        return {
            "name": scenario.name,
            "description": getattr(scenario, 'description', ''),
            "status": "success",
            "elapsed_seconds": round(elapsed, 3),
            "tape_hash": f"sha256:{tape_hash[:16]}" if tape_hash else None,
            "full_tape_hash": tape_hash,
            "replay_hash_match": replay_hash_match,
            "messages": len(messages),
            "turns": result.get("turn_count", 0),
            "tape_path": tape_path,
            "concentration": concentration,
        }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "name": scenario.name,
            "status": "error",
            "error": str(e),
            "elapsed_seconds": round(elapsed, 3),
            "messages": len(messages),
            "turns": 0,
        }


async def run_scenarios(
    scenarios_dir: Path,
    output_path: Path,
    tapes_dir: str,
    dispatch: bool = True,
    subset: str = "nightly",
) -> Dict[str, Any]:
    """
    Run scenarios based on subset and generate report.
    
    Args:
        scenarios_dir: Directory containing scenario files
        output_path: Path to write concentration report
        tapes_dir: Directory for tape files
        dispatch: Whether to dispatch to emotiond
        subset: Scenario subset to run (pr or nightly)
        
    Returns:
        Dict with overall results
    """
    # Get scenario list based on subset
    scenario_names = SUBSET_SCENARIOS.get(subset, ALL_SCENARIOS)
    
    # Find scenario files
    scenario_files = []
    for name in scenario_names:
        path = scenarios_dir / name
        if path.exists():
            scenario_files.append(path)
        else:
            print(f"Warning: Scenario file not found: {path}", file=sys.stderr)
    
    if not scenario_files:
        return {
            "subset": subset,
            "status": "error",
            "error": "No scenario files found",
            "scenarios_dir": str(scenarios_dir),
        }
    
    print(f"Running {len(scenario_files)} scenarios (subset: {subset})")
    
    # Create config
    config = TestbotConfig(
        channel="testbot",
        thread_id="test_batch",
        output_dir=tapes_dir,
    )
    
    # Run each scenario
    results = []
    start_time = time.time()
    
    for scenario_path in scenario_files:
        print(f"Running: {scenario_path.name}...")
        result = await run_single_scenario(scenario_path, config, dispatch=dispatch)
        results.append(result)
        
        status = result.get("status", "unknown")
        if status == "success":
            print(f"  ✓ Completed in {result.get('elapsed_seconds', 0):.3f}s")
            print(f"    Tape hash: {result.get('tape_hash', 'N/A')}")
            print(f"    Replay match: {result.get('replay_hash_match', 'N/A')}")
        else:
            print(f"  ✗ Error: {result.get('error', 'unknown')}")
    
    elapsed = time.time() - start_time
    
    # Compute aggregate concentration
    successful_results = [r for r in results if r.get("status") == "success"]
    failed_results = [r for r in results if r.get("status") == "error"]
    
    # Aggregate concentration across all scenarios
    all_concentrations = [r.get("concentration", {}) for r in successful_results]
    
    if all_concentrations:
        avg_top1 = sum(c.get("top1_share", 0) for c in all_concentrations) / len(all_concentrations)
        avg_hhi = sum(c.get("hhi", 0) for c in all_concentrations) / len(all_concentrations)
        total_unique = sum(c.get("unique_count", 0) for c in all_concentrations)
    else:
        avg_top1 = 0.0
        avg_hhi = 0.0
        total_unique = 0
    
    # Build report with new format
    report = {
        "subset": subset,
        "scenarios": [r.get("name") for r in results],
        "total": len(results),
        "successful": len(successful_results),
        "failed": len(failed_results),
        "results": [
            {
                "name": r.get("name"),
                "status": r.get("status"),
                "tape_hash": r.get("tape_hash"),
                "replay_hash_match": r.get("replay_hash_match"),
                "messages": r.get("messages", 0),
                "turns": r.get("turns", 0),
                "elapsed_seconds": r.get("elapsed_seconds"),
                "concentration": r.get("concentration"),
            }
            for r in results
        ],
        "concentration": {
            "avg_top1_share": round(avg_top1, 6),
            "avg_hhi": round(avg_hhi, 6),
            "total_unique_signatures": total_unique,
        },
        "metadata": {
            "report_type": "testbot_concentration",
            "generated_at": datetime.now().isoformat(),
            "total_elapsed_seconds": round(elapsed, 3),
            "scenarios_dir": str(scenarios_dir),
            "tapes_dir": tapes_dir,
        }
    }
    
    # Write report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\nReport written to: {output_path}")
    
    return report


def format_summary(report: Dict[str, Any]) -> str:
    """Format report as human-readable summary."""
    lines = [
        f"=== Testbot Scenarios Report (subset: {report.get('subset', 'unknown')}) ===",
        f"Generated:    {report.get('metadata', {}).get('generated_at', 'N/A')}",
        f"Total:        {report.get('total', 0)} scenarios",
        f"Successful:   {report.get('successful', 0)}",
        f"Failed:       {report.get('failed', 0)}",
        f"Elapsed:      {report.get('metadata', {}).get('total_elapsed_seconds', 0):.3f}s",
        "",
        "=== Aggregate Concentration ===",
    ]
    
    conc = report.get("concentration", {})
    lines.extend([
        f"  Avg Top1 Share:  {conc.get('avg_top1_share', 0):.6f}",
        f"  Avg HHI:         {conc.get('avg_hhi', 0):.6f}",
        f"  Unique Sigs:     {conc.get('total_unique_signatures', 0)}",
        "",
        "=== Per-Scenario Results ===",
    ])
    
    for r in report.get("results", []):
        status = "✓" if r.get("status") == "success" else "✗"
        lines.append(f"  [{status}] {r.get('name', 'unknown')}")
        lines.append(f"      Messages: {r.get('messages', 0)}, Turns: {r.get('turns', 0)}")
        lines.append(f"      Tape hash: {r.get('tape_hash', 'N/A')}")
        lines.append(f"      Replay match: {r.get('replay_hash_match', 'N/A')}")
        
        sc = r.get("concentration", {})
        if sc:
            lines.append(f"      Top1: {sc.get('top1_share', 0):.6f}, HHI: {sc.get('hhi', 0):.6f}")
        
        if r.get("status") == "error":
            lines.append(f"      Error: {r.get('error', 'unknown')}")
    
    return "\n".join(lines)


async def main() -> int:
    """Main entry point."""
    args = parse_args()
    
    scenarios_dir = Path(args.scenarios_dir)
    output_path = Path(args.output)
    tapes_dir = args.tapes_dir
    subset = args.subset
    
    if not scenarios_dir.exists():
        print(f"Error: Scenarios directory not found: {scenarios_dir}", file=sys.stderr)
        return 1
    
    dispatch = not args.dry_run
    
    report = await run_scenarios(
        scenarios_dir,
        output_path,
        tapes_dir,
        dispatch=dispatch,
        subset=subset,
    )
    
    # Output result
    if args.format == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(format_summary(report))
    
    # Return non-zero if any failures
    if report.get("failed", 0) > 0:
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
