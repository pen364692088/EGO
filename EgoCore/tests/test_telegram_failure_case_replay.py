from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from app.openemotion_hooks.subject_gate import SubjectGateVerdict
from app.response_contract import apply_output_check, build_direct_response_plan
from app.telegram_bot import TelegramBot
from app.telegram_runtime_result import TelegramTurnReply, TelegramTurnResult


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "telegram_failure_cases"


class DummyChat:
    id = 8420019401
    type = "private"


class DummyUser:
    id = 8420019401
    username = "moonlight"


class DummyMessage:
    def __init__(self, text: str, message_id: int):
        self.text = text
        self.message_id = message_id
        self.reply_to_message = None
        self.sent: List[str] = []

    async def reply_text(self, text, parse_mode=None):
        self.sent.append(text)
        return None


class DummyUpdate:
    def __init__(self, text: str, message_id: int):
        self.message = DummyMessage(text, message_id)
        self.effective_chat = DummyChat()
        self.effective_user = DummyUser()


class AllowingSubjectGate:
    def process_ingress(self, **kwargs):
        return SubjectGateVerdict.allow(stage="ingress")

    def process_finalized_result(self, **kwargs):
        return SubjectGateVerdict.allow(stage="finalized_result")

    def capture_response_plan(self, **kwargs):
        return SubjectGateVerdict.allow(stage="response_plan")

    def finalize_host_owned_result(self, **kwargs):
        return SubjectGateVerdict.allow(stage="response_plan")


def _load_cases() -> List[Dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(FIXTURE_DIR.glob("*.json"))
    ]


@pytest.mark.parametrize("case", _load_cases(), ids=lambda case: case["case_id"])
@pytest.mark.asyncio
async def test_telegram_failure_case_replay(case, monkeypatch):
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    bot.native_loop = object()
    bot.autonomy_orchestrator = None
    events: List[Dict[str, Any]] = []

    async def fake_publish_phase1_event(**kwargs):
        events.append(kwargs)

    async def fail_runtime(*args, **kwargs):
        raise AssertionError(f"{case['case_id']} should not fall back to runtime_v2")

    async def fake_native(*args, **kwargs):
        state = kwargs["state"]
        state.mark_task_completed()
        return TelegramTurnResult(
            status="completed_verified",
            state=state,
            reply=TelegramTurnReply(
                reply_text=case["expected"]["reply_text"],
                delivery_kind="final",
                status="completed_verified",
            ),
        )

    monkeypatch.setattr(bot, "_publish_phase1_event", fake_publish_phase1_event)
    monkeypatch.setattr(bot, "_run_runtime_v2_turn", fail_runtime)
    monkeypatch.setattr(bot, "_run_native_loop_turn", fake_native)
    monkeypatch.setattr(bot, "_get_subject_gate", lambda: AllowingSubjectGate())

    state = bot._get_runtime_state(case["initial_state"]["session_key"])
    state.task_status = case["initial_state"].get("task_status", state.task_status)
    state.waiting_for_user_input = case["initial_state"].get("waiting_for_user_input", state.waiting_for_user_input)
    state.last_inferred_action = case["initial_state"].get("last_inferred_action")
    for artifact in case["initial_state"].get("pending_artifacts", []):
        state.add_pending_artifact(
            artifact_id=artifact["artifact_id"],
            filename=artifact.get("filename"),
            artifact_ref=artifact.get("artifact_ref"),
        )

    update = DummyUpdate(case["turn"]["text"], case["turn"]["message_id"])
    await bot._handle_with_runtime_v2(
        update=update,
        text=update.message.text,
        chat_id=DummyChat.id,
        user_id=DummyUser.id,
        username=DummyUser.username,
        trace_id=f"replay-{case['case_id']}",
    )

    assert update.message.sent == [case["expected"]["reply_text"]]
    assert state.ingress_context["runtime_action"] == case["expected"]["runtime_action"]
    assert state.ingress_context["resolved_target"]["artifact_id"] == case["expected"]["resolved_target_artifact_id"]
    assert any(
        event["kind"] == "primary_path_selected"
        and event["payload"]["path"] == case["expected"]["primary_path"]
        for event in events
    )


@pytest.mark.asyncio
async def test_recent_result_continuation_failure_chain_replay_uses_analyze_write_and_blocks_false_completion_claims():
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    state = bot._get_runtime_state("telegram:dm:8420019401")
    target_path = r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html"
    state.recent_delivered_result_context = {
        "binding_kind": "recent_delivered_result",
        "target_name": "bilili_lookalike.html",
        "target_path": target_path,
        "runtime_status": "completed_verified",
        "source_turn_id": "turn_task_done",
    }

    class ModifyFeedbackLLM:
        async def complete(self, prompt):
            class Response:
                content = '{"segments": [{"text": "顶部导航栏右边的图标换一下 换一个好看点的", "kind": "small_talk", "confidence": 0.55}]}'
            return Response()

    turn2 = await bot.telegram_runtime_bridge.inspect_ingress_semantic(
        "顶部导航栏 右边的图标换一下 换一个好看点的",
        state,
        llm_client=ModifyFeedbackLLM(),
    )
    state.ingress_context = bot.telegram_runtime_bridge.build_ingress_context(turn2, state)
    bot._sync_pending_result_continuation_from_ingress(state, user_text="顶部导航栏 右边的图标换一下 换一个好看点的")

    assert state.ingress_context["runtime_action"] == "execute_task"
    assert state.ingress_context["request_mode"] == "analyze"
    assert state.pending_result_continuation["requested_mode"] == "analyze"

    state.get_chat_state().recent_assistant_replies.append("收到，那换什么风格的图标会更好看呢？")

    class WritePermissionLLM:
        async def complete(self, prompt):
            class Response:
                content = '{"segments": [{"text": "你先换个你觉得好看的", "kind": "small_talk", "confidence": 0.58}]}'
            return Response()

    turn3 = await bot.telegram_runtime_bridge.inspect_ingress_semantic(
        "你先换个你觉得好看的",
        state,
        llm_client=WritePermissionLLM(),
    )
    state.ingress_context = bot.telegram_runtime_bridge.build_ingress_context(turn3, state)
    bot._sync_pending_result_continuation_from_ingress(state, user_text="你先换个你觉得好看的")

    assert state.ingress_context["runtime_action"] == "execute_task"
    assert state.ingress_context["request_mode"] == "write"
    assert state.pending_result_continuation["requested_mode"] == "write"

    class StatusLLM:
        async def complete(self, prompt):
            class Response:
                content = '{"segments": [{"text": "改了吗", "kind": "status_query", "confidence": 0.96}]}'
            return Response()

    turn4 = await bot.telegram_runtime_bridge.inspect_ingress_semantic("改了吗", state, llm_client=StatusLLM())
    state.ingress_context = bot.telegram_runtime_bridge.build_ingress_context(turn4, state)

    assert state.ingress_context["runtime_action"] == "return_runtime_status"

    false_done_plan = build_direct_response_plan(
        "改好啦，换成了我挑的顺眼风格。",
        kind="chat",
        delivery_kind="chat",
        authority_source="test",
        reply_authority="model_chat",
        metadata={"conversation_act": "social_keepalive", "reply_origin": "chat_mainline"},
        state=state,
    )
    false_done_verdict = apply_output_check(false_done_plan, state)
    assert false_done_verdict.applied_authority == "host_degraded_fallback"
    assert "还没完成这次对 bilili_lookalike.html 的修改并验证结果" in false_done_verdict.reply_text

    class CorrectionLLM:
        async def complete(self, prompt):
            class Response:
                content = '{"segments": [{"text": "没变化呀 修改时间还是9:31", "kind": "small_talk", "confidence": 0.51}]}'
            return Response()

    turn5 = await bot.telegram_runtime_bridge.inspect_ingress_semantic(
        "没变化呀 修改时间还是9:31",
        state,
        llm_client=CorrectionLLM(),
    )
    state.ingress_context = bot.telegram_runtime_bridge.build_ingress_context(turn5, state)
    assert state.ingress_context["runtime_action"] == "execute_task"
    assert state.ingress_context["request_mode"] == "analyze"
    assert state.ingress_context["correction_context"] is True

    cache_excuse_plan = build_direct_response_plan(
        "抱歉，可能是缓存问题没刷新，你强制刷新一下试试。",
        kind="chat",
        delivery_kind="chat",
        authority_source="test",
        reply_authority="model_chat",
        metadata={"conversation_act": "social_keepalive", "reply_origin": "chat_mainline"},
        state=state,
    )
    cache_excuse_verdict = apply_output_check(cache_excuse_plan, state)
    assert cache_excuse_verdict.applied_authority == "host_degraded_fallback"
    assert "还没完成这次对 bilili_lookalike.html 的修改并验证结果" in cache_excuse_verdict.reply_text
