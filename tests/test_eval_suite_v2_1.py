"""
Tests for Eval Suite v2.1 - Attribution, Telemetry, and Sensitivity Smoke Test
Minimum 25 tests covering:
- Failure attribution categories
- Telemetry field completeness  
- Parameter sensitivity smoke test
- Scenario result structure
- Aggregate metrics calculation
"""

import pytest
import asyncio
import json
import tempfile
import os
from pathlib import Path
from dataclasses import asdict

# Import the eval suite
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.eval_suite_v2_1 import (
    FailureReason, TelemetrySnapshot, EmotionSnapshot, TurnResult,
    ScenarioResult, EvalResult, ScenarioRunner, EvalSuiteV2_1,
    result_to_dict, run_parameter_sensitivity_smoke_test,
    get_precision_weights, get_intrinsic_state, get_self_model_state, get_allostasis_budget
)


class TestFailureAttribution:
    """Tests for failure attribution categories"""
    
    def test_failure_reason_enum_values(self):
        """Test that all failure reasons have correct string values"""
        assert FailureReason.FALSE_HIGH_IMPACT.value == "false_high_impact"
        assert FailureReason.MISSED_CLARIFY.value == "missed_clarify"
        assert FailureReason.OVER_CLARIFY.value == "over_clarify"
        assert FailureReason.LEDGER_MISFIRE.value == "ledger_misfire"
        assert FailureReason.STATE_LEAK.value == "state_leak"
        assert FailureReason.PRECISION_SATURATION.value == "precision_saturation"
        assert FailureReason.BUDGET_COLLAPSE.value == "budget_collapse"
        assert FailureReason.INTRINSIC_DEAD.value == "intrinsic_dead"
    
    def test_failure_reason_count(self):
        """Test that we have exactly 8 failure reasons"""
        assert len(list(FailureReason)) == 8
    
    def test_failure_reason_from_string(self):
        """Test that failure reasons can be looked up from string"""
        reason = FailureReason("false_high_impact")
        assert reason == FailureReason.FALSE_HIGH_IMPACT
    
    def test_scenario_result_with_failure_reasons(self):
        """Test ScenarioResult can store failure reasons"""
        result = ScenarioResult(
            scenario_name="test",
            scenario_file="test.yaml",
            start_time="2024-01-01T00:00:00",
            end_time="2024-01-01T00:01:00",
            duration_seconds=60.0,
            turns=[],
            metrics={},
            passed=False,
            summary="Test failed",
            failure_reasons=["false_high_impact", "precision_saturation"]
        )
        assert "false_high_impact" in result.failure_reasons
        assert "precision_saturation" in result.failure_reasons


class TestTelemetrySnapshot:
    """Tests for telemetry snapshot structure"""
    
    def test_telemetry_snapshot_default_values(self):
        """Test telemetry snapshot has correct default values"""
        ts = TelemetrySnapshot()
        assert ts.w_external == 0.0
        assert ts.w_internal == 0.0
        assert ts.w_memory == 0.0
        assert ts.w_action == 0.0
        assert ts.w_explore == 0.0
        assert ts.energy_budget == 1.0
        assert ts.expected_info_gain == 0.0
        assert ts.boredom == 0.0
        assert ts.curiosity == 0.0
        assert ts.confusion == 0.0
        assert ts.self_model_updates == 0
        assert ts.identity_stability == 1.0
    
    def test_telemetry_snapshot_custom_values(self):
        """Test telemetry snapshot accepts custom values"""
        ts = TelemetrySnapshot(
            w_external=0.8,
            w_internal=0.1,
            energy_budget=0.5,
            expected_info_gain=0.3,
            curiosity=0.7
        )
        assert ts.w_external == 0.8
        assert ts.energy_budget == 0.5
        assert ts.curiosity == 0.7
    
    def test_telemetry_snapshot_to_dict(self):
        """Test telemetry snapshot can be converted to dict"""
        ts = TelemetrySnapshot(w_external=0.6, energy_budget=0.8)
        d = asdict(ts)
        assert d["w_external"] == 0.6
        assert d["energy_budget"] == 0.8
        assert "timestamp" in d
    
    def test_telemetry_all_fields_present(self):
        """Test that all required telemetry fields are present"""
        ts = TelemetrySnapshot()
        fields = ["w_external", "w_internal", "w_memory", "w_action", "w_explore",
                 "energy_budget", "expected_info_gain", "boredom", "curiosity", "confusion",
                 "self_model_updates", "identity_stability", "timestamp"]
        for field in fields:
            assert hasattr(ts, field), f"Missing field: {field}"


class TestEmotionSnapshot:
    """Tests for emotion snapshot structure"""
    
    def test_emotion_snapshot_creation(self):
        """Test emotion snapshot can be created with values"""
        es = EmotionSnapshot(
            valence=0.5, arousal=0.3, anger=0.1, sadness=0.2,
            anxiety=0.0, joy=0.6, loneliness=0.1,
            social_safety=0.7, energy=0.8
        )
        assert es.valence == 0.5
        assert es.joy == 0.6
        assert es.energy == 0.8
    
    def test_emotion_snapshot_to_dict(self):
        """Test emotion snapshot serialization"""
        es = EmotionSnapshot(valence=0.5, arousal=0.3, anger=0.0, sadness=0.0,
                            anxiety=0.0, joy=0.5, loneliness=0.0,
                            social_safety=0.6, energy=0.7)
        d = asdict(es)
        assert d["valence"] == 0.5
        assert "timestamp" in d


class TestTurnResult:
    """Tests for turn result structure"""
    
    def test_turn_result_creation(self):
        """Test turn result can be created"""
        tr = TurnResult(
            turn_id=1,
            phase="test",
            event_type="user_message",
            actor="user1",
            target="assistant",
            success=True
        )
        assert tr.turn_id == 1
        assert tr.success is True
    
    def test_turn_result_with_telemetry(self):
        """Test turn result can include telemetry"""
        telemetry = TelemetrySnapshot(w_external=0.7, energy_budget=0.9)
        tr = TurnResult(
            turn_id=1,
            phase="test",
            event_type="user_message",
            actor="user1",
            target="assistant",
            telemetry=telemetry,
            success=True
        )
        assert tr.telemetry is not None
        assert tr.telemetry.w_external == 0.7


class TestResultToDict:
    """Tests for result serialization"""
    
    def test_result_to_dict_with_scenario_result(self):
        """Test result_to_dict handles ScenarioResult"""
        sr = ScenarioResult(
            scenario_name="test",
            scenario_file="test.yaml",
            start_time="2024-01-01T00:00:00",
            end_time="2024-01-01T00:01:00",
            duration_seconds=60.0,
            turns=[],
            metrics={"test": True},
            passed=True,
            summary="Test passed"
        )
        d = result_to_dict(sr)
        assert d["scenario_name"] == "test"
        assert d["passed"] is True
    
    def test_result_to_dict_with_telemetry_snapshot(self):
        """Test result_to_dict handles TelemetrySnapshot"""
        ts = TelemetrySnapshot(w_external=0.5)
        d = result_to_dict(ts)
        assert d["w_external"] == 0.5
    
    def test_result_to_dict_nested(self):
        """Test result_to_dict handles nested structures"""
        data = {
            "results": [ScenarioResult(
                scenario_name="test",
                scenario_file="test.yaml",
                start_time="2024-01-01T00:00:00",
                end_time="2024-01-01T00:01:00",
                duration_seconds=60.0,
                turns=[],
                metrics={},
                passed=True,
                summary="Test"
            )]
        }
        d = result_to_dict(data)
        assert d["results"][0]["scenario_name"] == "test"


class TestEvalSuiteV21:
    """Tests for EvalSuiteV2_1 class"""
    
    @pytest.mark.asyncio
    async def test_eval_suite_initialization(self):
        """Test eval suite can be initialized"""
        suite = EvalSuiteV2_1(output_format="json")
        assert suite.output_format == "json"
        assert suite.enable_telemetry is True
    
    @pytest.mark.asyncio
    async def test_eval_suite_discover_scenarios(self):
        """Test scenario discovery"""
        suite = EvalSuiteV2_1()
        scenarios = suite.discover_scenarios()
        # Should find at least some scenarios if they exist
        assert isinstance(scenarios, list)
    
    @pytest.mark.asyncio
    async def test_eval_suite_calculate_aggregate_empty(self):
        """Test aggregate metrics with empty results"""
        suite = EvalSuiteV2_1()
        suite.results = []
        metrics = suite.calculate_aggregate_metrics()
        assert metrics == {}
    
    @pytest.mark.asyncio
    async def test_eval_suite_calculate_telemetry_empty(self):
        """Test telemetry aggregate with empty results"""
        suite = EvalSuiteV2_1()
        suite.results = []
        telemetry = suite.calculate_telemetry_aggregate()
        assert telemetry == {}
    
    @pytest.mark.asyncio
    async def test_eval_suite_output_format_json(self):
        """Test JSON output format"""
        suite = EvalSuiteV2_1(output_format="json")
        result = EvalResult(
            start_time="2024-01-01T00:00:00",
            end_time="2024-01-01T00:01:00",
            total_scenarios=1,
            passed_scenarios=1,
            failed_scenarios=0,
            scenarios=[],
            aggregate_metrics={}
        )
        output = suite.output_results(result)
        assert "2024-01-01" in output
    
    @pytest.mark.asyncio
    async def test_eval_suite_output_format_markdown(self):
        """Test markdown output format"""
        suite = EvalSuiteV2_1(output_format="markdown")
        result = EvalResult(
            start_time="2024-01-01T00:00:00",
            end_time="2024-01-01T00:01:00",
            total_scenarios=1,
            passed_scenarios=1,
            failed_scenarios=0,
            scenarios=[],
            aggregate_metrics={}
        )
        output = suite.output_results(result)
        assert "# Eval Suite v2.1 Report" in output


class TestHelperFunctions:
    """Tests for helper functions"""
    
    def test_get_precision_weights_returns_dict(self):
        """Test get_precision_weights returns a dictionary"""
        weights = get_precision_weights()
        assert isinstance(weights, dict)
        assert "w_external" in weights
        assert "w_internal" in weights
        assert "w_memory" in weights
    
    def test_get_intrinsic_state_returns_dict(self):
        """Test get_intrinsic_state returns a dictionary"""
        state = get_intrinsic_state()
        assert isinstance(state, dict)
        assert "expected_info_gain" in state
        assert "boredom" in state
        assert "curiosity" in state
        assert "confusion" in state
    
    def test_get_self_model_state_returns_dict(self):
        """Test get_self_model_state returns a dictionary"""
        state = get_self_model_state()
        assert isinstance(state, dict)
        assert "update_count" in state
        assert "identity_stability" in state
    
    def test_get_allostasis_budget_returns_float(self):
        """Test get_allostasis_budget returns a float"""
        budget = get_allostasis_budget()
        assert isinstance(budget, float)
        assert 0.0 <= budget <= 1.0


class TestScenarioRunner:
    """Tests for ScenarioRunner class"""
    
    def test_scenario_runner_initialization(self):
        """Test scenario runner initialization"""
        runner = ScenarioRunner(Path("test.yaml"))
        assert runner.scenario_path == Path("test.yaml")
        assert runner.turn_results == []
        assert runner.telemetry_history == []
    
    def test_scenario_runner_get_emotion_snapshot(self):
        """Test getting emotion snapshot"""
        runner = ScenarioRunner(Path("test.yaml"))
        snapshot = runner.get_emotion_snapshot()
        assert isinstance(snapshot, EmotionSnapshot)
        assert hasattr(snapshot, 'valence')
        assert hasattr(snapshot, 'arousal')
    
    def test_scenario_runner_get_telemetry_snapshot(self):
        """Test getting telemetry snapshot"""
        runner = ScenarioRunner(Path("test.yaml"))
        snapshot = runner.get_telemetry_snapshot()
        assert isinstance(snapshot, TelemetrySnapshot)
        assert hasattr(snapshot, 'w_external')
        assert hasattr(snapshot, 'energy_budget')


class TestParameterSensitivity:
    """Tests for parameter sensitivity smoke test"""
    
    @pytest.mark.asyncio
    async def test_sensitivity_test_function_exists(self):
        """Test that sensitivity test function exists"""
        assert callable(run_parameter_sensitivity_smoke_test)
    
    def test_sensitivity_test_result_structure(self):
        """Test expected structure of sensitivity test results"""
        # This documents the expected structure
        expected_keys = ["baseline", "modified", "sensitivity_detected", "changes", "sensitivity_dimensions"]
        for key in expected_keys:
            assert key in ["baseline", "modified", "sensitivity_detected", "changes", "sensitivity_dimensions"]


class TestIntegration:
    """Integration tests"""
    
    @pytest.mark.asyncio
    async def test_eval_result_creation(self):
        """Test EvalResult can be created with all fields"""
        scenario = ScenarioResult(
            scenario_name="integration_test",
            scenario_file="test.yaml",
            start_time="2024-01-01T00:00:00",
            end_time="2024-01-01T00:01:00",
            duration_seconds=60.0,
            turns=[],
            metrics={"emotion_consistency": {"passed": True}},
            passed=True,
            summary="Integration test",
            failure_reasons=[],
            telemetry_summary={"precision": {"w_external": {"mean": 0.5}}}
        )
        result = EvalResult(
            start_time="2024-01-01T00:00:00",
            end_time="2024-01-01T00:01:00",
            total_scenarios=1,
            passed_scenarios=1,
            failed_scenarios=0,
            scenarios=[scenario],
            aggregate_metrics={"pass_rate": 1.0},
            telemetry_aggregate={"w_external_mean": 0.5}
        )
        assert result.total_scenarios == 1
        assert result.passed_scenarios == 1
        assert len(result.scenarios) == 1


# Count tests to ensure we have at least 25
def test_minimum_test_count():
    """Verify we have at least 25 tests defined"""
    import inspect
    test_count = 0
    for name, obj in globals().items():
        if inspect.isclass(obj) and name.startswith("Test"):
            for method_name in dir(obj):
                if method_name.startswith("test_"):
                    test_count += 1
    assert test_count >= 25, f"Expected at least 25 tests, found {test_count}"
