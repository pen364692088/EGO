"""Tests for world_event subtypes driving relationship changes"""
import pytest
from httpx import AsyncClient, ASGITransport
from tests.conftest import get_system_headers
from emotiond.api import app


@pytest.mark.asyncio
async def test_care_increases_bond(isolated_db):
    """Care events should increase bond"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/event", json={
            "type": "world_event",
            "actor": "user_A",
            "target": "assistant",
            "meta": {"subtype": "care"}
        })
        
        response = await client.post("/plan", json={
            "user_id": "user_A",
            "user_text": "test"
        })
        
        assert response.json()["relationship"]["bond"] > 0


@pytest.mark.asyncio
async def test_betrayal_increases_grudge(isolated_db):
    """Betrayal events should increase grudge"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/event", json={
            "type": "world_event",
            "actor": "user_B",
            "target": "assistant",
            "meta": {"subtype": "betrayal"}
        }, headers=get_system_headers())
        
        response = await client.post("/plan", json={
            "user_id": "user_B",
            "user_text": "test"
        })
        
        assert response.json()["relationship"]["grudge"] > 0


@pytest.mark.asyncio
async def test_rejection_decreases_bond(isolated_db):
    """Rejection should decrease bond"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First establish some bond
        await client.post("/event", json={
            "type": "world_event",
            "actor": "user_C",
            "target": "assistant",
            "meta": {"subtype": "care"}
        })
        
        # Then rejection
        await client.post("/event", json={
            "type": "world_event",
            "actor": "user_C",
            "target": "assistant",
            "meta": {"subtype": "rejection"}
        })
        
        response = await client.post("/plan", json={
            "user_id": "user_C",
            "user_text": "test"
        })
        
        # Grudge should exist
        assert response.json()["relationship"]["grudge"] > 0


@pytest.mark.asyncio
async def test_repair_success_reduces_grudge(isolated_db):
    """Repair success should reduce grudge"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Build grudge
        await client.post("/event", json={
            "type": "world_event",
            "actor": "user_D",
            "target": "assistant",
            "meta": {"subtype": "betrayal"}
        }, headers=get_system_headers())
        
        # Check baseline grudge
        r1 = await client.post("/plan", json={"user_id": "user_D", "user_text": "test"})
        baseline_grudge = r1.json()["relationship"]["grudge"]
        
        # Repair
        await client.post("/event", json={
            "type": "world_event",
            "actor": "user_D",
            "target": "assistant",
            "meta": {"subtype": "repair_success"}
        }, headers=get_system_headers())
        
        r2 = await client.post("/plan", json={"user_id": "user_D", "user_text": "test"})
        after_grudge = r2.json()["relationship"]["grudge"]
        
        assert after_grudge < baseline_grudge
