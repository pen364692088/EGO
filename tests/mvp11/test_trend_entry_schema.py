from __future__ import annotations

from scripts.export_mvp11_trend_entry import export_trend_entry


def test_trend_entry_schema_and_types():
    dashboard = {
        "cycle_store": {"entries": 842, "evicted_entries": 1, "dedupe_rate": 0.91},
    }
    profile = {
        "config": {
            "sentinel_scenarios_selected": ["focused"],
            "sentinel_rotation_mode": "weekday",
        },
        "profile": {
            "sanity_ok_coverage": 0.996,
            "distribution": {
                "cycle_persistence_score": {"p50": 0.23, "p95": 0.41},
                "dot_ratio": {"p50": 0.71, "p95": 0.85},
                "return_time_p95": {"p50": 30, "p95": 37},
                "order_invariance_score": {"p50": 0.42, "p95": 0.55},
                "order_invariance_action_multiset": {"p50": 0.60, "p95": 0.78},
                "order_invariance_goal_closure": {"p50": 0.70, "p95": 0.90},
            },
            "threshold_recommendations": {
                "sanity_ok_rate_min": 0.99,
                "return_time_p95_max": 40,
            },
        },
    }
    gate = {
        "overall_pass": True,
        "gates": [
            {"pass": True},
            {"pass": True},
            {"pass": True, "skipped": True, "observed": "SKIPPED_C3_OFF"},
        ],
    }
    effects = {
        "effects": {"P1": {}},
        "structural_assertions": [
            {"name": "open_loop lowers cycle persistence", "pass": True},
            {"name": "remove_self_state weakens self-cycle structure", "pass": True},
            {"name": "disable_homeostasis weakens closure", "pass": True},
        ],
    }

    out = export_trend_entry(
        dashboard,
        profile,
        gate,
        effects,
        commit="abc123",
        date_utc="2026-03-05",
    )

    assert out["date_utc"] == "2026-03-05"
    assert out["commit"] == "abc123"
    assert out["sentinel"]["scenario"] == "focused"
    assert out["gate"]["overall"] == "PASS"
    assert out["gate"]["gate3"] == "SKIPPED_C3_OFF"

    assert isinstance(out["metrics"]["cycle_persistence_score"]["p50"], float)
    assert isinstance(out["metrics"]["dot_ratio"]["p95"], float)
    assert isinstance(out["metrics"]["return_time_p95"], float)
    assert isinstance(out["metrics"]["sanity_ok_coverage"], float)

    assert out["effects"]["open_loop"] == "PASS"
    assert out["effects"]["remove_self_state"] == "PASS"
    assert out["effects"]["disable_homeostasis"] == "PASS"
    assert out["effects"]["disable_broadcast"] == "PASS"

    # Privacy guard: trend entry contains no raw trajectories/events body.
    serialized = str(out)
    assert "events" not in serialized
    assert "raw_text" not in serialized
    assert "trajectory" not in serialized
