import json
from pathlib import Path

from ego_desktop_lab.llm_adapter import run_llm_cognition_adapter
from ego_desktop_lab.reducer import run_agent_cycle
from ego_desktop_lab.subject_state import build_demo_state


def test_llm_explanation_does_not_change_decision(tmp_path: Path) -> None:
    core = run_agent_cycle(
        build_demo_state(),
        evidence_log_path=tmp_path / "core.jsonl",
        timestamp="2026-05-13T00:00:00+00:00",
        append_evidence=False,
    )
    assert core.selected_intention is not None
    payload = {
        "explanation": json.dumps(
            {
                "related_evidence_id": core.evidence_record.event_id,
                "plain_language_summary": "This explanation must not change the selected intention.",
                "claim_ceiling": "lab-only deterministic explanation",
                "uncertainty_notes": "No state mutation is allowed.",
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

    assert result.explanation_draft is not None
    assert result.proposal_validation_results[0].accepted is True
    assert result.core_result.selected_intention.id == core.selected_intention.id
    assert result.core_result.selected_intention.goal == core.selected_intention.goal
    assert result.core_result.selected_intention.priority == core.selected_intention.priority
