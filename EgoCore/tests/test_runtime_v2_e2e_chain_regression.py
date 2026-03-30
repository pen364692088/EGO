import pytest

from app.telegram_bot import TelegramBot


class DummyBot:
    def __init__(self):
        self.sent = []

    async def send_chat_action(self, chat_id, action):
        return None

    async def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))
        return type("DummySentMessage", (), {"message_id": 9001, "chat": type("Chat", (), {"id": chat_id})()})()


class DummyChat:
    id = 123
    type = "private"


class DummyUser:
    id = 456
    username = "moonlight"


class DummyMessage:
    def __init__(self, text: str, message_id: int):
        self.text = text
        self.message_id = message_id
        self.reply_to_message = None
        self.sent = []

    async def reply_text(self, text, parse_mode=None):
        self.sent.append(text)


class DummyUpdate:
    def __init__(self, text: str, message_id: int):
        self.message = DummyMessage(text, message_id)
        self.effective_chat = DummyChat()
        self.effective_user = DummyUser()


@pytest.mark.asyncio
async def test_runtime_v2_task_probe_challenge_chain_stays_consistent(monkeypatch):
    """任务、短探针、挑战追问链保持一致性 - 不再发送 generic ACK/Busy"""
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    bot.app = type("A", (), {"bot": DummyBot()})()
    monkeypatch.setattr(bot, "_get_conflicted_active_run", lambda _session_key: None)
    runtime_loop = bot._get_runtime_v2_loop()

    session_id = "telegram:dm:456"
    state = bot._get_runtime_state(session_id)
    bot._sync_state_into_runtime_v2_loop(session_id, state)

    # 模拟不同的 turn 结果
    turn_count = [0]

    async def fake_run_turn_typed(session_id, user_input):
        from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult

        # 模拟 start_turn() 的效果（重置状态）
        state.start_turn()

        turn_count[0] += 1
        print(f"Turn {turn_count[0]}: {user_input!r}")

        if turn_count[0] == 1:
            # 第一个 turn: 任务完成
            state.mark_task_completed()
            return RuntimeV2TurnResult(
                status="completed_verified",
                state=state,
                reply=RuntimeV2Reply(
                    reply_text="已经改好了，背景换成了复古风格。",
                    delivery_kind="final",
                    status="completed_verified",
                ),
            )

        # 后续 turn: 正常处理
        state.task_status = "waiting_input"
        state.waiting_for_user_input = True
        return RuntimeV2TurnResult(
            status="waiting_input",
            state=state,
            reply=RuntimeV2Reply(
                reply_text="我继续检查刚才那个文件。",
                delivery_kind="progress",
                status="waiting_input",
            ),
        )

    monkeypatch.setattr(runtime_loop, "run_turn_typed", fake_run_turn_typed)

    update1 = DummyUpdate("/home/moonlight/Project/Github/MyProject/TestProject/hello.html 配色不太好看,你换成复古风格", 301)
    await bot.handle_message(update1, None)

    update2 = DummyUpdate("还在吗", 302)
    await bot.handle_message(update2, None)

    update3 = DummyUpdate("你没改啊", 303)
    await bot.handle_message(update3, None)

    # 不再发送 generic ACK，直接发送结果
    assert update1.message.sent == ["已经改好了，背景换成了复古风格。"]
    # 短探针进入 runtime，得到正常回复
    assert update2.message.sent == ["我继续检查刚才那个文件。"] or bot.app.bot.sent[-1] == (123, "我继续检查刚才那个文件。")
    # 挑战轮次进入 runtime，得到正常回复
    assert update3.message.sent == ["我继续检查刚才那个文件。"] or bot.app.bot.sent[-1] == (123, "我继续检查刚才那个文件。")
