"""
MVP14 DriveState Adapter

Provides backward-compatible interface for legacy DriveState (drive_homeostasis.py)
while projecting into the formal owner drive surface under
``openemotion.endogenous_drives``.

This adapter is intentionally a compatibility/projection helper, not a second
drives authority.
"""
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from openemotion.endogenous_drives.action_bias import compute_action_bias_from_priority_snapshot

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
    def get_instance(cls, enable_dual_run: Optional[bool] = None) -> "DriveStateAdapter":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls(enable_dual_run=True if enable_dual_run is None else enable_dual_run)
            return cls._instance

        if enable_dual_run is not None and enable_dual_run != cls._instance.enable_dual_run:
            cls._instance.enable_dual_run = enable_dual_run
            if enable_dual_run and cls._instance._new_manager is None:
                try:
                    from emotiond.drives import get_drive_manager
                    cls._instance._new_manager = get_drive_manager()
                except Exception as e:
                    logger.warning(f"[MVP14] Failed to enable DriveManager dual-run: {e}")
                    cls._instance.enable_dual_run = False
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

    def build_legacy_state(
        self,
        components: Dict[str, float],
        *,
        source: str = "snapshot",
        sync_new_manager: bool = True,
    ):
        """
        Build a fresh legacy-compatible state snapshot.

        The core mainline should consume the adapter, not import the legacy
        module directly. This method keeps that boundary while optionally
        syncing the formal-owner target in dual-run mode.
        """
        from emotiond.drive_homeostasis import DriveState as LegacyDriveState

        state = LegacyDriveState()
        for name, value in components.items():
            state.update_component(name, value)

        self._legacy_state = state
        self.metrics.legacy_calls += 1

        if sync_new_manager and self.enable_dual_run and self._new_manager:
            self._sync_new_manager_from_legacy_components(components, source=source)

        return state

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

    def get_drive_modulation_params_for_components(
        self,
        components: Dict[str, float],
        *,
        source: str = "snapshot",
        sync_new_manager: bool = True,
    ) -> Dict[str, Any]:
        """
        Get legacy-compatible modulation params from a fresh snapshot.

        This is the bounded migration path for Step05B: the mainline can move
        to the adapter interface first, while the legacy calculation remains an
        internal compatibility layer until the formal-owner path is ready to
        take over.
        """
        from emotiond.drive_homeostasis import get_drive_modulation_params

        state = self.build_legacy_state(
            components,
            source=source,
            sync_new_manager=sync_new_manager,
        )
        return get_drive_modulation_params(state)

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

    def get_owner_backed_action_bias(self, action: str) -> float:
        """
        Compute action bias from the formal owner drive state.

        This is the Step05C proof surface: the decision mainline may consume a
        bounded, auditable bias derived from the formal owner package without
        re-promoting the legacy drive_homeostasis surface as authority.
        """
        if not self.enable_dual_run or not self._new_manager:
            return 0.0

        priority_bias = self._new_manager.get_priority_bias()
        self.metrics.new_calls += 1
        return compute_action_bias_from_priority_snapshot(action, priority_bias)

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

    def _sync_new_manager_from_legacy_components(
        self,
        components: Dict[str, float],
        *,
        source: str = "legacy_snapshot",
    ) -> None:
        """Sync legacy snapshot values into the new DriveManager."""
        if not self._new_manager:
            return

        from emotiond.drives.schema import DriveType

        state = self._new_manager.get_state()

        for legacy_name, value in components.items():
            new_name = self.LEGACY_TO_NEW_MAPPING.get(legacy_name)
            if not new_name:
                continue

            try:
                drive_type = DriveType(new_name)
            except ValueError:
                continue

            drive = state.active_drives.get(drive_type.value)
            current = drive.intensity if drive else 0.0
            delta = float(value) - float(current)
            if abs(delta) <= 1e-9:
                continue
            self._new_manager.update_drive(drive_type, delta, cause=f"{source}:{legacy_name}")

        self.metrics.new_calls += 1

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
def get_drive_adapter(enable_dual_run: Optional[bool] = None) -> DriveStateAdapter:
    """Get the singleton DriveStateAdapter instance."""
    return DriveStateAdapter.get_instance(enable_dual_run=enable_dual_run)
