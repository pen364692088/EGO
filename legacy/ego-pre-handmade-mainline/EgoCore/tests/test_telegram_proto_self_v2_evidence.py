import json
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
from app.config import load_config
from app.openemotion_adapter.proto_self_adapter import ProtoSelfAdapter
from app.runtime_v2.proto_self_runtime import RuntimeV2ProtoSelfRuntime
from app.telegram_bot import TelegramBot
from app.telegram_evidence_collector import TelegramEvidenceCollector
from app.telegram_runtime_result import TelegramTurnReply, TelegramTurnResult
from openemotion.proto_self_v2.seed_schemas import SEED_SUBJECT_PROFILE


class DummyBot:
    async def send_chat_action(self, chat_id, action):
        return None


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
        self.date = datetime.now(timezone.utc)
        self.sent = []

    async def reply_text(self, text, parse_mode=None):
        self.sent.append(text)
        return SimpleNamespace(
            chat=SimpleNamespace(id=DummyChat.id),
            message_id=self.message_id + 1,
            date=datetime.now(timezone.utc),
        )


class DummyUpdate:
    def __init__(self, text: str, message_id: int):
        self.update_id = message_id + 9000
        self.message = DummyMessage(text, message_id)
        self.effective_chat = DummyChat()
        self.effective_user = DummyUser()

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


@pytest.mark.asyncio
async def test_telegram_handle_message_captures_proto_self_v2_trace_in_ledger(monkeypatch, tmp_path):
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    load_config(validate=False)

    collector = TelegramEvidenceCollector(
        artifacts_dir=tmp_path,
        source_type="simulated_external_entry",
        channel="telegram",
        evidence_level="E4",
    )
    monkeypatch.setattr(telegram_bot_module, "_EVIDENCE_COLLECTOR_AVAILABLE", True)
    monkeypatch.setattr(telegram_bot_module, "get_evidence_collector", lambda: collector)

    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    bot.app = SimpleNamespace(bot=DummyBot())
    state = bot._get_runtime_state("telegram:dm:456")
    state.proto_self_subject_profile_override = SEED_SUBJECT_PROFILE

    runtime = RuntimeV2ProtoSelfRuntime(
        adapter=ProtoSelfAdapter(mirror_dir=tmp_path / "mirror"),
        evidence_collector_factory=lambda: collector,
    )
    fake_hooks = SimpleNamespace(
        enabled=True,
        process_ingress=runtime.process_ingress,
        process_external_result=runtime.process_external_result,
        process_finalized_result=runtime.process_finalized_result,
        process_idle_check=runtime.process_idle_check,
        capture_response_plan=runtime.capture_response_plan,
    )
    monkeypatch.setattr(bot, "_get_native_openemotion_hooks", lambda: fake_hooks)

    async def fake_inspect_ingress(_text, _state, llm_client=None):
        return SimpleNamespace(
            _runtime_action="chat",
            is_challenge_turn=False,
            is_file_only=False,
            is_confirm_execution=False,
            _parsed_intent_graph=None,
        )

    monkeypatch.setattr(bot.telegram_runtime_bridge, "inspect_ingress_semantic", fake_inspect_ingress)
    monkeypatch.setattr(
        bot.telegram_runtime_bridge,
        "build_ingress_context",
            lambda ingress, state: {
                "runtime_action": "chat",
                "request_mode": "write",
                "proto_self_subject_profile": SEED_SUBJECT_PROFILE,
                "resolved_target": {"path": "app.py", "filename": "app.py", "source": "explicit_path"},
                "prediction_snapshot_prev": {"expected_success": True},
                "executed_action_prev": {"kind": "reply", "status": "delivered"},
            },
        )
    monkeypatch.setattr(
        bot.telegram_runtime_bridge,
        "plan_pre_runtime",
        lambda ingress, state: SimpleNamespace(
            should_return_early=False,
            remember_challenge_turn=False,
            ack_text=None,
            busy_notice_text=None,
            direct_reply_text=None,
            waiting_input_text=None,
            rule_enforcement=None,
            force_waiting_input=False,
        ),
    )

    async def fake_native_run_turn(*, session_key, user_input, ingress_context, proto_self_context):
        runtime_state = bot._get_runtime_state(session_key)
        return SimpleNamespace(
            reply_text="已收到",
            status="completed_verified",
            tool_results=[],
            task_contract=None,
            next_step_decision=None,
            verification_result=None,
            finish_reason="reply",
        )

    bot.native_loop = SimpleNamespace(run_turn=fake_native_run_turn)

    update = DummyUpdate("帮我看下 app.py", 5001)
    await bot.handle_message(update, None)

    samples = collector.get_samples()
    assert len(samples) == 1
    sample = samples[0]
    assert sample.normalized_event["schema_version"] == "proto_self.v2"
    assert sample.normalized_event["subject_profile"] == SEED_SUBJECT_PROFILE
    assert sample.openemotion_result["schema_version"] == "proto_self.output.v2"
    assert sample.openemotion_result["subject_profile"] == SEED_SUBJECT_PROFILE
    assert sample.openemotion_trace["schema_version"] == "proto_self.trace.v2"
    assert sample.openemotion_trace["subject_profile"] == SEED_SUBJECT_PROFILE
    for field in (
        "social_policy_hints",
        "embodied_policy_hints",
        "integrated_policy_hints",
        "initiative_policy_hints",
    ):
        assert field in sample.openemotion_result
        assert sample.openemotion_result[field] == {}
    for field in (
        "social_context",
        "environment_context",
        "selfhood_integration_context",
        "initiative_realization_context",
        "host_proactive_context",
    ):
        assert field in sample.openemotion_trace
        assert sample.openemotion_trace[field] == {}
    assert sample.ledger["openemotion"]["trace_payload"]["schema_version"] == "proto_self.trace.v2"
    stages = [item["stage"] for item in sample.openemotion_events]
    assert "ingress_kernel_trace" in stages
    ingress_event = next(item for item in sample.openemotion_events if item["stage"] == "kernel_output")
    assert ingress_event["payload"]["subject_profile"] == SEED_SUBJECT_PROFILE

    ledger_paths = list(tmp_path.glob("sample_*/ledger.json"))
    assert len(ledger_paths) == 1
    ledger = json.loads(ledger_paths[0].read_text(encoding="utf-8"))
    assert ledger["channel"] == "telegram"
    assert ledger["source_type"] == "simulated_external_entry"
    assert ledger["openemotion"]["trace_payload"]["schema_version"] == "proto_self.trace.v2"
    assert ledger["openemotion"]["result"]["subject_profile"] == SEED_SUBJECT_PROFILE
    for field in (
        "social_policy_hints",
        "embodied_policy_hints",
        "integrated_policy_hints",
        "initiative_policy_hints",
    ):
        assert ledger["openemotion"]["result"][field] == {}
    for field in (
        "social_context",
        "environment_context",
        "selfhood_integration_context",
        "initiative_realization_context",
        "host_proactive_context",
    ):
        assert ledger["openemotion"]["trace_payload"][field] == {}
    assert any(
        item["stage"] == "kernel_output" and item["payload"]["subject_profile"] == SEED_SUBJECT_PROFILE
        for item in ledger["openemotion"]["events"]
    )
    assert len(update.message.sent) == 1
