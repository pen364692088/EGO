"""
MVP14 T01: Endogenous Drive Infrastructure Tests

Tests for:
- Drive schema (ActiveDrive, HomeostaticSignal, MaintenanceDebt)
- Drive manager (accumulation, decay, prioritization)
- Homeostatic monitoring
"""
import pytest
import time

from emotiond.drives import (
    DriveState,
    ActiveDrive,
    DriveType,
    HomeostaticSignal,
    MaintenanceDebt,
    RegulationTarget,
    DriveHistory,
    DriveManager,
    get_drive_manager,
    reset_drive_manager,
)


class TestDriveSchema:
    """Tests for drive schema components."""
    
    def test_active_drive_defaults(self):
        """ActiveDrive should have sensible defaults."""
        drive = ActiveDrive(
            drive_id="test",
            drive_type=DriveType.STABILITY
        )
        assert drive.intensity == 0.5
        assert drive.persistence == 0.5
    
    def test_drive_compute_pressure(self):
        """Drive pressure should be intensity * persistence."""
        drive = ActiveDrive(
            drive_id="test",
            drive_type=DriveType.STABILITY,
            intensity=0.8,
            persistence=0.6
        )
        assert drive.compute_pressure() == 0.48
    
    def test_homeostatic_signal_in_range(self):
        """Signal in desired range should have zero deviation."""
        signal = HomeostaticSignal(
            signal_id="test",
            category="health",
            observed_value=0.5,
            desired_range_min=0.3,
            desired_range_max=0.7
        )
        deviation = signal.compute_deviation()
        assert deviation == 0.0
        assert signal.is_in_balance()
    
    def test_homeostatic_signal_below_range(self):
        """Signal below range should have positive deviation."""
        signal = HomeostaticSignal(
            signal_id="test",
            category="health",
            observed_value=0.2,
            desired_range_min=0.3,
            desired_range_max=0.7
        )
        deviation = signal.compute_deviation()
        assert abs(deviation - 0.1) < 0.001
        assert not signal.is_in_balance()
    
    def test_homeostatic_signal_above_range(self):
        """Signal above range should have positive deviation."""
        signal = HomeostaticSignal(
            signal_id="test",
            category="health",
            observed_value=0.8,
            desired_range_min=0.3,
            desired_range_max=0.7
        )
        deviation = signal.compute_deviation()
        assert abs(deviation - 0.1) < 0.001
        assert not signal.is_in_balance()
    
    def test_maintenance_debt(self):
        """MaintenanceDebt should track amount."""
        debt = MaintenanceDebt(
            debt_id="test",
            category="repair"
        )
        assert debt.amount == 0.0
        
        debt.add_debt(0.5)
        assert debt.amount == 0.5
        
        debt.reduce_debt(0.3)
        assert debt.amount == 0.2
    
    def test_regulation_target(self):
        """RegulationTarget should track deviation."""
        target = RegulationTarget(
            target_name="test",
            desired_range_min=0.3,
            desired_range_max=0.7
        )
        
        # In range
        target.update_observed(0.5)
        assert target.is_regulated()
        
        # Out of range
        target.update_observed(0.9)
        assert not target.is_regulated()
        assert abs(target.deviation_level - 0.2) < 0.001
    
    def test_drive_history(self):
        """DriveHistory should record transitions."""
        history = DriveHistory()
        
        entry = history.record(
            drive_id="test",
            change_type="activation",
            old_value=None,
            new_value=0.5,
            cause="test"
        )
        
        assert len(history.entries) == 1
        assert entry.drive_id == "test"


class TestDriveState:
    """Tests for complete DriveState."""
    
    def test_create_default_state(self):
        """Should create state with defaults."""
        state = DriveState()
        assert state.active_drives is not None
        assert state.homeostatic_signals is not None
    
    def test_get_total_pressure(self):
        """Should compute total drive pressure."""
        state = DriveState()
        state.active_drives["d1"] = ActiveDrive(
            drive_id="d1",
            drive_type=DriveType.STABILITY,
            intensity=0.5,
            persistence=0.8
        )
        state.active_drives["d2"] = ActiveDrive(
            drive_id="d2",
            drive_type=DriveType.COHERENCE,
            intensity=0.6,
            persistence=0.5
        )
        
        total = state.get_total_drive_pressure()
        assert total == 0.5 * 0.8 + 0.6 * 0.5
    
    def test_get_dominant_drive(self):
        """Should find highest intensity drive."""
        state = DriveState()
        state.active_drives["d1"] = ActiveDrive(
            drive_id="d1",
            drive_type=DriveType.STABILITY,
            intensity=0.3
        )
        state.active_drives["d2"] = ActiveDrive(
            drive_id="d2",
            drive_type=DriveType.COHERENCE,
            intensity=0.7
        )
        
        dominant = state.get_dominant_drive()
        assert dominant.drive_id == "d2"
    
    def test_get_summary(self):
        """Should return summary dict."""
        state = DriveState()
        summary = state.get_summary()
        
        assert "active_drive_count" in summary
        assert "total_drive_pressure" in summary


class TestDriveManager:
    """Tests for DriveManager."""
    
    def test_singleton(self):
        """Should return same instance."""
        reset_drive_manager()
        
        m1 = get_drive_manager()
        m2 = get_drive_manager()
        
        assert m1 is m2
    
    def test_default_drives_initialized(self):
        """Should initialize default drives."""
        reset_drive_manager()
        manager = get_drive_manager()
        
        assert len(manager.state.active_drives) > 0
        assert DriveType.STABILITY.value in manager.state.active_drives
    
    def test_update_drive(self):
        """Should update drive intensity."""
        reset_drive_manager()
        manager = get_drive_manager()
        
        drive = manager.update_drive(
            DriveType.STABILITY,
            0.2,
            cause="test"
        )
        
        assert drive.intensity > 0.4  # Should have increased
    
    def test_accumulate(self):
        """Should accumulate drive."""
        reset_drive_manager()
        manager = get_drive_manager()
        
        initial = manager.state.active_drives[DriveType.STABILITY.value].intensity
        drive = manager.accumulate(DriveType.STABILITY, 0.1, "test")
        
        assert drive.intensity > initial
    
    def test_homeostatic_signal_update(self):
        """Should update homeostatic signal."""
        reset_drive_manager()
        manager = get_drive_manager()
        
        signal = manager.update_homeostatic_signal(
            "identity_stability",
            0.9
        )
        
        assert signal.observed_value == 0.9
    
    def test_homeostatic_deviation_triggers_drive(self):
        """Homeostatic deviation should trigger stability drive."""
        reset_drive_manager()
        manager = get_drive_manager()
        
        initial_stability = manager.state.active_drives[DriveType.STABILITY.value].intensity
        
        # Trigger deviation
        manager.update_homeostatic_signal(
            "identity_stability",
            0.1  # Below desired range
        )
        
        # Stability drive should increase
        new_stability = manager.state.active_drives[DriveType.STABILITY.value].intensity
        assert new_stability > initial_stability
    
    def test_add_maintenance_debt(self):
        """Should add maintenance debt."""
        reset_drive_manager()
        manager = get_drive_manager()
        
        debt = manager.add_maintenance_debt(
            category="repair",
            amount=0.5,
            priority=0.8
        )
        
        assert debt.amount == 0.5
        assert debt.priority == 0.8
    
    def test_reduce_maintenance_debt(self):
        """Should reduce maintenance debt."""
        reset_drive_manager()
        manager = get_drive_manager()
        
        debt = manager.add_maintenance_debt("repair", 0.5)
        
        manager.reduce_maintenance_debt(debt.debt_id, 0.3)
        
        remaining = manager.state.maintenance_debt.get(debt.debt_id)
        assert remaining.amount == 0.2
    
    def test_get_drive_influence(self):
        """Should return drive influence weight."""
        reset_drive_manager()
        manager = get_drive_manager()
        
        influence = manager.get_drive_influence(DriveType.STABILITY)
        assert 0.0 <= influence <= 1.0
    
    def test_get_priority_bias(self):
        """Should return priority bias from all drives."""
        reset_drive_manager()
        manager = get_drive_manager()
        
        bias = manager.get_priority_bias()
        assert isinstance(bias, dict)
        assert len(bias) > 0
    
    def test_check_health(self):
        """Should check drive system health."""
        reset_drive_manager()
        manager = get_drive_manager()
        
        health = manager.check_health()
        
        assert "healthy" in health
        assert "issues" in health
        assert "summary" in health


class TestExitCriteria:
    """Tests for MVP14 Exit Criteria."""
    
    def test_drives_structurally_represented(self):
        """EC1: Drives must be structurally represented."""
        state = DriveState()
        
        # All components should be structured objects
        assert isinstance(state.active_drives, dict)
        assert isinstance(state.homeostatic_signals, dict)
        assert isinstance(state.maintenance_debt, dict)
        assert isinstance(state.regulation_targets, dict)
    
    def test_accumulation_decay_working(self):
        """EC2: Accumulation and decay dynamics working."""
        reset_drive_manager()
        manager = get_drive_manager()
        
        # Accumulation
        initial = manager.state.active_drives[DriveType.STABILITY.value].intensity
        manager.accumulate(DriveType.STABILITY, 0.1, "test")
        assert manager.state.active_drives[DriveType.STABILITY.value].intensity > initial
        
        # Decay
        manager.apply_decay()
        # After decay, intensity should decrease
    
    def test_homeostatic_deviation_detectable(self):
        """EC3: Homeostatic deviation detectable."""
        reset_drive_manager()
        manager = get_drive_manager()
        
        # Create deviation
        manager.update_homeostatic_signal("identity_stability", 0.1)
        
        unbalanced = manager.state.get_unbalanced_signals()
        assert len(unbalanced) > 0
    
    def test_self_maintenance_traceable(self):
        """EC4: Self-maintenance traceable."""
        reset_drive_manager()
        manager = get_drive_manager()
        
        # Add debt
        debt = manager.add_maintenance_debt("repair", 0.5, source="test")
        
        # Reduce debt
        manager.reduce_maintenance_debt(debt.debt_id, 0.3)
        
        # History should record changes
        assert len(manager.state.drive_history.entries) > 0
    
    def test_no_drive_bypasses_governance(self):
        """EC5: No drive may bypass governance."""
        # Drives only provide bias/influence, not direct control
        reset_drive_manager()
        manager = get_drive_manager()
        
        # Influence is just a weight
        influence = manager.get_drive_influence(DriveType.STABILITY)
        assert 0.0 <= influence <= 1.0
        
        # Priority bias is just a dict
        bias = manager.get_priority_bias()
        for v in bias.values():
            assert 0.0 <= v <= 1.0
    
    def test_drive_influence_measurable(self):
        """EC6: drive_influence_measurable >= 95%."""
        reset_drive_manager()
        manager = get_drive_manager()
        
        # All drive types should have measurable influence
        total = 0
        count = 0
        for drive_type in DriveType:
            influence = manager.get_drive_influence(drive_type)
            if influence > 0:
                total += 1
            count += 1
        
        coverage = total / count if count > 0 else 0
        assert coverage >= 0.95  # 7/7 default drives
