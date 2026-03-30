import pytest

from app.autonomy import AutonomyExecutorKind, AutonomyRun, AutonomyRunStatus
from app.runtime_v2.run_items import build_run_items_from_request
from app.runtime_v2.cli import run_cli
from app.telegram_bot import TelegramBot


def test_runtime_v2_cli_entry_imports():
    assert callable(run_cli)


@pytest.mark.asyncio
async def test_telegram_bot_runtime_v2_path(monkeypatch):
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    runtime_loop = bot._get_runtime_v2_loop()

    class DummyBot:
        async def send_chat_action(self, chat_id, action):
            return None

    class DummyMessage:
        text = "你好"
        message_id = 1
        reply_to_message = None
        last_text = None
        async def reply_text(self, text, parse_mode=None):
            self.last_text = text

    class DummyChat:
        id = 123
        type = "private"

    class DummyUser:
        id = 456
        username = "moonlight"

    class DummyUpdate:
        message = DummyMessage()
        effective_chat = DummyChat()
        effective_user = DummyUser()

    bot.app = type('A', (), {'bot': DummyBot()})()

    async def fake_run_turn_typed(session_id, user_input):
        from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
        return RuntimeV2TurnResult(
            status="chat",
            state=runtime_loop.get_state(session_id),
            reply=RuntimeV2Reply(reply_text="你好，我在。", delivery_kind="chat", status="chat"),
        )

    monkeypatch.setattr(runtime_loop, "run_turn_typed", fake_run_turn_typed)
    await bot.handle_message(DummyUpdate(), None)
    assert bot.runtime_v2_loop is not None
    assert DummyUpdate.message.last_text == "你好，我在。"


@pytest.mark.asyncio
async def test_telegram_bot_runtime_v2_busy_short_probe_enters_runtime(monkeypatch):
    """短探针不再被吸收，而是进入 runtime 获取正常回复"""
    bot = TelegramBot(token="test-token", use_runtime_v2=True)

    class DummyBot:
        async def send_chat_action(self, chat_id, action):
            return None

    class DummyMessage:
        text = "?"
        message_id = 2
        reply_to_message = None
        last_text = None
        async def reply_text(self, text, parse_mode=None):
            self.last_text = text

    class DummyChat:
        id = 123
        type = "private"

    class DummyUser:
        id = 456
        username = "moonlight"

    class DummyUpdate:
        message = DummyMessage()
        effective_chat = DummyChat()
        effective_user = DummyUser()

    bot.app = type('A', (), {'bot': DummyBot()})()
    runtime_loop = bot._get_runtime_v2_loop()
    state = bot._get_runtime_state('telegram:dm:456')
    bot._sync_state_into_runtime_v2_loop('telegram:dm:456', state)
    state.task_status = 'running'
    state.current_goal = '修改 hello.html 配色'

    async def fake_run_turn_typed(session_id, user_input):
        from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
        state.start_turn()  # 模拟 run_turn_typed 的行为
        return RuntimeV2TurnResult(
            status='waiting_input',
            state=state,
            reply=RuntimeV2Reply(
                reply_text='我正在处理你的任务，请稍等。',
                delivery_kind='progress',
                status='waiting_input',
            ),
        )

    monkeypatch.setattr(runtime_loop, 'run_turn_typed', fake_run_turn_typed)
    await bot.handle_message(DummyUpdate(), None)
    # 短探针现在会进入 runtime，返回正常回复
    assert DummyUpdate.message.last_text == '我正在处理你的任务，请稍等。'


@pytest.mark.asyncio
async def test_telegram_bot_runtime_v2_recent_completion_short_probe_enters_runtime(monkeypatch):
    """短探针现在先走 control-plane，不再进入 execute/runtime 路径"""
    bot = TelegramBot(token="test-token", use_runtime_v2=True)

    class DummyBot:
        async def send_chat_action(self, chat_id, action):
            return None

    class DummyMessage:
        text = "还在吗"
        message_id = 3
        reply_to_message = None
        last_text = None
        call_count = 0
        async def reply_text(self, text, parse_mode=None):
            self.last_text = text
            self.call_count += 1

    class DummyChat:
        id = 123
        type = "private"

    class DummyUser:
        id = 456
        username = "moonlight"

    class DummyUpdate:
        message = DummyMessage()
        effective_chat = DummyChat()
        effective_user = DummyUser()

    bot.app = type('A', (), {'bot': DummyBot()})()
    runtime_loop = bot._get_runtime_v2_loop()
    state = bot._get_runtime_state('telegram:dm:456')
    bot._sync_state_into_runtime_v2_loop('telegram:dm:456', state)
    state.mark_task_completed()
    monkeypatch.setattr(bot, "_get_active_run", lambda session_key: None)

    async def fake_run_turn_typed(session_id, user_input):
        from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
        state.start_turn()  # 模拟 run_turn_typed 的行为
        return RuntimeV2TurnResult(
            status='waiting_input',
            state=state,
            reply=RuntimeV2Reply(
                reply_text='任务已完成，还有什么需要帮忙的吗？',
                delivery_kind='progress',
                status='waiting_input',
            ),
        )

    monkeypatch.setattr(runtime_loop, 'run_turn_typed', fake_run_turn_typed)
    await bot.handle_message(DummyUpdate(), None)
    await bot.handle_message(DummyUpdate(), None)
    # 短探针现在由 control-plane 直接响应
    assert DummyUpdate.message.last_text == '当前没有运行中的任务。'
    assert DummyUpdate.message.call_count == 2


@pytest.mark.asyncio
async def test_telegram_bot_manual_resume_is_control_plane_with_immediate_ack(monkeypatch, tmp_path):
    bot = TelegramBot(token="test-token", use_runtime_v2=True)

    class DummyBot:
        async def send_chat_action(self, chat_id, action):
            return None

    class DummyMessage:
        text = "继续"
        message_id = 4
        reply_to_message = None
        last_text = None

        async def reply_text(self, text, parse_mode=None):
            self.last_text = text

    class DummyChat:
        id = 123
        type = "private"

    class DummyUser:
        id = 456
        username = "moonlight"

    class DummyUpdate:
        message = DummyMessage()
        effective_chat = DummyChat()
        effective_user = DummyUser()

    bot.app = type("A", (), {"bot": DummyBot()})()
    monkeypatch.setattr(bot, "_publish_phase1_event", lambda **kwargs: __import__("asyncio").sleep(0))

    state = bot._get_runtime_state("telegram:dm:456")
    state.ingress_context = {
        "runtime_action": "execute_task",
        "requested_output": {"target_directory": str(tmp_path)},
    }
    state.set_run_items(
        build_run_items_from_request(
            f"在 {tmp_path} 目录下创建 demo.txt。",
            ingress_context=state.ingress_context,
        )
    )
    state.ensure_active_run_item_started()
    state.mark_active_run_item_blocked({"reason": "run_item_missing"})

    run = AutonomyRun.create(
        session_key="telegram:dm:456",
        surface="telegram",
        status=AutonomyRunStatus.BLOCKED,
        executor_kind=AutonomyExecutorKind.GENERIC_RUNTIME,
        objective="继续当前任务",
        current_phase="blocked",
    )
    run.hard_blocker_reason = "no_progress_stall_detected"
    run.runtime_state_snapshot = state.to_snapshot()
    bot.autonomy_orchestrator.repository.create(run)

    resumed = {}

    async def fake_publish_phase1_event(**kwargs):
        return None

    def fake_spawn_manual_resume(run_id):
        resumed["run_id"] = run_id
        resumed["trigger_source"] = "manual"

    monkeypatch.setattr(bot, "_publish_phase1_event", fake_publish_phase1_event)
    monkeypatch.setattr(bot, "_spawn_manual_resume", fake_spawn_manual_resume)

    await bot.handle_message(DummyUpdate(), None)

    assert DummyUpdate.message.last_text == "继续处理 demo.txt。"
    assert resumed == {"run_id": run.id, "trigger_source": "manual"}


@pytest.mark.asyncio
async def test_telegram_bot_conflict_resolution_outside_conflict_returns_invalid_reply():
    bot = TelegramBot(token="test-token", use_runtime_v2=True)

    class DummyBot:
        async def send_chat_action(self, chat_id, action):
            return None

    class DummyMessage:
        text = "替换"
        message_id = 5
        reply_to_message = None
        last_text = None

        async def reply_text(self, text, parse_mode=None):
            self.last_text = text

    class DummyChat:
        id = 123
        type = "private"

    class DummyUser:
        id = 456
        username = "moonlight"

    class DummyUpdate:
        message = DummyMessage()
        effective_chat = DummyChat()
        effective_user = DummyUser()

    bot.app = type("A", (), {"bot": DummyBot()})()
    await bot.handle_message(DummyUpdate(), None)

    assert DummyUpdate.message.last_text == "当前没有待确认的新任务。"
