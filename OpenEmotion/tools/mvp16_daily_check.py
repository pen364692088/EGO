#!/usr/bin/env python3
"""
MVP16 Daily Observation Check

Run this daily during the observation window.

CRITICAL: This check reads from REAL persisted developmental state.
- No fake positives from reading default values after reset
- Returns 'insufficient_evidence' if no real data exists

WP11 / MVP16 status:
- input-only / historical observation helper
- not the formal owner path
- not current-mainline closeout proof
"""
import sys
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.developmental import get_developmental_manager, reset_developmental_manager


# Result status constants
STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_ALERT = "ALERT"
STATUS_INSUFFICIENT_EVIDENCE = "insufficient_evidence"
STATUS_BLOCKED = "blocked"


def check_tests() -> dict:
    """Run MVP16 tests and return results."""
    result = subprocess.run(
        ["pytest", "tests/mvp16/", "-v", "--tb=no", "-q"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True
    )
    output = result.stdout + result.stderr
    
    # Parse results - look for summary line like "13 passed"
    import re
    match = re.search(r'(\d+) passed', output)
    passed = int(match.group(1)) if match else 0
    
    match = re.search(r'(\d+) failed', output)
    failed = int(match.group(1)) if match else 0
    
    return {
        "passed": passed,
        "failed": failed,
        "status": STATUS_PASS if failed == 0 and passed > 0 else (STATUS_FAIL if failed > 0 else STATUS_PASS)
    }


def check_continuity() -> dict:
    """Check developmental continuity from REAL persisted state.
    
    Returns 'insufficient_evidence' if no real data exists.
    Does NOT reset and read default values (anti-false-positive).
    """
    # DO NOT reset - we want real persisted data
    manager = get_developmental_manager()
    summary = manager.get_summary()
    
    # CRITICAL: Check if we have real data, not just defaults
    if not summary.get("has_real_data", False):
        return {
            "current_phase": None,
            "episodes": 0,
            "transitions": 0,
            "identity_preserved": None,
            "continuity_score": None,
            "persisted": summary.get("persisted", False),
            "has_real_data": False,
            "status": STATUS_INSUFFICIENT_EVIDENCE,
            "reason": "No real developmental data found. Manager has only default values."
        }
    
    return {
        "current_phase": summary["current_phase"],
        "episodes": summary["episodes"],
        "transitions": summary["transitions"],
        "identity_preserved": summary["identity_preserved"],
        "continuity_score": summary["continuity_score"],
        "persisted": summary.get("persisted", False),
        "real_episode_count": summary.get("real_episode_count", 0),
        "real_session_count": summary.get("real_session_count", 0),
        "real_day_count": summary.get("real_day_count", 0),
        "has_real_data": True,
        "status": STATUS_PASS if summary["identity_preserved"] else STATUS_ALERT
    }


def check_metrics() -> dict:
    """Check all tracked metrics from REAL persisted state.
    
    Returns 'insufficient_evidence' if no real data exists.
    Does NOT reset and read default values (anti-false-positive).
    """
    # DO NOT reset - we want real persisted data
    manager = get_developmental_manager()
    
    summary = manager.get_summary()

    # CRITICAL: Check if we have admission-grade real data, not just defaults
    if not summary.get("has_real_data", False):
        return {
            "metrics": {},
            "alerts": [],
            "has_real_data": False,
            "status": STATUS_INSUFFICIENT_EVIDENCE,
            "reason": "No real developmental data found. Cannot evaluate metrics from defaults."
        }
    
    metrics = {}
    alerts = []
    
    for name, metric in manager.state.metrics.items():
        metrics[name] = {
            "value": round(metric.value, 3),
            "trend": metric.trend,
            "has_history": len(metric.history) > 0  # Real data indicator
        }
        
        # Check thresholds
        if name == "continuity_score" and metric.value < 0.6:
            alerts.append(f"continuity_score ({metric.value:.2f}) < 0.6")
        elif name == "continuity_score" and metric.value < 0.8:
            alerts.append(f"continuity_score ({metric.value:.2f}) < 0.8 [WARNING]")
            
        if name == "identity_stability" and metric.value < 0.95:
            alerts.append(f"identity_stability ({metric.value:.2f}) < 0.95")
            
        if name == "governance_compliance" and metric.value < 1.0:
            alerts.append(f"governance_compliance ({metric.value:.2f}) < 1.0")
    
    return {
        "metrics": metrics,
        "alerts": alerts,
        "real_episode_count": summary.get("real_episode_count", 0),
        "real_session_count": summary.get("real_session_count", 0),
        "real_day_count": summary.get("real_day_count", 0),
        "has_real_data": True,
        "status": STATUS_PASS if not alerts else STATUS_ALERT
    }


def check_invariants() -> dict:
    """Check identity invariants from REAL persisted state.
    
    Returns 'insufficient_evidence' if no real data exists.
    Does NOT reset and read default values (anti-false-positive).
    """
    # DO NOT reset - we want real persisted data
    manager = get_developmental_manager()
    
    summary = manager.get_summary()

    # CRITICAL: Check if we have admission-grade real data, not just defaults
    if not summary.get("has_real_data", False):
        return {
            "violations": [],
            "violation_count": 0,
            "has_real_data": False,
            "status": STATUS_INSUFFICIENT_EVIDENCE,
            "reason": "No real developmental data found. Cannot check invariants from defaults."
        }
    
    violations = []
    
    if not manager.check_identity_preservation():
        violations.append("identity_preserved = False")
    if not summary.get("trajectory_refs_present", False):
        violations.append("trajectory_refs_present = False")
    if not summary.get("replay_refs_present", False):
        violations.append("replay_refs_present = False")
    
    return {
        "violations": violations,
        "violation_count": len(violations),
        "trajectory_refs_present": summary.get("trajectory_refs_present", False),
        "replay_refs_present": summary.get("replay_refs_present", False),
        "has_real_data": True,
        "status": STATUS_PASS if not violations else STATUS_ALERT
    }


def check_admission_inputs() -> dict:
    """Check admission-grade trajectory inputs from persisted real projection."""
    manager = get_developmental_manager()
    summary = manager.get_summary()

    if not summary.get("has_real_data", False):
        return {
            "real_episode_count": 0,
            "real_session_count": 0,
            "real_day_count": 0,
            "session_reset_transition_count": 0,
            "calendar_rollover_transition_count": 0,
            "trajectory_refs_present": False,
            "replay_refs_present": False,
            "admission_inputs_present": False,
            "has_real_data": False,
            "status": STATUS_INSUFFICIENT_EVIDENCE,
            "reason": "No admission-grade real trajectory inputs found.",
        }

    return {
        "real_episode_count": summary.get("real_episode_count", 0),
        "real_session_count": summary.get("real_session_count", 0),
        "real_day_count": summary.get("real_day_count", 0),
        "session_reset_transition_count": summary.get("session_reset_transition_count", 0),
        "calendar_rollover_transition_count": summary.get("calendar_rollover_transition_count", 0),
        "trajectory_refs_present": summary.get("trajectory_refs_present", False),
        "replay_refs_present": summary.get("replay_refs_present", False),
        "admission_inputs_present": summary.get("admission_inputs_present", False),
        "has_real_data": True,
        "status": STATUS_PASS if summary.get("admission_inputs_present", False) else STATUS_ALERT,
    }


def run_daily_check() -> dict:
    """Run all daily checks."""
    timestamp = datetime.now().isoformat()
    
    results = {
        "timestamp": timestamp,
        "tests": check_tests(),
        "continuity": check_continuity(),
        "metrics": check_metrics(),
        "invariants": check_invariants(),
        "admission_inputs": check_admission_inputs(),
    }
    
    # Overall status - handle insufficient_evidence as BLOCKED
    all_statuses = [r["status"] for r in results.values() if isinstance(r, dict) and "status" in r]
    
    if STATUS_INSUFFICIENT_EVIDENCE in all_statuses:
        # If we don't have real data, this is BLOCKED, not PASS
        results["overall_status"] = STATUS_BLOCKED
        results["blocked_reason"] = "Insufficient real developmental data for validation"
    elif STATUS_FAIL in all_statuses:
        results["overall_status"] = STATUS_FAIL
    elif STATUS_ALERT in all_statuses:
        results["overall_status"] = STATUS_ALERT
    else:
        results["overall_status"] = STATUS_PASS
    
    return results


def format_report(results: dict) -> str:
    """Format results as markdown report."""
    lines = [
        f"# MVP16 Daily Observation Report",
        f"",
        f"**Timestamp**: {results['timestamp']}",
        f"**Status**: {results['overall_status']}",
        f"",
    ]
    
    if results.get("blocked_reason"):
        lines.append(f"**Blocked Reason**: {results['blocked_reason']}")
        lines.append(f"")
    
    lines.extend([
        f"## 1. Tests",
        f"- Passed: {results['tests']['passed']}",
        f"- Failed: {results['tests']['failed']}",
        f"- Status: {results['tests']['status']}",
        f"",
        f"## 2. Continuity",
    ])
    
    cont = results['continuity']
    if cont.get("has_real_data"):
        lines.extend([
            f"- Current Phase: {cont['current_phase']}",
            f"- Episodes: {cont['episodes']}",
            f"- Transitions: {cont['transitions']}",
            f"- Real Episodes: {cont.get('real_episode_count', 0)}",
            f"- Real Sessions: {cont.get('real_session_count', 0)}",
            f"- Real Days: {cont.get('real_day_count', 0)}",
            f"- Identity Preserved: {cont['identity_preserved']}",
            f"- Continuity Score: {cont['continuity_score']:.2f}",
            f"- Persisted: {cont.get('persisted', False)}",
            f"- Status: {cont['status']}",
        ])
    else:
        lines.extend([
            f"- **Has Real Data**: No",
            f"- **Status**: {cont['status']}",
            f"- **Reason**: {cont.get('reason', 'No real data')}",
        ])
    
    lines.extend([f"", f"## 3. Metrics"])
    
    met = results['metrics']
    if met.get("has_real_data"):
        for name, data in met['metrics'].items():
            history_indicator = " (real)" if data.get('has_history') else " (initialized)"
            lines.append(f"- {name}: {data['value']:.2f} ({data['trend']}){history_indicator}")
        
        if met['alerts']:
            lines.append(f"")
            lines.append(f"**Alerts**:")
            for alert in met['alerts']:
                lines.append(f"- ⚠️ {alert}")
        
        lines.append(f"- Status: {met['status']}")
    else:
        lines.extend([
            f"- **Has Real Data**: No",
            f"- **Status**: {met['status']}",
            f"- **Reason**: {met.get('reason', 'No real data')}",
        ])
    
    lines.extend([
        f"",
        f"## 4. Invariants",
    ])
    
    inv = results['invariants']
    if inv.get("has_real_data"):
        lines.extend([
            f"- Violation Count: {inv['violation_count']}",
            f"- Trajectory Refs Present: {inv.get('trajectory_refs_present', False)}",
            f"- Replay Refs Present: {inv.get('replay_refs_present', False)}",
            f"- Status: {inv['status']}",
        ])
    else:
        lines.extend([
            f"- **Has Real Data**: No",
            f"- **Status**: {inv['status']}",
            f"- **Reason**: {inv.get('reason', 'No real data')}",
        ])

    lines.extend([
        f"",
        f"## 5. Admission Inputs",
    ])

    adm = results["admission_inputs"]
    if adm.get("has_real_data"):
        lines.extend([
            f"- Real Episode Count: {adm['real_episode_count']}",
            f"- Real Session Count: {adm['real_session_count']}",
            f"- Real Day Count: {adm['real_day_count']}",
            f"- Session Reset Transitions: {adm['session_reset_transition_count']}",
            f"- Calendar Rollover Transitions: {adm['calendar_rollover_transition_count']}",
            f"- Trajectory Refs Present: {adm['trajectory_refs_present']}",
            f"- Replay Refs Present: {adm['replay_refs_present']}",
            f"- Admission Inputs Present: {adm['admission_inputs_present']}",
            f"- Status: {adm['status']}",
        ])
    else:
        lines.extend([
            f"- **Has Real Data**: No",
            f"- **Status**: {adm['status']}",
            f"- **Reason**: {adm.get('reason', 'No real data')}",
        ])

    lines.extend([
        f"",
        f"---",
        f"**Overall**: {results['overall_status']}",
    ])
    
    return "\n".join(lines)


def main():
    results = run_daily_check()
    report = format_report(results)
    
    print(report)
    print()
    print(json.dumps(results, indent=2, default=str))
    
    # Save to artifacts
    day_num = (datetime.now() - datetime(2026, 3, 12)).days + 1
    output_dir = Path(__file__).parent.parent / "artifacts" / "mvp16-observation"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    report_path = output_dir / f"day_{day_num}.md"
    report_path.write_text(report)
    print(f"\nReport saved to: {report_path}")
    
    # Update ROADMAP_STATE.json
    state_path = Path(__file__).parent.parent / "roadmap" / "ROADMAP_STATE.json"
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if "observation_window" in state:
            state["observation_window"]["day"] = day_num
            state["observation_window"]["last_check"] = results["timestamp"]
            state["observation_window"]["overall_status"] = results["overall_status"]
        state["last_update"] = results["timestamp"]
        state_path.write_text(json.dumps(state, indent=2))
    
    # Return exit code - blocked also returns non-zero
    exit_code = 0 if results["overall_status"] == STATUS_PASS else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
