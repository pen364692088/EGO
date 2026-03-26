from app.runtime_v2.proto_self_runtime import (
    RuntimeV2ProtoSelfRuntime,
    assess_risk_level,
    build_external_result_event,
    build_proto_self_ingress_event,
    build_response_plan_payload,
)
from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
from app.runtime_v2.state import RuntimeV2State


def test_assess_risk_level_keeps_existing_keywords():
    assert assess_risk_level("删除生产数据库") == "critical"
    assert assess_risk_level("git push origin main") == "high"
    assert assess_risk_level("状态查询") == "low"


def test_build_proto_self_ingress_event_uses_runtime_shape():
    state = RuntimeV2State(session_id="session:test")
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


def test_build_external_result_event_preserves_feedback_contract():
    state = RuntimeV2State(session_id="session:test")
    state.current_goal = "执行任务"
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


def test_capture_response_plan_uses_same_payload_shape():
    captured = {}

    class Collector:
        def capture_response_plan(self, plan):
            captured.update(plan)

    runtime = RuntimeV2ProtoSelfRuntime(adapter=object())
    result = RuntimeV2TurnResult(
        status="completed_verified",
        state=None,
        reply=RuntimeV2Reply(
            reply_text="已完成",
            delivery_kind="final",
            status="completed_verified",
        ),
    )
    runtime.capture_response_plan(result=result, evidence_collector=Collector())
    assert captured == build_response_plan_payload(result=result)


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
