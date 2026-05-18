"""
Tests for /decision API endpoint with target_id support.
"""
import pytest
import pytest_asyncio
import os
import asyncio
from httpx import AsyncClient, ASGITransport


@pytest_asyncio.fixture(scope="function")
async def isolated_db():
    """Setup isolated database for tests with proper cleanup"""
    from emotiond import config, db, core
    import importlib
    import tempfile
    
    test_data_dir = tempfile.mkdtemp(prefix="emotiond_test_")
    original_db_path = os.environ.get("EMOTIOND_DB_PATH")
    
    os.environ["EMOTIOND_DB_PATH"] = os.path.join(test_data_dir, "test_emotiond.db")
    
    importlib.reload(config)
    importlib.reload(db)
    importlib.reload(core)
    
    # Reset global state
    core.emotion_state.valence = 0.0
    core.emotion_state.arousal = 0.3
    core.emotion_state.subjective_time = 0
    core.emotion_state.prediction_error = 0.0
    core.emotion_state.anger = 0.0
    core.emotion_state.sadness = 0.0
    core.emotion_state.anxiety = 0.0
    core.emotion_state.joy = 0.0
    core.emotion_state.loneliness = 0.0
    core.emotion_state.regulation_budget = 1.0
    core.emotion_state.social_safety = 0.6
    core.emotion_state.energy = 0.7
    core.relationship_manager.relationships = {}
    core.relationship_manager.last_actions = {}
    
    await db.init_db()
    
    yield
    
    if original_db_path:
        os.environ["EMOTIOND_DB_PATH"] = original_db_path
    else:
        os.environ.pop("EMOTIOND_DB_PATH", None)


def get_client():
    """Get AsyncClient with proper ASGITransport for new httpx versions."""
    from emotiond.api import app
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_decision_global_no_decisions(isolated_db):
    """Test /decision returns no_decision when no decisions exist."""
    async with get_client() as client:
        response = await client.get("/decision")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "no_decision"
    assert data["decision"] is None


@pytest.mark.asyncio
async def test_decision_global_returns_latest(isolated_db):
    """Test /decision returns the latest decision."""
    from emotiond.db import save_decision
    
    # Create two decisions
    id1 = await save_decision("respond_warm", {"reason": "first"}, target_id="target_a")
    id2 = await save_decision("initiate_care", {"reason": "second"}, target_id="target_b")
    
    async with get_client() as client:
        response = await client.get("/decision")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["decision_id"] == id2  # Should return the latest
    assert data["action"] == "initiate_care"


@pytest.mark.asyncio
async def test_decision_with_target_no_match(isolated_db):
    """Test /decision?target_id returns no_decision when target has no decisions."""
    from emotiond.db import save_decision
    
    # Create a decision for a different target
    await save_decision("respond_warm", {"reason": "test"}, target_id="other_target")
    
    async with get_client() as client:
        response = await client.get("/decision?target_id=telegram:123")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "no_decision"
    assert data["decision"] is None


@pytest.mark.asyncio
async def test_decision_with_target_returns_latest(isolated_db):
    """Test /decision?target_id returns latest decision for that target."""
    from emotiond.db import save_decision
    
    target_id = "telegram:456"
    
    # Create multiple decisions for different targets
    id1 = await save_decision("respond_warm", {"reason": "first"}, target_id=target_id)
    id2 = await save_decision("initiate_care", {"reason": "other"}, target_id="other_target")
    id3 = await save_decision("do_nothing", {"reason": "second"}, target_id=target_id)
    
    async with get_client() as client:
        response = await client.get(f"/decision?target_id={target_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["decision_id"] == id3  # Latest for this target
    assert data["action"] == "do_nothing"
    assert data["target_id"] == target_id


@pytest.mark.asyncio
async def test_decision_with_target_isolation(isolated_db):
    """Test that /decision?target_id only returns decisions for that target."""
    from emotiond.db import save_decision
    
    # Create decisions for different targets
    await save_decision("respond_warm", {"reason": "a"}, target_id="target_a")
    await save_decision("initiate_care", {"reason": "b"}, target_id="target_b")
    await save_decision("do_nothing", {"reason": "c"}, target_id="target_a")
    
    async with get_client() as client:
        response = await client.get("/decision?target_id=target_b")
    
    data = response.json()
    assert data["status"] == "ok"
    assert data["action"] == "initiate_care"
    assert data["target_id"] == "target_b"


@pytest.mark.asyncio
async def test_decision_null_target_included_in_global(isolated_db):
    """Test that decisions with null target_id are included in global query."""
    from emotiond.db import save_decision
    
    # Create decision with null target_id (legacy)
    id1 = await save_decision("respond_warm", {"reason": "legacy"}, target_id=None)
    
    async with get_client() as client:
        response = await client.get("/decision")
    
    data = response.json()
    assert data["status"] == "ok"
    assert data["decision_id"] == id1


@pytest.mark.asyncio
async def test_decision_null_target_not_in_target_query(isolated_db):
    """Test that null target_id decisions are not returned for target query."""
    from emotiond.db import save_decision
    
    # Create decision with null target_id
    await save_decision("respond_warm", {"reason": "legacy"}, target_id=None)
    
    async with get_client() as client:
        response = await client.get("/decision?target_id=some_target")
    
    data = response.json()
    assert data["status"] == "no_decision"


@pytest.mark.asyncio
async def test_get_latest_decision_for_target(isolated_db):
    """Test get_latest_decision_for_target returns correct decision."""
    from emotiond.db import save_decision, get_latest_decision_for_target
    
    target_id = "test_target_123"
    
    # Create multiple decisions for the same target
    await save_decision("respond_warm", {"step": 1}, target_id=target_id)
    await save_decision("do_nothing", {"step": 2}, target_id=target_id)
    
    result = await get_latest_decision_for_target(target_id)
    
    assert result is not None
    assert result["action"] == "do_nothing"
    assert result["target_id"] == target_id


@pytest.mark.asyncio
async def test_get_latest_decision_for_nonexistent_target(isolated_db):
    """Test get_latest_decision_for_target returns None for unknown target."""
    from emotiond.db import get_latest_decision_for_target
    
    result = await get_latest_decision_for_target("nonexistent_target")
    
    assert result is None
