"""
MVP11.4.7 P2 - Schema Guard Tests for WORKFLOW_STATE.json

Problem Background:
- callback-handler uses flat `steps: [...]` structure
- Manual workflow creation sometimes used nested `batches: [{steps: [...]}]` 
- Structure mismatch causes `run_id_not_found` errors
- Workflow orchestration silently fails

This test ensures:
1. Flat `steps` structure is required (top-level array)
2. Nested `batches` structure is forbidden (must fail validation)
3. Each step has required fields: id, status
"""
import json
import pytest
from pathlib import Path
from typing import Any


# Schema definition for WORKFLOW_STATE.json
WORKFLOW_STATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "WORKFLOW_STATE Schema",
    "description": "Schema for subagent orchestration workflow state. MUST use flat steps structure.",
    "type": "object",
    "required": ["active", "steps"],
    "properties": {
        "active": {
            "type": "boolean",
            "description": "Whether the workflow is currently active"
        },
        "workflow_type": {
            "type": "string",
            "enum": ["serial", "parallel"],
            "description": "Type of workflow execution"
        },
        "steps": {
            "type": "array",
            "description": "Flat list of workflow steps. REQUIRED. Do NOT use 'batches'.",
            "items": {
                "type": "object",
                "required": ["id", "status"],
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Unique step identifier"
                    },
                    "task": {
                        "type": "string",
                        "description": "Task description"
                    },
                    "model": {
                        "type": "string",
                        "description": "Model to use for this step"
                    },
                    "run_id": {
                        "type": ["string", "null"],
                        "description": "Run ID assigned after spawn"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "running", "done", "failed", "timeout"],
                        "description": "Current status of the step"
                    },
                    "created_at": {
                        "type": "string",
                        "format": "date-time"
                    },
                    "started_at": {
                        "type": "string",
                        "format": "date-time"
                    },
                    "completed_at": {
                        "type": "string",
                        "format": "date-time"
                    }
                }
            }
        },
        "notify_on_done": {
            "type": "string",
            "description": "Message to send when all steps complete"
        },
        "created_at": {
            "type": "string",
            "format": "date-time"
        },
        "updated_at": {
            "type": "string",
            "format": "date-time"
        },
        "completed_at": {
            "type": "string",
            "format": "date-time"
        }
    },
    "additionalProperties": False,
    "not": {
        "required": ["batches"],
        "description": "Nested 'batches' structure is FORBIDDEN. Use flat 'steps' array."
    }
}


class WorkflowStateValidator:
    """Validator for WORKFLOW_STATE.json schema."""
    
    def __init__(self, schema: dict = None):
        self.schema = schema or WORKFLOW_STATE_SCHEMA
        self.errors = []
    
    def validate(self, instance: dict) -> tuple[bool, list[str]]:
        """
        Validate a WORKFLOW_STATE instance.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        self.errors = []
        
        # Check required fields
        required = self.schema.get("required", [])
        for field in required:
            if field not in instance:
                self.errors.append(f"Missing required field: '{field}'")
        
        # Check forbidden fields
        if "batches" in instance:
            self.errors.append(
                "FORBIDDEN: 'batches' field detected. "
                "Use flat 'steps: [...]' structure instead of nested 'batches: [{steps: [...]}]'. "
                "This structure causes 'run_id_not_found' errors in callback-handler."
            )
        
        # Validate steps structure if present
        if "steps" in instance:
            steps = instance["steps"]
            if not isinstance(steps, list):
                self.errors.append("'steps' must be an array")
            else:
                for i, step in enumerate(steps):
                    if not isinstance(step, dict):
                        self.errors.append(f"Step {i} must be an object")
                        continue
                    
                    # Check required step fields
                    if "id" not in step:
                        self.errors.append(f"Step {i} missing required field: 'id'")
                    if "status" not in step:
                        self.errors.append(f"Step {i} missing required field: 'status'")
                    
                    # Validate status enum
                    if "status" in step:
                        valid_statuses = ["pending", "running", "done", "failed", "timeout"]
                        if step["status"] not in valid_statuses:
                            self.errors.append(
                                f"Step {i} has invalid status '{step['status']}'. "
                                f"Must be one of: {valid_statuses}"
                            )
        
        # Validate active field
        if "active" in instance and not isinstance(instance["active"], bool):
            self.errors.append("'active' must be a boolean")
        
        # Validate workflow_type enum
        if "workflow_type" in instance:
            valid_types = ["serial", "parallel"]
            if instance["workflow_type"] not in valid_types:
                self.errors.append(
                    f"Invalid workflow_type '{instance['workflow_type']}'. "
                    f"Must be one of: {valid_types}"
                )
        
        return (len(self.errors) == 0, self.errors)


class TestWorkflowStateSchema:
    """Test WORKFLOW_STATE.json schema validation."""
    
    @pytest.fixture
    def validator(self):
        return WorkflowStateValidator()
    
    # ========================================
    # VALID STRUCTURES
    # ========================================
    
    def test_valid_minimal_workflow(self, validator):
        """Test minimal valid workflow with flat steps."""
        workflow = {
            "active": True,
            "steps": [
                {"id": "step1", "status": "pending"}
            ]
        }
        is_valid, errors = validator.validate(workflow)
        assert is_valid, f"Expected valid, got errors: {errors}"
    
    def test_valid_serial_workflow(self, validator):
        """Test valid serial workflow with all fields."""
        workflow = {
            "active": True,
            "workflow_type": "serial",
            "steps": [
                {"id": "phase1", "task": "Setup", "status": "done"},
                {"id": "phase2", "task": "Process", "status": "running", "run_id": "run_abc"},
                {"id": "phase3", "task": "Cleanup", "status": "pending"}
            ],
            "notify_on_done": "Workflow complete",
            "created_at": "2026-03-05T08:00:00"
        }
        is_valid, errors = validator.validate(workflow)
        assert is_valid, f"Expected valid, got errors: {errors}"
    
    def test_valid_parallel_workflow(self, validator):
        """Test valid parallel workflow."""
        workflow = {
            "active": True,
            "workflow_type": "parallel",
            "steps": [
                {"id": "p1", "task": "Task A", "status": "pending"},
                {"id": "p2", "task": "Task B", "status": "pending"}
            ]
        }
        is_valid, errors = validator.validate(workflow)
        assert is_valid, f"Expected valid, got errors: {errors}"
    
    def test_valid_completed_workflow(self, validator):
        """Test valid completed workflow with all steps done."""
        workflow = {
            "active": False,
            "workflow_type": "serial",
            "steps": [
                {"id": "step1", "status": "done", "completed_at": "2026-03-05T09:00:00"},
                {"id": "step2", "status": "done", "completed_at": "2026-03-05T09:30:00"}
            ],
            "notify_on_done": "Done",
            "completed_at": "2026-03-05T09:30:00"
        }
        is_valid, errors = validator.validate(workflow)
        assert is_valid, f"Expected valid, got errors: {errors}"
    
    # ========================================
    # FORBIDDEN: BATCHES STRUCTURE
    # ========================================
    
    def test_batches_structure_is_forbidden(self, validator):
        """Test that nested batches structure is rejected."""
        # This was the problematic structure that caused run_id_not_found
        workflow = {
            "active": True,
            "batches": [
                {
                    "steps": [
                        {"id": "step1", "status": "pending"}
                    ]
                }
            ]
        }
        is_valid, errors = validator.validate(workflow)
        assert not is_valid, "Expected validation to fail for batches structure"
        assert any("batches" in e.lower() for e in errors), \
            f"Expected error about 'batches' being forbidden, got: {errors}"
    
    def test_batches_with_steps_still_forbidden(self, validator):
        """Test that even if steps exists, batches is still forbidden."""
        workflow = {
            "active": True,
            "steps": [
                {"id": "step1", "status": "pending"}
            ],
            "batches": [
                {"steps": [{"id": "step1", "status": "pending"}]}
            ]
        }
        is_valid, errors = validator.validate(workflow)
        assert not is_valid, "Expected validation to fail when batches is present"
        assert any("batches" in e.lower() for e in errors)
    
    def test_batches_nested_steps_not_recognized(self, validator):
        """Test that steps inside batches are not valid top-level steps."""
        workflow = {
            "active": True,
            "batches": [
                {
                    "batch_id": "batch1",
                    "steps": [
                        {"id": "nested_step", "status": "pending"}
                    ]
                }
            ]
        }
        is_valid, errors = validator.validate(workflow)
        assert not is_valid
        # Should error about missing top-level steps AND forbidden batches
        error_text = " ".join(errors).lower()
        assert "batches" in error_text or "steps" in error_text
    
    # ========================================
    # REQUIRED FIELDS
    # ========================================
    
    def test_missing_active_field(self, validator):
        """Test that missing 'active' field fails validation."""
        workflow = {
            "steps": [{"id": "step1", "status": "pending"}]
        }
        is_valid, errors = validator.validate(workflow)
        assert not is_valid
        assert any("active" in e for e in errors)
    
    def test_missing_steps_field(self, validator):
        """Test that missing 'steps' field fails validation."""
        workflow = {
            "active": True
        }
        is_valid, errors = validator.validate(workflow)
        assert not is_valid
        assert any("steps" in e for e in errors)
    
    def test_missing_step_id(self, validator):
        """Test that step without 'id' fails validation."""
        workflow = {
            "active": True,
            "steps": [
                {"status": "pending"}  # Missing id
            ]
        }
        is_valid, errors = validator.validate(workflow)
        assert not is_valid
        assert any("id" in e for e in errors)
    
    def test_missing_step_status(self, validator):
        """Test that step without 'status' fails validation."""
        workflow = {
            "active": True,
            "steps": [
                {"id": "step1"}  # Missing status
            ]
        }
        is_valid, errors = validator.validate(workflow)
        assert not is_valid
        assert any("status" in e for e in errors)
    
    # ========================================
    # INVALID VALUES
    # ========================================
    
    def test_invalid_status_value(self, validator):
        """Test that invalid status value fails validation."""
        workflow = {
            "active": True,
            "steps": [
                {"id": "step1", "status": "invalid_status"}
            ]
        }
        is_valid, errors = validator.validate(workflow)
        assert not is_valid
        assert any("status" in e.lower() for e in errors)
    
    def test_invalid_workflow_type(self, validator):
        """Test that invalid workflow_type fails validation."""
        workflow = {
            "active": True,
            "workflow_type": "invalid_type",
            "steps": [
                {"id": "step1", "status": "pending"}
            ]
        }
        is_valid, errors = validator.validate(workflow)
        assert not is_valid
        assert any("workflow_type" in e for e in errors)
    
    def test_active_not_boolean(self, validator):
        """Test that non-boolean active field fails validation."""
        workflow = {
            "active": "yes",  # Should be boolean
            "steps": [
                {"id": "step1", "status": "pending"}
            ]
        }
        is_valid, errors = validator.validate(workflow)
        assert not is_valid
        assert any("active" in e for e in errors)
    
    def test_steps_not_array(self, validator):
        """Test that non-array steps fails validation."""
        workflow = {
            "active": True,
            "steps": {"step1": {"status": "pending"}}  # Should be array
        }
        is_valid, errors = validator.validate(workflow)
        assert not is_valid
        assert any("steps" in e.lower() and "array" in e.lower() for e in errors)
    
    # ========================================
    # CALLBACK-HANDLER COMPATIBILITY
    # ========================================
    
    def test_callback_handler_can_find_run_id_in_flat_steps(self, validator):
        """
        Test that callback-handler can find run_id in flat steps structure.
        
        This is the structure that callback-handler expects:
        state.get('steps', []) -> iterate -> step.get('run_id')
        """
        workflow = {
            "active": True,
            "workflow_type": "serial",
            "steps": [
                {"id": "step1", "run_id": "run_abc123", "status": "running", "task": "Do something"}
            ]
        }
        
        # Validate structure
        is_valid, errors = validator.validate(workflow)
        assert is_valid, f"Expected valid, got errors: {errors}"
        
        # Simulate callback-handler lookup
        run_id_to_find = "run_abc123"
        found_step = None
        for step in workflow.get('steps', []):
            if step.get('run_id') == run_id_to_find:
                found_step = step
                break
        
        assert found_step is not None, "run_id should be findable in flat steps structure"
        assert found_step['id'] == "step1"
    
    def test_callback_handler_cannot_find_run_id_in_batches(self, validator):
        """
        Test that callback-handler CANNOT find run_id in batches structure.
        
        This demonstrates why batches is forbidden:
        callback-handler looks at state.get('steps', []) which would be empty
        in a batches structure.
        """
        workflow = {
            "active": True,
            "batches": [
                {
                    "steps": [
                        {"id": "step1", "run_id": "run_abc123", "status": "running"}
                    ]
                }
            ]
        }
        
        # This should fail validation
        is_valid, errors = validator.validate(workflow)
        assert not is_valid
        
        # Simulate why callback-handler fails with this structure
        # callback-handler does: state.get('steps', [])
        steps_at_top_level = workflow.get('steps', [])
        assert steps_at_top_level == [], \
            "Top-level steps should be empty in batches structure (this is the bug)"
        
        # run_id lookup fails
        run_id_to_find = "run_abc123"
        found_step = None
        for step in steps_at_top_level:  # Empty list!
            if step.get('run_id') == run_id_to_find:
                found_step = step
                break
        
        assert found_step is None, \
            "run_id should NOT be findable at top level in batches structure"
    
    # ========================================
    # REAL-WORLD EXAMPLES
    # ========================================
    
    def test_real_openclaw_workflow_state(self, validator):
        """Test against real WORKFLOW_STATE.json structure from OpenClaw."""
        workflow = {
            "active": True,
            "workflow_type": "parallel",
            "steps": [
                {"id": "p1-versioning", "run_id": None, "status": "pending"},
                {"id": "p2-schema-guard", "run_id": None, "status": "pending"}
            ],
            "notify_on_done": "✅ MVP11.4.7 完成：阈值版本化 + 冻结机制 + Schema 守护测试"
        }
        is_valid, errors = validator.validate(workflow)
        assert is_valid, f"Expected valid, got errors: {errors}"


class TestWorkflowStateIntegration:
    """Integration tests with callback-handler logic."""
    
    @pytest.fixture
    def validator(self):
        return WorkflowStateValidator()
    
    def test_step_status_transitions_valid(self, validator):
        """Test that step status can transition through valid states."""
        workflow = {
            "active": True,
            "steps": [
                {"id": "step1", "status": "pending"}
            ]
        }
        
        # Validate initial state
        is_valid, errors = validator.validate(workflow)
        assert is_valid
        
        # Transition to running
        workflow["steps"][0]["status"] = "running"
        workflow["steps"][0]["run_id"] = "run_xyz"
        is_valid, errors = validator.validate(workflow)
        assert is_valid
        
        # Transition to done
        workflow["steps"][0]["status"] = "done"
        is_valid, errors = validator.validate(workflow)
        assert is_valid
    
    def test_step_status_can_fail(self, validator):
        """Test that step can have failed status."""
        workflow = {
            "active": True,
            "steps": [
                {"id": "step1", "status": "failed"}
            ]
        }
        is_valid, errors = validator.validate(workflow)
        assert is_valid
    
    def test_step_status_can_timeout(self, validator):
        """Test that step can have timeout status."""
        workflow = {
            "active": True,
            "steps": [
                {"id": "step1", "status": "timeout"}
            ]
        }
        is_valid, errors = validator.validate(workflow)
        assert is_valid


class TestSchemaDefinition:
    """Test the schema definition itself."""
    
    def test_schema_has_required_fields_defined(self):
        """Test that schema defines required fields."""
        required = WORKFLOW_STATE_SCHEMA.get("required", [])
        assert "active" in required, "Schema should require 'active'"
        assert "steps" in required, "Schema should require 'steps'"
    
    def test_schema_forbids_batches(self):
        """Test that schema explicitly forbids 'batches'."""
        # The 'not' constraint should reject batches
        not_constraint = WORKFLOW_STATE_SCHEMA.get("not", {})
        assert "batches" in not_constraint.get("required", [])
    
    def test_step_items_have_required_fields(self):
        """Test that step items schema defines required fields."""
        step_props = WORKFLOW_STATE_SCHEMA["properties"]["steps"]["items"]
        required = step_props.get("required", [])
        assert "id" in required, "Step should require 'id'"
        assert "status" in required, "Step should require 'status'"
    
    def test_status_has_valid_enum_values(self):
        """Test that status enum has expected values."""
        status_prop = WORKFLOW_STATE_SCHEMA["properties"]["steps"]["items"]["properties"]["status"]
        enum_values = status_prop.get("enum", [])
        expected = ["pending", "running", "done", "failed", "timeout"]
        for val in expected:
            assert val in enum_values, f"Status should include '{val}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
