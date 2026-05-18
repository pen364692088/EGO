"""
Tests for KnobRegistry parameter validation and AutoTune integration.
"""

import pytest
import tempfile
import json
import os
from pathlib import Path
from unittest.mock import patch

from emotiond.knob_registry import KnobRegistry, validate_parameter_change


class TestKnobRegistry:
    """Test suite for KnobRegistry functionality."""
    
    @pytest.fixture
    def temp_config(self):
        """Create temporary knob registry config."""
        config = {
            "allowlist": {
                "thresholds": {
                    "description": "Test thresholds",
                    "parameters": ["test_threshold_1", "test_threshold_2"]
                },
                "weights": {
                    "description": "Test weights", 
                    "parameters": ["test_weight_1"]
                }
            },
            "hard_freeze": {
                "safety": {
                    "description": "Safety critical",
                    "parameters": ["safety_param_1", "safety_param_2"]
                }
            },
            "validation_rules": {
                "allowlist_range_checks": {
                    "thresholds": {"min": 0.0, "max": 1.0},
                    "weights": {"min": 0.0, "max": 2.0}
                },
                "hard_freeze_violations": {
                    "action": "reject",
                    "log_level": "error",
                    "require_reason": True
                }
            },
            "version": "test-1.0.0",
            "last_updated": "2026-03-01T00:00:00Z"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config, f)
            f.flush()
            os.fsync(f.fileno())
            yield f.name
        Path(f.name).unlink()
    
    @pytest.fixture
    def registry(self, temp_config):
        """Create KnobRegistry instance with test config."""
        return KnobRegistry(temp_config)
    
    def test_load_config(self, temp_config):
        """Test config loading."""
        registry = KnobRegistry(temp_config)
        assert registry.config["version"] == "test-1.0.0"
        assert len(registry.allowlist_params) == 3
        assert len(registry.hard_freeze_params) == 2
    
    def test_allowlist_parameter_allowed(self, registry):
        """Test allowlisted parameter changes are allowed."""
        is_allowed, reason = registry.validate_parameter_change("test_threshold_1", 0.5)
        assert is_allowed is True
        assert reason is None
    
    def test_hard_freeze_parameter_rejected(self, registry):
        """Test hard freeze parameter changes are rejected."""
        is_allowed, reason = registry.validate_parameter_change("safety_param_1", 0.5)
        assert is_allowed is False
        assert "HARD_FREEZE_VIOLATION" in reason
    
    def test_unknown_parameter_rejected(self, registry):
        """Test unknown parameter changes are rejected."""
        is_allowed, reason = registry.validate_parameter_change("unknown_param", 0.5)
        assert is_allowed is False
        assert "NOT_IN_ALLOWLIST" in reason
    
    def test_range_validation(self, registry):
        """Test parameter range validation."""
        # Valid range
        is_allowed, reason = registry.validate_parameter_change("test_threshold_1", 0.5)
        assert is_allowed is True
        
        # Below minimum
        is_allowed, reason = registry.validate_parameter_change("test_threshold_1", -0.1)
        assert is_allowed is False
        assert "below minimum" in reason
        
        # Above maximum
        is_allowed, reason = registry.validate_parameter_change("test_threshold_1", 1.5)
        assert is_allowed is False
        assert "above maximum" in reason
    
    def test_audit_logging(self, registry):
        """Test audit logging functionality."""
        # Add some validation attempts
        registry.validate_parameter_change("test_threshold_1", 0.5)  # Allowed
        registry.validate_parameter_change("safety_param_1", 0.5)  # Rejected
        registry.validate_parameter_change("unknown_param", 0.5)  # Rejected
        
        assert len(registry.audit_log) == 3
        
        # Check audit log entries
        allowed_entry = registry.audit_log[0]
        assert allowed_entry["action"] == "ALLOW"
        assert allowed_entry["parameter"] == "test_threshold_1"
        
        rejected_entry = registry.audit_log[1]
        assert rejected_entry["action"] == "REJECT"
        assert rejected_entry["parameter"] == "safety_param_1"
    
    def test_validation_summary(self, registry):
        """Test validation summary statistics."""
        # Add some validation attempts
        registry.validate_parameter_change("test_threshold_1", 0.5)  # Allowed
        registry.validate_parameter_change("safety_param_1", 0.5)  # Rejected
        registry.validate_parameter_change("unknown_param", 0.5)  # Rejected
        
        summary = registry.get_validation_summary()
        
        assert summary["total_validations"] == 3
        assert summary["allowed_changes"] == 1
        assert summary["rejected_changes"] == 2
        assert "HARD_FREEZE_VIOLATION" in summary["rejection_reasons"]
        assert "NOT_IN_ALLOWLIST" in summary["rejection_reasons"]
    
    def test_get_parameter_config(self, registry):
        """Test getting parameter configuration details."""
        # Allowlisted parameter
        config = registry.get_parameter_config("test_threshold_1")
        assert config is not None
        assert config["status"] == "ALLOWLIST"
        assert config["category"] == "thresholds"
        
        # Hard freeze parameter
        config = registry.get_parameter_config("safety_param_1")
        assert config is not None
        assert config["status"] == "HARD_FREEZE"
        assert config["category"] == "safety"
        assert config["change_allowed"] is False
        
        # Unknown parameter
        config = registry.get_parameter_config("unknown_param")
        assert config is None
    
    def test_config_hash(self, registry):
        """Test configuration hash generation."""
        hash1 = registry.get_config_hash()
        hash2 = registry.get_config_hash()
        
        assert hash1 == hash2
        assert len(hash1) == 16  # First 16 chars of SHA256
    
    def test_convenience_function(self, temp_config):
        """Test global convenience function."""
        with patch('emotiond.knob_registry._knob_registry_instance', KnobRegistry(temp_config)):
            # First call should use patched instance
            is_allowed, reason = validate_parameter_change("test_threshold_1", 0.5)
            assert is_allowed is True

            # Second call should reuse same instance
            is_allowed, reason = validate_parameter_change("safety_param_1", 0.5)
            assert is_allowed is False
            assert "HARD_FREEZE_VIOLATION" in reason


class TestAutoTuneWithKnobRegistry:
    """Test AutoTune integration with KnobRegistry."""
    
    @pytest.fixture
    def temp_registry_config(self):
        """Create temporary registry config for AutoTune tests."""
        config = {
            "allowlist": {
                "thresholds": {
                    "description": "Test thresholds",
                    "parameters": [
                        "relationship_damage_threshold",
                        "recovery_priority_threshold",
                        "risk_tolerance_threshold",
                        "precision_uncertainty_threshold",
                        "social_drive_threshold",
                        "safety_drive_threshold",
                        "relationship_weight",
                        "recovery_weight",
                        "social_weight",
                        "safety_weight",
                        "rollout_branching_factor",
                        "timeout_multiplier"
                    ]
                },
                "strategy": {
                    "description": "Strategy parameters",
                    "parameters": [
                        "strategy_temperature",
                        "clarification_trigger_threshold"
                    ]
                }
            },
            "hard_freeze": {
                "safety": {
                    "description": "Safety critical parameters",
                    "parameters": [
                        "max_concurrent_requests",
                        "emergency_stop_conditions"
                    ]
                }
            },
            "validation_rules": {
                "allowlist_range_checks": {
                    "thresholds": {"min": 0.0, "max": 1.0},
                    "strategy": {"min": 0.1, "max": 5.0}
                },
                "hard_freeze_violations": {
                    "action": "reject",
                    "log_level": "error", 
                    "require_reason": True
                }
            },
            "version": "test-autotune-1.0.0",
            "last_updated": "2026-03-01T00:00:00Z"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config, f)
            f.flush()
            os.fsync(f.fileno())
            yield f.name
        Path(f.name).unlink()
    
    def test_autotune_respects_knob_registry(self, temp_registry_config):
        """Test that AutoTune respects KnobRegistry validation."""
        from scripts.auto_tune_v0_4 import AutoTuneEngine
        
        engine = AutoTuneEngine(
            scenarios_dir=Path("scenarios"),
            output_dir=Path("test_output"),
            seed=42
        )
        
        # Mock the registry instance
        engine.knob_registry = KnobRegistry(temp_registry_config)
        
        # Test valid parameter mutation
        baseline = {"relationship_damage_threshold": 0.3}
        candidate = engine.generate_candidate(baseline)
        
        # Should only contain allowlisted parameters with valid ranges
        for param, value in candidate.items():
            is_allowed, reason = engine.knob_registry.validate_parameter_change(param, value)
            assert is_allowed, f"Parameter {param} with value {value} should be allowed: {reason}"
    
    def test_autotune_rejects_hard_freeze_mutations(self, temp_registry_config):
        """Test that AutoTune rejects hard freeze parameter mutations."""
        from scripts.auto_tune_v0_4 import AutoTuneEngine
        
        engine = AutoTuneEngine(
            scenarios_dir=Path("scenarios"),
            output_dir=Path("test_output"),
            seed=42
        )
        
        # Mock the registry instance
        engine.knob_registry = KnobRegistry(temp_registry_config)
        
        # Try to mutate hard freeze parameter directly
        baseline = {"emergency_stop_conditions": "original_value"}
        
        # Manual validation should reject
        is_allowed, reason = engine.knob_registry.validate_parameter_change(
            "emergency_stop_conditions", "new_value"
        )
        assert is_allowed is False
        assert "HARD_FREEZE_VIOLATION" in reason


if __name__ == "__main__":
    pytest.main([__file__, "-v"])