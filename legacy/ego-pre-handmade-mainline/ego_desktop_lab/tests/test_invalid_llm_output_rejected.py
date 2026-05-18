from pathlib import Path

from ego_desktop_lab.event_log import read_evidence_records
from ego_desktop_lab.llm_adapter import run_llm_cognition_adapter
from ego_desktop_lab.reducer import run_agent_cycle
from ego_desktop_lab.subject_state import build_demo_state


def test_invalid_llm_output_rejected(tmp_path: Path) -> None:
    evidence_path = tmp_path / "llm.jsonl"
    core = run_agent_cycle(
        build_demo_state(),
        evidence_log_path=evidence_path,
        timestamp="2026-05-13T00:00:00+00:00",
        append_evidence=False,
    )

    result = run_llm_cognition_adapter(
        core,
        {"invalid_json": "{not-valid-json"},
        evidence_log_path=evidence_path,
        timestamp="2026-05-13T00:00:00+00:00",
    )
    record = read_evidence_records(evidence_path)[-1]

    assert result.rejected_llm_proposals[0]["proposal_type"] == "invalid_json"
    assert "invalid JSON" in result.rejected_llm_proposals[0]["reason"]
    assert result.core_result.suggestion == core.suggestion
    assert record["executive_rejected_proposals"][0]["proposal_type"] == "invalid_json"
