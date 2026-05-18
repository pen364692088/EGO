"""
T01 - Schema Validation Tests

Tests that all MVP-10 schemas are valid and can validate data.
"""
import json
import os
import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Try to import jsonschema, skip tests if not available
try:
    from jsonschema import validate, ValidationError, Draft7Validator
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


SCHEMAS_DIR = project_root / "schemas"


@pytest.fixture
def event_log_schema():
    """Load the event log schema."""
    schema_path = SCHEMAS_DIR / "mvp10_event_log.v1.json"
    with open(schema_path) as f:
        return json.load(f)


@pytest.fixture
def state_snapshot_schema():
    """Load the state snapshot schema."""
    schema_path = SCHEMAS_DIR / "mvp10_state_snapshot.v1.json"
    with open(schema_path) as f:
        return json.load(f)


@pytest.fixture
def plan_schema():
    """Load the plan schema."""
    schema_path = SCHEMAS_DIR / "mvp10_plan.v1.json"
    with open(schema_path) as f:
        return json.load(f)


class TestSchemaFiles:
    """Test that schema files exist and are valid JSON."""

    def test_event_log_schema_exists(self):
        """Test that event log schema file exists."""
        schema_path = SCHEMAS_DIR / "mvp10_event_log.v1.json"
        assert schema_path.exists(), f"Schema file not found: {schema_path}"

    def test_state_snapshot_schema_exists(self):
        """Test that state snapshot schema file exists."""
        schema_path = SCHEMAS_DIR / "mvp10_state_snapshot.v1.json"
        assert schema_path.exists(), f"Schema file not found: {schema_path}"

    def test_plan_schema_exists(self):
        """Test that plan schema file exists."""
        schema_path = SCHEMAS_DIR / "mvp10_plan.v1.json"
        assert schema_path.exists(), f"Schema file not found: {schema_path}"

    def test_event_log_schema_valid_json(self, event_log_schema):
        """Test that event log schema is valid JSON."""
        assert isinstance(event_log_schema, dict)
        assert "$schema" in event_log_schema

    def test_state_snapshot_schema_valid_json(self, state_snapshot_schema):
        """Test that state snapshot schema is valid JSON."""
        assert isinstance(state_snapshot_schema, dict)
        assert "$schema" in state_snapshot_schema

    def test_plan_schema_valid_json(self, plan_schema):
        """Test that plan schema is valid JSON."""
        assert isinstance(plan_schema, dict)
        assert "$schema" in plan_schema


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestEventLogSchema:
    """Test event log schema validation."""

    def test_valid_event_log(self, event_log_schema):
        """Test that a valid event log passes validation."""
        valid_event = {
            "tick_id": 1,
            "run_id": "run_abc123",
            "seed": 42,
            "ts": 1709515200.0,
            "candidates": [
                {"id": "goal_0", "score": 1.0, "type": "goal", "meta": {"goal": "test"}}
            ],
            "chosen_focus": "test goal",
            "chosen_intent": "achieve",
            "policy_params": {},
            "plan": {
                "plan_id": "plan_001",
                "goal": "test goal",
                "steps": [{"action": "seek_info", "params": {}}],
                "risk_level": "low",
                "expected_outcome": "success",
            },
            "action": {"type": "seek_info", "params": {}},
            "outcome": {"status": "success", "reason": "test"},
            "state_delta": {"before": {}, "after": {}, "changed_keys": []},
            "interventions": [],
        }
        validate(instance=valid_event, schema=event_log_schema)

    def test_missing_required_field(self, event_log_schema):
        """Test that missing required fields fail validation."""
        invalid_event = {
            "tick_id": 1,
            "run_id": "run_abc123",
            # Missing seed, ts, candidates, etc.
        }
        with pytest.raises(ValidationError):
            validate(instance=invalid_event, schema=event_log_schema)

    def test_invalid_action_type(self, event_log_schema):
        """Test that invalid action types fail validation."""
        invalid_event = {
            "tick_id": 1,
            "run_id": "run_abc123",
            "seed": 42,
            "ts": 1709515200.0,
            "candidates": [],
            "chosen_focus": "test",
            "chosen_intent": "test",
            "policy_params": {},
            "plan": {"steps": [], "risk_level": "low", "expected_outcome": "test"},
            "action": {"type": "invalid_action", "params": {}},
            "outcome": {"status": "success"},
            "state_delta": {"before": {}, "after": {}, "changed_keys": []},
            "interventions": [],
        }
        with pytest.raises(ValidationError):
            validate(instance=invalid_event, schema=event_log_schema)

    def test_invalid_outcome_status(self, event_log_schema):
        """Test that invalid outcome status fails validation."""
        invalid_event = {
            "tick_id": 1,
            "run_id": "run_abc123",
            "seed": 42,
            "ts": 1709515200.0,
            "candidates": [],
            "chosen_focus": "test",
            "chosen_intent": "test",
            "policy_params": {},
            "plan": {"steps": [], "risk_level": "low", "expected_outcome": "test"},
            "action": {"type": "seek_info"},
            "outcome": {"status": "invalid_status"},
            "state_delta": {"before": {}, "after": {}, "changed_keys": []},
            "interventions": [],
        }
        with pytest.raises(ValidationError):
            validate(instance=invalid_event, schema=event_log_schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestStateSnapshotSchema:
    """Test state snapshot schema validation."""

    def test_valid_snapshot(self, state_snapshot_schema):
        """Test that a valid snapshot passes validation."""
        valid_snapshot = {
            "snapshot_id": "snap_abc123",
            "run_id": "run_abc123",
            "tick_id": 5,
            "ts": 1709515200.0,
            "state": {
                "goals": [{"id": "g1", "description": "test", "priority": 1.0, "status": "active"}],
                "context": {},
                "history": [],
                "metrics": {},
                "constraints": [],
            },
        }
        validate(instance=valid_snapshot, schema=state_snapshot_schema)

    def test_missing_required_field(self, state_snapshot_schema):
        """Test that missing required fields fail validation."""
        invalid_snapshot = {
            "snapshot_id": "snap_abc123",
            # Missing run_id, tick_id, ts, state
        }
        with pytest.raises(ValidationError):
            validate(instance=invalid_snapshot, schema=state_snapshot_schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestPlanSchema:
    """Test plan schema validation."""

    def test_valid_plan(self, plan_schema):
        """Test that a valid plan passes validation."""
        valid_plan = {
            "plan": {
                "plan_id": "plan_001",
                "goal": "fix the bug",
                "steps": [
                    {"action": "seek_info", "params": {"query": "bug"}},
                ],
                "risk_level": "medium",
                "expected_outcome": "Bug fixed",
                "rollback": "Revert changes",
            }
        }
        validate(instance=valid_plan, schema=plan_schema)

    def test_invalid_risk_level(self, plan_schema):
        """Test that invalid risk level fails validation."""
        invalid_plan = {
            "plan": {
                "steps": [],
                "risk_level": "extreme",  # Invalid
                "expected_outcome": "test",
            }
        }
        with pytest.raises(ValidationError):
            validate(instance=invalid_plan, schema=plan_schema)

    def test_missing_steps(self, plan_schema):
        """Test that missing steps fails validation."""
        invalid_plan = {
            "plan": {
                "risk_level": "low",
                "expected_outcome": "test",
            }
        }
        with pytest.raises(ValidationError):
            validate(instance=invalid_plan, schema=plan_schema)


class TestSchemaRequiredFields:
    """Test that schemas have all required fields for MVP-10."""

    def test_event_log_has_required_fields(self, event_log_schema):
        """Test that event log schema has all required fields."""
        required = event_log_schema.get("required", [])
        expected_required = [
            "tick_id", "run_id", "seed", "ts", "candidates",
            "chosen_focus", "chosen_intent", "policy_params", "plan",
            "action", "outcome", "state_delta", "interventions"
        ]
        for field in expected_required:
            assert field in required, f"Missing required field: {field}"

    def test_state_snapshot_has_required_fields(self, state_snapshot_schema):
        """Test that state snapshot schema has all required fields."""
        required = state_snapshot_schema.get("required", [])
        expected_required = ["snapshot_id", "run_id", "tick_id", "ts", "state"]
        for field in expected_required:
            assert field in required, f"Missing required field: {field}"

    def test_plan_has_required_fields(self, plan_schema):
        """Test that plan schema has all required fields."""
        plan_props = plan_schema.get("properties", {}).get("plan", {})
        required = plan_props.get("required", [])
        expected_required = ["steps", "risk_level", "expected_outcome"]
        for field in expected_required:
            assert field in required, f"Missing required field: {field}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
