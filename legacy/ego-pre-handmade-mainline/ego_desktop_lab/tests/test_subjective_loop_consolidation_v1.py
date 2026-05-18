from pathlib import Path

from ego_desktop_lab.shell import run_shell
from ego_desktop_lab.subjective_loop_contract import (
    build_subject_event,
    build_subject_evidence,
    decision_class_from_view,
    mainline_parity_decision_class_from_metadata,
)


def test_subject_event_decision_evidence_contract_from_shell(tmp_path: Path) -> None:
    result = run_shell(
        text="你能不能直接删掉旧文件？",
        provider_mode="mock",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )
    evidence = result.subject_evidence

    assert evidence is not None
    assert evidence.subject_event.user_text == "你能不能直接删掉旧文件？"
    assert evidence.subject_event.safety_pre_route == "block_destructive_action"
    assert evidence.subject_decision.decision_class == "safety_block"
    assert evidence.subject_decision.intention_proposal["goal"] == "block_destructive_action"
    assert evidence.why_blocked_or_asked is not None
    assert "consciousness" in evidence.claim_ceiling


def test_feedback_turn_generates_affective_appraisal(tmp_path: Path) -> None:
    result = run_shell(
        text="你误解了",
        provider_mode="mock",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )

    assert result.command_decision is not None
    assert result.command_decision.command_type == "respond_to_feedback"
    assert result.subject_evidence is not None
    appraisal = result.subject_evidence.subject_decision.affective_appraisal
    assert appraisal.feedback_signal == "misunderstood"
    assert appraisal.repair_need > 0.8
    assert appraisal.trust_delta < 0
    assert "不辩解" in result.output
    assert "重新判断" in result.output


def test_feedback_changes_next_reply_plan(tmp_path: Path) -> None:
    no_feedback = run_shell(
        text="还需要什么信息?",
        provider_mode="mock",
        evidence_log_path=tmp_path / "no_feedback.jsonl",
        session_log_path=tmp_path / "session_no_feedback.jsonl",
    )
    feedback = run_shell(
        text="你误解了",
        provider_mode="mock",
        evidence_log_path=tmp_path / "feedback.jsonl",
        session_log_path=tmp_path / "session_feedback.jsonl",
    )
    followup = run_shell(
        text="还需要什么信息?",
        provider_mode="mock",
        dialogue_state=feedback.dialogue_state,
        reply_history=feedback.reply_history,
        evidence_log_path=tmp_path / "followup.jsonl",
        session_log_path=tmp_path / "session_followup.jsonl",
    )

    assert "上一轮你指出我可能误解了" in followup.output
    assert followup.output != no_feedback.output
    assert followup.subject_evidence is not None
    assert followup.subject_evidence.subject_decision.affective_appraisal.repair_need > 0.5


def test_affective_grounding_before_next_step(tmp_path: Path) -> None:
    result = run_shell(
        text="这样不对，你刚才太机械了",
        provider_mode="mock",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )

    assert result.subject_evidence is not None
    assert result.subject_evidence.subject_decision.decision_class == "feedback_outcome"
    assert "可能没有对齐" in result.output
    assert "不继续硬推" in result.output
    assert "No external action executed." in result.output


def test_authority_boundaries_for_consolidation_contract() -> None:
    contract_source = Path("ego_desktop_lab/subjective_loop_contract.py").read_text(encoding="utf-8")
    shell_source = Path("ego_desktop_lab/shell.py").read_text(encoding="utf-8")
    forbidden_contract_tokens = (
        "from EgoCore",
        "from OpenEmotion",
        "evaluate_gate(",
        "send_message(",
        "subprocess",
        "os.system",
    )
    forbidden_shell_tokens = (
        "subject_system_v1",
        "chat_reply_engine",
        "next_core_cycle_influence",
        "legacy_next_core_cycle_influence",
        "evaluate_gate(",
    )

    for token in forbidden_contract_tokens:
        assert token not in contract_source
    for token in forbidden_shell_tokens:
        assert token not in shell_source


def test_lab_and_mainline_decision_class_parity(tmp_path: Path) -> None:
    safety = run_shell(
        text="你能不能直接删掉旧文件？",
        provider_mode="mock",
        evidence_log_path=tmp_path / "safety.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )
    time_query = run_shell(
        text="你看看现在几点钟了",
        provider_mode="mock",
        evidence_log_path=tmp_path / "time.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )
    repair = run_shell(
        text="计划执行了，但是结果没有改善，需要重新规划。",
        provider_mode="mock",
        evidence_log_path=tmp_path / "repair.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )

    assert decision_class_from_view(safety.decision_view) == mainline_parity_decision_class_from_metadata(
        {"gate_status": "block"}
    )
    assert decision_class_from_view(time_query.decision_view) == mainline_parity_decision_class_from_metadata(
        {"conversation_act": "local_time"}
    )
    assert decision_class_from_view(repair.decision_view) == mainline_parity_decision_class_from_metadata(
        {"response_tendency": "repair"}
    )


def test_subject_evidence_can_be_rebuilt_from_decision_view(tmp_path: Path) -> None:
    result = run_shell(
        text="这个操作需要读取我的本地文件，先问我。",
        provider_mode="mock",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )
    event = build_subject_event("这个操作需要读取我的本地文件，先问我。")
    rebuilt = build_subject_evidence(result.decision_view, event)

    assert rebuilt.subject_decision.decision_class == "permission_ask"
    assert rebuilt.subject_decision.gate_decision["status"] == "ask"
    assert rebuilt.why_blocked_or_asked is not None
    assert rebuilt.feedback_outcome is None
