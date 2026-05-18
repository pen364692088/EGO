import pytest

from app.runtime_v2.action_protocol import RuntimeV2Action
from app.runtime_v2.loop import RuntimeV2Loop
from app.telegram_bot import TelegramBot


@pytest.mark.asyncio
async def test_runtime_v2_loop_sets_delivery_kind_for_complete(monkeypatch, tmp_path):
    loop = RuntimeV2Loop()
    target = tmp_path / "hello.html"
    target.write_text("<body style='background:#eee'>hi</body>", encoding="utf-8")

    actions = iter([
        RuntimeV2Action.from_model_output('{"type":"complete","summary":"已完成","verification":{"target":"' + str(target) + '","expected":"background"}}'),
    ])

    async def fake_decide(_state):
        return next(actions)

    monkeypatch.setattr(loop, "_decide", fake_decide)
    result = await loop.run_turn_typed("session:test", "请修改 hello.html")
    assert result.status == "completed_verified"
    assert result.delivery_kind == "final"


@pytest.mark.asyncio
async def test_runtime_v2_challenge_turn_keeps_specific_progress_text(monkeypatch):
    bot = TelegramBot(token="test-token", use_runtime_v2=True)

    class DummyBot:
        async def send_chat_action(self, chat_id, action):
            return None

    class DummyMessage:
        text = "你没改啊"
        message_id = 19
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
    state = bot.runtime_v2_loop.get_state("telegram:dm:456")
    state.mark_task_completed()

    async def fake_run_turn_typed(session_id, user_input):
        from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
        # 模拟 start_turn 的效果：重置 final_sent
        state.final_sent = False
        state.active_turn_status = "running"
        return RuntimeV2TurnResult(
            status="waiting_input",
            state=state,
            reply=RuntimeV2Reply(reply_text="我继续检查刚才那个文件。", delivery_kind="progress", status="waiting_input"),
        )

    monkeypatch.setattr(bot.runtime_v2_loop, "run_turn_typed", fake_run_turn_typed)
    await bot.handle_message(DummyUpdate(), None)
    assert DummyUpdate.message.last_text == "我继续检查刚才那个文件。"
