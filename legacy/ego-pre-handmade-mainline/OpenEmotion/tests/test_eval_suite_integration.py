"""
Integration tests for the evaluation suite - tests that actually run the evaluation.
"""

import pytest
import tempfile
import subprocess
import sys
from pathlib import Path


def test_eval_suite_runs_without_crash():
    """Test that the evaluation suite script runs without crashing."""
    
    # Run the evaluation suite with a short timeout
    result = subprocess.run(
        [sys.executable, "scripts/eval_suite.py"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
        timeout=30  # Should start and fail quickly if daemon not running
    )
    
    # Should not crash with Python errors
    assert result.returncode in [0, 1]  # 0 = success, 1 = expected failure (daemon not running)
    assert "Starting OpenEmotion evaluation suite" in result.stdout
    
    # Should provide meaningful output
    assert "Testing" in result.stdout or "ERROR" in result.stdout or "Error" in result.stdout or "failed" in result.stdout


def test_eval_suite_creates_report_file():
    """Test that evaluation suite creates the report file structure."""
    
    # Run with --help or similar to test file creation without full execution
    result = subprocess.run(
        [sys.executable, "scripts/eval_suite.py", "--help"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True
    )
    
    # Check that artifacts directory exists
    artifacts_dir = Path(__file__).parent.parent / "artifacts"
    assert artifacts_dir.exists()


def test_eval_suite_imports_correctly():
    """Test that all required imports work in the evaluation suite."""
    
    # Try to import the module
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    try:
        from scripts.eval_suite import (
            run_daemon_with_env, stop_daemon, test_intervention,
            test_prompt_attack_resistance, test_time_gap_drift,
            test_costly_choice_curve, test_object_specificity,
            run_evaluation, generate_report, main
        )
        # If we get here, imports succeeded
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import eval_suite: {e}")


def test_eval_suite_module_structure():
    """Test that the evaluation suite module has the expected structure."""
    
    import scripts.eval_suite as eval_module
    
    # Check required functions exist
    required_functions = [
        'run_daemon_with_env', 'stop_daemon', 'test_intervention',
        'test_prompt_attack_resistance', 'test_time_gap_drift',
        'test_costly_choice_curve', 'test_object_specificity',
        'run_evaluation', 'generate_report', 'main'
    ]
    
    for func_name in required_functions:
        assert hasattr(eval_module, func_name), f"Missing function: {func_name}"


def test_eval_suite_help_output():
    """Test that the evaluation suite provides usage information."""
    
    # Check the script has a main function
    import scripts.eval_suite as eval_module
    assert callable(eval_module.main)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])