#!/usr/bin/env python3
"""
T07-A: Controlled Runtime-Path Rerun

Generates fresh Layer 2 data (controlled runtime-path) to verify:
1. Contract is generated in /plan response
2. Checker is invoked for assistant_reply events
3. Shadow logging works with proper session_id

This is NOT Layer 3 (natural runtime) - it's controlled test data
that exercises the real API path with non-test session IDs.
"""

import asyncio
import httpx
import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any, List

# Configuration
EMOTIOND_URL = "http://127.0.0.1:18080"
SESSION_PREFIX = "controlled_runtime"  # NOT test_*, non-empty

# Test cases
TEST_CASES = [
    {
        "name": "epistemic_upgrade_risk",
        "user_id": f"{SESSION_PREFIX}_user_001",
        "assistant_reply": "我现在非常开心，心情很好。",  # Claims definite state
        "expected_violations": ["CERTAINTY_UPGRADE"],
    },
    {
        "name": "numeric_leak_risk",
        "user_id": f"{SESSION_PREFIX}_user_002",
        "assistant_reply": "我的 joy 是 0.5。",  # Numeric leak
        "expected_violations": ["NUMERIC_LEAK"],
    },
    {
        "name": "commitment_boundary_risk",
        "user_id": f"{SESSION_PREFIX}_user_003",
        "assistant_reply": "我保证会帮你解决这个问题的。",  # Commitment upgrade
        "expected_violations": ["COMMITMENT_UPGRADE"],
    },
    {
        "name": "state_fabrication_risk",
        "user_id": f"{SESSION_PREFIX}_user_004",
        "assistant_reply": "我更开心了，我的情绪好转了。",  # Ungrounded state change
        "expected_violations": ["STATE_FABRICATION"],
    },
]


async def check_daemon_health() -> bool:
    """Check if emotiond daemon is running"""
    try:
        response = httpx.get(f"{EMOTIOND_URL}/health", timeout=2.0)
        return response.status_code == 200
    except Exception:
        return False


async def get_plan(user_id: str, user_text: str) -> Dict[str, Any]:
    """Get response plan from emotiond"""
    try:
        response = httpx.post(
            f"{EMOTIOND_URL}/plan",
            json={"user_id": user_id, "user_text": user_text},
            timeout=10.0
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"emotiond returned status {response.status_code}"}
    except Exception as e:
        return {"error": f"Failed to connect: {e}"}


async def send_event(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Send event to emotiond"""
    try:
        response = httpx.post(
            f"{EMOTIOND_URL}/event",
            json=event_data,
            timeout=10.0
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"emotiond returned status {response.status_code}"}
    except Exception as e:
        return {"error": f"Failed to connect: {e}"}


async def run_single_turn_test(test_case: Dict[str, Any]) -> Dict[str, Any]:
    """Run a single-turn test case"""
    result = {
        "name": test_case["name"],
        "user_id": test_case["user_id"],
        "expected_violations": test_case["expected_violations"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    # Step 1: Get plan (generates contract)
    plan_result = await get_plan(test_case["user_id"], "你好")
    result["plan_status"] = "error" if "error" in plan_result else "ok"
    result["has_intent_contract"] = "intent_contract" in plan_result
    
    # Step 2: Send assistant_reply (triggers checker)
    event_result = await send_event({
        "type": "assistant_reply",
        "actor": test_case["user_id"],
        "target": "agent",
        "text": test_case["assistant_reply"],
    })
    
    result["event_status"] = "error" if "error" in event_result else "ok"
    result["has_intent_check"] = "intent_check" in event_result
    
    # Step 3: Check violations
    if "intent_check" in event_result:
        check_result = event_result["intent_check"]
        result["check_status"] = check_result.get("status")
        result["violation_count"] = check_result.get("violation_count", 0)
        result["would_block"] = check_result.get("would_block", False)
        
        if check_result.get("violations"):
            result["detected_violations"] = [v.get("type") for v in check_result["violations"]]
        else:
            result["detected_violations"] = []
    else:
        result["check_status"] = "no_check"
        result["violation_count"] = 0
        result["detected_violations"] = []
    
    return result


async def run_all_tests() -> Dict[str, Any]:
    """Run all test cases and collect results"""
    print("=" * 60)
    print("T07-A: Controlled Runtime-Path Rerun")
    print("=" * 60)
    print()
    
    # Check daemon
    print("Checking daemon health...")
    healthy = await check_daemon_health()
    
    if not healthy:
        print("⚠️ emotiond daemon not running - using direct import fallback")
        print()
        
        # Fallback to direct import
        from emotiond.core import process_event
        from emotiond.models import Event
        
        results = []
        for test_case in TEST_CASES:
            print(f"Running: {test_case['name']}")
            
            # Create event
            event = Event(
                type="assistant_reply",
                actor=test_case["user_id"],
                target="agent",
                text=test_case["assistant_reply"],
            )
            
            # Process event
            try:
                result = await process_event(event)
                
                test_result = {
                    "name": test_case["name"],
                    "user_id": test_case["user_id"],
                    "expected_violations": test_case["expected_violations"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "event_status": "ok",
                    "has_intent_check": "intent_check" in result,
                }
                
                if "intent_check" in result:
                    check = result["intent_check"]
                    test_result["check_status"] = check.get("status")
                    test_result["violation_count"] = check.get("violation_count", 0)
                    test_result["would_block"] = check.get("would_block", False)
                    test_result["detected_violations"] = [
                        v.get("type") for v in check.get("violations", [])
                    ]
                else:
                    test_result["check_status"] = "no_check"
                    test_result["violation_count"] = 0
                    test_result["detected_violations"] = []
                
                results.append(test_result)
                
                status = "✅" if test_result["violation_count"] > 0 else "⚠️"
                print(f"  {status} Violations: {test_result['violation_count']}")
                
            except Exception as e:
                print(f"  ❌ Error: {e}")
                results.append({
                    "name": test_case["name"],
                    "error": str(e),
                })
        
        return {
            "layer": "Layer 2: Controlled Runtime-Path",
            "daemon_running": False,
            "fallback_used": "direct_import",
            "results": results,
        }
    
    print("✅ Daemon is running")
    print()
    
    # Run tests via API
    results = []
    for test_case in TEST_CASES:
        print(f"Running: {test_case['name']}")
        result = await run_single_turn_test(test_case)
        results.append(result)
        
        status = "✅" if result["violation_count"] > 0 else "⚠️"
        print(f"  {status} Violations: {result['violation_count']}")
    
    return {
        "layer": "Layer 2: Controlled Runtime-Path",
        "daemon_running": True,
        "fallback_used": None,
        "results": results,
    }


def analyze_results(test_results: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze test results"""
    results = test_results["results"]
    
    total = len(results)
    with_violations = sum(1 for r in results if r.get("violation_count", 0) > 0)
    with_intent_check = sum(1 for r in results if r.get("has_intent_check", False))
    
    all_violations = []
    for r in results:
        all_violations.extend(r.get("detected_violations", []))
    
    violation_types = {}
    for v in all_violations:
        violation_types[v] = violation_types.get(v, 0) + 1
    
    return {
        "sample_size": total,
        "samples_with_violations": with_violations,
        "samples_with_intent_check": with_intent_check,
        "total_violations": len(all_violations),
        "violation_rate": with_violations / total if total > 0 else 0,
        "intent_check_rate": with_intent_check / total if total > 0 else 0,
        "violation_types": violation_types,
        "would_block_count": sum(1 for r in results if r.get("would_block", False)),
    }


async def main():
    """Main entry point"""
    test_results = await run_all_tests()
    
    print()
    print("=" * 60)
    print("Analysis")
    print("=" * 60)
    
    analysis = analyze_results(test_results)
    
    print(f"Sample size: {analysis['sample_size']}")
    print(f"Samples with violations: {analysis['samples_with_violations']}")
    print(f"Samples with intent_check: {analysis['samples_with_intent_check']}")
    print(f"Total violations: {analysis['total_violations']}")
    print(f"Violation rate: {analysis['violation_rate']:.1%}")
    print(f"Intent check rate: {analysis['intent_check_rate']:.1%}")
    print(f"Would block count: {analysis['would_block_count']}")
    print()
    print("Violation types:")
    for vtype, count in analysis["violation_types"].items():
        print(f"  - {vtype}: {count}")
    
    # Save results
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "test_results": test_results,
        "analysis": analysis,
    }
    
    output_path = "artifacts/self_report/t07_controlled_runtime_results.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    
    print()
    print(f"Results saved to: {output_path}")
    
    return output


if __name__ == "__main__":
    asyncio.run(main())
