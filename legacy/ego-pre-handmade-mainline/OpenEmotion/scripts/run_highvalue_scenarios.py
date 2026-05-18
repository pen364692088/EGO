#!/usr/bin/env python3
"""
Run high-value testbot scenarios with assertion checking.

Subsets:
  --subset pr       : 2 short high-value scenarios (for CI PR)
  --subset nightly  : All 5 high-value scenarios (for nightly)
  
Usage:
    python scripts/run_highvalue_scenarios.py --subset pr
    python scripts/run_highvalue_scenarios.py --subset nightly
"""
import argparse
import json
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.testbot.harness import TestbotHarness
from emotiond.testbot.assertions import AssertionChecker, format_assertion_report
from emotiond.testbot.models import TestbotMessage, TestbotConfig


# High-value scenario definitions
PR_SCENARIOS = [
    "governor_override_jailbreak.json",      # 6-8 turns, security test
    "nondeterminism_injection_random_path.json",  # 6 turns, determinism test
    "numeric_leak_extraction.json",           # NEW: numeric leak protection
]

NIGHTLY_SCENARIOS = [
    "governor_override_jailbreak.json",      # Security: Governor不可绕过
    "nondeterminism_injection_random_path.json",  # Determinism: 随机路径可回放
    "tool_loop_bait_and_budget.json",        # Resource: 工具循环与预算
    "long_drift_identity_invariants.json",    # Self-model: 长对话漂移 (20 turns)
    "goodhart_collapse_pressure.json",       # Concentration: 反塌缩
    # New adversarial scenarios
    "numeric_leak_extraction.json",           # Security: 数值泄露防护
    "intent_drift_alignment.json",            # Alignment: 意图漂移检测
    "numeric_fabrication_detection.json",     # Integrity: 编造检测
    "whitelist_bypass_attempt.json",          # Security: 白名单绕过防护
]

# Extended adversarial subset for comprehensive testing
ADVERSARIAL_SCENARIOS = [
    "numeric_leak_extraction.json",           # Numeric leak protection
    "intent_drift_alignment.json",            # Intent drift detection
    "numeric_fabrication_detection.json",     # Fabrication detection
    "whitelist_bypass_attempt.json",          # Whitelist bypass protection
    "governor_override_jailbreak.json",       # Governor bypass protection
]

SUBSET_SCENARIOS = {
    "pr": PR_SCENARIOS,
    "nightly": NIGHTLY_SCENARIOS,
    "adversarial": ADVERSARIAL_SCENARIOS,
}


def parse_args():
    parser = argparse.ArgumentParser(description="Run high-value testbot scenarios")
    parser.add_argument("--subset", choices=["pr", "nightly", "adversarial"], default="pr",
                        help="Scenario subset (default: pr)")
    parser.add_argument("--scenarios-dir", default="tests/testbot/scenarios",
                        help="Directory containing scenario files")
    parser.add_argument("--tapes-dir", default="artifacts/testbot/tapes",
                        help="Output directory for tapes")
    parser.add_argument("--output", default=None,
                        help="Output JSON report path")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't dispatch to emotiond")
    return parser.parse_args()


def load_scenario(path: Path) -> Dict[str, Any]:
    """Load scenario from JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    args = parse_args()
    
    scenarios_dir = Path(args.scenarios_dir)
    tapes_dir = Path(args.tapes_dir)
    tapes_dir.mkdir(parents=True, exist_ok=True)
    
    # Get scenario list
    scenario_files = SUBSET_SCENARIOS[args.subset]
    
    print(f"\n{'='*60}")
    print(f"High-Value Testbot Scenarios: {args.subset.upper()}")
    print(f"{'='*60}")
    print(f"Scenarios: {len(scenario_files)}")
    print(f"{'='*60}\n")
    
    harness = None  # Will be created per-scenario
    checker = AssertionChecker()
    
    results = []
    total_start = time.time()
    
    for scenario_file in scenario_files:
        scenario_path = scenarios_dir / scenario_file
        
        if not scenario_path.exists():
            print(f"❌ Scenario not found: {scenario_file}")
            continue
        
        scenario = load_scenario(scenario_path)
        scenario_name = scenario.get("name", scenario_file)
        
        print(f"Running: {scenario_name}...")
        start_time = time.time()
        
        # Run scenario
        messages = scenario.get("messages", [])
        thread_id = scenario.get("thread_id", f"test_{scenario_name}")
        
        # Configure harness for this scenario
        harness_config = TestbotConfig(
            channel="testbot",
            thread_id=thread_id,
            output_dir=str(tapes_dir),
        )
        harness = TestbotHarness(config=harness_config)
        
        try:
            # Process messages through harness
            processed_messages = []
            for i, msg in enumerate(messages):
                if msg.get("sender") == "user":
                    # Create TestbotMessage and process
                    test_msg = TestbotMessage(
                        message_id=f"{thread_id}_msg_{i}",
                        sender_id="test_user",
                        sender="user",
                        text=msg.get("text", ""),
                    )
                    if not args.dry_run:
                        harness.process_message(test_msg)
                    processed_messages.append(msg)
                else:
                    # Agent response (from scenario or live)
                    processed_messages.append(msg)
            
            # Run assertion checks
            assertion_report = checker.check_scenario(scenario, processed_messages)
            
            elapsed = time.time() - start_time
            
            result = {
                "name": scenario_name,
                "file": scenario_file,
                "status": "pass" if assertion_report.overall_passed else "fail",
                "elapsed_seconds": round(elapsed, 3),
                "messages": len(messages),
                "assertions": {
                    "passed": sum(1 for r in assertion_report.results if r.passed),
                    "total": len(assertion_report.results),
                    "details": [
                        {"name": r.name, "passed": r.passed, "reason": r.reason}
                        for r in assertion_report.results
                    ]
                }
            }
            
            status_icon = "✅" if assertion_report.overall_passed else "❌"
            p0_marker = " ⚠️ P0" if assertion_report.p0_risk else ""
            print(f"  {status_icon} {scenario_name}: {assertion_report.summary} ({elapsed:.3f}s){p0_marker}")
            
            # Print assertion details if failed
            if not assertion_report.overall_passed:
                print(format_assertion_report(assertion_report))
            
        except Exception as e:
            elapsed = time.time() - start_time
            result = {
                "name": scenario_name,
                "file": scenario_file,
                "status": "error",
                "error": str(e),
                "elapsed_seconds": round(elapsed, 3)
            }
            print(f"  ❌ {scenario_name}: ERROR - {e}")
        
        results.append(result)
    
    total_elapsed = time.time() - total_start
    
    # Summary
    passed = sum(1 for r in results if r.get("status") == "pass")
    failed = sum(1 for r in results if r.get("status") == "fail")
    errors = sum(1 for r in results if r.get("status") == "error")
    
    print(f"\n{'='*60}")
    print(f"Summary: {passed}/{len(results)} passed")
    if failed > 0:
        print(f"  ❌ Failed: {failed}")
    if errors > 0:
        print(f"  ⚠️  Errors: {errors}")
    print(f"Total time: {total_elapsed:.3f}s")
    print(f"{'='*60}\n")
    
    # Write report
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        report = {
            "subset": args.subset,
            "generated_at": datetime.now().isoformat(),
            "total_scenarios": len(results),
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "total_elapsed_seconds": round(total_elapsed, 3),
            "results": results
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"Report written to: {output_path}")
    
    # Exit code
    if failed > 0 or errors > 0:
        sys.exit(1)
    
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
