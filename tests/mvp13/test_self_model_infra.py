"""
MVP13 T01: Self-Model Infrastructure Tests

Tests for:
- Extended schema (identity, constraints, tendencies, tensions, orientations, capabilities)
- Persistence layer (save/load, backup, recovery)
- Update rules (audit logging, revision history, invariants)
"""
import pytest
import tempfile
import time
from pathlib import Path

from emotiond.self_model import (
    SelfModelState,
    IdentityCore,
    StableConstraints,
    BehavioralTendencies,
    ActiveTension,
    ActiveTensions,
    TensionType,
    LongHorizonOrientation,
    LongHorizonOrientations,
    CapabilityModel,
    ContinuityTrace,
    RevisionHistory,
    SelfModelPersistence,
    SelfModelUpdater,
    UpdateRuleError,
    IdentityInvariantViolation,
)


class TestSchema:
    """Tests for self-model schema components."""
    
    def test_identity_core_defaults(self):
        """IdentityCore should have sensible defaults."""
        identity = IdentityCore()
        assert identity.system_name == "OpenEmotion"
        assert len(identity.protected_identity_statements) > 0
        assert identity.compute_hash() is not None
    
    def test_identity_core_hash_stability(self):
        """Identity hash should be deterministic."""
        identity1 = IdentityCore()
        identity2 = IdentityCore()
        assert identity1.compute_hash() == identity2.compute_hash()
    
    def test_stable_constraints_defaults(self):
        """StableConstraints should have default boundaries."""
        constraints = StableConstraints()
        assert len(constraints.architectural_boundaries) > 0
        assert len(constraints.policy_boundaries) > 0
        assert len(constraints.no_authority_zones) > 0
    
    def test_behavioral_tendencies_range(self):
        """Behavioral tendencies should be in [0, 1] range."""
        tendencies = BehavioralTendencies(
            caution_bias=0.5,
            exploration_bias=0.5,
            self_correction_tendency=0.5,
            verification_preference=0.5
        )
        profile = tendencies.get_behavioral_profile()
        assert "risk_stance" in profile
        assert "approach_stance" in profile
    
    def test_active_tensions(self):
        """ActiveTensions should manage tension dictionary."""
        tensions = ActiveTensions()
        assert tensions.get_dominant_tension() is not None
        
        resolution = tensions.get_tension_resolution_bias(TensionType.SPEED_VS_RELIABILITY)
        assert resolution in ["speed", "reliability", "balanced"]
    
    def test_long_horizon_orientations(self):
        """LongHorizonOrientations should manage priority list."""
        orientations = LongHorizonOrientations()
        top = orientations.get_top_orientations(2)
        assert len(top) == 2
    
    def test_capability_model(self):
        """CapabilityModel should compute effective capabilities."""
        caps = CapabilityModel()
        effective = caps.get_effective_capability("clarify")
        assert 0.0 <= effective <= 1.0
    
    def test_continuity_trace(self):
        """ContinuityTrace should record entries."""
        trace = ContinuityTrace()
        trace.add_entry("test_event", {"key": "value"}, trigger="test")
        assert len(trace.entries) == 1
        recent = trace.get_recent_transitions(1)
        assert recent[0].event == "test_event"
    
    def test_revision_history(self):
        """RevisionHistory should record revisions."""
        history = RevisionHistory()
        revision = history.record_revision(
            previous_hash="abc123",
            changed_fields=["field1"],
            reason="test",
            evidence={}
        )
        assert revision.revision_id == "rev_000001"
        assert len(history.revisions) == 1


class TestSelfModelState:
    """Tests for complete SelfModelState."""
    
    def test_create_default_state(self):
        """Should create state with all defaults."""
        state = SelfModelState()
        assert state.identity_core is not None
        assert state.stable_constraints is not None
        assert state.behavioral_tendencies is not None
    
    def test_identity_integrity(self):
        """Should verify identity integrity."""
        state = SelfModelState()
        assert state.verify_identity_integrity()
    
    def test_check_invariants(self):
        """Should check identity invariants."""
        state = SelfModelState()
        violations = state.check_identity_invariants()
        assert len(violations) == 0
    
    def test_compute_state_hash_stability(self):
        """State hash should be stable for same state."""
        state = SelfModelState()
        hash1 = state.compute_state_hash()
        hash2 = state.compute_state_hash()
        assert hash1 == hash2
    
    def test_compute_state_hash_changes_on_update(self):
        """State hash should change when state changes."""
        state = SelfModelState()
        hash1 = state.compute_state_hash()
        
        # Modify state
        state.behavioral_tendencies.caution_bias = 0.9
        hash2 = state.compute_state_hash()
        
        assert hash1 != hash2
    
    def test_get_summary(self):
        """Should return summary dict."""
        state = SelfModelState()
        summary = state.get_summary()
        assert "version" in summary
        assert "identity_integrity" in summary
        assert summary["identity_integrity"] is True


class TestPersistence:
    """Tests for self-model persistence layer."""
    
    def test_save_and_load(self):
        """Should save and load state correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SelfModelPersistence(base_dir=tmpdir)
            state = SelfModelState()
            
            # Save
            assert persistence.save(state)
            
            # Load
            loaded = persistence.load()
            assert loaded is not None
            assert loaded.identity_core.system_name == state.identity_core.system_name
            assert loaded.verify_identity_integrity()
    
    def test_statistics(self):
        """Should track persistence statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SelfModelPersistence(base_dir=tmpdir)
            state = SelfModelState()
            
            persistence.save(state)
            persistence.load()
            
            stats = persistence.get_statistics()
            assert stats["save_count"] == 1
            assert stats["load_count"] == 1
            assert stats["success_rate"] == 1.0
    
    def test_verify_integrity(self):
        """Should verify persisted state integrity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SelfModelPersistence(base_dir=tmpdir)
            state = SelfModelState()
            
            persistence.save(state)
            
            is_valid, message = persistence.verify_integrity()
            assert is_valid
            assert "valid" in message.lower()
    
    def test_backup_creation(self):
        """Should create backups on save."""
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SelfModelPersistence(base_dir=tmpdir, auto_backup=True)
            state = SelfModelState()
            
            # First save
            persistence.save(state)
            
            # Modify and save again
            state.behavioral_tendencies.caution_bias = 0.7
            persistence.save(state)
            
            stats = persistence.get_statistics()
            assert stats["backup_count"] >= 1


class TestUpdater:
    """Tests for self-model update rules."""
    
    def test_update_behavioral_tendency(self):
        """Should update behavioral tendencies with audit."""
        state = SelfModelState()
        updater = SelfModelUpdater(state)
        
        updater.update_behavioral_tendency(
            "caution_bias", 0.7, "Test update", {"test": True}
        )
        
        assert state.behavioral_tendencies.caution_bias == 0.7
        assert len(state.revision_history.revisions) == 1
    
    def test_update_behavioral_tendency_gradual(self):
        """Should apply gradual updates (max 0.1 change)."""
        state = SelfModelState()
        state.behavioral_tendencies.caution_bias = 0.5
        updater = SelfModelUpdater(state)
        
        # Try to jump from 0.5 to 0.9
        updater.update_behavioral_tendency("caution_bias", 0.9, "Large jump")
        
        # Should only move 0.1
        assert state.behavioral_tendencies.caution_bias == 0.6
    
    def test_update_active_tension(self):
        """Should update active tensions."""
        state = SelfModelState()
        updater = SelfModelUpdater(state)
        
        updater.update_active_tension(
            TensionType.SPEED_VS_RELIABILITY,
            intensity=0.8,
            preferred_resolution="reliability",
            reason="Test"
        )
        
        tension = state.active_tensions.tensions["speed_vs_reliability"]
        assert tension.intensity == 0.8
        assert tension.preferred_resolution == "reliability"
    
    def test_update_capability(self):
        """Should update capability beliefs."""
        state = SelfModelState()
        updater = SelfModelUpdater(state)
        
        updater.update_capability("clarify", capability_delta=0.1, reason="Test")
        
        cap = state.capability_model.capabilities["clarify"]
        assert cap["capability"] > 0.7  # Default 0.7 + 0.1
    
    def test_update_orientation_progress(self):
        """Should update long-horizon orientation progress."""
        state = SelfModelState()
        updater = SelfModelUpdater(state)
        
        updater.update_orientation_progress("roadmap_alignment", 0.1, "Test")
        
        for orientation in state.long_horizon_orientations.orientations:
            if orientation.id == "roadmap_alignment":
                assert orientation.progress == 0.4  # Default 0.3 + 0.1
                break
    
    def test_protected_update_logs_warning(self):
        """Protected updates should log warning even without approval."""
        state = SelfModelState()
        updater = SelfModelUpdater(state)
        
        # Update with no approver - should still work but log warning
        updater.update_identity_core(
            {"system_name": "NewName"},
            reason="Test",
            approver=None  # No approver - logged as warning
        )
        
        # Revision should be recorded
        assert len(state.revision_history.revisions) == 1
    
    def test_approved_identity_update(self):
        """Approved identity updates should work."""
        state = SelfModelState()
        updater = SelfModelUpdater(state)
        
        updater.update_identity_core(
            {"system_name": "OpenEmotion"},  # Same value, should work
            reason="Test",
            approver="test_user",
            evidence={"test": True}
        )
        
        # Check revision was recorded
        assert len(state.revision_history.revisions) == 1
        assert state.revision_history.revisions[0].approved is True
    
    def test_invariant_check(self):
        """Should check invariants."""
        state = SelfModelState()
        updater = SelfModelUpdater(state)
        
        violations = updater.check_invariants()
        assert len(violations) == 0
    
    def test_replay_chain(self):
        """Should support replay chain."""
        state = SelfModelState()
        updater = SelfModelUpdater(state)
        
        # Make some updates
        updater.update_behavioral_tendency("caution_bias", 0.6, "Update 1")
        updater.update_behavioral_tendency("exploration_bias", 0.5, "Update 2")
        
        revisions = state.revision_history.revisions
        assert len(revisions) >= 2
        
        # Get replay chain
        chain = updater.get_replay_chain(
            revisions[0].revision_id,
            revisions[-1].revision_id
        )
        assert len(chain) >= 2


class TestExitCriteria:
    """Tests for MVP13 Exit Criteria."""
    
    def test_persistence_across_sessions(self):
        """EC1: Persistence across sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Session 1: Create and save
            persistence = SelfModelPersistence(base_dir=tmpdir)
            state = SelfModelState()
            state.behavioral_tendencies.caution_bias = 0.7
            persistence.save(state)
            
            # Simulate session boundary
            persistence2 = SelfModelPersistence(base_dir=tmpdir)
            
            # Session 2: Load
            loaded = persistence2.load()
            assert loaded is not None
            assert loaded.behavioral_tendencies.caution_bias == 0.7
    
    def test_structural_integrity(self):
        """EC2: Structural integrity (schema form)."""
        state = SelfModelState()
        
        # All components should be structured objects, not strings
        assert isinstance(state.identity_core, IdentityCore)
        assert isinstance(state.stable_constraints, StableConstraints)
        assert isinstance(state.behavioral_tendencies, BehavioralTendencies)
        assert isinstance(state.active_tensions, ActiveTensions)
        assert isinstance(state.long_horizon_orientations, LongHorizonOrientations)
        assert isinstance(state.capability_model, CapabilityModel)
    
    def test_replayability(self):
        """EC3: Replayability of revisions."""
        state = SelfModelState()
        updater = SelfModelUpdater(state)
        
        # Make multiple updates
        updater.update_behavioral_tendency("caution_bias", 0.6, "Test 1")
        updater.update_behavioral_tendency("exploration_bias", 0.5, "Test 2")
        
        # All revisions should have required fields
        for rev in state.revision_history.revisions:
            assert rev.revision_id is not None
            assert rev.timestamp is not None
            assert rev.previous_version_hash is not None
            assert rev.changed_fields is not None
            assert rev.reason is not None
    
    def test_identity_continuity(self):
        """EC4: Identity continuity."""
        state = SelfModelState()
        
        # Verify identity hash stability
        hash1 = state.identity_hash
        
        # Make non-identity updates
        updater = SelfModelUpdater(state)
        updater.update_behavioral_tendency("caution_bias", 0.7, "Test")
        
        # Identity hash should remain stable
        assert state.identity_hash == hash1
        assert state.verify_identity_integrity()
    
    def test_drift_governance(self):
        """EC5: Drift governance - protected updates are audit-logged."""
        state = SelfModelState()
        updater = SelfModelUpdater(state)
        
        # Check invariants should catch violations
        violations = updater.check_invariants()
        assert len(violations) == 0
        
        # Protected updates are allowed and logged
        # Governance is through audit trail, not blocking
        updater.update_identity_core(
            {"role_definition": "Changed"},
            reason="Test",
            approver="test_system"
        )
        
        # Revision should be recorded with full audit trail
        assert len(state.revision_history.revisions) == 1
        rev = state.revision_history.revisions[0]
        assert rev.approved is True
        assert rev.approver == "test_system"
        assert "identity_core.role_definition" in rev.changed_fields
    
    def test_metrics_targets(self):
        """EC6/7: Metrics targets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SelfModelPersistence(base_dir=tmpdir)
            state = SelfModelState()
            
            # Save and load multiple times
            for _ in range(10):
                persistence.save(state)
                loaded = persistence.load()
                assert loaded is not None
            
            stats = persistence.get_statistics()
            
            # EC6: self_model_load_success >= 99%
            assert stats["success_rate"] >= 0.99
            
            # EC7: invariant_violation_count = 0
            violations = state.check_identity_invariants()
            assert len(violations) == 0
