import json
from pathlib import Path

from ego_desktop_lab.llm_adapter import run_llm_cognition_adapter
from ego_desktop_lab.reducer import run_agent_cycle
from ego_desktop_lab.subject_state import build_demo_state


def test_llm_proposal_cannot_modify_state(tmp_path: Path) -> None:
    core = run_agent_cycle(
        build_demo_state(),
        evidence_log_path=tmp_path / "core.jsonl",
        timestamp="2026-05-13T00:00:00+00:00",
        append_evidence=False,
    )
    payload = {
        "semantic": json.dumps(
            {
                "source_event_id": core.evidence_record.event_id,
                "candidate_failure_type": "plan_failure",
                "confidence": 0.80,
                "evidence_refs": (core.evidence_record.event_id,),
                "rationale": "try to change state",
                "state_update": {"uncertainty": 0.0},
                "motivation_update": {"seek_truth": 0.0},
                "gate_decision": {"status": "allow"},
            },
            sort_keys=True,
        )
    }

    result = run_llm_cognition_adapter(
        core,
        payload,
        evidence_log_path=tmp_path / "llm.jsonl",
        timestamp="2026-05-13T00:00:00+00:00",
    )

    assert result.semantic_proposal is None
    assert result.rejected_llm_proposals
    assert "forbidden mutation fields" in result.rejected_llm_proposals[0]["reason"]
    assert result.core_result.old_state_summary == core.old_state_summary
    assert result.core_result.selected_intention == core.selected_intention
    assert result.core_result.gate_decision == core.gate_decision
