import pytest
from pathlib import Path

import app.telegram_bot as telegram_bot_module
from app.config import load_config
from app.memory.memory_manager import MemoryManager
from app.memory.profile_memory import ProfileMemory
from app.openemotion_hooks.subject_gate import SubjectGateVerdict
from app.telegram_bot import TelegramBot
from app.telegram_runtime_bridge import TelegramRuntimeBridge
from app.runtime_v2.state import RuntimeV2State
from app.tools import get_registry, setup_tools


EGOCORE_ROOT = Path(__file__).resolve().parents[1]


def _make_manager(tmp_path):
    return MemoryManager(
        db_path=tmp_path / "memory.db",
        memory_dir=tmp_path / "memory_store",
    )


def _ensure_tools_ready():
    cfg = load_config(
        config_dir=str(EGOCORE_ROOT / "config"),
        env_file=str(EGOCORE_ROOT / ".env"),
        validate=False,
    )
    registry = get_registry()
    if not registry.list_tools():
        setup_tools(cfg.get("tools", {}) if hasattr(cfg, "get") else {})


def _make_bridge(manager):
    return TelegramRuntimeBridge(
        profile_memory_factory=lambda scope: ProfileMemory(scope, manager=manager)
    )


def _make_bot(manager):
    bot = TelegramBot(token="test-token", use_runtime_v2=True)
    bridge = _make_bridge(manager)
    bot.telegram_runtime_bridge = bridge
    bot.runtime_v2_bridge = bridge

    class AllowingSubjectGate:
        def process_ingress(self, **kwargs):
            return SubjectGateVerdict.allow(stage="ingress")

        def finalize_host_owned_result(self, **kwargs):
            return SubjectGateVerdict.allow(stage="response_plan")

    bot._get_subject_gate = lambda: AllowingSubjectGate()
    return bot


class DummyMessage:
    def __init__(self, text: str, message_id: int):
        self.text = text
        self.message_id = message_id
        self.reply_to_message = None
        self.date = None
        self.last_text = None
        self.sent = []

    async def reply_text(self, text, parse_mode=None):
        self.last_text = text
        self.sent.append(text)
        return type(
            "SentMessage",
            (),
            {
                "chat": type("Chat", (), {"id": 123})(),
                "message_id": self.message_id + 100,
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
    def __init__(self, text: str, message_id: int, update_id: int | None = None):
        self.update_id = update_id if update_id is not None else message_id + 1000
        self.message = DummyMessage(text, message_id)
        self.effective_chat = DummyChat()
        self.effective_user = DummyUser()

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


def test_cat_rule_parser_becomes_path_prefix_reply_once(tmp_path):
    bridge = _make_bridge(_make_manager(tmp_path))
    state = RuntimeV2State(session_id="telegram:dm:456")

    decision = bridge.inspect_ingress(
        '以后凡是涉及"D:\\Project\\AIProject\\MyProject\\Test"文件夹的改动，你默认走“猫娘流程”：先只说一声什么喵?',
        state,
    )

    assert decision.registered_profile_rule is not None
    assert decision.registered_profile_rule["predicate"]["kind"] == "target_path_prefix"
    assert decision.registered_profile_rule["effect"]["type"] == "reply_only_once"
    assert decision.registered_profile_rule["effect"]["phrase"] == "什么喵?"


def test_snow_rule_parser_becomes_high_risk_read_only_bundle(tmp_path):
    bridge = _make_bridge(_make_manager(tmp_path))
    state = RuntimeV2State(session_id="telegram:dm:456")

    decision = bridge.inspect_ingress(
        "以后凡是涉及高风险改动，你默认走“雪松流程”：先只读检查，再给我一个最小验证动作，不要直接改文件。",
        state,
    )

    assert decision.registered_profile_rule is not None
    assert decision.registered_profile_rule["predicate"]["kind"] == "risk_class"
    effect = decision.registered_profile_rule["effect"]
    assert effect["type"] == "composite"
    effect_types = {item["type"] for item in effect["effects"]}
    assert "read_only_first" in effect_types
    assert "require_minimal_verification_before_mutation" in effect_types
    assert "forbid_direct_mutation_before_confirmation" in effect_types


@pytest.mark.asyncio
async def test_profile_rule_survives_new_command_and_replies_again(tmp_path):
    manager = _make_manager(tmp_path)
    bot = _make_bot(manager)
    target_file = tmp_path / "test_scope" / "task_output.html"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text("<html><body>hello</body></html>", encoding="utf-8")

    rule_update = DummyUpdate(
        f'以后凡是涉及"{target_file.parent}"文件夹的改动，你默认走“猫娘流程”：先只说一声什么喵?',
        1,
    )
    await bot.handle_message(rule_update, None)
    assert "已记住这条默认规则" in rule_update.message.last_text

    request_update_1 = DummyUpdate(f"我现在想改{target_file},你怎么看", 2)
    await bot.handle_message(request_update_1, None)
    assert request_update_1.message.last_text == "什么喵?"

    reset_update = DummyUpdate("/new", 3)
    await bot.handle_command(reset_update, None)
    assert "Session Reset" in reset_update.message.last_text

    request_update_2 = DummyUpdate(f"我现在想改{target_file},你怎么看", 4)
    await bot.handle_message(request_update_2, None)
    assert request_update_2.message.last_text == "什么喵?"


@pytest.mark.asyncio
async def test_profile_rule_survives_restart_with_same_memory_db(tmp_path):
    first_manager = _make_manager(tmp_path)
    first_bot = _make_bot(first_manager)
    target_file = tmp_path / "restart_scope" / "task_output.html"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text("<html><body>restart</body></html>", encoding="utf-8")

    await first_bot.handle_message(
        DummyUpdate(
            f'以后凡是涉及"{target_file.parent}"文件夹的改动，你默认走“猫娘流程”：先只说一声什么喵?',
            10,
        ),
        None,
    )

    restarted_manager = MemoryManager(
        db_path=tmp_path / "memory.db",
        memory_dir=tmp_path / "memory_store",
    )
    restarted_bot = _make_bot(restarted_manager)
    request_update = DummyUpdate(f"我现在想改{target_file},你怎么看", 11)
    await restarted_bot.handle_message(request_update, None)

    assert request_update.message.last_text == "什么喵?"


def test_profile_rule_scope_does_not_leak_to_other_paths(tmp_path):
    manager = _make_manager(tmp_path)
    bridge = _make_bridge(manager)
    state = RuntimeV2State(session_id="telegram:dm:456")
    in_scope = tmp_path / "scope_a"
    out_scope = tmp_path / "scope_b" / "task_output.html"

    bridge.inspect_ingress(
        f'以后凡是涉及"{in_scope}"文件夹的改动，你默认走“猫娘流程”：先只说一声什么喵?',
        state,
    )
    decision = bridge.inspect_ingress(f"我现在想改{out_scope},你怎么看", state)
    ingress_context = bridge.build_ingress_context(decision, state)
    action = bridge.plan_pre_runtime(decision, state)

    assert ingress_context["matched_profile_rules"] == []
    assert action.should_return_early is False


@pytest.mark.asyncio
async def test_high_risk_rule_forces_read_only_preflight_and_keeps_target_for_continue(tmp_path):
    _ensure_tools_ready()
    manager = _make_manager(tmp_path)
    bot = _make_bot(manager)
    target_file = Path("/tmp") / f"profile_rule_high_risk_{tmp_path.name}" / "task_output.html"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text("<html><body>draft</body></html>", encoding="utf-8")

    await bot.handle_message(
        DummyUpdate(
            "以后凡是涉及高风险改动，你默认走“雪松流程”：先只读检查，再给我一个最小验证动作，不要直接改文件。",
            20,
        ),
        None,
    )

    risky_update = DummyUpdate(f"请删除并重写 {target_file}", 21)
    await bot.handle_message(risky_update, None)
    reply = risky_update.message.last_text

    assert "先不直接改文件" in reply
    assert "只读检查：已读取" in reply
    assert "最小验证动作" in reply

    state = bot._get_runtime_state("telegram:dm:456")
    continue_decision = bot.telegram_runtime_bridge.inspect_ingress("继续读取完整内容，不要截断", state)
    ingress_context = bot.telegram_runtime_bridge.build_ingress_context(continue_decision, state)
    assert ingress_context["resolved_target"]["path"] == str(target_file)


@pytest.mark.asyncio
async def test_profile_rule_enforcement_is_written_into_host_response_plan(tmp_path, monkeypatch):
    manager = _make_manager(tmp_path)
    bot = _make_bot(manager)
    target_file = tmp_path / "evidence_scope" / "task_output.html"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text("<html><body>evidence</body></html>", encoding="utf-8")
    captured = {}

    class FakeCollector:
        def start_sample(self, update):
            captured["update"] = update

        def capture_host_response_plan(self, **kwargs):
            captured["plan"] = kwargs

        def capture_outbox_record(self, record):
            captured["outbox"] = record

        def finalize_sample(self):
            captured["finalized"] = True

    monkeypatch.setattr(telegram_bot_module, "_EVIDENCE_COLLECTOR_AVAILABLE", True)
    monkeypatch.setattr(telegram_bot_module, "get_evidence_collector", lambda: FakeCollector())

    await bot.handle_message(
        DummyUpdate(
            f'以后凡是涉及"{target_file.parent}"文件夹的改动，你默认走“猫娘流程”：先只说一声什么喵?',
            30,
        ),
        None,
    )
    request_update = DummyUpdate(f"我现在想改{target_file},你怎么看", 31)
    await bot.handle_message(request_update, None)

    assert captured["plan"]["status"] == "profile_rule_enforced"
    assert captured["plan"]["extra"]["authority_source"] == "profile_memory"
    assert captured["plan"]["extra"]["matched_rule_ids"]
    assert captured["plan"]["extra"]["rule_enforcement"]["kind"] == "reply_only_once"
