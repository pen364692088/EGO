"""Tests for US-702 Episodic Memory v0."""

import pytest
from core.episodic_memory import Episode, EpisodeStore


class TestEpisode:
    def test_episode_creation(self):
        ep = Episode(
            event="User expressed frustration",
            appraisal={"anger": 0.7},
            action="acknowledged and offered help",
        )
        assert ep.event == "User expressed frustration"
        assert ep.importance == 0.5
    
    def test_episode_serialization(self):
        ep = Episode(
            event="Test event",
            appraisal={"joy": 0.5},
            provenance={"source": "system", "signature": "abc"},
        )
        data = ep.to_dict()
        restored = Episode.from_dict(data)
        
        assert restored.event == "Test event"
        assert restored.appraisal == {"joy": 0.5}
    
    def test_episode_hash(self):
        ep = Episode(event="Test")
        hash1 = ep.compute_hash()
        hash2 = ep.compute_hash()
        assert hash1 == hash2
        assert len(hash1) == 64


class TestEpisodeStore:
    def test_append_success(self):
        store = EpisodeStore()
        ep = Episode(
            event="Test event",
            provenance={"source": "user"},
        )
        success, reason = store.append(ep)
        assert success is True
        assert reason == "ok"
        assert len(store) == 1
    
    def test_append_rejects_missing_provenance(self):
        store = EpisodeStore(enable_provenance_check=True)
        ep = Episode(event="Test event")
        success, reason = store.append(ep)
        assert success is False
        assert reason == "missing_provenance"
    
    def test_append_rejects_internal_without_signature(self):
        store = EpisodeStore(enable_provenance_check=True)
        ep = Episode(
            event="Test event",
            provenance={"source": "system"},  # No signature
        )
        success, reason = store.append(ep)
        assert success is False
        assert reason == "missing_signature_for_internal_source"
    
    def test_append_accepts_internal_with_signature(self):
        store = EpisodeStore(enable_provenance_check=True)
        ep = Episode(
            event="Test event",
            provenance={"source": "system", "signature": "valid_sig"},
        )
        success, reason = store.append(ep)
        assert success is True
    
    def test_append_rejects_duplicate(self):
        store = EpisodeStore()
        ep = Episode(
            event="Test event",
            provenance={"source": "user"},
        )
        store.append(ep)
        success, reason = store.append(ep)
        assert success is False
        assert reason == "duplicate_episode"
    
    def test_query_by_event(self):
        store = EpisodeStore()
        for i in range(5):
            store.append(Episode(
                event=f"Event {i}",
                provenance={"source": "user"},
            ))
        
        results = store.query(event_contains="Event")
        assert len(results) == 5
    
    def test_query_by_importance(self):
        store = EpisodeStore()
        store.append(Episode(event="Low", importance=0.1, provenance={"source": "user"}))
        store.append(Episode(event="High", importance=0.9, provenance={"source": "user"}))
        
        results = store.query(min_importance=0.5)
        assert len(results) == 1
        assert results[0].event == "High"
    
    def test_top_k_by_importance(self):
        store = EpisodeStore()
        for i in range(10):
            store.append(Episode(
                event=f"Event {i}",
                importance=i / 10,
                provenance={"source": "user"},
            ))
        
        top = store.top_k(k=3, by="importance")
        assert len(top) == 3
        assert top[0].importance >= top[1].importance
    
    def test_top_k_by_recency(self):
        store = EpisodeStore()
        import time
        for i in range(5):
            store.append(Episode(
                event=f"Event {i}",
                provenance={"source": "user"},
            ))
        
        top = store.top_k(k=3, by="recency")
        assert len(top) == 3
        # Most recent first
        assert "Event 4" in top[0].event
    
    def test_get_relevant_summary(self):
        store = EpisodeStore()
        store.append(Episode(event="User asked about X", provenance={"source": "user"}))
        store.append(Episode(event="User asked about Y", provenance={"source": "user"}))
        
        summary = store.get_relevant_summary("asked")
        assert len(summary["episodes"]) == 2
        assert "Found 2 relevant episodes" in summary["summary"]
    
    def test_size_cap(self):
        store = EpisodeStore(max_episodes=5)
        for i in range(10):
            store.append(Episode(
                event=f"Event {i}",
                provenance={"source": "user"},
            ))
        assert len(store) == 5
    
    def test_user_source_allowed_without_signature(self):
        store = EpisodeStore(enable_provenance_check=True)
        ep = Episode(
            event="User event",
            provenance={"source": "user"},  # No signature needed for user
        )
        success, reason = store.append(ep)
        assert success is True


class TestContinuity:
    """Tests for memory continuity and confabulation prevention."""
    
    def test_no_confabulation(self):
        """Episodes should not be fabricated without proper provenance."""
        store = EpisodeStore(enable_provenance_check=True)
        
        # Attempt to inject fake memory
        fake_ep = Episode(
            event="This never happened",
            provenance={"source": "system"},  # Missing signature
        )
        success, reason = store.append(fake_ep)
        
        # Should be rejected
        assert success is False
        assert len(store) == 0
    
    def test_retrieval_does_not_fabricate(self):
        """Retrieval should only return actual episodes."""
        store = EpisodeStore()
        store.append(Episode(event="Real event", provenance={"source": "user"}))
        
        results = store.query(event_contains="nonexistent")
        assert len(results) == 0
    
    def test_summary_only_points_to_real_episodes(self):
        """Summary should only reference actual stored episodes."""
        store = EpisodeStore()
        store.append(Episode(event="Real event", provenance={"source": "user"}))
        
        summary = store.get_relevant_summary("Real")
        for ep in summary["episodes"]:
            # Verify hash matches a real episode
            assert any(e.compute_hash().startswith(ep["hash"]) for e in store)
