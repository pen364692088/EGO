"""
MVP13 SelfModel Mirror Adapter

Provides read-only mirror of SelfModelV0 for new SelfModelManager.
Does NOT write back to legacy state.

Usage:
    from emotiond.self_model_mirror import SelfModelMirrorAdapter
    
    adapter = SelfModelMirrorAdapter()
    mirrored_state = adapter.mirror_from_legacy(legacy_self_model_v0)
"""
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path
import json
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class MirrorMetrics:
    """Metrics for mirror operations."""
    total_mirrors: int = 0
    successful_mirrors: int = 0
    failed_mirrors: int = 0
    invariant_violations: int = 0
    avg_conversion_time_ms: float = 0.0
    # New metrics (2026-03-13)
    p95_conversion_time_ms: float = 0.0
    key_field_missing_rate: float = 0.0
    event_type_coverage: Dict[str, int] = field(default_factory=dict)
    conversion_times: List[float] = field(default_factory=list)


class SelfModelMirrorAdapter:
    """
    Mirrors SelfModelV0 state to new SelfModelManager format.
    
    Read-only: Does NOT write back to legacy state.
    Only writes to shadow artifacts for verification.
    """
    
    _instance: Optional["SelfModelMirrorAdapter"] = None
    _artifacts_path: Path = Path("artifacts/mvp13/mirror")
    
    # Field mapping: legacy -> new
    LEGACY_TO_NEW_MAPPING = {
        "self_protection": "self_preservation",
        "affiliation": "connection_seeking",
        "self_actualization": "growth_orientation",
    }
    
    def __init__(self, enable: bool = True):
        self.enable = enable
        self.metrics = MirrorMetrics()
        self._mirror_history: list = []
        
        if enable:
            self._artifacts_path.mkdir(parents=True, exist_ok=True)
            logger.info("[MVP13] SelfModelMirrorAdapter initialized (read-only)")
    
    @classmethod
    def get_instance(cls) -> "SelfModelMirrorAdapter":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def mirror_from_legacy(self, legacy_state: Any) -> Optional[Dict[str, Any]]:
        """
        Mirror legacy SelfModelV0 state to new format.
        
        Args:
            legacy_state: SelfModelV0 instance
            
        Returns:
            Mirrored state dict (NOT written to legacy)
        """
        if not self.enable:
            return None
        
        start_time = datetime.now()
        self.metrics.total_mirrors += 1
        
        try:
            # Extract legacy values
            legacy_dict = self._extract_legacy_state(legacy_state)
            
            # Convert to new format
            mirrored_state = self._convert_to_new_format(legacy_dict)
            
            # Check invariants
            invariant_result = self._check_invariants(legacy_dict, mirrored_state)
            if not invariant_result["passed"]:
                self.metrics.invariant_violations += 1
                logger.warning(f"[MVP13] Invariant violation: {invariant_result['violations']}")
            
            # Record successful mirror
            self.metrics.successful_mirrors += 1
            
            # Calculate conversion time
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            self.metrics.conversion_times.append(elapsed_ms)
            self.metrics.avg_conversion_time_ms = (
                (self.metrics.avg_conversion_time_ms * (self.metrics.successful_mirrors - 1) + elapsed_ms)
                / self.metrics.successful_mirrors
            )
            
            # Calculate p95 conversion time
            if self.metrics.conversion_times:
                sorted_times = sorted(self.metrics.conversion_times)
                p95_index = int(len(sorted_times) * 0.95)
                self.metrics.p95_conversion_time_ms = sorted_times[min(p95_index, len(sorted_times) - 1)]
            
            # Update event type coverage
            event_type = "default"  # Would be extracted from event context
            self.metrics.event_type_coverage[event_type] = self.metrics.event_type_coverage.get(event_type, 0) + 1
            
            # Write to shadow artifacts (NOT to legacy)
            self._write_shadow_artifact(mirrored_state, invariant_result)
            
            # Record history
            self._mirror_history.append({
                "timestamp": datetime.now().isoformat(),
                "success": True,
                "invariant_passed": invariant_result["passed"],
                "conversion_time_ms": elapsed_ms,
            })
            
            logger.debug(f"[MVP13] Mirror successful: {invariant_result['passed']}")
            
            return mirrored_state
            
        except Exception as e:
            self.metrics.failed_mirrors += 1
            logger.warning(f"[MVP13] Mirror failed: {e}")
            
            self._mirror_history.append({
                "timestamp": datetime.now().isoformat(),
                "success": False,
                "error": str(e),
            })
            
            return None
    
    def _extract_legacy_state(self, legacy_state: Any) -> Dict[str, Any]:
        """Extract state from legacy SelfModelV0."""
        result = {
            "traits": {},
            "narrative": "",
            "value_weights": {},
        }
        
        # Extract traits
        if hasattr(legacy_state, "traits"):
            result["traits"] = dict(legacy_state.traits)
        
        # Extract narrative
        if hasattr(legacy_state, "narrative"):
            result["narrative"] = legacy_state.narrative
        
        # Extract value_weights
        if hasattr(legacy_state, "value_weights"):
            vw = legacy_state.value_weights
            result["value_weights"] = {
                "self_protection": getattr(vw, "self_protection", 0.5),
                "affiliation": getattr(vw, "affiliation", 0.5),
                "self_actualization": getattr(vw, "self_actualization", 0.5),
            }
        
        # Extract hash if available
        if hasattr(legacy_state, "compute_hash"):
            result["legacy_hash"] = legacy_state.compute_hash()
        
        return result
    
    def _convert_to_new_format(self, legacy_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Convert legacy format to new SelfModelManager format."""
        return {
            "identity": {
                "core_traits": legacy_dict.get("traits", {}),
                "core_narrative": legacy_dict.get("narrative", ""),
            },
            "behavioral_tendencies": {
                self.LEGACY_TO_NEW_MAPPING.get(k, k): v
                for k, v in legacy_dict.get("value_weights", {}).items()
            },
            "capability_assessments": {},
            "tension_biases": {},
            "legacy_hash": legacy_dict.get("legacy_hash", ""),
            "mirror_timestamp": datetime.now().isoformat(),
        }
    
    def _check_invariants(self, legacy_dict: Dict[str, Any], mirrored_state: Dict[str, Any]) -> Dict[str, Any]:
        """Check that invariants are preserved during mirror."""
        violations = []
        
        # Invariant 1: Traits should be preserved
        legacy_traits = set(legacy_dict.get("traits", {}).keys())
        mirrored_traits = set(mirrored_state.get("identity", {}).get("core_traits", {}).keys())
        if legacy_traits != mirrored_traits:
            violations.append(f"Traits mismatch: {legacy_traits} vs {mirrored_traits}")
        
        # Invariant 2: Narrative should be preserved
        legacy_narrative = legacy_dict.get("narrative", "")
        mirrored_narrative = mirrored_state.get("identity", {}).get("core_narrative", "")
        if legacy_narrative != mirrored_narrative:
            violations.append("Narrative mismatch")
        
        # Invariant 3: Value weights should sum approximately same
        legacy_sum = sum(legacy_dict.get("value_weights", {}).values())
        mirrored_sum = sum(mirrored_state.get("behavioral_tendencies", {}).values())
        if abs(legacy_sum - mirrored_sum) > 0.01:
            violations.append(f"Value sum mismatch: {legacy_sum} vs {mirrored_sum}")
        
        return {
            "passed": len(violations) == 0,
            "violations": violations,
        }
    
    def _write_shadow_artifact(self, mirrored_state: Dict[str, Any], invariant_result: Dict[str, Any]) -> None:
        """Write shadow artifact (NOT to legacy state)."""
        try:
            artifact = {
                "mirrored_state": mirrored_state,
                "invariant_check": invariant_result,
                "timestamp": datetime.now().isoformat(),
            }
            
            artifact_path = self._artifacts_path / f"mirror_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(artifact_path, "w") as f:
                json.dump(artifact, f, indent=2, default=str)
            
        except Exception as e:
            logger.warning(f"[MVP13] Failed to write shadow artifact: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get mirror metrics."""
        return {
            "enable": self.enable,
            "total_mirrors": self.metrics.total_mirrors,
            "successful_mirrors": self.metrics.successful_mirrors,
            "failed_mirrors": self.metrics.failed_mirrors,
            "invariant_violations": self.metrics.invariant_violations,
            "success_rate": (
                self.metrics.successful_mirrors / max(1, self.metrics.total_mirrors)
                if self.metrics.total_mirrors > 0 else 0
            ),
            "invariant_violation_rate": (
                self.metrics.invariant_violations / max(1, self.metrics.successful_mirrors)
                if self.metrics.successful_mirrors > 0 else 0
            ),
            "avg_conversion_time_ms": self.metrics.avg_conversion_time_ms,
            "p95_conversion_time_ms": self.metrics.p95_conversion_time_ms,
            "key_field_missing_rate": self.metrics.key_field_missing_rate,
            "event_type_coverage": self.metrics.event_type_coverage,
        }


def get_self_model_mirror() -> SelfModelMirrorAdapter:
    """Get the singleton SelfModelMirrorAdapter instance."""
    return SelfModelMirrorAdapter.get_instance()
