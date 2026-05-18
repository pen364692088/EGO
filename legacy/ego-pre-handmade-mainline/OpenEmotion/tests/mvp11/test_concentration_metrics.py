"""Tests for concentration.py module.

Ensures determinism and correct metric computation.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from emotiond.science.concentration import (
    compute_concentration,
    compute_concentration_from_run,
    render_concentration_markdown,
)
from emotiond.science.cycle import build_cycle_bucket, signature_phi


def _make_event(phi_sig: str, tick: int = 1) -> dict:
    """Create a minimal event with given phi signature."""
    return {
        "tick": tick,
        "cycle_signature_phi": phi_sig,
        "cycle_bucket": {
            "scenario_id": "global",
            "focus": "f0",
            "intent": "none",
            "phi": {
                "hs": {"energy": 0.6, "safety": 0.6, "certainty": 0.8, "autonomy": 0.8},
                "efe": {"risk": 0.0, "ambiguity": 0.0, "info_gain": 0.0, "cost": 0.0},
            },
        },
    }


class TestConcentrationMetricsDeterministic:
    """Test that concentration metrics are deterministic for same events."""
    
    def test_concentration_metrics_deterministic_same_events(self):
        """Same events must produce identical concentration metrics."""
        # Create events with known phi signatures
        events = [
            _make_event("sig_a", tick=1),
            _make_event("sig_a", tick=2),
            _make_event("sig_a", tick=3),
            _make_event("sig_b", tick=4),
            _make_event("sig_b", tick=5),
            _make_event("sig_c", tick=6),
            _make_event("sig_d", tick=7),
            _make_event("sig_e", tick=8),
            _make_event("sig_f", tick=9),
            _make_event("sig_a", tick=10),
        ]
        
        # Compute twice
        result1 = compute_concentration(events, rolling_window=100)
        result2 = compute_concentration(events, rolling_window=100)
        
        # Must be identical
        assert result1 == result2, f"Non-deterministic: {result1} vs {result2}"
        
        # Verify expected values
        # 4 sig_a out of 10 = 0.4
        assert result1["phi_top1_share"] == 0.4, f"Expected 0.4, got {result1['phi_top1_share']}"
        
        # top3: sig_a(4) + sig_b(2) + sig_c(1) = 7 out of 10 = 0.7
        assert result1["phi_top3_share"] == 0.7, f"Expected 0.7, got {result1['phi_top3_share']}"
        
        # HHI: sum of squared shares
        # sig_a: (4/10)^2 = 0.16
        # sig_b: (2/10)^2 = 0.04
        # sig_c: (1/10)^2 = 0.01
        # sig_d: (1/10)^2 = 0.01
        # sig_e: (1/10)^2 = 0.01
        # sig_f: (1/10)^2 = 0.01
        # HHI = 0.16 + 0.04 + 0.01 + 0.01 + 0.01 + 0.01 = 0.24
        assert result1["phi_hhi"] == 0.24, f"Expected 0.24, got {result1['phi_hhi']}"
        
        # unique: 6 unique out of 10 = 600 per 1000
        assert result1["unique_phi_per_1000"] == 600.0, f"Expected 600.0, got {result1['unique_phi_per_1000']}"
    
    def test_concentration_handles_ties_deterministic(self):
        """Tie-breaking must be deterministic (alphabetical)."""
        # Create events where multiple signatures have same count
        events = [
            _make_event("sig_z", tick=1),  # 3 occurrences
            _make_event("sig_z", tick=2),
            _make_event("sig_z", tick=3),
            _make_event("sig_a", tick=4),  # 3 occurrences
            _make_event("sig_a", tick=5),
            _make_event("sig_a", tick=6),
            _make_event("sig_m", tick=7),  # 3 occurrences
            _make_event("sig_m", tick=8),
            _make_event("sig_m", tick=9),
        ]
        
        # All three have count 3, alphabetical order should determine top-1
        result = compute_concentration(events, rolling_window=100)
        
        # sig_a should be top-1 (alphabetically first among ties)
        # top1_share = 3/9 = 0.333...
        expected_top1 = round(3 / 9, 6)
        assert result["phi_top1_share"] == expected_top1, f"Expected {expected_top1}, got {result['phi_top1_share']}"
        
        # top3 should include all three = 9/9 = 1.0
        assert result["phi_top3_share"] == 1.0, f"Expected 1.0, got {result['phi_top3_share']}"
        
        # Run multiple times to ensure determinism
        for _ in range(10):
            r = compute_concentration(events, rolling_window=100)
            assert r == result, "Non-deterministic tie-breaking detected"
    
    def test_concentration_rolling_window_50(self):
        """Rolling window of 50 should only consider last 50 events."""
        # Create 100 events: first 50 all sig_a, last 50 all sig_b
        events = []
        for i in range(50):
            events.append(_make_event("sig_a", tick=i + 1))
        for i in range(50):
            events.append(_make_event("sig_b", tick=i + 51))
        
        result = compute_concentration(events, rolling_window=50)
        
        # With window=50, only last 50 events (all sig_b) considered
        assert result["phi_top1_share"] == 1.0, f"Expected 1.0, got {result['phi_top1_share']}"
        assert result["phi_hhi"] == 1.0, f"Expected 1.0, got {result['phi_hhi']}"
        # 1 unique out of 50 = 20 per 1000
        assert result["unique_phi_per_1000"] == 20.0, f"Expected 20.0, got {result['unique_phi_per_1000']}"
    
    def test_concentration_rolling_window_100(self):
        """Rolling window of 100 should consider all 100 events."""
        # Create 100 events: first 50 all sig_a, last 50 all sig_b
        events = []
        for i in range(50):
            events.append(_make_event("sig_a", tick=i + 1))
        for i in range(50):
            events.append(_make_event("sig_b", tick=i + 51))
        
        result = compute_concentration(events, rolling_window=100)
        
        # With window=100, both sig_a and sig_b considered
        assert result["phi_top1_share"] == 0.5, f"Expected 0.5, got {result['phi_top1_share']}"
        # top2 = 100%, so top3 = 100%
        assert result["phi_top3_share"] == 1.0, f"Expected 1.0, got {result['phi_top3_share']}"
        # HHI = 0.5^2 + 0.5^2 = 0.5
        assert result["phi_hhi"] == 0.5, f"Expected 0.5, got {result['phi_hhi']}"
        # 2 unique out of 100 = 20 per 1000
        assert result["unique_phi_per_1000"] == 20.0, f"Expected 20.0, got {result['unique_phi_per_1000']}"
    
    def test_concentration_empty_events(self):
        """Empty events should return zeros."""
        result = compute_concentration([], rolling_window=100)
        
        assert result["phi_top1_share"] == 0.0
        assert result["phi_top3_share"] == 0.0
        assert result["phi_hhi"] == 0.0
        assert result["unique_phi_per_1000"] == 0.0
        assert result["window_size"] == 100
    
    def test_concentration_single_event(self):
        """Single event should have perfect concentration."""
        events = [_make_event("sig_x", tick=1)]
        
        result = compute_concentration(events, rolling_window=100)
        
        assert result["phi_top1_share"] == 1.0
        assert result["phi_top3_share"] == 1.0
        assert result["phi_hhi"] == 1.0
        # 1 unique out of 1 = 1000 per 1000
        assert result["unique_phi_per_1000"] == 1000.0
    
    def test_concentration_events_without_phi_signature(self):
        """Events without cycle_signature_phi should compute from cycle_bucket."""
        events = [
            {
                "tick": 1,
                "cycle_bucket": {
                    "scenario_id": "global",
                    "focus": "f0",
                    "intent": "none",
                    "phi": {
                        "hs": {"energy": 0.6, "safety": 0.6, "certainty": 0.8, "autonomy": 0.8},
                        "efe": {"risk": 0.0, "ambiguity": 0.0, "info_gain": 0.0, "cost": 0.0},
                    },
                },
            },
            {
                "tick": 2,
                "cycle_bucket": {
                    "scenario_id": "global",
                    "focus": "f0",
                    "intent": "none",
                    "phi": {
                        "hs": {"energy": 0.6, "safety": 0.6, "certainty": 0.8, "autonomy": 0.8},
                        "efe": {"risk": 0.0, "ambiguity": 0.0, "info_gain": 0.0, "cost": 0.0},
                    },
                },
            },
        ]
        
        # Both events have same phi content, so should have same signature
        result = compute_concentration(events, rolling_window=100)
        
        # Both should have same phi signature -> top1 = 100%
        assert result["phi_top1_share"] == 1.0
        # 1 unique out of 2 = 500 per 1000
        assert result["unique_phi_per_1000"] == 500.0
    
    def test_concentration_result_immutability(self):
        """Modifying returned result should not affect future computations."""
        events = [
            _make_event("sig_a", tick=1),
            _make_event("sig_a", tick=2),
            _make_event("sig_b", tick=3),
        ]
        
        result1 = compute_concentration(events, rolling_window=100)
        
        # Modify returned result
        result1["phi_top1_share"] = 0.999
        
        # Compute again
        result2 = compute_concentration(events, rolling_window=100)
        
        # New result should not be affected by previous modification
        assert result2["phi_top1_share"] == round(2 / 3, 6)
    
    def test_render_concentration_markdown(self):
        """Test markdown rendering."""
        metrics = {
            "phi_top1_share": 0.45,
            "phi_top3_share": 0.72,
            "phi_hhi": 0.21,
            "unique_phi_per_1000": 8.3,
            "window_size": 100,
        }
        
        md = render_concentration_markdown(metrics)
        
        assert "# Concentration Report" in md
        assert "phi_top1_share" in md
        assert "0.450000" in md
        assert "phi_hhi" in md
        assert "Interpretation" in md


class TestConcentrationFromRun:
    """Test loading concentration from run.jsonl files."""
    
    def test_compute_concentration_from_real_run(self):
        """Test with actual run.jsonl if available."""
        # Find a run file
        artifacts_dir = Path(__file__).parent.parent.parent / "artifacts" / "mvp11"
        run_files = list(artifacts_dir.glob("*.jsonl"))
        
        if not run_files:
            pytest.skip("No run.jsonl files available for testing")
        
        run_path = run_files[0]
        result = compute_concentration_from_run(str(run_path), rolling_window=100)
        
        # Verify output structure
        assert "phi_top1_share" in result
        assert "phi_top3_share" in result
        assert "phi_hhi" in result
        assert "unique_phi_per_1000" in result
        assert "window_size" in result
        
        # Verify value ranges
        assert 0.0 <= result["phi_top1_share"] <= 1.0
        assert 0.0 <= result["phi_top3_share"] <= 1.0
        assert 0.0 <= result["phi_hhi"] <= 1.0
        assert result["unique_phi_per_1000"] >= 0.0
        
        # Run again to verify determinism
        result2 = compute_concentration_from_run(str(run_path), rolling_window=100)
        assert result == result2, "Results not deterministic for same file"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
