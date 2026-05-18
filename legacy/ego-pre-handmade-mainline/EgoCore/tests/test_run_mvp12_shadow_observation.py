from __future__ import annotations

from EgoCore.tools.run_mvp12_shadow_observation import run_shadow_observation_cycles


def test_run_shadow_observation_cycles_returns_trace(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENEMOTION_MVP12_ARTIFACTS_DIR", str(tmp_path))
    result = run_shadow_observation_cycles(
        cycles=1,
        observation_source="synthetic",
        trigger="idle",
        session_id="session:mvp12:test",
        subject_profile="seed_v0_2",
    )
    assert len(result["cycles"]) == 1
    cycle = result["cycles"][0]
    assert cycle["developmental_summary"]["gate_status"] == "allow"
    assert cycle["developmental_gate"]["governance_violation_count"] == 0
    assert cycle["developmental_trace"]["candidate_hashes"]
