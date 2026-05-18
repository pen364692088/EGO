from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "OpenEmotion" / "tools" / "aggregate_mvp12_observations.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("mvp12_observation_aggregate", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_aggregate_summary_holds_when_time_span_too_short():
    module = _load_module()
    reports = [
        {
            "generated_at": "2026-04-01T21:59:14.349353",
            "report_dir": "controlled_a",
            "verification_level": "V3",
            "completion_class": "controlled_evidence_only",
            "total_cycles": 6,
            "direct_real_cycles": 0,
            "direct_real_window_count": 0,
            "governance_violation_count": 0,
            "replay_consistent": True,
            "unique_candidate_hash_sets": 5,
        },
        {
            "generated_at": "2026-04-01T22:06:14.468433",
            "report_dir": "controlled_b",
            "verification_level": "V3",
            "completion_class": "controlled_evidence_only",
            "total_cycles": 10,
            "direct_real_cycles": 4,
            "direct_real_window_count": 1,
            "governance_violation_count": 0,
            "replay_consistent": True,
            "unique_candidate_hash_sets": 9,
        },
        {
            "generated_at": "2026-04-01T22:15:34.958816",
            "report_dir": "controlled_c",
            "verification_level": "V3",
            "completion_class": "controlled_evidence_only",
            "total_cycles": 18,
            "direct_real_cycles": 12,
            "direct_real_window_count": 3,
            "governance_violation_count": 0,
            "replay_consistent": True,
            "unique_candidate_hash_sets": 17,
        },
    ]

    summary = module.build_aggregate_summary(
        reports,
        min_reports=3,
        min_direct_real_windows=3,
        min_span_hours=12.0,
    )

    assert summary["report_count"] == 3
    assert summary["direct_real_window_count_total"] == 4
    assert summary["governance_violation_total"] == 0
    assert summary["replay_consistent_all"] is True
    assert summary["stability_gate"]["checks"]["min_reports"] is True
    assert summary["stability_gate"]["checks"]["min_direct_real_windows"] is True
    assert summary["stability_gate"]["checks"]["min_span_hours"] is False
    assert summary["stability_gate"]["status"] == "hold"
