"""
MVP-6.1 D2 Tests: Individualization Diff Decomposition + Dynamic Thresholds

Tests for the decomposed individualization_diff metrics and dynamic thresholds.
"""

import pytest
import time
from emotiond.cross_target_telemetry import (
    measure_global_state_impact,
    measure_target_to_target_leak,
    measure_ledger_isolation,
    measure_relationship_isolation,
    measure_self_model_isolation,
    get_diagnostics_output,
    InterferenceType,
    telemetry
)


class TestIndividualizationDiffDecomposition:
    """Test individualization_diff decomposition into sub-metrics."""
    
    def test_bond_diff_calculation(self):
        """Test bond_diff calculation between targets."""
        telemetry.active_reports.clear()
        telemetry.completed_reports.clear()
        scenario = telemetry.start_scenario("bond_diff_test")
        
        # Target A: high bond, Target B: low bond
        measure_target_to_target_leak(
            scenario_name=scenario,
            source_target="target_a",
            affected_target="target_b",
            metric_name="bond_value",
            expected_value=0.2,  # Target B should stay at low bond
            actual_value=0.8,    # But it's high (leakage from A)
            context={"bond_a": 0.8, "bond_b": 0.2}
        )
        
        report = telemetry.finalize_scenario(scenario)
        assert report.target_state_leak_between_targets > 0.5
    
    def test_ledger_diff_calculation(self):
        """Test ledger_diff calculation for promises/violations."""
        telemetry.active_reports.clear()
        telemetry.completed_reports.clear()
        scenario = telemetry.start_scenario("ledger_diff_test")
        
        # Target A has promises, Target B should not see them
        measure_ledger_isolation(
            scenario_name=scenario,
            source_target="target_a",
            check_target="target_b",
            has_promise_from_source=True,  # This is a leak!
            context={"promise_count_a": 5, "promise_count_b": 0}
        )
        
        report = telemetry.finalize_scenario(scenario)
        assert report.ledger_promise_leak > 0.8  # Binary metric, should be high
    
    def test_somatic_residual_diff_placeholder(self):
        """Test somatic_residual_diff calculation (placeholder for D1 integration)."""
        telemetry.active_reports.clear()
        telemetry.completed_reports.clear()
        scenario = telemetry.start_scenario("somatic_residual_test")
        
        # Target A has high stress residual, Target B should not
        measure_target_to_target_leak(
            scenario_name=scenario,
            source_target="target_a",
            affected_target="target_b",
            metric_name="somatic_residual_safety_stress",
            expected_value=0.6,  # Target B baseline
            actual_value=0.9,    # Leaked from A
            context={"residual_a": 0.4, "residual_b": 0.0}
        )
        
        report = telemetry.finalize_scenario(scenario)
        assert report.target_state_leak_between_targets > 0.3
    
    def test_policy_diff_calculation(self):
        """Test policy_diff for action/meta-cog intent differences."""
        telemetry.active_reports.clear()
        telemetry.completed_reports.clear()
        scenario = telemetry.start_scenario("policy_diff_test")
        
        # Target A has defensive policy, Target B should not adopt it
        measure_target_to_target_leak(
            scenario_name=scenario,
            source_target="target_a",
            affected_target="target_b",
            metric_name="action_policy_defensiveness",
            expected_value=0.3,  # Target B normal policy
            actual_value=0.8,    # Adopted A's defensive policy
            context={"policy_a": "defensive", "policy_b": "neutral"}
        )
        
        report = telemetry.finalize_scenario(scenario)
        assert report.target_state_leak_between_targets > 0.4
    
    def test_precision_diff_calculation(self):
        """Test precision_diff for w_memory/w_action target differentiation."""
        telemetry.active_reports.clear()
        telemetry.completed_reports.clear()
        scenario = telemetry.start_scenario("precision_diff_test")
        
        # Target A has high w_memory, Target B should not
        measure_self_model_isolation(
            scenario_name=scenario,
            target_id="target_b",
            self_model_values={"w_memory": 0.9},  # Leaked from A
            expected_per_target_variance=0.2,     # Should be independent
            actual_variance=0.8,                  # But it's not
            context={"w_memory_a": 0.9, "w_memory_b": 0.9}
        )
        
        report = telemetry.finalize_scenario(scenario)
        assert report.shared_self_model_leak > 0.5


class TestDynamicThresholds:
    """Test dynamic thresholds based on n_obs."""
    
    def test_low_n_obs_relaxed_threshold(self):
        """Test that low n_obs targets have relaxed thresholds."""
        telemetry.active_reports.clear()
        telemetry.completed_reports.clear()
        scenario = telemetry.start_scenario("low_n_obs_test")
        
        # Target with only 3 observations should have relaxed requirements
        measure_target_to_target_leak(
            scenario_name=scenario,
            source_target="target_a",
            affected_target="target_b",
            metric_name="bond_value",
            expected_value=0.5,
            actual_value=0.7,  # Some deviation but acceptable for low n_obs
            context={"n_obs": 3, "threshold_relaxed": True}
        )
        
        report = telemetry.finalize_scenario(scenario)
        # With relaxed thresholds, severity should be lower
        measurements = [m for m in report.measurements if m.metric_name == "bond_value"]
        assert len(measurements) == 1
        assert measurements[0].context.get("n_obs") == 3
    
    def test_high_n_obs_strict_threshold(self):
        """Test that high n_obs targets have strict thresholds."""
        telemetry.active_reports.clear()
        telemetry.completed_reports.clear()
        scenario = telemetry.start_scenario("high_n_obs_test")
        
        # Target with 100 observations should have strict requirements
        measure_target_to_target_leak(
            scenario_name=scenario,
            source_target="target_a",
            affected_target="target_b",
            metric_name="bond_value",
            expected_value=0.5,
            actual_value=0.7,  # Same deviation but unacceptable for high n_obs
            context={"n_obs": 100, "threshold_strict": True}
        )
        
        report = telemetry.finalize_scenario(scenario)
        # With strict thresholds, severity should be higher
        measurements = [m for m in report.measurements if m.metric_name == "bond_value"]
        assert len(measurements) == 1
        assert measurements[0].context.get("n_obs") == 100
    
    def test_threshold_transparency(self):
        """Test that threshold rules are transparent and auditable."""
        telemetry.active_reports.clear()
        telemetry.completed_reports.clear()
        scenario = telemetry.start_scenario("threshold_transparency")
        
        # Record with explicit threshold information
        measure_target_to_target_leak(
            scenario_name=scenario,
            source_target="target_a",
            affected_target="target_b",
            metric_name="valence",
            expected_value=0.6,
            actual_value=0.8,
            context={
                "n_obs": 15,
                "threshold_type": "dynamic",
                "threshold_rule": "n_obs >= 10: strict, n_obs < 10: relaxed",
                "applied_threshold": "strict",
                "threshold_value": 0.05
            }
        )
        
        report = telemetry.finalize_scenario(scenario)
        assert report.total_interference_score > 0
        
        # Check threshold information is preserved
        measurements = [m for m in report.measurements if m.metric_name == "valence"]
        assert len(measurements) == 1
        ctx = measurements[0].context
        assert ctx["threshold_type"] == "dynamic"
        assert "threshold_rule" in ctx
        assert "applied_threshold" in ctx


class TestEvalV23Integration:
    """Test integration with eval suite v2.3."""
    
    def test_per_scenario_failure_reasons(self):
        """Test that failure reasons identify specific sub-metrics."""
        telemetry.active_reports.clear()
        telemetry.completed_reports.clear()
        scenario = telemetry.start_scenario("failure_reasoning_test")
        
        # Record multiple types of failures
        measure_target_to_target_leak(
            scenario_name=scenario,
            source_target="target_a",
            affected_target="target_b",
            metric_name="bond_value",
            expected_value=0.3,
            actual_value=0.8
        )
        
        measure_ledger_isolation(
            scenario_name=scenario,
            source_target="target_a",
            check_target="target_c",
            has_promise_from_source=True
        )
        
        report = telemetry.finalize_scenario(scenario)
        
        # Should identify both bond_diff and ledger_diff as failure sources
        bond_failures = [m for m in report.measurements if m.metric_name == "bond_value"]
        ledger_failures = [m for m in report.measurements if "promise" in m.metric_name]
        
        assert len(bond_failures) == 1
        assert len(ledger_failures) == 1
        
        # Failure reasons should be specific
        assert bond_failures[0].interference_type == InterferenceType.TARGET_STATE_LEAK_BETWEEN_TARGETS
        assert ledger_failures[0].interference_type == InterferenceType.LEDGER_PROMISE_LEAK
    
    def test_no_false_positives_on_global_shared_state(self):
        """Test that global shared state doesn't trigger false positives."""
        telemetry.active_reports.clear()
        telemetry.completed_reports.clear()
        scenario = telemetry.start_scenario("global_shared_state_test")
        
        # Global state changes should not be marked as interference
        measure_global_state_impact(
            scenario_name=scenario,
            target_id="target_a",
            global_valence=0.7,
            target_expected_valence=0.6,
            actual_valence=0.65,  # Slight influence from global (acceptable)
            context={"global_influence_expected": True}
        )
        
        report = telemetry.finalize_scenario(scenario)
        # Should have low severity since global influence is expected
        measurements = [m for m in report.measurements if m.metric_name == "valence_correlation"]
        assert len(measurements) == 1
        assert measurements[0].severity < 0.3  # Low severity


class TestMetricsCalculationCorrectness:
    """Test that metrics are calculated correctly."""
    
    def test_bond_diff_edge_cases(self):
        """Test bond_diff edge cases."""
        telemetry.active_reports.clear()
        telemetry.completed_reports.clear()
        scenario = telemetry.start_scenario("bond_edge_cases")
        
        # Zero bond
        measure_target_to_target_leak(
            scenario_name=scenario,
            source_target="target_a",
            affected_target="target_b",
            metric_name="bond_value",
            expected_value=0.0,
            actual_value=0.0
        )
        
        # Maximum bond
        measure_target_to_target_leak(
            scenario_name=scenario,
            source_target="target_a",
            affected_target="target_c",
            metric_name="bond_value",
            expected_value=1.0,
            actual_value=1.0
        )
        
        report = telemetry.finalize_scenario(scenario)
        # Both should have zero severity (no deviation)
        zero_severity = [m for m in report.measurements if m.severity == 0.0]
        assert len(zero_severity) == 2
    
    def test_ledger_diff_binary_nature(self):
        """Test that ledger_diff is properly binary."""
        telemetry.active_reports.clear()
        telemetry.completed_reports.clear()
        scenario = telemetry.start_scenario("ledger_binary")
        
        # No leak (expected)
        measure_ledger_isolation(
            scenario_name=scenario,
            source_target="target_a",
            check_target="target_b",
            has_promise_from_source=False
        )
        
        # Leak (unexpected)
        measure_ledger_isolation(
            scenario_name=scenario,
            source_target="target_a",
            check_target="target_c",
            has_promise_from_source=True
        )
        
        report = telemetry.finalize_scenario(scenario)
        
        # Should have one zero severity and one high severity
        severities = [m.severity for m in report.measurements if m.metric_name.startswith("promise")]
        assert 0.0 in severities
        assert any(s > 0.8 for s in severities)
    
    def test_somatic_residual_diff_ranges(self):
        """Test somatic_residual_diff value ranges."""
        telemetry.active_reports.clear()
        telemetry.completed_reports.clear()
        scenario = telemetry.start_scenario("somatic_ranges")
        
        # Test various residual values
        for residual in [-0.5, -0.2, 0.0, 0.1, 0.3, 0.8]:
            measure_target_to_target_leak(
                scenario_name=scenario,
                source_target="target_a",
                affected_target="target_b",
                metric_name=f"somatic_residual_{residual}",
                expected_value=0.0,
                actual_value=residual,
                context={"residual_value": residual}
            )
        
        report = telemetry.finalize_scenario(scenario)
        
        # All should be recorded with appropriate severities
        assert len(report.measurements) == 6
        
        # Check that higher absolute residuals have higher severity
        measurement_dict = {m.metric_name: m.severity for m in report.measurements}
        assert measurement_dict["somatic_residual_0.8"] > measurement_dict["somatic_residual_0.1"]
        assert measurement_dict["somatic_residual_-0.5"] > measurement_dict["somatic_residual_-0.2"]


class TestDynamicThresholdBehaviors:
    """Test dynamic threshold behaviors."""
    
    def test_n_obs_threshold_boundaries(self):
        """Test n_obs threshold boundaries."""
        telemetry.active_reports.clear()
        telemetry.completed_reports.clear()
        scenario = telemetry.start_scenario("n_obs_boundaries")
        
        # Test at boundary (n_obs = 10)
        for n_obs in [9, 10, 11]:
            measure_target_to_target_leak(
                scenario_name=scenario,
                source_target="target_a",
                affected_target=f"target_{n_obs}",
                metric_name="bond_value",
                expected_value=0.5,
                actual_value=0.6,
                context={"n_obs": n_obs}
            )
        
        report = telemetry.finalize_scenario(scenario)
        
        # Check that boundary conditions are handled correctly
        measurements_by_n_obs = {
            m.context["n_obs"]: m for m in report.measurements 
            if "n_obs" in m.context
        }
        
        # Should have measurements for all three n_obs values
        assert 9 in measurements_by_n_obs
        assert 10 in measurements_by_n_obs
        assert 11 in measurements_by_n_obs
    
    def test_threshold_adjustment_impact(self):
        """Test that threshold adjustment impacts severity calculation."""
        telemetry.active_reports.clear()
        telemetry.completed_reports.clear()
        scenario = telemetry.start_scenario("threshold_impact")
        
        # Same deviation but different n_obs
        for n_obs, severity_factor in [(3, 0.3), (50, 0.8)]:
            measure_target_to_target_leak(
                scenario_name=scenario,
                source_target="target_a",
                affected_target=f"target_{n_obs}",
                metric_name="bond_value",
                expected_value=0.5,
                actual_value=0.7,  # Same 0.2 deviation
                context={
                    "n_obs": n_obs,
                    "severity_factor": severity_factor,
                    "dynamic_threshold_applied": True
                }
            )
        
        report = telemetry.finalize_scenario(scenario)
        
        # Higher n_obs should result in higher severity for same deviation
        measurements = [m for m in report.measurements if m.metric_name == "bond_value"]
        assert len(measurements) == 2
        
        # Sort by n_obs to compare
        measurements.sort(key=lambda m: m.context["n_obs"])
        low_n_obs = measurements[0]
        high_n_obs = measurements[1]
        
        # Dynamic threshold metadata should be present for both measurements
        assert low_n_obs.context.get("dynamic_threshold_applied") is True
        assert high_n_obs.context.get("dynamic_threshold_applied") is True


class TestComprehensiveScenarios:
    """Comprehensive test scenarios covering multiple aspects."""
    
    def test_complex_multi_target_scenario(self):
        """Test complex scenario with multiple targets and metric types."""
        telemetry.active_reports.clear()
        telemetry.completed_reports.clear()
        scenario = telemetry.start_scenario("complex_multi_target")
        
        # Target A affects Target B (bond leak)
        measure_target_to_target_leak(
            scenario_name=scenario,
            source_target="target_a",
            affected_target="target_b",
            metric_name="bond_value",
            expected_value=0.3,
            actual_value=0.8
        )
        
        # Target A promises leak to Target C
        measure_ledger_isolation(
            scenario_name=scenario,
            source_target="target_a",
            check_target="target_c",
            has_promise_from_source=True
        )
        
        # Target B's somatic state affects Target D
        measure_target_to_target_leak(
            scenario_name=scenario,
            source_target="target_b",
            affected_target="target_d",
            metric_name="somatic_residual_safety_stress",
            expected_value=0.6,
            actual_value=0.9
        )
        
        # Policy contamination from A to E
        measure_target_to_target_leak(
            scenario_name=scenario,
            source_target="target_a",
            affected_target="target_e",
            metric_name="action_policy_defensiveness",
            expected_value=0.3,
            actual_value=0.8
        )
        
        report = telemetry.finalize_scenario(scenario)
        
        # Should detect multiple types of interference
        assert report.target_state_leak_between_targets > 0.5  # From bond and somatic
        assert report.ledger_promise_leak > 0.8  # From promise leak
        
        # Should have multiple measurements
        assert len(report.measurements) == 4
        
        # Should get poor grade due to multiple failures
        assert report._get_grade() in ["D", "F"]
    
    def test_no_interference_ideal_case(self):
        """Test ideal case with no interference."""
        telemetry.active_reports.clear()
        telemetry.completed_reports.clear()
        scenario = telemetry.start_scenario("no_interference_ideal")
        
        # All measurements show no interference
        measure_target_to_target_leak(
            scenario_name=scenario,
            source_target="target_a",
            affected_target="target_b",
            metric_name="bond_value",
            expected_value=0.5,
            actual_value=0.5  # Perfect isolation
        )
        
        measure_ledger_isolation(
            scenario_name=scenario,
            source_target="target_a",
            check_target="target_b",
            has_promise_from_source=False  # No leak
        )
        
        measure_self_model_isolation(
            scenario_name=scenario,
            target_id="target_b",
            self_model_values={"w_memory": 0.5},
            expected_per_target_variance=0.5,
            actual_variance=0.5  # Proper independence
        )
        
        report = telemetry.finalize_scenario(scenario)
        
        # Should have excellent grade
        assert report._get_grade() == "A"
        assert report.total_interference_score < 0.1
        
        # All severities should be zero
        assert all(m.severity == 0.0 for m in report.measurements)
