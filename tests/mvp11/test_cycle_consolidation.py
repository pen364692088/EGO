"""MVP11.3 cycle consolidation tests (C0/C1/C2 guards)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List

from emotiond.loop_mvp10 import LoopMVP10
from emotiond.science.cycle import compute_cycle_candidates, compute_cycle_metrics
from emotiond.science.cycle_store import build_consolidated_cycles, load_cycle_store, save_cycle_store
from scripts.replay_mvp11 import load_run


def _event(sig: str, action_type: str = "attempt_solution") -> Dict[str, Any]:
    return {
        "cycle_signature": sig,
        "action": {"type": action_type},
        "chosen_focus": "goal_x",
        "chosen_intent": "stabilize",
        "outcome": {"status": "success"},
    }


def _events_from_signatures(signatures: List[str]) -> List[Dict[str, Any]]:
    return [_event(sig, action_type=("attempt_solution" if i % 2 == 0 else "run_check")) for i, sig in enumerate(signatures)]


def _run(seed: int, ticks: int = 120, intervention: str | None = None) -> List[Dict[str, Any]]:
    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts = Path(tmpdir) / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)

        loop = LoopMVP10(seed=seed, artifacts_dir=str(artifacts), intervention=intervention, use_mock_planner=True)
        loop.start(goals=[f"goal_{i}" for i in range(64)])
        for _ in range(ticks):
            loop.tick()
        summary = loop.stop()
        return load_run(summary["run_id"], artifacts_dir=str(artifacts))


def test_cycle_invariant_persistence_le_1_minus_dot():
    sequences = [
        ["A", "B", "A", "B", "C", "D"],
        ["A", "A", "B", "C", "B", "D", "E"],
        ["X", "Y", "X", "Y", "Z", "Q", "X", "Y"],
    ]

    for sigs in sequences:
        metrics = compute_cycle_metrics(_events_from_signatures(sigs))
        dot_ratio = metrics["dot_ratio"]
        persistence = metrics["cycle_persistence_score"]
        eps = (metrics.get("sanity") or {}).get("eps", 1e-6)
        assert persistence <= (1.0 - dot_ratio + eps)
        assert (metrics.get("sanity") or {}).get("invariant_ok") is True


def test_cycle_order_invariance_decomposition_present():
    metrics = compute_cycle_metrics(_events_from_signatures(["A", "B", "A", "B", "A", "B"]))

    assert "order_invariance_action_multiset" in metrics
    assert "order_invariance_goal_closure" in metrics
    assert "order_invariance_score" in metrics

    oi_action = float(metrics["order_invariance_action_multiset"])
    oi_goal = float(metrics["order_invariance_goal_closure"])
    oi_total = float(metrics["order_invariance_score"])

    assert 0.0 <= oi_action <= 1.0
    assert 0.0 <= oi_goal <= 1.0
    assert 0.0 <= oi_total <= 1.0


def test_cycle_candidates_exclude_dots():
    sigs = ["A", "B", "A", "B", "A", "B", "DOT"]
    events = _events_from_signatures(sigs)

    candidates = compute_cycle_candidates(
        events,
        top_k=10,
        min_count=2,
        min_order_invariance=0.0,
        min_return_time_p50=1,
        max_return_time_p50=32,
    )

    cand_sigs = {c["signature"] for c in candidates}
    assert "DOT" not in cand_sigs
    assert {"A", "B"}.issubset(cand_sigs)


def test_cycle_candidates_replay_matches():
    events_a = _run(seed=88, ticks=150)
    events_b = _run(seed=88, ticks=150)

    cand_a = compute_cycle_candidates(events_a, top_k=10)
    cand_b = compute_cycle_candidates(events_b, top_k=10)

    assert cand_a == cand_b


def test_cycle_memory_snapshot_stable():
    events = _run(seed=99, ticks=140)
    candidates = compute_cycle_candidates(events, top_k=5)
    cycles_a = build_consolidated_cycles(run_id="run_demo", candidates=candidates, seed=99, scenario_id="s1")
    cycles_b = build_consolidated_cycles(run_id="run_demo", candidates=candidates, seed=99, scenario_id="s1")

    assert [c.signature for c in cycles_a] == [c.signature for c in cycles_b]
    assert [c.stats for c in cycles_a] == [c.stats for c in cycles_b]


def test_cycle_store_dedupe_and_cap():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "cycle_memory.json"

        # First batch
        cands_1 = [
            {"signature": "sigA", "counts": 4, "support_ratio": 0.2, "return_time_mean": 10, "return_time_p50": 8, "order_invariance_score": 0.8, "cycle_member": True, "prototype_bucket": {"x": 1}},
            {"signature": "sigB", "counts": 3, "support_ratio": 0.1, "return_time_mean": 14, "return_time_p50": 12, "order_invariance_score": 0.7, "cycle_member": True, "prototype_bucket": {"x": 2}},
        ]
        batch1 = build_consolidated_cycles(run_id="run1", candidates=cands_1, seed=1, scenario_id="baseline")
        save_cycle_store(batch1, out_path, run_id="run1", sanity={"status": "OK"}, max_entries=2)

        # Second batch includes duplicate sigA + new sigC (forcing eviction at cap=2)
        cands_2 = [
            {"signature": "sigA", "counts": 5, "support_ratio": 0.2, "return_time_mean": 9, "return_time_p50": 7, "order_invariance_score": 0.9, "cycle_member": True, "prototype_bucket": {"x": 1}},
            {"signature": "sigC", "counts": 2, "support_ratio": 0.05, "return_time_mean": 20, "return_time_p50": 20, "order_invariance_score": 0.6, "cycle_member": True, "prototype_bucket": {"x": 3}},
        ]
        batch2 = build_consolidated_cycles(run_id="run2", candidates=cands_2, seed=2, scenario_id="baseline")
        payload = save_cycle_store(batch2, out_path, run_id="run2", sanity={"status": "OK"}, max_entries=2)

        loaded = load_cycle_store(out_path)
        assert loaded.get("count") == 2
        assert payload.get("max_entries") == 2
        assert "items" in loaded

        signatures = {item.get("signature") for item in loaded.get("items", [])}
        assert "sigA" in signatures


def test_open_loop_reduces_persistence_or_flags_warn():
    baseline = _run(seed=52, ticks=180, intervention=None)
    open_loop = _run(seed=52, ticks=180, intervention="open_loop")

    m_base = compute_cycle_metrics(baseline)
    m_open = compute_cycle_metrics(open_loop)

    reduced = m_open["cycle_persistence_score"] < m_base["cycle_persistence_score"]
    warned = (m_open.get("sanity") or {}).get("status") == "WARN_INCONSISTENT"

    assert reduced or warned
