"""
T02 - Schema Validation Tests for MVP11

Tests that all MVP-11 schemas are valid and can validate data.
Includes tests for new MVP11 fields: homeostasis_state, homeostasis_delta, efe_terms, governor_decision.
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
    """Load the MVP11 event log schema."""
    schema_path = SCHEMAS_DIR / "mvp11_event_log.v1.json"
    with open(schema_path) as f:
        return json.load(f)


@pytest.fixture
def state_snapshot_schema():
    """Load the MVP11 state snapshot schema."""
    schema_path = SCHEMAS_DIR / "mvp11_state_snapshot.v1.json"
    with open(schema_path) as f:
        return json.load(f)


@pytest.fixture
def policy_params_schema():
    """Load the MVP11 policy params schema."""
    schema_path = SCHEMAS_DIR / "mvp11_policy_params.v1.json"
    with open(schema_path) as f:
        return json.load(f)


class TestSchemaFiles:
    """Test that schema files exist and are valid JSON."""

    def test_event_log_schema_exists(self):
        """Test that event log schema file exists."""
        schema_path = SCHEMAS_DIR / "mvp11_event_log.v1.json"
        assert schema_path.exists(), f"Schema file not found: {schema_path}"

    def test_state_snapshot_schema_exists(self):
        """Test that state snapshot schema file exists."""
        schema_path = SCHEMAS_DIR / "mvp11_state_snapshot.v1.json"
        assert schema_path.exists(), f"Schema file not found: {schema_path}"

    def test_policy_params_schema_exists(self):
        """Test that policy params schema file exists."""
        schema_path = SCHEMAS_DIR / "mvp11_policy_params.v1.json"
        assert schema_path.exists(), f"Schema file not found: {schema_path}"

    def test_event_log_schema_valid_json(self, event_log_schema):
        """Test that event log schema is valid JSON."""
        assert isinstance(event_log_schema, dict)
        assert "$schema" in event_log_schema

    def test_state_snapshot_schema_valid_json(self, state_snapshot_schema):
        """Test that state snapshot schema is valid JSON."""
        assert isinstance(state_snapshot_schema, dict)
        assert "$schema" in state_snapshot_schema

    def test_policy_params_schema_valid_json(self, policy_params_schema):
        """Test that policy params schema is valid JSON."""
        assert isinstance(policy_params_schema, dict)
        assert "$schema" in policy_params_schema


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestEventLogSchema:
    """Test MVP11 event log schema validation."""

    def test_valid_mvp10_event_log(self, event_log_schema):
        """Test that a valid MVP10 event log (without MVP11 fields) still passes validation."""
        # MVP10 compatible event (backward compatibility)
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

    def test_valid_event_log_with_mvp11_fields(self, event_log_schema):
        """Test that a valid MVP11 event log with all new fields passes validation."""
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
            "policy_params": {
                "risk_weight": 0.25,
                "info_gain_weight": 0.25,
                "cost_weight": 0.25,
                "precision": 1.0
            },
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
            # MVP11 new fields
            "homeostasis_state": {
                "energy_budget": 0.8,
                "compute_pressure": 0.3,
                "error_pressure": 0.1,
                "memory_pressure": 0.4,
                "risk_exposure": 0.2,
                "uncertainty": 0.5
            },
            "efe_terms": {
                "risk": 0.1,
                "ambiguity": 0.2,
                "info_gain": 0.3,
                "expected_cost": 0.4
            },
            "governor_decision": {
                "action": "ALLOW",
                "reason": "All homeostasis values within normal range"
            }
        }
        validate(instance=valid_event, schema=event_log_schema)

    def test_valid_event_log_with_homeostasis_delta(self, event_log_schema):
        """Test event log with optional homeostasis_delta field."""
        valid_event = {
            "tick_id": 2,
            "run_id": "run_abc123",
            "seed": 42,
            "ts": 1709515201.0,
            "candidates": [],
            "chosen_focus": "test",
            "chosen_intent": "test",
            "policy_params": {},
            "plan": {"steps": [], "risk_level": "low", "expected_outcome": "test"},
            "action": {"type": "noop"},
            "outcome": {"status": "success"},
            "state_delta": {"before": {}, "after": {}, "changed_keys": []},
            "interventions": [],
            "homeostasis_state": {
                "energy_budget": 0.7,
                "compute_pressure": 0.35,
                "error_pressure": 0.15,
                "memory_pressure": 0.45,
                "risk_exposure": 0.25,
                "uncertainty": 0.55
            },
            "homeostasis_delta": {
                "energy_budget": -0.1,
                "compute_pressure": 0.05,
                "error_pressure": 0.05,
                "memory_pressure": 0.05,
                "risk_exposure": 0.05,
                "uncertainty": 0.05
            },
            "efe_terms": {
                "risk": 0.15,
                "ambiguity": 0.25,
                "info_gain": 0.2,
                "expected_cost": 0.35
            },
            "governor_decision": {
                "action": "ALLOW",
                "reason": "Values stable"
            }
        }
        validate(instance=valid_event, schema=event_log_schema)

    def test_governor_decision_require_approval(self, event_log_schema):
        """Test governor decision with REQUIRE_APPROVAL action."""
        valid_event = {
            "tick_id": 3,
            "run_id": "run_abc123",
            "seed": 42,
            "ts": 1709515202.0,
            "candidates": [],
            "chosen_focus": "test",
            "chosen_intent": "test",
            "policy_params": {},
            "plan": {"steps": [], "risk_level": "high", "expected_outcome": "test"},
            "action": {"type": "attempt_solution"},
            "outcome": {"status": "success"},
            "state_delta": {"before": {}, "after": {}, "changed_keys": []},
            "interventions": [],
            "homeostasis_state": {
                "energy_budget": 0.5,
                "compute_pressure": 0.6,
                "error_pressure": 0.5,
                "memory_pressure": 0.5,
                "risk_exposure": 0.7,
                "uncertainty": 0.6
            },
            "efe_terms": {
                "risk": 0.5,
                "ambiguity": 0.4,
                "info_gain": 0.2,
                "expected_cost": 0.6
            },
            "governor_decision": {
                "action": "REQUIRE_APPROVAL",
                "reason": "Risk exposure above threshold",
                "thresholds_triggered": ["risk_exposure_max"]
            }
        }
        validate(instance=valid_event, schema=event_log_schema)

    def test_governor_decision_deny(self, event_log_schema):
        """Test governor decision with DENY action."""
        valid_event = {
            "tick_id": 4,
            "run_id": "run_abc123",
            "seed": 42,
            "ts": 1709515203.0,
            "candidates": [],
            "chosen_focus": "test",
            "chosen_intent": "test",
            "policy_params": {},
            "plan": {"steps": [], "risk_level": "critical", "expected_outcome": "test"},
            "action": {"type": "noop"},
            "outcome": {"status": "success"},
            "state_delta": {"before": {}, "after": {}, "changed_keys": []},
            "interventions": [],
            "homeostasis_state": {
                "energy_budget": 0.1,
                "compute_pressure": 0.9,
                "error_pressure": 0.85,
                "memory_pressure": 0.9,
                "risk_exposure": 0.95,
                "uncertainty": 0.9
            },
            "efe_terms": {
                "risk": 0.9,
                "ambiguity": 0.8,
                "info_gain": 0.1,
                "expected_cost": 0.9
            },
            "governor_decision": {
                "action": "DENY",
                "reason": "Multiple critical thresholds exceeded",
                "thresholds_triggered": [
                    "energy_budget_min",
                    "compute_pressure_max",
                    "memory_pressure_max",
                    "risk_exposure_max"
                ]
            }
        }
        validate(instance=valid_event, schema=event_log_schema)

    def test_invalid_governor_action(self, event_log_schema):
        """Test that invalid governor action fails validation."""
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
            "outcome": {"status": "success"},
            "state_delta": {"before": {}, "after": {}, "changed_keys": []},
            "interventions": [],
            "homeostasis_state": {
                "energy_budget": 0.8,
                "compute_pressure": 0.3,
                "error_pressure": 0.1,
                "memory_pressure": 0.4,
                "risk_exposure": 0.2,
                "uncertainty": 0.5
            },
            "efe_terms": {
                "risk": 0.1,
                "ambiguity": 0.2,
                "info_gain": 0.3,
                "expected_cost": 0.4
            },
            "governor_decision": {
                "action": "INVALID_ACTION",  # Invalid
                "reason": "test"
            }
        }
        with pytest.raises(ValidationError):
            validate(instance=invalid_event, schema=event_log_schema)

    def test_homeostasis_out_of_range(self, event_log_schema):
        """Test that homeostasis values out of range fail validation."""
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
            "outcome": {"status": "success"},
            "state_delta": {"before": {}, "after": {}, "changed_keys": []},
            "interventions": [],
            "homeostasis_state": {
                "energy_budget": 1.5,  # Out of range (> 1)
                "compute_pressure": 0.3,
                "error_pressure": 0.1,
                "memory_pressure": 0.4,
                "risk_exposure": 0.2,
                "uncertainty": 0.5
            },
            "efe_terms": {
                "risk": 0.1,
                "ambiguity": 0.2,
                "info_gain": 0.3,
                "expected_cost": 0.4
            },
            "governor_decision": {
                "action": "ALLOW",
                "reason": "test"
            }
        }
        with pytest.raises(ValidationError):
            validate(instance=invalid_event, schema=event_log_schema)

    def test_governor_decision_missing_required_action(self, event_log_schema):
        """Test that governor_decision without action fails validation."""
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
            "outcome": {"status": "success"},
            "state_delta": {"before": {}, "after": {}, "changed_keys": []},
            "interventions": [],
            "homeostasis_state": {
                "energy_budget": 0.8,
                "compute_pressure": 0.3,
                "error_pressure": 0.1,
                "memory_pressure": 0.4,
                "risk_exposure": 0.2,
                "uncertainty": 0.5
            },
            "efe_terms": {
                "risk": 0.1,
                "ambiguity": 0.2,
                "info_gain": 0.3,
                "expected_cost": 0.4
            },
            "governor_decision": {
                # Missing required "action" field
                "reason": "test"
            }
        }
        with pytest.raises(ValidationError):
            validate(instance=invalid_event, schema=event_log_schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestStateSnapshotSchema:
    """Test MVP11 state snapshot schema validation."""

    def test_valid_snapshot_with_homeostasis(self, state_snapshot_schema):
        """Test that a valid MVP11 snapshot passes validation."""
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
            "homeostasis": {
                "energy_budget": 0.8,
                "compute_pressure": 0.3,
                "error_pressure": 0.1,
                "memory_pressure": 0.4,
                "risk_exposure": 0.2,
                "uncertainty": 0.5,
                "trend": {
                    "energy_budget": "stable",
                    "compute_pressure": "increasing",
                    "error_pressure": "decreasing",
                    "memory_pressure": "stable",
                    "risk_exposure": "stable",
                    "uncertainty": "decreasing"
                },
                "alert_level": "normal"
            }
        }
        validate(instance=valid_snapshot, schema=state_snapshot_schema)

    def test_snapshot_with_warning_alert(self, state_snapshot_schema):
        """Test snapshot with warning alert level."""
        valid_snapshot = {
            "snapshot_id": "snap_abc124",
            "run_id": "run_abc123",
            "tick_id": 10,
            "ts": 1709515300.0,
            "state": {
                "goals": [],
                "context": {},
                "history": [],
                "metrics": {},
                "constraints": [],
            },
            "homeostasis": {
                "energy_budget": 0.5,
                "compute_pressure": 0.6,
                "error_pressure": 0.4,
                "memory_pressure": 0.7,
                "risk_exposure": 0.5,
                "uncertainty": 0.6,
                "alert_level": "warning"
            }
        }
        validate(instance=valid_snapshot, schema=state_snapshot_schema)

    def test_snapshot_with_critical_alert(self, state_snapshot_schema):
        """Test snapshot with critical alert level."""
        valid_snapshot = {
            "snapshot_id": "snap_abc125",
            "run_id": "run_abc123",
            "tick_id": 15,
            "ts": 1709515400.0,
            "state": {
                "goals": [],
                "context": {},
                "history": [],
                "metrics": {},
                "constraints": [],
            },
            "homeostasis": {
                "energy_budget": 0.15,
                "compute_pressure": 0.9,
                "error_pressure": 0.85,
                "memory_pressure": 0.9,
                "risk_exposure": 0.8,
                "uncertainty": 0.85,
                "alert_level": "critical"
            }
        }
        validate(instance=valid_snapshot, schema=state_snapshot_schema)

    def test_missing_homeostasis(self, state_snapshot_schema):
        """Test that missing homeostasis fails validation (required in MVP11)."""
        invalid_snapshot = {
            "snapshot_id": "snap_abc123",
            "run_id": "run_abc123",
            "tick_id": 5,
            "ts": 1709515200.0,
            "state": {
                "goals": [],
                "context": {},
                "history": [],
                "metrics": {},
                "constraints": [],
            }
            # Missing homeostasis (required in MVP11)
        }
        with pytest.raises(ValidationError):
            validate(instance=invalid_snapshot, schema=state_snapshot_schema)

    def test_missing_homeostasis_required_field(self, state_snapshot_schema):
        """Test that missing required homeostasis field fails validation."""
        invalid_snapshot = {
            "snapshot_id": "snap_abc123",
            "run_id": "run_abc123",
            "tick_id": 5,
            "ts": 1709515200.0,
            "state": {
                "goals": [],
                "context": {},
                "history": [],
                "metrics": {},
                "constraints": [],
            },
            "homeostasis": {
                "energy_budget": 0.8,
                "compute_pressure": 0.3,
                # Missing error_pressure, memory_pressure, risk_exposure, uncertainty
            }
        }
        with pytest.raises(ValidationError):
            validate(instance=invalid_snapshot, schema=state_snapshot_schema)


@pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
class TestPolicyParamsSchema:
    """Test MVP11 policy params schema validation."""

    def test_valid_policy_params(self, policy_params_schema):
        """Test that valid policy params pass validation."""
        valid_params = {
            "policy_params": {
                "risk_weight": 0.25,
                "info_gain_weight": 0.25,
                "cost_weight": 0.25,
                "precision": 1.0
            }
        }
        validate(instance=valid_params, schema=policy_params_schema)

    def test_valid_policy_params_full(self, policy_params_schema):
        """Test that valid policy params with all fields pass validation."""
        valid_params = {
            "policy_params": {
                "risk_weight": 0.3,
                "info_gain_weight": 0.3,
                "cost_weight": 0.2,
                "ambiguity_weight": 0.2,
                "precision": 2.0,
                "exploration_bonus": 0.15,
                "homeostasis_thresholds": {
                    "energy_budget_min": 0.15,
                    "compute_pressure_max": 0.85,
                    "error_pressure_max": 0.75,
                    "memory_pressure_max": 0.9,
                    "risk_exposure_max": 0.8,
                    "uncertainty_max": 0.95
                },
                "governor_mode": "strict",
                "action_timeout_seconds": 600,
                "max_replan_attempts": 5
            }
        }
        validate(instance=valid_params, schema=policy_params_schema)

    def test_policy_params_permissive_mode(self, policy_params_schema):
        """Test policy params with permissive governor mode."""
        valid_params = {
            "policy_params": {
                "risk_weight": 0.2,
                "info_gain_weight": 0.4,
                "cost_weight": 0.2,
                "precision": 1.5,
                "governor_mode": "permissive"
            }
        }
        validate(instance=valid_params, schema=policy_params_schema)

    def test_missing_required_field(self, policy_params_schema):
        """Test that missing required fields fail validation."""
        invalid_params = {
            "policy_params": {
                "risk_weight": 0.25,
                "info_gain_weight": 0.25,
                "cost_weight": 0.25
                # Missing precision
            }
        }
        with pytest.raises(ValidationError):
            validate(instance=invalid_params, schema=policy_params_schema)

    def test_invalid_weight_range(self, policy_params_schema):
        """Test that weights out of range fail validation."""
        invalid_params = {
            "policy_params": {
                "risk_weight": 1.5,  # Out of range (> 1)
                "info_gain_weight": 0.25,
                "cost_weight": 0.25,
                "precision": 1.0
            }
        }
        with pytest.raises(ValidationError):
            validate(instance=invalid_params, schema=policy_params_schema)

    def test_invalid_precision(self, policy_params_schema):
        """Test that precision <= 0 fails validation."""
        invalid_params = {
            "policy_params": {
                "risk_weight": 0.25,
                "info_gain_weight": 0.25,
                "cost_weight": 0.25,
                "precision": 0  # Invalid (must be > 0)
            }
        }
        with pytest.raises(ValidationError):
            validate(instance=invalid_params, schema=policy_params_schema)

    def test_invalid_governor_mode(self, policy_params_schema):
        """Test that invalid governor mode fails validation."""
        invalid_params = {
            "policy_params": {
                "risk_weight": 0.25,
                "info_gain_weight": 0.25,
                "cost_weight": 0.25,
                "precision": 1.0,
                "governor_mode": "invalid_mode"  # Invalid
            }
        }
        with pytest.raises(ValidationError):
            validate(instance=invalid_params, schema=policy_params_schema)


class TestSchemaRequiredFields:
    """Test that schemas have all required fields for MVP-11."""

    def test_event_log_has_mvp10_required_fields(self, event_log_schema):
        """Test that event log schema has all MVP10 required fields."""
        required = event_log_schema.get("required", [])
        expected_required = [
            "tick_id", "run_id", "seed", "ts", "candidates",
            "chosen_focus", "chosen_intent", "policy_params", "plan",
            "action", "outcome", "state_delta", "interventions"
        ]
        for field in expected_required:
            assert field in required, f"Missing required field: {field}"

    def test_event_log_has_mvp11_optional_fields(self, event_log_schema):
        """Test that event log schema has MVP11 optional fields defined."""
        properties = event_log_schema.get("properties", {})
        expected_optional = [
            "homeostasis_state", "homeostasis_delta", "efe_terms", "governor_decision"
        ]
        for field in expected_optional:
            assert field in properties, f"Missing MVP11 optional field: {field}"

    def test_state_snapshot_has_mvp11_required_fields(self, state_snapshot_schema):
        """Test that state snapshot schema has all MVP11 required fields."""
        required = state_snapshot_schema.get("required", [])
        expected_required = ["snapshot_id", "run_id", "tick_id", "ts", "state", "homeostasis"]
        for field in expected_required:
            assert field in required, f"Missing required field: {field}"

    def test_policy_params_has_required_fields(self, policy_params_schema):
        """Test that policy params schema has all required fields."""
        policy_props = policy_params_schema.get("properties", {}).get("policy_params", {})
        required = policy_props.get("required", [])
        expected_required = ["risk_weight", "info_gain_weight", "cost_weight", "precision"]
        for field in expected_required:
            assert field in required, f"Missing required field: {field}"

    def test_homeostasis_state_has_all_fields(self, event_log_schema):
        """Test that homeostasis_state has all required sub-fields."""
        homeostasis_props = event_log_schema.get("properties", {}).get("homeostasis_state", {}).get("properties", {})
        expected_fields = [
            "energy_budget", "compute_pressure", "error_pressure",
            "memory_pressure", "risk_exposure", "uncertainty"
        ]
        for field in expected_fields:
            assert field in homeostasis_props, f"Missing homeostasis_state field: {field}"

    def test_efe_terms_has_all_fields(self, event_log_schema):
        """Test that efe_terms has all required sub-fields."""
        efe_props = event_log_schema.get("properties", {}).get("efe_terms", {}).get("properties", {})
        expected_fields = ["risk", "ambiguity", "info_gain", "expected_cost"]
        for field in expected_fields:
            assert field in efe_props, f"Missing efe_terms field: {field}"

    def test_governor_decision_has_all_fields(self, event_log_schema):
        """Test that governor_decision has all required sub-fields."""
        gov_props = event_log_schema.get("properties", {}).get("governor_decision", {}).get("properties", {})
        expected_fields = ["action", "reason"]
        for field in expected_fields:
            assert field in gov_props, f"Missing governor_decision field: {field}"

    def test_governor_action_enum_values(self, event_log_schema):
        """Test that governor decision action has correct enum values."""
        action_prop = event_log_schema.get("properties", {}).get("governor_decision", {}).get("properties", {}).get("action", {})
        enum_values = action_prop.get("enum", [])
        expected_values = ["ALLOW", "REQUIRE_APPROVAL", "DENY"]
        for value in expected_values:
            assert value in enum_values, f"Missing governor action enum value: {value}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
