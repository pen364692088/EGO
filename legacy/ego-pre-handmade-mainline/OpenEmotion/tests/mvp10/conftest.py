"""
Pytest fixtures for MVP-10 tests.
"""
import os
import sys
import tempfile
import pytest
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def temp_artifacts_dir():
    """Create a temporary directory for test artifacts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts_dir = os.path.join(tmpdir, "artifacts", "mvp10")
        os.makedirs(artifacts_dir, exist_ok=True)
        yield artifacts_dir


@pytest.fixture
def sample_plan():
    """Sample plan for testing."""
    return {
        "plan_id": "test_plan_001",
        "goal": "fix the bug",
        "steps": [
            {"action": "seek_info", "params": {"query": "bug diagnosis"}, "expected_result": "problem identified"},
            {"action": "attempt_solution", "params": {"approach": "standard_repair"}, "expected_result": "issue resolved"},
            {"action": "run_check", "params": {"validation": "full"}, "expected_result": "all tests pass"},
        ],
        "risk_level": "medium",
        "expected_outcome": "Bug is fixed",
        "rollback": "Revert changes",
    }


@pytest.fixture
def sample_event():
    """Sample event log for testing."""
    return {
        "tick_id": 1,
        "run_id": "test_run_001",
        "seed": 42,
        "ts": 1709515200.0,
        "candidates": [
            {"id": "goal_0", "score": 1.0, "type": "goal", "meta": {"goal": "fix the bug"}},
        ],
        "chosen_focus": "fix the bug",
        "chosen_intent": "achieve",
        "policy_params": {},
        "plan": {
            "plan_id": "plan_42_1001",
            "goal": "fix the bug",
            "steps": [{"action": "seek_info", "params": {"query": "diagnose fix the bug"}}],
            "risk_level": "medium",
            "expected_outcome": "Goal 'fix the bug' achieved successfully",
        },
        "action": {"type": "seek_info", "params": {"query": "diagnose fix the bug"}},
        "outcome": {"status": "success", "reason": "Found information about 'diagnose fix the bug'"},
        "state_delta": {"before": {}, "after": {}, "changed_keys": []},
        "interventions": [],
    }
