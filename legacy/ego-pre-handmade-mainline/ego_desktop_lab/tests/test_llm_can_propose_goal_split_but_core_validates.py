import json
from dataclasses import replace
from pathlib import Path

from ego_desktop_lab.intention import Intention
from ego_desktop_lab.llm_adapter import run_llm_cognition_adapter
from ego_desktop_lab.reducer import run_agent_cycle
from ego_desktop_lab.subject_state import build_demo_state


def test_llm_can_propose_goal_split_but_core_validates(tmp_path: Path) -> None:
    core = run_agent_cycle(
        build_demo_state(),
        evidence_log_path=tmp_path / "core.jsonl",
        timestamp="2026-05-13T00:00:00+00:00",
        append_evidence=False,
    )
    assert core.selected_intention is not None
    payload = {
        "goal_reframe": json.dumps(
            {
                "source_event_id": core.evidence_record.event_id,
                "related_goal_id": "goal:001",
                "goal_split": "split verification from execution",
                "success_criteria_rewrite": "success requires evidence-backed proposal only",
                "subgoals": ("verify claim", "define bounded next step"),
                "confidence": 0.72,
                "rationale": "goal frame needs clarification",
            },
            sort_keys=True,
        )
    }
    rejected = run_llm_cognition_adapter(
        core,
        payload,
        evidence_log_path=tmp_path / "reject.jsonl",
        timestamp="2026-05-13T00:00:00+00:00",
    )
    reframe_core = replace(core, selected_intention=_reframe_intention(core.selected_intention))
    accepted = run_llm_cognition_adapter(
        reframe_core,
        payload,
        evidence_log_path=tmp_path / "accept.jsonl",
        timestamp="2026-05-13T00:00:01+00:00",
    )

    assert rejected.goal_reframe_proposal is None
    assert "core did not request goal reframe" in rejected.rejected_llm_proposals[0]["reason"]
    assert accepted.goal_reframe_proposal is not None
    assert accepted.goal_reframe_proposal.subgoals == ("verify claim", "define bounded next step")
    assert accepted.core_result.selected_intention.goal == "reframe_or_split_goal"


def _reframe_intention(source: Intention) -> Intention:
    return Intention(
        id="intention:test:reframe",
        goal="reframe_or_split_goal",
        reason="test reframe",
        source_tension=source.source_tension,
        priority=source.priority,
        risk=source.risk,
        cost=source.cost,
        proposed_action="suggestion_card",
        affordance="repair",
        goal_id="goal:001",
        goal_description=source.goal_description,
    )
