"""
MVP-10 T21: Science Mode Switch

Unified interface for controlling interventions in experiments.
All interventions are managed through this single interface,
eliminating scattered if-else checks across the codebase.

Key features:
- Enable/disable interventions with traceable logging
- Inject parameters for controlled experiments
- Log all interventions to run header for reproducibility
"""
import time
import json
import hashlib
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .interventions import (
    InterventionType,
    InterventionConfig,
    InterventionResult,
    InterventionManager,
    FreezeValenceIntervention,
    DisableHOTIntervention,
    DisableBroadcastIntervention,
)


class ScienceModeState(Enum):
    """State of science mode."""
    DISABLED = "disabled"  # Normal operation
    ENABLED = "enabled"    # Science mode active
    PAUSED = "paused"      # Temporarily paused


@dataclass
class InterventionSpec:
    """Specification for an intervention to apply."""
    intervention_type: InterventionType
    params: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    priority: int = 0  # Higher priority applied last


@dataclass
class RunHeader:
    """
    Header for a science run, logged to artifacts.
    
    Contains all intervention configurations for reproducibility.
    """
    run_id: str
    seed: int
    science_mode: ScienceModeState
    interventions: List[Dict[str, Any]]
    config_hash: str
    ts: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def compute_config_hash(self) -> str:
        """Compute hash of intervention configs for integrity."""
        config_str = json.dumps(self.interventions, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for logging."""
        return {
            "run_id": self.run_id,
            "seed": self.seed,
            "science_mode": self.science_mode.value,
            "interventions": self.interventions,
            "config_hash": self.config_hash,
            "ts": self.ts,
            "metadata": self.metadata,
        }


class ScienceMode:
    """
    Unified interface for science mode interventions.
    
    This class provides a single point of control for all interventions,
    eliminating the need for scattered if-else checks across the codebase.
    
    Usage:
        science = ScienceMode()
        
        # Start a science run
        science.start_run(seed=42)
        
        # Enable interventions
        science.enable_intervention(
            InterventionType.FREEZE_VALENCE,
            params={"valence": 0.5},
            reason="Testing valence effect"
        )
        
        # During tick loop, check interventions through unified interface
        if science.is_intervention_active(InterventionType.FREEZE_VALENCE):
            valence = science.get_intervention_param(
                InterventionType.FREEZE_VALENCE, "valence"
            )
        
        # End run and get header
        header = science.end_run()
    
    All interventions are logged to the run header for reproducibility.
    """
    
    def __init__(self, artifacts_dir: Optional[str] = None):
        """
        Initialize science mode.
        
        Args:
            artifacts_dir: Directory to store run headers (optional)
        """
        self._state = ScienceModeState.DISABLED
        self._manager = InterventionManager()
        self._active_specs: Dict[InterventionType, InterventionSpec] = {}
        self._run_header: Optional[RunHeader] = None
        self._artifacts_dir = Path(artifacts_dir) if artifacts_dir else None
        self._intervention_log: List[Dict[str, Any]] = []
    
    @property
    def state(self) -> ScienceModeState:
        """Get current science mode state."""
        return self._state
    
    @property
    def is_enabled(self) -> bool:
        """Check if science mode is enabled."""
        return self._state == ScienceModeState.ENABLED
    
    @property
    def run_id(self) -> Optional[str]:
        """Get current run ID if a run is active."""
        return self._run_header.run_id if self._run_header else None
    
    def start_run(
        self,
        seed: int,
        run_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Start a new science run.
        
        Args:
            seed: Random seed for reproducibility
            run_id: Optional run identifier (auto-generated if not provided)
            metadata: Optional metadata to include in run header
        
        Returns:
            The run ID
        """
        import uuid
        run_id = run_id or f"science_{uuid.uuid4().hex[:8]}"
        
        self._run_header = RunHeader(
            run_id=run_id,
            seed=seed,
            science_mode=ScienceModeState.ENABLED,
            interventions=[],
            config_hash="",
            metadata=metadata or {},
        )
        
        self._state = ScienceModeState.ENABLED
        self._intervention_log = []
        
        return run_id
    
    def enable_intervention(
        self,
        intervention_type: InterventionType,
        params: Optional[Dict[str, Any]] = None,
        reason: str = "",
        priority: int = 0,
    ) -> InterventionResult:
        """
        Enable an intervention.
        
        Args:
            intervention_type: Type of intervention to enable
            params: Parameters for the intervention
            reason: Reason for enabling (for logging)
            priority: Priority for application order
        
        Returns:
            InterventionResult indicating success
        """
        if not self.is_enabled:
            raise RuntimeError("Science mode not enabled. Call start_run() first.")
        
        spec = InterventionSpec(
            intervention_type=intervention_type,
            params=params or {},
            reason=reason,
            priority=priority,
        )
        
        # Store spec
        self._active_specs[intervention_type] = spec
        
        # Enable in manager
        result = self._manager.enable(intervention_type, params, reason)
        
        # Log to intervention log
        log_entry = {
            "action": "enable",
            "intervention_type": intervention_type.value,
            "params": params or {},
            "reason": reason,
            "priority": priority,
            "ts": time.time(),
            "success": result.success,
        }
        self._intervention_log.append(log_entry)
        
        # Update run header
        if self._run_header:
            self._run_header.interventions.append(log_entry)
            self._run_header.config_hash = self._run_header.compute_config_hash()
        
        return result
    
    def disable_intervention(self, intervention_type: InterventionType) -> InterventionResult:
        """
        Disable an intervention.
        
        Args:
            intervention_type: Type of intervention to disable
        
        Returns:
            InterventionResult indicating success
        """
        # Remove from active specs
        if intervention_type in self._active_specs:
            del self._active_specs[intervention_type]
        
        # Disable in manager
        result = self._manager.disable(intervention_type)
        
        # Log
        log_entry = {
            "action": "disable",
            "intervention_type": intervention_type.value,
            "ts": time.time(),
            "success": result.success,
        }
        self._intervention_log.append(log_entry)
        
        # Update run header
        if self._run_header:
            self._run_header.interventions.append(log_entry)
            self._run_header.config_hash = self._run_header.compute_config_hash()
        
        return result
    
    def is_intervention_active(self, intervention_type: InterventionType) -> bool:
        """
        Check if an intervention is active.
        
        This is the unified interface for checking interventions.
        All code should use this method instead of scattered if-else checks.
        
        Args:
            intervention_type: Type of intervention to check
        
        Returns:
            True if the intervention is active
        """
        return self._manager.is_active(intervention_type)
    
    def get_intervention_param(
        self,
        intervention_type: InterventionType,
        param_name: str,
        default: Any = None,
    ) -> Any:
        """
        Get a parameter value for an active intervention.
        
        Args:
            intervention_type: Type of intervention
            param_name: Name of the parameter
            default: Default value if not found
        
        Returns:
            Parameter value or default
        """
        config = self._manager.get_config(intervention_type)
        if config:
            return config.params.get(param_name, default)
        return default
    
    def get_all_active_interventions(self) -> Set[InterventionType]:
        """
        Get all currently active intervention types.
        
        Returns:
            Set of active intervention types
        """
        return set(self._active_specs.keys())
    
    def apply_to_state(
        self,
        valence: float,
        drives: Optional[Any] = None,
        policy: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Apply all active interventions to the given state.
        
        This is the unified interface for applying interventions.
        All code should use this method instead of scattered intervention logic.
        
        Args:
            valence: Current valence value
            drives: Current Drives instance
            policy: Current ValencePolicy instance
        
        Returns:
            Dict with potentially modified values
        """
        return self._manager.apply_intervention(valence, drives, policy)
    
    def pause(self) -> None:
        """Pause science mode (interventions remain configured but not applied)."""
        self._state = ScienceModeState.PAUSED
    
    def resume(self) -> None:
        """Resume science mode from paused state."""
        if self._run_header:
            self._state = ScienceModeState.ENABLED
    
    def end_run(self) -> RunHeader:
        """
        End the current science run.
        
        Returns:
            The run header with all intervention logs
        
        Raises:
            RuntimeError: If no run is active
        """
        if not self._run_header:
            raise RuntimeError("No active run to end.")
        
        # Set final state
        self._run_header.science_mode = self._state
        
        # Compute final hash
        self._run_header.config_hash = self._run_header.compute_config_hash()
        
        # Save header to artifacts if directory is set
        if self._artifacts_dir:
            self._save_run_header()
        
        header = self._run_header
        self._run_header = None
        self._state = ScienceModeState.DISABLED
        self._active_specs = {}
        self._manager.clear_all()
        
        return header
    
    def _save_run_header(self) -> None:
        """Save run header to artifacts directory."""
        if not self._artifacts_dir or not self._run_header:
            return
        
        self._artifacts_dir.mkdir(parents=True, exist_ok=True)
        header_path = self._artifacts_dir / f"header_{self._run_header.run_id}.json"
        
        with open(header_path, 'w') as f:
            json.dump(self._run_header.to_dict(), f, indent=2)
    
    def get_intervention_log(self) -> List[Dict[str, Any]]:
        """Get the full intervention log for the current run."""
        return self._intervention_log.copy()
    
    def inject_parameters(
        self,
        params: Dict[InterventionType, Dict[str, Any]],
        reason: str = "bulk_injection",
    ) -> Dict[InterventionType, InterventionResult]:
        """
        Bulk inject parameters for multiple interventions.
        
        Args:
            params: Dict mapping intervention types to their parameters
            reason: Reason for injection
        
        Returns:
            Dict mapping intervention types to their results
        """
        results = {}
        for intervention_type, intervention_params in params.items():
            results[intervention_type] = self.enable_intervention(
                intervention_type,
                params=intervention_params,
                reason=reason,
            )
        return results
    
    def create_freeze_valence(self, valence: float) -> FreezeValenceIntervention:
        """
        Create a freeze_valence intervention.
        
        Args:
            valence: Valence value to freeze to
        
        Returns:
            FreezeValenceIntervention instance
        """
        from .interventions import create_freeze_valence_intervention
        return create_freeze_valence_intervention(valence)
    
    def create_disable_hot(self) -> DisableHOTIntervention:
        """
        Create a disable_hot intervention.
        
        Returns:
            DisableHOTIntervention instance
        """
        from .interventions import create_disable_hot_intervention
        return create_disable_hot_intervention()
    
    def create_disable_broadcast(self) -> DisableBroadcastIntervention:
        """
        Create a disable_broadcast intervention.
        
        Returns:
            DisableBroadcastIntervention instance
        """
        from .interventions import create_disable_broadcast_intervention
        return create_disable_broadcast_intervention()
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize science mode state."""
        return {
            "state": self._state.value,
            "run_id": self.run_id,
            "active_interventions": [it.value for it in self._active_specs.keys()],
            "intervention_log_count": len(self._intervention_log),
            "manager": self._manager.to_dict(),
        }


def create_science_mode(artifacts_dir: Optional[str] = None) -> ScienceMode:
    """
    Factory function to create a ScienceMode instance.
    
    Args:
        artifacts_dir: Directory to store run headers
    
    Returns:
        ScienceMode instance
    """
    return ScienceMode(artifacts_dir=artifacts_dir)
