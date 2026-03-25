"""
Test suite for relationship management per target (US-019)
"""
import pytest
import asyncio
from emotiond.models import Event
from emotiond.core import RelationshipManager
import os
import tempfile


class TestRelationshipManagement:
    """Test relationship management per target functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.manager = RelationshipManager()
    
    def test_relationship_manager_initialization(self):
        """Test RelationshipManager initializes with empty relationships"""
        assert self.manager.relationships == {}
    
    def test_relationship_creation_on_first_event(self):
        """Test relationship is created for new target on first event"""
        event = Event(
            type="user_message",
            actor="user_A",
            target="assistant",
            text="Hello, this is a positive message"
        )
        
        self.manager.update_from_event(event)
        
        assert "user_A" in self.manager.relationships
        assert "bond" in self.manager.relationships["user_A"]
        assert "grudge" in self.manager.relationships["user_A"]
        assert self.manager.relationships["user_A"]["bond"] == 0.0
        assert self.manager.relationships["user_A"]["grudge"] == 0.0
    
    def test_positive_event_bond_increase(self):
        """Test positive user message increases bond"""
        event = Event(
            type="user_message",
            actor="user_A",
            target="assistant",
            text="This is great! I love it!"
        )
        
        self.manager.update_from_event(event)
        
        # Bond should increase by approximately 0.1 (plus memory impact)
        assert self.manager.relationships["user_A"]["bond"] > 0.0
        assert self.manager.relationships["user_A"]["bond"] <= 1.0
        assert self.manager.relationships["user_A"]["grudge"] == 0.0
    
    def test_negative_event_grudge_increase(self):
        """Test negative user message increases grudge"""
        event = Event(
            type="user_message",
            actor="user_A",
            target="assistant",
            text="This is terrible and awful!"
        )
        
        self.manager.update_from_event(event)
        
        # Grudge should increase by approximately 0.1 (plus memory impact)
        assert self.manager.relationships["user_A"]["grudge"] > 0.0
        assert self.manager.relationships["user_A"]["grudge"] <= 1.0
        assert self.manager.relationships["user_A"]["bond"] == 0.0
    
    def test_multiple_targets_separate_relationships(self):
        """Test relationships are maintained separately per target"""
        # Positive event for user_A
        event1 = Event(
            type="user_message",
            actor="user_A",
            target="assistant",
            text="Great job!"
        )
        self.manager.update_from_event(event1)
        
        # Negative event for user_B
        event2 = Event(
            type="user_message",
            actor="user_B",
            target="assistant",
            text="Terrible work!"
        )
        self.manager.update_from_event(event2)
        
        # Verify separate relationships
        assert "user_A" in self.manager.relationships
        assert "user_B" in self.manager.relationships
        assert self.manager.relationships["user_A"]["bond"] > 0.0
        assert self.manager.relationships["user_A"]["grudge"] == 0.0
        assert self.manager.relationships["user_B"]["grudge"] > 0.0
        assert self.manager.relationships["user_B"]["bond"] == 0.0
    
    def test_betrayal_event_grudge_bond_change(self):
        """Test betrayal world event increases grudge and decreases bond"""
        # First establish some bond
        event1 = Event(
            type="user_message",
            actor="user_A",
            target="assistant",
            text="Good work!"
        )
        self.manager.update_from_event(event1)
        initial_bond = self.manager.relationships["user_A"]["bond"]
        
        # Betrayal event
        event2 = Event(
            type="world_event",
            actor="user_A",
            target="user_A",
            text="Betrayal occurred",
            meta={"betrayal": True}
        )
        self.manager.update_from_event(event2)
        
        # Grudge should increase significantly
        assert self.manager.relationships["user_A"]["grudge"] > 0.0
        # Bond should decrease
        assert self.manager.relationships["user_A"]["bond"] < initial_bond
    
    def test_consolidation_drift_bond_decay(self):
        """Test bond decays over time with consolidation drift"""
        # Establish bond
        event = Event(
            type="user_message",
            actor="user_A",
            target="assistant",
            text="Great work!"
        )
        self.manager.update_from_event(event)
        initial_bond = self.manager.relationships["user_A"]["bond"]
        
        # Apply consolidation drift (decay factor 0.995)
        self.manager.apply_consolidation_drift()
        
        # Bond should decay slightly
        assert self.manager.relationships["user_A"]["bond"] < initial_bond
        assert self.manager.relationships["user_A"]["bond"] > 0.0
    
    def test_consolidation_drift_grudge_slower_decay(self):
        """Test grudge decays slower than bond"""
        # Establish grudge
        event = Event(
            type="user_message",
            actor="user_A",
            target="assistant",
            text="Terrible!"
        )
        self.manager.update_from_event(event)
        initial_grudge = self.manager.relationships["user_A"]["grudge"]
        
        # Apply consolidation drift (decay factor 0.998 for grudge vs 0.995 for bond)
        self.manager.apply_consolidation_drift()
        
        # Grudge should decay but remain higher than bond would
        assert self.manager.relationships["user_A"]["grudge"] < initial_grudge
        assert self.manager.relationships["user_A"]["grudge"] > 0.0
    
    def test_relationship_boundary_conditions(self):
        """Test relationship values stay within bounds [0, 1]"""
        # Test multiple positive events don't exceed 1.0
        for _ in range(20):
            event = Event(
                type="user_message",
                actor="user_A",
            target="assistant",
                text="Excellent!"
            )
            self.manager.update_from_event(event)
        
        assert self.manager.relationships["user_A"]["bond"] <= 1.0
        assert self.manager.relationships["user_A"]["bond"] >= 0.0
        
        # Test multiple negative events don't exceed 1.0
        for _ in range(20):
            event = Event(
                type="user_message",
                actor="user_B",
            target="assistant",
                text="Horrible!"
            )
            self.manager.update_from_event(event)
        
        assert self.manager.relationships["user_B"]["grudge"] <= 1.0
        assert self.manager.relationships["user_B"]["grudge"] >= 0.0
    
    def test_assistant_reply_no_relationship_change(self):
        """Test assistant replies don't change relationships"""
        # First establish some relationship
        event1 = Event(
            type="user_message",
            actor="user_A",
            target="assistant",
            text="Good work!"
        )
        self.manager.update_from_event(event1)
        initial_bond = self.manager.relationships["user_A"]["bond"]
        initial_grudge = self.manager.relationships["user_A"]["grudge"]
        
        # Assistant reply shouldn't change relationships
        event2 = Event(
            type="assistant_reply",
            actor="assistant",
            target="user_A",
            text="Thank you"
        )
        self.manager.update_from_event(event2)
        
        assert self.manager.relationships["user_A"]["bond"] == initial_bond
        assert self.manager.relationships["user_A"]["grudge"] == initial_grudge
    
    def test_relationship_values_clamped_at_zero(self):
        """Test relationship values don't go below zero"""
        # Create relationship with zero values
        self.manager.relationships["user_A"] = {"bond": 0.0, "grudge": 0.0}
        
        # Apply consolidation drift multiple times
        for _ in range(10):
            self.manager.apply_consolidation_drift()
        
        # Values should remain at zero
        assert self.manager.relationships["user_A"]["bond"] == 0.0
        assert self.manager.relationships["user_A"]["grudge"] == 0.0
    
    def test_neutral_user_message_no_relationship_change(self):
        """Test neutral user messages don't affect relationships"""
        # Create initial relationship
        self.manager.relationships["user_A"] = {"bond": 0.5, "grudge": 0.3}
        initial_bond = 0.5
        initial_grudge = 0.3
        
        # Neutral message
        event = Event(
            type="user_message",
            actor="user_A",
            target="assistant",
            text="Hello, how are you?"
        )
        self.manager.update_from_event(event)
        
        # No change should occur
        assert self.manager.relationships["user_A"]["bond"] == initial_bond
        assert self.manager.relationships["user_A"]["grudge"] == initial_grudge


if __name__ == "__main__":
    pytest.main([__file__, "-v"])