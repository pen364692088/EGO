"""
Test plan endpoint focus_target semantics and relationship handling
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
from emotiond.core import generate_plan
from emotiond import config, db, core


@pytest_asyncio.fixture(scope="function")
async def isolated_test_db():
    """Setup isolated database for each test with proper cleanup"""
    # Import here to avoid circular imports
    import importlib
    
    # Create temp directory for this test
    test_data_dir = tempfile.mkdtemp(prefix="emotiond_test_")
    
    # Override DB_PATH for this test
    original_db_path = os.environ.get("EMOTIOND_DB_PATH")
    os.environ["EMOTIOND_DB_PATH"] = os.path.join(test_data_dir, "test_emotiond.db")
    
    # Reimport config to pick up new DB path
    importlib.reload(config)
    importlib.reload(db)
    importlib.reload(core)  # Also reload core to pick up new db/config references
    
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
        os.environ.pop("EMOTIOND_DB_PATH", None)
    
    # Reset state after test
    core.emotion_state.valence = 0.0
    core.emotion_state.arousal = 0.3
    core.emotion_state.subjective_time = 0
    core.emotion_state.prediction_error = 0.0
    core.relationship_manager.relationships = {}
    
    # Remove temp directory
    shutil.rmtree(test_data_dir, ignore_errors=True)


class TestPlanFocusTargetSemantics:
    """Test focus_target parameter and relationship semantics"""
    
    @pytest.mark.asyncio
    async def test_plan_with_user_id_returns_relationship_for_user(self, isolated_test_db):
        """Test that /plan with user_id='X' returns relationship for X"""
        # Set up relationship for user X in database AND memory
        await update_state(0.3, 0.4, 100)
        await update_relationship("user_x", 0.7, 0.2)
        
        # Load into memory
        core.relationship_manager.relationships["user_x"] = {"bond": 0.7, "grudge": 0.2}
        
        # Generate plan without focus_target
        request = PlanRequest(
            user_id="user_x",
            user_text="Hello"
        )
        
        response = await generate_plan(request)
        
        # Verify relationship is for user_x
        assert response.focus_target == "user_x"
        assert response.relationship["bond"] == 0.7
        assert response.relationship["grudge"] == 0.2
        assert "trust" in response.relationship
    
    @pytest.mark.asyncio
    async def test_plan_with_focus_target_returns_relationship_for_target(self, isolated_test_db):
        """Test that /plan with user_id='X' and focus_target='Y' returns relationship for Y"""
        # Set up relationships for different users
        await update_state(0.3, 0.4, 100)
        await update_relationship("user_x", 0.7, 0.2)
        await update_relationship("user_y", 0.3, 0.8)
        
        # Load into memory
        core.relationship_manager.relationships["user_x"] = {"bond": 0.7, "grudge": 0.2}
        core.relationship_manager.relationships["user_y"] = {"bond": 0.3, "grudge": 0.8}
        
        # Generate plan with focus_target='Y'
        request = PlanRequest(
            user_id="user_x",
            user_text="Hello",
            focus_target="user_y"
        )
        
        response = await generate_plan(request)
        
        # Verify relationship is for user_y (focus_target)
        assert response.focus_target == "user_y"
        assert response.relationship["bond"] == 0.3
        assert response.relationship["grudge"] == 0.8
    
    @pytest.mark.asyncio
    async def test_plan_with_no_relationship_returns_empty(self, isolated_test_db):
        """Test that /plan returns empty relationship if no relationship exists"""
        await update_state(0.3, 0.4, 100)
        
        # No relationship set for new_user
        request = PlanRequest(
            user_id="new_user",
            user_text="Hello"
        )
        
        response = await generate_plan(request)
        
        # Verify empty relationship is returned
        assert response.focus_target == "new_user"
        assert response.relationship["bond"] == 0.0
        assert response.relationship["grudge"] == 0.0
        assert response.relationship["trust"] == 0.0
    
    @pytest.mark.asyncio
    async def test_plan_with_focus_target_no_relationship_returns_empty(self, isolated_test_db):
        """Test that /plan with focus_target returns empty relationship if target has no relationship"""
        await update_state(0.3, 0.4, 100)
        core.relationship_manager.relationships["user_x"] = {"bond": 0.5, "grudge": 0.1}
        
        # focus_target='user_z' has no relationship
        request = PlanRequest(
            user_id="user_x",
            user_text="Hello",
            focus_target="user_z"
        )
        
        response = await generate_plan(request)
        
        # Verify empty relationship for user_z
        assert response.focus_target == "user_z"
        assert response.relationship["bond"] == 0.0
        assert response.relationship["grudge"] == 0.0
        assert response.relationship["trust"] == 0.0
    
    @pytest.mark.asyncio
    async def test_plan_includes_trust_field(self, isolated_test_db):
        """Test that relationship includes trust field"""
        await update_state(0.3, 0.4, 100)
        core.relationship_manager.relationships["test_user"] = {"bond": 0.6, "grudge": 0.2}
        
        request = PlanRequest(
            user_id="test_user",
            user_text="Hello"
        )
        
        response = await generate_plan(request)
        
        # Verify trust field exists
        assert "trust" in response.relationship
        assert response.relationship["trust"] == 0.0  # Default value
    
    @pytest.mark.asyncio
    async def test_plan_relationships_field_disabled_by_default(self, isolated_test_db):
        """Test that relationships field is None by default"""
        await update_state(0.3, 0.4, 100)
        core.relationship_manager.relationships["user_a"] = {"bond": 0.6, "grudge": 0.1}
        core.relationship_manager.relationships["user_b"] = {"bond": 0.3, "grudge": 0.5}
        
        request = PlanRequest(
            user_id="user_a",
            user_text="Hello"
        )
        
        response = await generate_plan(request)
        
        # Verify relationships field is None by default
        assert response.relationships is None
    
    @pytest.mark.asyncio
    async def test_plan_relationships_field_enabled_with_env_flag(self, isolated_test_db):
        """Test that relationships field includes all relationships when env flag is set"""
        await update_state(0.3, 0.4, 100)
        core.relationship_manager.relationships["user_a"] = {"bond": 0.6, "grudge": 0.1}
        core.relationship_manager.relationships["user_b"] = {"bond": 0.3, "grudge": 0.5}
        
        # Set env flag
        with patch.dict(os.environ, {"EMOTIOND_PLAN_INCLUDE_RELATIONSHIPS": "1"}):
            request = PlanRequest(
                user_id="user_a",
                user_text="Hello"
            )
            
            response = await generate_plan(request)
            
            # Verify relationships field includes all relationships
            assert response.relationships is not None
            assert "user_a" in response.relationships
            assert "user_b" in response.relationships
            assert response.relationships["user_a"]["bond"] == 0.6
            assert response.relationships["user_b"]["grudge"] == 0.5
            # Verify trust field in all relationships
            assert "trust" in response.relationships["user_a"]
            assert "trust" in response.relationships["user_b"]
    
    @pytest.mark.asyncio
    async def test_plan_dynamic_target_any_string(self, isolated_test_db):
        """Test that target can be any string (not just A/B/C)"""
        await update_state(0.3, 0.4, 100)
        
        # Test with arbitrary user ID
        arbitrary_user = "arbitrary_user_123"
        core.relationship_manager.relationships[arbitrary_user] = {"bond": 0.8, "grudge": 0.1}
        
        request = PlanRequest(
            user_id=arbitrary_user,
            user_text="Hello"
        )
        
        response = await generate_plan(request)
        
        assert response.focus_target == arbitrary_user
        assert response.relationship["bond"] == 0.8
        assert response.relationship["grudge"] == 0.1
    
    @pytest.mark.asyncio
    async def test_plan_dynamic_focus_target_any_string(self, isolated_test_db):
        """Test that focus_target can be any string"""
        await update_state(0.3, 0.4, 100)
        
        arbitrary_target = "some_random_target_xyz"
        core.relationship_manager.relationships[arbitrary_target] = {"bond": 0.4, "grudge": 0.6}
        
        request = PlanRequest(
            user_id="user_a",
            user_text="Hello",
            focus_target=arbitrary_target
        )
        
        response = await generate_plan(request)
        
        assert response.focus_target == arbitrary_target
        assert response.relationship["bond"] == 0.4
        assert response.relationship["grudge"] == 0.6


class TestPlanAPIClient:
    """Test plan API with focus_target via HTTP client"""
    
    def test_api_plan_with_focus_target(self, isolated_test_db):
        """Test POST /plan with focus_target parameter"""
        from fastapi.testclient import TestClient
        from emotiond.api import app
        
        # Set up relationships BEFORE creating TestClient
        asyncio.run(update_state(0.3, 0.4, 100))
        asyncio.run(update_relationship("user_x", 0.7, 0.2))
        asyncio.run(update_relationship("user_y", 0.3, 0.8))
        
        core.relationship_manager.relationships["user_x"] = {"bond": 0.7, "grudge": 0.2}
        core.relationship_manager.relationships["user_y"] = {"bond": 0.3, "grudge": 0.8}
        
        # Create client AFTER setting up relationships
        client = TestClient(app)
        
        # Re-set relationships after TestClient startup
        core.relationship_manager.relationships["user_x"] = {"bond": 0.7, "grudge": 0.2}
        core.relationship_manager.relationships["user_y"] = {"bond": 0.3, "grudge": 0.8}
        
        # Request with focus_target
        request_data = {
            "user_id": "user_x",
            "user_text": "Hello",
            "focus_target": "user_y"
        }
        
        response = client.post("/plan", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify relationship is for focus_target (user_y)
        assert data["focus_target"] == "user_y"
        assert data["relationship"]["bond"] == 0.3
        assert data["relationship"]["grudge"] == 0.8
        assert "trust" in data["relationship"]
    
    def test_api_plan_without_focus_target_defaults_to_user_id(self, isolated_test_db):
        """Test POST /plan without focus_target defaults to user_id"""
        from fastapi.testclient import TestClient
        from emotiond.api import app
        
        asyncio.run(update_state(0.3, 0.4, 100))
        asyncio.run(update_relationship("user_x", 0.7, 0.2))
        
        core.relationship_manager.relationships["user_x"] = {"bond": 0.7, "grudge": 0.2}
        
        client = TestClient(app)
        
        # Re-set relationships after TestClient startup
        core.relationship_manager.relationships["user_x"] = {"bond": 0.7, "grudge": 0.2}
        
        # Request without focus_target
        request_data = {
            "user_id": "user_x",
            "user_text": "Hello"
        }
        
        response = client.post("/plan", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify focus_target defaults to user_id
        assert data["focus_target"] == "user_x"
        assert data["relationship"]["bond"] == 0.7
        assert data["relationship"]["grudge"] == 0.2
    
    def test_api_plan_with_env_flag_includes_all_relationships(self, isolated_test_db):
        """Test POST /plan with env flag includes all relationships"""
        from fastapi.testclient import TestClient
        from emotiond.api import app
        
        asyncio.run(update_state(0.3, 0.4, 100))
        
        # Set up relationships BEFORE creating TestClient
        core.relationship_manager.relationships["user_a"] = {"bond": 0.6, "grudge": 0.1}
        core.relationship_manager.relationships["user_b"] = {"bond": 0.3, "grudge": 0.5}
        
        client = TestClient(app)
        
        # Re-set relationships after TestClient startup
        core.relationship_manager.relationships["user_a"] = {"bond": 0.6, "grudge": 0.1}
        core.relationship_manager.relationships["user_b"] = {"bond": 0.3, "grudge": 0.5}
        
        # Set env flag
        with patch.dict(os.environ, {"EMOTIOND_PLAN_INCLUDE_RELATIONSHIPS": "1"}):
            request_data = {
                "user_id": "user_a",
                "user_text": "Hello"
            }
            
            response = client.post("/plan", json=request_data)
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify relationships field is present
            assert "relationships" in data
            assert data["relationships"] is not None
            assert "user_a" in data["relationships"]
            assert "user_b" in data["relationships"]
