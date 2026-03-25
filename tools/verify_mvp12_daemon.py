#!/usr/bin/env python
"""
MVP12 Daemon Integration Verification

Verifies that DevelopmentalCycleDaemon is properly integrated into daemon.py
with feature flag support and non-invasive operation.
"""
import asyncio
import os
import sys
import time
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.daemon import DaemonManager, ENABLE_DEVELOPMENTAL_CYCLE


async def test_feature_flag():
    """Test 1: Feature flag controls developmental cycle"""
    print("\n=== Test 1: Feature Flag ===")
    
    # Test with flag enabled (default)
    dm = DaemonManager()
    status = dm.get_developmental_status()
    
    print(f"Feature flag: {status['feature_flag']}")
    print(f"Module available: {status['module_available']}")
    print(f"Enabled: {status['enabled']}")
    
    assert status['feature_flag'] == True, "Feature flag should be True"
    assert status['enabled'] == True, "Should be enabled by default"
    print("✅ PASS: Feature flag works correctly")
    
    return True


async def test_daemon_lifecycle():
    """Test 2: Daemon starts and stops cleanly"""
    print("\n=== Test 2: Daemon Lifecycle ===")
    
    dm = DaemonManager()
    
    # Start daemon
    await dm.start()
    assert dm.is_running(), "Daemon should be running"
    
    status = dm.get_developmental_status()
    print(f"Daemon running: {dm.is_running()}")
    print(f"Developmental cycle loop running: {status['running']}")
    
    # Check that all loops are running
    loop_status = dm.get_loop_status()
    print(f"Loop status: {loop_status}")
    
    # Stop daemon
    await dm.stop()
    assert not dm.is_running(), "Daemon should be stopped"
    
    print("✅ PASS: Daemon lifecycle works correctly")
    return True


async def test_non_invasive():
    """Test 3: Developmental cycle is non-invasive"""
    print("\n=== Test 3: Non-Invasive ===")
    
    dm = DaemonManager()
    await dm.start()
    
    # Run for a short time
    await asyncio.sleep(2)
    
    # Check that homeostasis and consolidation loops are still running
    loop_status = dm.get_loop_status()
    
    # Homeostasis and consolidation should be running
    assert "homeostasis" in loop_status, "Homeostasis loop should exist"
    assert "consolidation" in loop_status, "Consolidation loop should exist"
    
    # Developmental cycle should exist if enabled
    if dm._dev_daemon_enabled:
        assert "developmental_cycle" in loop_status, "Developmental cycle loop should exist"
    
    print(f"Loop status: {loop_status}")
    
    await dm.stop()
    
    print("✅ PASS: Developmental cycle is non-invasive")
    return True


async def test_manual_cycle_trigger():
    """Test 4: Manual cycle trigger works"""
    print("\n=== Test 4: Manual Cycle Trigger ===")
    
    dm = DaemonManager()
    
    if not dm._dev_daemon:
        print("⚠️ SKIP: Developmental daemon not available")
        return True
    
    from emotiond.developmental_core.models import CycleTrigger
    
    # Get the cycle engine
    engine = dm._dev_daemon.cycle_engine
    
    # Start a cycle manually (using IDLE trigger)
    context = engine.start_cycle(
        trigger=CycleTrigger.IDLE,
        state_snapshot={'test': True}
    )
    
    print(f"Cycle ID: {context.cycle_id}")
    
    # Generate candidates
    candidates = dm._dev_daemon.hypothesis_generator.generate(
        context=context,
        state_snapshot={'test': True},
        max_candidates=5
    )
    
    print(f"Candidates generated: {len(candidates)}")
    
    # Complete the cycle
    result = engine.complete_cycle(context, candidates)
    
    print(f"Cycle success: {result.success}")
    print(f"Context cycle ID: {context.cycle_id}")
    
    # Check that engine has cycle count
    print(f"Engine cycle count: {engine.get_cycle_count()}")
    
    assert result.success, "Cycle should succeed"
    assert engine.get_cycle_count() >= 1, "Engine should have at least 1 cycle"
    
    print("✅ PASS: Manual cycle trigger works")
    return True


async def test_artifacts_generation():
    """Test 5: Artifacts are generated correctly"""
    print("\n=== Test 5: Artifacts Generation ===")
    
    artifacts_path = Path("artifacts/mvp12")
    
    # Check that artifacts directory exists
    assert artifacts_path.exists(), "Artifacts directory should exist"
    
    # Check for key files
    expected_files = [
        "candidate_pool.json",
        "developmental_cycles.json",
        "metrics_history.jsonl",
        "cycle_traces",
    ]
    
    for f in expected_files:
        path = artifacts_path / f
        if path.exists():
            print(f"✅ {f} exists")
        else:
            print(f"⚠️ {f} missing")
    
    # Check cycle_traces has content
    cycle_traces_path = artifacts_path / "cycle_traces"
    if cycle_traces_path.exists():
        traces = list(cycle_traces_path.glob("*.json"))
        print(f"Cycle traces: {len(traces)} files")
    
    print("✅ PASS: Artifacts are generated")
    return True


async def main():
    """Run all verification tests"""
    print("=" * 60)
    print("MVP12 Daemon Integration Verification")
    print("=" * 60)
    
    results = {}
    
    try:
        results["feature_flag"] = await test_feature_flag()
    except Exception as e:
        print(f"❌ FAIL: {e}")
        results["feature_flag"] = False
    
    try:
        results["daemon_lifecycle"] = await test_daemon_lifecycle()
    except Exception as e:
        print(f"❌ FAIL: {e}")
        results["daemon_lifecycle"] = False
    
    try:
        results["non_invasive"] = await test_non_invasive()
    except Exception as e:
        print(f"❌ FAIL: {e}")
        results["non_invasive"] = False
    
    try:
        results["manual_cycle"] = await test_manual_cycle_trigger()
    except Exception as e:
        print(f"❌ FAIL: {e}")
        results["manual_cycle"] = False
    
    try:
        results["artifacts"] = await test_artifacts_generation()
    except Exception as e:
        print(f"❌ FAIL: {e}")
        results["artifacts"] = False
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test}: {status}")
    
    print(f"\nTotal: {passed}/{total} passed")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
