"""MVP11.4.5 E2E Harness Tests - Concentration Fields in Nightly/Trend.

Tests for concentration metrics (phi_top1_share, phi_top3_share, phi_hhi, unique_phi_per_1000)
in nightly summary and trend outputs.
"""

from __future__ import annotations

from scripts.build_mvp11_trend_7d import build_trend, compute_concentration, render_markdown


def _entry_with_signature(i: int, signature: str = None) -> dict:
    """Create a trend entry with optional cycle signature."""
    entry = {
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
    
    if signature:
        entry["cycle_signature"] = signature
    
    return entry


def test_nightly_summary_includes_concentration_fields():
    """Test that trend output includes concentration fields."""
    # Create entries with different signatures
    entries = []
    for i in range(7):
        # Create varying signatures to test concentration
        if i < 4:
            sig = "sig_A"  # Dominant signature
        elif i < 6:
            sig = "sig_B"
        else:
            sig = "sig_C"
        entries.append(_entry_with_signature(i, signature=sig))
    
    trend = build_trend(entries, alert_threshold=0.2)
    
    # Check concentration field exists
    assert "concentration" in trend, "trend should have concentration field"
    
    concentration = trend["concentration"]
    
    # Check all required fields
    assert "phi_top1_share" in concentration
    assert "phi_top3_share" in concentration
    assert "phi_hhi" in concentration
    assert "unique_phi_per_1000" in concentration
    assert "warnings" in concentration
    
    # Check values are computed
    assert concentration["phi_top1_share"] is not None
    assert concentration["phi_top3_share"] is not None
    assert concentration["phi_hhi"] is not None
    assert concentration["unique_phi_per_1000"] is not None
    
    # Top1 share should be ~4/7 = 0.571
    assert 0.5 < concentration["phi_top1_share"] < 0.7
    
    # HHI should be positive
    assert concentration["phi_hhi"] > 0


def test_concentration_warnings_for_high_concentration():
    """Test that high concentration triggers warnings."""
    # Create entries where one signature dominates
    entries = []
    for i in range(10):
        if i < 8:
            sig = "dominant_sig"  # 80% share -> should trigger warning
        else:
            sig = f"minor_sig_{i}"
        entries.append(_entry_with_signature(i, signature=sig))
    
    concentration = compute_concentration(entries)
    
    # Should have warnings
    assert len(concentration["warnings"]) > 0, "Should warn on high top1_share"
    
    # Check warning message contains threshold info
    warning_text = " ".join(concentration["warnings"])
    assert "phi_top1_share" in warning_text or "phi_hhi" in warning_text


def test_concentration_empty_entries():
    """Test concentration with no signatures."""
    entries = []
    for i in range(5):
        entries.append(_entry_with_signature(i, signature=None))
    
    concentration = compute_concentration(entries)
    
    # Should return None values when no signatures
    assert concentration["phi_top1_share"] is None
    assert concentration["phi_top3_share"] is None
    assert concentration["phi_hhi"] is None
    assert concentration["unique_phi_per_1000"] is None
    assert concentration["warnings"] == []


def test_concentration_uniform_distribution():
    """Test concentration with uniform signature distribution."""
    entries = []
    for i in range(10):
        sig = f"sig_{i}"  # Each signature appears once
        entries.append(_entry_with_signature(i, signature=sig))
    
    concentration = compute_concentration(entries)
    
    # Top1 share should be 0.1
    assert 0.08 < concentration["phi_top1_share"] < 0.12
    
    # HHI should be low (1/10 for each of 10 = 0.1)
    assert concentration["phi_hhi"] < 0.15
    
    # No warnings for uniform distribution
    assert len(concentration["warnings"]) == 0


def test_trend_markdown_includes_concentration():
    """Test that markdown output includes concentration section."""
    entries = []
    for i in range(7):
        sig = "sig_A" if i < 4 else f"sig_{i}"
        entries.append(_entry_with_signature(i, signature=sig))
    
    trend = build_trend(entries, alert_threshold=0.2)
    md = render_markdown(trend)
    
    # Check concentration section exists
    assert "### Signature Concentration" in md
    
    # Check concentration metrics are shown
    assert "Top1 Share" in md
    assert "Top3 Share" in md
    assert "HHI" in md
    assert "Unique/1000" in md


def test_concentration_with_phi_dict():
    """Test concentration calculation with phi dict entries."""
    entries = []
    for i in range(5):
        entry = _entry_with_signature(i, signature=None)
        # Add phi dict instead of signature
        entry["phi"] = {
            "hs": {"energy": 0.5 + i * 0.1},
            "efe": {"risk": 0.1 * i},
        }
        entries.append(entry)
    
    concentration = compute_concentration(entries)
    
    # Should compute from phi dicts
    assert concentration["phi_top1_share"] is not None


def test_concentration_hhi_threshold():
    """Test HHI warning threshold."""
    # Create entries with high HHI (one signature very dominant)
    entries = []
    for i in range(100):
        if i < 60:
            sig = "dominant"  # 60% share
        elif i < 80:
            sig = "second"  # 20% share
        else:
            sig = f"other_{i}"  # 20% distributed
        entries.append(_entry_with_signature(i % 7, signature=sig))
    
    concentration = compute_concentration(entries)
    
    # HHI = 0.6^2 + 0.2^2 + ... = 0.36 + 0.04 + ... > 0.25
    assert concentration["phi_hhi"] > 0.25, "HHI should exceed threshold"
    
    # Should have warning about high HHI
    hhi_warnings = [w for w in concentration["warnings"] if "phi_hhi" in w]
    assert len(hhi_warnings) > 0, "Should warn on high HHI"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
