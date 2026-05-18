import json
from pathlib import Path

from ego_desktop_lab.goal_progress import GoalProgressState
from ego_desktop_lab.llm_adapter import run_llm_cognition_adapter
from ego_desktop_lab.reducer import run_agent_cycle
from ego_desktop_lab.subject_state import build_demo_state


def test_llm_can_propose_failure_type_but_not_commit_it(tmp_path: Path) -> None:
    core = run_agent_cycle(
        build_demo_state(),
        evidence_log_path=tmp_path / "core.jsonl",
        timestamp="2026-05-13T00:00:00+00:00",
        append_evidence=False,
    )
    progress = GoalProgressState(goal_id="goal:001", progress_score=0.30)
    payload = {
        "semantic": json.dumps(
            {
                "source_event_id": core.evidence_record.event_id,
                "candidate_failure_type": "plan_failure",
                "evidence_gap": 0.62,
                "goal_relevance": 0.80,
                "risk_hint": 0.30,
                "confidence": 0.75,
                "evidence_refs": (core.evidence_record.event_id,),
                "rationale": "LLM can propose only.",
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

    assert result.semantic_proposal is not None
    assert result.semantic_proposal.candidate_failure_type == "plan_failure"
    assert result.semantic_proposal.evidence_gap == 0.62
    assert result.core_result.selected_intention == core.selected_intention
    assert result.core_result.gate_decision == core.gate_decision
    assert progress == GoalProgressState(goal_id="goal:001", progress_score=0.30)
