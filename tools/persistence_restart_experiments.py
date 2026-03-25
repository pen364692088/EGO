#!/usr/bin/env python3
"""
Persistence and Restart Experiments for MVP11.5-16

This script tests whether state persists across:
1. Process restart (in-memory state lost)
2. Manager reset (intentional reset)
3. State serialization/deserialization
"""
import sys
import json
import time
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import modules
from emotiond.self_model import (
    get_self_model_v0, reset_self_model_v0,
    get_self_model_manager, reset_self_model_manager
)
from emotiond.drives import get_drive_manager, reset_drive_manager
from emotiond.developmental import get_developmental_manager, reset_developmental_manager
from emotiond.self_model.persistence import get_persistence, reset_persistence


def experiment_self_model_persistence():
    """
    Test if self-model state persists across manager reset.
    """
    print("\n" + "="*60)
    print("EXPERIMENT 1: Self-Model Persistence")
    print("="*60)
    
    results = {
        "experiment": "self_model_persistence",
        "tests": []
    }
    
    # Test 1: Legacy SelfModelV0 - Reset behavior
    print("\n[Test 1.1] Legacy SelfModelV0 - Reset Behavior")
    reset_self_model_v0()
    model = get_self_model_v0("test_target")
    
    # Record initial state
    initial_valence = getattr(model, 'valence', None)
    print(f"  Initial model valence: {initial_valence}")
    
    # Reset and get again
    reset_self_model_v0()
    model2 = get_self_model_v0("test_target")
    after_reset_valence = getattr(model2, 'valence', None)
    print(f"  After reset valence: {after_reset_valence}")
    
    test_result = {
        "name": "legacy_reset_behavior",
        "status": "PASS",
        "evidence": "Reset creates fresh instance (expected for in-memory)",
        "persistence": False,
        "reason": "Legacy SelfModelV0 is in-memory only, reset clears state"
    }
    results["tests"].append(test_result)
    print(f"  ℹ️ Legacy SelfModelV0 is in-memory, no persistence across reset")
    
    # Test 2: MVP13 SelfModelManager - Reset behavior
    print("\n[Test 1.2] MVP13 SelfModelManager - Reset Behavior")
    reset_self_model_manager()
    try:
        manager = get_self_model_manager()
        state = manager.state
        
        # Record initial state
        initial_phase = state.trajectory.current_phase if hasattr(state, 'trajectory') else None
        print(f"  Initial phase: {initial_phase}")
        
        # Reset and check
        reset_self_model_manager()
        manager2 = get_self_model_manager()
        state2 = manager2.state
        after_reset_phase = state2.trajectory.current_phase if hasattr(state2, 'trajectory') else None
        print(f"  After reset phase: {after_reset_phase}")
        
        test_result = {
            "name": "mvp13_reset_behavior",
            "status": "PASS",
            "evidence": f"Phase before/after reset: {initial_phase} -> {after_reset_phase}",
            "persistence": False,
            "reason": "MVP13 SelfModelManager is in-memory, reset creates fresh instance"
        }
        results["tests"].append(test_result)
        print(f"  ℹ️ MVP13 SelfModelManager is in-memory, no persistence across reset")
        
    except Exception as e:
        test_result = {
            "name": "mvp13_reset_behavior",
            "status": "FAIL",
            "evidence": f"Exception: {e}"
        }
        results["tests"].append(test_result)
        print(f"  ❌ Error: {e}")
    
    # Test 3: MVP13 SelfModelPersistence - File persistence
    print("\n[Test 1.3] MVP13 SelfModelPersistence - File Persistence")
    reset_persistence()
    try:
        persistence = get_persistence()
        
        # Check if persistence has save/load methods
        if hasattr(persistence, 'save') and hasattr(persistence, 'load'):
            test_result = {
                "name": "mvp13_persistence_api",
                "status": "PASS",
                "evidence": "Persistence has save/load methods"
            }
            results["tests"].append(test_result)
            print(f"  ✅ Persistence API exists")
            
            # Check if it actually saves to disk
            if hasattr(persistence, 'path'):
                print(f"  Persistence path: {persistence.path}")
        else:
            test_result = {
                "name": "mvp13_persistence_api",
                "status": "FAIL",
                "evidence": "Persistence missing save/load methods"
            }
            results["tests"].append(test_result)
            print(f"  ❌ Persistence API incomplete")
            
    except Exception as e:
        test_result = {
            "name": "mvp13_persistence_api",
            "status": "FAIL",
            "evidence": f"Exception: {e}"
        }
        results["tests"].append(test_result)
        print(f"  ❌ Error: {e}")
    
    # Test 4: Check if persistence is actually used by main chain
    print("\n[Test 1.4] Self-Model Persistence - Main Chain Usage")
    try:
        import emotiond.core as core_module
        source = Path(core_module.__file__).read_text()
        
        if "SelfModelPersistence" in source or "get_persistence" in source:
            test_result = {
                "name": "persistence_main_chain_usage",
                "status": "PASS",
                "evidence": "core.py uses SelfModelPersistence"
            }
            results["tests"].append(test_result)
            print(f"  ✅ Persistence used by main chain")
        else:
            test_result = {
                "name": "persistence_main_chain_usage",
                "status": "FAIL",
                "evidence": "core.py does NOT use SelfModelPersistence"
            }
            results["tests"].append(test_result)
            print(f"  ❌ Persistence NOT used by main chain")
            
    except Exception as e:
        test_result = {
            "name": "persistence_main_chain_usage",
            "status": "FAIL",
            "evidence": f"Exception: {e}"
        }
        results["tests"].append(test_result)
        print(f"  ❌ Error: {e}")
    
    return results


def experiment_drives_persistence():
    """
    Test if drive state persists across manager reset.
    """
    print("\n" + "="*60)
    print("EXPERIMENT 2: Drives Persistence")
    print("="*60)
    
    results = {
        "experiment": "drives_persistence",
        "tests": []
    }
    
    # Test 1: MVP14 DriveManager - Reset behavior
    print("\n[Test 2.1] MVP14 DriveManager - Reset Behavior")
    reset_drive_manager()
    try:
        manager = get_drive_manager()
        state = manager.state
        
        # Get initial state
        initial_drives = len(state.active_drives) if hasattr(state, 'active_drives') else 0
        print(f"  Initial drives count: {initial_drives}")
        
        # Reset and check
        reset_drive_manager()
        manager2 = get_drive_manager()
        state2 = manager2.state
        after_reset_drives = len(state2.active_drives) if hasattr(state2, 'active_drives') else 0
        print(f"  After reset drives count: {after_reset_drives}")
        
        test_result = {
            "name": "drives_reset_behavior",
            "status": "PASS",
            "evidence": "Reset creates fresh instance",
            "persistence": False,
            "reason": "DriveManager is in-memory, reset creates fresh instance"
        }
        results["tests"].append(test_result)
        print(f"  ℹ️ DriveManager is in-memory, no persistence across reset")
        
    except Exception as e:
        test_result = {
            "name": "drives_reset_behavior",
            "status": "FAIL",
            "evidence": f"Exception: {e}"
        }
        results["tests"].append(test_result)
        print(f"  ❌ Error: {e}")
    
    # Test 2: Check if drives have persistence mechanism
    print("\n[Test 2.2] MVP14 DriveManager - Persistence Mechanism")
    reset_drive_manager()
    try:
        manager = get_drive_manager()
        
        # Check for save/load methods
        has_save = hasattr(manager, 'save') or hasattr(manager.state, 'save')
        has_load = hasattr(manager, 'load') or hasattr(manager.state, 'load')
        
        if has_save and has_load:
            test_result = {
                "name": "drives_persistence_mechanism",
                "status": "PASS",
                "evidence": "DriveManager has save/load methods"
            }
            results["tests"].append(test_result)
            print(f"  ✅ DriveManager has persistence methods")
        else:
            test_result = {
                "name": "drives_persistence_mechanism",
                "status": "FAIL",
                "evidence": f"DriveManager missing persistence (save: {has_save}, load: {has_load})"
            }
            results["tests"].append(test_result)
            print(f"  ❌ DriveManager has no persistence mechanism")
            
    except Exception as e:
        test_result = {
            "name": "drives_persistence_mechanism",
            "status": "FAIL",
            "evidence": f"Exception: {e}"
        }
        results["tests"].append(test_result)
        print(f"  ❌ Error: {e}")
    
    return results


def experiment_developmental_persistence():
    """
    Test if developmental state persists across manager reset.
    This is the most critical for MVP16.
    """
    print("\n" + "="*60)
    print("EXPERIMENT 3: Developmental Persistence (CRITICAL FOR MVP16)")
    print("="*60)
    
    results = {
        "experiment": "developmental_persistence",
        "tests": []
    }
    
    # Test 1: Add episodes, then reset
    print("\n[Test 3.1] Developmental Manager - Episode Persistence Across Reset")
    reset_developmental_manager()
    manager = get_developmental_manager()
    
    # Add episodes
    for i in range(3):
        manager.record_episode(f"test_ep_{i}", "MVP16", f"Test episode {i}")
    
    episodes_before = len(manager.state.trajectory.episodes)
    continuity_before = manager.get_continuity_score()
    print(f"  Before reset: {episodes_before} episodes, continuity={continuity_before:.3f}")
    
    # Reset
    reset_developmental_manager()
    manager2 = get_developmental_manager()
    
    episodes_after = len(manager2.state.trajectory.episodes)
    continuity_after = manager2.get_continuity_score()
    print(f"  After reset: {episodes_after} episodes, continuity={continuity_after:.3f}")
    
    if episodes_after == episodes_before:
        test_result = {
            "name": "episodes_persist_across_reset",
            "status": "PASS",
            "evidence": f"Episodes preserved: {episodes_before} -> {episodes_after}"
        }
        results["tests"].append(test_result)
        print(f"  ✅ Episodes persist across reset")
    else:
        test_result = {
            "name": "episodes_persist_across_reset",
            "status": "FAIL",
            "evidence": f"Episodes LOST: {episodes_before} -> {episodes_after}",
            "critical": True,
            "reason": "DevelopmentalManager reset clears state - NO PERSISTENCE"
        }
        results["tests"].append(test_result)
        print(f"  ❌ Episodes LOST across reset - NO PERSISTENCE")
    
    # Test 2: Check persistence mechanism
    print("\n[Test 3.2] Developmental Manager - Persistence Mechanism")
    reset_developmental_manager()
    manager = get_developmental_manager()
    
    # Check for save/load methods
    has_save = hasattr(manager, 'save') or hasattr(manager.state, 'save') or hasattr(manager.state, 'to_json')
    has_load = hasattr(manager, 'load') or hasattr(manager.state, 'load') or hasattr(manager.state, 'from_json')
    
    if has_save and has_load:
        test_result = {
            "name": "developmental_persistence_mechanism",
            "status": "PASS",
            "evidence": f"Has persistence methods (save: {has_save}, load: {has_load})"
        }
        results["tests"].append(test_result)
        print(f"  ✅ DevelopmentalManager has persistence methods")
    else:
        test_result = {
            "name": "developmental_persistence_mechanism",
            "status": "FAIL",
            "evidence": f"NO persistence methods (save: {has_save}, load: {has_load})",
            "critical": True
        }
        results["tests"].append(test_result)
        print(f"  ❌ DevelopmentalManager has NO persistence mechanism")
    
    # Test 3: Check if persistence is actually used
    print("\n[Test 3.3] Developmental Persistence - Actual File Storage")
    
    # Check if there's a persistence file
    persistence_paths = [
        Path(__file__).parent.parent / "artifacts" / "developmental" / "state.json",
        Path(__file__).parent.parent / "state" / "developmental.json",
        Path(__file__).parent.parent / "data" / "developmental_state.json",
    ]
    
    found_persistence_file = None
    for path in persistence_paths:
        if path.exists():
            found_persistence_file = path
            break
    
    if found_persistence_file:
        test_result = {
            "name": "developmental_persistence_file",
            "status": "PASS",
            "evidence": f"Found persistence file: {found_persistence_file}"
        }
        results["tests"].append(test_result)
        print(f"  ✅ Found persistence file: {found_persistence_file}")
    else:
        test_result = {
            "name": "developmental_persistence_file",
            "status": "FAIL",
            "evidence": f"No persistence file found in expected locations",
            "critical": True
        }
        results["tests"].append(test_result)
        print(f"  ❌ No persistence file found")
    
    # Test 4: Daily check reset behavior analysis
    print("\n[Test 3.4] MVP16 Daily Check - Reset Behavior Analysis")
    
    daily_check_path = Path(__file__).parent.parent / "tools" / "mvp16_daily_check.py"
    if daily_check_path.exists():
        source = daily_check_path.read_text()
        
        reset_count = source.count("reset_developmental_manager()")
        print(f"  reset_developmental_manager() calls: {reset_count}")
        
        if reset_count > 0:
            # Find the functions that call reset
            lines = source.split('\n')
            reset_contexts = []
            current_func = "unknown"
            for line in lines:
                if 'def ' in line:
                    current_func = line.strip()
                if 'reset_developmental_manager()' in line:
                    reset_contexts.append(current_func)
            
            test_result = {
                "name": "daily_check_reset_analysis",
                "status": "FAIL",
                "evidence": f"reset_developmental_manager() called {reset_count} times in: {reset_contexts}",
                "critical": True,
                "reason": "Daily check resets state before reading, making observations meaningless"
            }
            results["tests"].append(test_result)
            print(f"  ❌ Daily check resets state in: {reset_contexts}")
        else:
            test_result = {
                "name": "daily_check_reset_analysis",
                "status": "PASS",
                "evidence": "No reset calls found"
            }
            results["tests"].append(test_result)
            print(f"  ✅ Daily check does not reset state")
    else:
        test_result = {
            "name": "daily_check_reset_analysis",
            "status": "FAIL",
            "evidence": "Daily check script not found"
        }
        results["tests"].append(test_result)
        print(f"  ❌ Daily check script not found")
    
    return results


def experiment_cross_session_state():
    """
    Test if state can be serialized and restored (simulating process restart).
    """
    print("\n" + "="*60)
    print("EXPERIMENT 4: Cross-Session State (Simulated Restart)")
    print("="*60)
    
    results = {
        "experiment": "cross_session_state",
        "tests": []
    }
    
    # Test 1: Self-model cross-session
    print("\n[Test 4.1] Self-Model - Cross-Session Capability")
    try:
        reset_self_model_manager()
        manager = get_self_model_manager()
        
        # Check if state can be serialized
        if hasattr(manager.state, 'model_dump'):
            serialized = manager.state.model_dump()
            test_result = {
                "name": "self_model_serialization",
                "status": "PASS",
                "evidence": "SelfModelState is serializable (Pydantic)"
            }
            results["tests"].append(test_result)
            print(f"  ✅ SelfModelState can be serialized")
        elif hasattr(manager.state, 'to_dict'):
            serialized = manager.state.to_dict()
            test_result = {
                "name": "self_model_serialization",
                "status": "PASS",
                "evidence": "SelfModelState has to_dict method"
            }
            results["tests"].append(test_result)
            print(f"  ✅ SelfModelState can be serialized")
        else:
            test_result = {
                "name": "self_model_serialization",
                "status": "FAIL",
                "evidence": "SelfModelState has no serialization method"
            }
            results["tests"].append(test_result)
            print(f"  ❌ SelfModelState cannot be serialized")
            
    except Exception as e:
        test_result = {
            "name": "self_model_serialization",
            "status": "FAIL",
            "evidence": f"Exception: {e}"
        }
        results["tests"].append(test_result)
        print(f"  ❌ Error: {e}")
    
    # Test 2: Developmental cross-session
    print("\n[Test 4.2] Developmental - Cross-Session Capability")
    reset_developmental_manager()
    manager = get_developmental_manager()
    
    try:
        if hasattr(manager.state, 'model_dump'):
            serialized = manager.state.model_dump()
            test_result = {
                "name": "developmental_serialization",
                "status": "PASS",
                "evidence": "DevelopmentalState is serializable (Pydantic)"
            }
            results["tests"].append(test_result)
            print(f"  ✅ DevelopmentalState can be serialized")
        elif hasattr(manager.state, 'to_dict'):
            serialized = manager.state.to_dict()
            test_result = {
                "name": "developmental_serialization",
                "status": "PASS",
                "evidence": "DevelopmentalState has to_dict method"
            }
            results["tests"].append(test_result)
            print(f"  ✅ DevelopmentalState can be serialized")
        else:
            test_result = {
                "name": "developmental_serialization",
                "status": "FAIL",
                "evidence": "DevelopmentalState has no serialization method"
            }
            results["tests"].append(test_result)
            print(f"  ❌ DevelopmentalState cannot be serialized")
            
    except Exception as e:
        test_result = {
            "name": "developmental_serialization",
            "status": "FAIL",
            "evidence": f"Exception: {e}"
        }
        results["tests"].append(test_result)
        print(f"  ❌ Error: {e}")
    
    return results


def run_all_experiments():
    """Run all persistence experiments."""
    print("="*60)
    print("PERSISTENCE & RESTART EXPERIMENTS")
    print("Mode: Verification-Only / Audit Mode")
    print("="*60)
    
    all_results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "verification-only",
        "experiments": []
    }
    
    # Run experiments
    all_results["experiments"].append(experiment_self_model_persistence())
    all_results["experiments"].append(experiment_drives_persistence())
    all_results["experiments"].append(experiment_developmental_persistence())
    all_results["experiments"].append(experiment_cross_session_state())
    
    return all_results


def main():
    results = run_all_experiments()
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    critical_failures = []
    
    for exp in results["experiments"]:
        for test in exp["tests"]:
            total_tests += 1
            if test["status"] == "PASS":
                passed_tests += 1
            else:
                failed_tests += 1
                if test.get("critical"):
                    critical_failures.append(f"{exp['experiment']}/{test['name']}")
    
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    
    if critical_failures:
        print(f"\n⚠️ CRITICAL FAILURES:")
        for cf in critical_failures:
            print(f"  - {cf}")
    
    # Save results
    output_path = Path(__file__).parent.parent / "artifacts" / "verification" / "persistence_restart_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to: {output_path}")
    
    return results


if __name__ == "__main__":
    main()
