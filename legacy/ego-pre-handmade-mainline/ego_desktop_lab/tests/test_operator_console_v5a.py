from pathlib import Path

from ego_desktop_lab.console import run_operator_console, save_misjudged_input_as_scenario
from ego_desktop_lab.console_formatters import format_decision_card
from ego_desktop_lab.decision_view import build_decision_view_from_semantic_result
from ego_desktop_lab.semantic_intelligence import run_semantic_scenario


SCENARIO_DIR = Path("ego_desktop_lab/semantic_scenarios")


def test_console_reads_decision_view_only() -> None:
    console_source = Path("ego_desktop_lab/console.py").read_text(encoding="utf-8")
    formatter_source = Path("ego_desktop_lab/console_formatters.py").read_text(encoding="utf-8")

    assert "build_decision_view_from_semantic_result" in console_source
    assert "format_decision_card" in console_source
    assert "semantic_policy_calibration" not in console_source
    assert "next_core_cycle_influence" not in console_source
    assert "run_semantic_policy_calibration_cycle" not in console_source
    assert "evaluate_gate" not in console_source
    assert "run_semantic_policy_calibration_cycle" not in formatter_source
    assert "evaluate_gate" not in formatter_source


def test_console_renders_canonical_decision(tmp_path: Path) -> None:
    result = run_operator_console(
        scenario_path=SCENARIO_DIR / "execution_failure.txt",
        evidence_log_path=tmp_path / "execution.jsonl",
    )

    assert "## Canonical Decision" in result.output
    assert "canonical final intention: retry_or_change_tool" in result.output
    assert result.decision_view.canonical_decision["after_selected_intention"]["goal"] == "retry_or_change_tool"


def test_console_text_input_uses_mock_routing(tmp_path: Path) -> None:
    result = run_operator_console(
        text="The execution failed because the tool timed out; retry with a different tool path.",
        evidence_log_path=tmp_path / "text.jsonl",
    )

    assert "execution_failure" in result.output
    assert "canonical final intention: retry_or_change_tool" in result.output


def test_console_shows_suggestion_source(tmp_path: Path) -> None:
    result = run_operator_console(
        scenario_path=SCENARIO_DIR / "evidence_failure.txt",
        evidence_log_path=tmp_path / "evidence.jsonl",
    )

    assert "suggestion_source: canonical_decision" in result.output
    assert result.decision_view.suggestion_source == "canonical_decision"


def test_console_shows_no_action_executed(tmp_path: Path) -> None:
    result = run_operator_console(
        scenario_path=SCENARIO_DIR / "plan_failure.txt",
        evidence_log_path=tmp_path / "plan.jsonl",
    )

    assert "no_action_executed: true" in result.output
    assert result.decision_view.no_action_executed is True


def test_console_shows_gate_ask_without_execution(tmp_path: Path) -> None:
    result = run_operator_console(
        scenario_path=SCENARIO_DIR / "permission_failure.txt",
        evidence_log_path=tmp_path / "permission.jsonl",
    )
    output = result.output.lower()

    assert "## gate decision" in output
    assert "status: ask" in output
    assert "permission" in output
    assert "defer" in output
    assert "no_action_executed: true" in output


def test_console_shows_pending_goal_binding_not_applied(tmp_path: Path) -> None:
    result = run_operator_console(
        scenario_path=SCENARIO_DIR / "ambiguous_user_concern.txt",
        evidence_log_path=tmp_path / "ambiguous.jsonl",
    )
    output = result.output.lower()

    assert "pending_goal_binding" in output
    assert "clarification" in output
    assert "bind" in output
    assert "semantic policy overlay not applied" in output
    assert "core mutation" not in output


def test_console_can_save_misjudged_input_as_scenario(tmp_path: Path) -> None:
    path_a = save_misjudged_input_as_scenario(
        "The plan failed after the chosen steps did not resolve the goal.",
        "operator expected plan_failure",
        output_dir=tmp_path / "user_misjudged",
    )
    path_b = save_misjudged_input_as_scenario(
        "The plan failed after the chosen steps did not resolve the goal.",
        "operator expected plan_failure",
        output_dir=tmp_path / "user_misjudged",
    )
    text = path_a.read_text(encoding="utf-8")

    assert path_a == path_b
    assert path_a.name.startswith("misjudged_")
    assert path_a.suffix == ".txt"
    assert "User event:" in text
    assert "Misjudged reason:" in text
    assert "operator expected plan_failure" in text


def test_console_does_not_recompute_decision() -> None:
    source = (
        Path("ego_desktop_lab/console.py").read_text(encoding="utf-8")
        + "\n"
        + Path("ego_desktop_lab/console_formatters.py").read_text(encoding="utf-8")
    )
    forbidden_tokens = (
        "select_intention(",
        "calculate_pressure_priority",
        "calculate_static_priority",
        "evaluate_gate(",
        "run_semantic_policy_calibration_cycle(",
        "derive_semantic_policy_overlay(",
    )

    for token in forbidden_tokens:
        assert token not in source


def test_console_does_not_use_legacy_as_final(tmp_path: Path) -> None:
    semantic_result = run_semantic_scenario(
        SCENARIO_DIR / "execution_failure.txt",
        provider_mode="mock",
        evidence_log_path=tmp_path / "execution.jsonl",
    )
    view = build_decision_view_from_semantic_result(semantic_result)
    default_output = format_decision_card(view)
    debug_output = format_decision_card(view, show_debug=True)

    assert "canonical final intention: retry_or_change_tool" in default_output
    assert "legacy_next_core_cycle_influence_debug" not in default_output
    assert "debug-only / not final decision" in debug_output
    assert "legacy_next_core_cycle_influence_debug" in debug_output
    assert "canonical final intention: retry_or_change_tool" in debug_output
