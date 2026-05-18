from pathlib import Path
from typing import Any

from ego_desktop_lab.decision_view import (
    CLAIM_CEILING,
    build_decision_view_contract_report,
    build_decision_view_from_evidence_record,
    build_decision_view_from_semantic_result,
)
from ego_desktop_lab.semantic_intelligence import run_semantic_scenario


SCENARIO_DIR = Path("ego_desktop_lab/semantic_scenarios")


def test_decision_view_uses_canonical_decision(tmp_path: Path) -> None:
    result = run_semantic_scenario(
        SCENARIO_DIR / "execution_failure.txt",
        provider_mode="mock",
        evidence_log_path=tmp_path / "execution.jsonl",
    )
    record = result.evidence_record.to_dict()
    view = build_decision_view_from_semantic_result(result)
    replay_view = build_decision_view_from_evidence_record(record, result.evidence_log_path)

    assert view.canonical_decision == record["canonical_decision"]
    assert replay_view.canonical_decision == record["canonical_decision"]
    assert view.canonical_decision["after_selected_intention"]["goal"] == "retry_or_change_tool"


def test_decision_view_never_uses_legacy_as_final(tmp_path: Path) -> None:
    result = run_semantic_scenario(
        SCENARIO_DIR / "execution_failure.txt",
        provider_mode="mock",
        evidence_log_path=tmp_path / "execution.jsonl",
    )
    view = build_decision_view_from_semantic_result(result)
    legacy = view.debug_refs["legacy_next_core_cycle_influence_debug"]

    assert view.canonical_decision["after_selected_intention"]["goal"] == "retry_or_change_tool"
    assert legacy["after_selected_intention"] == "verify_before_claim"
    assert legacy["after_selected_intention"] != view.canonical_decision["after_selected_intention"]["goal"]
    assert legacy["is_final_decision_source"] is False


def test_decision_view_exposes_legacy_only_as_debug_refs(tmp_path: Path) -> None:
    result = run_semantic_scenario(
        SCENARIO_DIR / "plan_failure.txt",
        provider_mode="mock",
        evidence_log_path=tmp_path / "plan.jsonl",
    )
    view_dict = build_decision_view_from_semantic_result(result).to_dict()

    assert "legacy_next_core_cycle_influence_debug" not in view_dict
    assert "next_core_cycle_influence" not in view_dict
    assert "legacy_next_core_cycle_influence_debug" in view_dict["debug_refs"]
    assert view_dict["debug_refs"]["legacy_next_core_cycle_influence_debug"]["record_role"] == "legacy_debug"
    assert (
        view_dict["debug_refs"]["legacy_next_core_cycle_influence_debug"]["is_final_decision_source"]
        is False
    )


def test_decision_view_contains_claim_ceiling(tmp_path: Path) -> None:
    result = run_semantic_scenario(
        SCENARIO_DIR / "evidence_failure.txt",
        provider_mode="mock",
        evidence_log_path=tmp_path / "evidence.jsonl",
    )
    view = build_decision_view_from_semantic_result(result)
    report_path = tmp_path / "decision_view_report.md"
    build_decision_view_contract_report(report_path)
    report_text = report_path.read_text(encoding="utf-8")

    assert view.claim_ceiling == CLAIM_CEILING
    assert CLAIM_CEILING in report_text
    assert "does not prove consciousness" in report_text
    assert "proves consciousness" not in report_text
    assert "proves live autonomy" not in report_text
    assert "proves real semantic intelligence" not in report_text


def test_decision_view_has_single_final_selected_intention(tmp_path: Path) -> None:
    result = run_semantic_scenario(
        SCENARIO_DIR / "permission_failure.txt",
        provider_mode="mock",
        evidence_log_path=tmp_path / "permission.jsonl",
    )
    view_dict = build_decision_view_from_semantic_result(result).to_dict()
    final_paths = _find_after_selected_paths(view_dict, skip_debug=True)

    assert final_paths == (("canonical_decision", "after_selected_intention"),)
    assert view_dict["canonical_decision"]["after_selected_intention"]["goal"] == "ask_permission_or_defer"


def test_future_console_contract_requires_decision_view() -> None:
    main_source = Path("ego_desktop_lab/main.py").read_text(encoding="utf-8")
    contract = Path("docs/DECISION_VIEW_CONTRACT.md").read_text(encoding="utf-8")
    decision_view_source = Path("ego_desktop_lab/decision_view.py").read_text(encoding="utf-8")

    assert "build_decision_view_from_semantic_result" in main_source
    assert '_print_section("decision view"' in main_source
    assert "semantic_policy_calibration.after_selected_intention" not in main_source
    assert "CLI / future GUI / explanation" in contract
    assert "EvidenceRecord.canonical_decision -> DecisionView -> CLI / GUI / explanation" in contract
    assert "select_intention(" not in decision_view_source
    assert "run_semantic_policy_calibration_cycle(" not in decision_view_source


def _find_after_selected_paths(value: Any, *, skip_debug: bool, prefix: tuple[str, ...] = ()) -> tuple[tuple[str, ...], ...]:
    if isinstance(value, dict):
        paths: list[tuple[str, ...]] = []
        for key, item in value.items():
            if skip_debug and key == "debug_refs":
                continue
            current = (*prefix, str(key))
            if key == "after_selected_intention":
                paths.append(current)
            paths.extend(_find_after_selected_paths(item, skip_debug=skip_debug, prefix=current))
        return tuple(paths)
    if isinstance(value, list):
        paths: list[tuple[str, ...]] = []
        for index, item in enumerate(value):
            paths.extend(_find_after_selected_paths(item, skip_debug=skip_debug, prefix=(*prefix, str(index))))
        return tuple(paths)
    return ()
