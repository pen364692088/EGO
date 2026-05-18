#!/usr/bin/env bash
# MVP-8.2.3 Cross-Process Replay Verifier (Production-Ready)
# Verifies self_hash stability across different Python processes with different PYTHONHASHSEED
# 
# Production-ready features:
# - Public API for reset (no private field access)
# - Configurable temp dir (cross-platform)
# - Multi-step narrative memory accumulation
# - Per-scenario DB isolation
# - Cross-process deterministic

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# Export for Python to pick up
export OPENEMOTION_ROOT_DIR="$ROOT_DIR"

echo "=== MVP-8.2.3 Cross-Process Replay Verifier (Production-Ready) ==="
echo "ROOT_DIR: $ROOT_DIR"
echo ""

python3 << 'PY'
import subprocess
import json
import os
import sys
import tempfile
from pathlib import Path

# Use environment variable (set by bash wrapper) instead of hardcoded path
ROOT_DIR = Path(os.environ.get("OPENEMOTION_ROOT_DIR", Path(__file__).resolve().parent.parent))
SCENARIO_DIR = ROOT_DIR / "tests/scenarios/mvp8"
OUTPUT_PATH = ROOT_DIR / "reports/mvp8_replay_verify.json"

# Cross-platform temp dir (respects OPENEMOTION_TMP_DIR override)
TEMP_BASE = Path(os.environ.get("OPENEMOTION_TMP_DIR", tempfile.gettempdir()))

# Script template for subprocess execution - processes FULL event sequence
SCRIPT_TEMPLATE = '''
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "{root_dir}")

os.environ["EMOTIOND_REPORTS_DIR"] = "{reports_dir}"
os.environ["EMOTIOND_DB_PATH"] = "{db_path}"

from emotiond.core import load_initial_state, process_event
from emotiond.db import init_db
from emotiond.models import Event
from emotiond.narrative_memory import narrative_memory
import asyncio

async def main():
    await init_db()
    await load_initial_state()
    
    # CRITICAL: Reset narrative memory ONCE per scenario using public API
    # This verifies multi-step accumulation still produces stable hash
    narrative_memory.reset()  # Public API instead of _by_target.clear()
    
    # Process ALL events in sequence (for narrative memory accumulation)
    events_data = {events_json}
    
    result = {{}}
    for ev in events_data:
        event = Event(
            type=ev.get("type", "user_message"),
            actor=ev.get("actor", "user"),
            target=ev.get("target", "agent"),
            text=ev.get("text", ""),
            meta=ev.get("meta", {{}}),
        )
        result = await process_event(event)
    
    sr = result.get("self_report", {{}})
    nm_state = sr.get("narrative_memory", {{}}).get("state", {{}})
    print(json.dumps({{
        "status": result.get("status"),
        "self_hash": sr.get("audit", {{}}).get("self_hash"),
        "primary_emotion": sr.get("emotional_reasoning", {{}}).get("primary_emotion"),
        "action_tendency": sr.get("emotional_reasoning", {{}}).get("action_tendency"),
        "event_count": nm_state.get("event_count", 0),
        "conflict_count": nm_state.get("conflict_count", 0),
    }}))

asyncio.run(main())
'''

def run_in_process(events: list, python_hash_seed: str, scenario_stem: str) -> dict:
    """Run scenario in isolated subprocess with specific PYTHONHASHSEED."""
    # Per-scenario DB isolation using cross-platform temp dir
    db_path = str(TEMP_BASE / f"replay_verify_{python_hash_seed}_{scenario_stem}.db")
    reports_dir = str(TEMP_BASE / f"replay_verify_{python_hash_seed}_{scenario_stem}")
    
    script = SCRIPT_TEMPLATE.format(
        root_dir=str(ROOT_DIR),
        reports_dir=reports_dir,
        db_path=db_path,
        events_json=json.dumps(events),
    )
    
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = python_hash_seed
    env["OPENEMOTION_ROOT_DIR"] = str(ROOT_DIR)
    env["OPENEMOTION_TMP_DIR"] = str(TEMP_BASE)
    
    result = subprocess.run(
        ["python3", "-c", script],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT_DIR),
        timeout=60,
    )
    
    if result.returncode != 0:
        return {"error": result.stderr, "returncode": result.returncode}
    
    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {e}", "stdout": result.stdout}

def verify_scenario(scenario_path: Path) -> dict:
    """Verify a single scenario across multiple processes."""
    scenario = json.loads(scenario_path.read_text())
    name = scenario.get("name", scenario_path.stem)
    scenario_stem = scenario_path.stem
    
    # Get ALL events (not just last one)
    events = scenario.get("events", [])
    if not events:
        events = [scenario.get("event", {})]
    
    # Run with different PYTHONHASHSEED values
    seeds = ["0", "1", "42", "random"]
    results = []
    hashes = []
    event_counts = []
    
    for seed in seeds:
        result = run_in_process(events, seed, scenario_stem)
        results.append({"seed": seed, "result": result})
        
        if "self_hash" in result:
            hashes.append(result["self_hash"])
            event_counts.append(result.get("event_count", 0))
    
    # Verify hash consistency
    hash_stable = len(set(hashes)) == 1 if hashes else False
    
    # Verify event_count consistency (multi-step accumulation verified)
    event_count_stable = len(set(event_counts)) == 1 if event_counts else False
    
    return {
        "name": name,
        "events_in_scenario": len(events),
        "hash_stable": hash_stable,
        "event_count_stable": event_count_stable,
        "final_event_count": event_counts[0] if event_counts else 0,
        "hashes": hashes,
        "unique_hashes": len(set(hashes)) if hashes else 0,
    }

# Main execution
scenario_files = sorted(SCENARIO_DIR.glob("*.json"))
all_results = []
all_stable = 0

for sf in scenario_files:
    result = verify_scenario(sf)
    all_results.append(result)
    if result["hash_stable"]:
        all_stable += 1
        ec = result.get("final_event_count", "?")
        esc = result.get("events_in_scenario", "?")
        print(f"✓ {result['name']}: hash stable ({result['hashes'][0][:16]}...) [events={esc}→count={ec}]")
    else:
        print(f"✗ {result['name']}: HASH DRIFT - {result['unique_hashes']} different hashes")
        for h in result["hashes"]:
            print(f"    {h[:32]}...")

# Write report
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
report = {
    "verifier_version": "mvp8.2.3",
    "production_ready_features": [
        "public_reset_api",
        "cross_platform_temp_dir",
        "multi_step_narrative_accumulation",
        "per_scenario_db_isolation", 
        "cross_process_deterministic",
    ],
    "temp_base_dir": str(TEMP_BASE),
    "total": len(scenario_files),
    "hash_stable_count": all_stable,
    "pass_rate": all_stable / max(1, len(scenario_files)),
    "target_pass_rate": 1.0,
    "ok": all_stable == len(scenario_files),
    "scenarios": all_results,
}
OUTPUT_PATH.write_text(json.dumps(report, indent=2))

print("")
print("=" * 50)
print(f"Replay Verify Result: {all_stable}/{len(scenario_files)} stable")
print(f"Target: 100% → {'PASS' if report['ok'] else 'FAIL'}")
print(f"Temp dir: {TEMP_BASE}")
print("=" * 50)

if not report["ok"]:
    sys.exit(1)
PY
