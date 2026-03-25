"""Tests for MVP11.2 cycle-closure evidence layer."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List

from emotiond.loop_mvp10 import LoopMVP10
from emotiond.science.cycle import compute_cycle_metrics
from scripts.replay_mvp11 import load_run, replay_run


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


def _run_with_replay(seed: int, ticks: int = 120) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts = Path(tmpdir) / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)

        loop = LoopMVP10(seed=seed, artifacts_dir=str(artifacts), use_mock_planner=True)
        loop.start(goals=[f"goal_{i}" for i in range(64)])
        for _ in range(ticks):
            loop.tick()
        summary = loop.stop()

        replay = replay_run(summary["run_id"], artifacts_dir=str(artifacts))
        return replay


def test_cycle_signature_deterministic_same_seed():
    events_a = _run(seed=42, ticks=160)
    events_b = _run(seed=42, ticks=160)

    sig_a = [e.get("cycle_signature") for e in events_a]
    sig_b = [e.get("cycle_signature") for e in events_b]

    assert sig_a == sig_b


def test_cycle_signature_trace_replay_matches():
    replay = _run_with_replay(seed=42, ticks=140)
    assert "error" not in replay
    assert replay.get("hash_match_rate", 0.0) >= 0.95


def test_cycle_metrics_drop_in_open_loop():
    baseline = _run(seed=52, ticks=180, intervention=None)
    open_loop = _run(seed=52, ticks=180, intervention="open_loop")

    m_base = compute_cycle_metrics(baseline)
    m_open = compute_cycle_metrics(open_loop)

    assert m_open["dot_ratio"] > m_base["dot_ratio"]


def test_cycle_metrics_change_in_remove_self_state():
    baseline = _run(seed=53, ticks=180, intervention=None)
    removed = _run(seed=53, ticks=180, intervention="remove_self_state")

    m_base = compute_cycle_metrics(baseline)
    m_removed = compute_cycle_metrics(removed)

    # Structural shift is required; direction can vary by scenario.
    delta = abs(m_removed["order_invariance_score"] - m_base["order_invariance_score"])
    assert delta > 0.01


def test_cycle_metrics_change_in_disable_homeostasis():
    baseline = _run(seed=54, ticks=180, intervention=None)
    disabled = _run(seed=54, ticks=180, intervention="disable_homeostasis")

    m_base = compute_cycle_metrics(baseline)
    m_disabled = compute_cycle_metrics(disabled)

    assert m_disabled["return_time_mean"] != m_base["return_time_mean"]

def test_event_contains_cycle_fields():
    events = _run(seed=61, ticks=20)
    assert events
    e0 = events[0]
    assert "cycle_signature" in e0
    assert "cycle_bucket" in e0
