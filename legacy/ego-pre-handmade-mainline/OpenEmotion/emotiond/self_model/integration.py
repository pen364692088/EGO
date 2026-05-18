"""
MVP13 T02: Self-Model Integration

Connects the new SelfModelState to emotiond core systems.
Provides backward compatibility with legacy self_model API.
"""
import time
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from .schema import (
    SelfModelState,
    IdentityCore,
    BehavioralTendencies,
    ActiveTension,
    TensionType,
    LongHorizonOrientation,
    CapabilityModel,
)
from .persistence import SelfModelPersistence, get_persistence
from .updates import SelfModelUpdater

logger = logging.getLogger(__name__)


class SelfModelManager:
    """
    Manages the persistent self-model instance.
    
    This is the main integration point between:
    - New MVP13 SelfModelState (persistent, structured)
    - Legacy SelfModel API (for backward compatibility)
    - emotiond core systems
    """
    
    _instance: Optional["SelfModelManager"] = None
    
    def __init__(
        self,
        persistence: Optional[SelfModelPersistence] = None,
        auto_save: bool = True
    ):
        self.persistence = persistence or get_persistence()
        self.auto_save = auto_save
        self._state: Optional[SelfModelState] = None
        self._updater: Optional[SelfModelUpdater] = None
    
    @classmethod
    def get_instance(cls) -> "SelfModelManager":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None
    
    @property
    def state(self) -> SelfModelState:
        """Get or load the self-model state."""
        if self._state is None:
            self._state = self._load_or_create()
        return self._state
    
    @property
    def updater(self) -> SelfModelUpdater:
        """Get updater for the current state."""
        if self._updater is None or self._updater.state != self._state:
            self._updater = SelfModelUpdater(self.state)
        return self._updater
    
    def _load_or_create(self) -> SelfModelState:
        """Load existing state or create new one."""
        if self.persistence.exists():
            loaded = self.persistence.load()
            if loaded is not None:
                logger.info("Loaded existing self-model state")
                return loaded
        
        logger.info("Creating new self-model state")
        return SelfModelState()
    
    def save(self) -> bool:
        """Save current state."""
        if self._state is None:
            return True
        return self.persistence.save(self._state)
    
    def get_identity_summary(self) -> Dict[str, Any]:
        """Get identity summary for legacy compatibility."""
        state = self.state
        return {
            "system_name": state.identity_core.system_name,
            "role_definition": state.identity_core.role_definition,
            "operating_orientation": state.identity_core.core_operating_orientation,
            "identity_hash": state.identity_hash,
            "integrity_valid": state.verify_identity_integrity(),
        }
    
    def get_behavioral_profile(self) -> Dict[str, Any]:
        """Get behavioral profile for decision making."""
        return self.state.behavioral_tendencies.get_behavioral_profile()
    
    def get_capability(self, name: str) -> float:
        """Get effective capability value."""
        return self.state.capability_model.get_effective_capability(name)
    
    def get_tension_bias(self, tension_type: TensionType) -> str:
        """Get preferred resolution for a tension."""
        return self.state.active_tensions.get_tension_resolution_bias(tension_type)
    
    def update_behavior(
        self,
        field: str,
        value: float,
        reason: str,
        evidence: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update a behavioral tendency with audit."""
        result = self.updater.update_behavioral_tendency(field, value, reason, evidence)
        if result and self.auto_save:
            self.save()
        return result
    
    def update_capability(
        self,
        name: str,
        capability_delta: Optional[float] = None,
        confidence_delta: Optional[float] = None,
        reason: str = "",
        evidence: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update a capability belief."""
        result = self.updater.update_capability(
            name, capability_delta, confidence_delta, reason, evidence
        )
        if result and self.auto_save:
            self.save()
        return result
    
    def update_tension(
        self,
        tension_type: TensionType,
        intensity: Optional[float] = None,
        preferred_resolution: Optional[str] = None,
        reason: str = ""
    ) -> bool:
        """Update an active tension."""
        result = self.updater.update_active_tension(
            tension_type, intensity, preferred_resolution, reason=reason
        )
        if result and self.auto_save:
            self.save()
        return result
    
    def record_orientation_progress(
        self,
        orientation_id: str,
        progress_delta: float,
        reason: str = ""
    ) -> bool:
        """Record progress on a long-horizon orientation."""
        result = self.updater.update_orientation_progress(
            orientation_id, progress_delta, reason
        )
        if result and self.auto_save:
            self.save()
        return result
    
    def check_health(self) -> Dict[str, Any]:
        """Check self-model health."""
        state = self.state
        violations = state.check_identity_invariants()
        
        return {
            "healthy": len(violations) == 0,
            "identity_integrity": state.verify_identity_integrity(),
            "invariant_violations": violations,
            "revision_count": len(state.revision_history.revisions),
            "continuity_entries": len(state.continuity_trace.entries),
            "persistence_stats": self.persistence.get_statistics(),
        }
    
    def get_full_state(self) -> SelfModelState:
        """Get the full self-model state."""
        return self.state
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the self-model."""
        return self.state.get_summary()


# Convenience functions for integration
def get_self_model_manager() -> SelfModelManager:
    """Get the singleton SelfModelManager."""
    return SelfModelManager.get_instance()


def reset_self_model_manager() -> None:
    """Reset the SelfModelManager singleton."""
    SelfModelManager.reset()
    from .persistence import reset_persistence
    reset_persistence()
