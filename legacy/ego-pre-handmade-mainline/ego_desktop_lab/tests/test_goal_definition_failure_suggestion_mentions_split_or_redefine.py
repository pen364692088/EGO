from pathlib import Path

from ego_desktop_lab.decision_view import build_decision_view_from_semantic_result
from ego_desktop_lab.semantic_intelligence import run_semantic_scenario


def test_goal_definition_failure_suggestion_mentions_split_or_redefine(tmp_path: Path) -> None:
    result = run_semantic_scenario(
        Path("ego_desktop_lab/semantic_scenarios/goal_definition_failure.txt"),
        provider_mode="mock",
        evidence_log_path=tmp_path / "goal_definition.jsonl",
    )
    view = build_decision_view_from_semantic_result(result)
    suggestion = view.rendered_suggestion.lower()
    subgoals = view.goal_operation_proposal["subgoals"]

    assert view.canonical_decision["after_selected_intention"]["goal"] in {
        "split_goal_or_redefine_success_criteria",
        "reframe_or_split_goal",
    }
    assert "split" in suggestion
    assert "success criteria" in suggestion
    assert subgoals
    assert subgoals[0]["proposed_title"].lower() in suggestion
    assert subgoals[0]["success_criteria"].lower() in suggestion
