from pathlib import Path

from app.config import load_config
from app.runtime_v2.proto_self_runtime import (
    RuntimeV2ProtoSelfRuntime,
    assess_risk_level,
    build_external_result_event,
    build_proto_self_ingress_event,
    build_response_plan_payload,
    resolve_proto_self_schema_version,
)
from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
from app.runtime_v2.state import RuntimeV2State
from app.telegram_evidence_collector import TelegramEvidenceCollector


def test_assess_risk_level_keeps_existing_keywords():
    assert assess_risk_level("删除生产数据库") == "critical"
    assert assess_risk_level("git push origin main") == "high"
    assert assess_risk_level("状态查询") == "low"


def test_build_proto_self_ingress_event_preserves_v1_fallback_shape():
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {
        "proto_self_version": "v1",
        "restore_observation": {
            "restore_id": "restore_001",
            "restore_status": "success",
            "post_restore_first_turn": True,
        }
    }
    event = build_proto_self_ingress_event(
        session_id="session:test",
        turn_id="turn_001",
        source="telegram",
        user_input="删除生产数据库",
        state=state,
    )
    assert event["event_id"] == "session:test_turn_001"
    assert event["source"] == "telegram"
    assert event["safety_context"]["risk_level"] == "critical"
    assert "risk" not in event["safety_context"]
    assert event["external_result"] is None
    assert event["runtime_summary"]["restore_observation"]["restore_id"] == "restore_001"


def test_resolve_proto_self_schema_version_defaults_to_v2():
    state = RuntimeV2State(session_id="session:test")
    assert resolve_proto_self_schema_version(state) == "proto_self.v2"


def test_resolve_proto_self_schema_version_supports_explicit_v1_fallback():
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {"proto_self_version": "v1"}
    assert resolve_proto_self_schema_version(state) == "proto_self.v1"


def test_build_proto_self_ingress_event_supports_v2_shape():
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {
        "proto_self_version": "v2",
        "prediction_snapshot_prev": {"expected_success": True},
        "executed_action_prev": {"kind": "reply"},
    }
    event = build_proto_self_ingress_event(
        session_id="session:test",
        turn_id="turn_002",
        source="telegram",
        user_input="帮我看下 app.py",
        state=state,
    )

    assert event["schema_version"] == "proto_self.v2"
    assert event["event"]["source"] == "telegram"
    assert event["safety_context"]["risk_level"] == "low"
    assert event["prediction_snapshot_prev"]["expected_success"] is True
    assert event["external_outcome"] is None


def test_build_external_result_event_preserves_v1_feedback_contract():
    state = RuntimeV2State(session_id="session:test")
    state.current_goal = "执行任务"
    state.ingress_context = {"proto_self_version": "v1"}
    event = build_external_result_event(
        session_id="session:test",
        turn_id="turn_001",
        step=0,
        tool_result={"success": False, "tool": "shell", "exit_code": 1, "stderr": "boom"},
        state=state,
    )
    assert event["event_type"] == "tool_result"
    assert event["safety_context"]["risk_level"] == "high"
    assert event["external_result"]["success"] is False
    assert event["task_context"]["blocked_tasks"] == 1


def test_build_external_result_event_supports_v2_shape():
    state = RuntimeV2State(session_id="session:test")
    state.current_goal = "执行任务"
    state.ingress_context = {
        "proto_self_version": "v2",
        "executed_action_prev": {"kind": "tool"},
    }
    event = build_external_result_event(
        session_id="session:test",
        turn_id="turn_003",
        step=1,
        tool_result={"success": False, "tool": "shell", "exit_code": 1, "stderr": "boom"},
        state=state,
    )

    assert event["schema_version"] == "proto_self.v2"
    assert event["event"]["event_type"] == "tool_result"
    assert event["external_outcome"]["success"] is False
    assert event["executed_action_prev"]["kind"] == "tool"


def test_build_external_result_event_v1_fallback_does_not_steal_family_or_repair_semantics():
    state = RuntimeV2State(session_id="session:test")
    state.current_goal = "执行任务"
    state.ingress_context = {"proto_self_version": "v1"}

    event = build_external_result_event(
        session_id="session:test",
        turn_id="turn_002",
        step=0,
        tool_result={"success": False, "tool": "file", "exit_code": 1, "stderr": "blocked: missing file"},
        state=state,
    )

    assert "closure_family_id" not in event
    assert "closure_signature" not in event
    assert "repair_closure" not in event
    assert "mode_signature" not in event
    assert event["external_result"] == {
        "success": False,
        "tool": "file",
        "exit_code": 1,
        "error": "blocked: missing file",
    }


def test_capture_response_plan_uses_same_payload_shape():
    captured = {}

    class Collector:
        def capture_response_plan(self, plan):
            captured.update(plan)

    runtime = RuntimeV2ProtoSelfRuntime(adapter=object())
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {
        "restore_observation": {
            "restore_id": "restore_001",
            "restore_status": "success",
            "post_restore_first_turn": True,
        }
    }
    result = RuntimeV2TurnResult(
        status="completed_verified",
        state=state,
        reply=RuntimeV2Reply(
            reply_text="已完成",
            delivery_kind="final",
            status="completed_verified",
        ),
    )
    runtime.capture_response_plan(result=result, evidence_collector=Collector())
    assert captured == build_response_plan_payload(result=result)
    assert captured["restore_observation"]["restore_id"] == "restore_001"


def test_process_ingress_prefers_collector_for_trace_capture():
    captured = {"normalized_event": None, "result": None, "trace": None}

    class Adapter:
        def handle_event(self, event):
            return {
                "event_id": event["event_id"],
                "policy_hint": {"risk_bias": "high"},
                "response_tendency": {"preferred_mode": "respond"},
                "reflection_note": None,
                "trace_payload": {
                    "schema_version": "proto_self.trace.v1",
                    "event_id": event["event_id"],
                    "policy_hint": {"risk_bias": "high"},
                },
            }

    class Collector:
        def capture_normalized_event(self, event):
            captured["normalized_event"] = event

        def capture_openemotion_result(self, result):
            captured["result"] = result

        def capture_openemotion_trace(self, trace_payload, *, stage):
            captured["trace"] = {"payload": trace_payload, "stage": stage}

    class TraceBridge:
        def __init__(self):
            self.entries = []

        def write(self, payload):
            self.entries.append(payload)

    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter(), trace_bridge=TraceBridge())
    state = RuntimeV2State(session_id="session:test")
    collector = Collector()

    runtime.process_ingress(
        session_id="session:test",
        turn_id="turn_001",
        source="telegram",
        user_input="删除生产数据库",
        state=state,
        evidence_collector=collector,
    )

    assert captured["normalized_event"]["event_id"] == "session:test_turn_001"
    assert captured["result"]["event_id"] == "session:test_turn_001"
    assert captured["trace"]["stage"] == "ingress_kernel_trace"
    assert runtime.trace_bridge.entries == []


def test_process_ingress_falls_back_to_trace_bridge_without_collector():
    class Adapter:
        def handle_event(self, event):
            return {
                "event_id": event["event_id"],
                "policy_hint": {"risk_bias": "normal"},
                "response_tendency": {"preferred_mode": "respond"},
                "reflection_note": None,
                "trace_payload": {
                    "schema_version": "proto_self.trace.v1",
                    "event_id": event["event_id"],
                    "policy_hint": {"risk_bias": "normal"},
                },
            }

    class TraceBridge:
        def __init__(self):
            self.entries = []

        def write(self, payload):
            self.entries.append(payload)

    bridge = TraceBridge()
    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter(), trace_bridge=bridge)
    state = RuntimeV2State(session_id="session:test")

    runtime.process_ingress(
        session_id="session:test",
        turn_id="turn_001",
        source="telegram",
        user_input="你好",
        state=state,
    )

    assert bridge.entries == [
        {
            "schema_version": "proto_self.trace.v1",
            "event_id": "session:test_turn_001",
            "policy_hint": {"risk_bias": "normal"},
        }
    ]


async def _run_chat_turn(loop, session_id: str, text: str, *, source: str, collector):
    from app.runtime_v2.action_protocol import RuntimeV2Action

    async def fake_decide(_state):
        return RuntimeV2Action.from_model_output('{"type":"chat","message":"已收到"}')

    loop._decide = fake_decide
    return await loop.run_turn_typed(session_id, text, source=source, evidence_collector=collector)


def test_runtime_loop_captures_proto_self_v2_evidence_in_ledger(monkeypatch, tmp_path):
    import asyncio

    from app.openemotion_adapter.proto_self_adapter import ProtoSelfAdapter
    from app.runtime_v2.loop import RuntimeV2Loop

    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    load_config(validate=False)

    collector = TelegramEvidenceCollector(
        artifacts_dir=tmp_path,
        source_type="simulated",
        channel="telegram",
        evidence_level="E4",
    )
    collector.start_sample(
        {
            "update_id": 5001,
            "message": {
                "message_id": 5001,
                "date": 1774483895,
                "chat": {"id": 42, "type": "private"},
                "from": {"id": 7, "is_bot": False, "username": "tester"},
                "text": "帮我看下 app.py",
            },
        }
    )

    loop = RuntimeV2Loop()
    loop.proto_self_runtime = RuntimeV2ProtoSelfRuntime(
        adapter=ProtoSelfAdapter(mirror_dir=tmp_path / "mirror")
    )
    state = loop.get_state("session:test-v2")
    state.ingress_context = {
        "proto_self_version": "v2",
        "prediction_snapshot_prev": {"expected_success": True},
        "executed_action_prev": {"kind": "reply", "status": "delivered"},
    }

    result = asyncio.run(
        _run_chat_turn(
            loop,
            "session:test-v2",
            "帮我看下 app.py",
            source="telegram",
            collector=collector,
        )
    )
    collector.capture_outbox_record(
        {
            "chat_id": 42,
            "message_id": 5002,
            "date": "2026-03-28T00:00:01",
            "text_length": len(result.reply_text),
            "success": True,
        }
    )
    sample = collector.finalize_sample()

    assert sample is not None
    assert sample.normalized_event["schema_version"] == "proto_self.v2"
    assert sample.openemotion_result["schema_version"] == "proto_self.output.v2"
    assert sample.openemotion_trace["schema_version"] == "proto_self.trace.v2"
    assert sample.ledger["openemotion"]["trace_payload"]["schema_version"] == "proto_self.trace.v2"
