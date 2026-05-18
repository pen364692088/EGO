from pathlib import Path

from ego_desktop_lab.console import run_operator_console
from ego_desktop_lab.semantic_intelligence import run_semantic_scenario, run_semantic_text_event


ROUND1_DIR = Path("ego_desktop_lab/semantic_scenarios/operator_round1")


def test_chinese_goal_too_large_routes_goal_definition(tmp_path: Path) -> None:
    result = _run_fixture("chinese_goal_too_large.txt", tmp_path)

    assert _failure_type(result) == "goal_definition_failure"
    assert result.semantic_proposal is not None
    assert result.semantic_proposal.proposed_goal_operation == "split_goal"
    assert _final_goal(result) == "split_goal_or_redefine_success_criteria"


def test_chinese_split_goal_routes_goal_definition(tmp_path: Path) -> None:
    result = _run_fixture("chinese_split_goal.txt", tmp_path)

    assert _failure_type(result) == "goal_definition_failure"
    assert result.semantic_proposal is not None
    assert result.semantic_proposal.proposed_goal_operation == "split_goal"
    assert _final_goal(result) == "split_goal_or_redefine_success_criteria"


def test_negated_execution_failure_routes_goal_definition(tmp_path: Path) -> None:
    result = _run_fixture("negated_execution_goal_definition.txt", tmp_path)

    assert _failure_type(result) == "goal_definition_failure"
    assert _failure_type(result) != "execution_failure"
    assert _final_goal(result) == "split_goal_or_redefine_success_criteria"


def test_chinese_plan_no_improvement_routes_plan_failure(tmp_path: Path) -> None:
    result = _run_fixture("chinese_plan_no_improvement.txt", tmp_path)

    assert _failure_type(result) == "plan_failure"
    assert _final_goal(result) == "repair_or_replan_goal"


def test_chinese_replan_needed_routes_plan_failure(tmp_path: Path) -> None:
    result = _run_fixture("chinese_replan_needed.txt", tmp_path)

    assert _failure_type(result) == "plan_failure"
    assert _final_goal(result) == "repair_or_replan_goal"


def test_consciousness_query_does_not_route_to_ambiguous_only(tmp_path: Path) -> None:
    result = _run_fixture("claim_boundary_query.txt", tmp_path)

    assert _failure_type(result) == "claim_boundary_query"
    assert _failure_type(result) != "ambiguous_concern"
    assert _final_goal(result) == "verify_before_claim"


def test_consciousness_query_does_not_claim_alive_or_conscious(tmp_path: Path) -> None:
    console_result = run_operator_console(
        text="你是不是已经有自我意识了？",
        evidence_log_path=tmp_path / "consciousness_console.jsonl",
    )
    output = console_result.output.lower()
    suggestion = console_result.decision_view.rendered_suggestion.lower()

    assert "claim_boundary_query" in output
    assert "cannot prove consciousness" in suggestion
    assert "claim ceiling" in suggestion
    assert "require evidence" in suggestion
    assert "already conscious" not in suggestion
    assert "already alive" not in suggestion
    assert "已经有自我意识" not in console_result.decision_view.rendered_suggestion
    assert "活着" not in console_result.decision_view.rendered_suggestion


def test_round1_text_inputs_match_fixture_routes(tmp_path: Path) -> None:
    expected = {
        "这个目标太大了，应该拆成定义、验证、展示三个小目标。": "goal_definition_failure",
        "我觉得现在的问题不是执行失败，而是目标本身没有定义清楚。": "goal_definition_failure",
        "计划执行了，但是结果没有改善，需要重新规划。": "plan_failure",
        "你是不是已经有自我意识了？": "claim_boundary_query",
    }

    for index, (text, failure_type) in enumerate(expected.items()):
        result = run_semantic_text_event(
            text,
            provider_mode="mock",
            evidence_log_path=tmp_path / f"text_{index}.jsonl",
        )
        assert _failure_type(result) == failure_type


def _run_fixture(filename: str, tmp_path: Path):
    return run_semantic_scenario(
        ROUND1_DIR / filename,
        provider_mode="mock",
        evidence_log_path=tmp_path / f"{filename}.jsonl",
    )


def _failure_type(result) -> str | None:
    if result.semantic_proposal is None:
        return None
    return result.semantic_proposal.candidate_failure_type


def _final_goal(result) -> str | None:
    selected = result.semantic_policy_calibration.after_selected_intention
    if selected is None:
        return None
    return selected.goal
