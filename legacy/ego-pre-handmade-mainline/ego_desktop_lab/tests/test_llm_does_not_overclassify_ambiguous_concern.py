from pathlib import Path

from ego_desktop_lab.semantic_intelligence import run_semantic_scenario


SCENARIO = Path("ego_desktop_lab/semantic_scenarios/ambiguous_user_concern.txt")


def test_llm_does_not_overclassify_ambiguous_concern(tmp_path: Path) -> None:
    result = run_semantic_scenario(
        SCENARIO,
        provider_mode="mock",
        evidence_log_path=tmp_path / "semantic.jsonl",
    )

    assert result.semantic_proposal is not None
    assert result.semantic_proposal.candidate_failure_type == "ambiguous_concern"
    assert result.semantic_proposal.candidate_failure_type != "plan_failure"
    assert result.semantic_proposal.confidence < 0.60
    assert result.semantic_proposal.binding_status == "pending_goal_binding"
    assert result.semantic_proposal.proposed_goal_operation == "ask_clarification"
    assert result.handoff.applied is False
