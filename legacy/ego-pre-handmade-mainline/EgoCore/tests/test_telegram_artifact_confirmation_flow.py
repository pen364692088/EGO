from __future__ import annotations

from typing import Any, Dict, List

import pytest

from app.openemotion_hooks.subject_gate import SubjectGateVerdict
from app.telegram_bot import TelegramBot
from app.telegram_runtime_result import TelegramTurnReply, TelegramTurnResult


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


class _AllowingSubjectGate:
    def process_ingress(self, **kwargs):
        return SubjectGateVerdict.allow(stage="ingress")

    def finalize_host_owned_result(self, **kwargs):
        return SubjectGateVerdict.allow(stage="response_plan")


def _install_allowing_subject_gate(monkeypatch, bot):
    monkeypatch.setattr(bot, "_get_subject_gate", lambda: _AllowingSubjectGate())


def _disable_autonomy_for_routing_fixture(bot):
    bot.autonomy_orchestrator = None


@pytest.mark.asyncio
async def test_uploaded_task_file_executes_immediately_on_native_mainline(monkeypatch):
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    _install_allowing_subject_gate(monkeypatch, bot)
    _disable_autonomy_for_routing_fixture(bot)
    bot.native_loop = object()
    events: List[Dict[str, Any]] = []

    async def fake_publish_phase1_event(**kwargs):
        events.append(kwargs)

    async def fail_runtime(*args, **kwargs):
        raise AssertionError("artifact execute confirmation should not fall back to runtime_v2")

    async def fake_native(*args, **kwargs):
        state = kwargs["state"]
        state.mark_task_completed()
        return TelegramTurnResult(
            status="completed_verified",
            state=state,
            reply=TelegramTurnReply(
                reply_text="页面已创建。",
                delivery_kind="final",
                status="completed_verified",
            ),
        )

    monkeypatch.setattr(bot, "_publish_phase1_event", fake_publish_phase1_event)
    monkeypatch.setattr(bot, "_run_runtime_v2_turn", fail_runtime)
    monkeypatch.setattr(bot, "_run_native_loop_turn", fake_native)

    session_key = "telegram:dm:8420019401"
    state = bot._get_runtime_state(session_key)
    state.add_pending_artifact("artifact://task-sheet", "任务单.txt", "artifact://task-sheet")

    update = DummyUpdate("[用户发送了文件: 任务单.txt]", 1886)
    await bot._handle_with_runtime_v2(
        update=update,
        text=update.message.text,
        chat_id=DummyChat.id,
        user_id=DummyUser.id,
        username=DummyUser.username,
        trace_id="trace-upload",
    )

    assert update.message.sent == ["页面已创建。"]
    assert state.task_status == "completed_verified"
    assert state.waiting_for_user_input is False
    assert state.last_inferred_action == "execute"
    assert any(
        event["kind"] == "primary_path_selected" and event["payload"]["path"] == "native_loop"
        for event in events
    )


@pytest.mark.asyncio
async def test_execute_confirmation_ingress_is_bound_to_pending_task(monkeypatch):
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    _install_allowing_subject_gate(monkeypatch, bot)
    _disable_autonomy_for_routing_fixture(bot)
    session_key = "telegram:dm:8420019401"
    state = bot._get_runtime_state(session_key)
    state.add_pending_artifact("artifact://task-sheet", "任务单.txt", "artifact://task-sheet")
    state.task_status = "waiting_input"
    state.waiting_for_user_input = True
    state.last_inferred_action = "execute"

    captured = {}

    async def fake_run_primary_turn(*args, **kwargs):
        captured["ingress_context"] = kwargs["state"].ingress_context
        return TelegramTurnResult(
            status="completed_verified",
            state=kwargs["state"],
            reply=TelegramTurnReply(
                reply_text="ok",
                delivery_kind="final",
                status="completed_verified",
            ),
        )

    monkeypatch.setattr(bot, "_run_primary_turn", fake_run_primary_turn)
    async def fake_publish_phase1_event(**kwargs):
        return None

    monkeypatch.setattr(bot, "_publish_phase1_event", fake_publish_phase1_event)

    update = DummyUpdate("执行", 1888)
    await bot._handle_with_runtime_v2(
        update=update,
        text=update.message.text,
        chat_id=DummyChat.id,
        user_id=DummyUser.id,
        username=DummyUser.username,
        trace_id="trace-bind",
    )

    ingress_context = captured["ingress_context"]
    assert ingress_context["runtime_action"] == "execute_task"
    assert ingress_context["request_mode"] == "execute"
    assert ingress_context["resolved_target"]["artifact_id"] == "artifact://task-sheet"


@pytest.mark.asyncio
async def test_execute_confirmation_hydrates_artifact_envelope_only_into_native_context(monkeypatch):
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    session_key = "telegram:dm:8420019401"
    state = bot._get_runtime_state(session_key)
    state.add_pending_artifact("artifact://compacted/task-sheet", "任务单.txt", "artifact://compacted/task-sheet")
    state.task_status = "waiting_input"
    state.waiting_for_user_input = True
    state.last_inferred_action = "execute"
    state.ingress_context = {
        "runtime_action": "execute_task",
        "resolved_target": {
            "artifact_id": "artifact://compacted/task-sheet",
            "artifact_ref": "artifact://compacted/task-sheet",
            "filename": "任务单.txt",
        },
    }

    hydrated = bot._hydrate_artifact_ingress_context(state)
    assert hydrated["resolved_artifact_filename"] == "任务单.txt"
    assert hydrated["resolved_artifact_id"] == "artifact://compacted/task-sheet"
    assert "resolved_artifact_text" not in hydrated
