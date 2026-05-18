import json
from pathlib import Path

from ego_desktop_lab.llm_adapter import run_llm_cognition_adapter
from ego_desktop_lab.reducer import run_agent_cycle
from ego_desktop_lab.subject_state import build_demo_state


def test_llm_can_propose_plan_but_gate_can_block(tmp_path: Path) -> None:
    core = run_agent_cycle(
        build_demo_state(),
        evidence_log_path=tmp_path / "core.jsonl",
        timestamp="2026-05-13T00:00:00+00:00",
        append_evidence=False,
    )
    assert core.selected_intention is not None
    payload = {
        "plan": json.dumps(
            {
                "plans": (
                    {
                        "plan_id": "plan:ok",
                        "related_goal_id": "goal:001",
                        "related_intention_id": core.selected_intention.id,
                        "steps": ("summarize",),
                        "expected_effect": "proposal-only summary",
                        "risk": 0.10,
                        "cost": 0.20,
                        "confidence": 0.70,
                        "required_permission": "suggestion_card",
                    },
                    {
                        "plan_id": "plan:blocked",
                        "related_goal_id": "goal:001",
                        "related_intention_id": core.selected_intention.id,
                        "steps": ("delete",),
                        "expected_effect": "invalid direct action",
                        "risk": 0.90,
                        "cost": 0.50,
                        "confidence": 0.70,
                        "required_permission": "file_delete",
                    },
                )
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

    assert result.plan_proposals is not None
    assert len(result.plan_proposals.plans) == 1
    assert result.plan_proposals.plans[0].plan_id == "plan:ok"
    assert result.plan_gate_decisions[0].status == "allow"
    assert any(not item.accepted and "proposal-only" in item.reason for item in result.proposal_validation_results)
