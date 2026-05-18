"""
Test consolidation loop functionality
"""
import os
import pytest
import pytest_asyncio
import asyncio
import time
from emotiond.core import RelationshipManager, consolidation_loop
from emotiond.db import init_db, get_relationships, update_relationship
from emotiond.config import DB_PATH


@pytest_asyncio.fixture
async def setup_db():
    """Setup database for tests"""
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Remove existing database for test isolation
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    # Initialize database
    await init_db()
    
    # Clean up after tests
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)


class TestConsolidationLoop:
    """Test consolidation loop functionality"""
    
    def test_relationship_consolidation_drift(self):
        """Test that relationship consolidation drift works correctly"""
        manager = RelationshipManager()
        
        # Set up relationships with high values
        manager.relationships["A"] = {"bond": 0.8, "grudge": 0.6}
        manager.relationships["B"] = {"bond": 0.9, "grudge": 0.7}
        
        # Apply consolidation drift
        manager.apply_consolidation_drift()
        
        # Both bond and grudge should decay
        assert manager.relationships["A"]["bond"] < 0.8
        assert manager.relationships["A"]["grudge"] < 0.6
        assert manager.relationships["B"]["bond"] < 0.9
        assert manager.relationships["B"]["grudge"] < 0.7
        
        # Grudge should decay slower than bond
        bond_decay_A = 0.8 - manager.relationships["A"]["bond"]
        grudge_decay_A = 0.6 - manager.relationships["A"]["grudge"]
        # Grudge decays slower than bond (0.998 vs 0.995)
        assert grudge_decay_A < bond_decay_A
    
    @pytest.mark.asyncio
    async def test_consolidation_loop_persistence(self, setup_db):
        """Test that consolidation loop persists relationship changes to database"""
        # Set up initial relationships in database
        await update_relationship("test_target", 0.8, 0.6)
        
        # Get initial values
        initial_relationships = await get_relationships()
        initial_target = [r for r in initial_relationships if r["target"] == "test_target"][0]
        initial_bond = initial_target["bond"]
        initial_grudge = initial_target["grudge"]
        
        # Apply consolidation drift (simulating what the loop would do)
        from emotiond.core import relationship_manager
        relationship_manager.relationships["test_target"] = {"bond": initial_bond, "grudge": initial_grudge}
        relationship_manager.apply_consolidation_drift()
        
        # Persist to database (simulating what the loop would do)
        for target, rel_data in relationship_manager.relationships.items():
            await update_relationship(target, rel_data["bond"], rel_data["grudge"])
        
        # Check that values have decayed in database
        final_relationships = await get_relationships()
        final_target = [r for r in final_relationships if r["target"] == "test_target"][0]
        assert final_target["bond"] < initial_bond
        assert final_target["grudge"] < initial_grudge
    
    def test_consolidation_loop_interval(self):
        """Test that consolidation loop runs at appropriate intervals"""
        # This test verifies the loop timing by checking the sleep interval
        # The consolidation loop should sleep for 30 seconds between runs
        
        # We can't directly test the loop timing without running it,
        # but we can verify the implementation logic
        from emotiond.core import consolidation_loop
        
        # The consolidation_loop function should exist and be async
        assert asyncio.iscoroutinefunction(consolidation_loop)
        
        # We can verify that the loop contains the expected sleep interval
        # by checking the source code structure
        source_code = open("emotiond/core.py").read()
        assert "await asyncio.sleep(30)" in source_code
    
    def test_consolidation_loop_with_multiple_targets(self):
        """Test consolidation drift with multiple relationship targets"""
        manager = RelationshipManager()
        
        # Set up multiple targets with different relationship values
        targets_data = {
            "user_A": {"bond": 0.9, "grudge": 0.1},
            "user_B": {"bond": 0.3, "grudge": 0.8},
            "user_C": {"bond": 0.5, "grudge": 0.5}
        }
        
        # Store initial values
        initial_values = {}
        for target, data in targets_data.items():
            manager.relationships[target] = data
            initial_values[target] = {"bond": data["bond"], "grudge": data["grudge"]}
        
        # Apply consolidation drift multiple times to ensure decay is visible
        for _ in range(10):
            manager.apply_consolidation_drift()
        
        # All relationships should have decayed
        for target, initial_data in initial_values.items():
            assert manager.relationships[target]["bond"] < initial_data["bond"]
            assert manager.relationships[target]["grudge"] < initial_data["grudge"]
        
        # Verify values remain within bounds
        for target in targets_data:
            assert 0.0 <= manager.relationships[target]["bond"] <= 1.0
            assert 0.0 <= manager.relationships[target]["grudge"] <= 1.0
    
    def test_consolidation_drift_boundary_conditions(self):
        """Test consolidation drift with boundary values"""
        manager = RelationshipManager()
        
        # Test with minimum values
        manager.relationships["min_target"] = {"bond": 0.0, "grudge": 0.0}
        manager.apply_consolidation_drift()
        assert manager.relationships["min_target"]["bond"] == 0.0
        assert manager.relationships["min_target"]["grudge"] == 0.0
        
        # Test with maximum values
        manager.relationships["max_target"] = {"bond": 1.0, "grudge": 1.0}
        manager.apply_consolidation_drift()
        assert manager.relationships["max_target"]["bond"] < 1.0
        assert manager.relationships["max_target"]["grudge"] < 1.0
        
        # Test with very small values
        manager.relationships["small_target"] = {"bond": 0.001, "grudge": 0.001}
        manager.apply_consolidation_drift()
        assert manager.relationships["small_target"]["bond"] < 0.001
        assert manager.relationships["small_target"]["grudge"] < 0.001
    
    @pytest.mark.asyncio
    async def test_consolidation_preserves_relationship_structure(self, setup_db):
        """Test that consolidation preserves the relationship structure"""
        # Set up complex relationship structure
        targets = ["user_A", "user_B", "user_C", "system"]
        
        for target in targets:
            await update_relationship(target, 0.5, 0.3)
        
        # Apply consolidation drift
        from emotiond.core import relationship_manager
        for target in targets:
            relationship_manager.relationships[target] = {"bond": 0.5, "grudge": 0.3}
        
        relationship_manager.apply_consolidation_drift()
        
        # Verify all targets still exist
        for target in targets:
            assert target in relationship_manager.relationships
            assert "bond" in relationship_manager.relationships[target]
            assert "grudge" in relationship_manager.relationships[target]
        
        # Persist and verify database structure
        for target, rel_data in relationship_manager.relationships.items():
            await update_relationship(target, rel_data["bond"], rel_data["grudge"])
        
        final_relationships = await get_relationships()
        final_targets = [r["target"] for r in final_relationships]
        assert set(targets).issubset(set(final_targets))