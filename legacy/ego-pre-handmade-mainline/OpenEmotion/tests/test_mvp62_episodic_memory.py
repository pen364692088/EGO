import pytest

from emotiond.db import add_event
from emotiond.episodic_memory import EpisodicMemoryManager


async def _seed_turns(target: str, n: int):
    for i in range(n):
        await add_event({
            "type": "user_message",
            "actor": target,
            "target": "assistant",
            "text": f"turn {i} about project timeline and preference for concise output",
            "meta": {"target_id": target},
        })


@pytest.mark.asyncio
async def test_init_tables(isolated_db):
    mgr = EpisodicMemoryManager()
    await mgr.init_db()
    out = await mgr.retrieve("t", "x", 3)
    assert out["top_k"] == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("n", [2, 3, 4, 5, 6, 7, 8, 9, 10, 11])
async def test_summary_triggers_by_turn_count(isolated_db, n):
    mgr = EpisodicMemoryManager(turns_per_episode=n)
    await mgr.init_db()
    for i in range(n - 1):
        ret = await mgr.observe_event({"type": "user_message", "actor": "u1", "target": "assistant", "text": f"msg {i}", "meta": {"target_id": "u1"}})
        assert ret is None
    last = await mgr.observe_event({"type": "user_message", "actor": "u1", "target": "assistant", "text": "final question?", "meta": {"target_id": "u1"}})
    assert last is not None
    assert 3 <= last["stored"] <= 5


@pytest.mark.asyncio
@pytest.mark.parametrize("subtype", ["episode_end", "session_wrap", "conversation_end", "interaction_outcome"])
async def test_summary_triggers_on_episode_end(isolated_db, subtype):
    mgr = EpisodicMemoryManager(turns_per_episode=99)
    await mgr.init_db()
    await _seed_turns("u2", 3)
    meta = {"target_id": "u2", "subtype": subtype}
    if subtype == "interaction_outcome":
        meta["result"] = "done"
    out = await mgr.observe_event({"type": "world_event", "actor": "system", "target": "assistant", "text": None, "meta": meta})
    assert out and out["stored"] >= 3


@pytest.mark.asyncio
async def test_summary_item_shape_and_count(isolated_db):
    mgr = EpisodicMemoryManager(turns_per_episode=3)
    await mgr.init_db()
    for t in ["I prefer short answers", "Can you clarify scope?", "great thanks"]:
        await mgr.observe_event({"type": "user_message", "actor": "u3", "target": "assistant", "text": t, "meta": {"target_id": "u3"}})
    out = await mgr.retrieve("u3", "scope clarify", 3)
    assert len(out["memories"]) == 3
    for m in out["memories"]:
        assert set(["memory_id", "q", "a", "kind", "utility", "safe_effects", "no_high_impact_trigger"]).issubset(m.keys())


@pytest.mark.asyncio
@pytest.mark.parametrize("query", [
    "scope", "clarify", "preference", "timeline", "neutral", "thanks", "angry", "what next", "concise", "project"
])
async def test_retrieval_determinism(isolated_db, query):
    mgr = EpisodicMemoryManager(turns_per_episode=3)
    await mgr.init_db()
    for t in ["I prefer concise output", "Can you clarify timeline?", "thanks"]:
        await mgr.observe_event({"type": "user_message", "actor": "u4", "target": "assistant", "text": t, "meta": {"target_id": "u4"}})
    a = await mgr.retrieve("u4", query, 3)
    b = await mgr.retrieve("u4", query, 3)
    assert [x["memory_id"] for x in a["memories"]] == [x["memory_id"] for x in b["memories"]]


@pytest.mark.asyncio
@pytest.mark.parametrize("k", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
async def test_topk_stability_and_bounds(isolated_db, k):
    mgr = EpisodicMemoryManager(turns_per_episode=3)
    await mgr.init_db()
    for t in ["I like concise responses", "question about architecture?", "let us continue same topic"]:
        await mgr.observe_event({"type": "user_message", "actor": "u5", "target": "assistant", "text": t, "meta": {"target_id": "u5"}})
    out = await mgr.retrieve("u5", "architecture concise", k)
    assert len(out["memories"]) <= k


@pytest.mark.asyncio
@pytest.mark.parametrize("target_a,target_b", [("A", "B"), ("alice", "bob"), ("t1", "t2"), ("x", "y"), ("left", "right")])
async def test_cross_target_isolation(isolated_db, target_a, target_b):
    mgr = EpisodicMemoryManager(turns_per_episode=3)
    await mgr.init_db()
    for _ in range(3):
        await mgr.observe_event({"type": "user_message", "actor": target_a, "target": "assistant", "text": "alpha only", "meta": {"target_id": target_a}})
    for _ in range(3):
        await mgr.observe_event({"type": "user_message", "actor": target_b, "target": "assistant", "text": "beta only", "meta": {"target_id": target_b}})
    a = await mgr.retrieve(target_a, "alpha", 3)
    b = await mgr.retrieve(target_b, "beta", 3)
    a_ids = {m["memory_id"] for m in a["memories"]}
    b_ids = {m["memory_id"] for m in b["memories"]}
    assert len(a_ids) > 0 and len(b_ids) > 0
    assert a_ids.isdisjoint(b_ids)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_utility", ["betrayal", "attack", "repair_success", "high_impact", "unsafe"])
async def test_unsafe_utility_coerced(isolated_db, bad_utility):
    mgr = EpisodicMemoryManager()
    await mgr.init_db()
    eid = await mgr._store_episode("u6", "manual")
    await mgr._store_items(eid, "u6", [{"q": "q", "a": "a", "kind": "k", "utility": bad_utility, "score": 1.0}])
    out = await mgr.retrieve("u6", "q", 1)
    assert out["memories"][0]["utility"] == "clarify"


@pytest.mark.asyncio
async def test_memory_cannot_directly_trigger_high_impact(isolated_db):
    mgr = EpisodicMemoryManager(turns_per_episode=3)
    await mgr.init_db()
    for t in ["I am upset", "This is bad", "Can you explain?"]:
        await mgr.observe_event({"type": "user_message", "actor": "u7", "target": "assistant", "text": t, "meta": {"target_id": "u7"}})
    out = await mgr.retrieve("u7", "upset", 3)
    for m in out["memories"]:
        assert m["no_high_impact_trigger"] is True
        assert "betrayal" not in m["safe_effects"]


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["", "   ", "none", "unknown", "q", "a", "z", "scope?", "next", "finish"]) 
async def test_telemetry_fields_present(isolated_db, query):
    mgr = EpisodicMemoryManager(turns_per_episode=3)
    await mgr.init_db()
    for t in ["I like concise output", "Could you clarify deadline?", "thanks"]:
        await mgr.observe_event({"type": "user_message", "actor": "u8", "target": "assistant", "text": t, "meta": {"target_id": "u8"}})
    out = await mgr.retrieve("u8", query, 3)
    tel = out["telemetry"]
    assert "memory_hit_rate" in tel
    assert "injection_budget_usage_bytes_avg" in tel
    assert "memory_utility_proxy" in tel


@pytest.mark.asyncio
@pytest.mark.parametrize("seed", list(range(1, 11)))
async def test_stable_order_with_equal_scores(isolated_db, seed):
    mgr = EpisodicMemoryManager()
    await mgr.init_db()
    eid = await mgr._store_episode("u9", "manual")
    items = [{"q": f"same {i}", "a": "token", "kind": "k", "utility": "clarify", "score": 1.0} for i in range(5)]
    await mgr._store_items(eid, "u9", items)
    a = await mgr.retrieve("u9", "none", 3)
    b = await mgr.retrieve("u9", "none", 3)
    assert [m["memory_id"] for m in a["memories"]] == [m["memory_id"] for m in b["memories"]]
