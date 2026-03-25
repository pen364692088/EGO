"""
Tests for Phase D (P1.1): counterparty_id / target_id contract

Verifies that:
1. PlanRequest supports target_id, counterparty_id, agent_id fields
2. Fallback logic works correctly
3. generate_plan uses counterparty_id for relationship lookup
4. target_id and counterparty_id are properly separated
"""
import os
import pytest
import pytest_asyncio
import asyncio
import tempfile
import shutil
from unittest.mock import patch
from emotiond.db import init_db, update_state, update_relationship
from emotiond.models import PlanRequest, PlanResponse
from emotiond.core import generate_plan, relationship_manager
from emotiond import config, db, core


@pytest_asyncio.fixture(scope="function")
async def isolated_test_db():
    """Setup isolated database for each test with proper cleanup"""
    import importlib
    
    # Create temp directory for this test
    test_data_dir = tempfile.mkdtemp(prefix="emotiond_test_")
    
    # Override DB_PATH for this test
    original_db_path = os.environ.get("EMOTIOND_DB_PATH")
    os.environ["EMOTIOND_DB_PATH"] = os.path.join(test_data_dir, "test_emotiond.db")
    
    # Reimport config to pick up new DB path
    importlib.reload(config)
    importlib.reload(db)
    importlib.reload(core)
    
    # Reset global state
    core.emotion_state.valence = 0.0
    core.emotion_state.arousal = 0.3
    core.emotion_state.subjective_time = 0
    core.emotion_state.prediction_error = 0.0
    core.relationship_manager.relationships = {}
    
    # Initialize database
    await db.init_db()
    
    yield
    
    # Cleanup
    if original_db_path:
        os.environ["EMOTIOND_DB_PATH"] = original_db_path
    else:
        del os.environ["EMOTIOND_DB_PATH"]
    
    shutil.rmtree(test_data_dir, ignore_errors=True)


class TestPlanRequestFields:
    """Test PlanRequest field semantics (no DB needed)."""
    
    def test_basic_fields_exist(self):
        """Verify new optional fields exist."""
        req = PlanRequest(user_id="test", user_text="hello")
        assert req.target_id is None
        assert req.counterparty_id is None
        assert req.agent_id is None
    
    def test_explicit_fields(self):
        """Verify explicit field values are preserved."""
        req = PlanRequest(
            user_id="user123",
            user_text="hello",
            target_id="telegram:8420019401",
            counterparty_id="moonlight",
            agent_id="agent"
        )
        assert req.target_id == "telegram:8420019401"
        assert req.counterparty_id == "moonlight"
        assert req.agent_id == "agent"
    
    def test_get_counterparty_id_fallback_to_focus_target(self):
        """counterparty_id falls back to focus_target."""
        req = PlanRequest(
            user_id="user123",
            user_text="hello",
            focus_target="target_a"
        )
        assert req.get_counterparty_id() == "target_a"
    
    def test_get_counterparty_id_fallback_to_user_id(self):
        """counterparty_id falls back to user_id if nothing else specified."""
        req = PlanRequest(user_id="user123", user_text="hello")
        assert req.get_counterparty_id() == "user123"
    
    def test_get_counterparty_id_explicit_wins(self):
        """Explicit counterparty_id takes precedence."""
        req = PlanRequest(
            user_id="user123",
            user_text="hello",
            focus_target="target_a",
            counterparty_id="moonlight"
        )
        assert req.get_counterparty_id() == "moonlight"
    
    def test_get_target_id_fallback_to_counterparty_id(self):
        """target_id falls back to counterparty_id."""
        req = PlanRequest(
            user_id="user123",
            user_text="hello",
            counterparty_id="moonlight"
        )
        assert req.get_target_id() == "moonlight"
    
    def test_get_target_id_explicit_wins(self):
        """Explicit target_id takes precedence."""
        req = PlanRequest(
            user_id="user123",
            user_text="hello",
            target_id="telegram:8420019401",
            counterparty_id="moonlight"
        )
        assert req.get_target_id() == "telegram:8420019401"
        assert req.get_counterparty_id() == "moonlight"
        # These should be different!
        assert req.get_target_id() != req.get_counterparty_id()
    
    def test_get_agent_id_default(self):
        """agent_id defaults to 'agent'."""
        req = PlanRequest(user_id="user123", user_text="hello")
        assert req.get_agent_id() == "agent"
    
    def test_get_agent_id_explicit(self):
        """Explicit agent_id is preserved."""
        req = PlanRequest(
            user_id="user123",
            user_text="hello",
            agent_id="custom_agent"
        )
        assert req.get_agent_id() == "custom_agent"


class TestGeneratePlanFieldUsage:
    """Test that generate_plan uses fields correctly."""
    
    @pytest.mark.asyncio
    async def test_plan_uses_counterparty_id_for_relationship(self, isolated_test_db):
        """Verify generate_plan uses counterparty_id for relationship lookup."""
        # Setup: Create a relationship for a specific counterparty
        core.relationship_manager.relationships["moonlight"] = {
            "bond": 0.8,
            "grudge": 0.1,
            "trust": 0.7,
            "repair_bank": 0.2,
            "uncertainty": 0.3
        }
        
        req = PlanRequest(
            user_id="user123",
            user_text="hello",
            target_id="telegram:8420019401",  # Different from counterparty_id
            counterparty_id="moonlight"
        )
        
        result = await generate_plan(req)
        
        # Verify the relationship returned is for counterparty_id (moonlight)
        assert result.relationship["bond"] == 0.8
        assert result.focus_target == "moonlight"
    
    @pytest.mark.asyncio
    async def test_plan_target_id_counterparty_id_separation(self, isolated_test_db):
        """
        Verify that target_id and counterparty_id can be different.
        
        This is the core issue Phase D (P1.1) addresses:
        - target_id = conversationId (session isolation)
        - counterparty_id = relationship target (who we have a relationship with)
        
        Different conversations with the same user should share the same
        relationship state, not create separate ones.
        """
        # Setup: Create a relationship for a specific user
        core.relationship_manager.relationships["moonlight"] = {
            "bond": 0.5,
            "grudge": 0.0,
            "trust": 0.5,
            "repair_bank": 0.0,
            "uncertainty": 0.5
        }
        
        # Request 1: conversation A
        req1 = PlanRequest(
            user_id="user123",
            user_text="hello",
            target_id="conversation_A",  # Different conversation
            counterparty_id="moonlight"   # Same user
        )
        
        # Request 2: conversation B
        req2 = PlanRequest(
            user_id="user123",
            user_text="hello",
            target_id="conversation_B",  # Different conversation
            counterparty_id="moonlight"   # Same user
        )
        
        result1 = await generate_plan(req1)
        result2 = await generate_plan(req2)
        
        # Both should return the same relationship state
        # because counterparty_id is the same
        assert result1.focus_target == "moonlight"
        assert result2.focus_target == "moonlight"
        assert result1.relationship["bond"] == result2.relationship["bond"]


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""
    
    @pytest.mark.asyncio
    async def test_plan_without_new_fields_still_works(self, isolated_test_db):
        """Verify existing code without new fields still works."""
        req = PlanRequest(user_id="moonlight", user_text="hello")
        
        result = await generate_plan(req)
        
        # Should use user_id as focus_target
        assert result.focus_target == "moonlight"
    
    @pytest.mark.asyncio
    async def test_plan_with_only_focus_target_still_works(self, isolated_test_db):
        """Verify focus_target alone still works."""
        req = PlanRequest(
            user_id="user123",
            user_text="hello",
            focus_target="target_a"
        )
        
        result = await generate_plan(req)
        
        assert result.focus_target == "target_a"
