"""
Tests for the evaluation suite functionality.
Version 2.0: Updated for new report format with significance markers.
"""

import pytest
import tempfile
import json
from pathlib import Path
from scripts.eval_suite import generate_report


def test_generate_report_structure():
    """Test that report generation creates proper markdown structure."""
    
    mock_results = {
        "core_enabled": {
            "intervention": {"intervention_resistance": True, "baseline_valence": 0.1, "avg_post_intervention_valence": 0.15, "valence_change": 0.05, "shaping_effective": True},
            "prompt_attack_resistance": {"attack_resistance": True, "valence_range": 0.2, "avg_valence": 0.1, "primed_valence": 0.15, "min_valence": 0.0, "max_valence": 0.2},
            "time_gap_drift": {"time_drift_present": True, "valence_drift": 0.05, "arousal_drift": 0.03, "initial_valence": 0.2, "final_valence": 0.15},
            "costly_choice_curve": {"cost_sensitivity": True, "constraint_counts": {"low_cost": {"constraints_count": 1}}},
            "object_specificity": {"object_specificity": True, "valence_difference": 0.3, "bond_difference": 0.2, "grudge_difference": 0.1, "relationship_A": {"bond": 0.3, "grudge": 0.0}, "relationship_B": {"bond": 0.1, "grudge": 0.2}}
        },
        "core_disabled": {
            "intervention": {"intervention_resistance": False, "baseline_valence": 0.0, "avg_post_intervention_valence": 0.8, "valence_change": 0.8, "shaping_effective": False},
            "prompt_attack_resistance": {"attack_resistance": False, "valence_range": 1.5, "avg_valence": 0.5, "primed_valence": 0.3, "min_valence": 0.0, "max_valence": 1.5},
            "time_gap_drift": {"time_drift_present": False, "valence_drift": 0.01, "arousal_drift": 0.01, "initial_valence": 0.1, "final_valence": 0.09},
            "costly_choice_curve": {"cost_sensitivity": False, "constraint_counts": {"low_cost": {"constraints_count": 1}}},
            "object_specificity": {"object_specificity": False, "valence_difference": 0.0, "bond_difference": 0.0, "grudge_difference": 0.0, "relationship_A": {"bond": 0.0, "grudge": 0.0}, "relationship_B": {"bond": 0.0, "grudge": 0.0}}
        }
    }
    
    report = generate_report(mock_results)
    
    # Check essential sections
    assert "# OpenEmotion Evaluation Report" in report
    assert "## Overview" in report
    assert "## Test Results Summary" in report
    assert "## Detailed Results" in report
    assert "## Conclusion" in report
    
    # Check test names in summary table (v2.0 format)
    assert "Intervention" in report
    assert "Prompt Attack" in report
    assert "Time Gap Drift" in report
    assert "Object Specificity" in report


def test_generate_report_with_errors():
    """Test report generation handles test errors gracefully."""
    
    mock_results = {
        "core_enabled": {
            "intervention": {"error": "Daemon failed to start"},
            "prompt_attack_resistance": {"attack_resistance": True, "valence_range": 0.2, "avg_valence": 0.1, "primed_valence": 0.1, "min_valence": 0.0, "max_valence": 0.2},
        },
        "core_disabled": {
            "intervention": {"intervention_resistance": False, "baseline_valence": 0.0, "avg_post_intervention_valence": 0.0, "valence_change": 0.0, "shaping_effective": False},
            "prompt_attack_resistance": {"error": "Connection timeout"},
        }
    }
    
    report = generate_report(mock_results)
    
    # v2.0 report should still generate with available data
    assert "# OpenEmotion Evaluation Report" in report
    assert "## Overview" in report


def test_generate_report_comparison_analysis():
    """Test that report includes significance markers."""
    
    mock_results = {
        "core_enabled": {
            "intervention": {"intervention_resistance": True, "baseline_valence": 0.2, "avg_post_intervention_valence": 0.25, "valence_change": 0.05, "shaping_effective": True},
            "time_gap_drift": {"time_drift_present": True, "valence_drift": 0.15, "arousal_drift": 0.1, "initial_valence": 0.3, "final_valence": 0.15},
            "object_specificity": {"object_specificity": True, "valence_difference": 0.25, "bond_difference": 0.2, "grudge_difference": 0.15, "relationship_A": {"bond": 0.3, "grudge": 0.0}, "relationship_B": {"bond": 0.1, "grudge": 0.15}},
        },
        "core_disabled": {
            "intervention": {"intervention_resistance": False, "baseline_valence": 0.0, "avg_post_intervention_valence": 0.5, "valence_change": 0.5, "shaping_effective": False},
            "time_gap_drift": {"time_drift_present": False, "valence_drift": 0.02, "arousal_drift": 0.01, "initial_valence": 0.1, "final_valence": 0.08},
            "object_specificity": {"object_specificity": False, "valence_difference": 0.0, "bond_difference": 0.0, "grudge_difference": 0.0, "relationship_A": {"bond": 0.0, "grudge": 0.0}, "relationship_B": {"bond": 0.0, "grudge": 0.0}},
        }
    }
    
    report = generate_report(mock_results)
    
    # v2.0 should include significance markers
    assert "显著Δ" in report or "Δ" in report


def test_eval_suite_import():
    """Test that the evaluation suite module can be imported."""
    from scripts import eval_suite
    
    assert hasattr(eval_suite, 'generate_report')
    assert hasattr(eval_suite, 'run_evaluation')
    assert hasattr(eval_suite, 'main')


def test_report_timestamp():
    """Test that report includes a timestamp."""
    mock_results = {
        "core_enabled": {"intervention": {"test": "data"}},
        "core_disabled": {"intervention": {"test": "data"}}
    }
    
    report = generate_report(mock_results)
    assert "Generated:" in report


def test_report_conclusion():
    """Test that report includes proper conclusion section."""
    mock_results = {
        "core_enabled": {"intervention": {"test": "data"}},
        "core_disabled": {"intervention": {"test": "data"}}
    }
    
    report = generate_report(mock_results)
    
    # v2.0 conclusion format
    assert "## Conclusion" in report
    assert "PASS" in report or "PARTIAL" in report or "FAIL" in report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
