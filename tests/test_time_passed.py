"""Tests for time_passed event and drift behavior"""
import pytest
from httpx import AsyncClient, ASGITransport
from emotiond.api import app


@pytest.mark.asyncio
async def test_time_passed_advances_drift_core_enabled(isolated_db):
    """Core-enabled: time_passed should cause emotional drift"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Establish positive state
        await client.post("/event", json={
            "type": "world_event",
            "actor": "user_A",
            "target": "assistant",
            "meta": {"subtype": "care"}
        })
        
        r1 = await client.post("/plan", json={"user_id": "user_A", "user_text": "test"})
        initial_valence = r1.json()["emotion"]["valence"]
        
        # Pass significant time
        await client.post("/event", json={
            "type": "world_event",
            "actor": "system",
            "target": "assistant",
            "meta": {"subtype": "time_passed", "seconds": 300}
        })
        
        r2 = await client.post("/plan", json={"user_id": "user_A", "user_text": "test"})
        final_valence = r2.json()["emotion"]["valence"]
        
        # Valence should drift toward neutral (decay)
        assert abs(final_valence - initial_valence) > 0.01


@pytest.mark.asyncio
async def test_core_disabled_remains_neutral(isolated_db, monkeypatch):
    """Core-disabled: identical events should produce no relationship dynamics"""
    # Set environment variable for core disabled
    monkeypatch.setenv("EMOTIOND_DISABLE_CORE", "1")
    
    # Need to reimport config to pick up the new env var
    import importlib
    from emotiond import config, core
    importlib.reload(config)
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Send care events
        await client.post("/event", json={
            "type": "world_event",
            "actor": "user_Z",
            "target": "assistant",
            "meta": {"subtype": "care"}
        })
        
        response = await client.post("/plan", json={"user_id": "user_Z", "user_text": "test"})
        relationship = response.json()["relationship"]
        
        # Relationship should remain neutral (bond: 0, grudge: 0)
        assert relationship["bond"] == 0.0
        assert relationship["grudge"] == 0.0
        
        # Send betrayal events
        await client.post("/event", json={
            "type": "world_event",
            "actor": "user_Z",
            "target": "assistant",
            "meta": {"subtype": "betrayal", "source": "system"}
        })
        
        response = await client.post("/plan", json={"user_id": "user_Z", "user_text": "test"})
        relationship = response.json()["relationship"]
        
        # Relationship should remain neutral
        assert relationship["bond"] == 0.0
        assert relationship["grudge"] == 0.0
    
    # Reset environment variable
    monkeypatch.delenv("EMOTIOND_DISABLE_CORE")


@pytest.mark.asyncio
async def test_time_passed_large_interval(isolated_db):
    """Large time_passed intervals should cause significant drift"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Establish positive state
        await client.post("/event", json={
            "type": "world_event",
            "actor": "user_B",
            "target": "assistant",
            "meta": {"subtype": "care"}
        })
        
        r1 = await client.post("/plan", json={"user_id": "user_B", "user_text": "test"})
        initial_valence = r1.json()["emotion"]["valence"]
        
        # Pass large time interval (1 hour)
        await client.post("/event", json={
            "type": "world_event",
            "actor": "system",
            "target": "assistant",
            "meta": {"subtype": "time_passed", "seconds": 3600}
        })
        
        r2 = await client.post("/plan", json={"user_id": "user_B", "user_text": "test"})
        final_valence = r2.json()["emotion"]["valence"]
        
        # Valence should drift significantly toward neutral (0.15 -> 0.0)
        assert abs(final_valence - initial_valence) > 0.1
