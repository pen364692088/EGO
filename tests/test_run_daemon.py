#!/usr/bin/env python3
"""
Tests for the daemon runner script.
"""

import os
import sys
import subprocess
import tempfile
import time
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts import run_daemon


def test_load_env_file():
    """Test loading environment variables from file."""
    # Create a temporary environment file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("TEST_VAR=test_value\n")
        f.write("EMOTIOND_PORT=18081\n")
        f.write("# This is a comment\n")
        f.write("ANOTHER_VAR=another_value\n")
        env_file = f.name
    
    try:
        # Clear any existing values
        if 'TEST_VAR' in os.environ:
            del os.environ['TEST_VAR']
        if 'EMOTIOND_PORT' in os.environ:
            del os.environ['EMOTIOND_PORT']
        
        # Load the environment file
        run_daemon.load_env_file(env_file)
        
        # Check that variables were set
        assert os.environ.get('TEST_VAR') == 'test_value'
        assert os.environ.get('EMOTIOND_PORT') == '18081'
        assert os.environ.get('ANOTHER_VAR') == 'another_value'
        
        print("✓ test_load_env_file passed")
        
    finally:
        # Clean up
        os.unlink(env_file)
        if 'TEST_VAR' in os.environ:
            del os.environ['TEST_VAR']
        if 'EMOTIOND_PORT' in os.environ:
            del os.environ['EMOTIOND_PORT']
        if 'ANOTHER_VAR' in os.environ:
            del os.environ['ANOTHER_VAR']


def test_load_env_file_nonexistent():
    """Test loading environment variables from nonexistent file."""
    # This should not raise an exception
    run_daemon.load_env_file("nonexistent.env")
    print("✓ test_load_env_file_nonexistent passed")


def test_find_venv_python():
    """Test finding Python executable in virtual environment."""
    python_exe = run_daemon.find_venv_python()
    assert python_exe is not None
    assert isinstance(python_exe, str)
    print(f"✓ test_find_venv_python passed (found: {python_exe})")


def test_script_exists():
    """Test that the runner script exists and is executable."""
    script_path = project_root / "scripts" / "run_daemon.py"
    assert script_path.exists(), "Runner script does not exist"
    assert os.access(script_path, os.X_OK), "Runner script is not executable"
    print("✓ test_script_exists passed")


def test_script_import():
    """Test that the runner script can be imported."""
    # This test verifies the script has valid Python syntax
    import scripts.run_daemon
    assert hasattr(scripts.run_daemon, 'main')
    assert hasattr(scripts.run_daemon, 'load_env_file')
    assert hasattr(scripts.run_daemon, 'find_venv_python')
    print("✓ test_script_import passed")


def test_script_structure():
    """Test the script structure and function signatures."""
    # Check main function
    assert callable(run_daemon.main)
    
    # Check load_env_file function
    assert callable(run_daemon.load_env_file)
    
    # Check find_venv_python function
    assert callable(run_daemon.find_venv_python)
    
    # Check signal_handler function
    assert callable(run_daemon.signal_handler)
    
    print("✓ test_script_structure passed")


def test_environment_variable_loading():
    """Test environment variable loading behavior."""
    # Test that the function handles missing files gracefully
    original_env = os.environ.copy()
    
    try:
        run_daemon.load_env_file("nonexistent_file.env")
        # Should not raise an exception
        print("✓ test_environment_variable_loading passed")
    except Exception as e:
        raise AssertionError(f"load_env_file raised unexpected exception: {e}")
    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)


def test_venv_detection():
    """Test virtual environment detection logic."""
    # This test verifies the function doesn't crash
    result = run_daemon.find_venv_python()
    assert isinstance(result, str)
    assert len(result) > 0
    print("✓ test_venv_detection passed")


def run_all_tests():
    """Run all tests."""
    print("Running daemon runner script tests...\n")
    
    tests = [
        test_load_env_file,
        test_load_env_file_nonexistent,
        test_find_venv_python,
        test_script_exists,
        test_script_import,
        test_script_structure,
        test_environment_variable_loading,
        test_venv_detection,
    ]
    
    failed_tests = []
    
    for test_func in tests:
        try:
            test_func()
        except AssertionError as e:
            print(f"✗ {test_func.__name__} failed: {e}")
            failed_tests.append(test_func.__name__)
        except Exception as e:
            print(f"✗ {test_func.__name__} failed with unexpected error: {e}")
            failed_tests.append(test_func.__name__)
    
    print(f"\nTest Results: {len(tests) - len(failed_tests)}/{len(tests)} passed")
    
    if failed_tests:
        print(f"Failed tests: {', '.join(failed_tests)}")
        return False
    else:
        print("All tests passed!")
        return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)