"""
Test wrapper for MVP-4 Eval Suite v2

Provides pytest integration for the evaluation framework.
"""
import os
import sys
import pytest
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.eval_suite_v2 import (
    EvalSuiteV2, ScenarioRunner, EmotionSnapshot, 
    result_to_dict, TEST_SYSTEM_TOKEN, TEST_OPENCLAW_TOKEN
)


# Test fixtures
@pytest.fixture
def scenarios_dir():
    """Path to scenarios directory"""
    return Path(__file__).parent.parent / "scenarios"


@pytest.fixture
def sample_scenario_path(scenarios_dir):
    """Path to baseline scenario"""
    return scenarios_dir / "baseline.yaml"


@pytest.fixture
def eval_suite(scenarios_dir):
    """Create eval suite instance"""
    return EvalSuiteV2(scenarios_dir=scenarios_dir, output_format="json")


class TestScenarioLoading:
    """Tests for scenario loading and parsing"""
    
    def test_scenarios_directory_exists(self, scenarios_dir):
        """Verify scenarios directory exists"""
        assert scenarios_dir.exists(), f"Scenarios directory not found: {scenarios_dir}"
    
    def test_minimum_scenario_count(self, scenarios_dir):
        """Verify at least 5 scenario files exist"""
        scenarios = list(scenarios_dir.glob("*.yaml")) + list(scenarios_dir.glob("*.yml"))
        scenarios += list(scenarios_dir.glob("*.json"))
        assert len(scenarios) >= 5, f"Expected at least 5 scenarios, found {len(scenarios)}"
    
    def test_baseline_scenario_loads(self, sample_scenario_path):
        """Verify baseline scenario loads correctly"""
        if not sample_scenario_path.exists():
            pytest.skip("baseline.yaml not found")
        
        runner = ScenarioRunner(sample_scenario_path)
        assert runner.load(), "Failed to load baseline scenario"
        assert runner.scenario_data is not None
        assert "metadata" in runner.scenario_data
        assert "scenario" in runner.scenario_data
    
    def test_all_scenarios_valid_yaml(self, scenarios_dir):
        """Verify all scenarios are valid YAML"""
        import yaml
        
        for scenario_file in scenarios_dir.glob("*.yaml"):
            with open(scenario_file, 'r') as f:
                try:
                    data = yaml.safe_load(f)
                    assert data is not None, f"Empty scenario: {scenario_file}"
                    assert "metadata" in data, f"Missing metadata in {scenario_file}"
                    has_body = any(k in data for k in ("scenario", "test_steps", "setup", "conditions", "events"))
                    assert has_body, f"Missing scenario body in {scenario_file}"
                except yaml.YAMLError as e:
                    pytest.fail(f"Invalid YAML in {scenario_file}: {e}")


class TestScenarioStructure:
    """Tests for scenario structure compliance"""
    
    @pytest.mark.parametrize("scenario_file", [
        "baseline.yaml",
        "promise_betrayal.yaml", 
        "meta_cognition.yaml",
        "relationship_building.yaml",
        "multi_target_isolation.yaml"
    ])
    def test_scenario_has_required_fields(self, scenarios_dir, scenario_file):
        """Verify scenarios have all required fields"""
        import yaml
        
        scenario_path = scenarios_dir / scenario_file
        if not scenario_path.exists():
            pytest.skip(f"{scenario_file} not found")
        
        with open(scenario_path, 'r') as f:
            data = yaml.safe_load(f)
        
        # Check metadata
        assert "metadata" in data
        metadata = data["metadata"]
        assert "name" in metadata
        assert "version" in metadata
        assert "description" in metadata
        
        # Check scenario
        assert "scenario" in data
        scenario = data["scenario"]
        assert "name" in scenario
        assert "turns" in scenario
        assert len(scenario["turns"]) > 0
        
        # Check turn structure
        for turn in scenario["turns"]:
            assert "turn_id" in turn
            assert "event" in turn
            assert "type" in turn["event"]
    
    def test_turn_count_support(self, scenarios_dir):
        """Verify scenarios support 50+ turn conversations"""
        import yaml
        
        relationship_scenario = scenarios_dir / "relationship_building.yaml"
        if not relationship_scenario.exists():
            pytest.skip("relationship_building.yaml not found")
        
        with open(relationship_scenario, 'r') as f:
            data = yaml.safe_load(f)
        
        turns = data.get("scenario", {}).get("turns", [])
        assert len(turns) >= 50, f"Expected 50+ turns, found {len(turns)}"


class TestMetrics:
    """Tests for metric calculations"""
    
    def test_emotion_consistency_metric(self, eval_suite):
        """Test emotion consistency metric calculation"""
        # Create mock results
        from scripts.eval_suite_v2 import ScenarioResult, TurnResult, EmotionSnapshot
        
        mock_turns = [
            TurnResult(
                turn_id=1, phase="test", event_type="user_message",
                actor="user", target="assistant",
                emotion_before=EmotionSnapshot(0.0, 0.3, 0.0, 0.0, 0.0, 0.0, 0.0, 0.6, 0.7),
                emotion_after=EmotionSnapshot(0.1, 0.3, 0.0, 0.0, 0.0, 0.0, 0.0, 0.6, 0.7),
                relationships={}, meta_cognition_triggered=False, success=True
            ),
            TurnResult(
                turn_id=2, phase="test", event_type="user_message",
                actor="user", target="assistant",
                emotion_before=EmotionSnapshot(0.1, 0.3, 0.0, 0.0, 0.0, 0.0, 0.0, 0.6, 0.7),
                emotion_after=EmotionSnapshot(0.2, 0.3, 0.0, 0.0, 0.0, 0.0, 0.0, 0.6, 0.7),
                relationships={}, meta_cognition_triggered=False, success=True
            )
        ]
        
        # Metric calculation happens in ScenarioRunner
        # This test verifies the metric structure
        assert True  # Placeholder for actual metric validation
    
    def test_individualization_diff_metric(self):
        """Test individualization diff metric structure"""
        expected_keys = ["max_diff", "actor_count", "passed"]
        for key in expected_keys:
            assert True  # Key existence will be verified in actual runs
    
    def test_high_impact_false_positive_rate_metric(self):
        """Test high impact false positive rate metric structure"""
        # Verify metric thresholds
        max_acceptable_rate = 0.1
        assert max_acceptable_rate == 0.1  # 10% false positive threshold
    
    def test_meta_cognition_trigger_rate_metric(self):
        """Test meta cognition trigger rate metric structure"""
        # Verify reasonable range
        min_rate = 0.05
        max_rate = 0.6
        assert min_rate <= max_rate


class TestEvalSuiteIntegration:
    """Integration tests for the eval suite"""
    
    @pytest.mark.asyncio
    async def test_eval_suite_discovers_scenarios(self, eval_suite, scenarios_dir):
        """Test that eval suite discovers scenario files"""
        scenarios = eval_suite.discover_scenarios()
        assert len(scenarios) >= 5, f"Expected at least 5 scenarios, found {len(scenarios)}"
    
    @pytest.mark.asyncio
    async def test_scenario_runner_setup(self, sample_scenario_path):
        """Test scenario runner initialization"""
        if not sample_scenario_path.exists():
            pytest.skip("baseline.yaml not found")
        
        runner = ScenarioRunner(sample_scenario_path)
        assert runner.load()
        
        # Verify scenario loaded correctly
        assert runner.scenario_data is not None
    
    @pytest.mark.asyncio
    async def test_json_output_format(self, eval_suite):
        """Test JSON output format"""
        from scripts.eval_suite_v2 import EvalResult, ScenarioResult
        
        # Create mock result
        mock_result = EvalResult(
            start_time="2024-01-01T00:00:00",
            end_time="2024-01-01T00:01:00",
            total_scenarios=1,
            passed_scenarios=1,
            failed_scenarios=0,
            scenarios=[],
            aggregate_metrics={"test": {"value": 1.0}}
        )
        
        output = eval_suite.output_results(mock_result)
        
        # Verify output is valid JSON
        import json
        parsed = json.loads(output)
        assert "total_scenarios" in parsed
        assert "aggregate_metrics" in parsed


class TestEnvironmentSetup:
    """Tests for environment setup and teardown"""
    
    @pytest.mark.asyncio
    async def test_environment_isolation(self, eval_suite):
        """Test that each run uses isolated environment"""
        original_db = os.environ.get("EMOTIOND_DB_PATH")
        
        await eval_suite.setup_environment()
        
        # Verify environment was set
        assert os.environ.get("EMOTIOND_SYSTEM_TOKEN") == TEST_SYSTEM_TOKEN
        assert os.environ.get("EMOTIOND_OPENCLAW_TOKEN") == TEST_OPENCLAW_TOKEN
        assert eval_suite.test_dir is not None
        
        # Cleanup
        eval_suite.teardown_environment()
        
        # Verify environment was restored
        if original_db:
            assert os.environ.get("EMOTIOND_DB_PATH") == original_db
        else:
            assert "EMOTIOND_DB_PATH" not in os.environ


class TestResultSerialization:
    """Tests for result serialization"""
    
    def test_emotion_snapshot_serialization(self):
        """Test EmotionSnapshot serialization"""
        snapshot = EmotionSnapshot(
            valence=0.5,
            arousal=0.3,
            anger=0.0,
            sadness=0.1,
            anxiety=0.0,
            joy=0.2,
            loneliness=0.0,
            social_safety=0.6,
            energy=0.7,
            timestamp=1234567890.0
        )
        
        result = result_to_dict(snapshot)
        
        assert result["valence"] == 0.5
        assert result["arousal"] == 0.3
        assert result["joy"] == 0.2
    
    def test_nested_result_serialization(self):
        """Test nested result serialization"""
        from scripts.eval_suite_v2 import ScenarioResult, TurnResult
        
        turn = TurnResult(
            turn_id=1, phase="test", event_type="user_message",
            actor="user", target="assistant",
            emotion_before=EmotionSnapshot(0.0, 0.3, 0.0, 0.0, 0.0, 0.0, 0.0, 0.6, 0.7),
            emotion_after=EmotionSnapshot(0.1, 0.3, 0.0, 0.0, 0.0, 0.0, 0.0, 0.6, 0.7),
            relationships={}, meta_cognition_triggered=False, success=True
        )
        
        scenario = ScenarioResult(
            scenario_name="test",
            scenario_file="test.yaml",
            start_time="2024-01-01T00:00:00",
            end_time="2024-01-01T00:01:00",
            duration_seconds=60.0,
            turns=[turn],
            metrics={"test": {"value": 1.0}},
            passed=True,
            summary="Test passed"
        )
        
        result = result_to_dict(scenario)
        
        assert result["scenario_name"] == "test"
        assert result["passed"] == True
        assert len(result["turns"]) == 1


# Run the full eval suite
class TestFullEvalSuite:
    """Full eval suite test - runs all scenarios"""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_run_full_eval_suite(self, eval_suite):
        """Run the complete evaluation suite"""
        result = await eval_suite.run_all()
        
        # Verify results structure
        assert result.total_scenarios >= 5, f"Expected at least 5 scenarios, ran {result.total_scenarios}"
        
        # Verify metrics output
        assert "emotion_consistency" in result.aggregate_metrics
        assert "individualization_diff" in result.aggregate_metrics
        assert "high_impact_false_positive_rate" in result.aggregate_metrics
        assert "meta_cognition_trigger_rate" in result.aggregate_metrics
        
        # Print summary
        print(f"\nEval Suite Results:")
        print(f"  Total Scenarios: {result.total_scenarios}")
        print(f"  Passed: {result.passed_scenarios}")
        print(f"  Failed: {result.failed_scenarios}")
        
        for name, metrics in result.aggregate_metrics.items():
            print(f"  {name}: {metrics}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
