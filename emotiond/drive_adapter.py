"""
MVP14 DriveState Adapter

Provides backward-compatible interface for legacy DriveState (drive_homeostasis.py)
while delegating to new DriveManager (drives/manager.py) in dual-run mode.

This adapter enables:
1. Legacy API continues to work
2. New DriveManager runs in parallel
3. Comparison logging for validation
4. Gradual migration path
"""
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AdapterMetrics:
    """Metrics for adapter monitoring."""
    legacy_calls: int = 0
    new_calls: int = 0
    mismatches: int = 0
    errors: int = 0


class DriveStateAdapter:
    """
    Adapts between legacy DriveState and new DriveManager.
    
    Usage:
        adapter = DriveStateAdapter(enable_dual_run=True)
        
        # Legacy API
        drive_state = adapter.get_legacy_state()
        params = adapter.get_drive_modulation_params()
        
        # New API (dual-run)
        new_state = adapter.get_new_state()
        
        # Metrics
        metrics = adapter.get_adapter_metrics()
    """
    
    _instance: Optional["DriveStateAdapter"] = None
    
    # Field mapping: legacy -> new
    LEGACY_TO_NEW_MAPPING = {
        "energy": "stability",
        "uncertainty": "coherence", 
        "social": "completion",
        "safety": "verification",
        "fatigue": "repair",
    }
    
    def __init__(self, enable_dual_run: bool = True):
        """
        Initialize adapter.
        
        Args:
            enable_dual_run: If True, run both legacy and new in parallel.
                            If False, only use legacy.
        """
        self.enable_dual_run = enable_dual_run
        self.metrics = AdapterMetrics()
        
        # Initialize legacy
        from emotiond.drive_homeostasis import DriveState as LegacyDriveState
        self._legacy_state = LegacyDriveState()
        
        # Initialize new (if dual-run enabled)
        self._new_manager = None
        if enable_dual_run:
            try:
                from emotiond.drives import get_drive_manager
                self._new_manager = get_drive_manager()
                logger.info("[MVP14] DriveStateAdapter initialized with dual-run mode")
            except Exception as e:
                logger.warning(f"[MVP14] Failed to initialize new DriveManager: {e}")
                self.enable_dual_run = False
    
    @classmethod
    def get_instance(cls) -> "DriveStateAdapter":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None
    
    # === Legacy API Compatibility ===
    
    def get_legacy_state(self):
        """Get legacy DriveState instance."""
        self.metrics.legacy_calls += 1
        return self._legacy_state
    
    def get_drive_modulation_params(self) -> Dict[str, Any]:
        """
        Get drive modulation params (legacy API).
        
        Returns params from legacy, optionally comparing with new.
        """
        from emotiond.drive_homeostasis import get_drive_modulation_params
        self.metrics.legacy_calls += 1
        
        # Get legacy params
        legacy_params = get_drive_modulation_params(self._legacy_state)
        
        # Dual-run: compare with new
        if self.enable_dual_run and self._new_manager:
            try:
                new_params = self._get_new_modulation_params()
                self._compare_params(legacy_params, new_params)
                self.metrics.new_calls += 1
            except Exception as e:
                logger.warning(f"[MVP14] Error getting new params: {e}")
                self.metrics.errors += 1
        
        # Always return legacy params (no behavior change)
        return legacy_params
    
    def drive_error(self) -> float:
        """Compute overall drive error (legacy API)."""
        from emotiond.drive_homeostasis import drive_error
        self.metrics.legacy_calls += 1
        return drive_error(self._legacy_state)
    
    def emotion_from_drive(self) -> str:
        """Map drive state to emotion (legacy API)."""
        from emotiond.drive_homeostasis import emotion_from_drive
        self.metrics.legacy_calls += 1
        return emotion_from_drive(self._legacy_state)
    
    # === New API Access ===
    
    def get_new_state(self):
        """Get new DriveManager state."""
        if not self._new_manager:
            return None
        self.metrics.new_calls += 1
        return self._new_manager.get_state()
    
    def _get_new_modulation_params(self) -> Dict[str, Any]:
        """Get modulation params from new DriveManager."""
        if not self._new_manager:
            return {}
        
        state = self._new_manager.get_state()
        
        # Map new state to legacy-style params
        # This is a simplified mapping for comparison
        return {
            "risk_aversion": 0.036,  # Placeholder
            "initiative_level": 0.982,  # Placeholder
            "source": "new_manager",
        }
    
    # === Comparison and Monitoring ===
    
    def _compare_params(self, legacy: Dict, new: Dict) -> None:
        """Compare legacy and new params, log mismatches."""
        # For now, just log the comparison
        # In production, this would do detailed comparison
        if legacy.get("risk_aversion") != new.get("risk_aversion"):
            self.metrics.mismatches += 1
            logger.debug(
                f"[MVP14] Param mismatch: "
                f"legacy_risk={legacy.get('risk_aversion')}, "
                f"new_risk={new.get('risk_aversion')}"
            )
    
    def get_adapter_metrics(self) -> Dict[str, Any]:
        """Get adapter metrics for monitoring."""
        return {
            "enable_dual_run": self.enable_dual_run,
            "legacy_calls": self.metrics.legacy_calls,
            "new_calls": self.metrics.new_calls,
            "mismatches": self.metrics.mismatches,
            "errors": self.metrics.errors,
            "mismatch_rate": (
                self.metrics.mismatches / max(1, self.metrics.new_calls)
                if self.metrics.new_calls > 0 else 0
            ),
        }
    
    # === Update Methods (dual-write) ===
    
    def update_component(self, name: str, delta: float) -> None:
        """Update a drive component (dual-write)."""
        # Update legacy
        self._legacy_state.update_component(name, delta)
        
        # Update new (if dual-run)
        if self.enable_dual_run and self._new_manager:
            try:
                new_name = self.LEGACY_TO_NEW_MAPPING.get(name, name)
                # New manager uses DriveType enum
                from emotiond.drives.schema import DriveType
                drive_type = DriveType(new_name)
                self._new_manager.accumulate(drive_type, abs(delta), f"legacy_update_{name}")
                self.metrics.new_calls += 1
            except Exception as e:
                logger.warning(f"[MVP14] Error updating new drive: {e}")
                self.metrics.errors += 1


# Convenience function
def get_drive_adapter() -> DriveStateAdapter:
    """Get the singleton DriveStateAdapter instance."""
    return DriveStateAdapter.get_instance()
