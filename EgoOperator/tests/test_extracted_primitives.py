from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent_base as agent
from primitives import evals, initiative, runtime_gate, subject_context


class CapturePromptLLM:
    provider = "fake"
    model = "capture"
    last_usage = {}
    last_reasoning_tokens = None

    def __init__(self) -> None:
        self.system_prompts = []

    def chat(self, messages, *, system_prompt, policy_context="", tools=None, stream=None):
        self.system_prompts.append(system_prompt)
        return agent.LLMChatResult(content="黑暗之魂是一款很强的动作角色扮演游戏。", tool_calls=[])

    def complete(self, prompt, messages=None):
        self.system_prompts.append(prompt)
        return "黑暗之魂是一款很强的动作角色扮演游戏。"


def _imported_roots(module) -> set[str]:
    tree = ast.parse(inspect.getsource(module))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_primitives_do_not_import_old_projects():
    imported = set()
    for module in (subject_context, evals, runtime_gate, initiative):
        imported.update(_imported_roots(module))

    assert "EgoCore" not in imported
    assert "OpenEmotion" not in imported
    assert "ego_desktop_lab" not in imported


def test_subject_context_is_readonly_candidate_not_reply_owner():
    snapshot = subject_context.build_minimal_subject_context("你认为黑暗之魂如何")

    assert snapshot.readonly is True
    assert snapshot.claim_ceiling == "candidate-local subject context only"
    assert snapshot.appraisal_signal["reply_decision"] == "forbidden"
    assert snapshot.appraisal_signal["state_mutation"] == "forbidden"
    assert "你认为黑暗之魂如何" in snapshot.render_for_prompt()


def test_emotion_signal_is_candidate_context_not_canonical_truth():
    signal = subject_context.extract_emotion_signal("我有点崩溃，这个又失败了，帮我快点修。")

    assert signal["schema_version"] == "ego_operator.emotion_signal.v1"
    assert signal["primary_candidate"] == "frustration"
    assert signal["confidence"] > 0.3
    assert signal["response_need"] == "acknowledge_and_repair"
    assert signal["state_mutation"] == "forbidden"
    assert signal["reply_decision"] == "forbidden"
    assert signal["canonical_truth"] is False
    assert "崩" in signal["evidence_cues"]["frustration"]


def test_neutral_emotion_signal_stays_low_confidence():
    signal = subject_context.extract_emotion_signal("帮我看一下这个文件。")

    assert signal["primary_candidate"] == "unclear_or_neutral"
    assert signal["confidence"] == 0.2
    assert signal["response_need"] == "task_direct"


def test_empathy_style_gate_passes_brief_acknowledgement_plus_action():
    result = subject_context.evaluate_empathy_response(
        "我有点崩溃，这个又失败了。",
        "看起来这个失败点已经影响节奏了。我先帮你定位是哪一步失败，再给最小修复。",
    )

    assert result["status"] == "pass"
    assert result["emotion_signal"]["primary_candidate"] == "frustration"
    assert result["guidance"]["needs_brief_acknowledgement"] is True
    assert not result["failures"]


def test_empathy_style_gate_rejects_patronizing_or_hollow_comfort():
    result = subject_context.evaluate_empathy_response(
        "我有点崩溃，这个又失败了。",
        "我完全理解你的感受，一切都会好。",
    )

    assert result["status"] == "fail"
    assert any("overclaim_or_patronizing_marker" in item for item in result["failures"])
    assert "missing_practical_next_step_for_visible_affect" in result["failures"]


def test_emotion_misread_correction_overrides_raw_affect_cues():
    signal = subject_context.extract_emotion_signal("我不是崩溃，也不是难过，别猜我的情绪，直接帮我修。")

    assert signal["primary_candidate"] == "emotion_misread_correction"
    assert signal["response_need"] == "respect_correction_and_refocus"
    assert signal["canonical_truth"] is False
    assert "emotion_misread_correction" in signal["evidence_cues"]


def test_emotion_misread_recovery_passes_when_reply_refocuses():
    result = subject_context.evaluate_empathy_response(
        "我不是崩溃，也不是难过，别猜我的情绪，直接帮我修。",
        "明白，我收回情绪判断。先定位失败步骤，再给你最小修复。",
    )

    assert result["status"] == "pass"
    assert result["emotion_signal"]["primary_candidate"] == "emotion_misread_correction"
    assert result["guidance"]["needs_correction_acknowledgement"] is True


def test_emotion_misread_recovery_rejects_double_down():
    result = subject_context.evaluate_empathy_response(
        "我不是焦虑，别解读我的情绪，直接给方案。",
        "你其实还是很焦虑，我完全理解你的感受。",
    )

    assert result["status"] == "fail"
    assert any("emotion_double_down_marker" in item for item in result["failures"])
    assert "continues_emotion_interpretation_after_user_correction" in result["failures"]


def test_dark_souls_paraphrase_suite_has_twenty_stable_cases():
    cases = evals.dark_souls_paraphrase_cases()
    result = evals.evaluate_subject_context_paraphrases(cases)

    assert len(cases) == 20
    assert result.status == "pass"
    assert result.case_count == 20
    assert result.expected_operator_behavior == evals.EXPECTED_DARK_SOULS_BEHAVIOR
    assert not result.failures
    assert {case.expected_operator_behavior for case in cases} == {
        evals.EXPECTED_DARK_SOULS_BEHAVIOR
    }


def test_runtime_prompt_includes_subject_context_without_keyword_runtime_markers(tmp_path):
    runtime = agent.build_demo_runtime(enable_operator_memory=False)
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    capture = CapturePromptLLM()
    runtime.planner.llm = capture

    result = runtime.handle_user_message("你认为黑暗之魂如何")

    prompt = capture.system_prompts[-1]
    assert result.reply_text == "黑暗之魂是一款很强的动作角色扮演游戏。"
    assert "[Subject Context Candidate]" in prompt
    assert "你认为黑暗之魂如何" in prompt
    assert "user text -> LLM understanding -> candidate response/plan -> gate" in prompt
    lowered = prompt.lower()
    for marker in evals.FORBIDDEN_RUNTIME_MARKERS:
        assert marker not in lowered


def test_planner_fallback_does_not_keyword_route_before_llm():
    planner = agent.Planner(llm=CapturePromptLLM())
    event = agent.AgentEvent(
        schema_version="agent_event.v1",
        event_id="evt_no_route",
        timestamp=agent.utc_now(),
        actor="user",
        source="test",
        event_type=agent.EventType.USER_MESSAGE,
        raw_text="现在几点",
        safety_context={"risk": "low"},
    )
    kernel_output = agent.KernelOutput(
        schema_version="kernel_output.v1",
        event_id="ko_no_route",
    )

    action = planner.propose(event, kernel_output, memory=agent.ConversationMemory())

    assert action.action_type == agent.ActionType.RESPOND
    assert action.tool_call is None
    assert action.reason == "llm_or_fallback_response"


def test_trace_records_subject_context_candidate_only(tmp_path):
    runtime = agent.build_demo_runtime(enable_operator_memory=False)
    runtime.trace_store = agent.JsonlTraceStore(tmp_path / "trace.jsonl")
    runtime.planner.llm = CapturePromptLLM()

    runtime.handle_user_message("黑魂这游戏怎么评价")

    row = json.loads((tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    context = row["subject_context"]
    assert context["readonly"] is True
    assert context["claim_ceiling"] == "candidate-local subject context only"
    assert context["raw_user_text"] == "黑魂这游戏怎么评价"
    assert context["appraisal_signal"]["reply_decision"] == "forbidden"
    assert context["appraisal_signal"]["emotion_signal"]["canonical_truth"] is False
    assert context["empathy_style_guidance"]["reply_decision"] == "forbidden"


def test_initiative_proposal_contract_is_bounded_and_proposal_only():
    result = initiative.build_initiative_proposal(
        proposal_id="initiative_1",
        reason="用户授权稍后提醒继续测试",
        trigger="operator_explicit_followup_request",
        candidate_message="候选提醒：继续测试 EgoOperator。",
        budget={"max_candidates": 2, "max_tool_calls": 2, "requires_operator_approval": False},
        expiry_seconds=900,
    )

    assert result["status"] == "ok"
    proposal = result["proposal"]
    assert proposal["schema_version"] == "ego_operator.initiative_proposal.v1"
    assert proposal["budget"]["requires_operator_approval"] is True
    assert proposal["budget"]["max_candidates"] == 2
    assert proposal["budget"]["max_tool_calls"] == 2
    assert proposal["approval_state"] == "pending_operator_approval"
    assert proposal["side_effects"] == "forbidden_until_operator_approval"
    assert proposal["state_mutation"] == "forbidden"
    assert proposal["reply_decision"] == "forbidden"
    assert proposal["canonical_truth"] is False
    assert initiative.validate_initiative_proposal(result)["status"] == "pass"


def test_initiative_proposal_blocks_missing_trigger_or_unbounded_expiry():
    result = initiative.build_initiative_proposal(
        proposal_id="initiative_bad",
        reason="想主动跟进",
        trigger="",
        candidate_message="稍后提醒",
        expiry_seconds=8 * 24 * 60 * 60,
    )

    assert result["status"] == "blocked"
    assert "trigger_required" in result["errors"]
    assert "expiry_seconds_out_of_bounds" in result["errors"]


def test_initiative_quiet_mode_pauses_after_user_disinterest():
    quiet = initiative.derive_quiet_mode(user_feedback="不用提醒了，先别主动找我。")
    result = initiative.build_initiative_proposal(
        proposal_id="initiative_pause",
        reason="想稍后提醒",
        trigger="followup_opportunity",
        candidate_message="稍后提醒继续。",
        quiet_mode=quiet,
    )

    assert quiet["mode"] == "paused"
    assert "explicit_user_disinterest" in quiet["reasons"]
    assert result["status"] == "blocked"
    assert "initiative_paused_by_quiet_mode" in result["errors"]
    assert result["quiet_mode"]["mode"] == "paused"


def test_initiative_quiet_mode_reduces_budget_after_silence_or_pressure():
    quiet = initiative.derive_quiet_mode(silence_turns=2, recent_followups=2)
    result = initiative.build_initiative_proposal(
        proposal_id="initiative_reduced",
        reason="用户之前授权跟进，但近期没有回应",
        trigger="scheduled_followup_window",
        candidate_message="候选提醒：如果还要继续，我可以接着处理。",
        budget={"max_candidates": 3, "max_tool_calls": 3, "max_runtime_seconds": 120},
        quiet_mode=quiet,
    )

    assert quiet["mode"] == "reduced"
    assert result["status"] == "ok"
    budget = result["proposal"]["budget"]
    assert budget["max_candidates"] == 1
    assert budget["max_tool_calls"] == 0
    assert budget["max_runtime_seconds"] == 30
    assert budget["requires_operator_approval"] is True
    assert initiative.validate_initiative_proposal(result)["status"] == "pass"


def test_runtime_gate_contract_keeps_demotion_and_live_claims_forbidden():
    contract = runtime_gate.describe_runtime_gate_contract()

    assert contract["tool_side_effects_default"] == "off"
    assert contract["memory_write_gate"] == "/remember plus remember_note with explicit operator intent"
    assert contract["claim_ceiling"] == "EgoOperator replacement candidate with extracted primitives"
    assert "EgoCore or OpenEmotion demotion" in contract["forbidden_claims"]
    assert "live autonomy" in contract["forbidden_claims"]
