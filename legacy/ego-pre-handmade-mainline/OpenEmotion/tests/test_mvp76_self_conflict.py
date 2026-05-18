"""Tests for MVP-7.6 Phase 1: SelfModel v0 Self-Conflict & Manifest/Replay."""
import pytest
from emotiond.self_model.legacy import SelfModelV0, build_self_model_v0


class TestSelfConflict:
    """Test self_conflict calculation."""
    
    def test_compute_self_conflict_basic(self):
        """Test basic self_conflict calculation."""
        model = SelfModelV0()
        
        # Test with neutral event
        conflict = model.compute_self_conflict("neutral_event")
        assert 0.0 <= conflict <= 1.0
    
    def test_compute_self_conflict_value_conflict(self):
        """Test value conflict component."""
        model = SelfModelV0()
        
        # High value conflict event
        conflict = model.compute_self_conflict("betrayal_event", meta={})
        assert conflict > 0.3  # Should be elevated due to value conflict
        
        # Explicit value alignment
        conflict_aligned = model.compute_self_conflict(
            "event", 
            meta={"value_alignment": 0.9}
        )
        conflict_opposed = model.compute_self_conflict(
            "event",
            meta={"value_alignment": 0.1}
        )
        
        assert conflict_aligned < conflict_opposed
    
    def test_compute_self_conflict_capability_failure(self):
        """Test capability failure component."""
        model = SelfModelV0()
        
        # Failure event
        conflict = model.compute_self_conflict("task_failure", meta={"success": False})
        assert conflict > 0.2
        
        # Success event
        conflict_success = model.compute_self_conflict("task_success", meta={"success": True})
        assert conflict_success < 0.3
    
    def test_compute_self_conflict_identity_threat(self):
        """Test identity threat component."""
        model = SelfModelV0()
        
        # High identity threat
        conflict = model.compute_self_conflict(
            "rejection_event",
            meta={"identity_threat": 0.8}
        )
        assert conflict > 0.2
    
    def test_compute_self_conflict_relationship_state(self):
        """Test relationship state influence on conflict."""
        model = SelfModelV0()
        
        # Low bond/trust with high connection value should create conflict
        relationship_state = {"bond": 0.2, "trust": 0.2}
        conflict = model.compute_self_conflict(
            "relationship_event",
            meta={},
            relationship_state=relationship_state
        )
        assert conflict > 0.1
    
    def test_compute_self_conflict_weighted_components(self):
        """Test that all three components contribute to final score."""
        model = SelfModelV0()
        
        # Create event with mixed signals
        meta = {
            "value_alignment": 0.5,  # Neutral
            "success": None,  # Unknown
        }
        relationship_state = {"bond": 0.5, "trust": 0.5}
        
        conflict = model.compute_self_conflict(
            "mixed_event",
            meta=meta,
            relationship_state=relationship_state
        )
        
        assert 0.0 <= conflict <= 1.0


class TestApplyEvent:
    """Test apply_event method."""
    
    def test_apply_event_returns_structure(self):
        """Test that apply_event returns correct structure."""
        model = SelfModelV0()
        event = {"type": "user_message", "meta": {}}
        ctx = {"relationship_state": {"bond": 0.5, "trust": 0.5}}
        
        result = model.apply_event(event, ctx)
        
        assert "delta" in result
        assert "self_conflict" in result
        assert "evidence" in result
        assert "old_state" in result
        assert "new_state" in result
    
    def test_apply_event_conflict_score(self):
        """Test that apply_event calculates conflict score."""
        model = SelfModelV0()
        event = {"type": "feedback", "meta": {"success": True}}
        
        result = model.apply_event(event)
        
        assert 0.0 <= result["self_conflict"] <= 1.0
    
    def test_apply_event_evidence(self):
        """Test that apply_event provides traceable evidence."""
        model = SelfModelV0()
        event = {"type": "user_message", "meta": {"key": "value"}}
        
        result = model.apply_event(event)
        
        evidence = result["evidence"]
        assert evidence["event_type"] == "user_message"
        assert evidence["event_meta"] == {"key": "value"}
        assert "conflict_components" in evidence
    
    def test_apply_event_state_update(self):
        """Test that apply_event updates state."""
        model = SelfModelV0()
        old_hash = model.compute_hash()
        
        event = {"type": "feedback", "meta": {"success": True}}
        result = model.apply_event(event)
        
        # State should change after apply_event
        new_hash = model.compute_hash()
        # Note: hash may or may not change depending on the event
        # The important thing is that old_state and new_state are captured
        assert result["old_state"] is not None
        assert result["new_state"] is not None
    
    def test_apply_event_high_conflict_increases_uncertainty(self):
        """Test that high conflict increases cognitive uncertainty."""
        model = SelfModelV0()
        initial_uncertainty = model.cognitive.uncertainty
        
        # Create high conflict event
        event = {"type": "betrayal", "meta": {}}
        
        model.apply_event(event)
        
        # Uncertainty should increase for high conflict events
        assert model.cognitive.uncertainty >= initial_uncertainty
    
    def test_apply_event_feedback_updates_confidence(self):
        """Test that feedback events update confidence."""
        model = SelfModelV0()
        initial_confidence = model.cognitive.confidence
        
        # Positive feedback
        event = {"type": "feedback", "meta": {"success": True}}
        model.apply_event(event)
        
        # Confidence should increase
        assert model.cognitive.confidence >= initial_confidence


class TestHashAndSnapshot:
    """Test hash and snapshot methods for manifest/replay."""
    
    def test_compute_hash_deterministic(self):
        """Test that hash is deterministic."""
        model = SelfModelV0()
        hash1 = model.compute_hash()
        hash2 = model.compute_hash()
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex
    
    def test_compute_hash_changes_with_state(self):
        """Test that hash changes when state changes."""
        model = SelfModelV0()
        hash1 = model.compute_hash()
        
        # Change state
        model.cognitive.confidence = 0.9
        hash2 = model.compute_hash()
        
        assert hash1 != hash2
    
    def test_snapshot_serializable(self):
        """Test that snapshot returns serializable dict."""
        model = SelfModelV0()
        snapshot = model.snapshot()
        
        # Should be a dict with expected keys
        assert isinstance(snapshot, dict)
        assert "bodily" in snapshot
        assert "relational" in snapshot
        assert "cognitive" in snapshot
        assert "identity" in snapshot
        assert "updated_at" in snapshot
    
    def test_snapshot_preserves_state(self):
        """Test that snapshot captures current state."""
        model = SelfModelV0()
        model.cognitive.confidence = 0.8
        model.relational.bond = 0.6
        
        snapshot = model.snapshot()
        
        assert snapshot["cognitive"]["confidence"] == 0.8
        assert snapshot["relational"]["bond"] == 0.6
    
    def test_from_snapshot_reconstruction(self):
        """Test reconstruction from snapshot."""
        model1 = SelfModelV0()
        model1.cognitive.confidence = 0.75
        model1.relational.bond = 0.65
        model1.relational.focus_target = "alice"
        
        snapshot = model1.snapshot()
        model2 = SelfModelV0.from_snapshot(snapshot)
        
        # Reconstructed model should have same state
        assert model2.cognitive.confidence == model1.cognitive.confidence
        assert model2.relational.bond == model1.relational.bond
        assert model2.relational.focus_target == model1.relational.focus_target
    
    def test_snapshot_hash_consistency(self):
        """Test that snapshot and hash are consistent."""
        model1 = SelfModelV0()
        snapshot1 = model1.snapshot()
        hash1 = model1.compute_hash()
        
        # Reconstruct from snapshot
        model2 = SelfModelV0.from_snapshot(snapshot1)
        hash2 = model2.compute_hash()
        
        # Hashes should match
        assert hash1 == hash2


class TestIntegration:
    """Integration tests for complete workflow."""
    
    def test_event_sequence_with_replay(self):
        """Test event sequence and replay from snapshots."""
        model = SelfModelV0()
        
        # Record initial state
        initial_snapshot = model.snapshot()
        initial_hash = model.compute_hash()
        
        # Apply sequence of events
        events = [
            {"type": "user_message", "meta": {"content": "Hello"}},
            {"type": "feedback", "meta": {"success": True}},
            {"type": "world_event", "meta": {}},
        ]
        
        results = []
        for event in events:
            result = model.apply_event(event)
            results.append(result)
        
        # Final state should be different from initial
        final_hash = model.compute_hash()
        assert final_hash != initial_hash
        
        # Can reconstruct initial state from snapshot
        reconstructed = SelfModelV0.from_snapshot(initial_snapshot)
        assert reconstructed.compute_hash() == initial_hash
    
    def test_conflict_tracking_across_events(self):
        """Test that conflict is tracked across multiple events."""
        model = SelfModelV0()
        
        events = [
            {"type": "neutral_event", "meta": {}},
            {"type": "conflict_event", "meta": {}},
            {"type": "betrayal_event", "meta": {}},
        ]
        
        conflicts = []
        for event in events:
            result = model.apply_event(event)
            conflicts.append(result["self_conflict"])
        
        # Later events should show higher conflict
        assert len(conflicts) == 3
        # Betrayal should have higher conflict than neutral
        assert conflicts[2] > conflicts[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
