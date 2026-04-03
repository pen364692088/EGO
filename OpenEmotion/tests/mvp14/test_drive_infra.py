import pytest

from openemotion.endogenous_drives import (
    DriveState,
    ActiveDrive,
    DriveType,
    HomeostaticSignal,
    MaintenanceDebt,
    RegulationTarget,
    DriveHistory,
    EndogenousDriveStore,
    DriveManager,
    get_drive_manager,
    replay_state_from_revisions,
    reset_drive_manager,
    validate_drive_state,
)


class TestDriveSchema:
    def test_active_drive_defaults(self):
        drive = ActiveDrive(drive_id="test", drive_type=DriveType.STABILITY)
        assert drive.intensity == 0.5
        assert drive.persistence == 0.5

    def test_drive_compute_pressure(self):
        drive = ActiveDrive(
            drive_id="test",
            drive_type=DriveType.STABILITY,
            intensity=0.8,
            persistence=0.6,
        )
        assert drive.compute_pressure() == 0.48

    def test_homeostatic_signal_in_range(self):
        signal = HomeostaticSignal(
            signal_id="test",
            category="health",
            observed_value=0.5,
            desired_range_min=0.3,
            desired_range_max=0.7,
        )
        deviation = signal.compute_deviation()
        assert deviation == 0.0
        assert signal.is_in_balance()

    def test_homeostatic_signal_below_range(self):
        signal = HomeostaticSignal(
            signal_id="test",
            category="health",
            observed_value=0.2,
            desired_range_min=0.3,
            desired_range_max=0.7,
        )
        deviation = signal.compute_deviation()
        assert abs(deviation - 0.1) < 0.001
        assert not signal.is_in_balance()

    def test_homeostatic_signal_above_range(self):
        signal = HomeostaticSignal(
            signal_id="test",
            category="health",
            observed_value=0.8,
            desired_range_min=0.3,
            desired_range_max=0.7,
        )
        deviation = signal.compute_deviation()
        assert abs(deviation - 0.1) < 0.001
        assert not signal.is_in_balance()

    def test_maintenance_debt(self):
        debt = MaintenanceDebt(debt_id="test", category="repair")
        assert debt.amount == 0.0
        debt.add_debt(0.5)
        assert debt.amount == 0.5
        debt.reduce_debt(0.3)
        assert debt.amount == 0.2

    def test_regulation_target(self):
        target = RegulationTarget(target_name="test", desired_range_min=0.3, desired_range_max=0.7)
        target.update_observed(0.5)
        assert target.is_regulated()
        target.update_observed(0.9)
        assert not target.is_regulated()
        assert abs(target.deviation_level - 0.2) < 0.001

    def test_drive_history(self):
        history = DriveHistory()
        entry = history.record(
            drive_id="test",
            change_type="activation",
            old_value=None,
            new_value=0.5,
            cause="test",
        )
        assert len(history.entries) == 1
        assert entry.drive_id == "test"


class TestDriveState:
    def test_create_default_state(self):
        state = DriveState()
        assert state.active_drives is not None
        assert state.homeostatic_signals is not None

    def test_get_total_pressure(self):
        state = DriveState()
        state.active_drives["d1"] = ActiveDrive(
            drive_id="d1",
            drive_type=DriveType.STABILITY,
            intensity=0.5,
            persistence=0.8,
        )
        state.active_drives["d2"] = ActiveDrive(
            drive_id="d2",
            drive_type=DriveType.COHERENCE,
            intensity=0.6,
            persistence=0.5,
        )
        assert state.get_total_drive_pressure() == 0.5 * 0.8 + 0.6 * 0.5

    def test_get_dominant_drive(self):
        state = DriveState()
        state.active_drives["d1"] = ActiveDrive(drive_id="d1", drive_type=DriveType.STABILITY, intensity=0.3)
        state.active_drives["d2"] = ActiveDrive(drive_id="d2", drive_type=DriveType.COHERENCE, intensity=0.7)
        assert state.get_dominant_drive().drive_id == "d2"

    def test_get_summary(self):
        summary = DriveState().get_summary()
        assert "active_drive_count" in summary
        assert "total_drive_pressure" in summary


class TestDriveManager:
    def test_singleton(self):
        reset_drive_manager()
        assert get_drive_manager() is get_drive_manager()

    def test_default_drives_initialized(self):
        reset_drive_manager()
        manager = get_drive_manager()
        assert len(manager.state.active_drives) > 0
        assert DriveType.STABILITY.value in manager.state.active_drives

    def test_update_drive(self):
        reset_drive_manager()
        manager = get_drive_manager()
        drive = manager.update_drive(DriveType.STABILITY, 0.2, cause="test")
        assert drive.intensity > 0.4

    def test_accumulate(self):
        reset_drive_manager()
        manager = get_drive_manager()
        initial = manager.state.active_drives[DriveType.STABILITY.value].intensity
        drive = manager.accumulate(DriveType.STABILITY, 0.1, "test")
        assert drive.intensity > initial

    def test_homeostatic_signal_update(self):
        reset_drive_manager()
        manager = get_drive_manager()
        signal = manager.update_homeostatic_signal("identity_stability", 0.9)
        assert signal.observed_value == 0.9

    def test_homeostatic_deviation_triggers_drive(self):
        reset_drive_manager()
        manager = get_drive_manager()
        initial = manager.state.active_drives[DriveType.STABILITY.value].intensity
        manager.update_homeostatic_signal("identity_stability", 0.1)
        assert manager.state.active_drives[DriveType.STABILITY.value].intensity > initial

    def test_add_maintenance_debt(self):
        reset_drive_manager()
        manager = get_drive_manager()
        debt = manager.add_maintenance_debt(category="repair", amount=0.5, priority=0.8)
        assert debt.amount == 0.5
        assert debt.priority == 0.8

    def test_reduce_maintenance_debt(self):
        reset_drive_manager()
        manager = get_drive_manager()
        debt = manager.add_maintenance_debt("repair", 0.5)
        manager.reduce_maintenance_debt(debt.debt_id, 0.3)
        assert manager.state.maintenance_debt[debt.debt_id].amount == pytest.approx(0.2)

    def test_get_drive_influence(self):
        reset_drive_manager()
        manager = get_drive_manager()
        influence = manager.get_drive_influence(DriveType.STABILITY)
        assert 0.0 <= influence <= 1.0

    def test_get_priority_bias(self):
        reset_drive_manager()
        manager = get_drive_manager()
        bias = manager.get_priority_bias()
        assert isinstance(bias, dict)
        assert len(bias) > 0

    def test_check_health(self):
        reset_drive_manager()
        manager = get_drive_manager()
        health = manager.check_health()
        assert "healthy" in health
        assert "issues" in health
        assert "summary" in health


class TestDriveOwnerInfra:
    def test_store_roundtrip_and_replay(self, tmp_path):
        reset_drive_manager()
        manager = DriveManager(store=EndogenousDriveStore(tmp_path))
        manager.accumulate(DriveType.COMPLETION, 0.1, "test_roundtrip")
        record = manager.persist(update_source="test_roundtrip")
        loaded = manager.store.load()
        revisions = manager.store.load_revision_log()
        replayed = replay_state_from_revisions(revisions)
        assert record.revision_id == "drive_rev_000001"
        assert loaded is not None
        assert loaded.last_revision_id == record.revision_id
        assert replayed is not None
        assert replayed.last_revision_id == record.revision_id

    def test_governance_rejects_excessive_pressure(self):
        state = DriveState()
        for drive_type in DriveType:
            state.active_drives[drive_type.value] = ActiveDrive(
                drive_id=drive_type.value,
                drive_type=drive_type,
                intensity=1.0,
                persistence=1.0,
            )
        verdict = validate_drive_state(state)
        assert not verdict.accepted
        assert "excessive_drive_pressure" in verdict.violations


class TestExitCriteria:
    def test_drives_structurally_represented(self):
        state = DriveState()
        assert isinstance(state.active_drives, dict)
        assert isinstance(state.homeostatic_signals, dict)
        assert isinstance(state.maintenance_debt, dict)
        assert isinstance(state.regulation_targets, dict)

    def test_accumulation_decay_working(self):
        reset_drive_manager()
        manager = get_drive_manager()
        initial = manager.state.active_drives[DriveType.STABILITY.value].intensity
        manager.accumulate(DriveType.STABILITY, 0.1, "test")
        assert manager.state.active_drives[DriveType.STABILITY.value].intensity > initial
        before_decay = manager.state.active_drives[DriveType.STABILITY.value].intensity
        manager.apply_decay()
        assert manager.state.active_drives[DriveType.STABILITY.value].intensity < before_decay

    def test_homeostatic_deviation_detectable(self):
        reset_drive_manager()
        manager = get_drive_manager()
        manager.update_homeostatic_signal("identity_stability", 0.1)
        assert len(manager.state.get_unbalanced_signals()) > 0

    def test_self_maintenance_traceable(self):
        reset_drive_manager()
        manager = get_drive_manager()
        debt = manager.add_maintenance_debt("repair", 0.5, source="test")
        manager.reduce_maintenance_debt(debt.debt_id, 0.3)
        assert len(manager.state.drive_history.entries) > 0

    def test_no_drive_bypasses_governance(self):
        reset_drive_manager()
        manager = get_drive_manager()
        influence = manager.get_drive_influence(DriveType.STABILITY)
        assert 0.0 <= influence <= 1.0
        bias = manager.get_priority_bias()
        for value in bias.values():
            assert 0.0 <= value <= 1.0

    def test_drive_influence_measurable(self):
        reset_drive_manager()
        manager = get_drive_manager()
        influences = [manager.get_drive_influence(drive_type) for drive_type in DriveType]
        coverage = len([value for value in influences if value > 0]) / len(influences)
        assert coverage >= 0.95
