#!/usr/bin/env python3
"""Auto-Tune v0.4 for OpenEmotion MVP-7.0 with KnobRegistry validation."""

import os
import sys
import json
import yaml
import random
import asyncio
import time
import statistics
import copy
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.eval_suite_v2_3 import EvalSuiteV2_3, EvalResult, result_to_dict
from emotiond.config import set_auto_tune_params, clear_auto_tune_params, get_auto_tune_params_snapshot
from emotiond.knob_registry import get_knob_registry, validate_parameter_change

DEFAULT_TUNABLE_PARAMS = {
    "precision_temperature": {"default": 0.5, "min": 0.1, "max": 1.0, "category": "precision"},
    "precision_uncertainty_threshold": {"default": 0.3, "min": 0.1, "max": 0.8, "category": "precision"},
    "w_external_default": {"default": 0.6, "min": 0.2, "max": 0.9, "category": "precision"},
    "w_internal_default": {"default": 0.5, "min": 0.2, "max": 0.8, "category": "precision"},
    "w_memory_default": {"default": 0.4, "min": 0.1, "max": 0.7, "category": "precision"},
    "w_action_default": {"default": 0.5, "min": 0.2, "max": 0.8, "category": "precision"},
    "w_explore_default": {"default": 0.3, "min": 0.1, "max": 0.6, "category": "precision"},
    "energy_recovery_rate": {"default": 0.001, "min": 0.0001, "max": 0.01, "category": "allostasis"},
    "energy_depletion_conflict": {"default": 0.05, "min": 0.01, "max": 0.15, "category": "allostasis"},
    "energy_depletion_uncertainty": {"default": 0.03, "min": 0.01, "max": 0.1, "category": "allostasis"},
    "low_energy_explore_dampening": {"default": 0.5, "min": 0.1, "max": 0.9, "category": "allostasis"},
    "low_energy_learning_dampening": {"default": 0.7, "min": 0.3, "max": 0.95, "category": "allostasis"},
    "curiosity_info_gain_threshold": {"default": 0.2, "min": 0.05, "max": 0.5, "category": "intrinsic"},
    "boredom_prediction_error_threshold": {"default": 0.05, "min": 0.01, "max": 0.2, "category": "intrinsic"},
    "confusion_error_threshold": {"default": 0.3, "min": 0.15, "max": 0.6, "category": "intrinsic"},
    "boredom_time_window": {"default": 300, "min": 60, "max": 900, "category": "intrinsic"},
    "self_model_update_rate": {"default": 0.1, "min": 0.01, "max": 0.3, "category": "self_model"},
    "identity_stability_threshold": {"default": 0.8, "min": 0.5, "max": 0.95, "category": "self_model"},
    "value_conflict_resolution_rate": {"default": 0.05, "min": 0.01, "max": 0.2, "category": "self_model"},
    "clarification_trigger_threshold": {"default": 0.4, "min": 0.2, "max": 0.7, "category": "meta_cognition"},
    "reflection_trigger_threshold": {"default": 0.5, "min": 0.3, "max": 0.8, "category": "meta_cognition"},
    "shrinkage_k": {"default": 10.0, "min": 1.0, "max": 50.0, "category": "target_residual"},
    "residual_learning_rate": {"default": 0.1, "min": 0.01, "max": 0.5, "category": "target_residual"},
    "residual_evidence_increment": {"default": 0.1, "min": 0.01, "max": 0.3, "category": "target_residual"},
    "residual_update_gain": {"default": 1.0, "min": 0.5, "max": 3.0, "category": "target_residual"},
    "relationship_damage_threshold": {"default": 0.3, "min": 0.1, "max": 0.8, "category": "thresholds"},
    "recovery_priority_threshold": {"default": 0.5, "min": 0.2, "max": 0.9, "category": "thresholds"},
    "risk_tolerance_threshold": {"default": 0.4, "min": 0.1, "max": 0.7, "category": "thresholds"},
    "uncertainty_threshold": {"default": 0.3, "min": 0.1, "max": 0.6, "category": "thresholds"},
    "tension_threshold": {"default": 0.5, "min": 0.2, "max": 0.8, "category": "thresholds"},
    "fatigue_threshold": {"default": 0.6, "min": 0.3, "max": 0.9, "category": "thresholds"},
    "social_drive_threshold": {"default": 0.4, "min": 0.1, "max": 0.7, "category": "thresholds"},
    "safety_drive_threshold": {"default": 0.8, "min": 0.5, "max": 0.95, "category": "thresholds"},
    "relationship_weight": {"default": 0.4, "min": 0.1, "max": 0.8, "category": "weights"},
    "recovery_weight": {"default": 0.5, "min": 0.2, "max": 0.9, "category": "weights"},
    "risk_weight": {"default": 0.3, "min": 0.1, "max": 0.6, "category": "weights"},
    "efficiency_weight": {"default": 0.2, "min": 0.05, "max": 0.5, "category": "weights"},
    "social_weight": {"default": 0.3, "min": 0.1, "max": 0.6, "category": "weights"},
    "safety_weight": {"default": 0.7, "min": 0.4, "max": 0.95, "category": "weights"},
    "strategy_temperature": {"default": 0.5, "min": 0.1, "max": 2.0, "category": "strategy"},
    "rollout_branching_factor": {"default": 3, "min": 2, "max": 5, "category": "strategy"},
    "clarification_trigger_threshold": {"default": 0.4, "min": 0.2, "max": 0.7, "category": "strategy"},
    "escalation_threshold": {"default": 0.6, "min": 0.3, "max": 0.9, "category": "strategy"},
    "timeout_multiplier": {"default": 1.5, "min": 1.0, "max": 3.0, "category": "strategy"},
    "episode_similarity_threshold": {"default": 0.7, "min": 0.3, "max": 0.9, "category": "retrieval"},
    "memory_retrieval_limit": {"default": 5, "min": 1, "max": 10, "category": "retrieval"},
    "context_injection_weight": {"default": 0.5, "min": 0.1, "max": 0.8, "category": "retrieval"},
    "episode_decay_rate": {"default": 0.1, "min": 0.01, "max": 0.3, "category": "retrieval"},
}

@dataclass
class Fitness:
    """Lexicographic fitness: passed_scenarios > avg_score > tie_breaker."""
    passed_scenarios: int
    avg_score: float
    tie_breaker: float
    
    @staticmethod
    def from_result(result: EvalResult) -> 'Fitness':
        return Fitness(
            passed_scenarios=result.passed_scenarios,
            avg_score=result.avg_score,
            tie_breaker=result.tie_breaker
        )
    
    def dominates(self, other: 'Fitness') -> bool:
        """Lexicographic domination."""
        if self.passed_scenarios != other.passed_scenarios:
            return self.passed_scenarios > other.passed_scenarios
        if abs(self.avg_score - other.avg_score) > 1e-9:
            return self.avg_score > other.avg_score
        return self.tie_breaker > other.tie_breaker

@dataclass
class CandidateResult:
    """Result for a single candidate configuration."""
    params: Dict[str, Any]
    param_hash: str
    fitness: Fitness
    eval_result: EvalResult
    validation_status: str = "VALID"  # VALID, REJECTED, OVERFIT
    validation_reason: Optional[str] = None
    
@dataclass
class TuneResult:
    """Result of tuning session."""
    baseline_fitness: Fitness
    baseline_result: EvalResult
    candidates: List[CandidateResult]
    best_candidate: Optional[CandidateResult] = None
    overall_improvement: bool = False
    lexicographic_improvement: Optional[str] = None
    validation_summary: Dict[str, Any] = field(default_factory=dict)
    rejection_reasons: Counter = field(default_factory=Counter)
    
class AutoTuneEngine:
    """Auto-tuning engine with KnobRegistry validation."""
    
    def __init__(self, scenarios_dir: Path, output_dir: Path, seed: int = 42):
        self.scenarios_dir = scenarios_dir
        self.output_dir = output_dir
        self.seed = seed
        self.rng = random.Random(seed)
        
        # Initialize KnobRegistry
        self.knob_registry = get_knob_registry()
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def generate_candidate(self, baseline_params: Dict[str, Any], 
                         generation: int = 0,
                         adaptive_factor: float = 0.2) -> Dict[str, Any]:
        """Generate a single candidate parameter set."""
        candidate = copy.deepcopy(baseline_params)
        
        # Adaptive mutation based on generation
        mutation_rate = 0.3 / (1 + generation * 0.1)
        mutation_strength = adaptive_factor * (1 + generation * 0.05)
        
        for param_name, param_config in DEFAULT_TUNABLE_PARAMS.items():
            if self.rng.random() < mutation_rate:
                min_val = param_config["min"]
                max_val = param_config["max"]
                default_val = param_config["default"]
                
                current_val = candidate.get(param_name, default_val)
                
                # Validate parameter change with KnobRegistry
                new_val = self._mutate_parameter(current_val, min_val, max_val, mutation_strength)
                is_allowed, reason = self.knob_registry.validate_parameter_change(param_name, new_val)
                
                if is_allowed:
                    candidate[param_name] = new_val
                else:
                    # Log rejection for debugging
                    self.knob_registry._audit_log(
                        "MUTATION_REJECT", param_name, new_val, reason, 
                        datetime.utcnow().isoformat()
                    )
        
        return candidate
    
    def _mutate_parameter(self, current_val: Any, min_val: float, max_val: float, 
                         strength: float) -> Any:
        """Mutate a single parameter."""
        if isinstance(current_val, int):
            # Integer mutation
            delta = int(self.rng.gauss(0, strength * (max_val - min_val)))
            new_val = max(int(min_val), min(int(max_val), current_val + delta))
            return new_val
        else:
            # Float mutation
            delta = self.rng.gauss(0, strength * (max_val - min_val))
            new_val = max(min_val, min(max_val, current_val + delta))
            return new_val
    
    def compute_param_hash(self, params: Dict[str, Any]) -> str:
        """Compute hash of candidate parameters for traceability."""
        params_str = json.dumps(params, sort_keys=True)
        return hashlib.sha256(params_str.encode()).hexdigest()[:16]
    
    async def evaluate_candidate(self, params: Dict[str, Any], 
                               scenarios: Optional[List[Path]] = None,
                               scenario_set: Optional[str] = None) -> EvalResult:
        """Evaluate a single candidate configuration."""
        # Apply parameters
        set_auto_tune_params(params)
        
        try:
            # Run evaluation
            eval_suite = EvalSuiteV2_3()
            
            if scenario_set:
                result = await eval_suite.run_scenario_set(scenario_set)
            elif scenarios:
                result = await eval_suite.run_scenarios(scenarios)
            else:
                result = await eval_suite.run_all()
            
            return result
            
        finally:
            # Always clear parameters
            clear_auto_tune_params()
    
    def validate_candidate_against_holdout(self, candidate: CandidateResult,
                                         holdout_result: EvalResult,
                                         tune_result: EvalResult) -> Tuple[str, Optional[str]]:
        """Validate candidate against holdout set for overfitting detection."""
        # Check for overfitting: tune improves but holdout degrades
        tune_score = tune_result.avg_score
        holdout_score = holdout_result.avg_score
        
        # Get baseline comparison
        baseline_tune_score = self.baseline_tune_score if hasattr(self, 'baseline_tune_score') else tune_result.avg_score
        baseline_holdout_score = self.baseline_holdout_score if hasattr(self, 'baseline_holdout_score') else holdout_result.avg_score
        
        tune_improvement = tune_score - baseline_tune_score
        holdout_degradation = baseline_holdout_score - holdout_score
        
        # Overfitting detection thresholds
        if tune_improvement > 0.05 and holdout_degradation > 0.03:
            return "OVERFIT", f"Tune +{tune_improvement:.3f} but Holdout -{holdout_degradation:.3f}"
        
        if holdout_degradation > 0.1:
            return "REJECTED", f"Holdout degradation too high: -{holdout_degradation:.3f}"
        
        return "VALID", None
    
    async def tune(self, baseline_params: Dict[str, Any],
                  candidate_params_list: Optional[List[Dict[str, Any]]] = None,
                  scenarios: Optional[List[Path]] = None,
                  generate_candidates: bool = True,
                  candidate_count: int = 30,
                  skip_sentinel: bool = False,
                  scenario_set: Optional[str] = "tune_set") -> TuneResult:
        """Run full tuning session with validation."""
        print("Starting Auto-Tune v0.4 with KnobRegistry validation...")
        
        # Step 1: Run baseline on tune set
        print("Running baseline evaluation on tune set...")
        baseline_result = await self.evaluate_candidate(baseline_params, scenarios, scenario_set)
        baseline_fitness = Fitness.from_result(baseline_result)
        
        # Store baseline scores for overfitting detection
        self.baseline_tune_score = baseline_result.avg_score
        
        # Step 2: Run baseline on holdout set for comparison
        print("Running baseline evaluation on holdout set...")
        holdout_result = await self.evaluate_candidate(baseline_params, scenario_set="holdout_set")
        self.baseline_holdout_score = holdout_result.avg_score
        
        print(f"Baseline - Tune: {baseline_fitness.passed_scenarios} passed, score: {baseline_fitness.avg_score:.3f}")
        print(f"Baseline - Holdout: {holdout_result.passed_scenarios} passed, score: {holdout_result.avg_score:.3f}")
        
        # Step 3: Generate or use provided candidates
        if generate_candidates:
            print(f"Generating {candidate_count} candidates...")
            candidates_params = []
            for i in range(candidate_count):
                candidate = self.generate_candidate(baseline_params, generation=i)
                candidates_params.append(candidate)
        else:
            candidates_params = candidate_params_list
        
        # Step 4: Evaluate all candidates
        candidates = []
        for i, params in enumerate(candidates_params):
            print(f"Evaluating candidate {i+1}/{len(candidates_params)}...")
            
            # Pre-validate with KnobRegistry
            all_valid = True
            validation_failures = []
            for param_name, param_value in params.items():
                is_allowed, reason = validate_parameter_change(param_name, param_value)
                if not is_allowed:
                    all_valid = False
                    validation_failures.append(f"{param_name}: {reason}")
            
            if not all_valid:
                print(f"  → REJECTED by KnobRegistry: {validation_failures[0]}")
                candidates.append(CandidateResult(
                    params=params,
                    param_hash=self.compute_param_hash(params),
                    fitness=Fitness(passed_scenarios=0, avg_score=0.0, tie_breaker=0.0),
                    eval_result=EvalResult.empty(),
                    validation_status="REJECTED",
                    validation_reason=f"KnobRegistry: {validation_failures[0]}"
                ))
                continue
            
            # Evaluate candidate
            eval_result = await self.evaluate_candidate(params, scenarios, scenario_set)
            fitness = Fitness.from_result(eval_result)
            param_hash = self.compute_param_hash(params)
            
            # Validate against holdout for overfitting
            holdout_candidate_result = await self.evaluate_candidate(params, scenario_set="holdout_set")
            validation_status, validation_reason = self.validate_candidate_against_holdout(
                CandidateResult(params, param_hash, fitness, eval_result),
                holdout_candidate_result,
                eval_result
            )
            
            candidate = CandidateResult(
                params=params,
                param_hash=param_hash,
                fitness=fitness,
                eval_result=eval_result,
                validation_status=validation_status,
                validation_reason=validation_reason
            )
            
            candidates.append(candidate)
            
            status_symbol = "✓" if validation_status == "VALID" else "✗"
            print(f"  → {status_symbol} {fitness.passed_scenarios} passed, score: {fitness.avg_score:.3f} ({validation_status})")
        
        # Step 5: Find best candidate (only among VALID ones)
        valid_candidates = [c for c in candidates if c.validation_status == "VALID"]
        best_candidate = None
        
        if valid_candidates:
            best_candidate = max(valid_candidates, key=lambda c: c.fitness)
            overall_improvement = best_candidate.fitness.dominates(baseline_fitness)
            
            # Determine lexicographic improvement level
            lexicographic_improvement = None
            if overall_improvement:
                if best_candidate.fitness.passed_scenarios > baseline_fitness.passed_scenarios:
                    lexicographic_improvement = "passed_scenarios"
                elif abs(best_candidate.fitness.avg_score - baseline_fitness.avg_score) > 1e-9:
                    lexicographic_improvement = "avg_score"
                else:
                    lexicographic_improvement = "tie_breaker"
        else:
            overall_improvement = False
            lexicographic_improvement = None
        
        # Step 6: Compile validation summary
        validation_summary = {
            "total_candidates": len(candidates),
            "valid_candidates": len(valid_candidates),
            "rejected_candidates": len(candidates) - len(valid_candidates),
            "overfit_candidates": len([c for c in candidates if c.validation_status == "OVERFIT"]),
            "knob_registry_summary": self.knob_registry.get_validation_summary()
        }
        
        rejection_reasons = Counter()
        for candidate in candidates:
            if candidate.validation_status != "VALID":
                reason_type = candidate.validation_reason.split(":")[0] if candidate.validation_reason else "UNKNOWN"
                rejection_reasons[reason_type] += 1
        
        return TuneResult(
            baseline_fitness=baseline_fitness,
            baseline_result=baseline_result,
            candidates=candidates,
            best_candidate=best_candidate,
            overall_improvement=overall_improvement,
            lexicographic_improvement=lexicographic_improvement,
            validation_summary=validation_summary,
            rejection_reasons=rejection_reasons
        )
    
    def save_report(self, result: TuneResult) -> Tuple[Path, Path]:
        """Save tuning report with validation details."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # JSON report
        json_data = {
            "timestamp": timestamp,
            "auto_tune_version": "0.4",
            "seed": self.seed,
            "baseline": result_to_dict(result.baseline_result),
            "baseline_fitness": {
                "passed_scenarios": result.baseline_fitness.passed_scenarios,
                "avg_score": result.baseline_fitness.avg_score,
                "tie_breaker": result.baseline_fitness.tie_breaker
            },
            "validation_summary": result.validation_summary,
            "rejection_reasons": dict(result.rejection_reasons),
            "candidates": []
        }
        
        for candidate in result.candidates:
            candidate_data = {
                "param_hash": candidate.param_hash,
                "params": candidate.params,
                "fitness": {
                    "passed_scenarios": candidate.fitness.passed_scenarios,
                    "avg_score": candidate.fitness.avg_score,
                    "tie_breaker": candidate.fitness.tie_breaker
                },
                "validation_status": candidate.validation_status,
                "validation_reason": candidate.validation_reason,
                "result": result_to_dict(candidate.eval_result)
            }
            json_data["candidates"].append(candidate_data)
        
        if result.best_candidate:
            json_data["best_candidate"] = {
                "param_hash": result.best_candidate.param_hash,
                "fitness": {
                    "passed_scenarios": result.best_candidate.fitness.passed_scenarios,
                    "avg_score": result.best_candidate.fitness.avg_score,
                    "tie_breaker": result.best_candidate.fitness.tie_breaker
                },
                "validation_status": result.best_candidate.validation_status,
                "params": result.best_candidate.params
            }
            json_data["overall_improvement"] = result.overall_improvement
            json_data["lexicographic_improvement"] = result.lexicographic_improvement
        
        json_path = self.output_dir / f"autotune_v04_{timestamp}.json"
        with open(json_path, 'w') as f:
            json.dump(json_data, f, indent=2)
        
        # Markdown report
        md_lines = [
            f"# Auto-Tune v0.4 Report (MVP-7.0 with KnobRegistry)",
            f"Generated: {timestamp}",
            f"Seed: {self.seed}",
            "",
            "## Validation Summary",
            f"- Total candidates: {result.validation_summary['total_candidates']}",
            f"- Valid candidates: {result.validation_summary['valid_candidates']}",
            f"- Rejected candidates: {result.validation_summary['rejected_candidates']}",
            f"- Overfit candidates: {result.validation_summary['overfit_candidates']}",
            "",
            "## Rejection Reasons",
        ]
        
        for reason, count in result.rejection_reasons.most_common():
            md_lines.append(f"- {reason}: {count}")
        
        md_lines.extend([
            "",
            "## KnobRegistry Summary",
            f"- Config version: {result.validation_summary['knob_registry_summary']['config_version']}",
            f"- Total validations: {result.validation_summary['knob_registry_summary']['total_validations']}",
            f"- Allowed changes: {result.validation_summary['knob_registry_summary']['allowed_changes']}",
            f"- Rejected changes: {result.validation_summary['knob_registry_summary']['rejected_changes']}",
            "",
            "## Baseline Performance",
            f"- Passed scenarios: {result.baseline_fitness.passed_scenarios}",
            f"- Average score: {result.baseline_fitness.avg_score:.3f}",
            f"- Tie-breaker: {result.baseline_fitness.tie_breaker:.6f}",
            ""
        ])
        
        if result.best_candidate:
            md_lines.extend([
                "## Best Candidate",
                f"- Param hash: {result.best_candidate.param_hash}",
                f"- Validation status: {result.best_candidate.validation_status}",
                f"- Passed scenarios: {result.best_candidate.fitness.passed_scenarios}",
                f"- Average score: {result.best_candidate.fitness.avg_score:.3f}",
                f"- Tie-breaker: {result.best_candidate.fitness.tie_breaker:.6f}",
                "",
                "### Best Parameters",
            ])
            
            for param, value in sorted(result.best_candidate.params.items()):
                md_lines.append(f"- {param}: {value}")
            
            md_lines.extend([
                "",
                "## Improvement Analysis",
                f"- Overall improvement: {'Yes' if result.overall_improvement else 'No'}",
            ])
            
            if result.lexicographic_improvement:
                md_lines.append(f"- Improvement level: {result.lexicographic_improvement}")
        
        md_path = self.output_dir / f"autotune_v04_{timestamp}.md"
        with open(md_path, 'w') as f:
            f.write('\n'.join(md_lines))
        
        return json_path, md_path

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Auto-Tune v0.4 for OpenEmotion MVP-7.0")
    parser.add_argument("--baseline", help="Baseline parameters file")
    parser.add_argument("--params", help="Candidate parameters file")
    parser.add_argument("--scenarios", nargs="+", help="Specific scenarios to run")
    parser.add_argument("--scenario-set", default="tune_set", help="Scenario set to use")
    parser.add_argument("--output", default="reports/mvp70", help="Output directory")
    parser.add_argument("--candidates", type=int, default=30, help="Number of candidates to generate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--skip-sentinel", action="store_true", help="Skip sentinel validation")
    
    args = parser.parse_args()
    
    # Setup paths
    repo_root = Path(__file__).parent.parent
    scenarios_dir = repo_root / "scenarios"
    output_dir = repo_root / args.output
    output_dir.mkdir(parents=True, exist_ok=True)
    
    baseline_params = {}
    if args.baseline:
        with open(args.baseline) as f:
            data = yaml.safe_load(f)
            baseline_params = data.get("params", data)
        print(f"Loaded baseline parameters from: {args.baseline}")

    candidate_params_list = None
    if args.params:
        with open(args.params) as f:
            data = yaml.safe_load(f)
            candidate_params = data.get("params", data)
        candidate_params_list = [candidate_params]
        print(f"Loaded candidate parameters from: {args.params}")

    scenarios = None
    if args.scenarios:
        scenarios = [Path(s) if Path(s).is_absolute() else scenarios_dir / s for s in args.scenarios]

    engine = AutoTuneEngine(scenarios_dir=scenarios_dir, output_dir=output_dir, seed=args.seed)

    print(f"\nRunning Auto-Tune v0.4 with KnobRegistry...")
    print(f"  Seed: {args.seed}")
    print(f"  Candidates: {args.candidates}")
    print(f"  Scenario set: {args.scenario_set}")
    print(f"  Output: {args.output}")
    print("")

    result = await engine.tune(
        baseline_params=baseline_params,
        candidate_params_list=candidate_params_list,
        scenarios=scenarios,
        generate_candidates=(candidate_params_list is None),
        candidate_count=args.candidates,
        skip_sentinel=args.skip_sentinel,
        scenario_set=args.scenario_set
    )

    json_path, md_path = engine.save_report(result)

    print(f"\nReports saved:")
    print(f"  JSON: {json_path}")
    print(f"  Markdown: {md_path}")
    print(f"\nBaseline: passed={result.baseline_fitness.passed_scenarios}, tie_breaker={result.baseline_fitness.tie_breaker:.6f}")
    if result.best_candidate:
        print(f"Best: passed={result.best_candidate.fitness.passed_scenarios}, tie_breaker={result.best_candidate.fitness.tie_breaker:.6f}")
        print(f"Overall: {'IMPROVED' if result.overall_improvement else 'NO IMPROVEMENT'}")
        if result.lexicographic_improvement:
            print(f"Improvement at level: {result.lexicographic_improvement}")
    
    print(f"\nValidation Summary:")
    print(f"  Valid: {result.validation_summary['valid_candidates']}/{result.validation_summary['total_candidates']}")
    print(f"  Rejected: {result.validation_summary['rejected_candidates']}")
    print(f"  Overfit: {result.validation_summary['overfit_candidates']}")

    return 0 if result.overall_improvement else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)