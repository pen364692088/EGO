import pytest

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
