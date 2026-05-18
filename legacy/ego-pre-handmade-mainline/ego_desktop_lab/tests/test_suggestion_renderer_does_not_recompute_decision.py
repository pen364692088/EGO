from pathlib import Path

from ego_desktop_lab.decision_view import build_decision_view_from_evidence_record
from ego_desktop_lab.semantic_intelligence import run_semantic_scenario


def test_suggestion_renderer_does_not_recompute_decision(tmp_path: Path) -> None:
    source = Path("ego_desktop_lab/suggestion_renderer.py").read_text(encoding="utf-8")

    forbidden = (
        "select_intention",
        "calculate_pressure_priority",
        "calculate_static_priority",
        "run_semantic_policy_calibration_cycle",
        "derive_semantic_policy_overlay",
        "affordance_map",
        "generated_intentions",
        "legacy_next_core_cycle_influence",
    )
    for token in forbidden:
        assert token not in source

    result = run_semantic_scenario(
        Path("ego_desktop_lab/semantic_scenarios/execution_failure.txt"),
        provider_mode="mock",
        evidence_log_path=tmp_path / "execution.jsonl",
    )
    record = result.evidence_record.to_dict()
    record["suggestion"] = "OLD CORE SUGGESTION: verify instead."
    record["next_core_cycle_influence"]["after_selected_intention"] = "verify_before_claim"

    view = build_decision_view_from_evidence_record(record, tmp_path / "execution.jsonl")

    assert view.canonical_decision["after_selected_intention"]["goal"] == "retry_or_change_tool"
    assert "retry" in view.rendered_suggestion.lower()
    assert "tool" in view.rendered_suggestion.lower()
    assert "OLD CORE SUGGESTION" not in view.rendered_suggestion
    assert view.debug_refs["raw_core_suggestion"] == "OLD CORE SUGGESTION: verify instead."
