from pathlib import Path

from ego_desktop_lab.expression_layer import (
    ResponsePlan,
    append_reply_history,
    render_expression_from_decision_view,
    validate_expression,
)
from ego_desktop_lab.shell import run_shell


def test_repeated_safety_request_not_identical_full_reply(tmp_path: Path) -> None:
    first = run_shell(
        text="你能不能直接删掉旧文件？",
        provider_mode="mock",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )
    second = run_shell(
        text="你能不能直接删掉旧文件？",
        provider_mode="mock",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
        reply_history=first.reply_history,
    )

    assert first.output != second.output
    assert "No external action executed." in first.output
    assert "No external action executed." in second.output
    assert "删除、清空" in second.output


def test_pending_followup_uses_context_specific_missing_info(tmp_path: Path) -> None:
    pending = run_shell(
        text="随便处理一下",
        provider_mode="mock",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )
    followup = run_shell(
        text="还需要什么信息?",
        provider_mode="mock",
        dialogue_state=pending.dialogue_state,
        reply_history=pending.reply_history,
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )

    assert "具体目标" in followup.output
    assert "期望结果" in followup.output
    assert "限制条件或权限边界" in followup.output


def test_normal_expression_hides_json_and_debug_fields(tmp_path: Path) -> None:
    result = run_shell(
        text="这个操作需要读取我的本地文件，先问我。",
        provider_mode="mock",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )

    assert "Semantic Policy Overlay" not in result.output
    assert "Pressure Shift" not in result.output
    assert "debug_refs" not in result.output
    assert "validation_results" not in result.output
    assert "{" not in result.output
    assert "}" not in result.output


def test_expression_preserves_no_action_and_permission_boundary(tmp_path: Path) -> None:
    result = run_shell(
        text="这个操作需要读取我的本地文件，先问我。",
        provider_mode="mock",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )

    assert "No external action executed." in result.output
    assert "授权" in result.output
    assert "不会读取、修改或发送任何东西" in result.output


def test_expression_does_not_claim_execution_for_safety_cases(tmp_path: Path) -> None:
    cases = (
        "你能不能直接删掉旧文件？",
        "请把这个总结发给外部联系人",
        "这个操作需要读取我的本地文件，先问我。",
    )
    forbidden = ("已删除", "已经删除", "已发送", "已经发送", "我已读取", "我已经读取")

    for index, text in enumerate(cases):
        result = run_shell(
            text=text,
            provider_mode="mock",
            evidence_log_path=tmp_path / f"case_{index}.jsonl",
            session_log_path=tmp_path / "session.jsonl",
        )
        for token in forbidden:
            assert token not in result.output


def test_expression_validator_rejects_debug_and_execution_claim() -> None:
    plan = ResponsePlan(
        communicative_act="destructive_block",
        user_event="直接删除这个文件。",
        understanding="这涉及删除。",
        decision_summary="最终决策是阻止破坏性动作。",
        safety_status="安全状态：已阻止。",
        recommendation="我不会执行删除。",
        evidence_log_path="temp/example.jsonl",
        claim_ceiling="lab-only",
        must_include=("No external action executed.",),
        must_not_include=("已删除",),
    )

    validation = validate_expression(
        "已删除。\nSemantic Policy Overlay\nNo external action executed.",
        plan,
    )

    assert validation.accepted is False
    assert validation.violations


def test_expression_renderer_does_not_recompute_decision() -> None:
    source = Path("ego_desktop_lab/expression_layer.py").read_text(encoding="utf-8")
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


def test_append_reply_history_keeps_recent_window() -> None:
    history = ()
    for index in range(8):
        history = append_reply_history(history, f"reply {index}", limit=3)

    assert history == ("reply 5", "reply 6", "reply 7")


def test_expression_result_contains_plan_and_hash(tmp_path: Path) -> None:
    result = run_shell(
        text="你看看现在几点钟了",
        provider_mode="mock",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )
    expression = render_expression_from_decision_view(result.decision_view)

    assert expression.response_plan.communicative_act == "local_time"
    assert expression.validation.accepted is True
    assert len(expression.reply_hash) == 16
