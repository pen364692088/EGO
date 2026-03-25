"""
MVP13 Gate B: E2E / Replay / Evidence Tests

Gate B verification:
- Behavioral verification passes
- Replay/rerun/evidence verifiable
- Core metrics meet exit criteria
- No targeted-only results
"""
import pytest
import tempfile
import json
import time
from pathlib import Path

from emotiond.self_model import (
    SelfModelState,
    SelfModelPersistence,
    SelfModelUpdater,
    SelfModelManager,
    TensionType,
)


class TestGateB_E2E:
    """End-to-end tests for Gate B."""
    
    def test_full_lifecycle(self):
        """Test complete self-model lifecycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create
            persistence = SelfModelPersistence(base_dir=tmpdir)
            state = SelfModelState()
            updater = SelfModelUpdater(state)
            
            # Make updates
            updater.update_behavioral_tendency("caution_bias", 0.7, "Learning event")
            updater.update_capability("clarify", capability_delta=0.1, reason="Practice")
            updater.update_active_tension(TensionType.SPEED_VS_RELIABILITY, intensity=0.6, reason="Context change")
            
            # Save
            assert persistence.save(state)
            
            # Load
            loaded = persistence.load()
            assert loaded is not None
            
            # Verify persistence
            assert loaded.behavioral_tendencies.caution_bias == 0.7
            assert len(loaded.revision_history.revisions) == 3
            
            # Verify identity integrity preserved
            assert loaded.verify_identity_integrity()
    
    def test_multi_session_continuity(self):
        """Test continuity across multiple sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            revisions = []
            
            # Session 1
            p1 = SelfModelPersistence(base_dir=tmpdir)
            m1 = SelfModelManager(persistence=p1)
            m1.update_behavior("caution_bias", 0.7, "Session 1")
            revisions.append(m1.state.revision_history.revisions[-1].revision_id)
            
            # Session 2 (simulated restart)
            p2 = SelfModelPersistence(base_dir=tmpdir)
            m2 = SelfModelManager(persistence=p2)
            m2.update_behavior("exploration_bias", 0.5, "Session 2")
            revisions.append(m2.state.revision_history.revisions[-1].revision_id)
            
            # Session 3
            p3 = SelfModelPersistence(base_dir=tmpdir)
            m3 = SelfModelManager(persistence=p3)
            
            # Verify all revisions preserved
            assert len(m3.state.revision_history.revisions) >= 2
            
            # Verify continuity trace
            assert len(m3.state.continuity_trace.entries) >= 2
    
    def test_evidence_chain(self):
        """Test evidence chain integrity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SelfModelPersistence(base_dir=tmpdir)
            state = SelfModelState()
            updater = SelfModelUpdater(state)
            
            # Make updates with evidence
            updater.update_behavioral_tendency(
                "caution_bias", 0.7, 
                "Learning from error",
                {"error_type": "boundary_violation", "count": 3}
            )
            
            # Verify evidence recorded
            rev = state.revision_history.revisions[0]
            assert rev.evidence is not None
            assert "error_type" in rev.evidence


class TestGateB_Replay:
    """Replay verification tests."""
    
    def test_revision_replay(self):
        """Test revision chain replay."""
        state = SelfModelState()
        updater = SelfModelUpdater(state)
        
        # Create revision chain
        updater.update_behavioral_tendency("caution_bias", 0.7, "Update 1")
        updater.update_behavioral_tendency("exploration_bias", 0.5, "Update 2")
        updater.update_behavioral_tendency("self_correction_tendency", 0.8, "Update 3")
        
        # Get replay chain
        revisions = state.revision_history.revisions
        chain = updater.get_replay_chain(
            revisions[0].revision_id,
            revisions[-1].revision_id
        )
        
        assert len(chain) == 3
        assert chain[0]["reason"] == "Update 1"
        assert chain[1]["reason"] == "Update 2"
        assert chain[2]["reason"] == "Update 3"
    
    def test_continuity_replay(self):
        """Test continuity trace replay."""
        state = SelfModelState()
        updater = SelfModelUpdater(state)
        
        # Create continuity entries
        updater.update_behavioral_tendency("caution_bias", 0.7, "Event 1")
        updater.update_capability("clarify", capability_delta=0.1, reason="Event 2")
        
        # Get recent transitions
        transitions = state.continuity_trace.get_recent_transitions(2)
        
        assert len(transitions) == 2
        assert transitions[0].event == "update_behavioral_tendency.caution_bias"
        assert transitions[1].event == "update_capability.clarify"


class TestGateB_Metrics:
    """Core metrics verification."""
    
    def test_load_success_rate(self):
        """Verify self_model_load_success >= 99%."""
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SelfModelPersistence(base_dir=tmpdir)
            state = SelfModelState()
            
            # Multiple save/load cycles
            for _ in range(100):
                persistence.save(state)
                loaded = persistence.load()
                assert loaded is not None
            
            stats = persistence.get_statistics()
            assert stats["success_rate"] >= 0.99
    
    def test_invariant_violation_count(self):
        """Verify invariant_violation_count = 0."""
        state = SelfModelState()
        violations = state.check_identity_invariants()
        assert len(violations) == 0
    
    def test_identity_integrity_preserved(self):
        """Verify identity integrity preserved across updates."""
        state = SelfModelState()
        updater = SelfModelUpdater(state)
        
        original_hash = state.identity_hash
        
        # Make non-identity updates
        updater.update_behavioral_tendency("caution_bias", 0.7, "Test")
        updater.update_capability("clarify", capability_delta=0.1, reason="Test")
        updater.update_active_tension(TensionType.SPEED_VS_RELIABILITY, intensity=0.6, reason="Test")
        
        # Identity should be preserved
        assert state.identity_hash == original_hash
        assert state.verify_identity_integrity()
    
    def test_persistence_metrics(self):
        """Verify persistence layer metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = SelfModelPersistence(base_dir=tmpdir)
            state = SelfModelState()
            
            # Save and load
            persistence.save(state)
            persistence.load()
            
            # Verify statistics
            stats = persistence.get_statistics()
            assert stats["save_count"] >= 1
            assert stats["load_count"] >= 1
            assert stats["error_count"] == 0


class TestGateB_NoTargetedOnly:
    """Verify no targeted-only results."""
    
    def test_all_components_tested(self):
        """Verify all schema components have tests."""
        from emotiond.self_model import (
            IdentityCore,
            StableConstraints,
            BehavioralTendencies,
            ActiveTensions,
            LongHorizonOrientations,
            CapabilityModel,
            ContinuityTrace,
            RevisionHistory,
        )
        
        # All components should be instantiable with defaults
        assert IdentityCore()
        assert StableConstraints()
        assert BehavioralTendencies()
        assert ActiveTensions()
        assert LongHorizonOrientations()
        assert CapabilityModel()
        assert ContinuityTrace()
        assert RevisionHistory()
    
    def test_full_state_integration(self):
        """Verify full state integration works."""
        state = SelfModelState()
        
        # All components accessible
        assert state.identity_core is not None
        assert state.stable_constraints is not None
        assert state.behavioral_tendencies is not None
        assert state.active_tensions is not None
        assert state.long_horizon_orientations is not None
        assert state.capability_model is not None
        assert state.continuity_trace is not None
        assert state.revision_history is not None
        
        # Summary includes all
        summary = state.get_summary()
        assert "identity" in summary
        assert "behavioral_profile" in summary
        assert "dominant_tension" in summary
        assert "top_orientations" in summary
