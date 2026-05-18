import pytest

from app.autonomy import AutonomyExecutorKind, AutonomyRun, AutonomyRunStatus
from app.runtime_v2.progress_events import ProgressEvent, ProgressEventType
from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
from app.telegram_runtime_result import TelegramTurnReply, TelegramTurnResult
from app.telegram_bot import TelegramBot


@pytest.mark.asyncio
async def test_telegram_runtime_v2_delivery_accepts_typed_result():
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    bot._get_runtime_v2_loop()

    class DummyMessage:
        last_text = None

        async def reply_text(self, text, parse_mode=None):
            self.last_text = text

    class DummyUpdate:
        message = DummyMessage()

    state = bot._get_runtime_state("telegram:dm:456")
    bot._sync_state_into_runtime_v2_loop("telegram:dm:456", state)
    result = RuntimeV2TurnResult(
        status="completed_verified",
        state=state,
        reply=RuntimeV2Reply(
            reply_text="已经改好了。",
            delivery_kind="final",
            status="completed_verified",
        ),
    )

    await bot._deliver_runtime_v2_result(DummyUpdate(), state, result, is_challenge_turn=False)
    assert DummyUpdate.message.last_text == "已经改好了。"


@pytest.mark.asyncio
async def test_telegram_runtime_v2_delivery_sends_progress_before_final_for_autonomy_execute_task():
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    bot._get_runtime_v2_loop()

    class DummyMessage:
        replies = []

        async def reply_text(self, text, parse_mode=None):
            self.replies.append(text)

    class DummyUpdate:
        message = DummyMessage()

    state = bot._get_runtime_state("telegram:dm:456")
    bot._sync_state_into_runtime_v2_loop("telegram:dm:456", state)
    state.ingress_context = {"runtime_action": "execute_task"}
    state.autonomy_context = {"run_id": "autonomy_1", "status": "running", "progress_delivery": {}}
    state.push_progress_event(
        ProgressEvent(event_type=ProgressEventType.TARGET_SELECTED, message="我先确认目标和约束。")
    )
    state.push_progress_event(
        ProgressEvent(event_type=ProgressEventType.EXECUTING_STEP, message="我开始处理文件和内容。")
    )
    state.push_progress_event(
        ProgressEvent(event_type=ProgressEventType.COMPLETED, message="这一步完成了。")
    )
    state.task_status = "completed_verified"

    result = RuntimeV2TurnResult(
        status="completed_verified",
        state=state,
        reply=RuntimeV2Reply(
            reply_text="已经改好了。",
            delivery_kind="final",
            status="completed_verified",
        ),
    )

    await bot._deliver_runtime_v2_result(DummyUpdate(), state, result, is_challenge_turn=False)
    assert DummyUpdate.message.replies == [
        "我先确认目标和约束。",
        "我开始处理文件和内容。",
        "已经改好了。",
    ]


@pytest.mark.asyncio
async def test_telegram_runtime_v2_delivery_keeps_progress_visible_after_internal_completion():
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    bot._get_runtime_v2_loop()

    class DummyMessage:
        replies = []

        async def reply_text(self, text, parse_mode=None):
            self.replies.append(text)

    class DummyUpdate:
        message = DummyMessage()

    state = bot._get_runtime_state("telegram:dm:789")
    bot._sync_state_into_runtime_v2_loop("telegram:dm:789", state)
    state.ingress_context = {"runtime_action": "execute_task"}
    state.autonomy_context = {"run_id": "autonomy_2", "status": "running", "progress_delivery": {}}
    state.push_progress_event(
        ProgressEvent(event_type=ProgressEventType.EXECUTING_STEP, message="我开始处理文件和内容。")
    )
    state.push_progress_event(
        ProgressEvent(event_type=ProgressEventType.VERIFYING_RESULT, message="我先核对结果。")
    )
    state.mark_task_completed()

    result = RuntimeV2TurnResult(
        status="completed_verified",
        state=state,
        reply=RuntimeV2Reply(
            reply_text="已经改好了。",
            delivery_kind="final",
            status="completed_verified",
        ),
    )

    await bot._deliver_runtime_v2_result(DummyUpdate(), state, result, is_challenge_turn=False)

    assert DummyUpdate.message.replies == [
        "我开始处理文件和内容。",
        "我先核对结果。",
        "已经改好了。",
    ]
    assert state.final_sent is True


@pytest.mark.asyncio
async def test_telegram_runtime_v2_chat_delivery_settles_turn_to_terminal():
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    bot._get_runtime_v2_loop()

    class DummyMessage:
        last_text = None

        async def reply_text(self, text, parse_mode=None):
            self.last_text = text

    class DummyUpdate:
        message = DummyMessage()

    state = bot._get_runtime_state("telegram:dm:chat_terminal")
    bot._sync_state_into_runtime_v2_loop("telegram:dm:chat_terminal", state)
    state.ingress_context = {"interaction_kind": "chat"}
    turn_id = state.start_turn()
    assert turn_id
    assert state.active_turn_status == "running"

    result = RuntimeV2TurnResult(
        status="chat",
        state=state,
        reply=RuntimeV2Reply(
            reply_text="我继续想了想，那个比喻还没说完。",
            delivery_kind="chat",
            status="chat",
        ),
    )

    await bot._deliver_runtime_v2_result(DummyUpdate(), state, result, is_challenge_turn=False)

    assert DummyUpdate.message.last_text == "我继续想了想，那个比喻还没说完。"
    assert state.final_sent is True
    assert state.active_turn_status == "terminal"


@pytest.mark.asyncio
async def test_telegram_progress_delivery_dedupes_identical_phase_text():
    bot = TelegramBot(token="test-token", use_runtime_v2=True)

    class DummyMessage:
        replies = []

        async def reply_text(self, text, parse_mode=None):
            self.replies.append(text)

    class DummyUpdate:
        message = DummyMessage()

    state = bot._get_runtime_state("telegram:dm:dup")
    state.autonomy_context = {"run_id": "autonomy_dup", "status": "running", "progress_delivery": {}}

    first = await bot._send_autonomy_progress_update(
        state=state,
        phase_key="planning_current_slice",
        text="我继续处理这个任务，做完直接给你结果。",
        update=DummyUpdate(),
        trace_id="trace_dup",
        ingress_message_id=1,
    )
    second = await bot._send_autonomy_progress_update(
        state=state,
        phase_key="planning_current_slice",
        text="我继续处理这个任务，做完直接给你结果。",
        update=DummyUpdate(),
        trace_id="trace_dup",
        ingress_message_id=1,
    )

    assert first is True
    assert second is False
    assert DummyUpdate.message.replies == ["我继续处理这个任务，做完直接给你结果。"]


@pytest.mark.asyncio
async def test_telegram_progress_delivery_edits_single_live_message():
    bot = TelegramBot(token="test-token", use_runtime_v2=True)

    class DummySentMessage:
        def __init__(self, chat_id, message_id):
            self.message_id = message_id
            self.chat = type("Chat", (), {"id": chat_id})()

    class DummyBot:
        def __init__(self):
            self.sent = []
            self.edits = []

        async def send_message(self, chat_id, text):
            self.sent.append((chat_id, text))
            return DummySentMessage(chat_id, 9001)

        async def edit_message_text(self, chat_id, message_id, text):
            self.edits.append((chat_id, message_id, text))

    bot.app = type("DummyApp", (), {"bot": DummyBot()})()

    state = bot._get_runtime_state("telegram:dm:edit")
    state.autonomy_context = {"run_id": "autonomy_edit", "status": "running", "progress_delivery": {}}

    first = await bot._send_autonomy_progress_update(
        state=state,
        phase_key="executing_changes",
        text="我先处理需要的文件。",
        chat_id=8420019401,
        trace_id="trace_edit",
        ingress_message_id=10,
    )
    second = await bot._send_autonomy_progress_update(
        state=state,
        phase_key="verifying",
        text="我先验证一下结果。",
        chat_id=8420019401,
        trace_id="trace_edit",
        ingress_message_id=10,
    )

    assert first is True
    assert second is True
    assert bot.app.bot.sent == [(8420019401, "我先处理需要的文件。")]
    assert bot.app.bot.edits == [(8420019401, 9001, "我先验证一下结果。")]


def test_extract_output_obligations_preserves_exact_explicit_filenames(tmp_path):
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    state = bot._get_runtime_state("telegram:dm:obligations")
    state.ingress_context = {
        "runtime_action": "execute_task",
        "requested_output": {"target_directory": str(tmp_path)},
    }

    obligations = bot._extract_output_obligations(
        f"在 {tmp_path} 目录下创建 demo.txt。最后做一个print hello world.py文件",
        state,
    )

    assert [item["name"] for item in obligations] == ["demo.txt", "print hello world.py"]
    assert obligations[1]["path"].endswith("print hello world.py")


@pytest.mark.asyncio
async def test_resume_telegram_autonomy_run_blocks_after_transient_retry_budget():
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    sent = []

    async def fake_send_chat_message(chat_id, text, finalize_evidence=True):
        sent.append((chat_id, text, finalize_evidence))

    bot._send_chat_message = fake_send_chat_message

    state = bot._get_runtime_state("telegram:dm:retry")
    bot._sync_state_into_runtime_v2_loop("telegram:dm:retry", state)
    state.autonomy_context = {"run_id": "autonomy_retry", "status": "resumable_pause", "progress_delivery": {}}
    state.task_status = "resumable_pause"

    run = AutonomyRun.create(
        session_key="telegram:dm:retry",
        surface="telegram",
        status=AutonomyRunStatus.RESUMABLE_PAUSE,
        executor_kind=AutonomyExecutorKind.GENERIC_RUNTIME,
        objective="长任务",
        current_phase="planning_current_slice",
    )
    run.metadata = {"chat_id": 8420019401}
    run.resume_count = bot.autonomy_transient_retry_limit
    run.runtime_state_snapshot = state.to_snapshot()
    run.last_result_summary = {"status": "resumable_pause", "finish_reason": "transient_decision_error"}

    outcome = await bot._resume_telegram_autonomy_run(run, trigger_source="driver")

    assert outcome.status == AutonomyRunStatus.BLOCKED
    assert outcome.hard_blocker_reason == "transient_retry_budget_exceeded"
    assert len(sent) == 1
    assert sent[0][0] == 8420019401
    assert "连续多次临时失败" in sent[0][1]


@pytest.mark.asyncio
async def test_resume_telegram_autonomy_run_uses_longer_backoff_for_rate_limited_runs(monkeypatch):
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    async def fake_continue_runtime_v2_turn(session_key, state, **kwargs):
        return TelegramTurnResult(
            status="resumable_pause",
            state=state,
            reply=TelegramTurnReply(
                reply_text="",
                delivery_kind="progress",
                status="resumable_pause",
            ),
            finish_reason="transient_decision_error",
            checkpoint_payload={"slice": 2},
        )

    monkeypatch.setattr("app.telegram_bot.asyncio.sleep", fake_sleep)
    bot._continue_runtime_v2_turn = fake_continue_runtime_v2_turn

    state = bot._get_runtime_state("telegram:dm:rate-limit")
    state.task_status = "resumable_pause"
    state.last_model_action = {
        "kind": "transient_decision_error",
        "status_code": 429,
        "retry_after_seconds": 45,
        "transient_kind": "rate_limited",
    }
    state.autonomy_context = {"run_id": "autonomy_rate_limit", "status": "resumable_pause", "progress_delivery": {}}

    run = AutonomyRun.create(
        session_key="telegram:dm:rate-limit",
        surface="telegram",
        status=AutonomyRunStatus.RESUMABLE_PAUSE,
        executor_kind=AutonomyExecutorKind.GENERIC_RUNTIME,
        objective="长任务",
        current_phase="planning_current_slice",
    )
    run.metadata = {"chat_id": 8420019401}
    run.resume_count = 1
    run.runtime_state_snapshot = state.to_snapshot()
    run.last_result_summary = {
        "status": "resumable_pause",
        "finish_reason": "transient_decision_error",
        "status_code": 429,
    }

    outcome = await bot._resume_telegram_autonomy_run(run, trigger_source="driver")

    assert outcome.status == AutonomyRunStatus.RESUMABLE_PAUSE
    assert slept == [60]


@pytest.mark.asyncio
async def test_manual_resume_resets_delivery_state_and_re_emits_progress():
    bot = TelegramBot(token="test-token", use_runtime_v2=True)

    async def fake_continue_runtime_v2_turn(session_key, state, **kwargs):
        return TelegramTurnResult(
            status="resumable_pause",
            state=state,
            reply=TelegramTurnReply(
                reply_text="",
                delivery_kind="progress",
                status="resumable_pause",
            ),
            finish_reason="transient_decision_error",
            checkpoint_payload={"slice": 2},
        )

    bot._continue_runtime_v2_turn = fake_continue_runtime_v2_turn

    class DummySentMessage:
        def __init__(self, chat_id, message_id):
            self.message_id = message_id
            self.chat = type("Chat", (), {"id": chat_id})()

    class DummyBot:
        def __init__(self):
            self.sent = []

        async def send_message(self, chat_id, text):
            self.sent.append((chat_id, text))
            return DummySentMessage(chat_id, 9101)

    bot.app = type("DummyApp", (), {"bot": DummyBot()})()

    state = bot._get_runtime_state("telegram:dm:manual-retry")
    state.final_sent = True
    state.task_status = "blocked"
    state.autonomy_context = {
        "run_id": "autonomy_manual_retry",
        "status": "blocked",
        "progress_delivery": {
            "last_phase_key": "planning_current_slice",
            "last_text": "我继续处理这个任务，做完直接给你结果。",
            "last_sent_at": 123.0,
        },
    }

    run = AutonomyRun.create(
        session_key="telegram:dm:manual-retry",
        surface="telegram",
        status=AutonomyRunStatus.BLOCKED,
        executor_kind=AutonomyExecutorKind.GENERIC_RUNTIME,
        objective="长任务恢复",
        current_phase="blocked",
    )
    run.metadata = {"chat_id": 8420019401}
    run.runtime_state_snapshot = state.to_snapshot()
    run.last_result_summary = {"status": "blocked", "finish_reason": "transient_retry_budget_exceeded"}

    outcome = await bot._resume_telegram_autonomy_run(run, trigger_source="manual")

    assert outcome.status == AutonomyRunStatus.RESUMABLE_PAUSE
    assert bot.app.bot.sent == []


@pytest.mark.asyncio
async def test_resume_telegram_autonomy_run_blocks_after_repeated_no_progress():
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    sent = []

    async def fake_send_chat_message(chat_id, text, finalize_evidence=True):
        sent.append((chat_id, text, finalize_evidence))

    async def fake_continue_runtime_v2_turn(session_key, state, **kwargs):
        state.current_step = "tool:file"
        state.last_tool_result = {
            "tool": "file",
            "success": True,
            "metadata": {"path": r"D:\Project\AIProject\MyProject\Test2\print_hello_world.py"},
        }
        state.last_verification_result = {
            "passed": False,
            "reason": "missing_target",
            "verifier": "none",
            "target": None,
            "evidence": {},
            "warnings": [],
        }
        return TelegramTurnResult(
            status="resumable_pause",
            state=state,
            reply=TelegramTurnReply(
                reply_text="",
                delivery_kind="progress",
                status="resumable_pause",
            ),
            finish_reason="max_steps_exhausted",
            checkpoint_payload={"slice": 2},
        )

    bot._send_chat_message = fake_send_chat_message
    bot._continue_runtime_v2_turn = fake_continue_runtime_v2_turn

    state = bot._get_runtime_state("telegram:dm:no-progress")
    state.task_status = "resumable_pause"
    state.output_obligations = [
        {"name": "demo.txt", "path": r"D:\Project\AIProject\MyProject\Test2\demo.txt", "status": "verified"},
        {"name": "print hello world.py", "path": r"D:\Project\AIProject\MyProject\Test2\print hello world.py", "status": "pending"},
    ]
    state.autonomy_context = {"run_id": "autonomy_no_progress", "status": "resumable_pause", "progress_delivery": {}}

    run = AutonomyRun.create(
        session_key="telegram:dm:no-progress",
        surface="telegram",
        status=AutonomyRunStatus.RESUMABLE_PAUSE,
        executor_kind=AutonomyExecutorKind.GENERIC_RUNTIME,
        objective="长任务",
        current_phase="planning_current_slice",
    )
    run.metadata = {"chat_id": 8420019401}
    run.runtime_state_snapshot = state.to_snapshot()
    run.last_result_summary = {"status": "resumable_pause", "finish_reason": "max_steps_exhausted"}

    outcome = None
    for index in range(bot.autonomy_no_progress_retry_limit):
        outcome = await bot._resume_telegram_autonomy_run(run, trigger_source="driver")
        run.runtime_state_snapshot = outcome.runtime_state_snapshot
        run.last_result_summary = outcome.last_result_summary
        run.hard_blocker_reason = outcome.hard_blocker_reason
        run.status = outcome.status

    assert outcome is not None
    assert outcome.status == AutonomyRunStatus.BLOCKED
    assert outcome.hard_blocker_reason == "no_progress_stall_detected"
    assert len(sent) == 1
    assert "连续多次没有新进展" in sent[0][1]
