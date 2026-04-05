from datetime import datetime, timezone
from types import SimpleNamespace
import time

import pytest

import app.telegram_bot as telegram_bot_module
from app.autonomy import AutonomyExecutorKind, AutonomyRun, AutonomyRunStatus, AutonomyStopReason
from app.runtime_v2.run_items import build_run_items_from_request
from app.runtime_v2.cli import run_cli
from app.telegram_bot import TelegramBot
from app.telegram_evidence_collector import TelegramEvidenceCollector
from app.telegram_runtime_result import TelegramTurnReply, TelegramTurnResult


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
async def test_telegram_bot_runtime_v2_natural_language_status_stays_in_chat(monkeypatch):
    """自然语言进度词退出 control-plane，按聊天主链处理。"""
    bot = TelegramBot(token="test-token", use_runtime_v2=True)

    class DummyBot:
        async def send_chat_action(self, chat_id, action):
            return None

    class DummyMessage:
        text = "好了吗"
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
    state = bot._get_runtime_state('telegram:dm:456')
    bot._sync_state_into_runtime_v2_loop('telegram:dm:456', state)
    state.mark_task_completed()

    async def fake_run_primary_turn(**kwargs):
        from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
        state.start_turn()  # 模拟 run_turn_typed 的行为
        return RuntimeV2TurnResult(
            status='chat',
            state=state,
            reply=RuntimeV2Reply(
                reply_text='刚才那件事已经停下来了；如果你要查状态，用 /status。',
                delivery_kind='chat',
                status='chat',
            ),
        )

    monkeypatch.setattr(bot, "_run_primary_turn", fake_run_primary_turn)
    await bot.handle_message(DummyUpdate(), None)
    await bot.handle_message(DummyUpdate(), None)
    assert DummyUpdate.message.last_text == '刚才那件事已经停下来了；如果你要查状态，用 /status。'
    assert DummyUpdate.message.call_count == 2


@pytest.mark.asyncio
async def test_telegram_bot_delivery_applies_output_check_host_completion_fallback(tmp_path):
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    events = []

    class DummyMessage:
        last_text = None
        async def reply_text(self, text, parse_mode=None):
            self.last_text = text

    class DummyUpdate:
        message = DummyMessage()

    async def fake_publish_phase1_event(**kwargs):
        events.append(kwargs)

    bot._publish_phase1_event = fake_publish_phase1_event

    state = bot._get_runtime_state("telegram:dm:456")
    state.ingress_context = {
        "runtime_action": "execute_task",
        "requested_output": {"target_directory": str(tmp_path)},
    }
    run_items = build_run_items_from_request(
        f"在 {tmp_path} 目录下创建 demo.txt。最后做一个print hello world.py文件",
        ingress_context=state.ingress_context,
    )
    for item in run_items:
        item.status = "verified"
    state.set_run_items(run_items)
    state.last_tool_result = {
        "success": True,
        "tool": "file",
        "stdout": "done",
        "metadata": {"path": str(tmp_path / "demo.txt")},
    }

    result = TelegramTurnResult(
        status="completed_verified",
        state=state,
        reply=TelegramTurnReply(
            reply_text="",
            delivery_kind="final",
            status="completed_verified",
        ),
    )

    await bot._deliver_runtime_v2_result(
        DummyUpdate(),
        state,
        result,
        is_challenge_turn=False,
        ingress_message_id=1,
        trace_id="trace",
    )

    assert "已完成这些任务" in DummyUpdate.message.last_text
    assert any(event["kind"] == "tool_delivery_bridge" for event in events)


@pytest.mark.asyncio
async def test_telegram_bot_bare_continue_no_longer_manual_resumes(monkeypatch, tmp_path):
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

    async def fake_run_primary_turn(**kwargs):
        from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
        state.start_turn()
        return RuntimeV2TurnResult(
            status="chat",
            state=state,
            reply=RuntimeV2Reply(
                reply_text="如果你是说恢复任务，用 /resume。",
                delivery_kind="chat",
                status="chat",
            ),
        )

    monkeypatch.setattr(bot, "_run_primary_turn", fake_run_primary_turn)

    await bot.handle_message(DummyUpdate(), None)

    assert DummyUpdate.message.last_text == "如果你是说恢复任务，用 /resume。"


@pytest.mark.asyncio
async def test_telegram_bot_manual_resume_never_stays_silent_when_no_new_milestone(monkeypatch, tmp_path):
    bot = TelegramBot(token="test-token", use_runtime_v2=True)

    state = bot._get_runtime_state("telegram:dm:456")
    state.ingress_context = {
        "runtime_action": "execute_task",
        "requested_output": {"target_directory": str(tmp_path)},
    }
    prompt = (
        f"在 {tmp_path} 目录下创建 demo.txt，写入 hello。"
        "然后读取这个文件确认内容。最后做一个print hello world.py文件"
    )
    state.begin_execute_task(prompt, build_run_items_from_request(prompt, ingress_context=state.ingress_context), state.ingress_context)
    state.ensure_active_run_item_started()
    state.mark_active_run_item_blocked({"reason": "no_progress_stall_detected"})

    run = AutonomyRun.create(
        session_key="telegram:dm:456",
        surface="telegram",
        status=AutonomyRunStatus.BLOCKED,
        executor_kind=AutonomyExecutorKind.GENERIC_RUNTIME,
        objective=prompt,
        current_phase="blocked",
    )
    run.hard_blocker_reason = AutonomyStopReason.NO_PROGRESS_STALL_DETECTED.value
    run.runtime_state_snapshot = state.to_snapshot()
    run.metadata = {"chat_id": 123, "trace_id": "trace-1", "ingress_message_id": 9}

    sent_texts = []

    async def fake_publish_phase1_event(**kwargs):
        return None

    async def fake_send_chat_message(chat_id, text, finalize_evidence=True):
        sent_texts.append(text)

    async def fake_continue_runtime_v2_turn(**kwargs):
        restored_state = kwargs["state"]
        restored_state.task_status = "resumable_pause"
        return TelegramTurnResult(
            status="resumable_pause",
            state=restored_state,
            reply=TelegramTurnReply(
                reply_text="",
                delivery_kind="progress",
                status="resumable_pause",
            ),
            finish_reason=AutonomyStopReason.MAX_STEPS_EXHAUSTED.value,
            checkpoint_payload={"state_snapshot": restored_state.to_snapshot()},
        )

    monkeypatch.setattr(bot, "_publish_phase1_event", fake_publish_phase1_event)
    monkeypatch.setattr(bot, "_send_chat_message", fake_send_chat_message)
    monkeypatch.setattr(bot, "_continue_runtime_v2_turn", fake_continue_runtime_v2_turn)
    monkeypatch.setattr(bot, "_deliver_runtime_progress_events", lambda **kwargs: __import__("asyncio").sleep(0, result=0))

    outcome = await bot._resume_telegram_autonomy_run(run, "manual")

    assert outcome.status == AutonomyRunStatus.BLOCKED
    assert sent_texts
    assert "这次继续后仍没有新的可验证进展" in sent_texts[-1]
    assert "创建 demo.txt" in sent_texts[-1]


@pytest.mark.asyncio
async def test_telegram_bot_runtime_delivery_uses_verbatim_directory_output(monkeypatch):
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    events = []

    class DummyMessage:
        message_id = 9

        def __init__(self):
            self.texts = []

        async def reply_text(self, text, parse_mode=None):
            self.texts.append(text)
            return None

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

    async def fake_publish_phase1_event(**kwargs):
        events.append(kwargs)

    monkeypatch.setattr(bot, "_publish_phase1_event", fake_publish_phase1_event)

    state = bot._get_runtime_state("telegram:dm:456")
    state.start_turn()
    state.task_status = "running"
    state.current_goal = "列目录"
    state.current_step = "tool:shell"
    state.last_verification_result = {"passed": True, "reason": "verified"}
    state.last_tool_result = {
        "success": True,
        "tool": "shell",
        "stdout": " Directory of D:\\Project\\AIProject\\MyProject\\Test2\n03/31/2026  04:18 PM               12 demo.txt",
        "metadata": {
            "command": r"dir D:\Project\AIProject\MyProject\Test2",
            "working_directory": r"D:\Project\AIProject\MyProject\Test2",
            "truncated": False,
        },
    }
    state.last_tool_result_turn_id = state.active_turn_id

    result = TelegramTurnResult(
        status="completed_verified",
        state=state,
        reply=TelegramTurnReply(
            reply_text="已列出 D:\\Project\\AIProject\\MyProject\\Test2 目录下的文件。",
            delivery_kind="final",
            status="completed_verified",
        ),
    )

    await bot._deliver_runtime_v2_result(
        DummyUpdate(),
        state,
        result,
        is_challenge_turn=False,
        ingress_message_id=9,
        trace_id="trace-read-list",
    )

    assert any(text.startswith("目录内容如下：\n") for text in DummyUpdate.message.texts)
    assert any("demo.txt" in text for text in DummyUpdate.message.texts)
    assert state.last_delivered_evidence_context is not None
    assert state.last_delivered_evidence_context["delivery_was_chunked"] is False
    assert state.task_status == "idle"
    assert state.current_goal is None
    assert state.current_step is None
    assert state.last_tool_result is None
    assert state.last_verification_result is None
    bridge_events = [event for event in events if event["kind"] == "tool_delivery_bridge"]
    assert bridge_events
    assert bridge_events[-1]["payload"]["fidelity_mode"] == "verbatim"
    assert bridge_events[-1]["payload"]["fidelity_gap"] is False
    assert bridge_events[-1]["payload"]["applied_authority"] == "host_evidence"


def test_telegram_bot_recent_directory_followup_uses_host_grounded_reply():
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    state = bot._get_runtime_state("telegram:dm:456")
    state.set_last_delivered_evidence_context(
        {
            "request_kind": "directory_listing",
            "body": " Directory of D:\\Project\\AIProject\\MyProject\\Test2\n03/31/2026  04:18 PM               12 demo.txt",
            "truncated": False,
            "delivery_was_chunked": False,
            "delivered_at": time.time(),
            "source_turn_id": "turn_test",
        }
    )

    reply = bot._build_recent_read_followup_reply(state, "什么意思 空的吗")

    assert reply is not None
    assert reply.startswith("不是空的。目录内容如下：\n")
    assert "demo.txt" in reply
    assert "截断" not in reply


def test_telegram_bot_plain_meaning_probe_after_evidence_skips_host_followup():
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    state = bot._get_runtime_state("telegram:dm:456")
    state.set_last_delivered_evidence_context(
        {
            "request_kind": "directory_listing",
            "body": " Directory of D:\\Project\\AIProject\\MyProject\\Test2\n03/31/2026  04:18 PM               12 demo.txt",
            "truncated": False,
            "delivery_was_chunked": False,
            "delivered_at": time.time(),
            "source_turn_id": "turn_test",
        }
    )

    reply = bot._build_recent_read_followup_reply(state, "什么意思")

    assert reply is None


@pytest.mark.asyncio
async def test_telegram_bot_presence_probe_after_evidence_stays_model_chat(monkeypatch):
    bot = TelegramBot(token="test-token", use_runtime_v2=True)

    class DummyBot:
        async def send_chat_action(self, chat_id, action):
            return None

    class DummyMessage:
        text = "在吗"
        message_id = 10
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
    state.set_last_delivered_evidence_context(
        {
            "request_kind": "directory_listing",
            "body": " Directory of D:\\Project\\AIProject\\MyProject\\Test2\n03/31/2026  04:18 PM               12 demo.txt",
            "truncated": False,
            "delivery_was_chunked": False,
            "delivered_at": time.time(),
            "source_turn_id": "turn_prev",
        }
    )

    async def fake_run_turn_typed(session_id, user_input):
        from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
        state.start_turn()
        return RuntimeV2TurnResult(
            status="chat",
            state=state,
            reply=RuntimeV2Reply(
                reply_text="在的，请说。",
                delivery_kind="chat",
                status="chat",
            ),
        )

    monkeypatch.setattr(runtime_loop, "run_turn_typed", fake_run_turn_typed)

    await bot.handle_message(DummyUpdate(), None)

    assert DummyUpdate.message.last_text == "在的，请说。"
    assert state.last_delivered_evidence_context is None


@pytest.mark.asyncio
async def test_telegram_bot_host_owned_reply_captures_explicit_response_plan(monkeypatch, tmp_path):
    collector = TelegramEvidenceCollector(
        artifacts_dir=tmp_path,
        source_type="simulated_external_entry",
        channel="telegram",
        evidence_level="E4",
    )
    monkeypatch.setattr(telegram_bot_module, "_EVIDENCE_COLLECTOR_AVAILABLE", True)
    monkeypatch.setattr(telegram_bot_module, "get_evidence_collector", lambda: collector)

    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    state = bot._get_runtime_state("telegram:dm:456")

    class DummyMessage:
        text = "继续"
        message_id = 11
        reply_to_message = None
        sent = []
        date = datetime.now(timezone.utc)

        async def reply_text(self, text, parse_mode=None):
            self.sent.append(text)
            return SimpleNamespace(
                chat=SimpleNamespace(id=123),
                message_id=self.message_id + len(self.sent),
                date=datetime.now(timezone.utc),
            )

    class DummyUpdate:
        message = DummyMessage()
        effective_chat = SimpleNamespace(id=123, type="private")
        effective_user = SimpleNamespace(id=456, username="tester")
        update_id = 9011

        def to_dict(self):
            return {
                "update_id": self.update_id,
                "message": {
                    "message_id": self.message.message_id,
                    "date": self.message.date.isoformat(),
                    "chat": {"id": self.effective_chat.id, "type": self.effective_chat.type},
                    "from": {
                        "id": self.effective_user.id,
                        "is_bot": False,
                        "username": self.effective_user.username,
                    },
                    "text": self.message.text,
                },
            }

    update = DummyUpdate()
    collector.start_sample(update.to_dict())

    sent = await bot._send_host_owned_reply(
        update,
        state=state,
        reply_text="当前已有一个活跃任务。",
        status="task_conflict_pending",
        delivery_kind="final",
        authority_source="host_pre_runtime",
        reply_authority="host_degraded_fallback",
        metadata={"conversation_act": "task_conflict"},
    )
    samples = collector.get_samples()

    assert sent is True
    assert len(samples) == 1
    sample = samples[0]
    assert sample.response_plan is not None
    assert sample.response_plan["status"] == "task_conflict_pending"
    assert sample.response_plan.get("inferred") is not True
    assert update.message.sent == ["当前已有一个活跃任务。"]


@pytest.mark.asyncio
async def test_telegram_bot_new_runtime_direct_reply_uses_runtime_authority_metadata(monkeypatch, tmp_path):
    collector = TelegramEvidenceCollector(
        artifacts_dir=tmp_path,
        source_type="simulated_external_entry",
        channel="telegram",
        evidence_level="E4",
    )
    monkeypatch.setattr(telegram_bot_module, "_EVIDENCE_COLLECTOR_AVAILABLE", True)
    monkeypatch.setattr(telegram_bot_module, "get_evidence_collector", lambda: collector)

    async def fake_run_agent(**kwargs):
        return SimpleNamespace(
            status=SimpleNamespace(value="completed"),
            duration_ms=1,
            reply_text="这是宿主层的正常回复。",
            request_id="req_runtime_direct",
        )

    monkeypatch.setattr(telegram_bot_module, "run_agent", fake_run_agent)

    bot = TelegramBot(token="test-token", use_runtime_v2=True)

    class DummyBot:
        async def send_chat_action(self, chat_id, action):
            return None

    class DummyMessage:
        text = "你好"
        message_id = 12
        reply_to_message = None
        sent = []
        date = datetime.now(timezone.utc)

        async def reply_text(self, text, parse_mode=None):
            self.sent.append(text)
            return SimpleNamespace(
                chat=SimpleNamespace(id=123),
                message_id=self.message_id + len(self.sent),
                date=datetime.now(timezone.utc),
            )

    class DummyUpdate:
        message = DummyMessage()
        effective_chat = SimpleNamespace(id=123, type="private")
        effective_user = SimpleNamespace(id=456, username="tester")
        update_id = 9012

        def to_dict(self):
            return {
                "update_id": self.update_id,
                "message": {
                    "message_id": self.message.message_id,
                    "date": self.message.date.isoformat(),
                    "chat": {"id": self.effective_chat.id, "type": self.effective_chat.type},
                    "from": {
                        "id": self.effective_user.id,
                        "is_bot": False,
                        "username": self.effective_user.username,
                    },
                    "text": self.message.text,
                },
            }

    bot.app = type("A", (), {"bot": DummyBot()})()
    update = DummyUpdate()
    collector.start_sample(update.to_dict())

    await bot._handle_with_new_runtime(
        update,
        text="你好",
        chat_id=123,
        user_id=456,
        username="tester",
        trace_id="trace_runtime_direct",
    )

    samples = collector.get_samples()
    assert len(samples) == 1
    sample = samples[0]
    assert sample.response_plan is not None
    assert sample.response_plan["status"] == "completed"
    assert sample.response_plan["authority_source"] == "host_runtime_result"
    assert sample.response_plan["reply_authority"] == "host_runtime"
    assert sample.response_plan.get("inferred") is not True
    assert update.message.sent == ["这是宿主层的正常回复。"]


@pytest.mark.asyncio
async def test_telegram_bot_send_reply_chunks_long_output():
    bot = TelegramBot(token="test-token", use_runtime_v2=True)

    class DummyMessage:
        def __init__(self):
            self.texts = []

        async def reply_text(self, text, parse_mode=None):
            self.texts.append(text)
            return None

    class DummyUpdate:
        message = DummyMessage()

    text = ("A" * 3400) + "\n" + ("B" * 3400) + "\n" + ("C" * 400)

    result = await bot._send_reply(DummyUpdate(), text)

    assert result["was_chunked"] is True
    assert len(DummyUpdate.message.texts) >= 2
    assert all(len(chunk) <= 3500 for chunk in DummyUpdate.message.texts)
    assert "... (已截断)" not in "".join(DummyUpdate.message.texts)
    assert "".join(DummyUpdate.message.texts).replace("\n", "") == text.replace("\n", "")


@pytest.mark.asyncio
async def test_telegram_bot_natural_language_conflict_words_no_longer_resolve_conflict(monkeypatch):
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
    async def fake_run_primary_turn(**kwargs):
        from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
        state = bot._get_runtime_state("telegram:dm:456")
        state.start_turn()
        return RuntimeV2TurnResult(
            status="chat",
            state=state,
            reply=RuntimeV2Reply(
                reply_text="你是在聊任务切换规则，还是要我现在处理某件事？",
                delivery_kind="chat",
                status="chat",
            ),
        )

    monkeypatch.setattr(bot, "_run_primary_turn", fake_run_primary_turn)
    await bot.handle_message(DummyUpdate(), None)

    assert DummyUpdate.message.last_text == "你是在聊任务切换规则，还是要我现在处理某件事？"
