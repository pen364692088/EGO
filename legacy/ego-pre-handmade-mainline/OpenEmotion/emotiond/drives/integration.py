"""
MVP14 T02: Drive Integration

Connects drives to self-model and emotiond core systems.

The formal owner lives in ``openemotion.endogenous_drives``. This bridge keeps
the historical integration API alive while avoiding a second drive authority.
"""
import logging
from typing import Dict, Any, Optional

from openemotion.endogenous_drives import DriveManager, DriveType, get_drive_manager

logger = logging.getLogger(__name__)


class DriveIntegrator:
    """
    Integrates drives with self-model and core systems.
    
    This is the bridge between:
    - Drive system (internal pressures)
    - Self-model (identity and tendencies)
    - Developmental core (candidate scoring)
    """
    
    def __init__(self, drive_manager: Optional[DriveManager] = None):
        self.drive_manager = drive_manager or get_drive_manager()
    
    def sync_with_self_model(self, self_model_state: Any) -> Dict[str, Any]:
        """
        Sync drives with self-model state.
        
        Args:
            self_model_state: SelfModelState from MVP13
            
        Returns:
            Sync result summary
        """
        result = {
            "drives_updated": 0,
            "signals_updated": 0,
        }
        
        # Sync from self-model tensions to drives
        if hasattr(self_model_state, 'active_tensions'):
            for tension_type, tension in self_model_state.active_tensions.tensions.items():
                # Map tensions to drives
                drive_type = self._map_tension_to_drive(tension_type)
                if drive_type:
                    intensity_delta = tension.intensity * 0.1
                    self.drive_manager.accumulate(
                        drive_type,
                        intensity_delta,
                        cause=f"self_model_tension:{tension_type}"
                    )
                    result["drives_updated"] += 1
        
        # Sync from self-model to homeostatic signals
        if hasattr(self_model_state, 'check_identity_invariants'):
            violations = self_model_state.check_identity_invariants()
            
            signal = self.drive_manager.update_homeostatic_signal(
                "identity_stability",
                1.0 if len(violations) == 0 else 0.5
            )
            result["signals_updated"] += 1
        
        # Sync continuity
        if hasattr(self_model_state, 'continuity_trace'):
            entries = len(self_model_state.continuity_trace.entries)
            # High continuity = good signal
            self.drive_manager.update_homeostatic_signal(
                "continuity_quality",
                min(1.0, entries / 50.0)
            )
            result["signals_updated"] += 1
        
        return result
    
    def _map_tension_to_drive(self, tension_type: str) -> Optional[DriveType]:
        """Map tension type to drive type."""
        mapping = {
            "speed_vs_reliability": DriveType.STABILITY,
            "autonomy_vs_governance": DriveType.CONSERVATION,
            "persistence_vs_flexibility": DriveType.EXPLORATION,
            "honesty_vs_harmony": DriveType.COHERENCE,
            "growth_vs_stability": DriveType.COMPLETION,
        }
        return mapping.get(tension_type)
    
    def get_candidate_bias(self) -> Dict[str, float]:
        """
        Get bias for candidate scoring.
        
        Returns:
            Dict mapping bias categories to weights
        """
        priority_bias = self.drive_manager.get_priority_bias()
        
        # Transform to candidate scoring bias
        bias = {
            "stability_weight": priority_bias.get("stability", 0.0),
            "coherence_weight": priority_bias.get("coherence", 0.0),
            "completion_weight": priority_bias.get("completion", 0.0),
            "exploration_weight": priority_bias.get("exploration", 0.0),
            "repair_weight": priority_bias.get("repair", 0.0),
        }
        
        return bias
    
    def get_maintenance_priority(self) -> Dict[str, Any]:
        """
        Get priority for self-maintenance tasks.
        
        Returns:
            Maintenance priority info
        """
        state = self.drive_manager.state
        
        urgent_debts = state.get_urgent_debts()
        unbalanced = state.get_unbalanced_signals()
        
        return {
            "urgent_maintenance": len(urgent_debts),
            "homeostatic_issues": len(unbalanced),
            "repair_drive": self.drive_manager.get_drive_influence(DriveType.REPAIR),
            "should_maintain": len(urgent_debts) > 0 or len(unbalanced) > 2,
        }
    
    def compute_cycle_influence(self) -> float:
        """
        Compute influence factor for developmental cycle.
        
        Returns:
            Influence factor [0, 1]
        """
        total_pressure = self.drive_manager.state.get_total_drive_pressure()
        deviation = self.drive_manager.state.get_total_homeostatic_deviation()
        
        # Higher pressure + deviation = more influence
        influence = min(1.0, (total_pressure / 5.0) + (deviation * 0.5))
        
        return influence
    
    def check_intervention_needed(self) -> Dict[str, Any]:
        """
        Check if drive system needs intervention.
        
        Returns:
            Intervention status
        """
        health = self.drive_manager.check_health()
        
        intervention = {
            "needed": not health["healthy"],
            "reasons": health["issues"],
            "dominant_drive": (
                self.drive_manager.state.get_dominant_drive().drive_type.value
                if self.drive_manager.state.get_dominant_drive() else None
            ),
        }
        
        return intervention


def get_drive_integrator() -> DriveIntegrator:
    """Get DriveIntegrator instance."""
    return DriveIntegrator()
