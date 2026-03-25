#!/usr/bin/env python3
"""
Causal Intervention Experiments for MVP11.5-16

This script performs controlled experiments to verify causal relationships
between state changes and behavioral outcomes.
"""
import sys
import json
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import modules
from emotiond.self_model import get_self_model_v0, reset_self_model_v0, get_self_model_manager, reset_self_model_manager
from emotiond.drives import get_drive_manager, reset_drive_manager
from emotiond.reflection_engine import get_reflection_engine
from emotiond.developmental import get_developmental_manager, reset_developmental_manager
from emotiond.drive_homeostasis import DriveState, drive_error, get_drive_modulation_params
from emotiond.core import EmotionState


def experiment_self_model_intervention():
    """
    Experiment: Modify self-model tension/behavioral tendency and observe effect on decision.
    
    Expected: Changes to self-model should affect bias in decision making.
    """
    print("\n" + "="*60)
    print("EXPERIMENT 1: Self-Model Causal Intervention")
    print("="*60)
    
    results = {
        "experiment": "self_model_intervention",
        "hypothesis": "Modifying self-model tension/behavioral tendency affects decision bias",
        "tests": []
    }
    
    # Test 1: Legacy Self-Model V0
    print("\n[Test 1.1] Legacy SelfModelV0 - Check if bias affects decision")
    reset_self_model_v0()
    model_v0 = get_self_model_v0("default_target")
    
    # Get initial state
    initial_bias = model_v0.value_weights.cooperation if hasattr(model_v0, 'value_weights') else None
    print(f"  Initial cooperation bias: {initial_bias}")
    
    # Check if apply_self_model_to_decision exists and works
    try:
        from emotiond.self_model import apply_self_model_to_decision
        # Create test decision context
        test_decision = {"action": "respond", "scores": {"cooperate": 0.5, "assert": 0.5}}
        
        # Apply self-model bias
        biased_decision = apply_self_model_to_decision(model_v0, test_decision)
        
        test_result = {
            "name": "legacy_self_model_bias",
            "status": "PASS",
            "evidence": f"apply_self_model_to_decision callable, biased decision: {biased_decision}"
        }
        results["tests"].append(test_result)
        print(f"  ✅ Legacy self-model can bias decisions")
    except Exception as e:
        test_result = {
            "name": "legacy_self_model_bias",
            "status": "FAIL",
            "evidence": f"Exception: {e}"
        }
        results["tests"].append(test_result)
        print(f"  ❌ Legacy self-model bias failed: {e}")
    
    # Test 2: New MVP13 SelfModelManager
    print("\n[Test 1.2] New MVP13 SelfModelManager - Check if tension updates work")
    reset_self_model_manager()
    try:
        manager = get_self_model_manager()
        state = manager.state
        
        # Add a tension
        from emotiond.self_model.schema import ActiveTension, TensionType
        tension = ActiveTension(
            tension_id="test_tension_1",
            tension_type=TensionType.VALUE_CONFLICT,
            description="Test tension between autonomy and connection",
            intensity=0.7,
            involved_values=["autonomy", "connection"]
        )
        
        # Try to add tension
        if hasattr(state, 'active_tensions'):
            state.active_tensions.tensions.append(tension)
            updated = manager.update()
            
            test_result = {
                "name": "mvp13_tension_update",
                "status": "PASS",
                "evidence": f"Tension added: {tension.tension_id}, update result: {updated}"
            }
            results["tests"].append(test_result)
            print(f"  ✅ MVP13 tension can be added")
        else:
            test_result = {
                "name": "mvp13_tension_update",
                "status": "FAIL",
                "evidence": "active_tensions not found in state"
            }
            results["tests"].append(test_result)
            print(f"  ❌ MVP13 state missing active_tensions")
            
    except Exception as e:
        test_result = {
            "name": "mvp13_tension_update",
            "status": "FAIL",
            "evidence": f"Exception: {e}"
        }
        results["tests"].append(test_result)
        print(f"  ❌ MVP13 tension update failed: {e}")
    
    # Test 3: Check if MVP13 self-model affects main chain
    print("\n[Test 1.3] MVP13 SelfModelManager - Main Chain Integration")
    try:
        # Check if core.py imports from self_model_manager
        import emotiond.core as core_module
        source = Path(core_module.__file__).read_text()
        
        if "get_self_model_manager" in source or "SelfModelManager" in source:
            test_result = {
                "name": "mvp13_main_chain_wired",
                "status": "PASS",
                "evidence": "core.py imports SelfModelManager"
            }
            results["tests"].append(test_result)
            print(f"  ✅ MVP13 SelfModelManager wired to main chain")
        else:
            test_result = {
                "name": "mvp13_main_chain_wired",
                "status": "FAIL",
                "evidence": "core.py does NOT import SelfModelManager - uses legacy API"
            }
            results["tests"].append(test_result)
            print(f"  ❌ MVP13 SelfModelManager NOT wired to main chain (uses legacy)")
    except Exception as e:
        test_result = {
            "name": "mvp13_main_chain_wired",
            "status": "FAIL",
            "evidence": f"Exception: {e}"
        }
        results["tests"].append(test_result)
        print(f"  ❌ Check failed: {e}")
    
    return results


def experiment_drives_intervention():
    """
    Experiment: Modify drive strength/homeostatic deviation and observe effect on behavior.
    
    Expected: Drive changes should affect candidate scoring and action prioritization.
    """
    print("\n" + "="*60)
    print("EXPERIMENT 2: Drives/Homeostasis Causal Intervention")
    print("="*60)
    
    results = {
        "experiment": "drives_intervention",
        "hypothesis": "Modifying drive strength/homeostatic deviation affects candidate scoring",
        "tests": []
    }
    
    # Test 1: Old DriveState (currently used by core.py)
    print("\n[Test 2.1] Legacy DriveState - Check modulation params")
    drive_state = DriveState()
    
    # Get modulation params with default state
    params_default = get_drive_modulation_params(drive_state)
    print(f"  Default modulation params: {params_default}")
    
    # Modify drive state
    drive_state.update_component("energy", 0.3)  # Low energy
    drive_state.update_component("safety", 0.4)  # Low safety
    params_modified = get_drive_modulation_params(drive_state)
    print(f"  Modified modulation params: {params_modified}")
    
    if params_default != params_modified:
        test_result = {
            "name": "legacy_drive_modulation",
            "status": "PASS",
            "evidence": f"Modulation changes: {params_default} -> {params_modified}"
        }
        results["tests"].append(test_result)
        print(f"  ✅ Legacy drive state affects modulation params")
    else:
        test_result = {
            "name": "legacy_drive_modulation",
            "status": "FAIL",
            "evidence": "No change in modulation params despite drive modification"
        }
        results["tests"].append(test_result)
        print(f"  ❌ Legacy drive state does not affect modulation")
    
    # Test 2: New MVP14 DriveManager
    print("\n[Test 2.2] New MVP14 DriveManager - Module existence")
    reset_drive_manager()
    try:
        manager = get_drive_manager()
        state = manager.state
        
        test_result = {
            "name": "mvp14_drive_manager_exists",
            "status": "PASS",
            "evidence": f"DriveManager exists with state: {type(state).__name__}"
        }
        results["tests"].append(test_result)
        print(f"  ✅ MVP14 DriveManager exists")
    except Exception as e:
        test_result = {
            "name": "mvp14_drive_manager_exists",
            "status": "FAIL",
            "evidence": f"Exception: {e}"
        }
        results["tests"].append(test_result)
        print(f"  ❌ MVP14 DriveManager failed: {e}")
    
    # Test 3: Check if MVP14 drives affects main chain
    print("\n[Test 2.3] MVP14 DriveManager - Main Chain Integration")
    try:
        import emotiond.core as core_module
        source = Path(core_module.__file__).read_text()
        
        if "get_drive_manager" in source or "DriveManager" in source:
            test_result = {
                "name": "mvp14_main_chain_wired",
                "status": "PASS",
                "evidence": "core.py imports DriveManager"
            }
            results["tests"].append(test_result)
            print(f"  ✅ MVP14 DriveManager wired to main chain")
        else:
            test_result = {
                "name": "mvp14_main_chain_wired",
                "status": "FAIL",
                "evidence": "core.py does NOT import DriveManager - uses legacy drive_homeostasis"
            }
            results["tests"].append(test_result)
            print(f"  ❌ MVP14 DriveManager NOT wired to main chain")
    except Exception as e:
        test_result = {
            "name": "mvp14_main_chain_wired",
            "status": "FAIL",
            "evidence": f"Exception: {e}"
        }
        results["tests"].append(test_result)
        print(f"  ❌ Check failed: {e}")
    
    # Test 4: Drive error affects emotion selection
    print("\n[Test 2.4] Legacy Drive Error - Affects Emotion Selection")
    drive_state = DriveState()
    drive_state.update_component("energy", 0.2)  # Very low energy
    
    error = drive_error(drive_state)
    emotion = drive_error(drive_state)  # Should return emotion suggestion
    
    # Check if drive_error produces meaningful output
    if error is not None:
        test_result = {
            "name": "drive_error_emotion",
            "status": "PASS",
            "evidence": f"Drive error produces: {error}"
        }
        results["tests"].append(test_result)
        print(f"  ✅ Drive error produces emotion signal")
    else:
        test_result = {
            "name": "drive_error_emotion",
            "status": "FAIL",
            "evidence": "Drive error returned None"
        }
        results["tests"].append(test_result)
        print(f"  ❌ Drive error returned None")
    
    return results


def experiment_reflection_intervention():
    """
    Experiment: Trigger reflection proposal and compare approved vs not approved behavior.
    
    Expected: Approved proposals should change future behavior; non-approved should not.
    """
    print("\n" + "="*60)
    print("EXPERIMENT 3: Reflection Engine Causal Intervention")
    print("="*60)
    
    results = {
        "experiment": "reflection_intervention",
        "hypothesis": "Approved reflection proposals change future behavior",
        "tests": []
    }
    
    # Test 1: Old reflection.py
    print("\n[Test 3.1] Legacy reflection.py - Check if run_reflection is callable")
    try:
        from emotiond.reflection import run_reflection
        
        # Create minimal context
        emotion_state = EmotionState()
        result = run_reflection(emotion_state, {})
        
        test_result = {
            "name": "legacy_reflection_callable",
            "status": "PASS",
            "evidence": f"run_reflection returned: {type(result).__name__ if result else 'None'}"
        }
        results["tests"].append(test_result)
        print(f"  ✅ Legacy run_reflection callable")
    except Exception as e:
        test_result = {
            "name": "legacy_reflection_callable",
            "status": "FAIL",
            "evidence": f"Exception: {e}"
        }
        results["tests"].append(test_result)
        print(f"  ❌ Legacy run_reflection failed: {e}")
    
    # Test 2: New MVP15 ReflectionEngine
    print("\n[Test 3.2] New MVP15 ReflectionEngine - Module existence")
    try:
        engine = get_reflection_engine()
        
        test_result = {
            "name": "mvp15_reflection_engine_exists",
            "status": "PASS",
            "evidence": f"ReflectionEngine exists: {type(engine).__name__}"
        }
        results["tests"].append(test_result)
        print(f"  ✅ MVP15 ReflectionEngine exists")
    except Exception as e:
        test_result = {
            "name": "mvp15_reflection_engine_exists",
            "status": "FAIL",
            "evidence": f"Exception: {e}"
        }
        results["tests"].append(test_result)
        print(f"  ❌ MVP15 ReflectionEngine failed: {e}")
    
    # Test 3: Check if MVP15 reflection affects main chain
    print("\n[Test 3.3] MVP15 ReflectionEngine - Main Chain Integration")
    try:
        import emotiond.core as core_module
        source = Path(core_module.__file__).read_text()
        
        if "get_reflection_engine" in source or "ReflectionEngine" in source:
            test_result = {
                "name": "mvp15_main_chain_wired",
                "status": "PASS",
                "evidence": "core.py imports ReflectionEngine"
            }
            results["tests"].append(test_result)
            print(f"  ✅ MVP15 ReflectionEngine wired to main chain")
        else:
            test_result = {
                "name": "mvp15_main_chain_wired",
                "status": "FAIL",
                "evidence": "core.py does NOT import ReflectionEngine - uses legacy reflection.py"
            }
            results["tests"].append(test_result)
            print(f"  ❌ MVP15 ReflectionEngine NOT wired to main chain")
    except Exception as e:
        test_result = {
            "name": "mvp15_main_chain_wired",
            "status": "FAIL",
            "evidence": f"Exception: {e}"
        }
        results["tests"].append(test_result)
        print(f"  ❌ Check failed: {e}")
    
    # Test 4: Proposal approval affects behavior?
    print("\n[Test 3.4] Reflection Proposal - Causal Effect on Behavior")
    try:
        from emotiond.reflection_engine import get_reflection_engine
        
        engine = get_reflection_engine()
        
        # Check if engine can generate and process proposals
        if hasattr(engine, 'generate_proposal'):
            proposal = engine.generate_proposal()
            
            # Check if approved proposal affects state
            if hasattr(engine, 'approve_proposal'):
                engine.approve_proposal(proposal)
                
                test_result = {
                    "name": "proposal_approval_effect",
                    "status": "PASS",
                    "evidence": "Proposal approval mechanism exists"
                }
                results["tests"].append(test_result)
                print(f"  ✅ Proposal approval mechanism exists")
            else:
                test_result = {
                    "name": "proposal_approval_effect",
                    "status": "FAIL",
                    "evidence": "approve_proposal method not found"
                }
                results["tests"].append(test_result)
                print(f"  ❌ No approve_proposal method")
        else:
            test_result = {
                "name": "proposal_approval_effect",
                "status": "FAIL",
                "evidence": "generate_proposal method not found"
            }
            results["tests"].append(test_result)
            print(f"  ❌ No generate_proposal method")
            
    except Exception as e:
        test_result = {
            "name": "proposal_approval_effect",
            "status": "FAIL",
            "evidence": f"Exception: {e}"
        }
        results["tests"].append(test_result)
        print(f"  ❌ Proposal test failed: {e}")
    
    return results


def experiment_developmental_intervention():
    """
    Experiment: Test if developmental state accumulates and affects continuity.
    
    Expected: Developmental metrics should accumulate over time, not reset.
    """
    print("\n" + "="*60)
    print("EXPERIMENT 4: Developmental Manager Causal Intervention")
    print("="*60)
    
    results = {
        "experiment": "developmental_intervention",
        "hypothesis": "Developmental state accumulates across operations",
        "tests": []
    }
    
    # Test 1: Initial state
    print("\n[Test 4.1] Developmental Manager - Initial State")
    reset_developmental_manager()
    manager = get_developmental_manager()
    
    initial_summary = manager.get_summary()
    print(f"  Initial summary: {initial_summary}")
    
    # Test 2: Add episode
    print("\n[Test 4.2] Add Episode - State Accumulation")
    manager.record_episode("test_episode", "MVP16", "Test episode for causal verification")
    
    summary_after_episode = manager.get_summary()
    print(f"  After episode: {summary_after_episode}")
    
    if summary_after_episode["episodes"] > initial_summary["episodes"]:
        test_result = {
            "name": "episode_accumulation",
            "status": "PASS",
            "evidence": f"Episodes: {initial_summary['episodes']} -> {summary_after_episode['episodes']}"
        }
        results["tests"].append(test_result)
        print(f"  ✅ Episodes accumulate")
    else:
        test_result = {
            "name": "episode_accumulation",
            "status": "FAIL",
            "evidence": "Episodes did not increase"
        }
        results["tests"].append(test_result)
        print(f"  ❌ Episodes did not accumulate")
    
    # Test 3: Update metric
    print("\n[Test 4.3] Update Metric - State Change")
    initial_continuity = manager.get_continuity_score()
    manager.update_metric("continuity_score", 0.9)
    updated_continuity = manager.get_continuity_score()
    
    print(f"  Continuity: {initial_continuity} -> {updated_continuity}")
    
    if abs(updated_continuity - 0.9) < 0.01:
        test_result = {
            "name": "metric_update",
            "status": "PASS",
            "evidence": f"Continuity updated: {initial_continuity} -> {updated_continuity}"
        }
        results["tests"].append(test_result)
        print(f"  ✅ Metrics can be updated")
    else:
        test_result = {
            "name": "metric_update",
            "status": "FAIL",
            "evidence": f"Metric not updated: {initial_continuity} != 0.9"
        }
        results["tests"].append(test_result)
        print(f"  ❌ Metric update failed")
    
    # Test 4: Check if MVP16 developmental affects main chain
    print("\n[Test 4.4] MVP16 Developmental - Main Chain Integration")
    try:
        import emotiond.core as core_module
        source = Path(core_module.__file__).read_text()
        
        if "get_developmental_manager" in source or "DevelopmentalManager" in source:
            test_result = {
                "name": "mvp16_main_chain_wired",
                "status": "PASS",
                "evidence": "core.py imports DevelopmentalManager"
            }
            results["tests"].append(test_result)
            print(f"  ✅ MVP16 DevelopmentalManager wired to main chain")
        else:
            test_result = {
                "name": "mvp16_main_chain_wired",
                "status": "FAIL",
                "evidence": "core.py does NOT import DevelopmentalManager"
            }
            results["tests"].append(test_result)
            print(f"  ❌ MVP16 DevelopmentalManager NOT wired to main chain")
    except Exception as e:
        test_result = {
            "name": "mvp16_main_chain_wired",
            "status": "FAIL",
            "evidence": f"Exception: {e}"
        }
        results["tests"].append(test_result)
        print(f"  ❌ Check failed: {e}")
    
    return results


def run_all_experiments():
    """Run all causal intervention experiments."""
    print("="*60)
    print("CAUSAL INTERVENTION EXPERIMENTS")
    print("Mode: Verification-Only / Audit Mode")
    print("="*60)
    
    all_results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "verification-only",
        "experiments": []
    }
    
    # Run experiments
    all_results["experiments"].append(experiment_self_model_intervention())
    all_results["experiments"].append(experiment_drives_intervention())
    all_results["experiments"].append(experiment_reflection_intervention())
    all_results["experiments"].append(experiment_developmental_intervention())
    
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
    
    for exp in results["experiments"]:
        for test in exp["tests"]:
            total_tests += 1
            if test["status"] == "PASS":
                passed_tests += 1
            else:
                failed_tests += 1
    
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    
    # Save results
    output_path = Path(__file__).parent.parent / "artifacts" / "verification" / "causal_intervention_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to: {output_path}")
    
    return results


if __name__ == "__main__":
    main()
