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
async def test_runtime_v2_task_then_challenge_followup_stays_coherent(monkeypatch):
    """任务执行后挑战追问保持一致性 - 不再发送 generic ACK"""
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    bot.app = type("A", (), {"bot": DummyBot()})()
    monkeypatch.setattr(bot, "_get_conflicted_active_run", lambda _session_key: None)
    runtime_loop = bot._get_runtime_v2_loop()

    session_id = "telegram:dm:456"
    state = bot._get_runtime_state(session_id)
    bot._sync_state_into_runtime_v2_loop(session_id, state)

    first = {
        "status": "completed_verified",
        "delivery_kind": "final",
        "reply_text": "已经改好了，背景换成了复古风格。",
        "state": state,
    }
    second = {
        "status": "waiting_input",
        "delivery_kind": "progress",
        "reply_text": "我继续检查刚才那个文件。",
        "state": state,
    }
    results = iter([first, second])

    async def fake_run_turn_typed(session_id, user_input):
        from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
        payload = next(results)
        return RuntimeV2TurnResult(
            status=payload["status"],
            state=payload["state"],
            reply=RuntimeV2Reply(
                reply_text=payload["reply_text"],
                delivery_kind=payload["delivery_kind"],
                status=payload["status"],
            ),
        )

    monkeypatch.setattr(runtime_loop, "run_turn_typed", fake_run_turn_typed)

    update1 = DummyUpdate("/home/moonlight/Project/Github/MyProject/TestProject/hello.html 配色不太好看,你换成复古风格", 101)
    await bot.handle_message(update1, None)

    update2 = DummyUpdate("你没改啊", 102)
    await bot.handle_message(update2, None)

    # 不再发送 generic ACK，直接发送结果
    assert update1.message.sent == ["已经改好了，背景换成了复古风格。"]
    allowed_followups = {"我继续检查刚才那个文件。", "开始处理 hello.html。"}
    delivered = set(update2.message.sent)
    delivered.update(text for _, text in bot.app.bot.sent)
    assert not any("当前已有一个活跃任务" in text for text in delivered)
    if delivered:
        assert delivered & allowed_followups


@pytest.mark.asyncio
async def test_runtime_v2_short_probe_no_longer_sends_busy_notice(monkeypatch):
    """短探针直接返回程序化状态，不再静默吸收或走 LLM。"""
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    bot.app = type("A", (), {"bot": DummyBot()})()
    monkeypatch.setattr(bot, "_get_conflicted_active_run", lambda _session_key: None)
    session_id = "telegram:dm:456"
    runtime_loop = bot._get_runtime_v2_loop()
    state = bot._get_runtime_state(session_id)
    bot._sync_state_into_runtime_v2_loop(session_id, state)
    state.task_status = "running"
    state.current_goal = "修改 hello.html 配色"

    async def fake_run_turn_typed(session_id, user_input):
        from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
        return RuntimeV2TurnResult(
            status="waiting_input",
            state=state,
            reply=RuntimeV2Reply(
                reply_text="",  # 空回复，不发送 generic busy
                delivery_kind="progress",
                status="waiting_input",
                suppressible=True,
            ),
        )

    monkeypatch.setattr(runtime_loop, "run_turn_typed", fake_run_turn_typed)

    update1 = DummyUpdate("还在吗", 201)
    await bot.handle_message(update1, None)
    update2 = DummyUpdate("还在吗", 202)
    await bot.handle_message(update2, None)

    assert update1.message.sent == ["正在处理：修改 hello.html 配色"]
    assert update2.message.sent == ["正在处理：修改 hello.html 配色"]
