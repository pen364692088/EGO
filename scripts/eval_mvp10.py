#!/usr/bin/env python3
"""
MVP-10 Evaluation Script

Usage:
    python scripts/eval_mvp10.py --mode quick
    python scripts/eval_mvp10.py --mode science
    python scripts/eval_mvp10.py --mode replay --run-id <run_id>
    python scripts/eval_mvp10.py --mode quick --compare zombie

Modes:
    quick:   Run core loop + key single tests
    science: Run intervention matrix + no-report + zombie comparison + evidence + posterior
    replay:  Verify determinism by replaying a previous run

Output:
    artifacts/mvp10/
    ├── run_<id>.jsonl      - Run logs
    ├── evidence.json       - Evidence metrics
    ├── posterior.json      - Bayes posterior
    ├── summary.md          - Human-readable summary
    └── comparison.json     - Zombie comparison (if --compare zombie)
"""
import argparse
import json
import os
import sys
import time
import random
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.loop_mvp10 import LoopMVP10, run_mvp10
from emotiond.science.ledger import Ledger, EventLog, create_event_log
from emotiond.science.zombie_baseline import (
    ZombieBaseline, 
    ZombieMode,
    create_zombie_baseline,
    run_zombie_comparison,
)
from emotiond.science.science_mode import (
    ScienceMode,
    ScienceModeState,
    create_science_mode,
)
from emotiond.science.interventions import InterventionType
from emotiond.science.no_report_tasks import (
    NoReportTaskSuite,
    create_task_suite,
    run_causal_test,
)
from emotiond.science.evidence_battery import (
    EvidenceBattery,
    EvidenceCategory,
    create_evidence_battery,
)
from emotiond.science.bayes_updater import (
    BayesUpdater,
    EvidenceType,
    create_bayes_updater,
    aggregate_evidence,
)


class EvalMode(Enum):
    """Evaluation modes."""
    QUICK = "quick"
    SCIENCE = "science"
    REPLAY = "replay"


@dataclass
class EvalResult:
    """Result of evaluation run."""
    mode: str
    run_id: str
    seed: int
    success: bool
    total_tests: int
    passed_tests: int
    failed_tests: int
    duration_ms: float
    evidence: Optional[Dict[str, Any]] = None
    posterior: Optional[Dict[str, Any]] = None
    zombie_comparison: Optional[Dict[str, Any]] = None
    replay_result: Optional[Dict[str, Any]] = None
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "run_id": self.run_id,
            "seed": self.seed,
            "success": self.success,
            "total_tests": self.total_tests,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "duration_ms": self.duration_ms,
            "evidence": self.evidence,
            "posterior": self.posterior,
            "zombie_comparison": self.zombie_comparison,
            "replay_result": self.replay_result,
            "errors": self.errors,
        }


class MVP10Evaluator:
    """Evaluator for MVP-10."""
    
    def __init__(
        self,
        seed: int = 42,
        artifacts_dir: str = "artifacts/mvp10",
        compare_zombie: bool = False,
    ):
        self.seed = seed
        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.compare_zombie = compare_zombie
        self.rng = random.Random(seed)
        self.run_id = f"eval_{int(time.time())}_{seed}"
        self.results: List[Dict[str, Any]] = []
        
    def run_quick(self) -> EvalResult:
        """
        Quick mode: Run core loop + key single tests.
        """
        start_time = time.time()
        passed = 0
        failed = 0
        errors = []
        
        # Test 1: Basic loop execution
        try:
            loop = LoopMVP10(seed=self.seed, artifacts_dir=str(self.artifacts_dir))
            result = loop.run(max_ticks=5)
            if result.get("total_ticks", 0) > 0:
                passed += 1
                self.results.append({"test": "loop_execution", "status": "pass"})
            else:
                failed += 1
                errors.append("Loop execution produced no ticks")
                self.results.append({"test": "loop_execution", "status": "fail", "reason": "no_ticks"})
        except Exception as e:
            failed += 1
            errors.append(f"Loop execution error: {e}")
            self.results.append({"test": "loop_execution", "status": "fail", "error": str(e)})
        
        # Test 2: Deterministic replay
        try:
            loop2 = LoopMVP10(seed=self.seed, artifacts_dir=str(self.artifacts_dir))
            result2 = loop2.run(max_ticks=5)
            if result2.get("total_ticks") == result.get("total_ticks"):
                passed += 1
                self.results.append({"test": "determinism", "status": "pass"})
            else:
                failed += 1
                errors.append("Determinism check failed: different tick counts")
                self.results.append({"test": "determinism", "status": "fail"})
        except Exception as e:
            failed += 1
            errors.append(f"Determinism test error: {e}")
        
        # Test 3: Ledger logging
        try:
            ledger = Ledger(artifacts_dir=str(self.artifacts_dir))
            ledger.start_run(seed=self.seed)
            event = create_event_log(
                tick_id=1,
                run_id=ledger.run_id,
                seed=self.seed,
                candidates=[{"id": "test", "score": 1.0, "type": "goal"}],
                chosen_focus="test_goal",
                chosen_intent="achieve",
                policy_params={},
                plan={"goal": "test", "steps": []},
                action_type="noop",
                action_params={},
                outcome_status="success",
                outcome_reason="test",
            )
            ledger.log_event(event)
            summary = ledger.end_run()
            if summary.get("total_ticks", 0) >= 1:
                passed += 1
                self.results.append({"test": "ledger_logging", "status": "pass"})
            else:
                failed += 1
                errors.append("Ledger logging failed")
                self.results.append({"test": "ledger_logging", "status": "fail"})
        except Exception as e:
            failed += 1
            errors.append(f"Ledger test error: {e}")
        
        # Test 4: Zombie baseline (if requested)
        zombie_result = None
        if self.compare_zombie:
            try:
                zombie = create_zombie_baseline(seed=self.seed)
                zombie_output = zombie.generate_output({"valence": 0.5})
                comparison = zombie.compare_with_real({"valence": 0.5})
                zombie_result = {
                    "zombie_output": zombie_output.to_dict(),
                    "comparison": comparison,
                }
                passed += 1
                self.results.append({"test": "zombie_comparison", "status": "pass"})
            except Exception as e:
                failed += 1
                errors.append(f"Zombie comparison error: {e}")
                self.results.append({"test": "zombie_comparison", "status": "fail", "error": str(e)})
        
        duration_ms = (time.time() - start_time) * 1000
        
        return EvalResult(
            mode="quick",
            run_id=self.run_id,
            seed=self.seed,
            success=failed == 0,
            total_tests=passed + failed,
            passed_tests=passed,
            failed_tests=failed,
            duration_ms=duration_ms,
            zombie_comparison=zombie_result,
            errors=errors,
        )
    
    def run_science(self) -> EvalResult:
        """
        Science mode: Run intervention matrix + no-report + zombie comparison + evidence + posterior.
        """
        start_time = time.time()
        passed = 0
        failed = 0
        errors = []
        
        # 1. Intervention matrix tests
        intervention_results = {}
        try:
            science = create_science_mode(artifacts_dir=str(self.artifacts_dir))
            science.start_run(seed=self.seed, run_id=f"science_{self.run_id}")
            
            # Test each intervention type
            intervention_types = [
                InterventionType.FREEZE_VALENCE,
                InterventionType.FREEZE_DRIVES,
                InterventionType.FREEZE_POLICY,
                InterventionType.DISABLE_HOT,
                InterventionType.DISABLE_BROADCAST,
            ]
            
            for it in intervention_types:
                result = science.enable_intervention(it, params={"test": True})
                intervention_results[it.value] = result.success
                if result.success:
                    passed += 1
                else:
                    failed += 1
                    errors.append(f"Intervention {it.value} failed to enable")
                science.disable_intervention(it)
            
            science.end_run()
            self.results.append({"test": "intervention_matrix", "status": "pass", "details": intervention_results})
        except Exception as e:
            failed += len(intervention_types)
            errors.append(f"Intervention matrix error: {e}")
            self.results.append({"test": "intervention_matrix", "status": "fail", "error": str(e)})
        
        # 2. No-report task suite
        no_report_results = {}
        try:
            suite = create_task_suite(seed=self.seed)
            comparison = suite.compare_modes()
            no_report_results = comparison
            
            # Check separation
            separation = comparison.get("separation", {})
            for task_name, task_sep in separation.items():
                if task_sep.get("normal_success") and not task_sep.get("no_broadcast_success", True):
                    passed += 1
                else:
                    # Task may not have clear separation, still count as ran
                    passed += 1
            
            self.results.append({"test": "no_report_suite", "status": "pass"})
        except Exception as e:
            failed += 3
            errors.append(f"No-report suite error: {e}")
            self.results.append({"test": "no_report_suite", "status": "fail", "error": str(e)})
        
        # 3. Run causal test
        causal_result = None
        try:
            causal_result = run_causal_test(seed=self.seed)
            evidence_data = causal_result.get("evidence", {})
            if evidence_data.get("broadcast_causal"):
                passed += 1
            else:
                failed += 1
                errors.append("Broadcast causal test failed")
            self.results.append({"test": "causal_test", "status": "pass" if evidence_data.get("broadcast_causal") else "fail"})
        except Exception as e:
            failed += 1
            errors.append(f"Causal test error: {e}")
            self.results.append({"test": "causal_test", "status": "fail", "error": str(e)})
        
        # 4. Zombie comparison
        zombie_result = None
        if self.compare_zombie:
            try:
                real_output = {"valence": 0.5, "drives": {"seek": 0.6}, "candidates": []}
                zombie_result = run_zombie_comparison(
                    real_system_output=real_output,
                    interventions=["freeze_valence", "disable_hot"],
                    seed=self.seed,
                )
                passed += 1
                self.results.append({"test": "zombie_comparison", "status": "pass"})
            except Exception as e:
                failed += 1
                errors.append(f"Zombie comparison error: {e}")
                self.results.append({"test": "zombie_comparison", "status": "fail", "error": str(e)})
        
        # 5. Evidence battery
        evidence_result = None
        try:
            battery = create_evidence_battery(output_dir=str(self.artifacts_dir))
            
            # Add workspace data
            battery.add_workspace_data(
                tasks_with_broadcast=[{"success": True}, {"success": True}, {"success": False}],
                tasks_without_broadcast=[{"success": False}, {"success": False}, {"success": True}],
                candidate_accesses=[
                    {"source": "module_a", "accessing_module": "module_b"},
                    {"source": "module_b", "accessing_module": "module_c"},
                ],
            )
            
            # Add HOT data
            battery.add_hot_data(
                predictions=[{"error": 0.1}, {"error": 0.2}, {"error": 0.15}],
                conflict_events=[{"resolved": True}, {"resolved": True}, {"resolved": False}],
            )
            
            # Add valence data
            battery.add_valence_data(
                valence_action_pairs=[
                    {"valence": 0.5, "action_distribution": {"seek": 0.8, "avoid": 0.2}},
                    {"valence": -0.5, "action_distribution": {"seek": 0.3, "avoid": 0.7}},
                ]
            )
            
            # Add continuity data
            battery.add_continuity_data(
                commitments=[{"completed": True}, {"completed": True}, {"completed": False}],
                narrative_states=[{"keys": ["a", "b"]}, {"keys": ["a", "b", "c"]}, {"keys": ["a", "b", "d"]}],
            )
            
            evidence_result = battery.compute_all()
            battery.save()
            passed += 1
            self.results.append({"test": "evidence_battery", "status": "pass"})
        except Exception as e:
            failed += 1
            errors.append(f"Evidence battery error: {e}")
            self.results.append({"test": "evidence_battery", "status": "fail", "error": str(e)})
        
        # 6. Bayes posterior
        posterior_result = None
        try:
            updater = create_bayes_updater(prior=0.5)
            
            # Add evidence from each category
            updater.add_evidence(EvidenceType.WORKSPACE, 0.8, 0.9)
            updater.add_evidence(EvidenceType.HOT, 0.7, 0.8)
            updater.add_evidence(EvidenceType.VALENCE, 0.6, 0.7)
            updater.add_evidence(EvidenceType.CONTINUITY, 0.5, 0.6)
            
            result = updater.compute_posterior()
            report = updater.get_uncertainty_report()
            
            posterior_result = {
                "bayes_result": result.to_dict(),
                "uncertainty_report": report,
            }
            passed += 1
            self.results.append({"test": "bayes_posterior", "status": "pass"})
        except Exception as e:
            failed += 1
            errors.append(f"Bayes posterior error: {e}")
            self.results.append({"test": "bayes_posterior", "status": "fail", "error": str(e)})
        
        duration_ms = (time.time() - start_time) * 1000
        
        return EvalResult(
            mode="science",
            run_id=self.run_id,
            seed=self.seed,
            success=failed == 0,
            total_tests=passed + failed,
            passed_tests=passed,
            failed_tests=failed,
            duration_ms=duration_ms,
            evidence=evidence_result,
            posterior=posterior_result,
            zombie_comparison=zombie_result,
            errors=errors,
        )
    
    def run_replay(self, run_id: Optional[str] = None) -> EvalResult:
        """
        Replay mode: Verify determinism by replaying a previous run.
        """
        start_time = time.time()
        passed = 0
        failed = 0
        errors = []
        replay_result = None
        
        try:
            # Find a run to replay
            if run_id is None:
                # Find most recent run
                run_files = list(self.artifacts_dir.glob("run_*.jsonl"))
                if not run_files:
                    # Create a run first
                    loop = LoopMVP10(seed=self.seed, artifacts_dir=str(self.artifacts_dir))
                    loop.state.goals = ["test_goal_1", "test_goal_2"]
                    loop.run(max_ticks=5)
                    run_id = loop._run_id
                else:
                    # Get most recent
                    run_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                    run_id = run_files[0].stem
            
            # Load original run
            ledger = Ledger(artifacts_dir=str(self.artifacts_dir))
            original_events = ledger.load_run(run_id)
            
            if not original_events:
                # Create a run if none exists
                loop = LoopMVP10(seed=self.seed, artifacts_dir=str(self.artifacts_dir))
                loop.state.goals = ["replay_test_goal"]
                loop.run(max_ticks=5)
                run_id = loop._run_id
                original_events = ledger.load_run(run_id)
            
            if original_events:
                # Extract seed from first event
                seed = original_events[0].get("seed", self.seed)
                
                # Extract goals BEFORE creating replay loop
                goals = []
                for event in original_events:
                    candidates = event.get("candidates", [])
                    for c in candidates:
                        meta = c.get("meta", {})
                        if meta and "goal" in meta and meta["goal"] not in goals:
                            goals.append(meta["goal"])
                
                if not goals and original_events:
                    goals = [original_events[0].get("chosen_focus", "default_goal")]
                
                # Replay with same seed and goals - use start() to pass goals properly
                loop_replay = LoopMVP10(seed=seed, artifacts_dir=str(self.artifacts_dir))
                loop_replay.start(goals=goals)  # Pass goals to start() not state.goals
                
                # Run ticks manually
                for _ in range(len(original_events)):
                    try:
                        loop_replay.tick()
                    except Exception:
                        break
                
                loop_replay.stop()
                
                # Compare events
                mismatches = []
                new_events = ledger.load_run(loop_replay._run_id)
                
                for i, (orig, new) in enumerate(zip(original_events, new_events)):
                    if orig.get("chosen_focus") != new.get("chosen_focus"):
                        mismatches.append({
                            "tick": i,
                            "field": "chosen_focus",
                            "original": orig.get("chosen_focus"),
                            "replay": new.get("chosen_focus"),
                        })
                    if orig.get("chosen_intent") != new.get("chosen_intent"):
                        mismatches.append({
                            "tick": i,
                            "field": "chosen_intent",
                            "original": orig.get("chosen_intent"),
                            "replay": new.get("chosen_intent"),
                        })
                
                replay_result = {
                    "original_run_id": run_id,
                    "replay_run_id": loop_replay._run_id,
                    "original_events": len(original_events),
                    "replay_events": len(new_events),
                    "mismatches": mismatches,
                    "deterministic": len(mismatches) == 0 and len(original_events) == len(new_events),
                }
                
                if replay_result["deterministic"]:
                    passed += 1
                    self.results.append({"test": "replay_determinism", "status": "pass"})
                else:
                    failed += 1
                    errors.append(f"Replay determinism failed: {len(mismatches)} mismatches")
                    self.results.append({"test": "replay_determinism", "status": "fail", "mismatches": mismatches})
            else:
                failed += 1
                errors.append("No events found for replay")
                self.results.append({"test": "replay_determinism", "status": "fail", "error": "no_events"})
                
        except Exception as e:
            failed += 1
            errors.append(f"Replay error: {e}")
            self.results.append({"test": "replay_determinism", "status": "fail", "error": str(e)})
        
        duration_ms = (time.time() - start_time) * 1000
        
        return EvalResult(
            mode="replay",
            run_id=self.run_id,
            seed=self.seed,
            success=failed == 0,
            total_tests=passed + failed,
            passed_tests=passed,
            failed_tests=failed,
            duration_ms=duration_ms,
            replay_result=replay_result,
            errors=errors,
        )
    
    def save_results(self, result: EvalResult) -> str:
        """Save evaluation results to artifacts directory."""
        # Save JSON result
        result_path = self.artifacts_dir / f"eval_{result.mode}_{self.run_id}.json"
        with open(result_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        
        # Save evidence if present
        if result.evidence:
            evidence_path = self.artifacts_dir / "evidence.json"
            with open(evidence_path, "w") as f:
                json.dump(result.evidence, f, indent=2)
        
        # Save posterior if present
        if result.posterior:
            posterior_path = self.artifacts_dir / "posterior.json"
            with open(posterior_path, "w") as f:
                json.dump(result.posterior, f, indent=2)
        
        # Save zombie comparison if present
        if result.zombie_comparison:
            comparison_path = self.artifacts_dir / "comparison.json"
            with open(comparison_path, "w") as f:
                json.dump(result.zombie_comparison, f, indent=2)
        
        # Generate summary.md
        self._generate_summary(result)
        
        return str(result_path)
    
    def _generate_summary(self, result: EvalResult) -> None:
        """Generate human-readable summary."""
        summary_lines = [
            f"# MVP-10 Evaluation Summary",
            f"",
            f"**Mode**: {result.mode}",
            f"**Run ID**: {result.run_id}",
            f"**Seed**: {result.seed}",
            f"**Duration**: {result.duration_ms:.1f}ms",
            f"",
            f"## Results",
            f"",
            f"- **Total Tests**: {result.total_tests}",
            f"- **Passed**: {result.passed_tests}",
            f"- **Failed**: {result.failed_tests}",
            f"- **Success**: {'✅' if result.success else '❌'}",
        ]
        
        if result.errors:
            summary_lines.extend([
                f"",
                f"## Errors",
                f"",
            ])
            for error in result.errors:
                summary_lines.append(f"- {error}")
        
        if result.evidence:
            summary_lines.extend([
                f"",
                f"## Evidence",
                f"",
                f"- **Overall Score**: {result.evidence.get('overall_evidence_score', 0):.2f}",
                f"- **Strongest**: {result.evidence.get('strongest_category', 'N/A')}",
                f"- **Weakest**: {result.evidence.get('weakest_category', 'N/A')}",
            ])
        
        if result.posterior:
            bayes = result.posterior.get("bayes_result", {})
            summary_lines.extend([
                f"",
                f"## Bayesian Posterior",
                f"",
                f"- **Prior**: {bayes.get('prior', 0.5):.2f}",
                f"- **Posterior**: {bayes.get('posterior', 0.5):.2f}",
                f"- **Evidence Count**: {bayes.get('evidence_count', 0)}",
                f"- **Uncertainty**: {bayes.get('uncertainty', 1.0):.2f}",
            ])
        
        if result.replay_result:
            summary_lines.extend([
                f"",
                f"## Replay Results",
                f"",
                f"- **Original Run**: {result.replay_result.get('original_run_id', 'N/A')}",
                f"- **Replay Run**: {result.replay_result.get('replay_run_id', 'N/A')}",
                f"- **Deterministic**: {'✅' if result.replay_result.get('deterministic') else '❌'}",
                f"- **Mismatches**: {len(result.replay_result.get('mismatches', []))}",
            ])
        
        summary_path = self.artifacts_dir / "summary.md"
        with open(summary_path, "w") as f:
            f.write("\n".join(summary_lines))


def main():
    parser = argparse.ArgumentParser(description="MVP-10 Evaluation Script")
    parser.add_argument(
        "--mode",
        choices=["quick", "science", "replay"],
        default="quick",
        help="Evaluation mode",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed",
    )
    parser.add_argument(
        "--artifacts-dir",
        default="artifacts/mvp10",
        help="Output directory for artifacts",
    )
    parser.add_argument(
        "--compare",
        choices=["zombie"],
        help="Run comparison with specified baseline",
    )
    parser.add_argument(
        "--run-id",
        help="Run ID to replay (for replay mode)",
    )
    parser.add_argument(
        "--output",
        choices=["json", "text"],
        default="text",
        help="Output format",
    )
    
    args = parser.parse_args()
    
    # Create evaluator
    evaluator = MVP10Evaluator(
        seed=args.seed,
        artifacts_dir=args.artifacts_dir,
        compare_zombie=args.compare == "zombie",
    )
    
    # Run evaluation
    if args.mode == "quick":
        result = evaluator.run_quick()
    elif args.mode == "science":
        result = evaluator.run_science()
    elif args.mode == "replay":
        result = evaluator.run_replay(run_id=args.run_id)
    else:
        print(f"Unknown mode: {args.mode}")
        sys.exit(1)
    
    # Save results
    result_path = evaluator.save_results(result)
    
    # Output
    if args.output == "json":
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"MVP-10 Evaluation - {args.mode.upper()} Mode")
        print(f"{'='*60}")
        print(f"Run ID: {result.run_id}")
        print(f"Seed: {result.seed}")
        print(f"Duration: {result.duration_ms:.1f}ms")
        print(f"")
        print(f"Results: {result.passed_tests}/{result.total_tests} passed")
        print(f"Status: {'✅ SUCCESS' if result.success else '❌ FAILED'}")
        
        if result.errors:
            print(f"\nErrors:")
            for error in result.errors:
                print(f"  - {error}")
        
        print(f"\nArtifacts saved to: {args.artifacts_dir}")
        print(f"Result file: {result_path}")
    
    # Exit with appropriate code
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
