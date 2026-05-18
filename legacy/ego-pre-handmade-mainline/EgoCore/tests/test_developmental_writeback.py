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
from app.runtime_v2.action_protocol import RuntimeV2Action
from app.runtime_v2.proto_self_runtime import RuntimeV2ProtoSelfRuntime
from app.telegram_bot import TelegramBot
from app.telegram_evidence_collector import TelegramEvidenceCollector
from emotiond.developmental import DevelopmentalManager, reset_developmental_manager


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
async def test_real_telegram_mainline_turn_writes_developmental_projection(monkeypatch, tmp_path):
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    load_config(validate=False)

    sample_dir = tmp_path / "telegram_samples"
    state_path = tmp_path / "developmental_state.json"
    observation_dir = tmp_path / "mvp16-observation"
    monkeypatch.setenv("EGO_DEVELOPMENTAL_STATE_PATH", str(state_path))
    monkeypatch.setenv("EGO_DEVELOPMENTAL_OBSERVATION_DIR", str(observation_dir))
    reset_developmental_manager(clear_persistence=True, state_path=state_path)

    collector = TelegramEvidenceCollector(
        artifacts_dir=sample_dir,
        source_type="real_channel",
        channel="telegram",
        evidence_level="E4",
    )
    monkeypatch.setattr(telegram_bot_module, "_EVIDENCE_COLLECTOR_AVAILABLE", True)
    monkeypatch.setattr(telegram_bot_module, "get_evidence_collector", lambda: collector)

    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    bot.app = SimpleNamespace(bot=DummyBot())
    loop = bot._get_runtime_v2_loop()
    loop.proto_self_runtime = RuntimeV2ProtoSelfRuntime(
        adapter=ProtoSelfAdapter(mirror_dir=tmp_path / "mirror"),
        evidence_collector_factory=lambda: collector,
    )

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

    async def fake_decide(_state):
        return RuntimeV2Action.from_model_output('{"type":"chat","message":"已收到"}')

    monkeypatch.setattr(loop.decision_engine, "decide", fake_decide)

    async def fake_run_turn(*, session_key, user_input, state, **kwargs):
        loop._states[session_key] = state
        result = await loop.run_turn_typed(session_id=session_key, user_input=user_input, source="telegram")
        return bot.telegram_runtime_fallback_runner.adapt_result(result)

    monkeypatch.setattr(bot.telegram_runtime_fallback_runner, "run_turn", fake_run_turn)

    update = DummyUpdate("帮我看下 app.py", 5001)
    await bot.handle_message(update, None)

    assert state_path.exists()
    assert (observation_dir / "real_trajectory_index.json").exists()
    assert (observation_dir / "real_trajectory_replay_audit.json").exists()

    reset_developmental_manager(state_path=state_path)
    manager = DevelopmentalManager(state_path=state_path)
    summary = manager.get_summary()

    assert summary["has_real_data"] is True
    assert summary["real_episode_count"] == 1
    assert summary["real_session_count"] == 1
    assert summary["real_day_count"] == 1
    assert summary["trajectory_refs_present"] is True
    assert summary["replay_refs_present"] is True
    assert summary["admission_inputs_present"] is False

    index_payload = json.loads((observation_dir / "real_trajectory_index.json").read_text(encoding="utf-8"))
    audit_payload = json.loads((observation_dir / "real_trajectory_replay_audit.json").read_text(encoding="utf-8"))

    assert index_payload["summary"]["real_episode_count"] == 1
    assert index_payload["episodes"][0]["sample_ref"].endswith("sample.json")
    assert audit_payload["source_refs_intact"] is True
    assert len(update.message.sent) == 1
