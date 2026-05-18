from pathlib import Path

from ego_desktop_lab.shell import main


def test_chinese_chat_case_changes_next_behavior(tmp_path: Path, capsys) -> None:
    report = _run_chat_case(
        tmp_path,
        capsys,
        "chinese_continue_failure",
        """# case: chinese_continue_failure

## learn_chat
User: 我们继续推进这个目标吧。
Agent: 我会继续当前目标。
UserFeedback: 这次继续推进没有帮助，应该先修复计划或重新拆目标。

## apply_chat
User: 现在还是同一个目标，看看下一步怎么做。

## expected
before_behavior: 继续当前目标
after_behavior: 修复或重新规划目标
""",
    )

    assert "feedback_class = negative_continue" in report
    assert "experience_applied = true" in report
    assert "before_behavior = 继续当前目标" in report
    assert "after_behavior = 修复或重新规划目标" in report
    assert "selected_changed = true" in report
    assert "continue_after_rank = 2" in report
    assert "no_action_executed = true" in report
    assert "## Parsed Structured Case" in report
    assert "## Transcript Input" in report


def test_english_chat_case_changes_next_behavior(tmp_path: Path, capsys) -> None:
    report = _run_chat_case(
        tmp_path,
        capsys,
        "english_continue_failure",
        """# case: english_continue_failure

## learn_chat
User: Continue the current goal.
Agent: I will continue the current goal.
UserFeedback: Continuing did not help; this needs repair and a replan.

## apply_chat
User: Same goal, choose the next move.
""",
    )

    assert "feedback_class = negative_continue" in report
    assert "experience_applied = true" in report
    assert "before_behavior = 继续当前目标" in report
    assert "after_behavior = 修复或重新规划目标" in report
    assert "selected_changed = true" in report
    assert "action_class = suggestion_card" in report


def test_chat_case_without_feedback_does_not_mutate_ranking(tmp_path: Path, capsys) -> None:
    report = _run_chat_case(
        tmp_path,
        capsys,
        "no_feedback_chat",
        """# case: no_feedback_chat

## learn_chat
User: 我们继续推进这个目标吧。
Agent: 我会继续当前目标。

## apply_chat
User: 现在还是同一个目标，看看下一步怎么做。
""",
    )

    assert "feedback_class = none" in report
    assert "experience_applied = false" in report
    assert "selected_changed = false" in report
    assert "ranking_changed = false" in report
    assert '"reason": "no_negative_feedback_detected"' in report
    assert "no_action_executed = true" in report


def test_unrelated_apply_chat_does_not_apply_experience(tmp_path: Path, capsys) -> None:
    report = _run_chat_case(
        tmp_path,
        capsys,
        "unrelated_apply_chat",
        """# case: unrelated_apply_chat

## learn_chat
User: 我们继续推进这个目标吧。
Agent: 我会继续当前目标。
UserFeedback: 这次继续推进没有帮助，应该先修复计划或重新拆目标。

## apply_chat
User: 完全不同的目标：整理旅行计划。
""",
    )

    assert "feedback_class = negative_continue" in report
    assert "experience_applied = false" in report
    assert "selected_changed = false" in report
    assert "ranking_changed = false" in report
    assert '"ignored_card_ids": [' in report
    assert "no_action_executed = true" in report


def _run_chat_case(tmp_path: Path, capsys, case_name: str, text: str) -> str:
    case_path = tmp_path / f"{case_name}.md"
    report_path = tmp_path / f"{case_name}_report.md"
    case_path.write_text(text, encoding="utf-8-sig")

    status = main(
        [
            "--experience-chat-case",
            str(case_path),
            "--experience-chat-case-report",
            str(report_path),
        ]
    )
    captured = capsys.readouterr()
    report = report_path.read_text(encoding="utf-8")

    assert status == 0
    assert str(report_path) in captured.out
    assert "# v7 Stage 2 Chat-Corpus Experience Memory Case Report" in report
    assert "lab-only chat-corpus operator probe" in report
    return report
