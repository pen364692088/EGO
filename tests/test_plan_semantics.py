"""Tests for /plan focus_target defaulting and relationship matching"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from tests.conftest import get_system_headers
from emotiond.api import app


@pytest.mark.asyncio
async def test_plan_focus_target_defaults_to_user_id(isolated_db):
    """If no focus_target provided, relationship should be for user_id"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First, build relationship with user_X via events
        response = await client.post("/event", json={
            "type": "world_event",
            "actor": "user_X",
            "target": "assistant",
            "meta": {"subtype": "care"}
        })
        assert response.status_code == 200
        
        # Request plan for user_X without focus_target
        response = await client.post("/plan", json={
            "user_id": "user_X",
            "user_text": "Hello"
        })
        
        data = response.json()
        assert data["focus_target"] == "user_X"
        assert data["relationship"]["bond"] > 0


@pytest.mark.asyncio
async def test_plan_explicit_focus_target(isolated_db):
    """If focus_target provided, relationship should be for that target"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Build relationship with user_Y
        await client.post("/event", json={
            "type": "world_event",
            "actor": "user_Y",
            "target": "assistant",
            "meta": {"subtype": "betrayal"}
        }, headers=get_system_headers())
        
        # Request plan for user_X but with focus_target=user_Y
        response = await client.post("/plan", json={
            "user_id": "user_X",
            "user_text": "Hello",
            "focus_target": "user_Y"
        })
        
        data = response.json()
        assert data["focus_target"] == "user_Y"
        assert data["relationship"]["grudge"] > 0


@pytest.mark.asyncio
async def test_plan_dynamic_target_strings(isolated_db):
    """Dynamic target strings (not just A/B/C) must work"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        arbitrary_id = "user_12345_arbitrary_string"
        
        await client.post("/event", json={
            "type": "world_event",
            "actor": arbitrary_id,
            "target": "assistant",
            "meta": {"subtype": "care"}
        })
        
        response = await client.post("/plan", json={
            "user_id": arbitrary_id,
            "user_text": "Test"
        })
        
        data = response.json()
        assert data["focus_target"] == arbitrary_id
        assert data["relationship"]["bond"] > 0
