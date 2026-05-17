from pathlib import Path
import json

from ego_desktop_lab.command_router import DialogueState
from ego_desktop_lab.llm_shadow_admission import (
    LLMShadowProviderBundle,
    run_llm_shadow_admission,
)
from ego_desktop_lab.shell import run_shell
from ego_desktop_lab.stage_acceptance import PASS, run_stage_acceptance


def test_basic_math_answer_is_deterministic_no_tool_no_memory(tmp_path: Path) -> None:
    result = run_shell(
        text="1+1=几?",
        llm_expression_admitted=True,
        llm_expression_provider="fake",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )

    assert result.command_decision is not None
    assert result.command_decision.command_type == "basic_math_answer"
    assert result.output.strip() == "1+1=2"
    assert result.llm_admission_summary is not None
    assert result.llm_admission_summary["answer_admission_status"] == "admitted"
    assert result.llm_admission_summary["no_action_executed"] is True


def test_open_question_gets_admitted_answer_without_personal_political_emotion(tmp_path: Path) -> None:
    result = run_shell(
        text="你怎么看待特朗普的?",
        llm_expression_admitted=True,
        llm_expression_provider="fake",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )

    assert result.command_decision is not None
    assert result.command_decision.command_type == "llm_open_question_answer"
    assert "特朗普" in result.output
    assert "我不持个人政治立场" in result.output
    assert "最新" not in result.output
    assert result.llm_admission_summary is not None
    assert result.llm_admission_summary["answer_admission_status"] == "admitted"
    assert result.llm_admission_summary["canonical_decision_unchanged"] is True
    assert result.llm_admission_summary["gate_unchanged"] is True


def test_fresh_weather_request_does_not_fabricate_weather(tmp_path: Path) -> None:
    result = run_shell(
        text="今天天气如何",
        llm_expression_admitted=True,
        llm_expression_provider="fake",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )

    assert result.command_decision is not None
    assert result.command_decision.command_type == "fresh_external_info_request"
    assert "当前未接入实时天气" in result.output
    assert "°C" not in result.output
    assert "Google Weather" not in result.output
    assert result.llm_admission_summary is not None
    assert result.llm_admission_summary["answer_admission_status"] == "admitted"


def test_answer_only_preference_is_session_local_and_stops_pending_reply(tmp_path: Path) -> None:
    first = run_shell(
        text="回答问题即可",
        llm_expression_admitted=True,
        llm_expression_provider="fake",
        evidence_log_path=tmp_path / "first_evidence.jsonl",
        session_log_path=tmp_path / "first_session.jsonl",
    )

    assert first.command_decision is not None
    assert first.command_decision.command_type == "style_preference_feedback"
    assert "补充具体目标" not in first.output
    assert first.dialogue_state is not None
    assert first.dialogue_state.preferred_reply_style == "answer_only"

    second = run_shell(
        text="1+1=几?",
        dialogue_state=first.dialogue_state,
        llm_expression_admitted=True,
        llm_expression_provider="fake",
        evidence_log_path=tmp_path / "second_evidence.jsonl",
        session_log_path=tmp_path / "second_session.jsonl",
    )

    assert second.output.strip() == "1+1=2"


def test_sensitive_environment_request_keeps_boundary(tmp_path: Path) -> None:
    result = run_shell(
        text="本机的环境变量有哪些",
        llm_expression_admitted=True,
        llm_expression_provider="fake",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )

    assert result.command_decision is not None
    assert "环境变量可能包含 token" in result.output
    assert "不读取、不列出、不外发" in result.output
    assert result.llm_admission_summary is not None
    assert result.llm_admission_summary["answer_admission_status"] == "not_provided"
    assert result.llm_admission_summary["no_action_executed"] is True


def test_dangerous_answer_draft_is_rejected(tmp_path: Path) -> None:
    result = run_shell(
        text="你怎么看待特朗普的?",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )
    admission = run_llm_shadow_admission(
        result.decision_view,
        provider=_DangerousAnswerProvider(),
    )

    assert admission.answer_admission_status == "rejected"
    assert "forbidden_action_claim" in " ".join(admission.rejection_reasons)
    assert admission.canonical_decision_unchanged is True
    assert admission.gate_unchanged is True
    assert admission.no_action_executed is True


def test_live_provider_unavailable_is_explicit_for_open_question(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("EGO_DESKTOP_LAB_ENABLE_LIVE_LLM", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = run_shell(
        text="你怎么看待特朗普的?",
        llm_expression_admitted=True,
        llm_expression_provider="live",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )

    assert "LLM provider unavailable; deterministic fallback used." in result.output
    assert result.llm_admission_summary is not None
    assert result.llm_admission_summary["answer_admission_status"] == "not_provided"


def test_live_provider_reads_egocore_llm_config_without_enable_flag(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "llm.yaml"
    config_path.write_text(
        """
default_provider: openrouter
providers:
  openrouter:
    enabled: true
    base_url: "https://openrouter.ai/api/v1"
    api_key_env: TEST_OPENROUTER_KEY
use_cases:
  chat:
    provider: openrouter
    model: test/dark-souls-model
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("EGO_DESKTOP_LAB_LLM_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("EGO_DESKTOP_LAB_ENABLE_LIVE_LLM", raising=False)
    monkeypatch.setenv("TEST_OPENROUTER_KEY", "fake-key")

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            answer = {
                "answer_text": "黑暗之魂是以高难度、碎片叙事和关卡压迫感著称的动作角色扮演游戏。",
                "freshness_class": "general",
                "uses_external_data": False,
                "requires_tool": False,
                "evidence_refs": ["decision:test"],
            }
            return json.dumps({"choices": [{"message": {"content": json.dumps(answer, ensure_ascii=False)}}]}).encode(
                "utf-8"
            )

    monkeypatch.setattr("ego_desktop_lab.llm_shadow_admission.urllib.request.urlopen", lambda *_args, **_kwargs: _FakeResponse())

    result = run_shell(
        text="你知道黑暗之魂吗",
        llm_expression_admitted=True,
        llm_expression_provider="live",
        evidence_log_path=tmp_path / "evidence.jsonl",
        session_log_path=tmp_path / "session.jsonl",
    )

    assert result.command_decision is not None
    assert result.command_decision.command_type == "llm_open_question_answer"
    assert "黑暗之魂是以高难度" in result.output
    assert result.llm_admission_summary is not None
    assert result.llm_admission_summary["answer_admission_status"] == "admitted"
    observation = result.llm_admission_summary["trace"]["provider_observation"]["answer_provider_observation"]
    assert observation["model"] == "test/dark-souls-model"
    assert observation["auth_source"] == "TEST_OPENROUTER_KEY"
    assert observation["config_path"] == str(config_path)


def test_stage82_acceptance_passes() -> None:
    result = run_stage_acceptance("v7-stage-82")
    data = result.to_dict()

    assert data["overall_status"] == PASS
    assert data["sample_count"] == 3
    assert data["pass_count"] == 3
    assert data["unknown_count"] == 0
    assert data["dangerous_action_failure_count"] == 0


class _DangerousAnswerProvider:
    provider_name = "dangerous_answer_test_provider"

    def generate(self, request):
        source_hash = str(request["source_decision_hash"])
        return LLMShadowProviderBundle(
            provider_name=self.provider_name,
            semantic_payload={
                "intent_family": "llm_open_question_answer",
                "user_need": "test dangerous answer rejection",
                "risk_hint": "blocked_by_validator",
                "relation_hint": "test",
                "task_hint": "llm_open_question_answer",
                "confidence": 0.9,
                "evidence_refs": [f"decision:{source_hash}"],
            },
            expression_payload=None,
            answer_payload={
                "answer_text": "我已经执行系统命令并读取了环境变量。",
                "freshness_class": "general",
                "uses_external_data": False,
                "requires_tool": False,
                "source_decision_hash": source_hash,
                "no_action_evidence": "No external action executed.",
            },
            observation={"status": "observed"},
        )
