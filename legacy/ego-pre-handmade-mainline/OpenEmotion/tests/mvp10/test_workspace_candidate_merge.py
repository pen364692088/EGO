"""
MVP-10 T04: Test Workspace Candidate API

Tests:
1. Candidate dataclass with source, type, utility, risk, cost, evidence, rationale, payload
2. CandidatePool class with add, remove, sort, dedupe, merge
3. Comparison and sorting support
"""
import pytest
import sys
sys.path.insert(0, '/home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion')

from emotiond.workspace import (
    Candidate,
    CandidateType,
    CandidatePool,
    create_candidate,
)


class TestCandidateDataclass:
    """Tests for Candidate dataclass."""
    
    def test_candidate_creation(self):
        """Test creating a candidate with all fields."""
        candidate = Candidate(
            id="test_1",
            source="drives",
            type=CandidateType.GOAL,
            utility=0.8,
            risk=0.2,
            cost=0.1,
            evidence=[{"type": "prediction", "value": 0.9}],
            rationale="High utility goal from drives module",
            payload={"goal_id": "goal_123"},
        )
        
        assert candidate.id == "test_1"
        assert candidate.source == "drives"
        assert candidate.type == CandidateType.GOAL
        assert candidate.utility == 0.8
        assert candidate.risk == 0.2
        assert candidate.cost == 0.1
        assert len(candidate.evidence) == 1
        assert candidate.rationale == "High utility goal from drives module"
        assert candidate.payload["goal_id"] == "goal_123"
    
    def test_candidate_type_enum(self):
        """Test CandidateType enum values."""
        assert CandidateType.INTENT.value == "intent"
        assert CandidateType.GOAL.value == "goal"
        assert CandidateType.ACTION.value == "action"
        assert CandidateType.REFLECTION.value == "reflection"
        assert CandidateType.INFO_SEEK.value == "info_seek"
        assert CandidateType.RECOVERY.value == "recovery"
    
    def test_candidate_auto_id(self):
        """Test that ID is auto-generated if not provided."""
        candidate = Candidate(
            id="",
            source="test",
            type=CandidateType.INTENT,
        )
        
        # Should have generated an ID
        assert candidate.id != ""
        assert len(candidate.id) == 8  # MD5 hash truncated to 8 chars
    
    def test_candidate_value_clamping(self):
        """Test that utility, risk, cost are clamped to [0, 1]."""
        candidate = Candidate(
            id="test",
            source="test",
            type=CandidateType.INTENT,
            utility=1.5,  # Above max
            risk=-0.5,   # Below min
            cost=2.0,    # Above max
        )
        
        assert candidate.utility == 1.0
        assert candidate.risk == 0.0
        assert candidate.cost == 1.0
    
    def test_compute_score(self):
        """Test score computation."""
        # High utility, low risk/cost
        c1 = Candidate(id="c1", source="test", type=CandidateType.INTENT, utility=0.9, risk=0.1, cost=0.1)
        # Expected: 0.9 - (0.1 * 0.5) - (0.1 * 0.3) = 0.9 - 0.05 - 0.03 = 0.82
        
        # Low utility, high risk/cost
        c2 = Candidate(id="c2", source="test", type=CandidateType.INTENT, utility=0.3, risk=0.8, cost=0.5)
        # Expected: 0.3 - (0.8 * 0.5) - (0.5 * 0.3) = 0.3 - 0.4 - 0.15 = -0.25
        
        assert c1.compute_score() > c2.compute_score()
        assert abs(c1.compute_score() - 0.82) < 0.01
    
    def test_candidate_comparison(self):
        """Test comparison operators based on score."""
        c1 = Candidate(id="c1", source="test", type=CandidateType.INTENT, utility=0.9)
        c2 = Candidate(id="c2", source="test", type=CandidateType.INTENT, utility=0.5)
        
        assert c1 > c2
        assert c1 >= c2
        assert c2 < c1
        assert c2 <= c1
        assert c1 != c2
    
    def test_candidate_equality(self):
        """Test equality based on ID."""
        c1 = Candidate(id="same", source="test", type=CandidateType.INTENT, utility=0.9)
        c2 = Candidate(id="same", source="other", type=CandidateType.GOAL, utility=0.5)
        c3 = Candidate(id="different", source="test", type=CandidateType.INTENT, utility=0.9)
        
        assert c1 == c2  # Same ID
        assert c1 != c3  # Different ID
    
    def test_candidate_hash(self):
        """Test hashing based on ID."""
        c1 = Candidate(id="same", source="test", type=CandidateType.INTENT)
        c2 = Candidate(id="same", source="other", type=CandidateType.GOAL)
        
        # Same ID should have same hash
        assert hash(c1) == hash(c2)
        
        # Can be used in set
        s = {c1, c2}
        assert len(s) == 1  # Only one because same ID
    
    def test_candidate_to_dict(self):
        """Test serialization to dict."""
        candidate = Candidate(
            id="test",
            source="drives",
            type=CandidateType.GOAL,
            utility=0.8,
            risk=0.2,
            cost=0.1,
        )
        
        data = candidate.to_dict()
        
        assert data["id"] == "test"
        assert data["source"] == "drives"
        assert data["type"] == "goal"
        assert data["utility"] == 0.8
        assert data["risk"] == 0.2
        assert data["cost"] == 0.1
        assert "score" in data
    
    def test_candidate_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "id": "test",
            "source": "drives",
            "type": "goal",
            "utility": 0.8,
            "risk": 0.2,
            "cost": 0.1,
            "evidence": [{"type": "test"}],
            "rationale": "test rationale",
            "payload": {"key": "value"},
        }
        
        candidate = Candidate.from_dict(data)
        
        assert candidate.id == "test"
        assert candidate.source == "drives"
        assert candidate.type == CandidateType.GOAL
        assert candidate.utility == 0.8


class TestCandidatePool:
    """Tests for CandidatePool class."""
    
    def test_pool_creation(self):
        """Test creating an empty pool."""
        pool = CandidatePool()
        
        assert len(pool) == 0
        assert pool.max_size == 100
    
    def test_add_candidate(self):
        """Test adding candidates."""
        pool = CandidatePool()
        c1 = Candidate(id="c1", source="test", type=CandidateType.INTENT)
        c2 = Candidate(id="c2", source="test", type=CandidateType.GOAL)
        
        assert pool.add(c1) is True
        assert pool.add(c2) is True
        assert len(pool) == 2
    
    def test_add_duplicate(self):
        """Test adding duplicate candidate (same ID)."""
        pool = CandidatePool()
        c1 = Candidate(id="same", source="test", type=CandidateType.INTENT)
        c2 = Candidate(id="same", source="other", type=CandidateType.GOAL)
        
        assert pool.add(c1) is True
        assert pool.add(c2) is False  # Duplicate ID
        assert len(pool) == 1
    
    def test_remove_candidate(self):
        """Test removing candidates by ID."""
        pool = CandidatePool()
        c = Candidate(id="test", source="test", type=CandidateType.INTENT)
        pool.add(c)
        
        removed = pool.remove("test")
        
        assert removed is not None
        assert removed.id == "test"
        assert len(pool) == 0
    
    def test_remove_nonexistent(self):
        """Test removing nonexistent candidate."""
        pool = CandidatePool()
        
        removed = pool.remove("nonexistent")
        
        assert removed is None
    
    def test_remove_by_source(self):
        """Test removing all candidates from a source."""
        pool = CandidatePool()
        pool.add(Candidate(id="c1", source="drives", type=CandidateType.INTENT))
        pool.add(Candidate(id="c2", source="drives", type=CandidateType.GOAL))
        pool.add(Candidate(id="c3", source="planner", type=CandidateType.ACTION))
        
        removed = pool.remove_by_source("drives")
        
        assert len(removed) == 2
        assert len(pool) == 1
        assert pool.candidates[0].source == "planner"
    
    def test_sort(self):
        """Test sorting by score."""
        pool = CandidatePool()
        pool.add(Candidate(id="low", source="test", type=CandidateType.INTENT, utility=0.3))
        pool.add(Candidate(id="high", source="test", type=CandidateType.INTENT, utility=0.9))
        pool.add(Candidate(id="mid", source="test", type=CandidateType.INTENT, utility=0.6))
        
        pool.sort(reverse=True)
        
        assert pool[0].id == "high"
        assert pool[1].id == "mid"
        assert pool[2].id == "low"
    
    def test_dedupe(self):
        """Test removing duplicates."""
        pool = CandidatePool()
        pool.add(Candidate(id="same", source="test", type=CandidateType.INTENT))
        pool.add(Candidate(id="same", source="other", type=CandidateType.GOAL))  # Should fail
        
        # Manually add duplicate to test dedupe
        pool.candidates.append(Candidate(id="same", source="manual", type=CandidateType.ACTION))
        
        removed_count = pool.dedupe()
        
        assert removed_count == 1
        assert len(pool) == 1
    
    def test_merge(self):
        """Test merging two pools."""
        pool1 = CandidatePool()
        pool1.add(Candidate(id="c1", source="test", type=CandidateType.INTENT))
        
        pool2 = CandidatePool()
        pool2.add(Candidate(id="c2", source="test", type=CandidateType.GOAL))
        pool2.add(Candidate(id="c3", source="test", type=CandidateType.ACTION))
        
        added = pool1.merge(pool2)
        
        assert added == 2
        assert len(pool1) == 3
    
    def test_merge_with_duplicates(self):
        """Test merging pools with overlapping candidates."""
        pool1 = CandidatePool()
        pool1.add(Candidate(id="same", source="test", type=CandidateType.INTENT))
        
        pool2 = CandidatePool()
        pool2.add(Candidate(id="same", source="other", type=CandidateType.GOAL))  # Duplicate ID
        pool2.add(Candidate(id="unique", source="test", type=CandidateType.ACTION))
        
        added = pool1.merge(pool2)
        
        assert added == 1  # Only unique added
        assert len(pool1) == 2
    
    def test_get_best(self):
        """Test getting the best candidate."""
        pool = CandidatePool()
        pool.add(Candidate(id="low", source="test", type=CandidateType.INTENT, utility=0.3))
        pool.add(Candidate(id="high", source="test", type=CandidateType.INTENT, utility=0.9))
        
        best = pool.get_best()
        
        assert best is not None
        assert best.id == "high"
    
    def test_get_by_type(self):
        """Test filtering by type."""
        pool = CandidatePool()
        pool.add(Candidate(id="c1", source="test", type=CandidateType.INTENT))
        pool.add(Candidate(id="c2", source="test", type=CandidateType.GOAL))
        pool.add(Candidate(id="c3", source="test", type=CandidateType.INTENT))
        
        intents = pool.get_by_type(CandidateType.INTENT)
        
        assert len(intents) == 2
    
    def test_get_by_source(self):
        """Test filtering by source."""
        pool = CandidatePool()
        pool.add(Candidate(id="c1", source="drives", type=CandidateType.INTENT))
        pool.add(Candidate(id="c2", source="planner", type=CandidateType.GOAL))
        pool.add(Candidate(id="c3", source="drives", type=CandidateType.ACTION))
        
        from_drives = pool.get_by_source("drives")
        
        assert len(from_drives) == 2
    
    def test_filter_by_score(self):
        """Test filtering by minimum score."""
        pool = CandidatePool()
        pool.add(Candidate(id="low", source="test", type=CandidateType.INTENT, utility=0.3))
        pool.add(Candidate(id="mid", source="test", type=CandidateType.INTENT, utility=0.5))
        pool.add(Candidate(id="high", source="test", type=CandidateType.INTENT, utility=0.9))
        
        above_0_4 = pool.filter_by_score(min_score=0.4)
        
        assert len(above_0_4) == 2
    
    def test_max_size_eviction(self):
        """Test that lowest-scored candidate is evicted when pool is full."""
        pool = CandidatePool(max_size=3)
        pool.add(Candidate(id="c1", source="test", type=CandidateType.INTENT, utility=0.5))
        pool.add(Candidate(id="c2", source="test", type=CandidateType.INTENT, utility=0.7))
        pool.add(Candidate(id="c3", source="test", type=CandidateType.INTENT, utility=0.3))
        
        # Add one more, should evict lowest (c3)
        pool.add(Candidate(id="c4", source="test", type=CandidateType.INTENT, utility=0.9))
        
        assert len(pool) == 3
        assert pool.get_by_id("c3") is None  # Evicted
    
    def test_iteration(self):
        """Test iterating over pool."""
        pool = CandidatePool()
        pool.add(Candidate(id="c1", source="test", type=CandidateType.INTENT))
        pool.add(Candidate(id="c2", source="test", type=CandidateType.GOAL))
        
        ids = [c.id for c in pool]
        
        assert "c1" in ids
        assert "c2" in ids
    
    def test_to_dict_and_from_dict(self):
        """Test serialization and deserialization."""
        pool = CandidatePool()
        pool.add(Candidate(id="c1", source="test", type=CandidateType.INTENT, utility=0.8))
        
        data = pool.to_dict()
        restored = CandidatePool.from_dict(data)
        
        assert len(restored) == 1
        assert restored[0].id == "c1"


class TestFactoryFunction:
    """Tests for create_candidate factory function."""
    
    def test_create_candidate(self):
        """Test creating candidate via factory."""
        candidate = create_candidate(
            source="drives",
            candidate_type="goal",
            utility=0.8,
            risk=0.2,
            cost=0.1,
            rationale="Test rationale",
            payload={"key": "value"},
        )
        
        assert candidate.source == "drives"
        assert candidate.type == CandidateType.GOAL
        assert candidate.utility == 0.8
        assert candidate.risk == 0.2
        assert candidate.cost == 0.1
        assert candidate.rationale == "Test rationale"
        assert candidate.payload["key"] == "value"


class TestIntegration:
    """Integration tests for workspace candidate API."""
    
    def test_full_workflow(self):
        """Test full workflow: create, add, sort, merge, select."""
        # Create pools
        pool1 = CandidatePool()
        pool2 = CandidatePool()
        
        # Add candidates
        for i in range(5):
            c = Candidate(
                id=f"goal_{i}",
                source="drives",
                type=CandidateType.GOAL,
                utility=0.5 + i * 0.1,
            )
            pool1.add(c)
        
        for i in range(3):
            c = Candidate(
                id=f"action_{i}",
                source="planner",
                type=CandidateType.ACTION,
                utility=0.6 - i * 0.1,
            )
            pool2.add(c)
        
        # Merge
        pool1.merge(pool2)
        
        # Sort
        pool1.sort(reverse=True)
        
        # Get best
        best = pool1.get_best()
        
        assert best is not None
        assert best.id == "goal_4"  # Highest utility
        assert len(pool1) == 8
    
    def test_candidate_scoring_variations(self):
        """Test various scoring scenarios."""
        # High utility, high risk
        c1 = Candidate(id="risky", source="test", type=CandidateType.ACTION, utility=0.9, risk=0.8)
        
        # Medium utility, low risk
        c2 = Candidate(id="safe", source="test", type=CandidateType.ACTION, utility=0.6, risk=0.1)
        
        # Safe option should score higher due to risk penalty
        assert c2.compute_score() > c1.compute_score()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
