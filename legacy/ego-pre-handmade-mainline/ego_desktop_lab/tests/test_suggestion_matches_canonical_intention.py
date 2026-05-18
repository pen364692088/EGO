from pathlib import Path

from ego_desktop_lab.decision_view import build_decision_view_from_semantic_result
from ego_desktop_lab.semantic_intelligence import run_semantic_scenario


SCENARIO_DIR = Path("ego_desktop_lab/semantic_scenarios")


def test_suggestion_matches_canonical_intention(tmp_path: Path) -> None:
    expected_keywords = {
        "ambiguous_user_concern": ("clarification", "bind"),
        "evidence_failure": ("verify", "evidence"),
        "execution_failure": ("retry", "tool"),
        "goal_definition_failure": ("split", "success criteria"),
        "permission_failure": ("permission", "defer"),
        "plan_failure": ("repair", "replan"),
    }

    for scenario_id, keywords in expected_keywords.items():
        result = run_semantic_scenario(
            SCENARIO_DIR / f"{scenario_id}.txt",
            provider_mode="mock",
            evidence_log_path=tmp_path / f"{scenario_id}.jsonl",
        )
        view = build_decision_view_from_semantic_result(result)
        suggestion = view.rendered_suggestion.lower()

        assert view.suggestion == view.rendered_suggestion
        assert view.suggestion_source == "canonical_decision"
        assert all(keyword in suggestion for keyword in keywords)
        assert view.canonical_decision["after_selected_intention"]["goal"]
