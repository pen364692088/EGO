"""
MVP15 Reflection Shadow Mode

Provides read-only shadow integration for ReflectionEngine.
Generates reflection artifacts without modifying any state.

Usage:
    from emotiond.reflection_shadow import ReflectionShadow
    
    shadow = ReflectionShadow(enable=True)
    shadow.process_event(event, state_snapshot)
"""
import logging
import os
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Feature flag
ENABLE_MVP15_SHADOW = os.environ.get("ENABLE_MVP15_SHADOW", "true").lower() == "true"


class ReflectionShadow:
    """
    Read-only shadow mode for ReflectionEngine.
    
    Features:
    - Read state from core
    - Generate reflection artifacts
    - No state modifications
    - Metrics tracking
    """
    
    _instance: Optional["ReflectionShadow"] = None
    _artifacts_path: Path = Path("artifacts/mvp15")
    
    def __init__(self, enable: bool = True):
        self.enable = enable and ENABLE_MVP15_SHADOW
        self._engine = None
        self._call_count = 0
        self._error_count = 0
        
        if self.enable:
            try:
                from emotiond.reflection_engine import get_reflection_engine
                self._engine = get_reflection_engine()
                self._artifacts_path.mkdir(parents=True, exist_ok=True)
                logger.info("[MVP15] Reflection shadow initialized")
            except Exception as e:
                logger.warning(f"[MVP15] Failed to initialize: {e}")
                self.enable = False
    
    @classmethod
    def get_instance(cls) -> "ReflectionShadow":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def process_event(self, event: Dict[str, Any], state_snapshot: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process event in shadow mode (read-only).
        
        Args:
            event: Event dict from core
            state_snapshot: Current state snapshot
            
        Returns:
            Reflection result if successful, None otherwise
        """
        if not self.enable or not self._engine:
            return None
        
        try:
            self._call_count += 1
            
            # Create reflection job (read-only)
            # Use STATE_AUDIT type for shadow mode
            from emotiond.reflection_engine.schema import ReflectionType
            
            job = self._engine.create_reflection_job(
                reflection_type=ReflectionType.STATE_AUDIT,
                target="event_processing",
                input_evidence={
                    "event_type": event.get("type"),
                    "event_text": event.get("text", "")[:200],
                    "state_keys": list(state_snapshot.keys()),
                }
            )
            
            # Execute reflection (generates artifacts, no state changes)
            result = self._engine.execute_reflection(job)
            
            logger.debug(f"[MVP15] Reflection completed: {result}")
            
            return result
            
        except Exception as e:
            self._error_count += 1
            logger.warning(f"[MVP15] Shadow reflection error: {e}")
            return None
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get shadow mode metrics."""
        return {
            "enable": self.enable,
            "call_count": self._call_count,
            "error_count": self._error_count,
            "artifacts_path": str(self._artifacts_path),
            "artifacts_generated": self._count_artifacts(),
        }
    
    def _count_artifacts(self) -> int:
        """Count generated artifacts."""
        if not self._artifacts_path.exists():
            return 0
        return len(list(self._artifacts_path.glob("*.json")))


def get_reflection_shadow() -> ReflectionShadow:
    """Get the singleton ReflectionShadow instance."""
    return ReflectionShadow.get_instance()
