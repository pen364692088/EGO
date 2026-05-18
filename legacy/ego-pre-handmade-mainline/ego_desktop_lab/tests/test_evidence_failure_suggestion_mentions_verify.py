from pathlib import Path

from ego_desktop_lab.decision_view import build_decision_view_from_semantic_result
from ego_desktop_lab.semantic_intelligence import run_semantic_scenario


def test_evidence_failure_suggestion_mentions_verify(tmp_path: Path) -> None:
    result = run_semantic_scenario(
        Path("ego_desktop_lab/semantic_scenarios/evidence_failure.txt"),
        provider_mode="mock",
        evidence_log_path=tmp_path / "evidence.jsonl",
    )
    view = build_decision_view_from_semantic_result(result)
    suggestion = view.rendered_suggestion.lower()

    assert view.canonical_decision["after_selected_intention"]["goal"] == "verify_before_claim"
    assert "verify" in suggestion
    assert "evidence" in suggestion
    assert "before making a claim" in suggestion
