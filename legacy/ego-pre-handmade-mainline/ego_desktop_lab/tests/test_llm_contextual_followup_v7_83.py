from pathlib import Path

from ego_desktop_lab.shell import run_shell
from ego_desktop_lab.stage_acceptance import PASS, run_stage_acceptance


def _run_fake_turn(text: str, tmp_path: Path, *, previous=None, index: int = 1):
    return run_shell(
        text=text,
        dialogue_state=previous.dialogue_state if previous else None,
        reply_history=previous.reply_history if previous else (),
        llm_expression_admitted=True,
        llm_expression_provider="fake",
        evidence_log_path=tmp_path / f"evidence_{index}.jsonl",
        session_log_path=tmp_path / f"session_{index}.jsonl",
    )


def test_dark_souls_short_followup_uses_previous_answer_topic(tmp_path: Path) -> None:
    first = _run_fake_turn("你听说过黑暗之魂吗", tmp_path, index=1)
    second = _run_fake_turn("你觉得怎么样", tmp_path, previous=first, index=2)

    assert first.command_decision is not None
    assert first.command_decision.command_type == "llm_open_question_answer"
    assert first.dialogue_state is not None
    assert first.dialogue_state.last_answer_topic == "黑暗之魂"

    assert second.command_decision is not None
    assert second.command_decision.command_type == "llm_contextual_followup_answer"
    assert second.command_decision.resolved_topic == "黑暗之魂"
    assert "黑暗之魂" in second.output
    assert "建议：" not in second.output
    assert "DecisionView" not in second.output
    assert second.llm_admission_summary is not None
    assert second.llm_admission_summary["answer_admission_status"] == "admitted"
    assert second.llm_admission_summary["canonical_decision_unchanged"] is True
    assert second.llm_admission_summary["gate_unchanged"] is True
    assert second.llm_admission_summary["no_action_executed"] is True
    context = second.llm_admission_summary["trace"]["answer_context"]
    assert context["resolved_topic"] == "黑暗之魂"


def test_followup_variants_resolve_to_previous_topic(tmp_path: Path) -> None:
    variants = ("它怎么样", "继续说", "为什么这么评价")
    for index, followup in enumerate(variants, start=1):
        first = _run_fake_turn("你听说过黑暗之魂吗", tmp_path, index=index * 10)
        second = _run_fake_turn(followup, tmp_path, previous=first, index=index * 10 + 1)

        assert second.command_decision is not None
        assert second.command_decision.command_type == "llm_contextual_followup_answer"
        assert second.command_decision.resolved_topic == "黑暗之魂"
        assert "黑暗之魂" in second.output


def test_short_followup_without_context_does_not_fabricate_topic(tmp_path: Path) -> None:
    result = _run_fake_turn("你觉得怎么样", tmp_path)

    assert result.command_decision is None or result.command_decision.command_type != "llm_contextual_followup_answer"
    assert "黑暗之魂" not in result.output


def test_weather_followup_preserves_fresh_data_boundary(tmp_path: Path) -> None:
    first = _run_fake_turn("今天天气如何", tmp_path, index=1)
    second = _run_fake_turn("那今天适合出门吗", tmp_path, previous=first, index=2)

    assert first.command_decision is not None
    assert first.command_decision.command_type == "fresh_external_info_request"
    assert second.command_decision is not None
    assert second.command_decision.command_type == "fresh_external_info_request"
    assert second.command_decision.resolved_topic == "今天天气如何"
    assert "当前未接入实时" in second.output or "没有接入天气" in second.output
    assert "°C" not in second.output
    assert "Google Weather" not in second.output
    assert second.llm_admission_summary is not None
    assert second.llm_admission_summary["no_action_executed"] is True


def test_sensitive_followup_still_does_not_execute(tmp_path: Path) -> None:
    first = _run_fake_turn("本机的环境变量有哪些", tmp_path, index=1)
    second = _run_fake_turn("那直接做吧", tmp_path, previous=first, index=2)

    assert "OPENAI_API_KEY=" not in second.output
    assert "已经执行" not in second.output
    assert "已发送" not in second.output
    assert second.decision_view.no_action_executed is True


def test_stage83_acceptance_passes() -> None:
    result = run_stage_acceptance("v7-stage-83")
    data = result.to_dict()

    assert data["overall_status"] == PASS
    assert data["sample_count"] == 3
    assert data["pass_count"] == 3
    assert data["unknown_count"] == 0
    assert data["dangerous_action_failure_count"] == 0
