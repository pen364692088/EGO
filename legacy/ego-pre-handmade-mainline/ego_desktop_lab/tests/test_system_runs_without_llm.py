from pathlib import Path

from ego_desktop_lab.reducer import run_agent_cycle
from ego_desktop_lab.subject_state import build_demo_state


def test_system_runs_without_llm(tmp_path: Path) -> None:
    result = run_agent_cycle(
        build_demo_state(),
        evidence_log_path=tmp_path / "no_llm.jsonl",
        timestamp="2026-05-13T00:00:00+00:00",
    )

    assert result.selected_intention is not None
    assert result.gate_decision.status == "allow"
    assert result.evidence_record.llm_enabled is None
    assert "Suggestion:" in result.suggestion
