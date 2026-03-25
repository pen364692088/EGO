#!/usr/bin/env python3
"""
Auto-Tune v0 for OpenEmotion MVP-5

Controlled self-evolution through parameter tuning only.
No automatic logic rewrites - only parameter adjustments.

Usage:
    python scripts/auto_tune_v0.py --params params.yaml --output reports/
    python scripts/auto_tune_v0.py --params params.json --perturbations 3 --seed 42

Features:
- Input: Tunable parameters (JSON/YAML)
- Run: eval_suite_v2 on baseline and candidate configurations
- Output: JSON report + Markdown summary with metric comparisons
- Reproducible: Fixed random seed support
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

# Import eval_suite_v2 components
from scripts.eval_suite_v2 import (
    EvalSuiteV2, ScenarioRunner, EvalResult, ScenarioResult,
    result_to_dict, TEST_SYSTEM_TOKEN, TEST_OPENCLAW_TOKEN
)
from emotiond import config, db, core


# Default tunable parameters and their ranges
DEFAULT_TUNABLE_PARAMS = {
    # Precision controller parameters (MVP-5 D1)
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

    # Allostasis budget parameters (MVP-5 D2)
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

    # Intrinsic motivation parameters (MVP-5 D3)
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

    # Self-model parameters (MVP-5 D4)
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
class MetricComparison:
    """Comparison of a metric between baseline and candidate"""
    metric_name: str
    baseline_value: float
    candidate_value: float
    absolute_diff: float
    relative_diff_percent: float
    improvement: bool
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "baseline_value": self.baseline_value,
            "candidate_value": self.candidate_value,
            "absolute_diff": self.absolute_diff,
            "relative_diff_percent": self.relative_diff_percent,
            "improvement": self.improvement,
            "description": self.description
        }


@dataclass
class AutoTuneResult:
    """Complete auto-tune result"""
    timestamp: str
    seed: int
    baseline_params: Dict[str, Any]
    candidate_params: Dict[str, Any]
    baseline_result: Dict[str, Any]
    candidate_result: Dict[str, Any]
    metric_comparisons: List[MetricComparison]
    overall_improvement: bool
    recommendations: List[str]
    report_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "seed": self.seed,
            "baseline_params": self.baseline_params,
            "candidate_params": self.candidate_params,
            "baseline_result": self.baseline_result,
            "candidate_result": self.candidate_result,
            "metric_comparisons": [m.to_dict() for m in self.metric_comparisons],
            "overall_improvement": self.overall_improvement,
            "recommendations": self.recommendations,
            "report_path": self.report_path
        }


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

        # Extract just the parameter values
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
        """
        Generate perturbed parameters.

        Args:
            params: Base parameters
            param_defs: Parameter definitions with min/max
            strategy: "random", "gaussian", or "boundary"
            magnitude: Perturbation magnitude (0-1)

        Returns:
            Perturbed parameter set
        """
        perturbed = copy.deepcopy(params)

        for name, value in perturbed.items():
            if name not in param_defs:
                continue

            definition = param_defs[name]
            min_val = definition.get("min", value * 0.5)
            max_val = definition.get("max", value * 1.5)
            range_val = max_val - min_val

            if strategy == "random":
                # Uniform random perturbation
                delta = self.rng.uniform(-1, 1) * magnitude * range_val
                new_value = value + delta
            elif strategy == "gaussian":
                # Gaussian perturbation
                std = magnitude * range_val / 3  # 3 sigma covers 99.7%
                delta = self.rng.gauss(0, std)
                new_value = value + delta
            elif strategy == "boundary":
                # Push toward boundaries
                if self.rng.random() < 0.5:
                    new_value = min_val + magnitude * range_val * self.rng.random()
                else:
                    new_value = max_val - magnitude * range_val * self.rng.random()
            else:
                raise ValueError(f"Unknown strategy: {strategy}")

            # Clamp to valid range
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
            magnitude = 0.1 + (i * 0.1)  # Increasing perturbation
            candidate = self.perturb(baseline, param_defs, strategy, magnitude)
            candidates.append(candidate)

        return candidates


class MetricExtractor:
    """Extract and compare metrics from eval results"""

    # Metrics to track for MVP-5
    TRACKED_METRICS = {
        # Existing metrics
        "emotion_consistency": {
            "path": ["emotion_consistency", "pass_rate"],
            "higher_is_better": True,
            "description": "Consistency of emotional responses across runs"
        },
        "individualization_diff": {
            "path": ["individualization_diff", "average"],
            "higher_is_better": True,
            "description": "Differentiation between different targets"
        },
        "high_impact_false_positive_rate": {
            "path": ["high_impact_false_positive_rate", "average"],
            "higher_is_better": False,
            "description": "Rate of false positives on high-impact events"
        },
        "meta_cognition_trigger_rate": {
            "path": ["meta_cognition_trigger_rate", "average"],
            "higher_is_better": None,  # Context-dependent
            "description": "Rate of meta-cognition triggers"
        },

        # MVP-5 new metrics
        "clarification_trigger_rate": {
            "path": ["meta_cognition_trigger_rate", "average"],  # Approximation
            "higher_is_better": None,
            "description": "Rate of clarification triggers"
        },
        "emotion_consistency_cross_run": {
            "path": ["emotion_consistency", "pass_rate"],
            "higher_is_better": True,
            "description": "Cross-run emotion consistency"
        },
        "cross_target_interference": {
            "path": ["individualization_diff", "max"],
            "higher_is_better": False,  # Lower interference is better
            "description": "Cross-target emotional interference"
        },
        "avg_tokens_per_turn": {
            "path": None,  # Will be calculated separately
            "higher_is_better": None,
            "description": "Average tokens per turn (approximated from turn count)"
        },
        "scenario_pass_rate": {
            "path": None,  # Calculated from scenarios
            "higher_is_better": True,
            "description": "Percentage of scenarios passing"
        },
    }

    @classmethod
    def extract(cls, eval_result: EvalResult) -> Dict[str, float]:
        """Extract metrics from eval result"""
        metrics = {}
        aggregate = eval_result.aggregate_metrics

        for metric_name, config in cls.TRACKED_METRICS.items():
            if config["path"] is None:
                # Calculate special metrics
                if metric_name == "scenario_pass_rate":
                    total = eval_result.total_scenarios
                    passed = eval_result.passed_scenarios
                    metrics[metric_name] = passed / total if total > 0 else 0.0
                elif metric_name == "avg_tokens_per_turn":
                    # Approximate: average turns per scenario
                    total_turns = sum(len(s.turns) for s in eval_result.scenarios)
                    total_scenarios = eval_result.total_scenarios
                    metrics[metric_name] = total_turns / total_scenarios if total_scenarios > 0 else 0.0
                continue

            # Navigate path
            value = aggregate
            for key in config["path"]:
                if isinstance(value, dict):
                    value = value.get(key, 0.0)
                else:
                    value = 0.0
                    break

            metrics[metric_name] = value

        return metrics

    @classmethod
    def compare(cls, baseline: Dict[str, float],
                candidate: Dict[str, float]) -> List[MetricComparison]:
        """Compare metrics between baseline and candidate"""
        comparisons = []

        all_metrics = set(baseline.keys()) | set(candidate.keys())

        for metric_name in all_metrics:
            base_val = baseline.get(metric_name, 0.0)
            cand_val = candidate.get(metric_name, 0.0)

            abs_diff = cand_val - base_val
            rel_diff = (abs_diff / base_val * 100) if base_val != 0 else 0.0

            # Determine if this is an improvement
            config = cls.TRACKED_METRICS.get(metric_name, {})
            higher_is_better = config.get("higher_is_better")

            if higher_is_better is True:
                improvement = abs_diff > 0
            elif higher_is_better is False:
                improvement = abs_diff < 0
            else:
                improvement = abs(abs_diff) < 0.1  # Small change is neutral/good

            comparison = MetricComparison(
                metric_name=metric_name,
                baseline_value=base_val,
                candidate_value=cand_val,
                absolute_diff=abs_diff,
                relative_diff_percent=rel_diff,
                improvement=improvement,
                description=config.get("description", "")
            )
            comparisons.append(comparison)

        return comparisons


class AutoTuneEngine:
    """Main auto-tuning engine"""

    def __init__(self, scenarios_dir: Path, output_dir: Path, seed: int = 42):
        self.scenarios_dir = scenarios_dir
        self.output_dir = output_dir
        self.seed = seed
        self.perturbation_gen = PerturbationGenerator(seed)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def apply_parameters(self, params: Dict[str, float]):
        """Apply parameters to the emotiond configuration"""
        # This modifies the config module's values
        # Note: These are applied to the current process only

        # Precision parameters
        if "precision_temperature" in params:
            # Store in core for precision calculations
            core._auto_tune_params = getattr(core, '_auto_tune_params', {})
            core._auto_tune_params['precision_temperature'] = params["precision_temperature"]

        # Allostasis parameters
        if "energy_recovery_rate" in params:
            core._auto_tune_params = getattr(core, '_auto_tune_params', {})
            core._auto_tune_params['energy_recovery_rate'] = params["energy_recovery_rate"]

        # Meta-cognition parameters
        if "clarification_trigger_threshold" in params:
            core._auto_tune_params = getattr(core, '_auto_tune_params', {})
            core._auto_tune_params['clarification_trigger_threshold'] = params["clarification_trigger_threshold"]

        if "reflection_trigger_threshold" in params:
            core._auto_tune_params = getattr(core, '_auto_tune_params', {})
            core._auto_tune_params['reflection_trigger_threshold'] = params["reflection_trigger_threshold"]

        # Store full params for reference
        core._auto_tune_params = getattr(core, '_auto_tune_params', {})
        core._auto_tune_params.update(params)

    async def run_eval(self, params: Dict[str, float],
                      scenarios: Optional[List[Path]] = None) -> EvalResult:
        """Run eval suite with given parameters"""
        # Apply parameters
        self.apply_parameters(params)

        # Create eval suite
        suite = EvalSuiteV2(
            scenarios_dir=self.scenarios_dir,
            output_format="json"
        )

        # Run evaluation
        result = await suite.run_all(scenarios)
        return result

    async def tune(self,
                   baseline_params: Optional[Dict[str, float]] = None,
                   candidate_params: Optional[Dict[str, float]] = None,
                   scenarios: Optional[List[Path]] = None,
                   generate_candidates: bool = False,
                   candidate_count: int = 1) -> AutoTuneResult:
        """
        Run auto-tuning comparison.

        Args:
            baseline_params: Baseline parameters (uses defaults if None)
            candidate_params: Specific candidate parameters (generates if None)
            scenarios: Specific scenarios to run (all if None)
            generate_candidates: Whether to generate candidate perturbations
            candidate_count: Number of candidates to generate

        Returns:
            AutoTuneResult with comparison
        """
        # Use default parameters if not provided
        if baseline_params is None:
            baseline_params = {
                name: defn["default"]
                for name, defn in DEFAULT_TUNABLE_PARAMS.items()
            }

        # Generate or use candidate
        if candidate_params is None:
            if generate_candidates:
                candidates = self.perturbation_gen.generate_candidates(
                    baseline_params, DEFAULT_TUNABLE_PARAMS, candidate_count
                )
                candidate_params = candidates[0]  # Use first candidate
            else:
                # Create a simple perturbation
                candidate_params = self.perturbation_gen.perturb(
                    baseline_params, DEFAULT_TUNABLE_PARAMS, "random", 0.15
                )

        print(f"Running baseline evaluation...")
        baseline_result = await self.run_eval(baseline_params, scenarios)

        print(f"Running candidate evaluation...")
        candidate_result = await self.run_eval(candidate_params, scenarios)

        # Extract metrics
        baseline_metrics = MetricExtractor.extract(baseline_result)
        candidate_metrics = MetricExtractor.extract(candidate_result)

        # Compare
        comparisons = MetricExtractor.compare(baseline_metrics, candidate_metrics)

        # Determine overall improvement
        improvements = sum(1 for c in comparisons if c.improvement)
        regressions = sum(1 for c in comparisons if not c.improvement)
        overall_improvement = improvements > regressions

        # Generate recommendations
        recommendations = self._generate_recommendations(comparisons, candidate_params)

        # Create result
        result = AutoTuneResult(
            timestamp=datetime.now().isoformat(),
            seed=self.seed,
            baseline_params=baseline_params,
            candidate_params=candidate_params,
            baseline_result=result_to_dict(baseline_result),
            candidate_result=result_to_dict(candidate_result),
            metric_comparisons=comparisons,
            overall_improvement=overall_improvement,
            recommendations=recommendations
        )

        return result

    def _generate_recommendations(self,
                                   comparisons: List[MetricComparison],
                                   candidate_params: Dict[str, float]) -> List[str]:
        """Generate tuning recommendations based on comparison"""
        recommendations = []

        # Check for significant improvements
        significant_improvements = [
            c for c in comparisons
            if c.improvement and abs(c.relative_diff_percent) > 10
        ]

        significant_regressions = [
            c for c in comparisons
            if not c.improvement and abs(c.relative_diff_percent) > 10
        ]

        if significant_improvements:
            rec = "Significant improvements in: " + ", ".join(
                c.metric_name for c in significant_improvements[:3]
            )
            recommendations.append(rec)

        if significant_regressions:
            rec = "Significant regressions in: " + ", ".join(
                c.metric_name for c in significant_regressions[:3]
            )
            recommendations.append(rec)

        # Parameter-specific recommendations
        if "precision_temperature" in candidate_params:
            temp = candidate_params["precision_temperature"]
            if temp < 0.3:
                recommendations.append(
                    "Low precision_temperature may cause over-confident decisions"
                )
            elif temp > 0.7:
                recommendations.append(
                    "High precision_temperature may cause excessive clarification"
                )

        if "energy_recovery_rate" in candidate_params:
            rate = candidate_params["energy_recovery_rate"]
            if rate > 0.005:
                recommendations.append(
                    "High energy_recovery_rate may mask genuine fatigue signals"
                )

        if not recommendations:
            recommendations.append("No significant changes detected. Parameters are stable.")

        return recommendations

    def save_report(self, result: AutoTuneResult) -> Tuple[Path, Path]:
        """Save reports (JSON and Markdown)"""
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename base
        base_name = f"auto_tune_{self.timestamp}"

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
            "# Auto-Tune v0 Report",
            "",
            f"**Generated:** {result.timestamp}",
            f"**Random Seed:** {result.seed}",
            f"**Overall Improvement:** {'Yes' if result.overall_improvement else 'No'}",
            "",
            "## Summary",
            "",
            f"- Baseline scenarios passed: {result.baseline_result.get('passed_scenarios', 0)}/{result.baseline_result.get('total_scenarios', 0)}",
            f"- Candidate scenarios passed: {result.candidate_result.get('passed_scenarios', 0)}/{result.candidate_result.get('total_scenarios', 0)}",
            "",
            "## Metric Comparisons",
            "",
            "| Metric | Baseline | Candidate | Diff | Change | Status |",
            "|--------|----------|-----------|------|--------|--------|",
        ]

        for comp in result.metric_comparisons:
            status = "OK" if comp.improvement else "REG"
            change = f"{comp.relative_diff_percent:+.1f}%"
            lines.append(
                f"| {comp.metric_name} | {comp.baseline_value:.4f} | "
                f"{comp.candidate_value:.4f} | {comp.absolute_diff:+.4f} | "
                f"{change} | {status} |"
            )

        lines.extend([
            "",
            "## Parameter Changes",
            "",
            "| Parameter | Baseline | Candidate | Change |",
            "|-----------|----------|-----------|--------|",
        ])

        baseline = result.baseline_params
        candidate = result.candidate_params
        all_params = set(baseline.keys()) | set(candidate.keys())

        for param in sorted(all_params):
            base_val = baseline.get(param, "N/A")
            cand_val = candidate.get(param, "N/A")
            if isinstance(base_val, (int, float)) and isinstance(cand_val, (int, float)):
                diff = f"{cand_val - base_val:+.4f}"
            else:
                diff = "N/A"
            lines.append(f"| {param} | {base_val} | {cand_val} | {diff} |")

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
            "*Generated by OpenEmotion Auto-Tune v0*",
        ])

        return "\n".join(lines)


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Auto-Tune v0 for OpenEmotion MVP-5"
    )
    parser.add_argument(
        "--params", "-p",
        type=Path,
        help="Parameter file (JSON/YAML) for candidate configuration"
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        help="Parameter file for baseline configuration (uses defaults if not specified)"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("reports"),
        help="Output directory for reports (default: reports/)"
    )
    parser.add_argument(
        "--scenarios", "-s",
        nargs="+",
        help="Specific scenario files to run"
    )
    parser.add_argument(
        "--perturbations", "-n",
        type=int,
        default=1,
        help="Number of candidate perturbations to generate (default: 1)"
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
        help="Perturbation strategy (default: random)"
    )
    parser.add_argument(
        "--magnitude",
        type=float,
        default=0.2,
        help="Perturbation magnitude 0-1 (default: 0.2)"
    )
    parser.add_argument(
        "--list-params",
        action="store_true",
        help="List all tunable parameters and exit"
    )
    parser.add_argument(
        "--generate-defaults",
        type=Path,
        metavar="OUTPUT_FILE",
        help="Generate default parameters file and exit"
    )

    args = parser.parse_args()

    # List parameters mode
    if args.list_params:
        print("# Tunable Parameters")
        print("")
        for name, defn in sorted(DEFAULT_TUNABLE_PARAMS.items()):
            print(f"## {name}")
            print(f"- **Default:** {defn['default']}")
            print(f"- **Range:** [{defn['min']}, {defn['max']}]")
            print(f"- **Category:** {defn['category']}")
            print(f"- **Description:** {defn['description']}")
            print("")
        return 0

    # Generate defaults mode
    if args.generate_defaults:
        defaults = {
            name: defn["default"]
            for name, defn in DEFAULT_TUNABLE_PARAMS.items()
        }
        metadata = {
            "description": "Default tunable parameters for OpenEmotion MVP-5",
            "generated": datetime.now().isoformat(),
            "version": "1.0"
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

    candidate_params = None
    if args.params:
        candidate_params = ParameterLoader.load(args.params)
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

    print(f"\nRunning Auto-Tune v0...")
    print(f"  Seed: {args.seed}")
    print(f"  Strategy: {args.strategy}")
    print(f"  Magnitude: {args.magnitude}")
    print(f"  Output: {args.output}")
    print("")

    # Run tuning
    result = await engine.tune(
        baseline_params=baseline_params,
        candidate_params=candidate_params,
        scenarios=scenarios,
        generate_candidates=(candidate_params is None),
        candidate_count=args.perturbations
    )

    # Save reports
    json_path, md_path = engine.save_report(result)

    print(f"\nReports saved:")
    print(f"  JSON: {json_path}")
    print(f"  Markdown: {md_path}")
    print(f"\nOverall: {'IMPROVED' if result.overall_improvement else 'REGRESSED/UNCHANGED'}")

    # Return exit code
    return 0 if result.overall_improvement else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)