"""
Simplified tests for KnobRegistry parameter validation.
"""

import pytest
import json
import tempfile
from pathlib import Path

from emotiond.knob_registry import KnobRegistry, validate_parameter_change


def test_knob_registry_basic():
    """Test basic KnobRegistry functionality."""
    # Create test config in memory
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
    
    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config, f)
        temp_path = f.name
    
    try:
        registry = KnobRegistry(temp_path)
        
        # Test config loading
        assert registry.config["version"] == "test-1.0.0"
        assert len(registry.allowlist_params) == 3
        assert len(registry.hard_freeze_params) == 2
        
        # Test allowlist parameter allowed
        is_allowed, reason = registry.validate_parameter_change("test_threshold_1", 0.5)
        assert is_allowed is True
        assert reason is None
        
        # Test hard freeze parameter rejected
        is_allowed, reason = registry.validate_parameter_change("safety_param_1", 0.5)
        assert is_allowed is False
        assert "HARD_FREEZE_VIOLATION" in reason
        
        # Test unknown parameter rejected
        is_allowed, reason = registry.validate_parameter_change("unknown_param", 0.5)
        assert is_allowed is False
        assert "NOT_IN_ALLOWLIST" in reason
        
        # Test range validation
        is_allowed, reason = registry.validate_parameter_change("test_threshold_1", 0.5)
        assert is_allowed is True
        
        is_allowed, reason = registry.validate_parameter_change("test_threshold_1", -0.1)
        assert is_allowed is False
        assert "below minimum" in reason
        
        # Test audit logging
        registry.validate_parameter_change("test_threshold_1", 0.5)
        registry.validate_parameter_change("safety_param_1", 0.5)
        
        assert len(registry.audit_log) >= 2
        
        # Test validation summary
        summary = registry.get_validation_summary()
        assert summary["total_validations"] >= 2
        assert summary["allowed_changes"] >= 1
        assert summary["rejected_changes"] >= 1
        
        # Test parameter config lookup
        config = registry.get_parameter_config("test_threshold_1")
        assert config["status"] == "ALLOWLIST"
        assert config["category"] == "thresholds"
        
        config = registry.get_parameter_config("safety_param_1")
        assert config["status"] == "HARD_FREEZE"
        assert config["change_allowed"] is False
        
    finally:
        Path(temp_path).unlink()


def test_knob_registry_config_hash():
    """Test configuration hash generation."""
    config = {
        "allowlist": {"thresholds": {"description": "Test", "parameters": ["test_param"]}},
        "hard_freeze": {"safety": {"description": "Test", "parameters": []}},
        "validation_rules": {"allowlist_range_checks": {}, "hard_freeze_violations": {}},
        "version": "test-1.0.0",
        "last_updated": "2026-03-01T00:00:00Z"
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config, f)
        temp_path = f.name
    
    try:
        registry = KnobRegistry(temp_path)
        hash1 = registry.get_config_hash()
        hash2 = registry.get_config_hash()
        
        assert hash1 == hash2
        assert len(hash1) == 16
    finally:
        Path(temp_path).unlink()


def test_validate_parameter_change_function():
    """Test global convenience function."""
    config = {
        "allowlist": {"thresholds": {"description": "Test", "parameters": ["test_param"]}},
        "hard_freeze": {"safety": {"description": "Test", "parameters": []}},
        "validation_rules": {"allowlist_range_checks": {}, "hard_freeze_violations": {}},
        "version": "test-1.0.0",
        "last_updated": "2026-03-01T00:00:00Z"
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config, f)
        temp_path = f.name
    
    try:
        # Patch the default path
        import emotiond.knob_registry
        original_path = emotiond.knob_registry.KnobRegistry.__init__.__code__.co_consts
        emotiond.knob_registry._knob_registry_instance = KnobRegistry(temp_path)
        
        # Test convenience function
        is_allowed, reason = validate_parameter_change("test_param", 0.5)
        assert is_allowed is True
        
        is_allowed, reason = validate_parameter_change("unknown_param", 0.5)
        assert is_allowed is False
        assert "NOT_IN_ALLOWLIST" in reason
        
    finally:
        Path(temp_path).unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])