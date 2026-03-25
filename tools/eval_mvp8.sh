#!/usr/bin/env bash
# MVP-8 Evaluation Script v2
# Runs events through real process_event() pipeline and validates expect assertions

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# Use temp dir for reports during eval (clean, reproducible)
export EMOTIOND_REPORTS_DIR="$(mktemp -d)"
trap 'rm -rf "$EMOTIOND_REPORTS_DIR"' EXIT

mkdir -p reports

python3 - << 'PY'
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Real pipeline imports
from emotiond.core import load_initial_state, process_event
from emotiond.db import init_db
from emotiond.models import Event


async def run_scenario(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """Run a single scenario through real process_event() pipeline."""
    events = scenario.get("events", [])
    if not events:
        # Fallback: single event format
        events = [scenario.get("event", {})]

    expect = scenario.get("expect", {})
    results = []

    # Initialize DB for each scenario (isolated)
    import tempfile
    db_path = tempfile.mktemp(suffix=".db")
    os.environ["EMOTIOND_DB_PATH"] = db_path
    await init_db()
    await load_initial_state()

    for ev in events:
        event = Event(
            type=ev.get("type", "user_message"),
            actor=ev.get("actor", "user"),
            target=ev.get("target", "agent"),
            text=ev.get("text"),
            meta=ev.get("meta", {}),
        )
        result = await process_event(event)
        results.append(result)

    # Aggregate last result for assertions
    last_result = results[-1] if results else {}
    report = last_result.get("self_report", {})

    # Run expect assertions
    failures = []

    # 1. primary_emotion check
    expected_emotion = expect.get("primary_emotion")
    actual_emotion = report.get("emotional_reasoning", {}).get("primary_emotion")
    if expected_emotion and actual_emotion != expected_emotion:
        failures.append(f"primary_emotion: expected '{expected_emotion}', got '{actual_emotion}'")

    # 2. action_tendency check
    expected_action = expect.get("action_tendency")
    actual_action = report.get("emotional_reasoning", {}).get("action_tendency")
    if expected_action and actual_action != expected_action:
        failures.append(f"action_tendency: expected '{expected_action}', got '{actual_action}'")

    # 3. has_conflict check
    if "has_conflict" in expect:
        actual_conflict = report.get("self_consistency", {}).get("has_conflict")
        if actual_conflict != expect["has_conflict"]:
            failures.append(f"has_conflict: expected {expect['has_conflict']}, got {actual_conflict}")

    # 4. repair_strategy check
    expected_repair = expect.get("repair_strategy")
    actual_repair = report.get("self_consistency", {}).get("repair_strategy")
    if expected_repair and expected_repair not in (actual_repair or ""):
        failures.append(f"repair_strategy: expected '{expected_repair}', got '{actual_repair}'")

    # 5. narrative summary contains check
    summary_contains = expect.get("narrative_summary_contains")
    if summary_contains:
        summary = report.get("narrative_memory", {}).get("compressed", "")
        if summary_contains not in summary:
            failures.append(f"narrative_summary: expected to contain '{summary_contains}'")

    # 6. Basic structural checks
    if not report.get("emotional_reasoning"):
        failures.append("missing emotional_reasoning")
    if not report.get("self_consistency"):
        failures.append("missing self_consistency")
    if not report.get("narrative_memory", {}).get("compressed"):
        failures.append("missing narrative_memory.compressed")

    # Cleanup
    try:
        os.unlink(db_path)
    except:
        pass

    return {
        "name": scenario.get("name", "unnamed"),
        "pass": len(failures) == 0,
        "failures": failures,
        "actual": {
            "primary_emotion": actual_emotion,
            "action_tendency": actual_action,
            "has_conflict": report.get("self_consistency", {}).get("has_conflict"),
            "repair_strategy": actual_repair,
        },
    }


async def main():
    scenario_dir = Path("tests/scenarios/mvp8")
    files = sorted(scenario_dir.glob("*.json"))

    if not files:
        print("ERROR: No scenario files found")
        sys.exit(1)

    results = []
    passed = 0

    for f in files:
        data = json.loads(f.read_text())
        result = await run_scenario(data)
        results.append(result)
        if result["pass"]:
            passed += 1
        else:
            print(f"FAIL: {result['name']}")
            for fail in result["failures"]:
                print(f"  - {fail}")

    rate = passed / max(1, len(files))
    out = {
        "total": len(files),
        "passed": passed,
        "pass_rate": rate,
        "target_pass_rate": 0.8,
        "ok": rate >= 0.8,
        "scenarios": results,
    }

    Path("reports/mvp8_eval.json").write_text(json.dumps(out, indent=2))
    print(f"\n{'='*50}")
    print(f"Eval Result: {passed}/{len(files)} passed ({rate:.0%})")
    print(f"Target: ≥80% → {'PASS' if rate >= 0.8 else 'FAIL'}")
    print(f"{'='*50}")

    if not out["ok"]:
        sys.exit(1)


asyncio.run(main())
PY
