import json
from pathlib import Path

from ego_desktop_lab.llm_adapter import run_llm_cognition_adapter
from ego_desktop_lab.reducer import run_agent_cycle
from ego_desktop_lab.subject_state import build_demo_state


def test_llm_cannot_modify_goal_progress(tmp_path: Path) -> None:
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
                "evidence_gap": 0.10,
                "goal_relevance": 0.90,
                "risk_hint": 0.20,
                "confidence": 0.80,
                "evidence_refs": (core.evidence_record.event_id,),
                "rationale": "try to write progress",
                "goal_progress_update": {"progress_score": 1.0},
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
    assert "goal_progress_update" in result.rejected_llm_proposals[0]["reason"]
