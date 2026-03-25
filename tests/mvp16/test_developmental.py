"""
MVP16: Open Developmental Self Tests

Tests cover:
- Schema validation
- Persistence mechanism
- Anti-false-positive behavior
- Reset semantics
- Incremental observation
"""
import json
import pytest
import tempfile
from pathlib import Path

from emotiond.developmental import (
    DevelopmentalState,
    DevelopmentalEpisode,
    TransitionRecord,
    GrowthMetric,
    DevelopmentalManager,
    get_developmental_manager,
    reset_developmental_manager,
    DEFAULT_STATE_PATH,
)


class TestDevelopmentalSchema:
    """Tests for developmental schema."""
    
    def test_episode_defaults(self):
        episode = DevelopmentalEpisode(
            episode_id="test",
            episode_type="growth",
            phase="MVP16"
        )
        assert episode.description == ""
        assert episode.achievements == []
    
    def test_transition_record(self):
        transition = TransitionRecord(
            transition_id="test",
            from_phase="MVP15",
            to_phase="MVP16"
        )
        assert transition.approved == False
    
    def test_growth_metric(self):
        metric = GrowthMetric(metric_name="test", value=0.8)
        assert metric.value == 0.8
        assert metric.trend == "stable"
    
    def test_state_serialization(self):
        """Test that DevelopmentalState can be serialized and deserialized."""
        state = DevelopmentalState()
        episode = DevelopmentalEpisode(
            episode_id="test_ep",
            episode_type="milestone",
            phase="MVP16"
        )
        state.trajectory.episodes.append(episode)
        
        # Serialize
        json_str = state.model_dump_json()
        data = json.loads(json_str)
        
        # Deserialize
        restored = DevelopmentalState(**data)
        assert len(restored.trajectory.episodes) == 1
        assert restored.trajectory.episodes[0].episode_id == "test_ep"


class TestDevelopmentalManagerPersistence:
    """Tests for DevelopmentalManager persistence mechanism."""
    
    @pytest.fixture(autouse=True)
    def cleanup(self, tmp_path):
        """Clean up before each test."""
        reset_developmental_manager()
        yield
        reset_developmental_manager()
    
    def test_persistence_save_and_load(self, tmp_path):
        """Test that state is persisted and can be loaded."""
        state_path = tmp_path / "test_state.json"
        
        # Create manager and record data
        manager = DevelopmentalManager(state_path=state_path)
        manager.record_episode("test_episode", "MVP16", "Test description")
        manager.update_metric("test_metric", 0.75)
        
        # Verify persistence file exists
        assert state_path.exists()
        
        # Reset and reload
        reset_developmental_manager()
        manager2 = DevelopmentalManager(state_path=state_path)
        
        # Verify data was loaded
        assert len(manager2.state.trajectory.episodes) == 1
        assert manager2.state.trajectory.episodes[0].description == "Test description"
        assert manager2.state.metrics["test_metric"].value == 0.75
    
    def test_persistence_auto_save_on_episode(self, tmp_path):
        """Test that recording an episode triggers auto-save."""
        state_path = tmp_path / "auto_save.json"
        manager = DevelopmentalManager(state_path=state_path)
        
        # Record episode (should auto-save)
        manager.record_episode("milestone", "MVP16")
        
        # Verify file was created
        assert state_path.exists()
    
    def test_persistence_auto_save_on_transition(self, tmp_path):
        """Test that recording a transition triggers auto-save."""
        state_path = tmp_path / "auto_save_trans.json"
        manager = DevelopmentalManager(state_path=state_path)
        
        # Record transition (should auto-save)
        manager.record_transition("MVP15", "MVP16")
        
        # Verify file was created
        assert state_path.exists()
    
    def test_persistence_auto_save_on_metric_update(self, tmp_path):
        """Test that updating a metric triggers auto-save."""
        state_path = tmp_path / "auto_save_metric.json"
        manager = DevelopmentalManager(state_path=state_path)
        
        # Update metric (should auto-save)
        manager.update_metric("continuity_score", 0.9)
        
        # Verify file was created
        assert state_path.exists()
    
    def test_persistence_not_overwritten_by_new_instance(self, tmp_path):
        """Test that a persisted state isn't overwritten by a new manager instance."""
        state_path = tmp_path / "preserve.json"
        
        # Create manager, record data, verify saved
        manager1 = DevelopmentalManager(state_path=state_path)
        manager1.record_episode("ep1", "MVP16", "First episode")
        assert state_path.exists()
        
        # Create new manager - should load from persistence
        reset_developmental_manager()
        manager2 = DevelopmentalManager(state_path=state_path)
        
        # Verify data was loaded, not overwritten
        assert len(manager2.state.trajectory.episodes) == 1
        assert manager2.state.trajectory.episodes[0].description == "First episode"
    
    def test_reset_with_clear_persistence(self, tmp_path):
        """Test that reset with clear_persistence deletes the state file."""
        state_path = tmp_path / "to_delete.json"
        
        manager = DevelopmentalManager(state_path=state_path)
        manager.record_episode("ep1", "MVP16")
        assert state_path.exists()
        
        # Store the path for verification before reset clears instance
        stored_path = manager._state_path
        
        # Reset with clear - must pass the same state_path
        reset_developmental_manager(clear_persistence=True, state_path=stored_path)
        
        # Verify file was deleted
        assert not stored_path.exists()
    
    def test_reset_without_clear_persistence(self, tmp_path):
        """Test that reset without clear_persistence preserves the state file."""
        state_path = tmp_path / "to_keep.json"
        
        manager = DevelopmentalManager(state_path=state_path)
        manager.record_episode("ep1", "MVP16")
        assert state_path.exists()
        
        # Reset without clear
        reset_developmental_manager(clear_persistence=False, state_path=state_path)
        
        # Verify file still exists
        assert state_path.exists()


class TestAntiFalsePositive:
    """Tests for anti-false-positive behavior.
    
    CRITICAL: These tests verify that the system does NOT report
    success when reading from default values after a reset.
    """
    
    @pytest.fixture(autouse=True)
    def cleanup(self, tmp_path):
        """Clean up before each test."""
        reset_developmental_manager()
        yield
        reset_developmental_manager()
    
    def test_has_real_data_false_after_init(self, tmp_path):
        """Test that has_real_data returns False for newly initialized manager."""
        state_path = tmp_path / "empty.json"
        manager = DevelopmentalManager(state_path=state_path)
        
        # Fresh manager has no real data
        assert manager.has_real_data() == False
    
    def test_has_real_data_true_after_episode(self, tmp_path):
        """Test that has_real_data returns True after recording an episode."""
        state_path = tmp_path / "with_episode.json"
        manager = DevelopmentalManager(state_path=state_path)
        
        manager.record_episode("milestone", "MVP16")
        
        assert manager.has_real_data() == True
    
    def test_has_real_data_true_after_transition(self, tmp_path):
        """Test that has_real_data returns True after recording a transition."""
        state_path = tmp_path / "with_transition.json"
        manager = DevelopmentalManager(state_path=state_path)
        
        manager.record_transition("MVP15", "MVP16")
        
        assert manager.has_real_data() == True
    
    def test_has_real_data_true_after_metric_update(self, tmp_path):
        """Test that has_real_data returns True after updating a metric."""
        state_path = tmp_path / "with_metric.json"
        manager = DevelopmentalManager(state_path=state_path)
        
        # Update a metric (creates history)
        manager.update_metric("continuity_score", 0.85)
        
        assert manager.has_real_data() == True
    
    def test_summary_includes_has_real_data(self, tmp_path):
        """Test that get_summary includes has_real_data flag."""
        state_path = tmp_path / "summary_test.json"
        manager = DevelopmentalManager(state_path=state_path)
        
        summary = manager.get_summary()
        assert "has_real_data" in summary
        assert summary["has_real_data"] == False
        
        manager.record_episode("test", "MVP16")
        summary = manager.get_summary()
        assert summary["has_real_data"] == True
    
    def test_no_false_positive_from_default_metrics(self, tmp_path):
        """Test that default metrics don't create false positives.
        
        A manager with only default metrics (no episodes, no transitions,
        no metric history) should NOT be considered as having real data.
        """
        state_path = tmp_path / "defaults_only.json"
        manager = DevelopmentalManager(state_path=state_path)
        
        # Manager has default metrics but no real data
        assert len(manager.state.metrics) > 0  # Has default metrics
        assert manager.has_real_data() == False  # But not real data
        
        # Summary should reflect this
        summary = manager.get_summary()
        assert summary["has_real_data"] == False


class TestResetBehavior:
    """Tests for reset behavior semantics."""
    
    @pytest.fixture(autouse=True)
    def cleanup(self, tmp_path):
        """Clean up before each test."""
        reset_developmental_manager()
        yield
        reset_developmental_manager()
    
    def test_reset_clears_instance(self, tmp_path):
        """Test that reset clears the singleton instance."""
        state_path = tmp_path / "reset_test.json"
        
        manager = DevelopmentalManager(state_path=state_path)
        manager.record_episode("ep1", "MVP16")
        
        # Reset
        reset_developmental_manager()
        
        # New instance should be None initially
        assert DevelopmentalManager._instance is None
        
        # Getting instance should create new one
        manager2 = get_developmental_manager(state_path=state_path)
        assert manager2 is not None
    
    def test_reset_without_clear_keeps_persistence(self, tmp_path):
        """Test that reset without clear keeps the persisted data."""
        state_path = tmp_path / "keep_data.json"
        
        manager = DevelopmentalManager(state_path=state_path)
        manager.record_episode("ep1", "MVP16", "Saved episode")
        
        # Reset without clearing
        reset_developmental_manager(clear_persistence=False, state_path=state_path)
        
        # New instance should load persisted data
        manager2 = DevelopmentalManager(state_path=state_path)
        assert len(manager2.state.trajectory.episodes) == 1
        assert manager2.state.trajectory.episodes[0].description == "Saved episode"
    
    def test_reset_with_clear_removes_persistence(self, tmp_path):
        """Test that reset with clear removes the persisted data."""
        state_path = tmp_path / "remove_data.json"
        
        manager = DevelopmentalManager(state_path=state_path)
        manager.record_episode("ep1", "MVP16", "Will be deleted")
        
        # Store the path for verification before reset clears instance
        stored_path = manager._state_path
        
        # Reset with clearing - must pass the same state_path
        reset_developmental_manager(clear_persistence=True, state_path=stored_path)
        
        # File should be gone
        assert not stored_path.exists()
        
        # New instance should have fresh state
        manager2 = DevelopmentalManager(state_path=stored_path)
        assert len(manager2.state.trajectory.episodes) == 0


class TestIncrementalObservation:
    """Tests for incremental observation of developmental changes."""
    
    @pytest.fixture(autouse=True)
    def cleanup(self, tmp_path):
        """Clean up before each test."""
        reset_developmental_manager()
        yield
        reset_developmental_manager()
    
    def test_episode_increment(self, tmp_path):
        """Test that episodes are incrementally added."""
        state_path = tmp_path / "incremental.json"
        manager = DevelopmentalManager(state_path=state_path)
        
        # Record multiple episodes
        ep1 = manager.record_episode("milestone", "MVP16", "Episode 1")
        ep2 = manager.record_episode("milestone", "MVP16", "Episode 2")
        ep3 = manager.record_episode("milestone", "MVP16", "Episode 3")
        
        assert len(manager.state.trajectory.episodes) == 3
        
        # Reload and verify persistence
        reset_developmental_manager()
        manager2 = DevelopmentalManager(state_path=state_path)
        assert len(manager2.state.trajectory.episodes) == 3
    
    def test_transition_increment(self, tmp_path):
        """Test that transitions are incrementally recorded."""
        state_path = tmp_path / "trans_incremental.json"
        manager = DevelopmentalManager(state_path=state_path)
        
        # Record transitions
        t1 = manager.record_transition("MVP14", "MVP15")
        t2 = manager.record_transition("MVP15", "MVP16")
        
        assert len(manager.state.trajectory.transitions) == 2
        assert manager.state.trajectory.current_phase == "MVP16"
    
    def test_metric_history_tracking(self, tmp_path):
        """Test that metric history is tracked over time."""
        state_path = tmp_path / "metric_history.json"
        manager = DevelopmentalManager(state_path=state_path)
        
        # Update metric multiple times
        # Note: continuity_score starts with default 0.8, so first update adds that to history
        manager.update_metric("continuity_score", 0.7)  # history: [0.8], value: 0.7
        manager.update_metric("continuity_score", 0.8)  # history: [0.8, 0.7], value: 0.8
        manager.update_metric("continuity_score", 0.9)  # history: [0.8, 0.7, 0.8], value: 0.9
        
        metric = manager.state.metrics["continuity_score"]
        # History includes: default 0.8 + two updates
        assert len(metric.history) >= 2  # At least two previous values
        assert metric.value == 0.9
        # Trend improves from 0.8 to 0.9
        assert metric.trend == "improving"
    
    def test_trend_calculation(self, tmp_path):
        """Test that trend is calculated correctly."""
        state_path = tmp_path / "trend.json"
        manager = DevelopmentalManager(state_path=state_path)
        
        # First update creates new metric (no history for trend calc)
        manager.update_metric("test_metric", 0.5)
        # Second update: history now has 1 item, trend still "stable" (need 2+ for trend)
        manager.update_metric("test_metric", 0.7)
        # Check that value is correct
        assert manager.state.metrics["test_metric"].value == 0.7
        
        # Third update: now we have enough history for trend
        manager.update_metric("test_metric", 0.9)
        # Trend should be improving (0.9 > 0.7)
        assert manager.state.metrics["test_metric"].trend == "improving"
        
        # Declining trend
        manager.update_metric("test_metric", 0.4)
        assert manager.state.metrics["test_metric"].trend == "declining"
        
        # Stable trend
        manager.update_metric("test_metric", 0.4)
        assert manager.state.metrics["test_metric"].trend == "stable"


class TestExitCriteria:
    """Tests for MVP16 Exit Criteria."""
    
    @pytest.fixture(autouse=True)
    def cleanup(self, tmp_path):
        """Clean up before each test."""
        reset_developmental_manager()
        yield
        reset_developmental_manager()
    
    def test_long_horizon_continuity(self, tmp_path):
        state_path = tmp_path / "long_horizon.json"
        manager = DevelopmentalManager(state_path=state_path)
        
        # Record multiple episodes
        for i in range(5):
            manager.record_episode(f"episode_{i}", "MVP16")
        
        assert len(manager.state.trajectory.episodes) == 5
    
    def test_governed_growth(self, tmp_path):
        state_path = tmp_path / "governed.json"
        manager = DevelopmentalManager(state_path=state_path)
        
        transition = manager.record_transition("MVP15", "MVP16", approved=True, approver="governor")
        assert transition.approved == True
    
    def test_identity_preservation(self, tmp_path):
        state_path = tmp_path / "identity.json"
        manager = DevelopmentalManager(state_path=state_path)
        
        manager.record_episode("test", "MVP16")
        assert manager.check_identity_preservation() == True
    
    def test_continuity_score(self, tmp_path):
        state_path = tmp_path / "score.json"
        manager = DevelopmentalManager(state_path=state_path)
        
        manager.update_metric("continuity_score", 0.85)
        score = manager.get_continuity_score()
        assert 0.0 <= score <= 1.0


class TestSingletonBehavior:
    """Tests for singleton behavior of DevelopmentalManager."""
    
    @pytest.fixture(autouse=True)
    def cleanup(self, tmp_path):
        """Clean up before each test."""
        reset_developmental_manager()
        yield
        reset_developmental_manager()
    
    def test_singleton_returns_same_instance(self, tmp_path):
        state_path = tmp_path / "singleton.json"
        
        m1 = get_developmental_manager(state_path=state_path)
        m2 = get_developmental_manager(state_path=state_path)
        
        assert m1 is m2
    
    def test_singleton_with_different_paths(self, tmp_path):
        """Test that different paths create different instances after reset."""
        path1 = tmp_path / "path1.json"
        path2 = tmp_path / "path2.json"
        
        m1 = get_developmental_manager(state_path=path1)
        m1.record_episode("ep1", "MVP16")
        
        # Reset and get with different path
        reset_developmental_manager()
        m2 = get_developmental_manager(state_path=path2)
        
        # Should be different object
        assert m1 is not m2
        # m2 should not have m1's data
        assert len(m2.state.trajectory.episodes) == 0
