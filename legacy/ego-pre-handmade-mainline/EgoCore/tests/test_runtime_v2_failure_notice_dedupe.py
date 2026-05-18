import pytest

from app.telegram_bot import TelegramBot


@pytest.mark.asyncio
async def test_runtime_v2_generic_busy_is_not_sent(monkeypatch):
    """
    WS-4: generic busy 不再默认发送
    
    旧行为：发送 "我还在继续处理刚才那个任务。"
    新行为：generic busy 被 drop
    """
    bot = TelegramBot(token='test-token', use_runtime_v2=True)

    class DummyBot:
        async def send_chat_action(self, chat_id, action):
            return None

    class DummyMessage:
        text = '/home/test.html 配色不太好看'
        message_id = 11
        reply_to_message = None
        sent = []
        async def reply_text(self, text, parse_mode=None):
            self.sent.append(text)

    class DummyChat:
        id = 123
        type = 'private'

    class DummyUser:
        id = 456
        username = 'moonlight'

    class DummyUpdate:
        message = DummyMessage()
        effective_chat = DummyChat()
        effective_user = DummyUser()

    bot.app = type('A', (), {'bot': DummyBot()})()

    async def fake_run_turn_typed(session_id, user_input):
        from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
        return RuntimeV2TurnResult(
            status='waiting_input',
            state=bot.runtime_v2_loop.get_state(session_id),
            reply=RuntimeV2Reply(
                reply_text='我还在继续处理刚才那个任务。',
                delivery_kind='progress',
                status='waiting_input',
                suppressible=True,
            ),
        )

    monkeypatch.setattr(bot.runtime_v2_loop, 'run_turn_typed', fake_run_turn_typed)
    await bot.handle_message(DummyUpdate(), None)

    # WS-4: generic busy 不再发送
    failure_msgs = [x for x in DummyUpdate.message.sent if '继续处理刚才那个任务' in x]
    assert len(failure_msgs) == 0
