"""
MVP14 T01: Drive Manager

Manages endogenous drives with accumulation, decay, and prioritization.
"""
import time
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from .schema import (
    DriveState,
    ActiveDrive,
    DriveType,
    HomeostaticSignal,
    MaintenanceDebt,
    RegulationTarget,
    DriveHistory,
)

logger = logging.getLogger(__name__)


class DriveManager:
    """
    Manages endogenous drives.
    
    Features:
    - Drive activation and deactivation
    - Accumulation and decay dynamics
    - Homeostatic monitoring
    - Maintenance debt tracking
    """
    
    _instance: Optional["DriveManager"] = None
    
    # Decay rate per cycle (drives decay over time)
    DECAY_RATE = 0.01
    
    # Accumulation rate per input event
    ACCUMULATION_RATE = 0.05
    
    # Threshold for drive activation
    ACTIVATION_THRESHOLD = 0.3
    
    # Threshold for drive deactivation
    DEACTIVATION_THRESHOLD = 0.1
    
    def __init__(self, initial_state: Optional[DriveState] = None):
        self.state = initial_state or DriveState()
        self._initialize_default_drives()
        self._initialize_homeostatic_signals()
        self._initialize_regulation_targets()
    
    @classmethod
    def get_instance(cls) -> "DriveManager":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None
    
    def _initialize_default_drives(self) -> None:
        """Initialize default drive types.
        
        MVP14 Normalization: Default values aligned with legacy DriveState.
        - stability = legacy energy (0.75)
        - coherence = legacy uncertainty (0.25)
        - completion = legacy social (0.5)
        - verification = legacy safety (0.75)
        - repair = legacy fatigue (0.15)
        """
        default_drives = [
            (DriveType.STABILITY, 0.75, "System stability maintenance"),  # normalized: match legacy energy
            (DriveType.COHERENCE, 0.25, "Internal consistency maintenance"),  # normalized: match legacy uncertainty
            (DriveType.COMPLETION, 0.5, "Goal completion pressure"),  # normalized: match legacy social
            (DriveType.VERIFICATION, 0.75, "State verification drive"),  # normalized: match legacy safety
            (DriveType.REPAIR, 0.15, "Self-repair drive"),  # normalized: match legacy fatigue
            (DriveType.EXPLORATION, 0.4, "Capability exploration drive"),
            (DriveType.CONSERVATION, 0.3, "Resource conservation drive"),
        ]
        
        for drive_type, intensity, source in default_drives:
            if drive_type.value not in self.state.active_drives:
                self.state.active_drives[drive_type.value] = ActiveDrive(
                    drive_id=drive_type.value,
                    drive_type=drive_type,
                    intensity=intensity,
                    source=source
                )
    
    def _initialize_homeostatic_signals(self) -> None:
        """Initialize default homeostatic signals."""
        default_signals = [
            ("identity_stability", 0.8, 0.6, 1.0),
            ("continuity_quality", 0.7, 0.5, 1.0),
            ("maintenance_balance", 0.5, 0.3, 0.7),
            ("tension_resolution", 0.4, 0.2, 0.6),
        ]
        
        for name, value, min_val, max_val in default_signals:
            if name not in self.state.homeostatic_signals:
                signal = HomeostaticSignal(
                    signal_id=name,
                    category="system_health",
                    observed_value=value,
                    desired_range_min=min_val,
                    desired_range_max=max_val
                )
                signal.compute_deviation()
                self.state.homeostatic_signals[name] = signal
    
    def _initialize_regulation_targets(self) -> None:
        """Initialize default regulation targets."""
        default_targets = [
            ("drive_pressure", 0.2, 0.8),
            ("homeostatic_deviation", 0.0, 0.3),
            ("maintenance_debt", 0.0, 0.5),
        ]
        
        for name, min_val, max_val in default_targets:
            if name not in self.state.regulation_targets:
                self.state.regulation_targets[name] = RegulationTarget(
                    target_name=name,
                    desired_range_min=min_val,
                    desired_range_max=max_val
                )
    
    def update_drive(
        self,
        drive_type: DriveType,
        intensity_delta: float,
        cause: str = "",
        evidence: Optional[Dict[str, Any]] = None
    ) -> ActiveDrive:
        """
        Update a drive's intensity.
        
        Args:
            drive_type: Type of drive to update
            intensity_delta: Change in intensity (+ or -)
            cause: Reason for the update
            evidence: Supporting evidence
            
        Returns:
            The updated drive
        """
        drive_id = drive_type.value
        
        if drive_id not in self.state.active_drives:
            # Create new drive
            drive = ActiveDrive(
                drive_id=drive_id,
                drive_type=drive_type,
                intensity=min(1.0, max(0.0, self.ACTIVATION_THRESHOLD + intensity_delta)),
                source=cause
            )
            self.state.active_drives[drive_id] = drive
        else:
            drive = self.state.active_drives[drive_id]
            old_intensity = drive.intensity
            drive.intensity = min(1.0, max(0.0, drive.intensity + intensity_delta))
            drive.last_updated = time.time()
            
            # Record history
            self.state.drive_history.record(
                drive_id=drive_id,
                change_type="intensity_update",
                old_value=old_intensity,
                new_value=drive.intensity,
                cause=cause,
                evidence=evidence
            )
        
        self.state.update_timestamp()
        return self.state.active_drives[drive_id]
    
    def apply_decay(self) -> None:
        """Apply decay to all active drives."""
        for drive_id, drive in self.state.active_drives.items():
            old_intensity = drive.intensity
            drive.intensity = max(0.0, drive.intensity - self.DECAY_RATE)
            
            if drive.intensity < self.DEACTIVATION_THRESHOLD:
                # Move to latent drives
                self.state.latent_drives[drive_id] = drive
                del self.state.active_drives[drive_id]
            elif old_intensity != drive.intensity:
                self.state.drive_history.record(
                    drive_id=drive_id,
                    change_type="decay",
                    old_value=old_intensity,
                    new_value=drive.intensity,
                    cause="automatic_decay"
                )
        
        self.state.update_timestamp()
    
    def accumulate(
        self,
        drive_type: DriveType,
        amount: float = 0.05,
        cause: str = ""
    ) -> ActiveDrive:
        """
        Accumulate a drive (increase intensity).
        
        Args:
            drive_type: Type of drive
            amount: Amount to add
            cause: Reason for accumulation
            
        Returns:
            The updated drive
        """
        return self.update_drive(drive_type, amount, cause)
    
    def activate_drive(
        self,
        drive_type: DriveType,
        intensity: float = 0.5,
        source: str = ""
    ) -> ActiveDrive:
        """
        Activate a drive with specific intensity.
        
        Args:
            drive_type: Type of drive
            intensity: Target intensity
            source: Source of activation
            
        Returns:
            The activated drive
        """
        drive_id = drive_type.value
        
        # Check if in latent drives
        if drive_id in self.state.latent_drives:
            drive = self.state.latent_drives.pop(drive_id)
            drive.intensity = intensity
            drive.source = source
            drive.last_updated = time.time()
            self.state.active_drives[drive_id] = drive
        else:
            drive = ActiveDrive(
                drive_id=drive_id,
                drive_type=drive_type,
                intensity=intensity,
                source=source
            )
            self.state.active_drives[drive_id] = drive
        
        self.state.drive_history.record(
            drive_id=drive_id,
            change_type="activation",
            old_value=None,
            new_value=intensity,
            cause=source
        )
        
        self.state.update_timestamp()
        return drive
    
    def update_homeostatic_signal(
        self,
        signal_id: str,
        observed_value: float
    ) -> HomeostaticSignal:
        """
        Update a homeostatic signal.
        
        Args:
            signal_id: Signal identifier
            observed_value: New observed value
            
        Returns:
            The updated signal
        """
        if signal_id not in self.state.homeostatic_signals:
            signal = HomeostaticSignal(
                signal_id=signal_id,
                category="custom",
                observed_value=observed_value
            )
            self.state.homeostatic_signals[signal_id] = signal
        else:
            signal = self.state.homeostatic_signals[signal_id]
            signal.observed_value = observed_value
        
        deviation = signal.compute_deviation()
        signal.last_checked = time.time()
        
        # If deviation, trigger related drives
        if deviation > 0.1:
            self.accumulate(DriveType.STABILITY, deviation * 0.5, f"homeostatic_deviation:{signal_id}")
        
        self.state.update_timestamp()
        return signal
    
    def add_maintenance_debt(
        self,
        category: str,
        amount: float,
        priority: float = 0.5,
        source: str = ""
    ) -> MaintenanceDebt:
        """
        Add maintenance debt.
        
        Args:
            category: Debt category
            amount: Debt amount
            priority: Priority level
            source: Source of debt
            
        Returns:
            The debt entry
        """
        debt_id = f"{category}_{int(time.time())}"
        
        debt = MaintenanceDebt(
            debt_id=debt_id,
            category=category,
            amount=amount,
            priority=priority,
            source=source
        )
        
        self.state.maintenance_debt[debt_id] = debt
        
        # Trigger repair drive
        self.accumulate(DriveType.REPAIR, amount * 0.1, f"maintenance_debt:{category}")
        
        self.state.update_timestamp()
        return debt
    
    def reduce_maintenance_debt(
        self,
        debt_id: str,
        amount: float
    ) -> Optional[MaintenanceDebt]:
        """
        Reduce maintenance debt.
        
        Args:
            debt_id: Debt identifier
            amount: Amount to reduce
            
        Returns:
            The updated debt or None
        """
        if debt_id not in self.state.maintenance_debt:
            return None
        
        debt = self.state.maintenance_debt[debt_id]
        old_amount = debt.amount
        debt.reduce_debt(amount)
        
        # Remove if fully paid
        if debt.amount == 0:
            del self.state.maintenance_debt[debt_id]
        
        self.state.update_timestamp()
        return debt
    
    def update_regulation_target(
        self,
        target_name: str,
        observed_value: float
    ) -> RegulationTarget:
        """
        Update a regulation target.
        
        Args:
            target_name: Target name
            observed_value: New observed value
            
        Returns:
            The updated target
        """
        if target_name not in self.state.regulation_targets:
            self.state.regulation_targets[target_name] = RegulationTarget(
                target_name=target_name
            )
        
        target = self.state.regulation_targets[target_name]
        target.update_observed(observed_value)
        
        self.state.update_timestamp()
        return target
    
    def get_drive_influence(self, drive_type: DriveType) -> float:
        """
        Get the influence weight for a drive.
        
        This can be used to bias candidate scoring.
        
        Args:
            drive_type: Type of drive
            
        Returns:
            Influence weight [0, 1]
        """
        drive_id = drive_type.value
        
        if drive_id not in self.state.active_drives:
            return 0.0
        
        drive = self.state.active_drives[drive_id]
        return drive.compute_pressure()
    
    def get_priority_bias(self) -> Dict[str, float]:
        """
        Get priority bias from all drives.
        
        Returns:
            Dict mapping drive types to bias values
        """
        return {
            drive_id: drive.compute_pressure()
            for drive_id, drive in self.state.active_drives.items()
        }
    
    def check_health(self) -> Dict[str, Any]:
        """
        Check drive system health.
        
        Returns:
            Health status dict
        """
        summary = self.state.get_summary()
        
        issues = []
        
        # Check for high homeostatic deviation
        if summary["homeostatic_deviation"] > 0.5:
            issues.append("high_homeostatic_deviation")
        
        # Check for urgent maintenance debt
        if summary["urgent_debts"] > 3:
            issues.append("high_maintenance_debt")
        
        # Check for drive imbalance
        if summary["total_drive_pressure"] > 5.0:
            issues.append("excessive_drive_pressure")
        
        return {
            "healthy": len(issues) == 0,
            "issues": issues,
            "summary": summary,
        }
    
    def get_state(self) -> DriveState:
        """Get current drive state."""
        return self.state
    
    def get_summary(self) -> Dict[str, Any]:
        """Get drive state summary."""
        return self.state.get_summary()


def get_drive_manager() -> DriveManager:
    """Get singleton DriveManager."""
    return DriveManager.get_instance()


def reset_drive_manager() -> None:
    """Reset DriveManager singleton."""
    DriveManager.reset()
