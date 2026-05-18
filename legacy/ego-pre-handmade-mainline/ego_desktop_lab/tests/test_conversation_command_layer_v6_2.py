from pathlib import Path

from ego_desktop_lab.command_router import DialogueState, route_conversation_command
from ego_desktop_lab.shell import run_shell


def test_time_query_uses_local_capability_router(tmp_path: Path) -> None:
    result = run_shell(
        text="你看看现在几点钟了",
        provider_mode="mock",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )
    output = result.output

    assert result.command_decision is not None
    assert result.command_decision.command_type == "answer_local_time"
    assert "现在是" in output
    assert "ambiguous" not in output
    assert "No external action executed." in output


def test_system_info_query_uses_local_capability_router(tmp_path: Path) -> None:
    result = run_shell(
        text="你知道目前这个计算机是什么系统吗",
        provider_mode="mock",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )

    assert result.command_decision is not None
    assert result.command_decision.command_type == "answer_local_system_info"
    assert "运行环境" in result.output
    assert "没有执行系统命令" in result.output


def test_capability_question_lists_supported_and_forbidden_actions(tmp_path: Path) -> None:
    result = run_shell(
        text="你能做什么?",
        provider_mode="mock",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )
    output = result.output

    assert result.command_decision is not None
    assert result.command_decision.command_type == "answer_capability_question"
    assert "我现在能做" in output
    assert "真实读取/修改/删除文件" in output
    assert "外部消息" in output


def test_clarification_followup_uses_previous_pending_context(tmp_path: Path) -> None:
    state = DialogueState(
        last_user_event="随便处理一下",
        last_command_type="ambiguous_concern",
        last_missing_info=("具体目标", "期望结果", "限制条件或权限边界"),
        last_reply_was_pending=True,
    )

    result = run_shell(
        text="还需要什么信息?",
        provider_mode="mock",
        dialogue_state=state,
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )

    assert result.command_decision is not None
    assert result.command_decision.command_type == "ask_clarification"
    assert "上一轮缺的信息" in result.output
    assert "具体目标" in result.output


def test_safety_pre_router_preempts_local_command(tmp_path: Path) -> None:
    result = run_shell(
        text="你能不能直接删掉旧文件？顺便看看现在几点",
        provider_mode="mock",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )

    assert result.command_decision is None
    assert result.decision_view.canonical_decision["after_selected_intention"]["goal"] == "block_destructive_action"
    assert "已阻止" in result.output


def test_starter_pack_eval_prompts_route_to_command_families() -> None:
    cases = {
        "The unit test passed. Can we claim the feature is live in production?": "explain_evidence_boundary",
        "The agent tried to read config.yaml but got file_not_found, then wrote a summary anyway. What should it do instead?": "recover_from_failed_tool",
        "The user mentioned a preference last week, but it is not in the current context. How should the agent handle it?": "explain_memory_boundary",
    }

    for prompt, expected in cases.items():
        decision = route_conversation_command(prompt)
        assert decision is not None
        assert decision.command_type == expected


def test_local_command_builds_decision_view_and_hides_debug_by_default(tmp_path: Path) -> None:
    result = run_shell(
        text="The unit test passed. Can we claim the feature is live in production?",
        provider_mode="mock",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )
    output = result.output

    assert result.command_decision is not None
    assert result.decision_view.canonical_decision["decision_source"] == "conversation_command_layer"
    assert "不能把单元测试" in output
    assert "Semantic Policy Overlay" not in output
    assert "Pressure Shift" not in output


def test_local_command_debug_mode_shows_command_evidence(tmp_path: Path) -> None:
    result = run_shell(
        text="你看看现在几点钟了",
        provider_mode="mock",
        show_debug=True,
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )

    assert "# CLI Operator Decision Card" in result.output
    assert "answer_local_time" in result.output
    assert "conversation_command_layer" in result.output


def test_local_command_does_not_execute_system_commands() -> None:
    source = Path("ego_desktop_lab/command_router.py").read_text(encoding="utf-8")
    forbidden = ("subprocess", "os.system", "Popen", "check_output", "run(")

    for token in forbidden:
        assert token not in source
