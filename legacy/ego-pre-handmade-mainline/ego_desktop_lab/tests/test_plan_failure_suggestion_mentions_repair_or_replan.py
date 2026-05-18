from pathlib import Path

from ego_desktop_lab.decision_view import build_decision_view_from_semantic_result
from ego_desktop_lab.semantic_intelligence import run_semantic_scenario


def test_plan_failure_suggestion_mentions_repair_or_replan(tmp_path: Path) -> None:
    result = run_semantic_scenario(
        Path("ego_desktop_lab/semantic_scenarios/plan_failure.txt"),
        provider_mode="mock",
        evidence_log_path=tmp_path / "plan.jsonl",
    )
    view = build_decision_view_from_semantic_result(result)
    suggestion = view.rendered_suggestion.lower()

    assert view.canonical_decision["after_selected_intention"]["goal"] == "repair_or_replan_goal"
    assert "repair" in suggestion
    assert "replan" in suggestion
    assert "verify" not in suggestion
    assert view.debug_refs["raw_core_suggestion"] != view.rendered_suggestion
