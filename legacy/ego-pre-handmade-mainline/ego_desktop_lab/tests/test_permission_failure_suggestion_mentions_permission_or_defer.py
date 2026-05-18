from pathlib import Path

from ego_desktop_lab.decision_view import build_decision_view_from_semantic_result
from ego_desktop_lab.semantic_intelligence import run_semantic_scenario


def test_permission_failure_suggestion_mentions_permission_or_defer(tmp_path: Path) -> None:
    result = run_semantic_scenario(
        Path("ego_desktop_lab/semantic_scenarios/permission_failure.txt"),
        provider_mode="mock",
        evidence_log_path=tmp_path / "permission.jsonl",
    )
    view = build_decision_view_from_semantic_result(result)
    suggestion = view.rendered_suggestion.lower()

    assert view.canonical_decision["after_selected_intention"]["goal"] == "ask_permission_or_defer"
    assert "permission" in suggestion
    assert "defer" in suggestion
    assert "no external action has been executed" in suggestion
    assert view.no_action_executed is True
