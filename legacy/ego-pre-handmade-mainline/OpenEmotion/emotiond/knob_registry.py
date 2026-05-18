"""
Knob Registry - Parameter Learning Boundary Enforcement

This module enforces which parameters can be tuned (allowlist) and which are 
permanently frozen (hard_freeze) to prevent system corruption during AutoTune.
"""

import json
import hashlib
import logging
from typing import Dict, List, Set, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class KnobRegistry:
    """
    Registry for managing parameter learning boundaries.
    
    Enforces allowlist (tunable) and hard_freeze (immutable) parameter sets
    with validation and audit tracking.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize knob registry from configuration file.
        
        Args:
            config_path: Path to knob_registry.json config file
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "scripts" / "knob_registry.json"
        
        self.config_path = Path(config_path)
        self.config = self._load_config()
        
        # Build fast lookup sets
        self.allowlist_params = self._build_allowlist_set()
        self.hard_freeze_params = self._build_hard_freeze_set()
        
        # Audit log for validation attempts
        self.audit_log = []
        
    def _load_config(self) -> Dict[str, Any]:
        """Load knob registry configuration."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            logger.info(f"Loaded knob registry from {self.config_path}")
            return config
        except FileNotFoundError:
            logger.error(f"Knob registry config not found: {self.config_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in knob registry: {e}")
            raise
    
    def _build_allowlist_set(self) -> Set[str]:
        """Build set of all allowlisted parameters."""
        allowlist_cfg = self.config.get("allowlist", {})
        if isinstance(allowlist_cfg, list):
            return set(allowlist_cfg)

        allowlist = set()
        if isinstance(allowlist_cfg, dict):
            for _category, config in allowlist_cfg.items():
                if isinstance(config, dict):
                    allowlist.update(config.get("parameters", []))
        return allowlist
    
    def _build_hard_freeze_set(self) -> Set[str]:
        """Build set of all hard frozen parameters."""
        hard_cfg = self.config.get("hard_freeze", {})
        hard_freeze = set()

        if isinstance(hard_cfg, list):
            hard_freeze.update(hard_cfg)
        elif isinstance(hard_cfg, dict):
            # New schema: {"keys": [...], "prefixes": [...], ...}
            if isinstance(hard_cfg.get("keys"), list):
                hard_freeze.update(hard_cfg["keys"])
            # Legacy schema: category -> {parameters: [...]}
            for _category, config in hard_cfg.items():
                if isinstance(config, dict):
                    hard_freeze.update(config.get("parameters", []))

        return hard_freeze
    
    def validate_parameter_change(self, param_name: str, new_value: Any) -> Tuple[bool, Optional[str]]:
        """
        Validate if a parameter change is allowed.
        
        Args:
            param_name: Name of parameter to change
            new_value: New value to set
            
        Returns:
            Tuple of (is_allowed, reason_code)
        """
        timestamp = datetime.utcnow().isoformat()
        
        # Check hard freeze violations first (critical)
        if param_name in self.hard_freeze_params:
            reason = f"HARD_FREEZE_VIOLATION: {param_name} is in hard freeze list"
            self._audit_log("REJECT", param_name, new_value, reason, timestamp)
            logger.warning(f"Parameter change rejected: {reason}")
            return False, reason
        
        # Check if parameter is in allowlist
        if param_name not in self.allowlist_params:
            reason = f"NOT_IN_ALLOWLIST: {param_name} not in tunable parameters"
            self._audit_log("REJECT", param_name, new_value, reason, timestamp)
            logger.warning(f"Parameter change rejected: {reason}")
            return False, reason
        
        # Validate range if applicable
        range_valid, range_reason = self._validate_parameter_range(param_name, new_value)
        if not range_valid:
            reason = f"RANGE_VIOLATION: {range_reason}"
            self._audit_log("REJECT", param_name, new_value, reason, timestamp)
            logger.warning(f"Parameter change rejected: {reason}")
            return False, reason
        
        # Parameter change is allowed
        self._audit_log("ALLOW", param_name, new_value, "VALID_CHANGE", timestamp)
        logger.info(f"Parameter change allowed: {param_name} = {new_value}")
        return True, None
    
    def _validate_parameter_range(self, param_name: str, value: Any) -> Tuple[bool, Optional[str]]:
        """Validate parameter value against allowed ranges."""
        allowlist_cfg = self.config.get("allowlist", {})
        if not isinstance(allowlist_cfg, dict):
            return True, None  # Flat allowlist schema has no category range rules

        # Find which category this parameter belongs to
        category = None
        for cat_name, cat_config in allowlist_cfg.items():
            if isinstance(cat_config, dict) and param_name in cat_config.get("parameters", []):
                category = cat_name
                break

        if category is None:
            return True, None  # No range constraints defined

        range_rules = self.config.get("validation_rules", {}).get("allowlist_range_checks", {})
        if category not in range_rules:
            return True, None  # No range rules for this category

        range_config = range_rules[category]
        
        # Check numeric ranges
        if isinstance(value, (int, float)):
            min_val = range_config.get("min")
            max_val = range_config.get("max")
            
            if min_val is not None and value < min_val:
                return False, f"{param_name} = {value} below minimum {min_val}"
            
            if max_val is not None and value > max_val:
                return False, f"{param_name} = {value} above maximum {max_val}"
        
        return True, None
    
    def _audit_log(self, action: str, param_name: str, value: Any, reason: str, timestamp: str):
        """Add entry to audit log."""
        entry = {
            "timestamp": timestamp,
            "action": action,
            "parameter": param_name,
            "value": str(value),
            "reason": reason
        }
        self.audit_log.append(entry)
        
        # Keep audit log size manageable
        if len(self.audit_log) > 10000:
            self.audit_log = self.audit_log[-5000:]
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of validation statistics."""
        total_attempts = len(self.audit_log)
        allowed_count = sum(1 for entry in self.audit_log if entry["action"] == "ALLOW")
        rejected_count = total_attempts - allowed_count
        
        # Group rejections by reason
        rejection_reasons = {}
        for entry in self.audit_log:
            if entry["action"] == "REJECT":
                reason_type = entry["reason"].split(":")[0]
                rejection_reasons[reason_type] = rejection_reasons.get(reason_type, 0) + 1
        
        return {
            "total_validations": total_attempts,
            "allowed_changes": allowed_count,
            "rejected_changes": rejected_count,
            "rejection_reasons": rejection_reasons,
            "allowlist_size": len(self.allowlist_params),
            "hard_freeze_size": len(self.hard_freeze_params),
            "config_version": self.config.get("version"),
            "last_updated": self.config.get("last_updated")
        }
    
    def get_parameter_config(self, param_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration details for a specific parameter."""
        allowlist_cfg = self.config.get("allowlist", {})
        if isinstance(allowlist_cfg, dict):
            for category, config in allowlist_cfg.items():
                if isinstance(config, dict) and param_name in config.get("parameters", []):
                    return {
                        "status": "ALLOWLIST",
                        "category": category,
                        "description": config.get("description"),
                        "range_rules": self.config.get("validation_rules", {}).get("allowlist_range_checks", {}).get(category)
                    }
        elif isinstance(allowlist_cfg, list) and param_name in allowlist_cfg:
            return {
                "status": "ALLOWLIST",
                "category": "flat",
                "description": "Flat allowlist entry",
                "range_rules": None,
            }

        hard_cfg = self.config.get("hard_freeze", {})
        if isinstance(hard_cfg, dict):
            if isinstance(hard_cfg.get("keys"), list) and param_name in hard_cfg["keys"]:
                return {
                    "status": "HARD_FREEZE",
                    "category": "keys",
                    "description": "Hard freeze key",
                    "change_allowed": False,
                }
            for category, config in hard_cfg.items():
                if isinstance(config, dict) and param_name in config.get("parameters", []):
                    return {
                        "status": "HARD_FREEZE",
                        "category": category,
                        "description": config.get("description"),
                        "change_allowed": False
                    }

        if isinstance(hard_cfg, list) and param_name in hard_cfg:
            return {
                "status": "HARD_FREEZE",
                "category": "flat",
                "description": "Hard freeze entry",
                "change_allowed": False,
            }

        return None
    
    def get_config_hash(self) -> str:
        """Get hash of current configuration for traceability."""
        config_str = json.dumps(self.config, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()[:16]
    
    def export_audit_log(self, filepath: Optional[str] = None) -> str:
        """Export audit log to file."""
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"logs/knob_registry_audit_{timestamp}.json"
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        export_data = {
            "export_timestamp": datetime.utcnow().isoformat(),
            "config_hash": self.get_config_hash(),
            "summary": self.get_validation_summary(),
            "audit_log": self.audit_log
        }
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        logger.info(f"Exported knob registry audit log to {filepath}")
        return filepath


# Global instance for system-wide use
_knob_registry_instance = None

def get_knob_registry() -> KnobRegistry:
    """Get global knob registry instance."""
    global _knob_registry_instance
    if _knob_registry_instance is None:
        _knob_registry_instance = KnobRegistry()
    return _knob_registry_instance

def validate_parameter_change(param_name: str, new_value: Any) -> Tuple[bool, Optional[str]]:
    """
    Convenience function to validate parameter change.
    
    Args:
        param_name: Name of parameter to change
        new_value: New value to set
        
    Returns:
        Tuple of (is_allowed, reason_code)
    """
    registry = get_knob_registry()
    return registry.validate_parameter_change(param_name, new_value)