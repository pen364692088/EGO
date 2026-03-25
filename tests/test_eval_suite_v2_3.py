"""
MVP-6.1 D2 Tests: Eval Suite v2.3 - Individualization Decomposition + Dynamic Thresholds

Tests for:
- Individualization diff decomposition (5 subscores: bond, ledger, somatic, policy, precision)
- Dynamic thresholds by n_obs
- Eval version bump to v2.3
- Failure reason decomposition
- No false leakage detection on global shared quantities
"""

import pytest
import sys
import os
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass, field
from typing import Dict, Any, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the eval suite v2.3 components
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import importlib.util
spec = importlib.util.spec_from_file_location("eval_suite_v2_3", 
    Path(__file__).parent.parent / "scripts" / "eval_suite_v2_3.py")
eval_suite_v2_3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eval_suite_v2_3)

from eval_suite_v2_3 import (
    DynamicThreshold,
    DYNAMIC_THRESHOLDS,
    IndividualizationSubscores,
    IndividualizationAnalyzer,
    FailureReason,
    ScenarioRunner,
    EvalSuiteV2_3,
    BodyTelemetryTracker,
    RecoveryAnalyzer,
    ConsequenceTagger
)


class TestDynamicThresholds:
    """Test dynamic threshold configuration and behavior."""
    
    def test_threshold_by_n_obs_low(self):
        """Test that low n_obs (<10) uses relaxed threshold."""
        dt = DynamicThreshold("test_metric", 0.1, 0.05, 0.15)
        
        # Low n_obs should use low_n_obs_threshold
        assert dt.get_threshold(5) == 0.05
        assert dt.get_threshold(9) == 0.05
        
    def test_threshold_by_n_obs_high(self):
        """Test that high n_obs (>=10) uses strict threshold."""
        dt = DynamicThreshold("test_metric", 0.1, 0.05, 0.15)
        
        # High n_obs should use high_n_obs_threshold
        assert dt.get_threshold(10) == 0.15
        assert dt.get_threshold(50) == 0.15
        assert dt.get_threshold(100) == 0.15
        
    def test_diff_metric_check_pass(self):
        """Test pass/fail check for diff metrics (higher is better)."""
        dt = DynamicThreshold("bond_diff", 0.1, 0.05, 0.15, is_diff_metric=True)
        
        # Low n_obs, value above threshold
        passed, severity = dt.check_pass(0.08, 5)
        assert passed is True
        assert severity < 0.5
        
        # Low n_obs, value below threshold
        passed, severity = dt.check_pass(0.02, 5)
        assert passed is False
        assert severity > 0.5
        
    def test_rate_metric_check_pass(self):
        """Test pass/fail check for rate metrics (lower is better)."""
        dt = DynamicThreshold("fp_rate", 0.1, 0.15, 0.05, is_diff_metric=False)
        
        # High n_obs, value below strict threshold
        passed, severity = dt.check_pass(0.03, 10)
        assert passed is True
        
        # High n_obs, value above strict threshold
        passed, severity = dt.check_pass(0.08, 10)
        assert passed is False
        
    def test_dynamic_thresholds_defined(self):
        """Test that all required dynamic thresholds are defined."""
        required_metrics = [
            "bond_diff",
            "ledger_diff", 
            "somatic_residual_diff",
            "policy_diff",
            "precision_diff",
            "high_impact_false_positive_rate"
        ]
        
        for metric in required_metrics:
            assert metric in DYNAMIC_THRESHOLDS
            

    def test_n_obs_boundary_safe_int_conversion(self):
        """n_obs_boundary must be int-coercible and comparison direction must stay correct."""
        dt = DynamicThreshold("test_metric", 0.1, 0.05, 0.15, n_obs_boundary="10")
        assert isinstance(dt.n_obs_boundary, int)
        assert dt.get_threshold(9) == 0.05
        assert dt.get_threshold(10) == 0.15

    def test_two_fixed_inputs_threshold_direction(self):
        """Two fixed inputs verify relax(<boundary) and strict(>=boundary) directions."""
        dt = DynamicThreshold("test_metric", 0.1, 0.01, 0.2, n_obs_boundary=10)
        low = dt.get_threshold(3)
        high = dt.get_threshold(20)
        assert low < high
    def test_threshold_transparency(self):
        """Test that threshold rules are transparent and auditable."""
        for name, dt in DYNAMIC_THRESHOLDS.items():
            assert dt.metric_name == name
            assert dt.base_threshold >= 0
            assert dt.low_n_obs_threshold >= 0
            assert dt.high_n_obs_threshold >= 0
            assert dt.n_obs_boundary == 10


class TestIndividualizationSubscores:
    """Test individualization subscores data structure."""
    
    def test_subscore_initialization(self):
        """Test that subscores initialize correctly."""
        subscores = IndividualizationSubscores()
        
        assert subscores.bond_diff == 0.0
        assert subscores.ledger_diff == 0.0
        assert subscores.somatic_residual_diff == 0.0
        assert subscores.policy_diff == 0.0
        assert subscores.precision_diff == 0.0
        
        assert subscores.bond_diff_passed is False
        assert subscores.ledger_diff_passed is False
        
    def test_calculate_aggregate(self):
        """Test aggregate score calculation with weights."""
        subscores = IndividualizationSubscores()
        subscores.bond_diff = 0.2
        subscores.ledger_diff = 0.1
        subscores.somatic_residual_diff = 0.15
        subscores.policy_diff = 0.1
        subscores.precision_diff = 0.1
        
        aggregate = subscores.calculate_aggregate()
        
        # Expected: 0.2*0.25 + 0.1*0.20 + 0.15*0.25 + 0.1*0.15 + 0.1*0.15
        expected = 0.2*0.25 + 0.1*0.20 + 0.15*0.25 + 0.1*0.15 + 0.1*0.15
        assert abs(aggregate - expected) < 0.001
        
    def test_all_passed(self):
        """Test all_passed check."""
        subscores = IndividualizationSubscores()
        assert subscores.all_passed() is False
        
        subscores.bond_diff_passed = True
        subscores.ledger_diff_passed = True
        subscores.somatic_residual_diff_passed = True
        subscores.policy_diff_passed = True
        subscores.precision_diff_passed = True
        
        assert subscores.all_passed() is True
        
    def test_to_dict(self):
        """Test conversion to dictionary."""
        subscores = IndividualizationSubscores()
        subscores.bond_diff = 0.15
        subscores.bond_diff_passed = True
        subscores.target_n_obs = {"target_a": 15, "target_b": 5}
        subscores.failure_reasons = ["test_reason"]
        
        result = subscores.to_dict()
        
        assert result["bond_diff"]["value"] == 0.15
        assert result["bond_diff"]["passed"] is True
        assert result["target_n_obs"]["target_a"] == 15
        assert "test_reason" in result["failure_reasons"]


class TestIndividualizationAnalyzer:
    """Test individualization analyzer functionality."""
    
    @pytest.fixture
    def analyzer(self):
        return IndividualizationAnalyzer()
        
    def test_record_turn(self, analyzer):
        """Test recording turn data."""
        from eval_suite_v2_3 import TurnResult, EmotionSnapshot, RelationshipSnapshot
        
        turn = TurnResult(
            turn_id=1,
            phase="test",
            event_type="user_message",
            actor="user_a",
            target="assistant"
        )
        turn.relationships = {
            "user_a": RelationshipSnapshot(
                target_id="user_a",
                bond=0.7,
                grudge=0.0,
                trust=0.6,
                repair_bank=0.0,
                promises=[],
                violations=[],
                n_obs=5
            )
        }
        
        analyzer.record_turn(turn)
        
        assert analyzer.target_n_obs["user_a"] == 1
        assert len(analyzer.target_bonds["user_a"]) == 1
        assert analyzer.target_bonds["user_a"][0] == 0.7
        
    def test_calculate_bond_diff_single_target(self, analyzer):
        """Test bond diff with single target returns 0."""
        analyzer.target_bonds["target_a"] = [0.5, 0.6, 0.7]
        
        diff = analyzer.calculate_bond_diff()
        assert diff == 0.0
        
    def test_calculate_bond_diff_multiple_targets(self, analyzer):
        """Test bond diff with multiple targets."""
        analyzer.target_bonds["target_a"] = [0.8, 0.8, 0.8]  # avg 0.8
        analyzer.target_bonds["target_b"] = [0.3, 0.3, 0.3]  # avg 0.3
        
        diff = analyzer.calculate_bond_diff()
        assert diff > 0  # Should detect difference
        
    def test_calculate_ledger_diff(self, analyzer):
        """Test ledger diff calculation."""
        analyzer.target_ledgers["target_a"]["promises"] = [{}, {}, {}]  # 3 promises
        analyzer.target_ledgers["target_b"]["promises"] = [{}]  # 1 promise
        
        diff = analyzer.calculate_ledger_diff()
        assert diff > 0  # Should detect difference
        
    def test_is_likely_global_influence_low_variance(self, analyzer):
        """Test detection of global influence via low variance."""
        target_values = {"a": 0.51, "b": 0.50, "c": 0.49}  # Low variance
        
        is_global = analyzer.is_likely_global_influence("energy", target_values)
        assert is_global is True
        
    def test_is_likely_global_influence_high_variance(self, analyzer):
        """Test that high variance is not flagged as global."""
        target_values = {"a": 0.9, "b": 0.1, "c": 0.5}  # High variance
        
        is_global = analyzer.is_likely_global_influence("bond", target_values)
        assert is_global is False
        
    def test_calculate_subscores(self, analyzer):
        """Test complete subscore calculation."""
        analyzer.target_bonds["target_a"] = [0.8]
        analyzer.target_bonds["target_b"] = [0.3]
        analyzer.target_n_obs["target_a"] = 15
        analyzer.target_n_obs["target_b"] = 15
        
        subscores = analyzer.calculate_subscores()
        
        assert isinstance(subscores, IndividualizationSubscores)
        assert "target_a" in subscores.target_n_obs
        assert "target_b" in subscores.target_n_obs
        
    def test_no_false_leakage_on_global_metrics(self, analyzer):
        """Test that global metrics don't trigger false leakage."""
        # Simulate global energy depletion affecting all targets similarly
        analyzer.target_bonds["target_a"] = [0.51, 0.50, 0.49]
        analyzer.target_bonds["target_b"] = [0.50, 0.49, 0.48]
        
        # This should be detected as global influence, not leakage
        is_global = analyzer.is_likely_global_influence("energy", {
            "target_a": 0.5, "target_b": 0.49
        })
        
        assert is_global is True


class TestFailureReasons:
    """Test failure reason enumeration and usage."""
    
    def test_failure_reason_values(self):
        """Test that all failure reasons are properly defined."""
        reasons = list(FailureReason)
        
        assert FailureReason.BOND_DIFF_TOO_LOW in reasons
        assert FailureReason.LEDGER_DIFF_TOO_LOW in reasons
        assert FailureReason.SOMATIC_RESIDUAL_DIFF_TOO_LOW in reasons
        assert FailureReason.POLICY_DIFF_TOO_LOW in reasons
        assert FailureReason.PRECISION_DIFF_TOO_LOW in reasons
        assert FailureReason.HIGH_IMPACT_FALSE_POSITIVE in reasons
        assert FailureReason.RECOVERY_FAILED in reasons
        assert FailureReason.EMOTION_INCONSISTENT in reasons
        
    def test_failure_reason_strings(self):
        """Test that failure reason strings are descriptive."""
        assert "bond_diff" in FailureReason.BOND_DIFF_TOO_LOW.value
        assert "ledger_diff" in FailureReason.LEDGER_DIFF_TOO_LOW.value
        assert "somatic_residual_diff" in FailureReason.SOMATIC_RESIDUAL_DIFF_TOO_LOW.value


class TestEvalV23Version:
    """Test eval suite version information."""
    
    def test_version_number(self):
        """Test that version is v2.3.0."""
        from eval_suite_v2_3 import EvalResult
        
        result = EvalResult()
        assert result.version == "2.3.0"
        
    def test_version_in_output(self):
        """Test that version appears in output."""
        from eval_suite_v2_3 import EvalResult
        
        result = EvalResult()
        result_dict = result.__dict__
        
        assert "version" in result_dict
        assert result_dict["version"] == "2.3.0"


class TestIntegration:
    """Integration tests for eval v2.3."""
    
    def test_dynamic_threshold_integration(self):
        """Test dynamic thresholds integrate with subscores."""
        analyzer = IndividualizationAnalyzer()
        
        # Setup with varying n_obs
        analyzer.target_bonds["target_a"] = [0.8]
        analyzer.target_bonds["target_b"] = [0.3]
        analyzer.target_n_obs["target_a"] = 5  # Low n_obs
        analyzer.target_n_obs["target_b"] = 5
        
        subscores = analyzer.calculate_subscores()
        
        # With low n_obs, threshold should be relaxed (0.05)
        # Bond diff of 0.5 should pass relaxed threshold
        assert subscores.bond_diff > 0
        
    def test_subscore_failure_reasons(self):
        """Test that failure reasons are properly generated."""
        analyzer = IndividualizationAnalyzer()
        
        # Setup with no differentiation (should fail)
        analyzer.target_bonds["target_a"] = [0.5]
        analyzer.target_bonds["target_b"] = [0.5]  # Same as a - no diff
        analyzer.target_n_obs["target_a"] = 100  # High n_obs = strict
        analyzer.target_n_obs["target_b"] = 100
        
        subscores = analyzer.calculate_subscores()
        
        # Should have failure reasons
        assert len(subscores.failure_reasons) > 0

    def test_negative_sanity_forced_no_differentiation_fails(self):
        """If bond/ledger/residual/precision are forced identical, at least one submetric must fail."""
        analyzer = IndividualizationAnalyzer()
        for tid in ("target_a", "target_b"):
            analyzer.target_bonds[tid] = [0.5, 0.5]
            analyzer.target_ledgers[tid]["promises"] = [{}]
            analyzer.target_ledgers[tid]["violations"] = []
            analyzer.target_somatic_residuals[tid]["safety_stress"] = [0.0, 0.0]
            analyzer.target_somatic_residuals[tid]["social_need"] = [0.0, 0.0]
            analyzer.target_somatic_residuals[tid]["novelty_need"] = [0.0, 0.0]
            analyzer.target_precision[tid]["w_action"] = [0.7, 0.7]
            analyzer.target_precision[tid]["w_memory"] = [0.6, 0.6]
            analyzer.target_policies[tid] = ["observe", "observe"]
            analyzer.target_n_obs[tid] = 20

        subscores = analyzer.calculate_subscores()
        assert not subscores.all_passed()
        assert len(subscores.failure_reasons) >= 1



class TestBodyTelemetryTracker:
    """Test body telemetry tracking."""
    
    def test_record_snapshot(self):
        """Test recording telemetry snapshot."""
        tracker = BodyTelemetryTracker()
        
        mock_emotion = Mock()
        mock_emotion.valence = 0.5
        mock_emotion.arousal = 0.3
        mock_emotion.energy = 0.7
        mock_emotion.social_safety = 0.6
        mock_emotion.anxiety = 0.1
        mock_emotion.joy = 0.4
        mock_emotion.loneliness = 0.2
        mock_emotion.regulation_budget = 1.0
        
        tracker.record(1, mock_emotion, {"target_a": {"stress": 0.3}})
        
        assert len(tracker.snapshots) == 1
        assert tracker.snapshots[0].turn_id == 1
        assert tracker.snapshots[0].target_residuals["target_a"]["stress"] == 0.3
        
    def test_calculate_metrics_empty(self):
        """Test metrics calculation with no snapshots."""
        tracker = BodyTelemetryTracker()
        
        metrics = tracker.calculate_metrics()
        assert metrics == {}


class TestRecoveryAnalyzer:
    """Test recovery analysis."""
    
    def test_recovery_metrics_no_windows(self):
        """Test recovery metrics when no recovery windows."""
        analyzer = RecoveryAnalyzer()
        
        metrics = analyzer.calculate_metrics()
        
        assert metrics["recovery_count"] == 0
        assert metrics["recovery_rate"] == 1.0  # No failures
        assert metrics["avg_half_life"] == 0


class TestConsequenceTagger:
    """Test consequence tagging."""
    
    def test_tag_turn_no_emotion(self):
        """Test tagging when no emotion data."""
        tagger = ConsequenceTagger()
        
        from eval_suite_v2_3 import TurnResult
        turn = TurnResult(
            turn_id=1,
            phase="test",
            event_type="user_message",
            actor="user",
            target="assistant"
        )
        
        tags = tagger.tag_turn(turn)
        assert tags == []
        
    def test_calculate_distribution_empty(self):
        """Test distribution calculation with no tags."""
        tagger = ConsequenceTagger()
        
        dist = tagger.calculate_distribution([])
        
        assert dist["total"] == 0
        assert dist["unique_tags"] == 0


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
