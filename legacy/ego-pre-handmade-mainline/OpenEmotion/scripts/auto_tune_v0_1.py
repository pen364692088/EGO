#!/usr/bin/env python3
"""
Auto-Tune v0.1 for OpenEmotion MVP-5.1 (D2)

Two-stage search with multi-objective fitness:
- Stage A: Global coarse search (Random + Latin Hypercube Sampling)
- Stage B: Local refinement (Coordinate descent / random hill climbing)

Features:
- Multi-objective fitness function with configurable weights
- Reproducible with --seed
- JSON/Markdown report outputs
- Best params JSON export

Usage:
    python scripts/auto_tune_v0_1.py --candidates 200 --refine-top 5 --refine-iters 100 --seed 42
"""

import os
import sys
import json
import yaml
import random
import asyncio
import tempfile
import shutil
import time
import statistics
import copy
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.eval_suite_v2 import (
    EvalSuiteV2, EvalResult, result_to_dict,
    TEST_SYSTEM_TOKEN, TEST_OPENCLAW_TOKEN
)
from emotiond import config, db, core


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
    "k_arousal": {"default": 2.0, "min": 0.5, "max": 5.0, "category": "timing"},
    "emotion_scale": {"default": 1.0, "min": 0.5, "max": 1.5, "category": "emotion"},
}

DEFAULT_FITNESS_WEIGHTS = {
    "scenario_pass_rate": 2.0,
    "high_impact_false_positive_rate": -1.5,
    "cross_target_interference": -1.0,
    "over_clarification_rate": -0.5,
    "avg_tokens_per_turn": -0.1,
}


@dataclass
class CandidateResult:
    candidate_id: int
    params: Dict[str, float]
    eval_result: Dict[str, Any]
    metrics: Dict[str, float]
    fitness: float
    stage: str
    parent_id: Optional[int] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "params": self.params,
            "eval_result": self.eval_result,
            "metrics": self.metrics,
            "fitness": self.fitness,
            "stage": self.stage,
            "parent_id": self.parent_id,
            "timestamp": self.timestamp
        }


@dataclass
class AutoTuneV1Result:
    timestamp: str
    seed: int
    git_commit: str
    param_space_version: str
    scenario_version: str
    baseline_params: Dict[str, float]
    baseline_metrics: Dict[str, float]
    baseline_fitness: float
    candidates: List[CandidateResult]
    top_candidates: List[CandidateResult]
    best_candidate: CandidateResult
    fitness_weights: Dict[str, float]
    search_config: Dict[str, Any]
    report_path: Optional[str] = None
    best_params_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "seed": self.seed,
            "git_commit": self.git_commit,
            "param_space_version": self.param_space_version,
            "scenario_version": self.scenario_version,
            "baseline_params": self.baseline_params,
            "baseline_metrics": self.baseline_metrics,
            "baseline_fitness": self.baseline_fitness,
            "candidates": [c.to_dict() for c in self.candidates],
            "top_candidates": [c.to_dict() for c in self.top_candidates],
            "best_candidate": self.best_candidate.to_dict(),
            "fitness_weights": self.fitness_weights,
            "search_config": self.search_config,
            "report_path": self.report_path,
            "best_params_path": self.best_params_path
        }


class ParameterLoader:
    @staticmethod
    def load(path: Path) -> Dict[str, float]:
        if not path.exists():
            raise FileNotFoundError(f"Parameter file not found: {path}")
        with open(path, 'r') as f:
            if path.suffix in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            elif path.suffix == '.json':
                data = json.load(f)
            else:
                raise ValueError(f"Unsupported file format: {path.suffix}")
        if isinstance(data, dict):
            if "params" in data:
                return data["params"]
            return {k: v for k, v in data.items() if isinstance(v, (int, float))}
        raise ValueError("Invalid parameter file format")

    @staticmethod
    def save(params: Dict[str, float], path: Path, metadata: Optional[Dict] = None):
        data = {"params": params}
        if metadata:
            data["metadata"] = metadata
        with open(path, 'w') as f:
            if path.suffix in ['.yaml', '.yml']:
                yaml.dump(data, f, default_flow_style=False)
            elif path.suffix == '.json':
                json.dump(data, f, indent=2)
            else:
                raise ValueError(f"Unsupported file format: {path.suffix}")


class LatinHypercubeSampler:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def sample(self, param_defs: Dict[str, Dict], n_samples: int) -> List[Dict[str, float]]:
        param_names = list(param_defs.keys())
        n_params = len(param_names)
        lhc = []
        for j in range(n_params):
            perm = list(range(n_samples))
            self.rng.shuffle(perm)
            lhc.append(perm)
        samples = []
        for i in range(n_samples):
            sample = {}
            for j, param_name in enumerate(param_names):
                defn = param_defs[param_name]
                min_val = defn["min"]
                max_val = defn["max"]
                range_val = max_val - min_val
                stratum = lhc[j][i]
                stratum_size = range_val / n_samples
                offset = self.rng.random() * stratum_size
                value = min_val + stratum * stratum_size + offset
                sample[param_name] = max(min_val, min(max_val, value))
            samples.append(sample)
        return samples


class RandomSampler:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def sample(self, param_defs: Dict[str, Dict], n_samples: int) -> List[Dict[str, float]]:
        samples = []
        for _ in range(n_samples):
            sample = {}
            for param_name, defn in param_defs.items():
                min_val = defn["min"]
                max_val = defn["max"]
                sample[param_name] = min_val + self.rng.random() * (max_val - min_val)
            samples.append(sample)
        return samples


class LocalRefiner:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.coordinate_index = 0

    def refine(self, center: Dict[str, float], param_defs: Dict[str, Dict],
               strategy: str = "coordinate_descent", step_size: float = 0.1) -> Dict[str, float]:
        refined = copy.deepcopy(center)
        param_names = list(center.keys())

        if strategy == "coordinate_descent":
            param_name = param_names[self.coordinate_index % len(param_names)]
            self.coordinate_index += 1
            defn = param_defs[param_name]
            min_val = defn["min"]
            max_val = defn["max"]
            range_val = max_val - min_val
            current = center[param_name]
            delta = self.rng.choice([-1, 1]) * step_size * range_val
            new_value = current + delta
            refined[param_name] = max(min_val, min(max_val, new_value))
        elif strategy == "random_hill":
            for param_name in param_names:
                defn = param_defs[param_name]
                min_val = defn["min"]
                max_val = defn["max"]
                range_val = max_val - min_val
                current = center[param_name]
                delta = self.rng.gauss(0, step_size * range_val)
                new_value = current + delta
                refined[param_name] = max(min_val, min(max_val, new_value))
        else:
            raise ValueError(f"Unknown refinement strategy: {strategy}")
        return refined


class FitnessEvaluator:
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or DEFAULT_FITNESS_WEIGHTS.copy()

    def extract_metrics(self, eval_result: EvalResult) -> Dict[str, float]:
        metrics = {}
        aggregate = eval_result.aggregate_metrics
        total = eval_result.total_scenarios
        passed = eval_result.passed_scenarios
        metrics["scenario_pass_rate"] = passed / total if total > 0 else 0.0
        fp_data = aggregate.get("high_impact_false_positive_rate", {})
        metrics["high_impact_false_positive_rate"] = fp_data.get("average", 0.0)
        indiv_data = aggregate.get("individualization_diff", {})
        max_diff = indiv_data.get("max", 0.0)
        metrics["cross_target_interference"] = max(0.0, 1.0 - max_diff)
        mc_data = aggregate.get("meta_cognition_trigger_rate", {})
        trigger_rate = mc_data.get("average", 0.0)
        metrics["over_clarification_rate"] = max(0.0, trigger_rate - 0.5)
        total_turns = sum(len(s.turns) for s in eval_result.scenarios)
        metrics["avg_tokens_per_turn"] = total_turns / total if total > 0 else 0.0
        return metrics

    def compute_fitness(self, metrics: Dict[str, float]) -> float:
        fitness = 0.0
        for metric_name, weight in self.weights.items():
            value = metrics.get(metric_name, 0.0)
            fitness += weight * value
        return fitness

    def compare_candidates(self, c1: CandidateResult, c2: CandidateResult) -> int:
        if c1.fitness > c2.fitness:
            return -1
        elif c1.fitness < c2.fitness:
            return 1
        pass1 = c1.metrics.get("scenario_pass_rate", 0)
        pass2 = c2.metrics.get("scenario_pass_rate", 0)
        if pass1 > pass2:
            return -1
        elif pass1 < pass2:
            return 1
        return 0


class AutoTuneV1Engine:
    def __init__(self, scenarios_dir: Path, output_dir: Path,
                 seed: int = 42, fitness_weights: Optional[Dict[str, float]] = None):
        self.scenarios_dir = scenarios_dir
        self.output_dir = output_dir
        self.seed = seed
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.lhs_sampler = LatinHypercubeSampler(seed)
        self.random_sampler = RandomSampler(seed + 1)
        self.refiner = LocalRefiner(seed + 2)
        self.fitness_evaluator = FitnessEvaluator(fitness_weights)
        self.candidate_counter = 0
        self.candidates: List[CandidateResult] = []
        self.git_commit = self._get_git_commit()
        self.param_space_version = "mvp5.1_v1"
        self.scenario_version = self._get_scenario_version()

    def _get_git_commit(self) -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except Exception:
            return "unknown"

    def _get_scenario_version(self) -> str:
        try:
            if self.scenarios_dir.exists():
                files = sorted(self.scenarios_dir.glob("*.yaml"))
                content = b""
                for f in files:
                    content += f.read_bytes()
                return hashlib.md5(content).hexdigest()[:8]
        except Exception:
            pass
        return "unknown"

    def apply_parameters(self, params: Dict[str, float]):
        """Apply parameters to config module for dynamic override during evaluation."""
        # MVP-5.1: Set params in config module (not just core)
        from emotiond import config
        config.clear_auto_tune_params()
        for name, value in params.items():
            config.set_auto_tune_param(name, value)
        # Also set on core for backward compatibility
        core._auto_tune_params = getattr(core, '_auto_tune_params', {})
        core._auto_tune_params.update(params)

    async def run_eval(self, params: Dict[str, float],
                      scenarios: Optional[List[Path]] = None) -> EvalResult:
        self.apply_parameters(params)
        suite = EvalSuiteV2(scenarios_dir=self.scenarios_dir, output_format="json")
        result = await suite.run_all(scenarios)
        return result

    def _create_candidate(self, params: Dict[str, float], eval_result: EvalResult,
                         stage: str, parent_id: Optional[int] = None) -> CandidateResult:
        self.candidate_counter += 1
        metrics = self.fitness_evaluator.extract_metrics(eval_result)
        fitness = self.fitness_evaluator.compute_fitness(metrics)
        return CandidateResult(
            candidate_id=self.candidate_counter,
            params=params,
            eval_result=result_to_dict(eval_result),
            metrics=metrics,
            fitness=fitness,
            stage=stage,
            parent_id=parent_id
        )

    async def run_stage_a_global_search(self, baseline: Dict[str, float],
                                        n_candidates: int = 200,
                                        scenarios: Optional[List[Path]] = None) -> List[CandidateResult]:
        print(f"\n{'='*60}")
        print("STAGE A: Global Coarse Search")
        print(f"{'='*60}")
        print(f"Generating {n_candidates} candidates using LHS + Random sampling")
        n_lhs = int(n_candidates * 0.7)
        n_random = n_candidates - n_lhs
        lhs_samples = self.lhs_sampler.sample(DEFAULT_TUNABLE_PARAMS, n_lhs)
        random_samples = self.random_sampler.sample(DEFAULT_TUNABLE_PARAMS, n_random)
        all_samples = lhs_samples + random_samples
        random.Random(self.seed + 3).shuffle(all_samples)
        stage_candidates = []
        for i, params in enumerate(all_samples):
            print(f"\n[Stage A] Evaluating candidate {i+1}/{n_candidates} (ID: {self.candidate_counter + 1})")
            try:
                eval_result = await self.run_eval(params, scenarios)
                candidate = self._create_candidate(params, eval_result, stage="global")
                stage_candidates.append(candidate)
                print(f"  Fitness: {candidate.fitness:.4f}")
                print(f"  Pass rate: {candidate.metrics.get('scenario_pass_rate', 0):.2%}")
            except Exception as e:
                print(f"  ERROR: {e}")
                continue
        print(f"\nStage A complete: {len(stage_candidates)} candidates evaluated")
        return stage_candidates

    async def run_stage_b_local_refinement(self, top_candidates: List[CandidateResult],
                                           n_iterations: int = 100,
                                           scenarios: Optional[List[Path]] = None) -> List[CandidateResult]:
        print(f"\n{'='*60}")
        print("STAGE B: Local Refinement")
        print(f"{'='*60}")
        print(f"Refining top {len(top_candidates)} candidates with {n_iterations} iterations")
        stage_candidates = []
        iterations_per_candidate = n_iterations // len(top_candidates)
        for top_idx, top_candidate in enumerate(top_candidates):
            print(f"\n[Stage B] Refining candidate {top_candidate.candidate_id} ({top_idx+1}/{len(top_candidates)})")
            print(f"  Starting fitness: {top_candidate.fitness:.4f}")
            current_best = top_candidate
            current_center = copy.deepcopy(top_candidate.params)
            for iteration in range(iterations_per_candidate):
                strategy = "coordinate_descent" if iteration % 2 == 0 else "random_hill"
                step_size = 0.1 * (1.0 - iteration / iterations_per_candidate)
                refined_params = self.refiner.refine(current_center, DEFAULT_TUNABLE_PARAMS, strategy, step_size)
                try:
                    eval_result = await self.run_eval(refined_params, scenarios)
                    refined_candidate = self._create_candidate(
                        refined_params, eval_result, stage="local", parent_id=current_best.candidate_id
                    )
                    stage_candidates.append(refined_candidate)
                    if refined_candidate.fitness > current_best.fitness:
                        print(f"    Iter {iteration+1}: Improved! {current_best.fitness:.4f} -> {refined_candidate.fitness:.4f}")
                        current_best = refined_candidate
                        current_center = copy.deepcopy(refined_params)
                except Exception as e:
                    print(f"    Iter {iteration+1}: ERROR - {e}")
                    continue
            print(f"  Final fitness: {current_best.fitness:.4f}")
        print(f"\nStage B complete: {len(stage_candidates)} additional candidates evaluated")
        return stage_candidates

    async def tune(self, baseline_params: Optional[Dict[str, float]] = None,
                   scenarios: Optional[List[Path]] = None,
                   n_global_candidates: int = 200,
                   n_refine_top: int = 5,
                   n_refine_iterations: int = 100) -> AutoTuneV1Result:
        start_time = datetime.now()
        if baseline_params is None:
            baseline_params = {name: defn["default"] for name, defn in DEFAULT_TUNABLE_PARAMS.items()}
        print(f"\n{'#'*60}")
        print("# Auto-Tune v0.1 - Two-Stage Parameter Search")
        print(f"{'#'*60}")
        print(f"Seed: {self.seed}")
        print(f"Git commit: {self.git_commit}")
        print(f"Global candidates: {n_global_candidates}")
        print(f"Refinement: top-{n_refine_top} with {n_refine_iterations} iterations")
        print(f"\n{'='*60}")
        print("BASELINE EVALUATION")
        print(f"{'='*60}")
        baseline_eval = await self.run_eval(baseline_params, scenarios)
        baseline_metrics = self.fitness_evaluator.extract_metrics(baseline_eval)
        baseline_fitness = self.fitness_evaluator.compute_fitness(baseline_metrics)
        print(f"Baseline fitness: {baseline_fitness:.4f}")
        print(f"Baseline pass rate: {baseline_metrics.get('scenario_pass_rate', 0):.2%}")
        global_candidates = await self.run_stage_a_global_search(baseline_params, n_global_candidates, scenarios)
        self.candidates.extend(global_candidates)
        sorted_candidates = sorted(self.candidates, key=lambda c: c.fitness, reverse=True)
        top_for_refinement = sorted_candidates[:n_refine_top]
        print(f"\nTop {n_refine_top} candidates for refinement:")
        for i, c in enumerate(top_for_refinement):
            print(f"  {i+1}. ID {c.candidate_id}: fitness={c.fitness:.4f}, pass_rate={c.metrics.get('scenario_pass_rate', 0):.2%}")
        local_candidates = await self.run_stage_b_local_refinement(top_for_refinement, n_refine_iterations, scenarios)
        self.candidates.extend(local_candidates)
        all_sorted = sorted(self.candidates, key=lambda c: c.fitness, reverse=True)
        top_10 = all_sorted[:10]
        best = all_sorted[0]
        result = AutoTuneV1Result(
            timestamp=start_time.isoformat(),
            seed=self.seed,
            git_commit=self.git_commit,
            param_space_version=self.param_space_version,
            scenario_version=self.scenario_version,
            baseline_params=baseline_params,
            baseline_metrics=baseline_metrics,
            baseline_fitness=baseline_fitness,
            candidates=self.candidates,
            top_candidates=top_10,
            best_candidate=best,
            fitness_weights=self.fitness_evaluator.weights,
            search_config={
                "n_global_candidates": n_global_candidates,
                "n_refine_top": n_refine_top,
                "n_refine_iterations": n_refine_iterations,
                "lhs_ratio": 0.7,
                "random_ratio": 0.3
            }
        )
        return result

    def save_reports(self, result: AutoTuneV1Result) -> Tuple[Path, Path, Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        base_name = f"auto_tune_{self.timestamp}"
        json_path = self.output_dir / f"{base_name}.json"
        with open(json_path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2, default=str)
        md_path = self.output_dir / f"{base_name}.md"
        markdown = self._generate_markdown(result)
        with open(md_path, 'w') as f:
            f.write(markdown)
        best_params_path = self.output_dir / f"best_params_{self.timestamp}.json"
        best_params_data = {
            "params": result.best_candidate.params,
            "metadata": {
                "candidate_id": result.best_candidate.candidate_id,
                "fitness": result.best_candidate.fitness,
                "metrics": result.best_candidate.metrics,
                "timestamp": result.timestamp,
                "git_commit": result.git_commit,
                "seed": result.seed
            }
        }
        with open(best_params_path, 'w') as f:
            json.dump(best_params_data, f, indent=2)
        result.report_path = str(json_path)
        result.best_params_path = str(best_params_path)
        return json_path, md_path, best_params_path

    def _generate_markdown(self, result: AutoTuneV1Result) -> str:
        lines = []
        lines.append("# Auto-Tune v0.1 Report")
        lines.append("")
        lines.append(f"**Generated:** {result.timestamp}")
        lines.append(f"**Random Seed:** {result.seed}")
        lines.append(f"**Git Commit:** {result.git_commit}")
        lines.append(f"**Param Space Version:** {result.param_space_version}")
        lines.append(f"**Scenario Version:** {result.scenario_version}")
        lines.append("")
        lines.append("## Search Configuration")
        lines.append("")
        lines.append(f"- Global candidates: {result.search_config['n_global_candidates']}")
        lines.append(f"- Refinement top-k: {result.search_config['n_refine_top']}")
        lines.append(f"- Refinement iterations: {result.search_config['n_refine_iterations']}")
        lines.append(f"- LHS ratio: {result.search_config['lhs_ratio']}")
        lines.append(f"- Random ratio: {result.search_config['random_ratio']}")
        lines.append("")
        lines.append("## Fitness Weights")
        lines.append("")
        lines.append("| Objective | Weight |")
        lines.append("|-----------|--------|")
        for obj, weight in result.fitness_weights.items():
            direction = "maximize" if weight > 0 else "minimize"
            lines.append(f"| {obj} | {weight} ({direction}) |")
        lines.append("")
        lines.append("## Baseline vs Best")
        lines.append("")
        lines.append("| Metric | Baseline | Best | Improvement |")
        lines.append("|--------|----------|------|-------------|")
        for metric_name in result.fitness_weights.keys():
            base_val = result.baseline_metrics.get(metric_name, 0)
            best_val = result.best_candidate.metrics.get(metric_name, 0)
            diff = best_val - base_val
            pct = (diff / base_val * 100) if base_val != 0 else 0
            lines.append(f"| {metric_name} | {base_val:.4f} | {best_val:.4f} | {diff:+.4f} ({pct:+.1f}%) |")
        lines.append("")
        lines.append(f"**Baseline Fitness:** {result.baseline_fitness:.4f}")
        lines.append(f"**Best Fitness:** {result.best_candidate.fitness:.4f}")
        lines.append(f"**Fitness Improvement:** {result.best_candidate.fitness - result.baseline_fitness:+.4f}")
        lines.append("")
        lines.append("## Top 10 Candidates")
        lines.append("")
        lines.append("| Rank | ID | Stage | Fitness | Pass Rate |")
        lines.append("|------|-----|-------|---------|-----------|")
        for i, c in enumerate(result.top_candidates):
            pass_rate = c.metrics.get('scenario_pass_rate', 0)
            lines.append(f"| {i+1} | {c.candidate_id} | {c.stage} | {c.fitness:.4f} | {pass_rate:.2%} |")
        lines.append("")
        lines.append("## Best Candidate Parameters")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(result.best_candidate.params, indent=2))
        lines.append("```")
        lines.append("")
        lines.append("## Trade-off Analysis")
        lines.append("")
        lines.append("The best candidate was selected based on multi-objective fitness.")
        lines.append("")
        best = result.best_candidate
        base = result.baseline_metrics
        improvements = []
        regressions = []
        for metric_name, weight in result.fitness_weights.items():
            best_val = best.metrics.get(metric_name, 0)
            base_val = base.get(metric_name, 0)
            diff = best_val - base_val
            if weight > 0 and diff > 0:
                improvements.append(f"- **{metric_name}**: +{diff:.4f} (better)")
            elif weight < 0 and diff < 0:
                improvements.append(f"- **{metric_name}**: {diff:.4f} (better)")
            elif abs(diff) > 0.01:
                regressions.append(f"- **{metric_name}**: {diff:+.4f} (sacrificed)")
        if improvements:
            lines.append("### Improvements")
            lines.extend(improvements)
            lines.append("")
        if regressions:
            lines.append("### Sacrifices")
            lines.extend(regressions)
            lines.append("")
        lines.append("---")
        lines.append("*Generated by OpenEmotion Auto-Tune v0.1*")
        return "\n".join(lines)


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Auto-Tune v0.1 for OpenEmotion MVP-5.1")
    parser.add_argument("--baseline", type=Path, help="Baseline parameter file")
    parser.add_argument("--output", "-o", type=Path, default=Path("reports"), help="Output directory")
    parser.add_argument("--scenarios", "-s", nargs="+", help="Specific scenario files")
    parser.add_argument("--candidates", type=int, default=200, help="Number of global candidates")
    parser.add_argument("--refine-top", type=int, default=5, help="Top candidates to refine")
    parser.add_argument("--refine-iters", type=int, default=100, help="Refinement iterations")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--fitness-weights", type=Path, help="Custom fitness weights JSON")
    parser.add_argument("--list-params", action="store_true", help="List tunable parameters")
    parser.add_argument("--generate-defaults", type=Path, metavar="OUTPUT_FILE", help="Generate defaults")
    args = parser.parse_args()

    if args.list_params:
        print("# Tunable Parameters")
        for name, defn in sorted(DEFAULT_TUNABLE_PARAMS.items()):
            print(f"\n## {name}")
            print(f"- Default: {defn['default']}")
            print(f"- Range: [{defn['min']}, {defn['max']}]")
            print(f"- Category: {defn['category']}")
        return 0

    if args.generate_defaults:
        defaults = {name: defn["default"] for name, defn in DEFAULT_TUNABLE_PARAMS.items()}
        metadata = {"description": "Default parameters", "version": "0.1"}
        ParameterLoader.save(defaults, args.generate_defaults, metadata)
        print(f"Defaults written to: {args.generate_defaults}")
        return 0

    base_path = Path(__file__).parent.parent
    scenarios_dir = base_path / "scenarios"
    baseline_params = None
    if args.baseline:
        baseline_params = ParameterLoader.load(args.baseline)
    fitness_weights = None
    if args.fitness_weights:
        with open(args.fitness_weights, 'r') as f:
            fitness_weights = json.load(f)
    scenarios = None
    if args.scenarios:
        scenarios = [Path(s) if Path(s).is_absolute() else scenarios_dir / s for s in args.scenarios]

    engine = AutoTuneV1Engine(scenarios_dir=scenarios_dir, output_dir=args.output,
                              seed=args.seed, fitness_weights=fitness_weights)
    print(f"Running Auto-Tune v0.1 with seed={args.seed}")
    result = await engine.tune(baseline_params=baseline_params, scenarios=scenarios,
                               n_global_candidates=args.candidates,
                               n_refine_top=args.refine_top,
                               n_refine_iterations=args.refine_iters)
    json_path, md_path, best_params_path = engine.save_reports(result)
    print(f"\nReports saved:")
    print(f"  JSON: {json_path}")
    print(f"  Markdown: {md_path}")
    print(f"  Best params: {best_params_path}")
    return 0 if result.best_candidate.fitness > result.baseline_fitness else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
