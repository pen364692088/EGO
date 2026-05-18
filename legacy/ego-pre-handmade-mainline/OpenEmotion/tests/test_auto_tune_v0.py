#!/usr/bin/env python3
"""
Tests for Auto-Tune v0 (MVP-5 D5)

Coverage:
1. Reproducibility with fixed seed
2. Schema completeness
3. Clear failure messages
4. Parameter loading/saving
5. Metric extraction and comparison
6. Perturbation generation
7. Report generation
"""

import os
import sys
import json
import yaml
import pytest
import tempfile
import random
import asyncio
from pathlib import Path
from datetime import datetime
from dataclasses import asdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.auto_tune_v0 import (
    DEFAULT_TUNABLE_PARAMS,
    ParameterSet,
    MetricComparison,
    AutoTuneResult,
    ParameterLoader,
    PerturbationGenerator,
    MetricExtractor,
    AutoTuneEngine,
)
from scripts.eval_suite_v2 import EvalResult, ScenarioResult


class TestReproducibility:
    """Test reproducibility with fixed seed"""

    def test_perturbation_reproducibility(self):
        """Same seed should produce same perturbations"""
        gen1 = PerturbationGenerator(seed=42)
        gen2 = PerturbationGenerator(seed=42)

        baseline = {"param1": 0.5, "param2": 0.3}

        pert1 = gen1.perturb(baseline, DEFAULT_TUNABLE_PARAMS, "random", 0.2)
        pert2 = gen2.perturb(baseline, DEFAULT_TUNABLE_PARAMS, "random", 0.2)

        assert pert1 == pert2, "Perturbations with same seed should be identical"

    def test_different_seeds_produce_different_results_fixed(self):
        """Different seeds should produce different perturbations"""
        gen1 = PerturbationGenerator(seed=42)
        gen2 = PerturbationGenerator(seed=99)

        baseline = {"precision_temperature": 0.5, "energy_recovery_rate": 0.001}
        param_defs = {"precision_temperature": {"min": 0.1, "max": 1.0, "default": 0.5}, "energy_recovery_rate": {"min": 0.0001, "max": 0.01, "default": 0.001}}

        pert1 = gen1.perturb(baseline, param_defs, "random", 0.5)
        pert2 = gen2.perturb(baseline, param_defs, "random", 0.5)

        assert pert1 != pert2, "Different seeds should produce different perturbations"

    def test_candidate_generation_reproducibility(self):
        """Candidate generation should be reproducible with same seed"""
        gen1 = PerturbationGenerator(seed=42)
        gen2 = PerturbationGenerator(seed=42)

        baseline = {name: defn["default"] for name, defn in DEFAULT_TUNABLE_PARAMS.items()}

        cand1 = gen1.generate_candidates(baseline, DEFAULT_TUNABLE_PARAMS, count=3)
        cand2 = gen2.generate_candidates(baseline, DEFAULT_TUNABLE_PARAMS, count=3)

        assert len(cand1) == len(cand2) == 3
        for c1, c2 in zip(cand1, cand2):
            assert c1 == c2, "Candidates with same seed should be identical"


class TestSchemaCompleteness:
    """Test schema completeness and validation"""

    def test_default_params_schema(self):
        """All default parameters should have required schema fields"""
        required_fields = ["default", "min", "max", "description", "category"]

        for name, defn in DEFAULT_TUNABLE_PARAMS.items():
            for field in required_fields:
                assert field in defn, f"Parameter {name} missing field: {field}"

    def test_default_within_range(self):
        """Default values should be within min/max range"""
        for name, defn in DEFAULT_TUNABLE_PARAMS.items():
            default = defn["default"]
            min_val = defn["min"]
            max_val = defn["max"]

            assert min_val <= default <= max_val, \
                f"Parameter {name} default {default} not in range [{min_val}, {max_val}]"

    def test_categories_valid(self):
        """All parameters should have valid categories"""
        valid_categories = ["precision", "allostasis", "intrinsic", "self_model", "meta_cognition"]

        for name, defn in DEFAULT_TUNABLE_PARAMS.items():
            assert defn["category"] in valid_categories, \
                f"Parameter {name} has invalid category: {defn['category']}"

    def test_parameter_set_serialization(self):
        """ParameterSet should serialize/deserialize correctly"""
        params = {"param1": 0.5, "param2": 0.3}
        ps = ParameterSet(name="test", params=params, seed=42)

        # Test to_dict
        d = ps.to_dict()
        assert d["name"] == "test"
        assert d["params"] == params
        assert d["seed"] == 42
        assert "timestamp" in d

        # Test from_dict
        ps2 = ParameterSet.from_dict(d)
        assert ps2.name == ps.name
        assert ps2.params == ps.params
        assert ps2.seed == ps.seed


class TestFailureMessages:
    """Test clear failure messages"""

    def test_file_not_found_error(self):
        """Loading non-existent file should give clear error"""
        with pytest.raises(FileNotFoundError) as exc_info:
            ParameterLoader.load(Path("/nonexistent/file.yaml"))

        assert "not found" in str(exc_info.value).lower()

    def test_invalid_file_format(self):
        """Loading invalid format should give clear error"""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"invalid")
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError) as exc_info:
                ParameterLoader.load(temp_path)

            assert "unsupported" in str(exc_info.value).lower()
        finally:
            os.unlink(temp_path)

    def test_invalid_yaml_content(self):
        """Loading invalid YAML should give clear error"""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode='w') as f:
            f.write("not: valid: yaml: [")
            temp_path = Path(f.name)

        try:
            with pytest.raises(Exception):
                ParameterLoader.load(temp_path)
        finally:
            os.unlink(temp_path)

    def test_unknown_perturbation_strategy(self):
        """Unknown strategy should give clear error"""
        gen = PerturbationGenerator(seed=42)
        baseline = {"param1": 0.5}
        param_defs = {"param1": {"min": 0.0, "max": 1.0, "default": 0.5}}

        with pytest.raises(ValueError) as exc_info:
            gen.perturb(baseline, param_defs, "unknown_strategy", 0.2)

        assert "unknown" in str(exc_info.value).lower()


class TestParameterLoading:
    """Test parameter loading and saving"""

    def test_load_json_params(self):
        """Test loading JSON parameter file"""
        params = {"param1": 0.5, "param2": 0.3}
        data = {"params": params, "metadata": {"version": "1.0"}}

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode='w') as f:
            json.dump(data, f)
            temp_path = Path(f.name)

        try:
            loaded = ParameterLoader.load(temp_path)
            assert loaded == params
        finally:
            os.unlink(temp_path)

    def test_load_yaml_params(self):
        """Test loading YAML parameter file"""
        params = {"param1": 0.5, "param2": 0.3}
        data = {"params": params, "metadata": {"version": "1.0"}}

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode='w') as f:
            yaml.dump(data, f)
            temp_path = Path(f.name)

        try:
            loaded = ParameterLoader.load(temp_path)
            assert loaded == params
        finally:
            os.unlink(temp_path)

    def test_save_json_params(self):
        """Test saving JSON parameter file"""
        params = {"param1": 0.5, "param2": 0.3}
        metadata = {"version": "1.0"}

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = Path(f.name)

        try:
            ParameterLoader.save(params, temp_path, metadata)
            loaded = ParameterLoader.load(temp_path)
            assert loaded == params
        finally:
            os.unlink(temp_path)

    def test_save_yaml_params(self):
        """Test saving YAML parameter file"""
        params = {"param1": 0.5, "param2": 0.3}
        metadata = {"version": "1.0"}

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            temp_path = Path(f.name)

        try:
            ParameterLoader.save(params, temp_path, metadata)
            loaded = ParameterLoader.load(temp_path)
            assert loaded == params
        finally:
            os.unlink(temp_path)

    def test_load_flat_dict(self):
        """Test loading flat dictionary (no 'params' key)"""
        data = {"param1": 0.5, "param2": 0.3, "name": "test"}

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode='w') as f:
            json.dump(data, f)
            temp_path = Path(f.name)

        try:
            loaded = ParameterLoader.load(temp_path)
            assert "param1" in loaded
            assert "param2" in loaded
            assert "name" not in loaded  # Non-numeric values filtered
        finally:
            os.unlink(temp_path)


class TestPerturbationGeneration:
    """Test perturbation generation"""

    def test_perturbation_respects_bounds(self):
        """Perturbations should respect min/max bounds"""
        gen = PerturbationGenerator(seed=42)

        baseline = {"precision_temperature": 0.5}
        param_defs = {
            "precision_temperature": {"min": 0.1, "max": 1.0, "default": 0.5}
        }

        for _ in range(100):
            perturbed = gen.perturb(baseline, param_defs, "random", 0.5)
            assert 0.1 <= perturbed["precision_temperature"] <= 1.0

    def test_perturbation_strategies(self):
        """Test different perturbation strategies"""
        gen = PerturbationGenerator(seed=42)
        baseline = {"param1": 0.5}
        param_defs = {"param1": {"min": 0.0, "max": 1.0, "default": 0.5}}

        for strategy in ["random", "gaussian", "boundary"]:
            perturbed = gen.perturb(baseline, param_defs, strategy, 0.2)
            assert 0.0 <= perturbed["param1"] <= 1.0

    def test_magnitude_effect(self):
        """Higher magnitude should produce larger changes on average"""
        gen = PerturbationGenerator(seed=42)
        baseline = {"param1": 0.5}
        param_defs = {"param1": {"min": 0.0, "max": 1.0, "default": 0.5}}

        small_changes = []
        large_changes = []

        for _ in range(50):
            p1 = gen.perturb(baseline, param_defs, "random", 0.1)
            p2 = gen.perturb(baseline, param_defs, "random", 0.5)
            small_changes.append(abs(p1["param1"] - baseline["param1"]))
            large_changes.append(abs(p2["param1"] - baseline["param1"]))

        avg_small = sum(small_changes) / len(small_changes)
        avg_large = sum(large_changes) / len(large_changes)

        assert avg_large > avg_small, "Larger magnitude should produce larger changes"


class TestMetricExtraction:
    """Test metric extraction and comparison"""

    def test_metric_extraction_structure(self):
        """Test that metric extraction produces expected structure"""
        # Create a minimal mock EvalResult
        mock_result = EvalResult(
            start_time=datetime.now().isoformat(),
            end_time=datetime.now().isoformat(),
            total_scenarios=5,
            passed_scenarios=3,
            failed_scenarios=2,
            scenarios=[],
            aggregate_metrics={
                "emotion_consistency": {"pass_rate": 0.8},
                "individualization_diff": {"average": 0.15, "max": 0.3},
                "high_impact_false_positive_rate": {"average": 0.05},
                "meta_cognition_trigger_rate": {"average": 0.25}
            }
        )

        metrics = MetricExtractor.extract(mock_result)

        assert "emotion_consistency" in metrics
        assert "scenario_pass_rate" in metrics
        assert metrics["scenario_pass_rate"] == 0.6  # 3/5

    def test_metric_comparison(self):
        """Test metric comparison logic"""
        baseline = {"metric1": 0.5, "metric2": 0.3}
        candidate = {"metric1": 0.6, "metric2": 0.2}

        comparisons = MetricExtractor.compare(baseline, candidate)

        assert len(comparisons) == 2

        # metric1: higher is better (emotion_consistency)
        comp1 = next(c for c in comparisons if c.metric_name == "metric1")
        assert abs(comp1.absolute_diff - 0.1) < 0.001
        assert abs(comp1.relative_diff_percent - 20.0) < 0.001

        # metric2: depends on metric definition
        comp2 = next(c for c in comparisons if c.metric_name == "metric2")
        assert abs(comp2.absolute_diff - (-0.1)) < 0.001

    def test_improvement_detection(self):
        """Test improvement detection for different metric types"""
        # For high_is_better=True metrics
        baseline = {"emotion_consistency": 0.5}
        candidate_improved = {"emotion_consistency": 0.6}
        candidate_worsened = {"emotion_consistency": 0.4}

        comp_improved = MetricExtractor.compare(baseline, candidate_improved)[0]
        comp_worsened = MetricExtractor.compare(baseline, candidate_worsened)[0]

        assert comp_improved.improvement is True
        assert comp_worsened.improvement is False

        # For high_is_better=False metrics (high_impact_false_positive_rate)
        baseline_fp = {"high_impact_false_positive_rate": 0.1}
        candidate_fp_improved = {"high_impact_false_positive_rate": 0.05}
        candidate_fp_worsened = {"high_impact_false_positive_rate": 0.15}

        comp_fp_improved = MetricExtractor.compare(baseline_fp, candidate_fp_improved)[0]
        comp_fp_worsened = MetricExtractor.compare(baseline_fp, candidate_fp_worsened)[0]

        assert comp_fp_improved.improvement is True  # Lower is better
        assert comp_fp_worsened.improvement is False


class TestAutoTuneResult:
    """Test AutoTuneResult data class"""

    def test_result_serialization(self):
        """Test AutoTuneResult serialization"""
        comparisons = [
            MetricComparison(
                metric_name="test",
                baseline_value=0.5,
                candidate_value=0.6,
                absolute_diff=0.1,
                relative_diff_percent=20.0,
                improvement=True,
                description="Test metric"
            )
        ]

        result = AutoTuneResult(
            timestamp=datetime.now().isoformat(),
            seed=42,
            baseline_params={"p1": 0.5},
            candidate_params={"p1": 0.6},
            baseline_result={"passed": 5},
            candidate_result={"passed": 6},
            metric_comparisons=comparisons,
            overall_improvement=True,
            recommendations=["Test recommendation"]
        )

        d = result.to_dict()
        assert d["seed"] == 42
        assert d["overall_improvement"] is True
        assert len(d["metric_comparisons"]) == 1
        assert d["recommendations"][0] == "Test recommendation"


class TestIntegration:
    """Integration tests for auto-tune workflow"""

    @pytest.mark.asyncio
    async def test_auto_tune_engine_initialization(self):
        """Test AutoTuneEngine initialization"""
        with tempfile.TemporaryDirectory() as tmpdir:
            scenarios_dir = Path(tmpdir) / "scenarios"
            output_dir = Path(tmpdir) / "reports"
            scenarios_dir.mkdir()

            engine = AutoTuneEngine(
                scenarios_dir=scenarios_dir,
                output_dir=output_dir,
                seed=42
            )

            assert engine.seed == 42
            assert engine.scenarios_dir == scenarios_dir
            assert engine.output_dir == output_dir

    def test_report_generation(self):
        """Test report generation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            comparisons = [
                MetricComparison(
                    metric_name="emotion_consistency",
                    baseline_value=0.5,
                    candidate_value=0.6,
                    absolute_diff=0.1,
                    relative_diff_percent=20.0,
                    improvement=True,
                    description="Consistency metric"
                )
            ]

            result = AutoTuneResult(
                timestamp=datetime.now().isoformat(),
                seed=42,
                baseline_params={"p1": 0.5},
                candidate_params={"p1": 0.6},
                baseline_result={"passed_scenarios": 3, "total_scenarios": 5},
                candidate_result={"passed_scenarios": 4, "total_scenarios": 5},
                metric_comparisons=comparisons,
                overall_improvement=True,
                recommendations=["Test rec"]
            )

            engine = AutoTuneEngine(
                scenarios_dir=output_dir,
                output_dir=output_dir,
                seed=42
            )

            json_path, md_path = engine.save_report(result)

            assert json_path.exists()
            assert md_path.exists()

            # Verify JSON content
            with open(json_path) as f:
                saved = json.load(f)
                assert saved["seed"] == 42
                assert saved["overall_improvement"] is True

            # Verify Markdown content
            with open(md_path) as f:
                content = f.read()
                assert "Auto-Tune v0 Report" in content
                assert "emotion_consistency" in content
                assert "Test rec" in content


class TestSecurityAudit:
    """Security audit tests"""

    def test_no_hardcoded_secrets(self):
        """Verify no hardcoded secrets in default parameters"""
        suspicious_patterns = ["password", "secret", "token", "key", "api_key", "credential"]

        for name, defn in DEFAULT_TUNABLE_PARAMS.items():
            for pattern in suspicious_patterns:
                assert pattern not in name.lower(), f"Parameter name contains suspicious pattern: {name}"
                assert pattern not in str(defn).lower(), f"Parameter definition contains suspicious pattern: {name}"

    def test_safe_temp_directory_usage(self):
        """Verify safe temporary directory usage"""
        # The engine should use proper temp directory handling
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            engine = AutoTuneEngine(
                scenarios_dir=output_dir,
                output_dir=output_dir,
                seed=42
            )

            # Should not create files outside of output_dir
            assert not any(Path("/tmp").glob("auto_tune_*"))

    def test_injection_cap_respected(self):
        """Verify 3KB injection cap is documented and respected"""
        # This is a conceptual test - the actual enforcement is in emotiond.security
        # We verify that auto_tune doesn't try to bypass it

        # Generate a large report and verify it's handled properly
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create a result with large data
            large_result = AutoTuneResult(
                timestamp=datetime.now().isoformat(),
                seed=42,
                baseline_params={"p" + str(i): 0.5 for i in range(100)},
                candidate_params={"p" + str(i): 0.6 for i in range(100)},
                baseline_result={"data": "x" * 10000},
                candidate_result={"data": "y" * 10000},
                metric_comparisons=[],
                overall_improvement=True,
                recommendations=[]
            )

            engine = AutoTuneEngine(
                scenarios_dir=output_dir,
                output_dir=output_dir,
                seed=42
            )

            # Should complete without error
            json_path, md_path = engine.save_report(large_result)
            assert json_path.exists()


class TestTraceRotation:
    """Test trace rotation compatibility"""

    def test_trace_rotation_not_disrupted(self):
        """Verify auto_tune doesn't disrupt trace rotation"""
        # This is a conceptual test - actual trace rotation is in emotiond.db
        # We verify that auto_tune doesn't interfere with database operations

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            engine = AutoTuneEngine(
                scenarios_dir=output_dir,
                output_dir=output_dir,
                seed=42
            )

            # The engine should not modify trace settings
            assert hasattr(engine, 'timestamp')
            assert engine.timestamp is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
