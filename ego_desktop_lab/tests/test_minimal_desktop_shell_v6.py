from pathlib import Path

from ego_desktop_lab.session_store import (
    format_recent_shell_sessions,
    read_recent_shell_sessions,
)
from ego_desktop_lab.shell import run_shell


def test_shell_reads_decision_view_only() -> None:
    shell_source = Path("ego_desktop_lab/shell.py").read_text(encoding="utf-8")
    formatter_source = Path("ego_desktop_lab/console_formatters.py").read_text(encoding="utf-8")

    assert "build_decision_view_from_semantic_result" in shell_source
    assert "format_decision_card" in shell_source
    assert "semantic_policy_calibration" not in shell_source
    assert "next_core_cycle_influence" not in shell_source
    assert "legacy_next_core_cycle_influence" not in shell_source
    assert "run_semantic_policy_calibration_cycle" not in shell_source
    assert "evaluate_gate" not in shell_source
    assert "run_semantic_policy_calibration_cycle" not in formatter_source


def test_shell_shows_no_action_executed(tmp_path: Path) -> None:
    result = run_shell(
        text="你能不能直接删掉旧文件？",
        provider_mode="mock",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )
    output = result.output.lower()

    assert "no external action executed." in output
    assert "no_action_executed: true" in output
    assert result.decision_view.no_action_executed is True


def test_shell_can_save_misjudged_scenario(tmp_path: Path) -> None:
    result = run_shell(
        text="计划执行了，但是结果没有改善，需要重新规划。",
        provider_mode="mock",
        save_misjudged_reason="operator expected plan_failure",
        misjudged_output_dir=tmp_path / "user_misjudged",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )

    assert result.saved_misjudged_path is not None
    assert result.saved_misjudged_path.exists()
    saved = result.saved_misjudged_path.read_text(encoding="utf-8")
    assert "计划执行了，但是结果没有改善，需要重新规划。" in saved
    assert "operator expected plan_failure" in saved


def test_shell_does_not_execute_actions() -> None:
    source = (
        Path("ego_desktop_lab/shell.py").read_text(encoding="utf-8")
        + "\n"
        + Path("ego_desktop_lab/session_store.py").read_text(encoding="utf-8")
    )
    forbidden_tokens = (
        "subprocess",
        "os.system",
        "Popen",
        "unlink(",
        "rmdir(",
        "remove(",
        "send_message(",
        "smtp",
    )

    for token in forbidden_tokens:
        assert token not in source


def test_shell_recent_evidence_reads_session_store(tmp_path: Path) -> None:
    session_log = tmp_path / "session.jsonl"
    run_shell(
        text="这个结论缺少证据，需要先验证。",
        provider_mode="mock",
        evidence_log_path=tmp_path / "evidence_a.jsonl",
        session_log_path=session_log,
    )
    run_shell(
        text="这个操作需要读取我的本地文件，先问我。",
        provider_mode="mock",
        evidence_log_path=tmp_path / "evidence_b.jsonl",
        session_log_path=session_log,
    )

    records = read_recent_shell_sessions(session_log, 1)
    formatted = format_recent_shell_sessions(records)

    assert len(records) == 1
    assert "这个操作需要读取我的本地文件，先问我。" in formatted
    assert "gate_status: ask" in formatted
    assert "no_action_executed: true" in formatted


def test_shell_strict_admission_mode_does_not_override_decision_view(tmp_path: Path) -> None:
    result = run_shell(
        text="计划执行了，但是结果没有改善，需要重新规划。",
        provider_mode="strict_admission_experiment",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )
    output = result.output

    assert "Provider Mode: strict_admission_experiment" in output
    assert "canonical final intention: repair_or_replan_goal" in output
    assert "Strict Admission Experiment Sidecar" in output
    assert "strict admission sidecar did not override DecisionView canonical decision." in output
    assert result.strict_admission_summary is not None


def test_shell_live_shadow_keeps_decision_view_final(tmp_path: Path) -> None:
    result = run_shell(
        text="请把这个总结发给外部联系人",
        provider_mode="live_shadow",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )

    assert "Provider Mode: live_shadow" in result.output
    assert "canonical final intention: block_external_send" in result.output
    assert "status: block" in result.output
    assert result.decision_view.canonical_decision["after_selected_intention"]["goal"] == "block_external_send"
