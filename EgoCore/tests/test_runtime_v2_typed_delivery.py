import pytest

from app.autonomy import AutonomyExecutorKind, AutonomyRun, AutonomyRunStatus
from app.runtime_v2.progress_events import ProgressEvent, ProgressEventType
from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
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
