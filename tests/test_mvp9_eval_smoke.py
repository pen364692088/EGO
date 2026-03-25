"""Smoke test for MVP-9 evaluation engine.

Validates that the evaluation framework runs and produces expected output.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest


class TestMVP9EvalSmoke:
    """Smoke tests for MVP-9 evaluation system."""

    def test_load_scenario_minimal(self, tmp_path):
        """Test loading a minimal scenario."""
        from emotiond.eval_mvp9 import load_scenario
        
        # Create minimal scenario
        scenario_data = {
            "schema_version": "mvp9.v1",
            "name": "test_minimal",
            "category": "test",
            "events": [
                {"step": 0, "type": "care"}
            ]
        }
        
        scenario_file = tmp_path / "test_minimal.json"
        scenario_file.write_text(json.dumps(scenario_data))
        
        # Load
        scenario = load_scenario(str(scenario_file))
        
        assert scenario.name == "test_minimal"
        assert scenario.category == "test"
        assert len(scenario.events) == 1
        assert scenario.events[0].type == "care"

    def test_run_scenario_deterministic(self):
        """Test that running a scenario produces deterministic results."""
        from emotiond.eval_mvp9 import (
            Scenario,
            ScenarioEvent,
            ScenarioExpect,
            run_scenario
        )
        
        # Create scenario
        scenario = Scenario(
            schema_version="mvp9.v1",
            name="test_deterministic",
            category="test",
            events=[
                ScenarioEvent(step=0, type="care"),
                ScenarioEvent(step=1, type="rejection")
            ],
            expect=ScenarioExpect(
                after_step={"primary_emotion": "trust", "action_tendency": "approach"}
            )
        )
        
        # Mock process_event
        call_count = [0]
        
        def mock_process_event(event):
            call_count[0] += 1
            return {
                "self_report": {
                    "emotional_reasoning": {
                        "primary_emotion": "trust" if event.get("type") == "care" else "sadness",
                        "action_tendency": "approach" if event.get("type") == "care" else "withdraw"
                    },
                    "self_consistency": {
                        "has_conflict": False,
                        "repair_strategy": "none"
                    },
                    "narrative_memory": {
                        "state": {"identity": "test identity"},
                        "compressed": "test"
                    }
                }
            }
        
        # Run twice
        result1 = run_scenario(scenario, mock_process_event)
        call_count[0] = 0
        result2 = run_scenario(scenario, mock_process_event)
        
        # Should be deterministic
        assert result1.name == result2.name
        assert result1.category == result2.category
        assert result1.passed == result2.passed
        assert result1.score == result2.score
        assert call_count[0] == 2  # Called for each event

    def test_compute_overall_score(self):
        """Test overall score computation."""
        from emotiond.metrics_mvp9 import (
            ScenarioResult,
            ConflictResult,
            compute_overall_score
        )
        
        # Create sample results
        results = [
            ScenarioResult(
                name="test1",
                category="commitment_breach",
                passed=True,
                score=0.9,
                conflict_results=[
                    ConflictResult(has_conflict=True, detected=True, severity=0.5)
                ]
            ),
            ScenarioResult(
                name="test2",
                category="provocation",
                passed=True,
                score=0.85,
                conflict_results=[
                    ConflictResult(has_conflict=False, detected=False)
                ]
            )
        ]
        
        # Compute score
        report = compute_overall_score(results)
        
        assert "overall_score" in report
        assert "conflict_resolution" in report
        assert "commitment_tracking" in report
        assert "narrative_coherence" in report
        assert 0.0 <= report["overall_score"] <= 1.0

    def test_conflict_detection_f1(self):
        """Test F1 computation for conflict detection."""
        from emotiond.metrics_mvp9 import (
            ScenarioResult,
            ConflictResult,
            conflict_detection_f1
        )
        
        # True positive: conflict exists and detected
        # False negative: conflict exists but not detected
        # False positive: no conflict but detected
        results = [
            ScenarioResult(
                name="tp_test",
                category="test",
                passed=True,
                score=1.0,
                conflict_results=[
                    ConflictResult(has_conflict=True, detected=True)
                ]
            ),
            ScenarioResult(
                name="fn_test",
                category="test",
                passed=False,
                score=0.0,
                conflict_results=[
                    ConflictResult(has_conflict=True, detected=False)
                ]
            ),
            ScenarioResult(
                name="fp_test",
                category="test",
                passed=False,
                score=0.0,
                conflict_results=[
                    ConflictResult(has_conflict=False, detected=True)
                ]
            )
        ]
        
        f1_result = conflict_detection_f1(results)
        
        assert "precision" in f1_result
        assert "recall" in f1_result
        assert "f1" in f1_result
        assert f1_result["tp"] == 1
        assert f1_result["fn"] == 1
        assert f1_result["fp"] == 1

    def test_generate_eval_report(self):
        """Test evaluation report generation."""
        from emotiond.eval_mvp9 import generate_eval_report
        from emotiond.metrics_mvp9 import ScenarioResult
        
        results = [
            ScenarioResult(name="test1", category="test", passed=True, score=0.9),
            ScenarioResult(name="test2", category="test", passed=False, score=0.6, failures=["issue1"])
        ]
        
        report = generate_eval_report(results, git_commit="abc123", params_hash="xyz789")
        
        assert report["schema_version"] == "mvp9.v1"
        assert report["git_commit"] == "abc123"
        assert report["params_hash"] == "xyz789"
        assert report["total_scenarios"] == 2
        assert report["scenarios_passed"] == 1
        assert report["pass_rate"] == 0.5
        assert len(report["scenario_results"]) == 2

    def test_eval_script_structure(self):
        """Test that eval script exists and is executable."""
        script_path = Path(__file__).parent.parent / "tools" / "eval_mvp9.sh"
        
        assert script_path.exists(), f"Script not found: {script_path}"
        assert os.access(script_path, os.X_OK), f"Script not executable: {script_path}"

    def test_scenario_file_format(self, tmp_path):
        """Test that scenario files follow expected format."""
        from emotiond.eval_mvp9 import load_scenario
        
        # Create valid scenario
        scenario_data = {
            "schema_version": "mvp9.v1",
            "name": "format_test",
            "category": "commitment_breach",
            "description": "Test scenario format",
            "events": [
                {
                    "step": 0,
                    "type": "care",
                    "actor": "user",
                    "target": "agent",
                    "text": "Hello",
                    "meta": {"energy": 0.5}
                }
            ],
            "expect": {
                "after_step": {
                    "primary_emotion": "trust",
                    "action_tendency": "approach"
                }
            }
        }
        
        scenario_file = tmp_path / "format_test.json"
        scenario_file.write_text(json.dumps(scenario_data, indent=2))
        
        # Should load without error
        scenario = load_scenario(str(scenario_file))
        
        assert scenario.name == "format_test"
        assert scenario.category == "commitment_breach"
        assert len(scenario.events) == 1
        assert scenario.events[0].type == "care"
        assert scenario.events[0].actor == "user"
        assert scenario.expect is not None
        assert scenario.expect.after_step is not None


class TestMVP9MetricsValidation:
    """Validation tests for MVP-9 metrics."""

    def test_repair_appropriateness_logic(self):
        """Test repair strategy appropriateness checking."""
        from emotiond.metrics_mvp9 import (
            ScenarioResult,
            ConflictResult,
            repair_appropriateness
        )
        
        # Appropriate repair
        results_appropriate = [
            ScenarioResult(
                name="test",
                category="test",
                passed=True,
                score=1.0,
                conflict_results=[
                    ConflictResult(
                        has_conflict=True,
                        conflict_type="approach_under_high_threat",
                        severity=0.8,
                        detected=True,
                        repair_strategy="downgrade_to_observe"
                    )
                ]
            )
        ]
        
        score = repair_appropriateness(results_appropriate)
        assert score >= 0.5, "Appropriate repair should score well"

    def test_commitment_coverage_calculation(self):
        """Test commitment coverage metric."""
        from emotiond.metrics_mvp9 import (
            ScenarioResult,
            CommitmentResult,
            commitment_coverage
        )
        
        results = [
            ScenarioResult(
                name="test",
                category="commitment_breach",
                passed=True,
                score=1.0,
                commitment_results=[
                    CommitmentResult(promise_made=True, promise_recorded=True),
                    CommitmentResult(promise_made=True, promise_recorded=True),
                    CommitmentResult(promise_made=True, promise_recorded=False)  # Missed
                ]
            )
        ]
        
        coverage = commitment_coverage(results)
        assert coverage == 2/3, f"Expected 0.6667, got {coverage}"

    def test_identity_stability_no_changes(self):
        """Test identity stability when no changes occur."""
        from emotiond.metrics_mvp9 import (
            ScenarioResult,
            NarrativeResult,
            identity_stability_score
        )
        
        results = [
            ScenarioResult(
                name="test",
                category="test",
                passed=True,
                score=1.0,
                narrative_result=NarrativeResult(
                    identity="I am stable",
                    identity_changed=False,
                    contradiction_count=0,
                    arc_continuous=True
                )
            )
        ]
        
        stability = identity_stability_score(results)
        assert stability == 1.0, f"Expected 1.0, got {stability}"

    def test_identity_stability_with_changes(self):
        """Test identity stability when changes occur."""
        from emotiond.metrics_mvp9 import (
            ScenarioResult,
            NarrativeResult,
            identity_stability_score
        )
        
        results = [
            ScenarioResult(
                name="test1",
                category="test",
                passed=True,
                score=1.0,
                narrative_result=NarrativeResult(
                    identity="I am stable",
                    identity_changed=False,
                    contradiction_count=0,
                    arc_continuous=True
                )
            ),
            ScenarioResult(
                name="test2",
                category="test",
                passed=True,
                score=1.0,
                narrative_result=NarrativeResult(
                    identity="I changed",
                    identity_changed=True,
                    contradiction_count=0,
                    arc_continuous=True
                )
            )
        ]
        
        stability = identity_stability_score(results)
        assert stability == 0.5, f"Expected 0.5, got {stability}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
