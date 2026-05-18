from pathlib import Path

from ego_desktop_lab.event_log import read_evidence_records
from ego_desktop_lab.reducer import run_agent_cycle
from ego_desktop_lab.subject_state import SubjectState


def test_evidence_log_records_selected_intention_and_gate(tmp_path: Path) -> None:
    log_path = tmp_path / "evidence.jsonl"
    state = SubjectState(
        agent_id="test-agent",
        core_commitments=("avoid false claims",),
        uncertainty=0.82,
        integrity=0.90,
        goal_pressure=0.10,
        risk_sensitivity=0.50,
        unfinished_goals=(),
        recent_failures=(),
        identity_conflict=False,
    )

    run_agent_cycle(
        state,
        evidence_log_path=log_path,
        timestamp="2026-05-12T00:00:00+00:00",
    )

    records = read_evidence_records(log_path)

    assert len(records) == 1
    assert records[0]["timestamp"] == "2026-05-12T00:00:00+00:00"
    assert "appraisal" in records[0]
    assert "motivation_diff" in records[0]
    assert "motivation_pressure" in records[0]
    assert "affordance_pressure" in records[0]
    assert records[0]["selected_intention"]["goal"] == "verify_before_claim"  # type: ignore[index]
    assert records[0]["gate_decision"]["status"] == "allow"  # type: ignore[index]
    assert records[0]["motivation_diff"]["avoid_false_claims"]["delta"] > 0  # type: ignore[index]
    assert "verify uncertainty-sensitive claims" in str(records[0]["suggestion"])
