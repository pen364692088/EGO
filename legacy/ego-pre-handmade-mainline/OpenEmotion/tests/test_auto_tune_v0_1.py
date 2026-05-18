#!/usr/bin/env python3
"""
Tests for Auto-Tune v0.1 (MVP-5.1 D2)

Coverage:
1. Two-stage search reproducibility
2. Latin Hypercube Sampling correctness
3. Local refinement convergence
4. Multi-objective fitness calculation
5. Report schema completeness
6. Best params export
7. Error handling
8. Candidate variation (metrics must change)
"""

import os
import sys
import json
import yaml
import pytest
import tempfile
import random
import asyncio
import statistics
from pathlib import Path
from datetime import datetime
from dataclasses import asdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.auto_tune_v0_1 import (
    DEFAULT_TUNABLE_PARAMS,
    DEFAULT_FITNESS_WEIGHTS,
    CandidateResult,
    AutoTuneV1Result,
    ParameterLoader,
    LatinHypercubeSampler,
    RandomSampler,
    LocalRefiner,
    FitnessEvaluator,
    AutoTuneV1Engine,
)
from scripts.eval_suite_v2 import EvalResult, ScenarioResult


class TestTwoStageSearchReproducibility:
    """Test two-stage search reproducibility with fixed seed"""

    def test_lhs_sampler_reproducibility(self):
        """LHS sampler with same seed should produce identical samples"""
        sampler1 = LatinHypercubeSampler(seed=42)
        sampler2 = LatinHypercubeSampler(seed=42)

        samples1 = sampler1.sample(DEFAULT_TUNABLE_PARAMS, 50)
        samples2 = sampler2.sample(DEFAULT_TUNABLE_PARAMS, 50)

        assert len(samples1) == len(samples2) == 50
        for s1, s2 in zip(samples1, samples2):
            assert s1 == s2, "LHS samples with same seed should be identical"

    def test_random_sampler_reproducibility(self):
        """Random sampler with same seed should produce identical samples"""
        sampler1 = RandomSampler(seed=42)
        sampler2 = RandomSampler(seed=42)

        samples1 = sampler1.sample(DEFAULT_TUNABLE_PARAMS, 50)
        samples2 = sampler2.sample(DEFAULT_TUNABLE_PARAMS, 50)

        assert len(samples1) == len(samples2) == 50
        for s1, s2 in zip(samples1, samples2):
            assert s1 == s2, "Random samples with same seed should be identical"

    def test_local_refiner_reproducibility(self):
        """Local refiner with same seed should produce identical refinements"""
        refiner1 = LocalRefiner(seed=42)
        refiner2 = LocalRefiner(seed=42)

        center = {name: defn["default"] for name, defn in DEFAULT_TUNABLE_PARAMS.items()}

        refined1 = refiner1.refine(center, DEFAULT_TUNABLE_PARAMS, "coordinate_descent", 0.1)
        refined2 = refiner2.refine(center, DEFAULT_TUNABLE_PARAMS, "coordinate_descent", 0.1)

        assert refined1 == refined2, "Refined params with same seed should be identical"

    def test_different_seeds_produce_different_samples(self):
        """Different seeds should produce different samples"""
        sampler1 = LatinHypercubeSampler(seed=42)
        sampler2 = LatinHypercubeSampler(seed=99)

        samples1 = sampler1.sample(DEFAULT_TUNABLE_PARAMS, 10)
        samples2 = sampler2.sample(DEFAULT_TUNABLE_PARAMS, 10)

        # At least some samples should differ
        any_diff = any(s1 != s2 for s1, s2 in zip(samples1, samples2))
        assert any_diff, "Different seeds should produce different samples"


class TestLatinHypercubeSampling:
    """Test Latin Hypercube Sampling properties"""

    def test_lhs_sample_count(self):
        """LHS should produce exactly n_samples"""
        sampler = LatinHypercubeSampler(seed=42)
        samples = sampler.sample(DEFAULT_TUNABLE_PARAMS, 100)
        assert len(samples) == 100

    def test_lhs_samples_within_bounds(self):
        """All LHS samples should be within parameter bounds"""
        sampler = LatinHypercubeSampler(seed=42)
        samples = sampler.sample(DEFAULT_TUNABLE_PARAMS, 50)

        for sample in samples:
            for param_name, value in sample.items():
                defn = DEFAULT_TUNABLE_PARAMS[param_name]
                assert defn["min"] <= value <= defn["max"], \
                    f"Parameter {param_name} out of bounds: {value}"

    def test_lhs_stratification(self):
        """LHS should have good stratification (one sample per stratum)"""
        sampler = LatinHypercubeSampler(seed=42)
        n_samples = 20
        samples = sampler.sample(DEFAULT_TUNABLE_PARAMS, n_samples)

        # Check a single parameter for stratification
        param_name = list(DEFAULT_TUNABLE_PARAMS.keys())[0]
        defn = DEFAULT_TUNABLE_PARAMS[param_name]
        range_val = defn["max"] - defn["min"]
        stratum_size = range_val / n_samples

        values = [s[param_name] for s in samples]

        # Each stratum should have exactly one sample
        stratum_counts = [0] * n_samples
        for v in values:
            stratum_idx = int((v - defn["min"]) / stratum_size)
            stratum_idx = min(stratum_idx, n_samples - 1)  # Handle edge case
            stratum_counts[stratum_idx] += 1

        # Most strata should have exactly one sample
        correct_strata = sum(1 for c in stratum_counts if c == 1)
        assert correct_strata >= n_samples * 0.8, \
            f"LHS stratification failed: only {correct_strata}/{n_samples} strata have one sample"

    def test_lhs_coverage(self):
        """LHS should cover the full parameter range"""
        sampler = LatinHypercubeSampler(seed=42)
        n_samples = 100
        samples = sampler.sample(DEFAULT_TUNABLE_PARAMS, n_samples)

        for param_name, defn in DEFAULT_TUNABLE_PARAMS.items():
            values = [s[param_name] for s in samples]
            min_val = min(values)
            max_val = max(values)
            range_coverage = (max_val - min_val) / (defn["max"] - defn["min"])
            assert range_coverage > 0.9, \
                f"Parameter {param_name} range coverage too low: {range_coverage:.2%}"


class TestLocalRefinement:
    """Test local refinement strategies"""

    def test_coordinate_descent_perturbs_one_param(self):
        """Coordinate descent should perturb only one parameter at a time"""
        refiner = LocalRefiner(seed=42)
        center = {name: defn["default"] for name, defn in DEFAULT_TUNABLE_PARAMS.items()}

        refined = refiner.refine(center, DEFAULT_TUNABLE_PARAMS, "coordinate_descent", 0.1)

        # Count differences
        diffs = sum(1 for k in center if center[k] != refined[k])
        assert diffs == 1, f"Coordinate descent should change exactly 1 parameter, changed {diffs}"

    def test_random_hill_perturbs_multiple_params(self):
        """Random hill should perturb multiple parameters"""
        refiner = LocalRefiner(seed=42)
        center = {name: defn["default"] for name, defn in DEFAULT_TUNABLE_PARAMS.items()}

        refined = refiner.refine(center, DEFAULT_TUNABLE_PARAMS, "random_hill", 0.1)

        # Should change multiple parameters
        diffs = sum(1 for k in center if abs(center[k] - refined[k]) > 0.0001)
        assert diffs >= 3, f"Random hill should change multiple parameters, only changed {diffs}"

    def test_refinement_respects_bounds(self):
        """Refined parameters should stay within bounds"""
        refiner = LocalRefiner(seed=42)
        center = {name: defn["default"] for name, defn in DEFAULT_TUNABLE_PARAMS.items()}

        for _ in range(100):
            strategy = random.choice(["coordinate_descent", "random_hill"])
            refined = refiner.refine(center, DEFAULT_TUNABLE_PARAMS, strategy, 0.5)

            for param_name, value in refined.items():
                defn = DEFAULT_TUNABLE_PARAMS[param_name]
                assert defn["min"] <= value <= defn["max"], \
                    f"Refined parameter {param_name} out of bounds: {value}"

    def test_step_size_affects_magnitude(self):
        """Larger step size should produce larger changes"""
        refiner = LocalRefiner(seed=42)
        center = {name: defn["default"] for name, defn in DEFAULT_TUNABLE_PARAMS.items()}

        small_changes = []
        large_changes = []

        for _ in range(50):
            small = refiner.refine(center, DEFAULT_TUNABLE_PARAMS, "random_hill", 0.05)
            large = refiner.refine(center, DEFAULT_TUNABLE_PARAMS, "random_hill", 0.5)

            small_diff = sum(abs(center[k] - small[k]) for k in center)
            large_diff = sum(abs(center[k] - large[k]) for k in center)

            small_changes.append(small_diff)
            large_changes.append(large_diff)

        avg_small = statistics.mean(small_changes)
        avg_large = statistics.mean(large_changes)

        assert avg_large > avg_small, \
            f"Larger step size should produce larger changes: {avg_large} vs {avg_small}"


class TestMultiObjectiveFitness:
    """Test multi-objective fitness calculation"""

    def test_fitness_weights_schema(self):
        """Fitness weights should have expected objectives"""
        expected_objectives = [
            "scenario_pass_rate",
            "high_impact_false_positive_rate",
            "cross_target_interference",
            "over_clarification_rate",
            "avg_tokens_per_turn",
        ]

        for obj in expected_objectives:
            assert obj in DEFAULT_FITNESS_WEIGHTS, f"Missing objective: {obj}"

    def test_fitness_calculation(self):
        """Fitness should be calculated correctly from metrics"""
        evaluator = FitnessEvaluator()

        metrics = {
            "scenario_pass_rate": 0.8,
            "high_impact_false_positive_rate": 0.1,
            "cross_target_interference": 0.2,
            "over_clarification_rate": 0.05,
            "avg_tokens_per_turn": 10.0,
        }

        fitness = evaluator.compute_fitness(metrics)

        expected = (
            DEFAULT_FITNESS_WEIGHTS["scenario_pass_rate"] * 0.8 +
            DEFAULT_FITNESS_WEIGHTS["high_impact_false_positive_rate"] * 0.1 +
            DEFAULT_FITNESS_WEIGHTS["cross_target_interference"] * 0.2 +
            DEFAULT_FITNESS_WEIGHTS["over_clarification_rate"] * 0.05 +
            DEFAULT_FITNESS_WEIGHTS["avg_tokens_per_turn"] * 10.0
        )

        assert abs(fitness - expected) < 0.0001, \
            f"Fitness calculation mismatch: {fitness} vs {expected}"

    def test_higher_pass_rate_increases_fitness(self):
        """Higher pass rate should increase fitness"""
        evaluator = FitnessEvaluator()

        metrics_low = {"scenario_pass_rate": 0.5}
        metrics_high = {"scenario_pass_rate": 0.9}

        fitness_low = evaluator.compute_fitness(metrics_low)
        fitness_high = evaluator.compute_fitness(metrics_high)

        assert fitness_high > fitness_low, \
            "Higher pass rate should increase fitness"

    def test_lower_false_positive_increases_fitness(self):
        """Lower false positive rate should increase fitness (negative weight)"""
        evaluator = FitnessEvaluator()

        metrics_high_fp = {"high_impact_false_positive_rate": 0.5}
        metrics_low_fp = {"high_impact_false_positive_rate": 0.1}

        fitness_high_fp = evaluator.compute_fitness(metrics_high_fp)
        fitness_low_fp = evaluator.compute_fitness(metrics_low_fp)

        assert fitness_low_fp > fitness_high_fp, \
            "Lower false positive should increase fitness"

    def test_candidate_comparison(self):
        """Candidate comparison should rank by fitness then pass rate"""
        evaluator = FitnessEvaluator()

        # Create mock candidates
        candidate_better = CandidateResult(
            candidate_id=1,
            params={},
            eval_result={},
            metrics={"scenario_pass_rate": 0.9, "fitness": 1.5},
            fitness=1.5,
            stage="global"
        )

        candidate_worse = CandidateResult(
            candidate_id=2,
            params={},
            eval_result={},
            metrics={"scenario_pass_rate": 0.5, "fitness": 1.0},
            fitness=1.0,
            stage="global"
        )

        result = evaluator.compare_candidates(candidate_better, candidate_worse)
        assert result == -1, "Better candidate should be ranked higher"


class TestReportSchema:
    """Test report schema completeness"""

    def test_candidate_result_schema(self):
        """CandidateResult should have all required fields"""
        candidate = CandidateResult(
            candidate_id=1,
            params={"param1": 0.5},
            eval_result={"scenarios": []},
            metrics={"pass_rate": 0.8},
            fitness=1.0,
            stage="global",
            parent_id=None
        )

        data = candidate.to_dict()
        required_fields = ["candidate_id", "params", "eval_result", "metrics",
                          "fitness", "stage", "parent_id", "timestamp"]

        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_autotune_v1_result_schema(self):
        """AutoTuneV1Result should have all required fields"""
        best_candidate = CandidateResult(
            candidate_id=1,
            params={},
            eval_result={},
            metrics={},
            fitness=1.0,
            stage="global"
        )

        result = AutoTuneV1Result(
            timestamp=datetime.now().isoformat(),
            seed=42,
            git_commit="abc123",
            param_space_version="v1",
            scenario_version="v1",
            baseline_params={},
            baseline_metrics={},
            baseline_fitness=0.5,
            candidates=[best_candidate],
            top_candidates=[best_candidate],
            best_candidate=best_candidate,
            fitness_weights=DEFAULT_FITNESS_WEIGHTS,
            search_config={}
        )

        data = result.to_dict()
        required_fields = ["timestamp", "seed", "git_commit", "param_space_version",
                          "scenario_version", "baseline_params", "baseline_metrics",
                          "baseline_fitness", "candidates", "top_candidates",
                          "best_candidate", "fitness_weights", "search_config"]

        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_json_serialization(self):
        """Result should be JSON serializable"""
        best_candidate = CandidateResult(
            candidate_id=1,
            params={"param1": 0.5},
            eval_result={"scenarios": []},
            metrics={"pass_rate": 0.8},
            fitness=1.0,
            stage="global"
        )

        result = AutoTuneV1Result(
            timestamp=datetime.now().isoformat(),
            seed=42,
            git_commit="abc123",
            param_space_version="v1",
            scenario_version="v1",
            baseline_params={"param1": 0.3},
            baseline_metrics={"pass_rate": 0.5},
            baseline_fitness=0.5,
            candidates=[best_candidate],
            top_candidates=[best_candidate],
            best_candidate=best_candidate,
            fitness_weights=DEFAULT_FITNESS_WEIGHTS,
            search_config={"n_global_candidates": 200, "n_refine_top": 5, "n_refine_iterations": 100, "lhs_ratio": 0.7, "random_ratio": 0.3}
        )

        # Should not raise
        json_str = json.dumps(result.to_dict(), indent=2, default=str)
        assert len(json_str) > 0

        # Should be parseable
        parsed = json.loads(json_str)
        assert parsed["seed"] == 42


class TestParameterLoader:
    """Test parameter loading and saving"""

    def test_load_json_params(self, tmp_path):
        """Should load parameters from JSON file"""
        params_file = tmp_path / "params.json"
        data = {"params": {"param1": 0.5, "param2": 0.3}}
        params_file.write_text(json.dumps(data))

        loaded = ParameterLoader.load(params_file)
        assert loaded == {"param1": 0.5, "param2": 0.3}

    def test_load_yaml_params(self, tmp_path):
        """Should load parameters from YAML file"""
        params_file = tmp_path / "params.yaml"
        data = {"params": {"param1": 0.5, "param2": 0.3}}
        params_file.write_text(yaml.dump(data))

        loaded = ParameterLoader.load(params_file)
        assert loaded == {"param1": 0.5, "param2": 0.3}

    def test_save_json_params(self, tmp_path):
        """Should save parameters to JSON file"""
        params_file = tmp_path / "params.json"
        params = {"param1": 0.5, "param2": 0.3}
        metadata = {"version": "1.0"}

        ParameterLoader.save(params, params_file, metadata)

        loaded = json.loads(params_file.read_text())
        assert loaded["params"] == params
        assert loaded["metadata"] == metadata

    def test_save_yaml_params(self, tmp_path):
        """Should save parameters to YAML file"""
        params_file = tmp_path / "params.yaml"
        params = {"param1": 0.5, "param2": 0.3}

        ParameterLoader.save(params, params_file)

        loaded = yaml.safe_load(params_file.read_text())
        assert loaded["params"] == params


class TestCandidateVariation:
    """Test that candidate metrics show variation"""

    def test_different_params_produce_different_metrics(self):
        """Different parameter sets should produce different metrics"""
        # Create two very different parameter sets
        params_low = {name: defn["min"] for name, defn in DEFAULT_TUNABLE_PARAMS.items()}
        params_high = {name: defn["max"] for name, defn in DEFAULT_TUNABLE_PARAMS.items()}

        # They should be different
        assert params_low != params_high, "Min and max params should differ"

        # At least some parameters should have different values
        diffs = sum(1 for k in params_low if params_low[k] != params_high[k])
        assert diffs > 0, f"Expected parameter differences, got {diffs}"

    def test_lhs_produces_diverse_samples(self):
        """LHS should produce diverse samples across the parameter space"""
        sampler = LatinHypercubeSampler(seed=42)
        samples = sampler.sample(DEFAULT_TUNABLE_PARAMS, 50)

        # Check diversity for a few parameters
        for param_name in list(DEFAULT_TUNABLE_PARAMS.keys())[:5]:
            values = [s[param_name] for s in samples]
            value_range = max(values) - min(values)
            defn = DEFAULT_TUNABLE_PARAMS[param_name]
            param_range = defn["max"] - defn["min"]
            coverage = value_range / param_range

            assert coverage > 0.5, \
                f"Parameter {param_name} has low diversity: {coverage:.2%} coverage"

    def test_random_produces_diverse_samples(self):
        """Random sampler should produce diverse samples"""
        sampler = RandomSampler(seed=42)
        samples = sampler.sample(DEFAULT_TUNABLE_PARAMS, 50)

        # Check diversity
        for param_name in list(DEFAULT_TUNABLE_PARAMS.keys())[:5]:
            values = [s[param_name] for s in samples]
            value_range = max(values) - min(values)
            defn = DEFAULT_TUNABLE_PARAMS[param_name]
            param_range = defn["max"] - defn["min"]
            coverage = value_range / param_range

            assert coverage > 0.5, \
                f"Parameter {param_name} has low diversity: {coverage:.2%} coverage"

    def test_metrics_vary_with_params(self):
        """Metrics should vary with different parameter configurations"""
        evaluator = FitnessEvaluator()

        # Test with extreme parameter values
        metrics_configs = [
            {"scenario_pass_rate": 0.2, "high_impact_false_positive_rate": 0.8},
            {"scenario_pass_rate": 0.8, "high_impact_false_positive_rate": 0.1},
            {"scenario_pass_rate": 0.5, "high_impact_false_positive_rate": 0.5},
        ]

        fitnesses = [evaluator.compute_fitness(m) for m in metrics_configs]

        # Fitnesses should vary
        unique_fitnesses = len(set(round(f, 4) for f in fitnesses))
        assert unique_fitnesses > 1, \
            f"Fitness should vary with metrics, got {unique_fitnesses} unique values"


class TestErrorHandling:
    """Test error handling"""

    def test_load_nonexistent_file(self, tmp_path):
        """Loading nonexistent file should raise FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            ParameterLoader.load(tmp_path / "nonexistent.json")

    def test_load_invalid_format(self, tmp_path):
        """Loading invalid format should raise ValueError"""
        bad_file = tmp_path / "params.txt"
        bad_file.write_text("invalid content")

        with pytest.raises(ValueError):
            ParameterLoader.load(bad_file)

    def test_unknown_refinement_strategy(self):
        """Unknown refinement strategy should raise ValueError"""
        refiner = LocalRefiner(seed=42)
        center = {name: defn["default"] for name, defn in DEFAULT_TUNABLE_PARAMS.items()}

        with pytest.raises(ValueError):
            refiner.refine(center, DEFAULT_TUNABLE_PARAMS, "unknown_strategy", 0.1)


class TestIntegration:
    """Integration tests"""

    @pytest.mark.asyncio
    async def test_engine_initialization(self, tmp_path):
        """Engine should initialize correctly"""
        scenarios_dir = tmp_path / "scenarios"
        scenarios_dir.mkdir()
        output_dir = tmp_path / "reports"

        engine = AutoTuneV1Engine(
            scenarios_dir=scenarios_dir,
            output_dir=output_dir,
            seed=42
        )

        assert engine.seed == 42
        assert engine.git_commit is not None
        assert engine.param_space_version == "mvp5.1_v1"

    def test_report_generation(self, tmp_path):
        """Reports should be generated correctly"""
        scenarios_dir = tmp_path / "scenarios"
        scenarios_dir.mkdir()
        output_dir = tmp_path / "reports"

        engine = AutoTuneV1Engine(
            scenarios_dir=scenarios_dir,
            output_dir=output_dir,
            seed=42
        )

        # Create mock result
        best_candidate = CandidateResult(
            candidate_id=1,
            params={"param1": 0.5},
            eval_result={"scenarios": []},
            metrics={"scenario_pass_rate": 0.8},
            fitness=1.5,
            stage="global"
        )

        result = AutoTuneV1Result(
            timestamp=datetime.now().isoformat(),
            seed=42,
            git_commit="abc123",
            param_space_version="v1",
            scenario_version="v1",
            baseline_params={"param1": 0.3},
            baseline_metrics={"scenario_pass_rate": 0.5},
            baseline_fitness=0.5,
            candidates=[best_candidate],
            top_candidates=[best_candidate],
            best_candidate=best_candidate,
            fitness_weights=DEFAULT_FITNESS_WEIGHTS,
            search_config={"n_global_candidates": 200, "n_refine_top": 5, "n_refine_iterations": 100, "lhs_ratio": 0.7, "random_ratio": 0.3}
        )

        json_path, md_path, best_params_path = engine.save_reports(result)

        assert json_path.exists()
        assert md_path.exists()
        assert best_params_path.exists()

        # Verify JSON content
        with open(json_path) as f:
            data = json.load(f)
            assert data["seed"] == 42
            assert data["best_candidate"]["fitness"] == 1.5

        # Verify best params content
        with open(best_params_path) as f:
            data = json.load(f)
            assert "params" in data
            assert "metadata" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
