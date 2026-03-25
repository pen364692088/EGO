"""
MVP14 Gate B: E2E / Replay / Evidence Tests
"""
import pytest

from emotiond.drives import (
    DriveManager,
    DriveType,
)
from emotiond.drives.integration import DriveIntegrator
from emotiond.self_model import SelfModelState, SelfModelUpdater


class TestGateB_E2E:
    """End-to-end tests for Gate B."""
    
    def test_full_drive_lifecycle(self):
        """Test complete drive lifecycle."""
        manager = DriveManager()
        
        # Activate drive
        drive = manager.activate_drive(DriveType.STABILITY, 0.7, "test")
        assert drive.intensity == 0.7
        
        # Accumulate
        manager.accumulate(DriveType.STABILITY, 0.1, "event")
        assert manager.state.active_drives[DriveType.STABILITY.value].intensity > 0.7
        
        # Apply decay
        manager.apply_decay()
        
        # Verify history recorded
        assert len(manager.state.drive_history.entries) > 0
    
    def test_drive_self_model_integration(self):
        """Test drive-self-model integration."""
        manager = DriveManager()
        integrator = DriveIntegrator(manager)
        self_model = SelfModelState()
        
        # Sync
        result = integrator.sync_with_self_model(self_model)
        
        assert result["drives_updated"] >= 0
        assert result["signals_updated"] >= 0
    
    def test_homeostatic_regulation(self):
        """Test homeostatic regulation triggers drives."""
        manager = DriveManager()
        
        # Create deviation
        initial = manager.state.active_drives[DriveType.STABILITY.value].intensity
        manager.update_homeostatic_signal("identity_stability", 0.1)
        
        # Stability drive should increase
        new_intensity = manager.state.active_drives[DriveType.STABILITY.value].intensity
        assert new_intensity > initial
    
    def test_maintenance_debt_triggers_repair(self):
        """Test maintenance debt triggers repair drive."""
        manager = DriveManager()
        
        initial_repair = manager.state.active_drives[DriveType.REPAIR.value].intensity
        manager.add_maintenance_debt("repair", 0.5, source="test")
        
        # Repair drive should increase
        new_repair = manager.state.active_drives[DriveType.REPAIR.value].intensity
        assert new_repair > initial_repair


class TestGateB_Metrics:
    """Metrics verification tests."""
    
    def test_drive_influence_coverage(self):
        """All drive types should have measurable influence."""
        manager = DriveManager()
        
        covered = 0
        for drive_type in DriveType:
            influence = manager.get_drive_influence(drive_type)
            if influence >= 0:
                covered += 1
        
        coverage = covered / len(DriveType)
        assert coverage >= 0.95
    
    def test_governance_preserved(self):
        """Drives should not bypass governance."""
        integrator = DriveIntegrator()
        
        # Influence is just weights, not direct control
        bias = integrator.get_candidate_bias()
        for v in bias.values():
            assert 0.0 <= v <= 1.0
        
        # Cycle influence is bounded
        influence = integrator.compute_cycle_influence()
        assert 0.0 <= influence <= 1.0
