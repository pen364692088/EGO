#!/usr/bin/env python3
"""
Auto-Tune v0.2 for OpenEmotion MVP-6

Upgrades from v0:
- New fitness metrics: recovery_score, collapse_penalty, efficiency
- Only tuning parameters, not core logic
- Enhanced candidate evaluation with body telemetry
- Reproducible with fixed seed

Usage:
    python scripts/auto_tune_v0_2.py --params params.yaml --output reports/
    python scripts/auto_tune_v0_2.py --candidates 100 --seed 42 --output reports/

Features:
- Input: Tunable parameters (JSON/YAML)
- Run: eval_suite_v2_2 on baseline and candidate configurations
- Output: JSON report + Markdown summary with fitness metrics
- Reproducible: Fixed random seed support
- Fitness v0.2: recovery_score, collapse_penalty, efficiency
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
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field, asdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import eval_suite_v2_2 components
from scripts.eval_suite_v2_2 import (
    EvalSuiteV2_2, ScenarioRunner, EvalResult, ScenarioResult,
    result_to_dict, TEST_SYSTEM_TOKEN, TEST_OPENCLAW_TOKEN
)
from emotiond import config, db, core


# Default tunable parameters and their ranges (same as v0)
DEFAULT_TUNABLE_PARAMS = {
    # Precision controller parameters
    "precision_temperature": {
        "default": 0.5,
        "min": 0.1,
        "max": 1.0,
        "description": "Temperature for precision weight calculations",
        "category": "precision"
    },
    "precision_uncertainty_threshold": {
        "default": 0.3,
        "min": 0.1,
        "max": 0.8,
        "description": "Threshold for triggering precision-based clarification",
        "category": "precision"
    },
    "w_external_default": {
        "default": 0.6,
        "min": 0.2,
        "max": 0.9,
        "description": "Default weight for external (user) information",
        "category": "precision"
    },
    "w_internal_default": {
        "default": 0.5,
        "min": 0.2,
        "max": 0.8,
        "description": "Default weight for internal (interoceptive) states",
        "category": "precision"
    },
    "w_memory_default": {
        "default": 0.4,
        "min": 0.1,
        "max": 0.7,
        "description": "Default weight for memory/ledger/bond",
        "category": "precision"
    },
    "w_action_default": {
        "default": 0.5,
        "min": 0.2,
        "max": 0.8,
        "description": "Default weight for action decisiveness",
        "category": "precision"
    },
    "w_explore_default": {
        "default": 0.3,
        "min": 0.1,
        "max": 0.6,
        "description": "Default weight for exploration tendency",
        "category": "precision"
    },

    # Allostasis budget parameters
    "energy_recovery_rate": {
        "default": 0.001,
        "min": 0.0001,
        "max": 0.01,
        "description": "Rate of energy recovery per second",
        "category": "allostasis"
    },
    "energy_depletion_conflict": {
        "default": 0.05,
        "min": 0.01,
        "max": 0.15,
        "description": "Energy depletion from high conflict events",
        "category": "allostasis"
    },
    "energy_depletion_uncertainty": {
        "default": 0.03,
        "min": 0.01,
        "max": 0.1,
        "description": "Energy depletion from high uncertainty",
        "category": "allostasis"
    },
    "low_energy_explore_dampening": {
        "default": 0.5,
        "min": 0.1,
        "max": 0.9,
        "description": "Factor to reduce exploration when energy is low",
        "category": "allostasis"
    },
    "low_energy_learning_dampening": {
        "default": 0.7,
        "min": 0.3,
        "max": 0.95,
        "description": "Factor to reduce learning rate when energy is low",
        "category": "allostasis"
    },

    # Intrinsic motivation parameters
    "curiosity_info_gain_threshold": {
        "default": 0.2,
        "min": 0.05,
        "max": 0.5,
        "description": "Expected info gain threshold to trigger curiosity",
        "category": "intrinsic"
    },
    "boredom_prediction_error_threshold": {
        "default": 0.05,
        "min": 0.01,
        "max": 0.2,
        "description": "Low prediction error threshold for boredom onset",
        "category": "intrinsic"
    },
    "confusion_error_threshold": {
        "default": 0.3,
        "min": 0.15,
        "max": 0.6,
        "description": "High prediction error threshold for confusion",
        "category": "intrinsic"
    },
    "boredom_time_window": {
        "default": 300,
        "min": 60,
        "max": 900,
        "description": "Time window (seconds) for boredom accumulation",
        "category": "intrinsic"
    },

    # Self-model parameters
    "self_model_update_rate": {
        "default": 0.1,
        "min": 0.01,
        "max": 0.3,
        "description": "Rate of self-model update from new evidence",
        "category": "self_model"
    },
    "identity_stability_threshold": {
        "default": 0.8,
        "min": 0.5,
        "max": 0.95,
        "description": "Threshold for identity stability (prevents jumpy updates)",
        "category": "self_model"
    },
    "value_conflict_resolution_rate": {
        "default": 0.05,
        "min": 0.01,
        "max": 0.2,
        "description": "Rate for resolving value conflicts",
        "category": "self_model"
    },

    # Meta-cognition parameters
    "clarification_trigger_threshold": {
        "default": 0.4,
        "min": 0.2,
        "max": 0.7,
        "description": "Threshold for triggering clarification meta-cognition",
        "category": "meta_cognition"
    },
    "reflection_trigger_threshold": {
        "default": 0.5,
        "min": 0.3,
        "max": 0.8,
        "description": "Threshold for triggering reflection meta-cognition",
        "category": "meta_cognition"
    },
}


@dataclass
class ParameterSet:
    """A set of tunable parameters"""
    name: str
    params: Dict[str, float]
    seed: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "params": self.params,
            "seed": self.seed,
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ParameterSet":
        return cls(
            name=data["name"],
            params=data["params"],
            seed=data.get("seed", 42),
            timestamp=data.get("timestamp", datetime.now().isoformat())
        )


@dataclass
class FitnessMetrics:
    """MVP-6 Fitness v0.2 metrics"""
    recovery_score: float  # 0-1, higher is better
    collapse_penalty: float  # 0-1, lower is better (penalty for energy/valence collapse)
    efficiency: float  # 0-1, higher is better (success per unit resource)
    emotion_consistency: float  # 0-1
    robustness: float  # 0-1
    
    # Composite score
    composite: float = 0.0
    
    def calculate_composite(self) -> float:
        """Calculate weighted composite fitness score"""
        weights = {
            "recovery_score": 0.25,
            "collapse_penalty": 0.25,  # Inverted in calculation
            "efficiency": 0.20,
            "emotion_consistency": 0.15,
            "robustness": 0.15
        }
        
        # Invert collapse_penalty (lower is better, so we want 1 - penalty)
        collapse_score = 1.0 - self.collapse_penalty
        
        self.composite = (
            weights["recovery_score"] * self.recovery_score +
            weights["collapse_penalty"] * collapse_score +
            weights["efficiency"] * self.efficiency +
            weights["emotion_consistency"] * self.emotion_consistency +
            weights["robustness"] * self.robustness
        )
        return self.composite
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "recovery_score": self.recovery_score,
            "collapse_penalty": self.collapse_penalty,
            "efficiency": self.efficiency,
            "emotion_consistency": self.emotion_consistency,
            "robustness": self.robustness,
            "composite": self.composite
        }


@dataclass
class CandidateResult:
    """Result for a single candidate evaluation"""
    candidate_id: str
    params: Dict[str, float]
    fitness: FitnessMetrics
    eval_result: Dict[str, Any]
    rank: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "params": self.params,
            "fitness": self.fitness.to_dict(),
            "eval_result": self.eval_result,
            "rank": self.rank
        }


@dataclass
class AutoTuneResult:
    """Complete auto-tune result"""
    timestamp: str
    seed: int
    baseline_params: Dict[str, Any]
    baseline_fitness: FitnessMetrics
    baseline_result: Dict[str, Any]
    candidates: List[CandidateResult]
    best_candidate: Optional[CandidateResult] = None
    overall_improvement: bool = False
    recommendations: List[str] = field(default_factory=list)
    report_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "seed": self.seed,
            "baseline_params": self.baseline_params,
            "baseline_fitness": self.baseline_fitness.to_dict(),
            "baseline_result": self.baseline_result,
            "candidates": [c.to_dict() for c in self.candidates],
            "best_candidate": self.best_candidate.to_dict() if self.best_candidate else None,
            "overall_improvement": self.overall_improvement,
            "recommendations": self.recommendations,
            "report_path": self.report_path
        }


class FitnessCalculator:
    """Calculate fitness v0.2 metrics from eval results"""
    
    @staticmethod
    def calculate_recovery_score(eval_result: EvalResult) -> float:
        """Calculate recovery score from eval results"""
        recovery_scores = []
        
        for scenario in eval_result.scenarios:
            # Get recovery metrics from scenario
            recovery_data = scenario.metrics.get("recovery_score", {})
            score = recovery_data.get("score", 1.0)
            recovery_scores.append(score)
        
        return statistics.mean(recovery_scores) if recovery_scores else 1.0
    
    @staticmethod
    def calculate_collapse_penalty(eval_result: EvalResult) -> float:
        """Calculate collapse penalty (energy/valence collapse detection)"""
        penalties = []
        
        for scenario in eval_result.scenarios:
            telemetry = scenario.metrics.get("body_telemetry", {}).get("data", {})
            
            # Check for energy collapse
            energy_min = telemetry.get("energy", {}).get("min", 0.7)
            energy_collapse = max(0, 0.3 - energy_min) / 0.3  # Penalty if energy < 0.3
            
            # Check for valence collapse
            valence_data = telemetry.get("valence", {})
            valence_min = valence_data.get("min", 0) if isinstance(valence_data, dict) else 0
            valence_collapse = max(0, -0.5 - valence_min) / 0.5  # Penalty if valence < -0.5
            
            # Combined penalty
            penalty = max(energy_collapse, valence_collapse)
            penalties.append(min(1.0, penalty))
        
        return statistics.mean(penalties) if penalties else 0.0
    
    @staticmethod
    def calculate_efficiency(eval_result: EvalResult) -> float:
        """Calculate efficiency (success per unit resource)"""
        if not eval_result.scenarios:
            return 0.0
        
        total_turns = sum(len(s.turns) for s in eval_result.scenarios)
        successful_turns = sum(
            sum(1 for t in s.turns if t.success)
            for s in eval_result.scenarios
        )
        
        # Efficiency = success rate normalized
        if total_turns == 0:
            return 0.0
        
        success_rate = successful_turns / total_turns
        
        # Adjust for energy consumption (lower energy min = less efficient)
        avg_energy_min = statistics.mean([
            s.metrics.get("body_telemetry", {}).get("data", {}).get("energy", {}).get("min", 0.7)
            for s in eval_result.scenarios
        ]) if eval_result.scenarios else 0.7
        
        # Efficiency = success_rate * energy_efficiency
        energy_efficiency = avg_energy_min  # Higher min energy = more efficient
        
        return success_rate * energy_efficiency
    
    @staticmethod
    def calculate_emotion_consistency(eval_result: EvalResult) -> float:
        """Calculate emotion consistency score"""
        consistency_data = eval_result.aggregate_metrics.get("emotion_consistency", {})
        return consistency_data.get("pass_rate", 1.0)
    
    @staticmethod
    def calculate_robustness(eval_result: EvalResult) -> float:
        """Calculate robustness score"""
        robustness_scores = []
        
        for scenario in eval_result.scenarios:
            robustness_data = scenario.metrics.get("robustness_score", {})
            score = robustness_data.get("score", 1.0)
            robustness_scores.append(score)
        
        return statistics.mean(robustness_scores) if robustness_scores else 1.0
    
    @classmethod
    def calculate_all(cls, eval_result: EvalResult) -> FitnessMetrics:
        """Calculate all fitness metrics"""
        fitness = FitnessMetrics(
            recovery_score=cls.calculate_recovery_score(eval_result),
            collapse_penalty=cls.calculate_collapse_penalty(eval_result),
            efficiency=cls.calculate_efficiency(eval_result),
            emotion_consistency=cls.calculate_emotion_consistency(eval_result),
            robustness=cls.calculate_robustness(eval_result)
        )
        fitness.calculate_composite()
        return fitness


class ParameterLoader:
    """Load parameters from JSON/YAML files"""

    @staticmethod
    def load(path: Path) -> Dict[str, float]:
        """Load parameters from file"""
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
        """Save parameters to file"""
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


class PerturbationGenerator:
    """Generate parameter perturbations for candidate testing"""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def perturb(self, params: Dict[str, float], param_defs: Dict[str, Dict],
                strategy: str = "random", magnitude: float = 0.2) -> Dict[str, float]:
        """Generate perturbed parameters"""
        perturbed = copy.deepcopy(params)

        for name, value in perturbed.items():
            definition = param_defs.get(name, {})
            min_val = definition.get("min", value * 0.5)
            max_val = definition.get("max", value * 1.5)
            range_val = max_val - min_val

            if strategy == "random":
                delta = self.rng.uniform(-1, 1) * magnitude * range_val
                new_value = value + delta
            elif strategy == "gaussian":
                std = magnitude * range_val / 3
                delta = self.rng.gauss(0, std)
                new_value = value + delta
            elif strategy == "boundary":
                if self.rng.random() < 0.5:
                    new_value = min_val + magnitude * range_val * self.rng.random()
                else:
                    new_value = max_val - magnitude * range_val * self.rng.random()
            else:
                raise ValueError(f"Unknown strategy: {strategy}")

            perturbed[name] = max(min_val, min(max_val, new_value))

        return perturbed

    def generate_candidates(self, baseline: Dict[str, float],
                           param_defs: Dict[str, Dict],
                           count: int = 3,
                           strategies: List[str] = None) -> List[Dict[str, float]]:
        """Generate multiple candidate parameter sets"""
        if strategies is None:
            strategies = ["random", "gaussian", "boundary"]

        candidates = []
        for i in range(count):
            strategy = strategies[i % len(strategies)]
            magnitude = 0.1 + (i * 0.05)  # Gradually increasing perturbation
            candidate = self.perturb(baseline, param_defs, strategy, magnitude)
            candidates.append(candidate)

        return candidates


class AutoTuneEngine:
    """Main auto-tuning engine v0.2"""

    def __init__(self, scenarios_dir: Path, output_dir: Path, seed: int = 42):
        self.scenarios_dir = scenarios_dir
        self.output_dir = output_dir
        self.seed = seed
        self.perturbation_gen = PerturbationGenerator(seed)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def apply_parameters(self, params: Dict[str, float]):
        """Apply parameters to the emotiond configuration"""
        core._auto_tune_params = getattr(core, '_auto_tune_params', {})
        core._auto_tune_params.update(params)

    async def run_eval(self, params: Dict[str, float],
                      scenarios: Optional[List[Path]] = None) -> EvalResult:
        """Run eval suite with given parameters"""
        self.apply_parameters(params)

        suite = EvalSuiteV2_2(
            scenarios_dir=self.scenarios_dir,
            output_format="json",
            seed=self.seed
        )

        result = await suite.run_all(scenarios)
        return result

    async def tune(self,
                   baseline_params: Optional[Dict[str, float]] = None,
                   candidate_params_list: Optional[List[Dict[str, float]]] = None,
                   scenarios: Optional[List[Path]] = None,
                   generate_candidates: bool = False,
                   candidate_count: int = 1) -> AutoTuneResult:
        """Run auto-tuning comparison with multiple candidates"""
        
        # Use default parameters if not provided
        if baseline_params is None:
            baseline_params = {
                name: defn["default"]
                for name, defn in DEFAULT_TUNABLE_PARAMS.items()
            }

        # Generate or use candidates
        if candidate_params_list is None:
            if generate_candidates:
                candidate_params_list = self.perturbation_gen.generate_candidates(
                    baseline_params, DEFAULT_TUNABLE_PARAMS, candidate_count
                )
            else:
                candidate_params_list = [
                    self.perturbation_gen.perturb(
                        baseline_params, DEFAULT_TUNABLE_PARAMS, "random", 0.15
                    )
                ]

        print(f"Running baseline evaluation...")
        baseline_eval_result = await self.run_eval(baseline_params, scenarios)
        baseline_fitness = FitnessCalculator.calculate_all(baseline_eval_result)

        print(f"Baseline fitness: composite={baseline_fitness.composite:.4f}")
        print(f"  - recovery_score: {baseline_fitness.recovery_score:.4f}")
        print(f"  - collapse_penalty: {baseline_fitness.collapse_penalty:.4f}")
        print(f"  - efficiency: {baseline_fitness.efficiency:.4f}")
        print(f"  - robustness: {baseline_fitness.robustness:.4f}")

        # Evaluate candidates
        candidates = []
        for i, candidate_params in enumerate(candidate_params_list):
            print(f"\nRunning candidate {i+1}/{len(candidate_params_list)}...")
            candidate_eval_result = await self.run_eval(candidate_params, scenarios)
            candidate_fitness = FitnessCalculator.calculate_all(candidate_eval_result)
            
            print(f"  Candidate {i+1} fitness: composite={candidate_fitness.composite:.4f}")
            
            candidate_result = CandidateResult(
                candidate_id=f"candidate_{i+1}",
                params=candidate_params,
                fitness=candidate_fitness,
                eval_result=result_to_dict(candidate_eval_result)
            )
            candidates.append(candidate_result)

        # Rank candidates by composite fitness
        candidates.sort(key=lambda c: c.fitness.composite, reverse=True)
        for i, c in enumerate(candidates):
            c.rank = i + 1

        # Find best candidate
        best_candidate = candidates[0] if candidates else None
        
        # Determine overall improvement
        overall_improvement = False
        if best_candidate:
            overall_improvement = best_candidate.fitness.composite > baseline_fitness.composite

        # Generate recommendations
        recommendations = self._generate_recommendations(
            baseline_fitness, candidates, baseline_params
        )

        # Create result
        result = AutoTuneResult(
            timestamp=datetime.now().isoformat(),
            seed=self.seed,
            baseline_params=baseline_params,
            baseline_fitness=baseline_fitness,
            baseline_result=result_to_dict(baseline_eval_result),
            candidates=candidates,
            best_candidate=best_candidate,
            overall_improvement=overall_improvement,
            recommendations=recommendations
        )

        return result

    def _generate_recommendations(self,
                                   baseline_fitness: FitnessMetrics,
                                   candidates: List[CandidateResult],
                                   baseline_params: Dict[str, float]) -> List[str]:
        """Generate tuning recommendations based on comparison"""
        recommendations = []

        if not candidates:
            recommendations.append("No candidates evaluated.")
            return recommendations

        best = candidates[0]
        
        # Check for significant improvements
        if best.fitness.composite > baseline_fitness.composite:
            improvement_pct = ((best.fitness.composite - baseline_fitness.composite) 
                              / baseline_fitness.composite * 100)
            recommendations.append(
                f"Best candidate shows {improvement_pct:+.1f}% improvement in composite fitness"
            )
        
        # Recovery score analysis
        if best.fitness.recovery_score > baseline_fitness.recovery_score:
            recommendations.append("Candidate improves recovery_score - better resilience to negative events")
        elif best.fitness.recovery_score < baseline_fitness.recovery_score:
            recommendations.append("Warning: Candidate has lower recovery_score - may be less resilient")
            
        # Collapse penalty analysis
        if best.fitness.collapse_penalty < baseline_fitness.collapse_penalty:
            recommendations.append("Candidate reduces collapse_penalty - better stability under stress")
        elif best.fitness.collapse_penalty > baseline_fitness.collapse_penalty:
            recommendations.append("Warning: Candidate has higher collapse_penalty - may collapse more easily")
            
        # Efficiency analysis
        if best.fitness.efficiency > baseline_fitness.efficiency:
            recommendations.append("Candidate improves efficiency - better resource utilization")
            
        # Robustness analysis
        if best.fitness.robustness > baseline_fitness.robustness:
            recommendations.append("Candidate improves robustness - more stable overall")

        # Parameter-specific recommendations
        param_changes = {}
        for param_name in baseline_params:
            if param_name in best.params:
                change = best.params[param_name] - baseline_params[param_name]
                if abs(change) > 0.05:
                    param_changes[param_name] = change
                    
        if param_changes:
            rec_lines = ["Key parameter changes in best candidate:"]
            for param, change in sorted(param_changes.items(), key=lambda x: abs(x[1]), reverse=True)[:5]:
                direction = "↑" if change > 0 else "↓"
                rec_lines.append(f"  - {param}: {direction} {abs(change):.4f}")
            recommendations.append("\n".join(rec_lines))

        if not recommendations:
            recommendations.append("No significant changes detected. Parameters are stable.")

        return recommendations

    def save_report(self, result: AutoTuneResult) -> Tuple[Path, Path]:
        """Save reports (JSON and Markdown)"""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        base_name = f"auto_tune_v0_2_{self.timestamp}"

        # Save JSON report
        json_path = self.output_dir / f"{base_name}.json"
        with open(json_path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2, default=str)

        # Save Markdown report
        md_path = self.output_dir / f"{base_name}.md"
        markdown = self._generate_markdown(result)
        with open(md_path, 'w') as f:
            f.write(markdown)

        result.report_path = str(json_path)

        return json_path, md_path

    def _generate_markdown(self, result: AutoTuneResult) -> str:
        """Generate Markdown report"""
        lines = [
            "# Auto-Tune v0.2 Report",
            "",
            f"**Generated:** {result.timestamp}",
            f"**Random Seed:** {result.seed}",
            f"**Overall Improvement:** {'Yes' if result.overall_improvement else 'No'}",
            "",
            "## Baseline Fitness",
            "",
            f"- **Composite:** {result.baseline_fitness.composite:.4f}",
            f"- **Recovery Score:** {result.baseline_fitness.recovery_score:.4f}",
            f"- **Collapse Penalty:** {result.baseline_fitness.collapse_penalty:.4f}",
            f"- **Efficiency:** {result.baseline_fitness.efficiency:.4f}",
            f"- **Emotion Consistency:** {result.baseline_fitness.emotion_consistency:.4f}",
            f"- **Robustness:** {result.baseline_fitness.robustness:.4f}",
            "",
            "## Candidate Rankings",
            "",
            "| Rank | Candidate | Composite | Recovery | Collapse | Efficiency | Robustness |",
            "|------|-----------|-----------|----------|----------|------------|------------|",
        ]

        for c in result.candidates:
            lines.append(
                f"| {c.rank} | {c.candidate_id} | "
                f"{c.fitness.composite:.4f} | "
                f"{c.fitness.recovery_score:.4f} | "
                f"{c.fitness.collapse_penalty:.4f} | "
                f"{c.fitness.efficiency:.4f} | "
                f"{c.fitness.robustness:.4f} |"
            )

        if result.best_candidate:
            best = result.best_candidate
            lines.extend([
                "",
                "## Best Candidate Details",
                "",
                f"**Candidate ID:** {best.candidate_id}",
                f"**Composite Fitness:** {best.fitness.composite:.4f}",
                "",
                "### Fitness Breakdown",
                f"- **Recovery Score:** {best.fitness.recovery_score:.4f}",
                f"- **Collapse Penalty:** {best.fitness.collapse_penalty:.4f}",
                f"- **Efficiency:** {best.fitness.efficiency:.4f}",
                f"- **Emotion Consistency:** {best.fitness.emotion_consistency:.4f}",
                f"- **Robustness:** {best.fitness.robustness:.4f}",
                "",
                "### Parameter Changes from Baseline",
                "",
                "| Parameter | Baseline | Candidate | Change |",
                "|-----------|----------|-----------|--------|",
            ])

            for param in sorted(best.params.keys()):
                base_val = result.baseline_params.get(param, "N/A")
                cand_val = best.params[param]
                if isinstance(base_val, (int, float)):
                    diff = f"{cand_val - base_val:+.4f}"
                else:
                    diff = "N/A"
                lines.append(f"| {param} | {base_val} | {cand_val:.4f} | {diff} |")

        lines.extend([
            "",
            "## Recommendations",
            "",
        ])

        for rec in result.recommendations:
            lines.append(f"- {rec}")

        lines.extend([
            "",
            "---",
            "*Generated by OpenEmotion Auto-Tune v0.2*",
        ])

        return "\n".join(lines)


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Auto-Tune v0.2 for OpenEmotion MVP-6"
    )
    parser.add_argument(
        "--params", "-p",
        type=Path,
        help="Parameter file (JSON/YAML) for candidate configuration"
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        help="Parameter file for baseline configuration"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("reports"),
        help="Output directory for reports"
    )
    parser.add_argument(
        "--scenarios", "-s",
        nargs="+",
        help="Specific scenario files to run"
    )
    parser.add_argument(
        "--candidates", "-n",
        type=int,
        default=10,
        help="Number of candidate perturbations to generate (default: 10)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)"
    )
    parser.add_argument(
        "--strategy",
        choices=["random", "gaussian", "boundary"],
        default="random",
        help="Perturbation strategy"
    )
    parser.add_argument(
        "--magnitude",
        type=float,
        default=0.2,
        help="Perturbation magnitude 0-1"
    )
    parser.add_argument(
        "--list-params",
        action="store_true",
        help="List all tunable parameters"
    )
    parser.add_argument(
        "--generate-defaults",
        type=Path,
        metavar="OUTPUT_FILE",
        help="Generate default parameters file"
    )

    args = parser.parse_args()

    if args.list_params:
        print("# Tunable Parameters (v0.2)")
        print("")
        for name, defn in sorted(DEFAULT_TUNABLE_PARAMS.items()):
            print(f"## {name}")
            print(f"- **Default:** {defn['default']}")
            print(f"- **Range:** [{defn['min']}, {defn['max']}]")
            print(f"- **Category:** {defn['category']}")
            print(f"- **Description:** {defn['description']}")
            print("")
        return 0

    if args.generate_defaults:
        defaults = {
            name: defn["default"]
            for name, defn in DEFAULT_TUNABLE_PARAMS.items()
        }
        metadata = {
            "description": "Default tunable parameters for OpenEmotion MVP-6",
            "generated": datetime.now().isoformat(),
            "version": "0.2"
        }
        ParameterLoader.save(defaults, args.generate_defaults, metadata)
        print(f"Default parameters written to: {args.generate_defaults}")
        return 0

    # Determine base path
    base_path = Path(__file__).parent.parent
    scenarios_dir = base_path / "scenarios"

    # Load parameters
    baseline_params = None
    if args.baseline:
        baseline_params = ParameterLoader.load(args.baseline)
        print(f"Loaded baseline parameters from: {args.baseline}")

    # Load or generate candidate parameters
    candidate_params_list = None
    if args.params:
        # Single candidate from file
        candidate_params = ParameterLoader.load(args.params)
        candidate_params_list = [candidate_params]
        print(f"Loaded candidate parameters from: {args.params}")

    # Determine scenarios
    scenarios = None
    if args.scenarios:
        scenarios = [
            Path(s) if Path(s).is_absolute() else scenarios_dir / s
            for s in args.scenarios
        ]

    # Create engine and run
    engine = AutoTuneEngine(
        scenarios_dir=scenarios_dir,
        output_dir=args.output,
        seed=args.seed
    )

    print(f"\nRunning Auto-Tune v0.2...")
    print(f"  Seed: {args.seed}")
    print(f"  Candidates: {args.candidates}")
    print(f"  Strategy: {args.strategy}")
    print(f"  Magnitude: {args.magnitude}")
    print(f"  Output: {args.output}")
    print("")

    # Run tuning
    result = await engine.tune(
        baseline_params=baseline_params,
        candidate_params_list=candidate_params_list,
        scenarios=scenarios,
        generate_candidates=(candidate_params_list is None),
        candidate_count=args.candidates
    )

    # Save reports
    json_path, md_path = engine.save_report(result)

    print(f"\nReports saved:")
    print(f"  JSON: {json_path}")
    print(f"  Markdown: {md_path}")
    print(f"\nBaseline Composite Fitness: {result.baseline_fitness.composite:.4f}")
    if result.best_candidate:
        print(f"Best Candidate Composite Fitness: {result.best_candidate.fitness.composite:.4f}")
    print(f"Overall: {'IMPROVED' if result.overall_improvement else 'NO IMPROVEMENT'}")

    # Return exit code
    return 0 if result.overall_improvement else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)