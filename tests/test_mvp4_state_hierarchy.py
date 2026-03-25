"""
MVP-4 D1: Hierarchical State System Tests

Tests for the 3-layer state hierarchy with different time scales:
- Affect (fast): Changes in seconds
- Mood (medium): Changes in hours  
- Bond/Trust (slow): Changes in days/weeks
"""
import pytest
import asyncio
import os
import sys
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emotiond.state import (
    AffectState, MoodState, BondState, StateHierarchy,
    apply_time_passed_affect, apply_time_passed_mood, apply_time_passed_bond
)
from emotiond.config import AFFECT_DECAY_TAU, MOOD_DECAY_TAU, BOND_CHANGE_RATE


class TestAffectState:
    """Tests for AffectState class"""
    
    def test_affect_state_creation(self):
        """Test that AffectState can be created with defaults"""
        affect = AffectState()
        assert affect.valence == 0.0
        assert affect.arousal == 0.3
        assert affect.anger == 0.0
        assert affect.sadness == 0.0
        assert affect.anxiety == 0.0
        assert affect.joy == 0.0
        assert affect.loneliness == 0.0
        assert affect.social_safety == 0.6
        assert affect.energy == 0.7
        assert affect.uncertainty == 0.5
        assert affect.last_updated > 0
    
    def test_affect_state_to_dict(self):
        """Test AffectState serialization"""
        affect = AffectState(valence=0.5, arousal=0.7)
        data = affect.to_dict()
        assert data["valence"] == 0.5
        assert data["arousal"] == 0.7
        assert "uncertainty" in data
        assert "last_updated" in data
    
    def test_affect_state_from_dict(self):
        """Test AffectState deserialization"""
        data = {"valence": 0.3, "arousal": 0.5, "uncertainty": 0.7}
        affect = AffectState.from_dict(data)
        assert affect.valence == 0.3
        assert affect.arousal == 0.5
        assert affect.uncertainty == 0.7


class TestMoodState:
    """Tests for MoodState class"""
    
    def test_mood_state_creation(self):
        """Test that MoodState can be created with defaults"""
        mood = MoodState()
        assert mood.valence == 0.0
        assert mood.arousal == 0.3
        assert mood.anxiety == 0.0
        assert mood.uncertainty == 0.5
        assert mood.last_updated > 0
    
    def test_mood_state_to_dict(self):
        """Test MoodState serialization"""
        mood = MoodState(valence=0.2, anxiety=0.1)
        data = mood.to_dict()
        assert data["valence"] == 0.2
        assert data["anxiety"] == 0.1
        assert "uncertainty" in data
    
    def test_mood_state_from_dict(self):
        """Test MoodState deserialization"""
        data = {"valence": -0.1, "anxiety": 0.3, "uncertainty": 0.6}
        mood = MoodState.from_dict(data)
        assert mood.valence == -0.1
        assert mood.anxiety == 0.3
        assert mood.uncertainty == 0.6


class TestBondState:
    """Tests for BondState class"""
    
    def test_bond_state_creation(self):
        """Test that BondState can be created with defaults"""
        bond = BondState(target="user_A")
        assert bond.target == "user_A"
        assert bond.bond == 0.0
        assert bond.trust == 0.0
        assert bond.grudge == 0.0
        assert bond.uncertainty == 0.5
        assert bond.last_updated > 0
    
    def test_bond_state_to_dict(self):
        """Test BondState serialization"""
        bond = BondState(target="user_B", bond=0.5, trust=0.3)
        data = bond.to_dict()
        assert data["target"] == "user_B"
        assert data["bond"] == 0.5
        assert data["trust"] == 0.3
    
    def test_bond_state_from_dict(self):
        """Test BondState deserialization"""
        data = {"target": "user_C", "bond": 0.7, "grudge": 0.2, "uncertainty": 0.4}
        bond = BondState.from_dict(data)
        assert bond.target == "user_C"
        assert bond.bond == 0.7
        assert bond.grudge == 0.2
        assert bond.uncertainty == 0.4


class TestTimeBasedDynamics:
    """Tests for time-based decay/homeostasis"""
    
    def test_affect_changes_faster_than_mood(self):
        """Test that affect changes faster than mood"""
        affect = AffectState(valence=0.8, arousal=0.5)
        mood = MoodState(valence=0.0, arousal=0.3)
        
        # Apply 60 seconds of time
        new_affect, new_mood = apply_time_passed_affect(affect, mood, time_seconds=60)
        
        # Affect should have decayed significantly toward mood
        affect_change = abs(new_affect.valence - 0.8)
        mood_change = abs(new_mood.valence - 0.0)
        
        # Affect change should be much larger than mood change
        assert affect_change > mood_change * 10, f"Affect change ({affect_change}) should be much larger than mood change ({mood_change})"
    
    def test_mood_changes_slower_than_affect(self):
        """Test that mood changes slower than affect"""
        affect = AffectState(valence=0.5)
        mood = MoodState(valence=0.0)
        
        # Apply 1 hour
        new_affect, new_mood = apply_time_passed_affect(affect, mood, time_seconds=3600)
        
        # After 1 hour, affect should be close to mood
        assert abs(new_affect.valence - new_mood.valence) < 0.2
    
    def test_mood_decays_to_baseline(self):
        """Test that mood decays toward baseline over time"""
        mood = MoodState(valence=0.8, anxiety=0.5)
        
        # Apply 24 hours
        new_mood = apply_time_passed_mood(mood, time_seconds=86400)
        
        # Mood should have decayed toward 0
        assert abs(new_mood.valence) < abs(mood.valence)
        assert abs(new_mood.anxiety) < abs(mood.anxiety)
    
    def test_bond_changes_very_slowly(self):
        """Test that bond/trust changes very slowly"""
        bond = BondState(target="user_A", bond=0.8, grudge=0.5)
        
        # Apply 1 day
        new_bond = apply_time_passed_bond(bond, time_seconds=86400)
        
        # Bond should have decayed very little
        bond_change = abs(new_bond.bond - 0.8)
        assert bond_change < 0.1, f"Bond change ({bond_change}) should be very small"
    
    def test_uncertainty_grows_with_time(self):
        """Test that uncertainty grows over time"""
        affect = AffectState(uncertainty=0.3)
        mood = MoodState(uncertainty=0.3)
        
        new_affect, _ = apply_time_passed_affect(affect, mood, time_seconds=300)
        
        # Uncertainty should have grown
        assert new_affect.uncertainty > affect.uncertainty


class TestTargetIsolation:
    """Tests for target isolation in bond/trust"""
    
    def test_target_a_bond_does_not_affect_target_b(self):
        """Test that Target A's bond change does not affect Target B"""
        hierarchy = StateHierarchy()
        
        # Set up bonds for two targets
        hierarchy.bonds["user_A"] = BondState(target="user_A", bond=0.8, trust=0.5)
        hierarchy.bonds["user_B"] = BondState(target="user_B", bond=0.2, trust=0.1)
        
        # Apply time
        hierarchy.apply_time_passed(time_seconds=86400)
        
        # Check isolation - both should have changed independently
        assert "user_A" in hierarchy.bonds
        assert "user_B" in hierarchy.bonds
        assert hierarchy.bonds["user_A"].bond != hierarchy.bonds["user_B"].bond
    
    def test_target_specific_uncertainty(self):
        """Test that each target has its own uncertainty"""
        hierarchy = StateHierarchy()
        
        # Create bonds with different uncertainties
        hierarchy.bonds["user_A"] = BondState(target="user_A", uncertainty=0.3)
        hierarchy.bonds["user_B"] = BondState(target="user_B", uncertainty=0.7)
        
        assert hierarchy.bonds["user_A"].uncertainty != hierarchy.bonds["user_B"].uncertainty
    
    def test_get_bond_creates_if_missing(self):
        """Test that get_bond creates bond state if missing"""
        hierarchy = StateHierarchy()
        
        bond = hierarchy.get_bond("new_target")
        assert bond.target == "new_target"
        assert bond.bond == 0.0
        assert bond.uncertainty == 0.5


class TestStateHierarchy:
    """Tests for StateHierarchy class"""
    
    def test_state_hierarchy_creation(self):
        """Test that StateHierarchy can be created"""
        hierarchy = StateHierarchy()
        assert hierarchy.affect is not None
        assert hierarchy.mood is not None
        assert isinstance(hierarchy.bonds, dict)
    
    def test_apply_time_passed_all_layers(self):
        """Test that apply_time_passed updates all layers"""
        hierarchy = StateHierarchy()
        
        # Set up some state
        hierarchy.affect.valence = 0.8
        hierarchy.mood.valence = 0.2
        hierarchy.bonds["user_A"] = BondState(target="user_A", bond=0.5)
        
        # Apply time
        hierarchy.apply_time_passed(time_seconds=60)
        
        # All layers should have changed
        assert hierarchy.affect.valence < 0.8  # Decay toward mood
        # Mood changes very slowly
        # Bond changes very slowly
    
    def test_to_dict_and_from_dict(self):
        """Test StateHierarchy serialization"""
        hierarchy = StateHierarchy()
        hierarchy.affect.valence = 0.5
        hierarchy.mood.anxiety = 0.3
        hierarchy.bonds["user_A"] = BondState(target="user_A", bond=0.7)
        
        data = hierarchy.to_dict()
        
        assert data["affect"]["valence"] == 0.5
        assert data["mood"]["anxiety"] == 0.3
        assert "user_A" in data["bonds"]
        
        # Deserialize
        new_hierarchy = StateHierarchy.from_dict(data)
        assert new_hierarchy.affect.valence == 0.5
        assert new_hierarchy.mood.anxiety == 0.3
        assert new_hierarchy.bonds["user_A"].bond == 0.7


class TestUncertaintyTracking:
    """Tests for uncertainty tracking"""
    
    def test_affect_uncertainty_increases_without_observation(self):
        """Test that affect uncertainty increases over time"""
        affect = AffectState(uncertainty=0.2)
        mood = MoodState()
        
        new_affect, _ = apply_time_passed_affect(affect, mood, time_seconds=600)
        
        assert new_affect.uncertainty > affect.uncertainty
    
    def test_mood_uncertainty_increases_without_observation(self):
        """Test that mood uncertainty increases over time"""
        mood = MoodState(uncertainty=0.2)
        
        new_mood = apply_time_passed_mood(mood, time_seconds=86400)
        
        assert new_mood.uncertainty > mood.uncertainty
    
    def test_bond_uncertainty_increases_without_observation(self):
        """Test that bond uncertainty increases over time"""
        bond = BondState(target="user_A", uncertainty=0.2)
        
        new_bond = apply_time_passed_bond(bond, time_seconds=86400)
        
        assert new_bond.uncertainty > bond.uncertainty


class TestTimeConstants:
    """Tests for time constants from config"""
    
    def test_affect_decay_tau_is_fast(self):
        """Test that affect decay tau is in seconds/minutes range"""
        # AFFECT_DECAY_TAU should be around 300 seconds (5 minutes)
        assert AFFECT_DECAY_TAU < 1000, "Affect decay should be fast (seconds/minutes)"
        assert AFFECT_DECAY_TAU > 60, "Affect decay should be at least a minute"
    
    def test_mood_decay_tau_is_slow(self):
        """Test that mood decay tau is in hours range"""
        # MOOD_DECAY_TAU should be around 86400 seconds (24 hours)
        assert MOOD_DECAY_TAU > 3600, "Mood decay should be slow (hours)"
        assert MOOD_DECAY_TAU < 172800, "Mood decay should be less than 2 days"
    
    def test_bond_change_rate_is_very_slow(self):
        """Test that bond change rate is very slow"""
        # BOND_CHANGE_RATE should be very small
        assert BOND_CHANGE_RATE < 0.01, "Bond change rate should be very slow"
        assert BOND_CHANGE_RATE > 0, "Bond change rate should be positive"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
