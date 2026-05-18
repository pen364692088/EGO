from pathlib import Path

from ego_desktop_lab.decision_view import build_decision_view_from_semantic_result
from ego_desktop_lab.semantic_intelligence import run_semantic_scenario


def test_execution_failure_suggestion_mentions_retry_or_tool_change(tmp_path: Path) -> None:
    result = run_semantic_scenario(
        Path("ego_desktop_lab/semantic_scenarios/execution_failure.txt"),
        provider_mode="mock",
        evidence_log_path=tmp_path / "execution.jsonl",
    )
    view = build_decision_view_from_semantic_result(result)
    suggestion = view.rendered_suggestion.lower()

    assert view.canonical_decision["after_selected_intention"]["goal"] == "retry_or_change_tool"
    assert "retry" in suggestion
    assert "tool" in suggestion
    assert "execution route" in suggestion
    assert view.suggestion_source == "canonical_decision"
