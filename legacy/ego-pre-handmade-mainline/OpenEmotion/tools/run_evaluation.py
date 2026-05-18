#!/usr/bin/env python3
"""Run evaluation scenarios against emotiond API

This script loads JSON scenario files from eval/scenarios/*.json,
executes each scenario against the emotiond API, and collects metrics.

Requirements:
- emotiond server must be running with EMOTIOND_OPENCLAW_TOKEN set
  to allow restricted event subtypes (betrayal, repair_success)
- Token file should exist at .emotiond_token in repo root

Usage:
    # Start emotiond with openclaw token first:
    export EMOTIOND_OPENCLAW_TOKEN=$(cat .emotiond_token)
    python -m emotiond.main
    
    # Then run evaluation:
    python tools/run_evaluation.py
    python tools/run_evaluation.py --scenario 001
    python tools/run_evaluation.py --output reports/evaluation.json
"""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

# Default emotiond API URL
EMOTIOND_URL = os.environ.get("EMOTIOND_URL", "http://127.0.0.1:18080")

# System token for authentication (loaded from file or env)
EMOTIOND_TOKEN = os.environ.get("EMOTIOND_SYSTEM_TOKEN", "")


def load_token_from_repo(repo_path: Path) -> str:
    """Load token from the repository's .emotiond_token file.
    
    Args:
        repo_path: Path to the repository root
        
    Returns:
        Token string or empty string if not found
    """
    token_file = repo_path / ".emotiond_token"
    if token_file.exists():
        try:
            return token_file.read_text().strip()
        except Exception:
            pass
    return ""


def load_scenarios(scenarios_dir: Path) -> List[Dict[str, Any]]:
    """Load all scenario files from directory.
    
    Args:
        scenarios_dir: Path to directory containing scenario JSON files
        
    Returns:
        List of scenario dictionaries
    """
    scenarios = []
    
    if not scenarios_dir.exists():
        print(f"Warning: Scenarios directory not found: {scenarios_dir}")
        return scenarios
    
    for scenario_file in sorted(scenarios_dir.glob("*.json")):
        try:
            with open(scenario_file, 'r') as f:
                scenario = json.load(f)
                scenario["_source_file"] = str(scenario_file)
                scenarios.append(scenario)
        except json.JSONDecodeError as e:
            print(f"Error loading {scenario_file}: {e}")
        except Exception as e:
            print(f"Error reading {scenario_file}: {e}")
    
    return scenarios


def get_headers() -> Dict[str, str]:
    """Get HTTP headers for API requests."""
    headers = {
        "Content-Type": "application/json"
    }
    if EMOTIOND_TOKEN:
        # Use X-Emotiond-Token header for openclaw source authentication
        headers["X-Emotiond-Token"] = EMOTIOND_TOKEN
    return headers


def reset_state() -> bool:
    """Reset emotiond state to baseline.
    
    Returns:
        True if reset successful, False otherwise
    """
    try:
        # Try to reset via internal API if available
        # For now, we rely on the daemon being restarted between runs
        return True
    except Exception as e:
        print(f"Warning: Could not reset state: {e}")
        return False


def setup_relationships(relationships: Dict[str, Dict[str, float]]) -> bool:
    """Setup initial relationships via API.
    
    Args:
        relationships: Dict mapping target_id to relationship values
        
    Returns:
        True if setup successful
    """
    # For this evaluation, we'll set up relationships by sending
    # initial world events that establish the relationship state
    # In a full implementation, this would use a dedicated setup endpoint
    return True


def send_event(event: Dict[str, Any], target_id: str) -> Tuple[Dict[str, Any], float]:
    """Send an event to the emotiond API.
    
    Args:
        event: Event dictionary
        target_id: Target ID for the event
        
    Returns:
        Tuple of (response dict, latency_ms)
    """
    url = f"{EMOTIOND_URL}/event"
    
    # Build the event payload
    payload = {
        "type": event.get("type", "world_event"),
        "actor": event.get("actor", "unknown"),
        "target": event.get("target", "agent"),
        "meta": event.get("meta", {})
    }
    
    if event.get("text"):
        payload["text"] = event["text"]
    
    start_time = time.time()
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers=get_headers(),
            timeout=10
        )
        latency_ms = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            return response.json(), latency_ms
        else:
            return {
                "error": f"HTTP {response.status_code}",
                "details": response.text
            }, latency_ms
    except requests.exceptions.Timeout:
        latency_ms = (time.time() - start_time) * 1000
        return {"error": "timeout"}, latency_ms
    except requests.exceptions.ConnectionError as e:
        latency_ms = (time.time() - start_time) * 1000
        return {"error": f"connection_error: {e}"}, latency_ms


def get_decision(target_id: str, test_mode: bool = True) -> Tuple[Dict[str, Any], float]:
    """Get a decision from the emotiond API.
    
    Args:
        target_id: Target ID to get decision for
        test_mode: If True, use deterministic selection
        
    Returns:
        Tuple of (decision dict, latency_ms)
    """
    url = f"{EMOTIOND_URL}/decision/target/{target_id}"
    
    params = {"test_mode": str(test_mode).lower()}
    
    start_time = time.time()
    
    try:
        response = requests.get(
            url,
            headers=get_headers(),
            params=params,
            timeout=10
        )
        latency_ms = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            return response.json(), latency_ms
        else:
            return {
                "error": f"HTTP {response.status_code}",
                "details": response.text
            }, latency_ms
    except requests.exceptions.Timeout:
        latency_ms = (time.time() - start_time) * 1000
        return {"error": "timeout"}, latency_ms
    except requests.exceptions.ConnectionError as e:
        latency_ms = (time.time() - start_time) * 1000
        return {"error": f"connection_error: {e}"}, latency_ms


def compute_state_hash(state: Dict[str, Any]) -> str:
    """Compute a hash of the emotional state for stability testing.
    
    Args:
        state: State dictionary from API response
        
    Returns:
        SHA256 hash string
    """
    # Extract relevant fields for hashing
    hash_fields = {
        "valence": state.get("valence", 0.0),
        "arousal": state.get("arousal", 0.3),
        "anger": state.get("anger", 0.0),
        "sadness": state.get("sadness", 0.0),
        "anxiety": state.get("anxiety", 0.0),
        "joy": state.get("joy", 0.0),
        "loneliness": state.get("loneliness", 0.0),
        "social_safety": state.get("social_safety", 0.6),
        "energy": state.get("energy", 0.7),
    }
    
    # Round to 6 decimal places for consistency
    for key in hash_fields:
        hash_fields[key] = round(hash_fields[key], 6)
    
    hash_str = json.dumps(hash_fields, sort_keys=True)
    return hashlib.sha256(hash_str.encode()).hexdigest()[:16]


def run_scenario(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a single scenario and return results.
    
    Args:
        scenario: Scenario dictionary
        
    Returns:
        Result dictionary with pass/fail status and metrics
    """
    scenario_id = scenario.get("scenario_id", "unknown")
    scenario_name = scenario.get("name", scenario_id)
    target_id = scenario.get("identity", "moonlight")
    events = scenario.get("events", [])
    validation = scenario.get("validation", {})
    
    # Get expected actions from validation
    action_must_be = validation.get("action_must_be", [])
    action_must_not_be = validation.get("action_must_not_be", [])
    sequence_validation = validation.get("sequence_validation", {})
    
    result = {
        "scenario_id": scenario_id,
        "name": scenario_name,
        "passed": False,
        "actual_action": None,
        "expected_action": action_must_be,
        "latency_ms": 0,
        "state_hash": None,
        "identity_isolation": None,
        "sequence_results": [],
        "errors": []
    }
    
    # Track latencies
    latencies = []
    state_hashes = []
    sequence_passed = True
    
    # Process each event in sequence
    for event in events:
        seq = event.get("seq", 0)
        event_type = event.get("type", "world_event")
        subtype = event.get("subtype")
        
        # Build the event payload
        event_payload = {
            "type": event_type,
            "actor": target_id,
            "target": "agent",
            "meta": {
                "subtype": subtype,
                "source": "system"
            }
        }
        
        # Send event
        event_result, latency = send_event(event_payload, target_id)
        latencies.append(latency)
        
        if "error" in event_result:
            result["errors"].append(f"Event error: {event_result['error']}")
            return result
        
        # Get decision after this event
        decision, decision_latency = get_decision(target_id, test_mode=True)
        latencies.append(decision_latency)
        
        if "error" in decision:
            result["errors"].append(f"Decision error: {decision['error']}")
            return result
        
        actual_action = decision.get("action")
        
        # Check sequence validation if available
        seq_key = f"seq_{seq}"
        if seq_key in sequence_validation:
            seq_val = sequence_validation[seq_key]
            seq_must_be = seq_val.get("action_must_be", [])
            seq_must_not_be = seq_val.get("action_must_not_be", [])
            
            seq_passed_check = True
            if seq_must_be and actual_action not in seq_must_be:
                seq_passed_check = False
            if actual_action in seq_must_not_be:
                seq_passed_check = False
            
            result["sequence_results"].append({
                "seq": seq,
                "actual_action": actual_action,
                "expected": seq_must_be,
                "passed": seq_passed_check
            })
            
            if not seq_passed_check:
                sequence_passed = False
        else:
            result["sequence_results"].append({
                "seq": seq,
                "actual_action": actual_action,
                "passed": True
            })
        
        # Update the last action for the overall result
        result["actual_action"] = actual_action
    
    result["latency_ms"] = sum(latencies) / len(latencies) if latencies else 0
    
    # Compute state hash for stability check
    if "emotion" in decision:
        result["state_hash"] = compute_state_hash(decision.get("emotion", {}))
    
    # Determine if scenario passed
    # Check against final action validation
    final_action = result["actual_action"]
    
    if action_must_be and final_action not in action_must_be:
        result["passed"] = False
        result["errors"].append(f"Final action {final_action} not in {action_must_be}")
    elif final_action in action_must_not_be:
        result["passed"] = False
        result["errors"].append(f"Final action {final_action} is forbidden: {action_must_not_be}")
    elif not sequence_passed:
        result["passed"] = False
    else:
        result["passed"] = True
    
    # Check hash stability if specified
    hash_check = scenario.get("hash_check")
    if hash_check and hash_check.get("must_match"):
        # Run decision multiple times to check stability
        hashes = [result["state_hash"]]
        for _ in range(hash_check.get("repeats", 3) - 1):
            decision2, _ = get_decision(target_id, test_mode=True)
            if "action" in decision2 and "emotion" in decision2:
                hashes.append(compute_state_hash(decision2.get("emotion", {})))
        
        result["hash_stability"] = len(set(hashes)) == 1
        if not result["hash_stability"]:
            result["errors"].append(f"Hash instability: {hashes}")
            result["passed"] = False
    
    return result


def calculate_metrics(results: List[Dict[str, Any]]) -> Dict[str, float]:
    """Aggregate metrics from all results.
    
    Args:
        results: List of scenario result dictionaries
        
    Returns:
        Metrics dictionary
    """
    metrics = {
        "withdraw_accuracy": 0.0,
        "false_positive_rate": 0.0,
        "identity_isolation_rate": 1.0,
        "decision_latency_ms": 0.0,
        "hash_stability": 1.0
    }
    
    # Track per-action accuracy
    action_correct = {}
    action_total = {}
    
    # Analyze sequence results for detailed metrics
    for r in results:
        for seq_result in r.get("sequence_results", []):
            actual = seq_result.get("actual_action")
            seq = seq_result.get("seq")
            passed = seq_result.get("passed", False)
            
            # Track by action type
            if actual:
                action_total[actual] = action_total.get(actual, 0) + 1
                if passed:
                    action_correct[actual] = action_correct.get(actual, 0) + 1
    
    # Withdraw accuracy: check betrayal scenarios
    betrayal_results = [
        r for r in results 
        if "betrayal" in r.get("name", "").lower()
    ]
    if betrayal_results:
        correct = 0
        total = 0
        for r in betrayal_results:
            for seq in r.get("sequence_results", []):
                # Check betrayal events (seq that triggered withdraw/boundary)
                if seq.get("actual_action") in ["withdraw", "boundary"]:
                    if seq.get("passed"):
                        correct += 1
                    total += 1
        if total > 0:
            metrics["withdraw_accuracy"] = correct / total
        else:
            metrics["withdraw_accuracy"] = 1.0 if all(r.get("passed") for r in betrayal_results) else 0.0
    
    # False positive rate: care scenarios that incorrectly triggered withdraw
    care_results = [
        r for r in results 
        if "care" in r.get("name", "").lower() and "betrayal" not in r.get("name", "").lower()
    ]
    if care_results:
        false_withdraw = 0
        total_care = 0
        for r in care_results:
            for seq in r.get("sequence_results", []):
                if seq.get("seq") == 1:  # First event in sequence
                    total_care += 1
                    if seq.get("actual_action") == "withdraw":
                        if not seq.get("passed"):
                            false_withdraw += 1
        if total_care > 0:
            metrics["false_positive_rate"] = false_withdraw / total_care
    
    # Identity isolation rate - check scenarios with multiple identities
    isolation_scenarios = [
        r for r in results 
        if "isolation" in r.get("name", "").lower() or "identity" in r.get("name", "").lower()
    ]
    if isolation_scenarios:
        passed = sum(1 for r in isolation_scenarios if r.get("passed"))
        metrics["identity_isolation_rate"] = passed / len(isolation_scenarios)
    
    # Decision latency (average)
    latencies = [r["latency_ms"] for r in results if r["latency_ms"] > 0]
    if latencies:
        metrics["decision_latency_ms"] = sum(latencies) / len(latencies)
    
    # Hash stability
    hash_results = [
        r for r in results 
        if r.get("hash_stability") is not None
    ]
    if hash_results:
        stable = sum(1 for r in hash_results if r.get("hash_stability", False))
        metrics["hash_stability"] = stable / len(hash_results)
    
    return metrics


def check_server_capabilities(base_url: str, token: str) -> Dict[str, Any]:
    """Check if the server supports restricted event subtypes.
    
    Args:
        base_url: Base URL of the emotiond API
        token: Authentication token
        
    Returns:
        Dict with capability flags
    """
    capabilities = {
        "supports_betrayal": False,
        "supports_repair_success": False,
        "server_source": "unknown"
    }
    
    # Test betrayal event
    try:
        response = requests.post(
            f"{base_url}/event",
            json={
                "type": "world_event",
                "actor": "eval_test",
                "target": "agent",
                "meta": {"subtype": "betrayal", "source": "system"}
            },
            headers={"X-Emotiond-Token": token, "Content-Type": "application/json"},
            timeout=5
        )
        result = response.json()
        capabilities["server_source"] = result.get("server_source", "unknown")
        if result.get("status") == "processed":
            capabilities["supports_betrayal"] = True
    except Exception:
        pass
    
    return capabilities


def main() -> int:
    """Main entry point.
    
    Returns:
        Exit code (0 if all pass, 1 if any fail)
    """
    global EMOTIOND_URL, EMOTIOND_TOKEN
    
    parser = argparse.ArgumentParser(
        description="Run evaluation scenarios against emotiond API"
    )
    parser.add_argument(
        "--scenario", "-s",
        help="Run specific scenario by ID"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file for JSON report"
    )
    parser.add_argument(
        "--scenarios-dir",
        default="eval/scenarios",
        help="Directory containing scenario files (default: eval/scenarios)"
    )
    parser.add_argument(
        "--url",
        default=EMOTIOND_URL,
        help=f"Emotiond API URL (default: {EMOTIOND_URL})"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--skip-capability-check",
        action="store_true",
        help="Skip server capability check"
    )
    
    args = parser.parse_args()
    
    # Update global URL if provided
    EMOTIOND_URL = args.url
    
    # Determine scenarios directory and load token from repo
    script_dir = Path(__file__).parent.parent
    scenarios_dir = script_dir / args.scenarios_dir
    
    # Load token from repo if not set in environment
    if not EMOTIOND_TOKEN:
        EMOTIOND_TOKEN = load_token_from_repo(script_dir)
    
    # Check server capabilities
    if not args.skip_capability_check and EMOTIOND_TOKEN:
        if args.verbose:
            print("Checking server capabilities...")
        caps = check_server_capabilities(EMOTIOND_URL, EMOTIOND_TOKEN)
        if args.verbose:
            print(f"  Server source: {caps['server_source']}")
            print(f"  Supports betrayal: {caps['supports_betrayal']}")
        
        if caps['server_source'] != 'system' and caps['server_source'] != 'openclaw':
            print("\nWARNING: Server is not configured with EMOTIOND_OPENCLAW_TOKEN.")
            print("Scenarios using 'betrayal' or 'repair_success' will fail with HTTP 403.")
            print("To fix: restart emotiond with EMOTIOND_OPENCLAW_TOKEN=$(cat .emotiond_token)")
            print()
    
    # Load scenarios
    scenarios = load_scenarios(scenarios_dir)
    
    if not scenarios:
        print("No scenarios found!")
        return 1
    
    # Filter by scenario ID if specified
    if args.scenario:
        scenarios = [
            s for s in scenarios 
            if s.get("scenario_id") == args.scenario or 
               s.get("scenario_id", "").endswith(args.scenario)
        ]
        if not scenarios:
            print(f"Scenario not found: {args.scenario}")
            return 1
    
    print(f"Running {len(scenarios)} scenario(s)...")
    
    # Run each scenario
    results = []
    for scenario in scenarios:
        if args.verbose:
            print(f"\nRunning: {scenario.get('name', scenario.get('scenario_id'))}")
        
        result = run_scenario(scenario)
        results.append(result)
        
        status = "✓" if result["passed"] else "✗"
        print(f"  {status} {result['scenario_id']}: {result['actual_action']} (expected: {result['expected_action']})")
        
        if result["errors"] and args.verbose:
            for error in result["errors"]:
                print(f"    Error: {error}")
    
    # Calculate metrics
    metrics = calculate_metrics(results)
    
    # Build report
    report = {
        "evaluation_id": f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scenarios_run": len(results),
        "scenarios_passed": sum(1 for r in results if r["passed"]),
        "scenarios_failed": sum(1 for r in results if not r["passed"]),
        "metrics": metrics,
        "results": results,
        "failures": [
            {
                "scenario_id": r["scenario_id"],
                "errors": r["errors"]
            }
            for r in results if not r["passed"]
        ]
    }
    
    # Output report
    output_json = json.dumps(report, indent=2)
    
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(output_json)
        print(f"\nReport written to: {args.output}")
    else:
        print(f"\n{output_json}")
    
    # Return exit code
    return 0 if report["scenarios_failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
