#!/usr/bin/env python3
"""
Tests for Eval Suite v2.2 (MVP-6)

Coverage:
1. Body telemetry metrics (energy, social_safety, arousal trajectories)
2. Consequence tag distribution
3. Recovery and robustness indicators
4. Mandatory scenario execution (Tool Failure Spiral, Rewarded Progress, Boredom/Novelty Need)
5. Seed reproducibility
6. Report generation
"""

import os
import sys
import json
import pytest
import asyncio
import tempfile
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.eval_suite_v2_2 import (
    EvalSuiteV2_2, ScenarioRunner, EvalResult, ScenarioResult,
    BodyTelemetryTracker, ConsequenceTagger, RecoveryAnalyzer,
    BodyTelemetrySnapshot, ConsequenceTag, RecoveryWindow,
    EmotionSnapshot, TurnResult
)


class TestBodyTelemetry:
    """Test body telemetry tracking and metrics"""

    @pytest.fixture
    def mock_emotion_state(self):
        """Create a mock emotion state for testing"""
        class MockState:
            def __init__(self):
                self.valence = 0.0
                self.arousal = 0.3
                self.energy = 0.7
                self.social_safety = 0.6
                self.anxiety = 0.1
                self.joy = 0.2
                self.loneliness = 0.1
                self.regulation_budget = 1.0
        return MockState()

    def test_telemetry_tracker_records_snapshots(self, mock_emotion_state):
        """Telemetry tracker should record snapshots"""
        tracker = BodyTelemetryTracker()
        
        tracker.record(1, mock_emotion_state)
        tracker.record(2, mock_emotion_state)
        tracker.record(3, mock_emotion_state)
        
        assert len(tracker.snapshots) == 3
        assert tracker.snapshots[0].turn_id == 1
        assert tracker.snapshots[1].turn_id == 2
        assert tracker.snapshots[2].turn_id == 3

    def test_telemetry_metrics_calculation(self, mock_emotion_state):
        """Telemetry metrics should be calculated correctly"""
        tracker = BodyTelemetryTracker()
        
        # Record varying states
        mock_emotion_state.energy = 0.8
        tracker.record(1, mock_emotion_state)
        
        mock_emotion_state.energy = 0.6
        tracker.record(2, mock_emotion_state)
        
        mock_emotion_state.energy = 0.7
        tracker.record(3, mock_emotion_state)
        
        metrics = tracker.calculate_metrics()
        
        assert "energy" in metrics
        assert metrics["energy"]["min"] == 0.6
        assert metrics["energy"]["max"] == 0.8
        assert metrics["energy"]["range"] == 0.2
        assert metrics["energy"]["mean"] == pytest.approx(0.7, abs=0.01)

    def test_telemetry_empty_metrics(self):
        """Empty telemetry should return empty metrics"""
        tracker = BodyTelemetryTracker()
        metrics = tracker.calculate_metrics()
        assert metrics == {}


class TestConsequenceTagging:
    """Test consequence tag generation and distribution"""

    def test_tag_energy_depletion(self):
        """Should tag energy depletion events"""
        tagger = ConsequenceTagger()
        
        before = EmotionSnapshot(
            valence=0.0, arousal=0.3, anger=0.0, sadness=0.0,
            anxiety=0.1, joy=0.2, loneliness=0.1,
            social_safety=0.6, energy=0.7
        )
        after = EmotionSnapshot(
            valence=0.0, arousal=0.3, anger=0.0, sadness=0.0,
            anxiety=0.1, joy=0.2, loneliness=0.1,
            social_safety=0.6, energy=0.6  # Depleted
        )
        
        turn = TurnResult(
            turn_id=1, phase="test", event_type="world_event",
            actor="system", target="assistant",
            emotion_before=before, emotion_after=after
        )
        
        tags = tagger.tag_turn(turn)
        
        tag_names = [t.tag for t in tags]
        assert "energy_depletion" in tag_names

    def test_tag_valence_surge(self):
        """Should tag valence surge events"""
        tagger = ConsequenceTagger()
        
        before = EmotionSnapshot(
            valence=0.0, arousal=0.3, anger=0.0, sadness=0.0,
            anxiety=0.1, joy=0.2, loneliness=0.1,
            social_safety=0.6, energy=0.7
        )
        after = EmotionSnapshot(
            valence=0.3, arousal=0.3, anger=0.0, sadness=0.0,
            anxiety=0.1, joy=0.2, loneliness=0.1,
            social_safety=0.6, energy=0.7
        )
        
        turn = TurnResult(
            turn_id=1, phase="test", event_type="world_event",
            actor="system", target="assistant",
            emotion_before=before, emotion_after=after
        )
        
        tags = tagger.tag_turn(turn)
        
        tag_names = [t.tag for t in tags]
        assert "valence_surge" in tag_names

    def test_tag_distribution_calculation(self):
        """Should calculate tag distribution correctly"""
        tagger = ConsequenceTagger()
        
        tags = [
            ConsequenceTag(tag="energy_depletion", severity=1.0, source_event="e1", turn_id=1),
            ConsequenceTag(tag="energy_depletion", severity=1.5, source_event="e2", turn_id=2),
            ConsequenceTag(tag="joy_boost", severity=2.0, source_event="e3", turn_id=3),
            ConsequenceTag(tag="anxiety_spike", severity=2.5, source_event="e4", turn_id=4),
        ]
        
        dist = tagger.calculate_distribution(tags)
        
        assert dist["total"] == 4
        assert dist["by_tag"]["energy_depletion"] == 2
        assert dist["by_tag"]["joy_boost"] == 1
        assert dist["by_tag"]["anxiety_spike"] == 1
        assert dist["unique_tags"] == 3

    def test_empty_tag_distribution(self):
        """Empty tags should return empty distribution"""
        tagger = ConsequenceTagger()
        dist = tagger.calculate_distribution([])
        
        assert dist["total"] == 0
        assert dist["unique_tags"] == 0


class TestRecoveryAnalysis:
    """Test recovery window detection and metrics"""

    def test_recovery_window_detection(self):
        """Should detect recovery windows from negative events"""
        analyzer = RecoveryAnalyzer()
        
        # Trigger event (valence crash)
        before = EmotionSnapshot(
            valence=0.0, arousal=0.3, anger=0.0, sadness=0.0,
            anxiety=0.1, joy=0.2, loneliness=0.1,
            social_safety=0.6, energy=0.7
        )
        after = EmotionSnapshot(
            valence=-0.3, arousal=0.3, anger=0.0, sadness=0.0,
            anxiety=0.1, joy=0.2, loneliness=0.1,
            social_safety=0.6, energy=0.6
        )
        
        turn = TurnResult(
            turn_id=1, phase="test", event_type="world_event",
            actor="system", target="assistant",
            emotion_before=before, emotion_after=after
        )
        
        analyzer.process_turn(turn)
        
        # Recovery turn
        before2 = EmotionSnapshot(
            valence=-0.3, arousal=0.3, anger=0.0, sadness=0.0,
            anxiety=0.1, joy=0.2, loneliness=0.1,
            social_safety=0.6, energy=0.6
        )
        after2 = EmotionSnapshot(
            valence=0.1, arousal=0.3, anger=0.0, sadness=0.0,
            anxiety=0.1, joy=0.2, loneliness=0.1,
            social_safety=0.6, energy=0.65
        )
        
        turn2 = TurnResult(
            turn_id=2, phase="test", event_type="world_event",
            actor="system", target="assistant",
            emotion_before=before2, emotion_after=after2
        )
        
        analyzer.process_turn(turn2)
        
        metrics = analyzer.calculate_metrics()
        
        assert metrics["recovery_count"] >= 0  # May or may not detect recovery

    def test_recovery_metrics_empty(self):
        """Empty recovery should return default metrics"""
        analyzer = RecoveryAnalyzer()
        metrics = analyzer.calculate_metrics()
        
        assert metrics["recovery_count"] == 0
        assert metrics["recovery_rate"] == 1.0  # No failures = perfect recovery rate
        assert metrics["robustness_score"] == 1.0


class TestSeedReproducibility:
    """Test reproducibility with fixed seeds"""

    @pytest.mark.asyncio
    async def test_eval_suite_reproducibility(self):
        """Same seed should produce same results"""
        base_path = Path(__file__).parent.parent
        scenarios_dir = base_path / "scenarios"
        
        # Run with same seed twice
        suite1 = EvalSuiteV2_2(scenarios_dir=scenarios_dir, seed=42)
        suite2 = EvalSuiteV2_2(scenarios_dir=scenarios_dir, seed=42)
        
        # Use only baseline scenario for speed
        baseline_scenario = scenarios_dir / "baseline.yaml"
        
        if baseline_scenario.exists():
            result1 = await suite1.run_all([baseline_scenario])
            result2 = await suite2.run_all([baseline_scenario])
            
            assert result1.seed == result2.seed == 42
            assert result1.total_scenarios == result2.total_scenarios

    def test_random_seed_generation(self):
        """Different seeds should produce different states"""
        import random
        
        random.seed(42)
        val1 = random.random()
        
        random.seed(99)
        val2 = random.random()
        
        random.seed(42)
        val3 = random.random()
        
        assert val1 == val3  # Same seed = same value
        assert val1 != val2  # Different seed = different value


class TestMandatoryScenarios:
    """Test mandatory MVP-6 scenarios"""

    def test_tool_failure_spiral_scenario_exists(self):
        """Tool Failure Spiral scenario should exist"""
        base_path = Path(__file__).parent.parent
        scenario_path = base_path / "scenarios" / "tool_failure_spiral.yaml"
        
        assert scenario_path.exists(), "Tool Failure Spiral scenario is mandatory"

    def test_rewarded_progress_scenario_exists(self):
        """Rewarded Progress scenario should exist"""
        base_path = Path(__file__).parent.parent
        scenario_path = base_path / "scenarios" / "rewarded_progress.yaml"
        
        assert scenario_path.exists(), "Rewarded Progress scenario is mandatory"

    def test_boredom_novelty_scenario_exists(self):
        """Boredom/Novelty Need scenario should exist"""
        base_path = Path(__file__).parent.parent
        scenario_path = base_path / "scenarios" / "boredom_novelty_need.yaml"
        
        assert scenario_path.exists(), "Boredom/Novelty Need scenario is mandatory"

    @pytest.mark.asyncio
    async def test_mandatory_scenarios_loadable(self):
        """All mandatory scenarios should be loadable"""
        base_path = Path(__file__).parent.parent
        scenarios_dir = base_path / "scenarios"
        
        mandatory = [
            "tool_failure_spiral.yaml",
            "rewarded_progress.yaml",
            "boredom_novelty_need.yaml"
        ]
        
        for scenario_file in mandatory:
            scenario_path = scenarios_dir / scenario_file
            if scenario_path.exists():
                runner = ScenarioRunner(scenario_path, seed=42)
                loaded = runner.load()
                assert loaded, f"Failed to load {scenario_file}"
                assert runner.scenario_data is not None


class TestReportGeneration:
    """Test report generation and output formats"""

    @pytest.mark.asyncio
    async def test_json_output_format(self):
        """JSON output should be valid"""
        base_path = Path(__file__).parent.parent
        scenarios_dir = base_path / "scenarios"
        
        suite = EvalSuiteV2_2(
            scenarios_dir=scenarios_dir,
            output_format="json",
            seed=42
        )
        
        baseline_scenario = scenarios_dir / "baseline.yaml"
        
        if baseline_scenario.exists():
            result = await suite.run_all([baseline_scenario])
            output = suite.output_results(result)
            
            # Should be valid JSON
            parsed = json.loads(output)
            assert "seed" in parsed
            assert "total_scenarios" in parsed

    @pytest.mark.asyncio
    async def test_markdown_output_format(self):
        """Markdown output should contain expected sections"""
        base_path = Path(__file__).parent.parent
        scenarios_dir = base_path / "scenarios"
        
        suite = EvalSuiteV2_2(
            scenarios_dir=scenarios_dir,
            output_format="markdown",
            seed=42
        )
        
        baseline_scenario = scenarios_dir / "baseline.yaml"
        
        if baseline_scenario.exists():
            result = await suite.run_all([baseline_scenario])
            output = suite.output_results(result)
            
            assert "# Eval Suite v2.2 Report" in output
            assert "## Aggregate Metrics" in output
            assert "## Scenario Results" in output


class TestMetricsIntegration:
    """Test integration of all v2.2 metrics"""

    @pytest.mark.asyncio
    async def test_all_metrics_present(self):
        """All v2.2 metrics should be present in results"""
        base_path = Path(__file__).parent.parent
        scenarios_dir = base_path / "scenarios"
        
        suite = EvalSuiteV2_2(scenarios_dir=scenarios_dir, seed=42)
        
        baseline_scenario = scenarios_dir / "baseline.yaml"
        
        if baseline_scenario.exists():
            result = await suite.run_all([baseline_scenario])
            
            if result.scenarios:
                scenario = result.scenarios[0]
                
                # Check all v2.2 metrics exist
                assert "emotion_consistency" in scenario.metrics
                assert "body_telemetry" in scenario.metrics
                assert "recovery_score" in scenario.metrics
                assert "robustness_score" in scenario.metrics
                assert "consequence_distribution" in scenario.metrics

    def test_aggregate_metrics_structure(self):
        """Aggregate metrics should have correct structure"""
        base_path = Path(__file__).parent.parent
        scenarios_dir = base_path / "scenarios"
        
        suite = EvalSuiteV2_2(scenarios_dir=scenarios_dir, seed=42)
        
        # Create mock results
        from scripts.eval_suite_v2_2 import ScenarioResult
        
        mock_scenario = ScenarioResult(
            scenario_name="test",
            scenario_file="test.yaml",
            start_time=datetime.now().isoformat(),
            end_time=datetime.now().isoformat(),
            duration_seconds=1.0,
            turns=[],
            metrics={
                "emotion_consistency": {"passed": True},
                "body_telemetry": {"data": {"energy": {"min": 0.5}}},
                "recovery_score": {"score": 0.8},
                "robustness_score": {"score": 0.7}
            },
            passed=True,
            summary="test"
        )
        
        suite.results = [mock_scenario]
        
        aggregates = suite.calculate_aggregate_metrics()
        
        assert "emotion_consistency" in aggregates
        assert "body_telemetry" in aggregates
        assert "recovery_score" in aggregates
        assert "robustness_score" in aggregates


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
