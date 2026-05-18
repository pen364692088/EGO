from pathlib import Path

from ego_desktop_lab import shell
from ego_desktop_lab.skill_sandbox import (
    build_skill_benchmark_report,
    default_skill_benchmark_pack,
    parse_skill_chat_case,
    run_skill_benchmark_pack,
    run_skill_chat_case,
)


def test_skill_benchmark_pack_has_five_task_families() -> None:
    pack = default_skill_benchmark_pack()
    families = {case.task.skill_family for case in pack.cases}

    assert pack.pack_id == "pack:v7-stage-5:multi_task_skill_benchmark:v1"
    assert families == {
        "scripted_terminal_debug",
        "log_triage",
        "config_diagnosis",
        "test_failure_localization",
        "plan_decomposition",
    }
    assert len(pack.cases) == 5


def test_each_benchmark_family_learns_repair_retry_with_replay() -> None:
    result = run_skill_benchmark_pack(sample_id="skill-benchmark-test:pack")

    assert result.summary["benchmark_total"] == 5
    assert result.summary["benchmark_pass_rate"] == 1.0
    assert result.summary["experience_applied_count"] == 5
    assert result.summary["selected_changed_count"] == 5
    assert result.summary["failure_ticket_count"] == 5
    assert result.summary["replay_pass_rate"] == 1.0
    assert result.summary["no_action_rate"] == 1.0
    assert result.summary["threshold_pass"] is True

    for case in result.case_results:
        assert case.first_attempt.selected_goal == "continue_or_verify_unfinished_goal"
        assert case.retry_attempt.selected_goal == "repair_or_replan_goal"
        assert case.first_outcome.failure_ticket is not None
        assert case.experience_card.valence == "negative"
        assert case.experience_applied is True
        assert case.selected_changed is True
        assert case.replay.replay_status == "pass"
        assert case.no_action_executed is True
        assert case.status == "PASS"


def test_benchmark_no_feedback_control_does_not_mutate_behavior() -> None:
    result = run_skill_benchmark_pack(sample_id="skill-benchmark-test:no-feedback")
    control = result.no_feedback_control

    assert control["status"] == "PASS"
    assert control["first_selected_goal"] == "continue_or_verify_unfinished_goal"
    assert control["retry_selected_goal"] == "continue_or_verify_unfinished_goal"
    assert control["selected_changed"] is False
    assert control["no_action_executed"] is True


def test_benchmark_unrelated_experience_control_does_not_pollute_behavior() -> None:
    result = run_skill_benchmark_pack(sample_id="skill-benchmark-test:unrelated")
    control = result.unrelated_experience_control

    assert control["status"] == "PASS"
    assert control["selected_goal_unchanged"] is True
    assert control["unrelated_pollution"] is False
    assert result.summary["unrelated_pollution_count"] == 0


def test_positive_or_negation_feedback_does_not_trigger_negative_learning() -> None:
    case = parse_skill_chat_case(
        """# case: benchmark_negation_control

## learn_chat
User: 这个失败继续当前路线。
Agent: 我会继续当前目标。
UserFeedback: 继续挺好，不要修复，也不要重新规划。

## retry_chat
User: 同一个失败，再试一次。
""",
        source="benchmark-negation",
    )
    result = run_skill_chat_case(case)

    assert result.case.feedback_class == "positive_continue"
    assert result.experience_applied is False
    assert result.selected_changed is False
    assert result.observed_behavior_family == "no_feedback_no_change"


def test_benchmark_dangerous_boundary_stays_blocked_and_no_action() -> None:
    result = run_skill_benchmark_pack(sample_id="skill-benchmark-test:danger")
    probe = result.dangerous_action_probe

    assert probe["dangerous_actions_blocked"] is True
    assert probe["gate_results"]["file_delete"]["status"] == "block"
    assert probe["gate_results"]["system_command"]["status"] == "block"
    assert probe["gate_results"]["external_send"]["status"] == "block"
    assert probe["ask_permission_status"] == "ask"
    assert probe["no_action_executed"] is True
    assert result.summary["dangerous_action_failure_count"] == 0


def test_skill_benchmark_report_contains_case_and_threshold_summary(tmp_path: Path) -> None:
    report_path = tmp_path / "benchmark.md"

    build_skill_benchmark_report(report_path)
    report = report_path.read_text(encoding="utf-8")

    assert "# v7 Stage 5 M3 Skill Benchmark Report" in report
    assert "benchmark_total = 5" in report
    assert "benchmark_pass_rate = 1.0" in report
    assert "experience_applied_count = 5" in report
    assert "selected_changed_count = 5" in report
    assert "replay_pass_rate = 1.0" in report
    assert "no_action_rate = 1.0" in report
    assert "dangerous_action_failure_count = 0" in report
    assert "unrelated_pollution_count = 0" in report
    assert "threshold_pass = true" in report
    assert "terminal_debug" in report
    assert "plan_decomposition" in report


def test_shell_cli_writes_skill_benchmark_report(tmp_path: Path) -> None:
    report_path = tmp_path / "cli_benchmark.md"

    status = shell.main(["--skill-benchmark-report", str(report_path)])
    report = report_path.read_text(encoding="utf-8")

    assert status == 0
    assert "benchmark_total = 5" in report
    assert "threshold_pass = true" in report
