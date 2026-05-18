"""
Test plan generation API endpoint
"""
import os
import pytest
import pytest_asyncio
import asyncio
import tempfile
import shutil
from fastapi.testclient import TestClient
from emotiond.api import app
from emotiond.db import init_db, update_state, update_relationship
from emotiond import config, db, core
from emotiond.core import relationship_manager


def reset_all_global_state():
    """Reset all global state to ensure test isolation"""
    core.emotion_state.valence = 0.0
    core.emotion_state.arousal = 0.3
    core.emotion_state.subjective_time = 0
    core.emotion_state.prediction_error = 0.0
    core.relationship_manager.relationships = {}


@pytest_asyncio.fixture(scope="function")
async def isolated_test_db():
    """Setup isolated database for each test with proper cleanup"""
    # Reset global state FIRST
    reset_all_global_state()
    
    # Create temp directory for this test
    test_data_dir = tempfile.mkdtemp(prefix="emotiond_test_")
    
    # Override DB_PATH for this test
    original_db_path = os.environ.get("EMOTIOND_DB_PATH")
    os.environ["EMOTIOND_DB_PATH"] = os.path.join(test_data_dir, "test_emotiond.db")
    
    # Reimport config to pick up new DB path
    import importlib
    importlib.reload(config)
    importlib.reload(db)
    importlib.reload(core)  # Also reload core to pick up new db/config references
    
    # Reset again after reload
    reset_all_global_state()
    
    # Initialize database
    await db.init_db()
    
    yield
    
    # Cleanup
    if original_db_path:
        os.environ["EMOTIOND_DB_PATH"] = original_db_path
    else:
        os.environ.pop("EMOTIOND_DB_PATH", None)
    
    # Remove temp directory
    shutil.rmtree(test_data_dir, ignore_errors=True)


class TestPlanAPI:
    """Test plan generation API endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup_db(self, isolated_test_db):
        """Setup database for tests - uses isolated_test_db fixture"""
        yield
        reset_all_global_state()
    
    def test_plan_endpoint_returns_valid_json(self, isolated_test_db):
        """Test POST /plan endpoint returns valid Response Plan JSON"""
        reset_all_global_state()
        
        client = TestClient(app)
        
        # Set up initial state
        asyncio.run(update_state(0.5, 0.3, 100))
        asyncio.run(update_relationship("test_user", 0.7, 0.1))
        
        request_data = {
            "user_id": "test_user",
            "user_text": "How are you feeling?"
        }
        
        response = client.post("/plan", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "tone" in data
        assert "intent" in data
        assert "focus_target" in data
        assert "key_points" in data
        assert "constraints" in data
        assert "emotion" in data
        assert "relationship" in data
    
    def test_plan_endpoint_includes_all_required_fields(self, isolated_test_db):
        """Test POST /plan endpoint includes all required fields"""
        reset_all_global_state()
        
        client = TestClient(app)
        
        # Set up initial state
        asyncio.run(update_state(0.2, 0.4, 100))
        asyncio.run(update_relationship("user_b", 0.5, 0.2))
        
        request_data = {
            "user_id": "user_b",
            "user_text": "What's on your mind?"
        }
        
        response = client.post("/plan", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check all required fields
        assert data["tone"] in ["soft", "warm", "guarded", "cold"]
        assert data["intent"] in ["repair", "distance", "seek", "set_boundary", "retaliate"]
        assert data["focus_target"] == "user_b"
        assert isinstance(data["key_points"], list)
        assert isinstance(data["constraints"], list)
        assert isinstance(data["emotion"], dict)
        assert "valence" in data["emotion"]
        assert "arousal" in data["emotion"]
        assert isinstance(data["relationship"], dict)
        assert "bond" in data["relationship"]
        assert "grudge" in data["relationship"]
    
    def test_plan_endpoint_emotion_ranges(self, isolated_test_db):
        """Test that emotion values in plan response are within valid ranges"""
        reset_all_global_state()
        
        client = TestClient(app)
        
        # Set up extreme state
        asyncio.run(update_state(-0.9, 0.95, 100))
        asyncio.run(update_relationship("test_user", 0.1, 0.9))
        
        request_data = {
            "user_id": "test_user",
            "user_text": "Test"
        }
        
        response = client.post("/plan", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check emotion ranges
        assert -1.0 <= data["emotion"]["valence"] <= 1.0
        assert 0.0 <= data["emotion"]["arousal"] <= 1.0
        
        # Check relationship ranges
        assert 0.0 <= data["relationship"]["bond"] <= 1.0
        assert 0.0 <= data["relationship"]["grudge"] <= 1.0
    
    def test_plan_endpoint_key_points_and_constraints(self, isolated_test_db):
        """Test that key_points and constraints are generated in plan response"""
        reset_all_global_state()
        
        client = TestClient(app)
        
        # Set up state
        asyncio.run(update_state(0.4, 0.5, 100))
        asyncio.run(update_relationship("test_user", 0.6, 0.3))
        
        request_data = {
            "user_id": "test_user",
            "user_text": "Hello"
        }
        
        response = client.post("/plan", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify key_points and constraints exist
        assert isinstance(data["key_points"], list)
        assert isinstance(data["constraints"], list)
        assert len(data["key_points"]) > 0
        assert len(data["constraints"]) > 0
        
        # Verify they are strings
        for point in data["key_points"]:
            assert isinstance(point, str)
        for constraint in data["constraints"]:
            assert isinstance(constraint, str)
    
    def test_plan_endpoint_with_different_users(self, isolated_test_db):
        """Test that plan endpoint works with different user IDs"""
        reset_all_global_state()
        
        client = TestClient(app)
        
        # Set up different relationships for different users
        asyncio.run(update_state(0.3, 0.4, 100))
        asyncio.run(update_relationship("user_a", 0.8, 0.1))
        asyncio.run(update_relationship("user_b", 0.2, 0.7))
        
        # Re-set relationships in memory after TestClient startup
        relationship_manager.relationships["user_a"] = {"bond": 0.8, "grudge": 0.1}
        relationship_manager.relationships["user_b"] = {"bond": 0.2, "grudge": 0.7}
        
        # Test user A (high bond, low grudge)
        request_a = {
            "user_id": "user_a",
            "user_text": "Hello"
        }
        response_a = client.post("/plan", json=request_a)
        assert response_a.status_code == 200
        data_a = response_a.json()
        assert data_a["focus_target"] == "user_a"
        assert "bond" in data_a["relationship"]
        assert "grudge" in data_a["relationship"]
        
        # Test user B (low bond, high grudge)
        request_b = {
            "user_id": "user_b",
            "user_text": "Hello"
        }
        response_b = client.post("/plan", json=request_b)
        assert response_b.status_code == 200
        data_b = response_b.json()
        assert data_b["focus_target"] == "user_b"
        assert "bond" in data_b["relationship"]
        assert "grudge" in data_b["relationship"]

    def test_plan_self_report_boundary_and_evidence(self, isolated_test_db):
        """MVP-7 boundary check: self_report must be structured state, not user text echo."""
        reset_all_global_state()
        client = TestClient(app)

        asyncio.run(update_state(0.1, 0.4, 100))
        asyncio.run(update_relationship("u_boundary", 0.55, 0.15, 0.61, 0.03))

        injected = "I am furious and my secret token is XYZ-123"
        response = client.post("/plan", json={"user_id": "u_boundary", "user_text": injected})
        assert response.status_code == 200
        data = response.json()

        assert "self_report" in data and isinstance(data["self_report"], dict)
        report = data["self_report"]
        assert "self_model" in report and "evidence" in report
        assert "self_model_fields" in report["evidence"]

        # boundary: raw user text must not leak into structured self report payload
        dumped = str(report)
        assert "XYZ-123" not in dumped
        assert "furious" not in dumped.lower()
