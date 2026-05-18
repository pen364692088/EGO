#!/usr/bin/env python3
"""
Tests for Auto-Tune v0.2 (MVP-6)

Coverage:
1. Fitness metrics calculation (recovery_score, collapse_penalty, efficiency)
2. Candidate ranking and selection
3. Parameter perturbation with seed reproducibility
4. Report generation
5. Parameter coverage (all tunable params)
6. Integration with eval_suite_v2_2
"""

import os
import sys
import json
import yaml
import pytest
import asyncio
import tempfile
import random
from pathlib import Path
from datetime import datetime
from dataclasses import asdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.auto_tune_v0_2 import (
    DEFAULT_TUNABLE_PARAMS,
    ParameterSet,
    FitnessMetrics,
    CandidateResult,
    AutoTuneResult,
    ParameterLoader,
    PerturbationGenerator,
    FitnessCalculator,
    AutoTuneEngine,
)
from scripts.eval_suite_v2_2 import EvalResult, ScenarioResult


class TestFitnessMetrics:
    """Test fitness v0.2 metrics calculation"""

    def test_fitness_metrics_creation(self):
        """Should create fitness metrics with all fields"""
        fitness = FitnessMetrics(
            recovery_score=0.8,
            collapse_penalty=0.2,
            efficiency=0.75,
            emotion_consistency=0.9,
            robustness=0.85
        )
        
        assert fitness.recovery_score == 0.8
        assert fitness.collapse_penalty == 0.2
        assert fitness.efficiency == 0.75
        assert fitness.emotion_consistency == 0.9
        assert fitness.robustness == 0.85

    def test_composite_fitness_calculation(self):
        """Should calculate composite fitness correctly"""
        fitness = FitnessMetrics(
            recovery_score=1.0,
            collapse_penalty=0.0,  # No penalty = best
            efficiency=1.0,
            emotion_consistency=1.0,
            robustness=1.0
        )
        
        composite = fitness.calculate_composite()
        
        # All perfect scores should give high composite
        assert composite > 0.9
        assert fitness.composite == composite

    def test_composite_with_collapse_penalty(self):
        """Collapse penalty should reduce composite score"""
        fitness = FitnessMetrics(
            recovery_score=1.0,
            collapse_penalty=0.5,  # 50% penalty
            efficiency=1.0,
            emotion_consistency=1.0,
            robustness=1.0
        )
        
        composite = fitness.calculate_composite()
        
        # Penalty should reduce score
        assert composite < 1.0

    def test_fitness_to_dict(self):
        """Should convert to dict correctly"""
        fitness = FitnessMetrics(
            recovery_score=0.8,
            collapse_penalty=0.2,
            efficiency=0.75,
            emotion_consistency=0.9,
            robustness=0.85
        )
        fitness.calculate_composite()
        
        d = fitness.to_dict()
        
        assert d["recovery_score"] == 0.8
        assert d["collapse_penalty"] == 0.2
        assert d["efficiency"] == 0.75
        assert d["composite"] == fitness.composite


class TestFitnessCalculator:
    """Test fitness calculation from eval results"""

    def test_calculate_recovery_score(self):
        """Should calculate recovery score from scenarios"""
        # Create mock eval result
        mock_scenario = ScenarioResult(
            scenario_name="test",
            scenario_file="test.yaml",
            start_time=datetime.now().isoformat(),
            end_time=datetime.now().isoformat(),
            duration_seconds=1.0,
            turns=[],
            metrics={
                "recovery_score": {"score": 0.8}
            },
            passed=True,
            summary="test"
        )
        
        mock_eval = EvalResult(
            start_time=datetime.now().isoformat(),
            end_time=datetime.now().isoformat(),
            total_scenarios=1,
            passed_scenarios=1,
            failed_scenarios=0,
            scenarios=[mock_scenario],
            aggregate_metrics={},
            seed=42
        )
        
        score = FitnessCalculator.calculate_recovery_score(mock_eval)
        
        assert score == 0.8

    def test_calculate_collapse_penalty(self):
        """Should detect energy/valence collapse"""
        mock_scenario = ScenarioResult(
            scenario_name="test",
            scenario_file="test.yaml",
            start_time=datetime.now().isoformat(),
            end_time=datetime.now().isoformat(),
            duration_seconds=1.0,
            turns=[],
            metrics={
                "body_telemetry": {
                    "data": {
                        "energy": {"min": 0.1},  # Collapsed
                        "valence": {"min": -0.6}  # Collapsed
                    }
                }
            },
            passed=True,
            summary="test"
        )
        
        mock_eval = EvalResult(
            start_time=datetime.now().isoformat(),
            end_time=datetime.now().isoformat(),
            total_scenarios=1,
            passed_scenarios=1,
            failed_scenarios=0,
            scenarios=[mock_scenario],
            aggregate_metrics={},
            seed=42
        )
        
        penalty = FitnessCalculator.calculate_collapse_penalty(mock_eval)
        
        # Should have high penalty due to collapse
        assert penalty > 0.5

    def test_calculate_efficiency(self):
        """Should calculate efficiency metric"""
        from scripts.eval_suite_v2_2 import TurnResult, EmotionSnapshot
        
        mock_turn = TurnResult(
            turn_id=1,
            phase="test",
            event_type="user_message",
            actor="user",
            target="assistant",
            emotion_before=None,
            emotion_after=EmotionSnapshot(
                valence=0.0, arousal=0.3, anger=0.0, sadness=0.0,
                anxiety=0.1, joy=0.2, loneliness=0.1,
                social_safety=0.6, energy=0.7
            ),
            success=True
        )
        
        mock_scenario = ScenarioResult(
            scenario_name="test",
            scenario_file="test.yaml",
            start_time=datetime.now().isoformat(),
            end_time=datetime.now().isoformat(),
            duration_seconds=1.0,
            turns=[mock_turn],
            metrics={
                "body_telemetry": {
                    "data": {
                        "energy": {"min": 0.7}
                    }
                }
            },
            passed=True,
            summary="test"
        )
        
        mock_eval = EvalResult(
            start_time=datetime.now().isoformat(),
            end_time=datetime.now().isoformat(),
            total_scenarios=1,
            passed_scenarios=1,
            failed_scenarios=0,
            scenarios=[mock_scenario],
            aggregate_metrics={},
            seed=42
        )
        
        efficiency = FitnessCalculator.calculate_efficiency(mock_eval)
        
        # Should have positive efficiency
        assert efficiency > 0
        assert efficiency <= 1.0

    def test_calculate_all_fitness(self):
        """Should calculate all fitness metrics"""
        mock_scenario = ScenarioResult(
            scenario_name="test",
            scenario_file="test.yaml",
            start_time=datetime.now().isoformat(),
            end_time=datetime.now().isoformat(),
            duration_seconds=1.0,
            turns=[],
            metrics={
                "recovery_score": {"score": 0.8},
                "body_telemetry": {
                    "data": {
                        "energy": {"min": 0.6},
                        "valence": {"min": -0.2}
                    }
                },
                "robustness_score": {"score": 0.75}
            },
            passed=True,
            summary="test"
        )
        
        mock_eval = EvalResult(
            start_time=datetime.now().isoformat(),
            end_time=datetime.now().isoformat(),
            total_scenarios=1,
            passed_scenarios=1,
            failed_scenarios=0,
            scenarios=[mock_scenario],
            aggregate_metrics={
                "emotion_consistency": {"pass_rate": 0.9}
            },
            seed=42
        )
        
        fitness = FitnessCalculator.calculate_all(mock_eval)
        
        assert fitness.recovery_score == 0.8
        assert fitness.robustness == 0.75
        assert fitness.emotion_consistency == 0.9
        assert fitness.composite > 0


class TestParameterCoverage:
    """Test that all parameters are covered"""

    def test_all_params_have_schema(self):
        """All tunable params should have complete schema"""
        required_fields = ["default", "min", "max", "description", "category"]
        
        for name, defn in DEFAULT_TUNABLE_PARAMS.items():
            for field in required_fields:
                assert field in defn, f"Parameter {name} missing {field}"

    def test_default_within_range(self):
        """Default values should be within min/max"""
        for name, defn in DEFAULT_TUNABLE_PARAMS.items():
            default = defn["default"]
            min_val = defn["min"]
            max_val = defn["max"]
            
            assert min_val <= default <= max_val, \
                f"Parameter {name} default {default} not in range [{min_val}, {max_val}]"

    def test_param_categories(self):
        """Parameters should have valid categories"""
        valid_categories = [
            "precision", "allostasis", "intrinsic", "self_model", "meta_cognition"
        ]
        
        for name, defn in DEFAULT_TUNABLE_PARAMS.items():
            assert defn["category"] in valid_categories, \
                f"Parameter {name} has invalid category: {defn['category']}"

    def test_param_count(self):
        """Should have expected number of tunable parameters"""
        # MVP-6 should have at least 20 tunable parameters
        assert len(DEFAULT_TUNABLE_PARAMS) >= 20


class TestPerturbationReproducibility:
    """Test parameter perturbation with seeds"""

    def test_perturbation_reproducibility(self):
        """Same seed should produce same perturbations"""
        gen1 = PerturbationGenerator(seed=42)
        gen2 = PerturbationGenerator(seed=42)

        baseline = {"param1": 0.5, "param2": 0.3}

        pert1 = gen1.perturb(baseline, DEFAULT_TUNABLE_PARAMS, "random", 0.2)
        pert2 = gen2.perturb(baseline, DEFAULT_TUNABLE_PARAMS, "random", 0.2)

        assert pert1 == pert2

    def test_different_seeds_different_results(self):
        """Different seeds should produce different perturbations"""
        gen1 = PerturbationGenerator(seed=42)
        gen2 = PerturbationGenerator(seed=99)

        baseline = {"param1": 0.5, "param2": 0.3}

        pert1 = gen1.perturb(baseline, DEFAULT_TUNABLE_PARAMS, "random", 0.2)
        pert2 = gen2.perturb(baseline, DEFAULT_TUNABLE_PARAMS, "random", 0.2)

        assert pert1 != pert2

    def test_candidate_generation_reproducibility(self):
        """Candidate generation should be reproducible"""
        gen1 = PerturbationGenerator(seed=42)
        gen2 = PerturbationGenerator(seed=42)

        baseline = {name: defn["default"] for name, defn in DEFAULT_TUNABLE_PARAMS.items()}

        cand1 = gen1.generate_candidates(baseline, DEFAULT_TUNABLE_PARAMS, count=5)
        cand2 = gen2.generate_candidates(baseline, DEFAULT_TUNABLE_PARAMS, count=5)

        assert len(cand1) == len(cand2) == 5
        for c1, c2 in zip(cand1, cand2):
            assert c1 == c2

    def test_perturbation_respects_bounds(self):
        """Perturbation should respect parameter bounds"""
        gen = PerturbationGenerator(seed=42)
        
        baseline = {name: defn["default"] for name, defn in DEFAULT_TUNABLE_PARAMS.items()}
        
        perturbed = gen.perturb(baseline, DEFAULT_TUNABLE_PARAMS, "random", 0.5)
        
        for name, value in perturbed.items():
            defn = DEFAULT_TUNABLE_PARAMS[name]
            assert defn["min"] <= value <= defn["max"], \
                f"Parameter {name} = {value} out of bounds [{defn['min']}, {defn['max']}]"


class TestParameterLoader:
    """Test parameter loading and saving"""

    def test_load_json_params(self, tmp_path):
        """Should load JSON parameters"""
        param_file = tmp_path / "params.json"
        
        data = {
            "params": {
                "precision_temperature": 0.6,
                "energy_recovery_rate": 0.002
            }
        }
        
        with open(param_file, 'w') as f:
            json.dump(data, f)
        
        loaded = ParameterLoader.load(param_file)
        
        assert loaded["precision_temperature"] == 0.6
        assert loaded["energy_recovery_rate"] == 0.002

    def test_load_yaml_params(self, tmp_path):
        """Should load YAML parameters"""
        param_file = tmp_path / "params.yaml"
        
        data = {
            "params": {
                "precision_temperature": 0.6,
                "energy_recovery_rate": 0.002
            }
        }
        
        with open(param_file, 'w') as f:
            yaml.dump(data, f)
        
        loaded = ParameterLoader.load(param_file)
        
        assert loaded["precision_temperature"] == 0.6
        assert loaded["energy_recovery_rate"] == 0.002

    def test_save_json_params(self, tmp_path):
        """Should save JSON parameters"""
        param_file = tmp_path / "params.json"
        
        params = {"precision_temperature": 0.6}
        metadata = {"version": "1.0"}
        
        ParameterLoader.save(params, param_file, metadata)
        
        with open(param_file, 'r') as f:
            loaded = json.load(f)
        
        assert loaded["params"]["precision_temperature"] == 0.6
        assert loaded["metadata"]["version"] == "1.0"

    def test_save_yaml_params(self, tmp_path):
        """Should save YAML parameters"""
        param_file = tmp_path / "params.yaml"
        
        params = {"precision_temperature": 0.6}
        metadata = {"version": "1.0"}
        
        ParameterLoader.save(params, param_file, metadata)
        
        with open(param_file, 'r') as f:
            loaded = yaml.safe_load(f)
        
        assert loaded["params"]["precision_temperature"] == 0.6


class TestCandidateRanking:
    """Test candidate ranking and selection"""

    def test_candidate_ranking_by_composite(self):
        """Candidates should be ranked by composite fitness"""
        candidates = [
            CandidateResult(
                candidate_id="c1",
                params={},
                fitness=FitnessMetrics(0.5, 0.5, 0.5, 0.5, 0.5),
                eval_result={}
            ),
            CandidateResult(
                candidate_id="c2",
                params={},
                fitness=FitnessMetrics(0.9, 0.1, 0.9, 0.9, 0.9),
                eval_result={}
            ),
            CandidateResult(
                candidate_id="c3",
                params={},
                fitness=FitnessMetrics(0.7, 0.3, 0.7, 0.7, 0.7),
                eval_result={}
            ),
        ]
        
        # Calculate composites
        for c in candidates:
            c.fitness.calculate_composite()
        
        # Sort by composite
        candidates.sort(key=lambda c: c.fitness.composite, reverse=True)
        
        # Assign ranks
        for i, c in enumerate(candidates):
            c.rank = i + 1
        
        # c2 should be rank 1 (best)
        assert candidates[0].candidate_id == "c2"
        assert candidates[0].rank == 1

    def test_best_candidate_selection(self):
        """Best candidate should have highest composite fitness"""
        baseline = FitnessMetrics(0.6, 0.4, 0.6, 0.6, 0.6)
        baseline.calculate_composite()
        
        candidates = [
            CandidateResult(
                candidate_id="c1",
                params={},
                fitness=FitnessMetrics(0.5, 0.5, 0.5, 0.5, 0.5),
                eval_result={}
            ),
            CandidateResult(
                candidate_id="c2",
                params={},
                fitness=FitnessMetrics(0.9, 0.1, 0.9, 0.9, 0.9),
                eval_result={}
            ),
        ]
        
        for c in candidates:
            c.fitness.calculate_composite()
        
        best = max(candidates, key=lambda c: c.fitness.composite)
        
        assert best.candidate_id == "c2"
        assert best.fitness.composite > baseline.composite


class TestReportGeneration:
    """Test report generation"""

    def test_markdown_report_structure(self):
        """Markdown report should have expected structure"""
        base_path = Path(__file__).parent.parent
        scenarios_dir = base_path / "scenarios"
        output_dir = Path(tempfile.mkdtemp())
        
        engine = AutoTuneEngine(
            scenarios_dir=scenarios_dir,
            output_dir=output_dir,
            seed=42
        )
        
        baseline_fitness = FitnessMetrics(0.7, 0.3, 0.7, 0.8, 0.75)
        baseline_fitness.calculate_composite()
        
        result = AutoTuneResult(
            timestamp=datetime.now().isoformat(),
            seed=42,
            baseline_params={"param1": 0.5},
            baseline_fitness=baseline_fitness,
            baseline_result={},
            candidates=[],
            overall_improvement=False,
            recommendations=["Test recommendation"]
        )
        
        markdown = engine._generate_markdown(result)
        
        assert "# Auto-Tune v0.2 Report" in markdown
        assert "## Baseline Fitness" in markdown
        assert "Recovery Score" in markdown
        assert "Collapse Penalty" in markdown
        assert "## Recommendations" in markdown

    def test_json_report_structure(self, tmp_path):
        """JSON report should have expected structure"""
        base_path = Path(__file__).parent.parent
        scenarios_dir = base_path / "scenarios"
        
        engine = AutoTuneEngine(
            scenarios_dir=scenarios_dir,
            output_dir=tmp_path,
            seed=42
        )
        
        baseline_fitness = FitnessMetrics(0.7, 0.3, 0.7, 0.8, 0.75)
        baseline_fitness.calculate_composite()
        
        result = AutoTuneResult(
            timestamp=datetime.now().isoformat(),
            seed=42,
            baseline_params={"param1": 0.5},
            baseline_fitness=baseline_fitness,
            baseline_result={},
            candidates=[],
            overall_improvement=True,
            recommendations=[]
        )
        
        json_path, md_path = engine.save_report(result)
        
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        assert data["seed"] == 42
        assert data["overall_improvement"] == True
        assert "baseline_fitness" in data
        assert data["baseline_fitness"]["composite"] == baseline_fitness.composite


class TestIntegration:
    """Integration tests"""

    @pytest.mark.asyncio
    async def test_end_to_end_with_mock(self):
        """End-to-end test with mock eval"""
        base_path = Path(__file__).parent.parent
        scenarios_dir = base_path / "scenarios"
        output_dir = Path(tempfile.mkdtemp())
        
        engine = AutoTuneEngine(
            scenarios_dir=scenarios_dir,
            output_dir=output_dir,
            seed=42
        )
        
        baseline = {name: defn["default"] for name, defn in DEFAULT_TUNABLE_PARAMS.items()}
        
        # Run with just 2 candidates for speed
        result = await engine.tune(
            baseline_params=baseline,
            candidate_params_list=None,
            scenarios=None,
            generate_candidates=True,
            candidate_count=2
        )
        
        assert result.seed == 42
        assert len(result.candidates) == 2
        assert result.baseline_fitness is not None
        
        for c in result.candidates:
            assert c.fitness.composite > 0
            assert c.fitness.recovery_score >= 0
            assert c.fitness.collapse_penalty >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
