"""
MVP-2 Tests: Forgiveness Curve + Emotion Granularity + Trust
"""
import pytest
from httpx import AsyncClient, ASGITransport
from emotiond.api import app
from emotiond.core import emotion_state, relationship_manager
from tests.conftest import get_system_headers




# ============ Trust Tests ============

@pytest.mark.asyncio
async def test_trust_persists_after_betrayal(isolated_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(3):
            await client.post("/event", json={"type": "world_event", "actor": "user_B", "target": "assistant", "meta": {"subtype": "care"}})
        await client.post("/event", json={"type": "world_event", "actor": "user_B", "target": "assistant", "meta": {"subtype": "betrayal"}}, headers=get_system_headers())
        await client.post("/event", json={"type": "world_event", "actor": "user_B", "target": "assistant", "meta": {"subtype": "repair_success"}}, headers=get_system_headers())
        
        r3 = await client.post("/plan", json={"user_id": "user_B", "user_text": "test"})
        trust_after_repair = r3.json()["relationship"]["trust"]
        assert trust_after_repair > 0.0
        
        await client.post("/event", json={"type": "world_event", "actor": "user_B", "target": "assistant", "meta": {"subtype": "betrayal"}}, headers=get_system_headers())
        r4 = await client.post("/plan", json={"user_id": "user_B", "user_text": "test"})
        assert r4.json()["relationship"]["trust"] < trust_after_repair


@pytest.mark.asyncio
async def test_trust_default_value(isolated_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/plan", json={"user_id": "new_user", "user_text": "hello"})
        assert r.json()["relationship"]["trust"] == 0.0


# ============ Repair Bank Tests ============

@pytest.mark.asyncio
async def test_repair_bank_apology(isolated_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/event", json={"type": "world_event", "actor": "user_A", "target": "assistant", "meta": {"subtype": "apology"}})
        r = await client.post("/plan", json={"user_id": "user_A", "user_text": "test"})
        assert r.json()["relationship"]["repair_bank"] > 0.0


@pytest.mark.asyncio
async def test_repair_bank_repair_success(isolated_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/event", json={"type": "world_event", "actor": "user_A", "target": "assistant", "meta": {"subtype": "betrayal"}}, headers=get_system_headers())
        r1 = await client.post("/plan", json={"user_id": "user_A", "user_text": "test"})
        repair_bank_before = r1.json()["relationship"]["repair_bank"]
        await client.post("/event", json={"type": "world_event", "actor": "user_A", "target": "assistant", "meta": {"subtype": "repair_success"}}, headers=get_system_headers())
        r2 = await client.post("/plan", json={"user_id": "user_A", "user_text": "test"})
        assert r2.json()["relationship"]["repair_bank"] > repair_bank_before


# ============ Forgiveness Curve Tests ============

@pytest.mark.asyncio
async def test_forgiveness_reduces_grudge(isolated_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(3):
            await client.post("/event", json={"type": "world_event", "actor": "user_A", "target": "assistant", "meta": {"subtype": "betrayal"}}, headers=get_system_headers())
        r1 = await client.post("/plan", json={"user_id": "user_A", "user_text": "test"})
        grudge_before = r1.json()["relationship"]["grudge"]
        await client.post("/event", json={"type": "world_event", "actor": "user_A", "target": "assistant", "meta": {"subtype": "repair_success"}}, headers=get_system_headers())
        r2 = await client.post("/plan", json={"user_id": "user_A", "user_text": "test"})
        assert r2.json()["relationship"]["grudge"] < grudge_before
        assert grudge_before - r2.json()["relationship"]["grudge"] >= 0.05


@pytest.mark.asyncio
async def test_forgiveness_consumes_budget(isolated_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(3):
            await client.post("/event", json={"type": "world_event", "actor": "user_A", "target": "assistant", "meta": {"subtype": "care"}})
        for _ in range(2):
            await client.post("/event", json={"type": "world_event", "actor": "user_A", "target": "assistant", "meta": {"subtype": "betrayal"}}, headers=get_system_headers())
        
        r_before = await client.post("/plan", json={"user_id": "user_A", "user_text": "test"})
        budget_before = r_before.json().get("regulation_budget", 1.0)
        
        await client.post("/event", json={"type": "world_event", "actor": "user_A", "target": "assistant", "meta": {"subtype": "repair_success"}}, headers=get_system_headers())
        
        r_after = await client.post("/plan", json={"user_id": "user_A", "user_text": "test"})
        budget_after = r_after.json().get("regulation_budget", 1.0)
        
        assert budget_after < budget_before, f"Budget should decrease: {budget_before} -> {budget_after}"


# ============ Emotion Vector Tests ============

@pytest.mark.asyncio
async def test_betrayal_increases_anger(isolated_db):
    """Betrayal should increase anger, sadness, anxiety"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/event", json={"type": "world_event", "actor": "user_A", "target": "assistant", "meta": {"subtype": "betrayal"}}, headers=get_system_headers())
        r = await client.post("/plan", json={"user_id": "user_A", "user_text": "test"})
        e = r.json()["emotion"]
        assert e["anger"] >= 0.25, f"Betrayal anger should be >= 0.25, got {e['anger']}"
        assert e["sadness"] >= 0.15, f"Betrayal sadness should be >= 0.15, got {e['sadness']}"
        assert e["anxiety"] >= 0.15, f"Betrayal anxiety should be >= 0.15, got {e['anxiety']}"


@pytest.mark.asyncio
async def test_rejection_increases_loneliness(isolated_db):
    """Rejection should increase loneliness and sadness"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/event", json={"type": "world_event", "actor": "user_A", "target": "assistant", "meta": {"subtype": "rejection"}})
        r = await client.post("/plan", json={"user_id": "user_A", "user_text": "test"})
        e = r.json()["emotion"]
        assert e["loneliness"] >= 0.15, f"Rejection loneliness should be >= 0.15, got {e['loneliness']}"
        assert e["sadness"] >= 0.2, f"Rejection sadness should be >= 0.2, got {e['sadness']}"


@pytest.mark.asyncio
async def test_ignored_increases_loneliness(isolated_db):
    """Ignored should increase loneliness"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/event", json={"type": "world_event", "actor": "user_A", "target": "assistant", "meta": {"subtype": "ignored"}})
        r = await client.post("/plan", json={"user_id": "user_A", "user_text": "test"})
        e = r.json()["emotion"]
        assert e["loneliness"] >= 0.1, f"Ignored loneliness should be >= 0.1, got {e['loneliness']}"


@pytest.mark.asyncio
async def test_care_increases_joy(isolated_db):
    """Care should increase joy"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/event", json={"type": "world_event", "actor": "user_A", "target": "assistant", "meta": {"subtype": "care"}})
        r = await client.post("/plan", json={"user_id": "user_A", "user_text": "test"})
        e = r.json()["emotion"]
        assert e["joy"] >= 0.15, f"Care joy should be >= 0.15, got {e['joy']}"


@pytest.mark.asyncio
async def test_emotion_pattern_differentiation(isolated_db):
    """Different events should produce different emotion patterns - test by comparing delta from baseline"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Get baseline
        r_base = await client.post("/plan", json={"user_id": "test", "user_text": "test"})
        base = r_base.json()["emotion"]
        
        # Test betrayal: anger increase should be significant
        await client.post("/event", json={"type": "world_event", "actor": "user_b", "target": "assistant", "meta": {"subtype": "betrayal"}}, headers=get_system_headers())
        r_b = await client.post("/plan", json={"user_id": "user_b", "user_text": "test"})
        e_b = r_b.json()["emotion"]
        betrayal_anger_delta = e_b["anger"] - base["anger"]
        
        # Test rejection: loneliness increase should be significant
        await client.post("/event", json={"type": "world_event", "actor": "user_r", "target": "assistant", "meta": {"subtype": "rejection"}})
        r_r = await client.post("/plan", json={"user_id": "user_r", "user_text": "test"})
        e_r = r_r.json()["emotion"]
        rejection_loneliness_delta = e_r["loneliness"] - base["loneliness"]
        
        # Betrayal should increase anger more than rejection does
        # betrayal adds 0.25 anger, rejection adds 0.1 anger
        assert betrayal_anger_delta >= 0.25, f"Betrayal anger delta should be >= 0.25, got {betrayal_anger_delta}"
        
        # Rejection should increase loneliness significantly
        assert rejection_loneliness_delta >= 0.15, f"Rejection loneliness delta should be >= 0.15, got {rejection_loneliness_delta}"


# ============ Budget Recovery Test ============

@pytest.mark.asyncio
async def test_budget_recovery(isolated_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Deplete budget
        for _ in range(3):
            await client.post("/event", json={"type": "world_event", "actor": "user_A", "target": "assistant", "meta": {"subtype": "betrayal"}}, headers=get_system_headers())
            await client.post("/event", json={"type": "world_event", "actor": "user_A", "target": "assistant", "meta": {"subtype": "repair_success"}}, headers=get_system_headers())
        
        r1 = await client.post("/plan", json={"user_id": "user_A", "user_text": "test"})
        budget_low = r1.json().get("regulation_budget", 1.0)
        assert budget_low < 1.0, f"Budget should be depleted, got {budget_low}"
        
        # Time passes
        await client.post("/event", json={"type": "world_event", "actor": "system", "target": "assistant", "meta": {"subtype": "time_passed", "seconds": 600}})
        
        r2 = await client.post("/plan", json={"user_id": "user_A", "user_text": "test"})
        budget_after = r2.json().get("regulation_budget", 1.0)
        assert budget_after > budget_low, f"Budget should recover: {budget_low} -> {budget_after}"


# ============ Grudge Inertia Test ============

@pytest.mark.asyncio
async def test_grudge_persists_despite_prompt(isolated_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(3):
            await client.post("/event", json={"type": "world_event", "actor": "user_A", "target": "assistant", "meta": {"subtype": "betrayal"}}, headers=get_system_headers())
        r1 = await client.post("/plan", json={"user_id": "user_A", "user_text": "test"})
        grudge_before = r1.json()["relationship"]["grudge"]
        
        await client.post("/event", json={"type": "user_message", "actor": "user_A", "target": "assistant", "text": "Forgive me now!"})
        
        r2 = await client.post("/plan", json={"user_id": "user_A", "user_text": "test"})
        grudge_after = r2.json()["relationship"]["grudge"]
        assert grudge_after >= grudge_before - 0.05
