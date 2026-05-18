import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

if "requests" not in sys.modules:
    sys.modules["requests"] = SimpleNamespace(
        get=lambda *args, **kwargs: None,
        post=lambda *args, **kwargs: None,
        exceptions=SimpleNamespace(
            Timeout=Exception,
            ConnectionError=Exception,
        ),
    )

import app.telegram_bot as telegram_bot_module
from app.config import get_config, load_config
from app.autonomy import AutonomyExecutorKind, AutonomyRun, AutonomyRunStatus
from app.openemotion_hooks.subject_gate import SubjectGateVerdict
from app.runtime_v2.run_items import RunConflictState, RunItem
from app.telegram_bot import TelegramBot
from app.interaction.session_context_store import get_session_context_store

EGOCORE_ROOT = Path(__file__).resolve().parents[1]


class _AllowingSubjectGate:
    def __init__(self, calls=None):
        self.calls = calls if calls is not None else []

    def process_ingress(self, **kwargs):
        self.calls.append(("ingress", kwargs.get("user_input")))
        return SubjectGateVerdict.allow(stage="ingress")

    def finalize_host_owned_result(self, **kwargs):
        self.calls.append(("finalized_result", kwargs["result"].status))
        return SubjectGateVerdict.allow(stage="response_plan")


def _install_allowing_subject_gate(monkeypatch, bot, calls=None):
    gate = _AllowingSubjectGate(calls)
    monkeypatch.setattr(bot, "_get_subject_gate", lambda: gate)
    return gate


@pytest.mark.asyncio
async def test_new_command_resets_runtime_v2_session(monkeypatch):
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    _install_allowing_subject_gate(monkeypatch, bot)

    class DummyMessage:
        text = "/new"
        message_id = 21
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

    session_key = "telegram:dm:456"
    state = bot._get_runtime_state(session_key)
    state.task_status = "running"
    state.current_goal = "修改 hello.html"
    state.push_proactive_outbox_event(
        {
            "schema_version": "mvp12.proactive_outbox_event.v1",
            "session_id": session_key,
            "initiative_candidate_id": "candidate-old-thread",
            "reply_text": "旧线程 proactive",
            "outbox_status": "queued",
        }
    )
    get_session_context_store().add_turn(session_key, "user", "hello")

    await bot.handle_command(DummyUpdate(), None)
    new_state = bot._get_runtime_state(session_key)
    assert "Session Reset" in DummyUpdate.message.last_text
    assert new_state.task_status == "idle"
    assert new_state.current_goal is None
    assert new_state.peek_proactive_outbox_events() == []
    assert new_state.proto_self_subject_profile_override == "seed_v0_2"
    assert get_session_context_store().get_recent_turns(session_key) == []


@pytest.mark.asyncio
async def test_new_command_supersedes_active_durable_runs(monkeypatch):
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    _install_allowing_subject_gate(monkeypatch, bot)

    class DummyMessage:
        text = "/new"
        message_id = 31
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

    session_key = "telegram:dm:456"
    run = AutonomyRun.create(
        session_key=session_key,
        surface="telegram",
        status=AutonomyRunStatus.BLOCKED,
        executor_kind=AutonomyExecutorKind.GENERIC_RUNTIME,
        objective="旧活跃任务",
        current_phase="blocked",
    )
    bot.autonomy_orchestrator.repository.create(run)

    await bot.handle_command(DummyUpdate(), None)

    superseded = bot.autonomy_orchestrator.repository.get(run.id)
    assert superseded is not None
    assert superseded.status == AutonomyRunStatus.SUPERSEDED


@pytest.mark.asyncio
async def test_status_command_returns_runtime_style_card(monkeypatch):
    load_config(
        config_dir=str(EGOCORE_ROOT / "config"),
        env_file=str(EGOCORE_ROOT / ".env"),
        validate=False,
    )
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    _install_allowing_subject_gate(monkeypatch, bot)

    class DummyMessage:
        text = "/status"
        message_id = 22
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

    session_key = "telegram:dm:456"
    state = bot._get_runtime_state(session_key)
    state.task_status = "running"
    state.task_id = "task_abc123"
    state.current_goal = "连续性验证"
    state.current_step = "检查 test.html"

    await bot.handle_command(DummyUpdate(), None)
    text = DummyUpdate.message.last_text
    chat_cfg = get_config().get_llm_config_for_use_case("chat")
    expected_model = f"{chat_cfg['provider']}/{chat_cfg['model']}"
    assert bot.runtime_v2_loop is None
    assert "EgoCore Runtime" in text
    assert expected_model in text
    assert "Session ID:" in text
    assert "native\\_loop" in text
    assert "task\\_status" in text and "running" in text
    assert "loaded:" in text


@pytest.mark.asyncio
async def test_new_command_captures_real_command_ingress(monkeypatch):
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    captured = {}

    class FakeCollector:
        def start_sample(self, update):
            captured["started"] = update["message"]["text"]

        def capture_host_response_plan(self, **kwargs):
            captured["plan"] = kwargs

        def capture_outbox_record(self, record):
            captured["outbox"] = record

        def finalize_sample(self):
            captured["finalized"] = True

    class FakeHooks:
        enabled = True

        def process_ingress(self, **kwargs):
            captured["ingress"] = kwargs

        def process_finalized_result(self, **kwargs):
            captured["finalized_result"] = kwargs

        def capture_response_plan(self, **kwargs):
            captured["plan_captured"] = kwargs

    monkeypatch.setattr(telegram_bot_module, "_EVIDENCE_COLLECTOR_AVAILABLE", True)
    monkeypatch.setattr(telegram_bot_module, "get_evidence_collector", lambda: FakeCollector())
    monkeypatch.setattr(bot, "_get_native_openemotion_hooks", lambda: FakeHooks())

    class DummyMessage:
        text = "/new"
        message_id = 21
        reply_to_message = None
        date = None
        async def reply_text(self, text, parse_mode=None):
            self.last_text = text
            return type(
                "SentMessage",
                (),
                {
                    "chat": type("Chat", (), {"id": 123})(),
                    "message_id": 22,
                    "date": None,
                },
            )()

    class DummyChat:
        id = 123
        type = "private"

    class DummyUser:
        id = 456
        username = "moonlight"

    class DummyUpdate:
        update_id = 999
        message = DummyMessage()
        effective_chat = DummyChat()
        effective_user = DummyUser()

        def to_dict(self):
            return {
                "update_id": self.update_id,
                "message": {
                    "message_id": self.message.message_id,
                    "chat": {"id": self.effective_chat.id, "type": self.effective_chat.type},
                    "from": {"id": self.effective_user.id, "username": self.effective_user.username},
                    "text": self.message.text,
                },
            }

    await bot.handle_command(DummyUpdate(), None)

    assert captured["started"] == "/new"
    assert captured["ingress"]["user_input"] == "/new"
    assert captured["ingress"]["session_id"] == "telegram:dm:456"
    assert captured["finalized_result"]["session_id"] == "telegram:dm:456"
    assert captured["plan_captured"]["result"].status == "command_result"
    assert captured["finalized"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("command_text", "expected_fragment"),
    [
        ("/new", "Session Reset"),
        ("/status", "EgoCore Runtime"),
        ("/context list", "Loaded Context"),
        ("/prompt list", "Prompt Files"),
        ("/proto status", "Proto-Self Ingress Mode"),
    ],
)
async def test_command_results_use_subject_gate(monkeypatch, command_text, expected_fragment):
    load_config(
        config_dir=str(EGOCORE_ROOT / "config"),
        env_file=str(EGOCORE_ROOT / ".env"),
        validate=False,
    )
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    calls = []

    class RecordingGate:
        def process_ingress(self, **kwargs):
            calls.append(("ingress", kwargs["user_input"]))
            return SubjectGateVerdict.allow(stage="ingress")

        def finalize_host_owned_result(self, **kwargs):
            calls.append(("finalized_result", kwargs["result"].status))
            return SubjectGateVerdict.allow(stage="response_plan")

    monkeypatch.setattr(bot, "_get_subject_gate", lambda: RecordingGate())

    class DummyMessage:
        text = command_text
        message_id = 77
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

    await bot.handle_command(DummyUpdate(), None)

    assert calls[0] == ("ingress", command_text)
    assert ("finalized_result", "command_result") in calls
    assert expected_fragment in DummyUpdate.message.last_text


@pytest.mark.asyncio
async def test_command_ingress_failure_blocks_reply(monkeypatch):
    bot = TelegramBot(token="test-token", use_runtime_v2=True)

    class BlockingSubjectGate:
        def process_ingress(self, **kwargs):
            return SubjectGateVerdict.block(stage="ingress", reason="hooks_disabled")

    monkeypatch.setattr(bot, "_get_subject_gate", lambda: BlockingSubjectGate())

    class DummyMessage:
        text = "/status"
        message_id = 78
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

    await bot.handle_command(DummyUpdate(), None)

    assert DummyUpdate.message.last_text == "subject_gate_failed：主体暂时不可用，这一步已阻断，请稍后重试。"


@pytest.mark.asyncio
@pytest.mark.parametrize(("command_text", "expected_message"), [("/append", "已把新任务追加到当前任务队列"), ("/cancel", "已取消这次新任务")])
async def test_task_conflict_command_results_use_subject_gate(monkeypatch, command_text, expected_message):
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    state = bot._get_runtime_state("telegram:dm:456")
    state.set_pending_task_conflict(
        RunConflictState(
            existing_run_id="run_existing",
            existing_objective="旧任务",
            incoming_text="新的任务",
            incoming_run_items=[RunItem(item_id="item_1", order_index=1, kind="generic", description="新增任务").to_dict()],
        )
    )
    calls = []

    class RecordingGate:
        def process_ingress(self, **kwargs):
            calls.append(("ingress", kwargs["user_input"]))
            return SubjectGateVerdict.allow(stage="ingress")

        def finalize_host_owned_result(self, **kwargs):
            calls.append(("finalized_result", kwargs["result"].status))
            return SubjectGateVerdict.allow(stage="response_plan")

    monkeypatch.setattr(bot, "_get_subject_gate", lambda: RecordingGate())
    monkeypatch.setattr(bot, "_publish_phase1_event", lambda **kwargs: __import__("asyncio").sleep(0))

    class DummyMessage:
        text = command_text
        message_id = 88
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

    await bot.handle_command(DummyUpdate(), None)

    assert calls[0] == ("ingress", command_text)
    assert ("finalized_result", "command_result") in calls
    assert expected_message in DummyUpdate.message.last_text


@pytest.mark.asyncio
async def test_replace_command_subject_gates_command_ingress_before_runtime(monkeypatch):
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    state = bot._get_runtime_state("telegram:dm:456")
    state.set_pending_task_conflict(
        RunConflictState(
            existing_run_id="run_existing",
            existing_objective="旧任务",
            incoming_text="请执行新的任务内容",
            incoming_run_items=[],
        )
    )
    calls = []
    captured = {}

    class RecordingGate:
        def process_ingress(self, **kwargs):
            calls.append(("ingress", kwargs["user_input"]))
            return SubjectGateVerdict.allow(stage="ingress")

    async def fake_handle_with_runtime_v2(update, text, chat_id, user_id, username, trace_id=None, extra_context=None):
        captured["text"] = text

    monkeypatch.setattr(bot, "_get_subject_gate", lambda: RecordingGate())
    monkeypatch.setattr(bot, "_handle_with_runtime_v2", fake_handle_with_runtime_v2)

    class DummyMessage:
        text = "/replace"
        message_id = 89
        reply_to_message = None

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

    await bot.handle_command(DummyUpdate(), None)

    assert calls == [("ingress", "/replace")]
    assert captured["text"] == "请执行新的任务内容"


@pytest.mark.asyncio
async def test_proto_command_enables_v2_override(monkeypatch):
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    _install_allowing_subject_gate(monkeypatch, bot)
    state = bot._get_runtime_state("telegram:dm:456")
    state.proto_self_version_override = "v1"

    class DummyMessage:
        text = "/proto v2 on"
        message_id = 23
        reply_to_message = None
        date = datetime.now(timezone.utc)
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

    await bot.handle_command(DummyUpdate(), None)

    assert state.proto_self_version_override is None
    assert state.proto_self_subject_profile_override == "seed_v0_2"
    assert "version\\_override: \\`default(v2)\\`" in DummyUpdate.message.last_text
    assert "subject\\_profile: \\`default(seed\\_v0\\_2)\\`" in DummyUpdate.message.last_text


@pytest.mark.asyncio
async def test_proto_command_clears_override(monkeypatch):
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    _install_allowing_subject_gate(monkeypatch, bot)
    state = bot._get_runtime_state("telegram:dm:456")

    class DummyMessage:
        text = "/proto off"
        message_id = 24
        reply_to_message = None
        date = datetime.now(timezone.utc)
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

    await bot.handle_command(DummyUpdate(), None)

    assert state.proto_self_version_override == "v1"
    assert "version\\_override: \\`v1\\`" in DummyUpdate.message.last_text


@pytest.mark.asyncio
async def test_proto_command_enables_seed_profile(monkeypatch):
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    _install_allowing_subject_gate(monkeypatch, bot)
    state = bot._get_runtime_state("telegram:dm:456")

    class DummyMessage:
        text = "/proto seed on"
        message_id = 25
        reply_to_message = None
        date = datetime.now(timezone.utc)
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

    await bot.handle_command(DummyUpdate(), None)

    assert state.proto_self_version_override is None
    assert state.proto_self_subject_profile_override == "seed_v0_2"
    assert "subject\\_profile: \\`default(seed\\_v0\\_2)\\`" in DummyUpdate.message.last_text


@pytest.mark.asyncio
async def test_proto_command_disables_seed_profile(monkeypatch):
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    _install_allowing_subject_gate(monkeypatch, bot)
    state = bot._get_runtime_state("telegram:dm:456")
    state.proto_self_subject_profile_override = "seed_v0_2"

    class DummyMessage:
        text = "/proto seed off"
        message_id = 26
        reply_to_message = None
        date = datetime.now(timezone.utc)
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

    await bot.handle_command(DummyUpdate(), None)

    assert state.proto_self_subject_profile_override is None
    assert "subject\\_profile: \\`default(core\\_v2)\\`" in DummyUpdate.message.last_text


@pytest.mark.asyncio
async def test_proto_status_uses_default_seed_wording(monkeypatch):
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    _install_allowing_subject_gate(monkeypatch, bot)
    state = bot._get_runtime_state("telegram:dm:456")
    state.proto_self_subject_profile_override = "seed_v0_2"

    class DummyMessage:
        text = "/proto status"
        message_id = 27
        reply_to_message = None
        date = datetime.now(timezone.utc)
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

    await bot.handle_command(DummyUpdate(), None)

    assert "subject\\_profile: \\`default(seed\\_v0\\_2)\\`" in DummyUpdate.message.last_text
    assert "explicit profile overlay only" not in DummyUpdate.message.last_text


@pytest.mark.asyncio
async def test_append_command_resolves_pending_task_conflict(monkeypatch):
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    _install_allowing_subject_gate(monkeypatch, bot)
    state = bot._get_runtime_state("telegram:dm:456")
    monkeypatch.setattr(bot, "_publish_phase1_event", lambda **kwargs: __import__("asyncio").sleep(0))
    state.set_pending_task_conflict(
        RunConflictState(
            existing_run_id="run_existing",
            existing_objective="旧任务",
            incoming_text="新任务",
            incoming_run_items=[RunItem(item_id="item_1", order_index=1, kind="generic", description="新增任务").to_dict()],
        )
    )

    class DummyMessage:
        text = "/append"
        message_id = 28
        reply_to_message = None
        date = datetime.now(timezone.utc)
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

    await bot.handle_command(DummyUpdate(), None)

    assert state.get_pending_task_conflict() is None
    assert state.run_items
    assert state.run_items[-1]["description"] == "新增任务"
    assert "已把新任务追加到当前任务队列" in DummyUpdate.message.last_text


@pytest.mark.asyncio
async def test_replace_command_routes_conflict_text_back_into_runtime(monkeypatch):
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    _install_allowing_subject_gate(monkeypatch, bot)
    state = bot._get_runtime_state("telegram:dm:456")
    state.set_pending_task_conflict(
        RunConflictState(
            existing_run_id="run_existing",
            existing_objective="旧任务",
            incoming_text="请执行新的任务内容",
            incoming_run_items=[],
        )
    )
    captured = {}

    async def fake_handle_with_runtime_v2(update, text, chat_id, user_id, username, trace_id=None, extra_context=None):
        captured["text"] = text
        update.message.last_text = text

    monkeypatch.setattr(bot, "_handle_with_runtime_v2", fake_handle_with_runtime_v2)

    class DummyMessage:
        text = "/replace"
        message_id = 29
        reply_to_message = None
        date = datetime.now(timezone.utc)
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

    await bot.handle_command(DummyUpdate(), None)

    assert state.get_pending_task_conflict() is None
    assert captured["text"] == "请执行新的任务内容"
