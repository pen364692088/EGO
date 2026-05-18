from pathlib import Path

from ego_desktop_lab.semantic_intelligence import run_semantic_scenario


SCENARIO = Path("ego_desktop_lab/semantic_scenarios/goal_definition_failure.txt")


def test_llm_classifies_goal_definition_failure(tmp_path: Path) -> None:
    result = run_semantic_scenario(
        SCENARIO,
        provider_mode="mock",
        evidence_log_path=tmp_path / "semantic.jsonl",
    )

    assert result.semantic_proposal is not None
    assert result.semantic_proposal.candidate_failure_type == "goal_definition_failure"
    assert result.semantic_proposal.binding_status == "bound"
    assert result.goal_operation_proposal is not None
    assert result.goal_operation_proposal.operation == "split_goal"
    assert result.goal_operation_proposal.subgoals[0].proposed_title == "Define the target behavior"
