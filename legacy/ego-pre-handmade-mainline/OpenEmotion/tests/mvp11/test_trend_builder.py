from __future__ import annotations

from scripts.build_mvp11_trend_7d import build_trend, render_markdown


def _entry(i: int) -> dict:
    # 7 days rising persistence, falling dot ratio
    return {
        "date_utc": f"2026-03-0{i+1}",
        "commit": f"c{i}",
        "sentinel": {"scenario": ["baseline", "focused", "wide"][i % 3], "rotation_mode": "weekday"},
        "gate": {
            "overall": "PASS" if i != 2 else "FAIL",
            "gate1": "PASS",
            "gate2": "PASS" if i != 2 else "FAIL",
            "gate3": "SKIPPED_C3_OFF",
        },
        "metrics": {
            "cycle_persistence_score": {"p50": 0.20 + 0.02 * i, "p95": 0.35 + 0.02 * i},
            "dot_ratio": {"p50": 0.80 - 0.03 * i, "p95": 0.90 - 0.03 * i},
            "return_time_p95": 40 - i,
            "order_invariance": {
                "score": {"p50": 0.30 + 0.01 * i, "p95": 0.45 + 0.01 * i},
                "action_multiset": {"p50": 0.50 + 0.01 * i, "p95": 0.65 + 0.01 * i},
                "goal_closure": {"p50": 0.55 + 0.01 * i, "p95": 0.70 + 0.01 * i},
            },
            "sanity_ok_coverage": 0.995 - 0.0005 * i,
        },
        "cycle_store": {"entries": 100 + i, "evicted_entries": i, "dedupe_rate": 0.9},
        "effects": {
            "open_loop": "PASS",
            "remove_self_state": "PASS",
            "disable_homeostasis": "PASS",
            "disable_broadcast": "PASS",
        },
        "threshold_recommendations": {
            "sanity_ok_rate_min": 0.99,
            "cycle_persistence_score_range": {"min": 0.18, "max": 0.60},
            "dot_ratio_range": {"min": 0.3, "max": 0.9},
            "return_time_p95_max": 60,
            "governor_block_rate_max": 0.1,
            "homeostasis_drift_mean_max": 0.2,
        },
    }


def test_trend_builder_outputs_stable_shapes():
    entries = [_entry(i) for i in range(7)]
    trend = build_trend(entries, alert_threshold=0.2)

    assert trend["window_days"] == 7
    assert len(trend["entries"]) == 7

    sparks = trend["sparklines"]
    assert len(sparks["cycle_persistence_p50"]) == 7
    assert len(sparks["dot_ratio_p50"]) == 7
    assert len(sparks["sanity_ok_coverage"]) == 7

    slopes = trend["slopes"]
    assert isinstance(slopes["cycle_persistence_p50"], float)
    assert isinstance(slopes["dot_ratio_p50"], float)

    assert isinstance(trend["drift"]["latest_score"], float)
    assert isinstance(trend["drift"]["potential_drift"], bool)


def test_trend_markdown_contains_heatmap_and_alert_section():
    entries = [_entry(i) for i in range(7)]
    trend = build_trend(entries, alert_threshold=0.2)
    md = render_markdown(trend)

    assert "## 7-Day Trend" in md
    assert "Date | G1 | G2 | G3 | Overall | Sentinel | Drift" in md
    assert "### Sparklines" in md
    assert "### Drift Alert" in md


def test_scenario_grouping_correctness():
    """T1: Scenario grouping correctness - verify counts and null handling."""
    entries = [_entry(i) for i in range(7)]
    trend = build_trend(entries, alert_threshold=0.2)
    
    # scenario_counts: baseline=3 (i=0,3,6), focused=2 (i=1,4), wide=2 (i=2,5)
    # Actually: i%3 => 0->baseline, 1->focused, 2->wide, 3->baseline, 4->focused, 5->wide, 6->baseline
    # So: baseline=3, focused=2, wide=2
    assert trend["scenario_counts"]["baseline"] == 3
    assert trend["scenario_counts"]["focused"] == 2
    assert trend["scenario_counts"]["wide"] == 2
    
    # Check that scenario_series[scenario][metric] only has non-null on matching dates
    # baseline appears on 2026-03-01 (i=0), 2026-03-04 (i=3), 2026-03-07 (i=6)
    baseline_series = trend["scenario_series"]["baseline"]
    dates = trend["dates"]
    
    # Find indices for dates where baseline should appear
    baseline_dates = {"2026-03-01", "2026-03-04", "2026-03-07"}
    
    for idx, date in enumerate(dates):
        if date in baseline_dates:
            # Non-null expected
            assert baseline_series["persistence_p50"][idx] is not None, f"Expected non-null for baseline on {date}"
        else:
            # Null expected for missing dates
            assert baseline_series["persistence_p50"][idx] is None, f"Expected null for baseline on {date}, got {baseline_series['persistence_p50'][idx]}"
    
    # Verify missing values are null, not 0
    # focused appears on 2026-03-02 (i=1), 2026-03-05 (i=4)
    focused_series = trend["scenario_series"]["focused"]
    focused_dates = {"2026-03-02", "2026-03-05"}
    
    for idx, date in enumerate(dates):
        if date not in focused_dates:
            assert focused_series["persistence_p50"][idx] is None, f"Expected null for focused on {date}"


def test_sparkline_placeholder_stability():
    """T2: Sparkline placeholder stability - verify · for missing data."""
    entries = [_entry(i) for i in range(7)]
    trend = build_trend(entries, alert_threshold=0.2)
    
    # Get scenario sparklines
    for scenario in ["baseline", "focused", "wide"]:
        series = trend["scenario_series"][scenario]
        spark = series["sparklines"]["persistence_p50"]
        
        # Sparkline length must match date axis
        assert len(spark) == len(trend["dates"]), f"Sparkline length mismatch for {scenario}"
        
        # Sparkline must contain · for missing dates
        # baseline has 3 dates, missing 4 -> should have 4 ·'s
        # focused has 2 dates, missing 5 -> should have 5 ·'s
        # wide has 2 dates, missing 5 -> should have 5 ·'s
        assert "·" in spark, f"Expected · placeholder in sparkline for {scenario}"
    
    # Verify MD output contains · placeholders
    md = render_markdown(trend)
    assert "·" in md, "Markdown output should contain · placeholders for missing data"


def test_recent_k_observations_block():
    """T3: Recent K observations - each scenario gets K entries (or all if fewer)."""
    # Create entries spanning 14 days to test beyond-window observations
    all_entries = []
    for i in range(14):
        e = _entry(i % 7)  # Reuse pattern
        e["date_utc"] = f"2026-03-{(i+1):02d}"
        # Rotate scenarios: i%3
        scenario = ["baseline", "focused", "wide"][i % 3]
        e["sentinel"]["scenario"] = scenario
        e["commit"] = f"c{i}"
        all_entries.append(e)
    
    trend = build_trend(all_entries, alert_threshold=0.2)
    
    # Check recent_observations for each scenario
    recent_obs = trend["recent_observations"]
    
    # baseline appears at i=0,3,6,9,12 -> 5 dates within K=5
    baseline_recent = recent_obs["baseline"]
    assert len(baseline_recent) <= 5, "baseline should have at most K=5 recent observations"
    assert len(baseline_recent) >= 1, "baseline should have at least 1 observation"
    
    # focused appears at i=1,4,7,10,13 -> 5 dates
    focused_recent = recent_obs["focused"]
    assert len(focused_recent) <= 5, "focused should have at most K=5 recent observations"
    
    # wide appears at i=2,5,8,11 -> 4 dates
    wide_recent = recent_obs["wide"]
    assert len(wide_recent) <= 5, "wide should have at most K=5 recent observations"
    
    # Verify recent observations are sorted by date descending
    for scenario, obs_list in recent_obs.items():
        if len(obs_list) > 1:
            dates = [o.get("date_utc", "") for o in obs_list]
            assert dates == sorted(dates, reverse=True), f"{scenario} observations should be sorted descending"
    
    # Verify MD output contains Recent K=5 Observations section
    md = render_markdown(trend)
    assert "#### Recent K=5 Observations" in md
    assert "**baseline**" in md
    assert "**focused**" in md
    assert "**wide**" in md
