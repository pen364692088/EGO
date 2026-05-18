"""
MVP13 T02: Self-Model Integration Tests

Tests for:
- SelfModelManager singleton
- Integration with emotiond core
- Backward compatibility
"""
import pytest
import tempfile

from emotiond.self_model import (
    SelfModelManager,
    get_self_model_manager,
    reset_self_model_manager,
    TensionType,
)


class TestSelfModelManager:
    """Tests for SelfModelManager."""
    
    def test_singleton(self):
        """Should return same instance."""
        reset_self_model_manager()
        
        manager1 = get_self_model_manager()
        manager2 = get_self_model_manager()
        
        assert manager1 is manager2
    
    def test_state_access(self):
        """Should provide access to state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from emotiond.self_model import SelfModelPersistence
            persistence = SelfModelPersistence(base_dir=tmpdir)
            manager = SelfModelManager(persistence=persistence)
            
            state = manager.state
            assert state is not None
            assert state.identity_core.system_name == "OpenEmotion"
    
    def test_save_and_reload(self):
        """Should persist state across sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from emotiond.self_model import SelfModelPersistence
            persistence = SelfModelPersistence(base_dir=tmpdir)
            
            # Session 1 - start from default (0.6), gradual update adds max 0.1
            manager1 = SelfModelManager(persistence=persistence)
            manager1.update_behavior("caution_bias", 0.7, "Test update")
            
            # Session 2 (simulating restart)
            persistence2 = SelfModelPersistence(base_dir=tmpdir)
            manager2 = SelfModelManager(persistence=persistence2)
            
            # State should persist (0.7 due to gradual update constraint)
            assert manager2.state.behavioral_tendencies.caution_bias == 0.7
    
    def test_identity_summary(self):
        """Should provide identity summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from emotiond.self_model import SelfModelPersistence
            persistence = SelfModelPersistence(base_dir=tmpdir)
            manager = SelfModelManager(persistence=persistence)
            
            summary = manager.get_identity_summary()
            assert summary["system_name"] == "OpenEmotion"
            assert summary["integrity_valid"] is True
    
    def test_behavioral_profile(self):
        """Should provide behavioral profile."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from emotiond.self_model import SelfModelPersistence
            persistence = SelfModelPersistence(base_dir=tmpdir)
            manager = SelfModelManager(persistence=persistence)
            
            profile = manager.get_behavioral_profile()
            assert "risk_stance" in profile
            assert "approach_stance" in profile
    
    def test_capability_access(self):
        """Should provide capability values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from emotiond.self_model import SelfModelPersistence
            persistence = SelfModelPersistence(base_dir=tmpdir)
            manager = SelfModelManager(persistence=persistence)
            
            capability = manager.get_capability("clarify")
            assert 0.0 <= capability <= 1.0
    
    def test_tension_bias(self):
        """Should provide tension resolution bias."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from emotiond.self_model import SelfModelPersistence
            persistence = SelfModelPersistence(base_dir=tmpdir)
            manager = SelfModelManager(persistence=persistence)
            
            bias = manager.get_tension_bias(TensionType.SPEED_VS_RELIABILITY)
            assert bias in ["speed", "reliability", "balanced"]
    
    def test_update_behavior(self):
        """Should update behavior with audit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from emotiond.self_model import SelfModelPersistence
            persistence = SelfModelPersistence(base_dir=tmpdir)
            manager = SelfModelManager(persistence=persistence)
            
            result = manager.update_behavior(
                "caution_bias", 0.7, "Test update", {"test": True}
            )
            
            assert result is True
            assert manager.state.behavioral_tendencies.caution_bias == 0.7
            assert len(manager.state.revision_history.revisions) == 1
    
    def test_update_capability(self):
        """Should update capability."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from emotiond.self_model import SelfModelPersistence
            persistence = SelfModelPersistence(base_dir=tmpdir)
            manager = SelfModelManager(persistence=persistence)
            
            result = manager.update_capability(
                "clarify", capability_delta=0.1, reason="Test"
            )
            
            assert result is True
    
    def test_update_tension(self):
        """Should update tension."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from emotiond.self_model import SelfModelPersistence
            persistence = SelfModelPersistence(base_dir=tmpdir)
            manager = SelfModelManager(persistence=persistence)
            
            result = manager.update_tension(
                TensionType.AUTONOMY_VS_GOVERNANCE,
                intensity=0.8,
                preferred_resolution="governance",
                reason="Test"
            )
            
            assert result is True
    
    def test_record_orientation_progress(self):
        """Should record orientation progress."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from emotiond.self_model import SelfModelPersistence
            persistence = SelfModelPersistence(base_dir=tmpdir)
            manager = SelfModelManager(persistence=persistence)
            
            result = manager.record_orientation_progress(
                "roadmap_alignment", 0.1, "Test"
            )
            
            assert result is True
    
    def test_health_check(self):
        """Should check self-model health."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from emotiond.self_model import SelfModelPersistence
            persistence = SelfModelPersistence(base_dir=tmpdir)
            manager = SelfModelManager(persistence=persistence)
            
            health = manager.check_health()
            
            assert health["healthy"] is True
            assert health["identity_integrity"] is True
            assert health["invariant_violations"] == []
    
    def test_get_summary(self):
        """Should get summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from emotiond.self_model import SelfModelPersistence
            persistence = SelfModelPersistence(base_dir=tmpdir)
            manager = SelfModelManager(persistence=persistence)
            
            summary = manager.get_summary()
            
            assert "identity" in summary
            assert "identity_integrity" in summary
            assert summary["identity_integrity"] is True
