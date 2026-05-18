from types import SimpleNamespace

import pytest

from app.telegram_bot import TelegramBot
from app.telegram_runtime_result import TelegramTurnReply, TelegramTurnResult


@pytest.mark.asyncio
async def test_primary_turn_prefers_native_loop_for_execute_task(monkeypatch):
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    bot.native_loop = object()
    state = bot._get_runtime_state("telegram:dm:1")
    ingress = SimpleNamespace(_runtime_action="execute_task", is_file_only=False)

    async def fail_runtime(*args, **kwargs):
        raise AssertionError("runtime_v2 fallback should not be used")

    async def native(*args, **kwargs):
        return TelegramTurnResult(
            status="completed_verified",
            state=state,
            reply=TelegramTurnReply(reply_text="done", delivery_kind="final", status="completed_verified"),
        )

    monkeypatch.setattr(bot, "_run_runtime_v2_turn", fail_runtime)
    monkeypatch.setattr(bot, "_run_native_loop_turn", native)

    result = await bot._run_primary_turn(
        update=None,
        session_key="telegram:dm:1",
        text="create page",
        state=state,
        ingress=ingress,
        ack_text=None,
    )

    assert result.reply_text == "done"


@pytest.mark.asyncio
async def test_primary_turn_falls_back_when_native_loop_fails(monkeypatch):
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    bot.native_loop = object()
    state = bot._get_runtime_state("telegram:dm:1")
    ingress = SimpleNamespace(_runtime_action="execute_task", is_file_only=False)

    async def native(*args, **kwargs):
        raise RuntimeError("boom")

    async def runtime(*args, **kwargs):
        return TelegramTurnResult(
            status="completed_verified",
            state=state,
            reply=TelegramTurnReply(reply_text="fallback", delivery_kind="final", status="completed_verified"),
        )

    monkeypatch.setattr(bot, "_run_native_loop_turn", native)
    monkeypatch.setattr(bot, "_run_runtime_v2_turn", runtime)

    result = await bot._run_primary_turn(
        update=None,
        session_key="telegram:dm:1",
        text="create page",
        state=state,
        ingress=ingress,
        ack_text=None,
    )

    assert result.reply_text == "fallback"


@pytest.mark.asyncio
async def test_primary_turn_blocks_instead_of_fallback_for_artifact_execute_when_native_fails(monkeypatch):
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    bot.native_loop = object()
    state = bot._get_runtime_state("telegram:dm:1")
    state.ingress_context = {
        "runtime_action": "execute_task",
        "resolved_target": {
            "artifact_id": "artifact://task-sheet",
            "artifact_ref": "artifact://task-sheet",
            "filename": "任务单.txt",
        },
    }
    ingress = SimpleNamespace(_runtime_action="execute_task", is_file_only=False)

    async def native(*args, **kwargs):
        raise RuntimeError("The read operation timed out")

    async def fail_runtime(*args, **kwargs):
        raise AssertionError("artifact execute should not fall back to runtime_v2")

    monkeypatch.setattr(bot, "_run_native_loop_turn", native)
    monkeypatch.setattr(bot, "_run_runtime_v2_turn", fail_runtime)

    result = await bot._run_primary_turn(
        update=None,
        session_key="telegram:dm:1",
        text="执行",
        state=state,
        ingress=ingress,
        ack_text=None,
    )

    assert result.status == "blocked"
    assert "避免卡在 read_artifact" in result.reply_text
    assert state.task_status == "blocked"


@pytest.mark.asyncio
async def test_runtime_v2_loop_is_lazy_until_runtime_turn(monkeypatch):
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    state = bot._get_runtime_state("telegram:dm:1")
    assert bot.runtime_v2_loop is None

    class FakeLoop:
        def __init__(self):
            self._states = {}

        async def run_turn_typed(self, *args, **kwargs):
            assert bot.runtime_v2_loop is not None
            return type(
                "LegacyResult",
                (),
                {
                    "status": "completed_verified",
                    "state": state,
                    "reply": type(
                        "LegacyReply",
                        (),
                        {
                            "reply_text": "fallback",
                            "delivery_kind": "final",
                            "status": "completed_verified",
                            "suppressible": False,
                            "request_id": None,
                            "generation_id": None,
                            "turn_id": None,
                        },
                    )(),
                },
            )()

    fake_loop = FakeLoop()

    def fake_get_loop():
        bot.runtime_v2_fallback_runner._loop = fake_loop
        return fake_loop

    monkeypatch.setattr(bot.runtime_v2_fallback_runner, "get_loop", fake_get_loop)

    result = await bot._run_runtime_v2_turn(
        update=None,
        session_key="telegram:dm:1",
        text="create page",
        state=state,
        ack_text=None,
    )

    assert result.reply_text == "fallback"


def test_should_not_use_native_loop_for_chat_like_turns():
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    bot.native_loop = object()
    state = bot._get_runtime_state("telegram:dm:1")
    state.ingress_context = {"interaction_kind": "chat"}
    ingress = SimpleNamespace(_runtime_action="chat", is_file_only=False, interaction_kind="chat")

    assert bot._should_use_native_loop(ingress, state) is False


def test_should_not_use_native_loop_for_status_fast_path():
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    bot.native_loop = object()
    state = bot._get_runtime_state("telegram:dm:1")
    ingress = SimpleNamespace(_runtime_action="return_runtime_status", is_file_only=False)

    assert bot._should_use_native_loop(ingress, state) is False


def test_should_use_native_loop_for_execute_confirmation_while_waiting_input():
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    bot.native_loop = object()
    state = bot._get_runtime_state("telegram:dm:1")
    state.task_status = "waiting_input"
    state.waiting_for_user_input = True
    ingress = SimpleNamespace(_runtime_action="execute_task", is_file_only=False, is_confirm_execution=True)

    assert bot._should_use_native_loop(ingress, state) is True


def test_should_use_native_loop_for_task_artifact_upload_even_if_previous_turn_waiting_input():
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    bot.native_loop = object()
    state = bot._get_runtime_state("telegram:dm:1")
    state.task_status = "waiting_input"
    state.waiting_for_user_input = True
    state.ingress_context = {
        "runtime_action": "execute_task",
        "resolved_target": {
            "artifact_id": "artifact://compacted/task-sheet",
            "artifact_ref": "artifact://compacted/task-sheet",
            "filename": "任务单.txt",
        },
    }
    ingress = SimpleNamespace(_runtime_action="execute_task", is_file_only=True, is_confirm_execution=False)

    assert bot._should_use_native_loop(ingress, state) is True


def test_should_use_native_loop_for_explicit_path_execute_while_waiting_input():
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    bot.native_loop = object()
    state = bot._get_runtime_state("telegram:dm:1")
    state.task_status = "waiting_input"
    state.waiting_for_user_input = True
    state.ingress_context = {
        "runtime_action": "execute_task",
        "resolved_target": {
            "path": r"D:\Project\AIProject\MyProject\Test\CLAUDE.md",
            "filename": "CLAUDE.md",
            "source": "explicit_path",
        },
    }
    ingress = SimpleNamespace(_runtime_action="execute_task", is_file_only=False, is_confirm_execution=False)

    assert bot._should_use_native_loop(ingress, state) is True


@pytest.mark.asyncio
async def test_native_loop_turn_calls_openemotion_hooks(monkeypatch):
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    state = bot._get_runtime_state("telegram:dm:1")
    calls = []

    class Hook:
        enabled = True

        def process_ingress(self, **kwargs):
            calls.append(("ingress", kwargs["session_id"], kwargs["turn_id"], "evidence_collector" in kwargs))

        def process_external_result(self, **kwargs):
            calls.append(("external", kwargs["session_id"], kwargs["step"], "evidence_collector" in kwargs))

        def capture_response_plan(self, **kwargs):
            calls.append(("plan", kwargs["result"].status, "evidence_collector" in kwargs))

    class NativeResult:
        reply_text = "native done"
        tool_results = [
            {
                "tool_name": "file",
                "result": {"success": True, "output": "ok", "error": None, "metadata": {}},
            }
        ]

    async def fake_send_reply(*args, **kwargs):
        return None

    async def fake_run_turn(**kwargs):
        return NativeResult()

    bot.native_openemotion_hooks = Hook()
    bot.native_loop = type("Loop", (), {"run_turn": None})()
    monkeypatch.setattr(bot, "_send_reply", fake_send_reply)
    monkeypatch.setattr(bot.native_loop, "run_turn", fake_run_turn)

    result = await bot._run_native_loop_turn(
        update=None,
        session_key="telegram:dm:1",
        text="create page",
        state=state,
        ack_text=None,
    )

    assert result.reply_text == "native done"
    assert calls[0][0] == "ingress"
    assert ("external", "telegram:dm:1", 0, True) in calls
    assert ("plan", "completed_verified", True) in calls


@pytest.mark.asyncio
async def test_runtime_v2_turn_does_not_append_uploaded_artifact_when_explicit_path_present(monkeypatch):
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    state = bot._get_runtime_state("telegram:dm:1")
    state.last_uploaded_artifact = {
        "artifact_id": "artifact://compacted/task-sheet",
        "artifact_ref": "artifact://compacted/task-sheet",
        "filename": "P3_closure_real_probe_task.txt",
    }
    state.ingress_context = {
        "resolved_target": {
            "path": r"D:\Project\AIProject\MyProject\Test\missing_closure_probe.md",
            "filename": "missing_closure_probe.md",
            "source": "explicit_path",
        }
    }

    captured = {}

    class FakeRunner:
        loop = object()

        def get_loop(self):
            return self.loop

        async def run_turn(self, *, session_key, user_input, state, **kwargs):
            captured["user_input"] = user_input
            return TelegramTurnResult(
                status="completed_verified",
                state=state,
                reply=TelegramTurnReply(reply_text="ok", delivery_kind="final", status="completed_verified"),
            )

    bot.telegram_runtime_fallback_runner = FakeRunner()

    result = await bot._run_runtime_v2_turn(
        update=None,
        session_key="telegram:dm:1",
        text=r"读取 D:\Project\AIProject\MyProject\Test\missing_closure_probe.md 前 1 行",
        state=state,
        ack_text=None,
    )

    assert result.reply_text == "ok"
    assert captured["user_input"] == r"读取 D:\Project\AIProject\MyProject\Test\missing_closure_probe.md 前 1 行"


@pytest.mark.asyncio
async def test_native_loop_turn_publishes_tool_result_event(monkeypatch):
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    state = bot._get_runtime_state("telegram:dm:1")
    events = []

    class Hook:
        enabled = False

    class NativeResult:
        reply_text = "native done"
        tool_results = [
            {
                "tool_name": "file",
                "result": {"success": True, "output": "ok", "error": None, "metadata": {}},
            }
        ]

    async def fake_send_reply(*args, **kwargs):
        return None

    async def fake_run_turn(**kwargs):
        return NativeResult()

    async def fake_publish(**kwargs):
        events.append(kwargs)

    bot.native_openemotion_hooks = Hook()
    bot.native_loop = type("Loop", (), {"run_turn": None})()
    monkeypatch.setattr(bot, "_send_reply", fake_send_reply)
    monkeypatch.setattr(bot.native_loop, "run_turn", fake_run_turn)
    monkeypatch.setattr(bot, "_publish_phase1_event", fake_publish)

    result = await bot._run_native_loop_turn(
        update=None,
        session_key="telegram:dm:1",
        text="create page",
        state=state,
        ack_text=None,
    )

    assert result.reply_text == "native done"
    assert any(event["kind"] == "native_tool_result" for event in events)
    assert any(event["kind"] == "tool_delivery_bridge" for event in events)


@pytest.mark.asyncio
async def test_native_loop_turn_publishes_contract_runtime_events(monkeypatch):
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    state = bot._get_runtime_state("telegram:dm:1")
    events = []

    class Hook:
        enabled = False

    class NativeResult:
        reply_text = "需要重新锁定。"
        tool_results = []
        task_contract = {
            "task_id": "contract_1",
            "goal": "create file",
            "success_criteria": ["file exists"],
            "hard_constraints": ["write only target"],
            "risk_level": "medium",
            "ask_needed": False,
        }
        next_step_decision = {
            "step_id": "step_1",
            "action_type": "call_tool",
            "expected_signal": "file exists",
            "tool_name": "file",
        }
        verification_result = {
            "step_id": "step_1",
            "expected_signal_matched": False,
            "need_relock": True,
            "stop_reason": "verification_failed",
            "contract_delta": {"reason": "target_missing"},
        }

    async def fake_run_turn(**kwargs):
        return NativeResult()

    async def fake_publish(**kwargs):
        events.append(kwargs)

    bot.native_openemotion_hooks = Hook()
    bot.native_loop = type("Loop", (), {"run_turn": None})()
    monkeypatch.setattr(bot.native_loop, "run_turn", fake_run_turn)
    monkeypatch.setattr(bot, "_publish_phase1_event", fake_publish)

    result = await bot._run_native_loop_turn(
        update=None,
        session_key="telegram:dm:1",
        text="create page",
        state=state,
        ack_text=None,
    )

    assert result.status == "waiting_input"
    kinds = [event["kind"] for event in events]
    assert "contract_locked" in kinds
    assert "next_step_decided" in kinds
    assert "step_verified" in kinds
    assert "need_relock" in kinds
    relock_payload = next(event["payload"] for event in events if event["kind"] == "need_relock")
    assert relock_payload["trace_schema"] == "contract_runtime_v1"
    assert relock_payload["need_relock"] is True


@pytest.mark.asyncio
async def test_native_loop_turn_publishes_artifact_stage_events(monkeypatch):
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    state = bot._get_runtime_state("telegram:dm:1")
    state.ingress_context = {
        "runtime_action": "execute_task",
        "resolved_target": {
            "artifact_id": "artifact://compacted/demo",
            "artifact_ref": "artifact://compacted/demo",
            "filename": "任务单.txt",
        },
    }
    events = []

    class Hook:
        enabled = False

    class NativeResult:
        reply_text = "任务单原文已读取，方向已重新锁定。请继续下一步执行。"
        task_contract = {"task_id": "contract_1", "goal": "x", "success_criteria": [], "hard_constraints": [], "risk_level": "medium", "ask_needed": False}
        next_step_decision = {"step_id": "step_1", "action_type": "read_artifact", "expected_signal": "Artifact content becomes available for re-lock.", "tool_name": "read_artifact"}
        verification_result = {"step_id": "step_1", "expected_signal_matched": True, "need_relock": True, "stop_reason": "artifact_ready", "contract_delta": {"resolved_artifact_text": True}}
        tool_results = [{"tool_name": "read_artifact", "result": {"success": True, "output": "ok", "error": None, "metadata": {"stage_error_code": None}}}]

    async def fake_run_turn(**kwargs):
        return NativeResult()

    async def fake_publish(**kwargs):
        events.append(kwargs)

    bot.native_openemotion_hooks = Hook()
    bot.native_loop = type("Loop", (), {"run_turn": None})()
    monkeypatch.setattr(bot.native_loop, "run_turn", fake_run_turn)
    monkeypatch.setattr(bot, "_publish_phase1_event", fake_publish)

    await bot._run_native_loop_turn(
        update=None,
        session_key="telegram:dm:1",
        text="[用户发送了文件: 任务单.txt]",
        state=state,
        ack_text=None,
    )

    kinds = [event["kind"] for event in events]
    assert "artifact_envelope_ready" in kinds
    assert "artifact_read_started" in kinds
    assert "artifact_read_completed" in kinds


@pytest.mark.asyncio
async def test_native_loop_turn_preserves_state_for_planning_timeout(monkeypatch):
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    state = bot._get_runtime_state("telegram:dm:1")
    state.ingress_context = {
        "runtime_action": "execute_task",
        "resolved_target": {
            "artifact_id": "artifact://compacted/demo",
            "artifact_ref": "artifact://compacted/demo",
            "filename": "任务单.txt",
        },
    }

    class Hook:
        enabled = False

    class NativeResult:
        status = "resumable_pause"
        finish_reason = "planning_timeout"
        reply_text = ""
        task_contract = {"task_id": "contract_1", "goal": "x", "success_criteria": [], "hard_constraints": [], "risk_level": "medium", "ask_needed": False}
        next_step_decision = {"step_id": "step_2", "action_type": "call_tool", "expected_signal": "write target file", "tool_name": "file"}
        verification_result = {"step_id": "step_2", "expected_signal_matched": False, "need_relock": False, "stop_reason": "planning_timeout", "contract_delta": {"stage_error_code": "planning_timeout"}}
        tool_results = [{"tool_name": "read_artifact", "result": {"success": True, "output": "在D:\\Project\\AIProject\\MyProject\\Test\\task_output.html创建html页面", "error": None, "metadata": {"stage_error_code": None}}}]
        checkpoint_payload = {"next_step": {"action_type": "call_tool"}}

    async def fake_run_turn(**kwargs):
        return NativeResult()

    bot.native_openemotion_hooks = Hook()
    bot.native_loop = type("Loop", (), {"run_turn": None})()
    monkeypatch.setattr(bot.native_loop, "run_turn", fake_run_turn)

    result = await bot._run_native_loop_turn(
        update=None,
        session_key="telegram:dm:1",
        text="[用户发送了文件: 任务单.txt]",
        state=state,
        ack_text=None,
    )

    assert result.status == "resumable_pause"
    assert state.task_status == "resumable_pause"
    assert state.contract_phase == "planning_stalled"
    assert state.waiting_for_user_input is False
    assert state.ingress_context["resolved_artifact_text"].startswith("在D:\\Project")


@pytest.mark.asyncio
async def test_native_loop_turn_returns_blocked_reply_on_failed_tool_without_final(monkeypatch):
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    state = bot._get_runtime_state("telegram:dm:1")
    state.ingress_context = {
        "runtime_action": "execute_task",
        "resolved_target": {"filename": "任务单.txt"},
    }

    class Hook:
        enabled = False

    class NativeResult:
        reply_text = ""
        tool_results = [
            {
                "tool_name": "file",
                "result": {"success": False, "output": "", "error": "File extension not allowed: .example", "metadata": {}},
            }
        ]

    async def fake_run_turn(**kwargs):
        return NativeResult()

    bot.native_openemotion_hooks = Hook()
    bot.native_loop = type("Loop", (), {"run_turn": None})()
    monkeypatch.setattr(bot.native_loop, "run_turn", fake_run_turn)

    result = await bot._run_native_loop_turn(
        update=None,
        session_key="telegram:dm:1",
        text="执行",
        state=state,
        ack_text=None,
    )

    assert result.status == "blocked"
    assert "File extension not allowed: .example" in result.reply_text
    assert state.task_status == "blocked"
