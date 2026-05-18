import asyncio

import pytest

from app.runtime_v2.action_protocol import RuntimeV2Action
from app.runtime_v2.loop import RuntimeV2Loop
from app.runtime_v2.semantic_parser import semantic_parse_message
from app.telegram_bot import TelegramBot


def test_action_protocol_invalid_json_returns_internal_ask_without_user_text():
    action = RuntimeV2Action.from_model_output('not json at all')
    assert action.type == 'ask'
    assert action.question is None
    assert action.raw['kind'] == 'invalid_json'


@pytest.mark.asyncio
async def test_runtime_v2_loop_retries_invalid_json_once(monkeypatch):
    loop = RuntimeV2Loop()
    actions = iter([
        RuntimeV2Action.from_model_output('not json at all'),
        RuntimeV2Action.from_model_output('{"type":"chat","message":"你好，我在。"}'),
    ])

    async def fake_decide(_state):
        return next(actions)

    monkeypatch.setattr(loop, '_decide', fake_decide)
    result = await loop.run_turn_typed('session:test', '你好')
    assert result.status == 'chat'
    assert result.reply_text == '你好，我在。'


@pytest.mark.asyncio
async def test_challenge_turn_does_not_get_absorbed_as_busy_placeholder(monkeypatch):
    bot = TelegramBot(token='test-token', use_runtime_v2=True)

    class DummyBot:
        async def send_chat_action(self, chat_id, action):
            return None

    class DummyMessage:
        text = '你没改啊'
        message_id = 9
        reply_to_message = None
        last_text = None
        async def reply_text(self, text, parse_mode=None):
            self.last_text = text

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
    state = bot._get_runtime_state('telegram:dm:456')
    state.task_status = 'running'
    state.current_goal = '修改 test.html 配色'

    async def fake_run_turn_typed(session_id, user_input):
        from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
        return RuntimeV2TurnResult(
            status='waiting_input',
            state=state,
            reply=RuntimeV2Reply(reply_text='我继续检查刚才那个文件。', delivery_kind='progress', status='waiting_input'),
        )

    async def fake_runner_run_turn(*, session_key, user_input, state, **kwargs):
        return bot.runtime_v2_fallback_runner.adapt_result(await fake_run_turn_typed(session_key, user_input))

    monkeypatch.setattr(bot, '_should_use_native_loop', lambda ingress, state: False)
    monkeypatch.setattr(bot.runtime_v2_fallback_runner, 'run_turn', fake_runner_run_turn)
    await bot.handle_message(DummyUpdate(), None)
    assert DummyUpdate.message.last_text == '我继续检查刚才那个文件。'


@pytest.mark.asyncio
async def test_runtime_v2_typing_starts_before_semantic_parse_finishes(monkeypatch):
    bot = TelegramBot(token='test-token', use_runtime_v2=True)
    observed = {"typing_calls": 0, "typing_seen_before_parse_release": False}
    parse_gate = asyncio.Event()

    class DummyBot:
        async def send_chat_action(self, chat_id, action):
            if action == "typing":
                observed["typing_calls"] += 1

    class DummyMessage:
        text = '帮我改一下 hello.html 配色'
        message_id = 10
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

    async def fake_inspect(text, state, llm_client):
        observed["typing_seen_before_parse_release"] = observed["typing_calls"] > 0
        await parse_gate.wait()
        return bot.runtime_v2_bridge.inspect_ingress(text, state)

    async def fake_run_turn_typed(session_id, user_input):
        from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
        state = bot._get_runtime_state(session_id)
        return RuntimeV2TurnResult(
            status='chat',
            state=state,
            reply=RuntimeV2Reply(reply_text='已收到。', delivery_kind='chat', status='chat'),
        )

    monkeypatch.setattr(bot.runtime_v2_bridge, 'inspect_ingress_semantic', fake_inspect)
    async def fake_runner_run_turn(*, session_key, user_input, state, **kwargs):
        return bot.runtime_v2_fallback_runner.adapt_result(await fake_run_turn_typed(session_key, user_input))

    monkeypatch.setattr(bot.runtime_v2_fallback_runner, 'run_turn', fake_runner_run_turn)

    task = asyncio.create_task(bot.handle_message(DummyUpdate(), None))
    await asyncio.sleep(0.05)
    parse_gate.set()
    await task

    assert observed["typing_seen_before_parse_release"] is True
    assert observed["typing_calls"] >= 1


@pytest.mark.asyncio
async def test_semantic_parse_short_probe_uses_fast_heuristic_without_llm():
    class FailingClient:
        def generate(self, prompt):
            raise AssertionError("fast heuristic should bypass LLM")

    graph = await semantic_parse_message(
        text="你没改啊",
        recent_turns=[],
        runtime_snapshot={},
        llm_client=FailingClient(),
    )

    assert graph.parser_source == "heuristic_parser"
    assert graph.primary_intent == "correction"
    assert graph.has_correction is True
