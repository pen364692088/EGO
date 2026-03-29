from pathlib import Path

from app.config import load_config
from app.runtime_v2.proto_self_runtime import (
    RuntimeV2ProtoSelfRuntime,
    assess_risk_level,
    build_external_result_event,
    build_finalized_result_event,
    build_idle_check_event,
    build_proto_self_ingress_event,
    build_response_plan_payload,
    resolve_proto_self_schema_version,
    resolve_proto_self_subject_profile,
)
from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
from app.runtime_v2.state import RuntimeV2State
from app.telegram_evidence_collector import TelegramEvidenceCollector
from openemotion.proto_self_v2.seed_schemas import SEED_SUBJECT_PROFILE


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


def test_build_proto_self_ingress_event_supports_seed_profile_shape():
    state = RuntimeV2State(session_id="session:test")
    state.current_goal = "finish_seed_contract"
    state.ingress_context = {
        "proto_self_subject_profile": SEED_SUBJECT_PROFILE,
        "request_mode": "write",
        "runtime_action": "execute_task",
        "resolved_target": {"path": "app.py", "filename": "app.py"},
    }

    event = build_proto_self_ingress_event(
        session_id="session:test",
        turn_id="turn_seed_001",
        source="telegram",
        user_input="修改 app.py",
        state=state,
    )

    assert resolve_proto_self_subject_profile(state) == SEED_SUBJECT_PROFILE
    assert event["subject_profile"] == SEED_SUBJECT_PROFILE
    assert event["seed_event"]["event_type"] == "user_event"
    assert event["seed_event"]["runtime_summary"]["request_mode"] == "write"
    assert event["seed_event"]["payload"]["resolved_target_path"] == "app.py"


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


def test_build_finalized_result_event_supports_seed_feedback_writeback():
    state = RuntimeV2State(session_id="session:test")
    state.current_goal = "finish_seed_contract"
    state.last_model_action = {"type": "act"}
    state.ingress_context = {
        "proto_self_subject_profile": SEED_SUBJECT_PROFILE,
        "request_mode": "write",
        "runtime_action": "execute_task",
        "resolved_target": {"path": "app.py", "filename": "app.py"},
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

    event = build_finalized_result_event(
        session_id="session:test",
        turn_id="turn_004",
        result=result,
        state=state,
    )

    assert event is not None
    assert event["subject_profile"] == SEED_SUBJECT_PROFILE
    assert event["seed_event"]["event_type"] == "exec_result"
    assert event["seed_event"]["payload"]["status"] == "success"
    assert event["seed_event"]["payload"]["details"]["host_terminal_status"] == "completed_verified"


def test_build_idle_check_event_requires_seed_profile():
    state = RuntimeV2State(session_id="session:test")
    assert build_idle_check_event(session_id="session:test", turn_id="turn_005", state=state) is None

    state.proto_self_subject_profile_override = SEED_SUBJECT_PROFILE
    idle_event = build_idle_check_event(session_id="session:test", turn_id="turn_005", state=state)
    assert idle_event is not None
    assert idle_event["subject_profile"] == SEED_SUBJECT_PROFILE
    assert idle_event["seed_event"]["event_type"] == "idle_check"


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
    state.proto_self_context = {
        "subject_profile": SEED_SUBJECT_PROFILE,
        "candidate_actions": [{"action_type": "inspect_file"}],
        "governor_hint": {"status": "approved"},
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
    assert captured["proto_self_subject_profile"] == SEED_SUBJECT_PROFILE
    assert captured["candidate_action_types"] == ["inspect_file"]
    assert captured["proto_self_governor_hint"]["status"] == "approved"


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


def test_process_finalized_result_and_idle_check_capture_seed_trace():
    captured = {"stages": []}

    class Adapter:
        def handle_event(self, event):
            suffix = event["event_id"].split("_")[-1]
            return {
                "schema_version": "proto_self.output.v2",
                "event_id": event["event_id"],
                "subject_profile": event.get("subject_profile"),
                "candidate_actions": [{"action_type": "inspect_file"}] if suffix == "idle" else [],
                "policy_hint": {"governor_hint": {"status": "approved"}},
                "response_tendency": {"preferred_mode": "respond"},
                "reflection_note": None,
                "trace_payload": {
                    "schema_version": "proto_self.trace.v2",
                    "event_id": event["event_id"],
                    "subject_profile": event.get("subject_profile"),
                    "exec_result": (event.get("seed_event") or {}).get("payload"),
                    "candidate_actions": [{"action_type": "inspect_file"}] if suffix == "idle" else [],
                },
            }

    class Collector:
        def capture_openemotion_result(self, result):
            captured.setdefault("results", []).append(result["event_id"])

        def capture_openemotion_trace(self, trace_payload, *, stage):
            captured["stages"].append(stage)

    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter())
    state = RuntimeV2State(session_id="session:test")
    state.proto_self_subject_profile_override = SEED_SUBJECT_PROFILE
    state.ingress_context = {
        "proto_self_subject_profile": SEED_SUBJECT_PROFILE,
        "resolved_target": {"path": "app.py", "filename": "app.py"},
    }
    result = RuntimeV2TurnResult(
        status="completed_verified",
        state=state,
        reply=RuntimeV2Reply(
            reply_text="done",
            delivery_kind="final",
            status="completed_verified",
        ),
    )

    runtime.process_finalized_result(
        session_id="session:test",
        turn_id="turn_final",
        result=result,
        state=state,
        evidence_collector=Collector(),
    )
    runtime.process_idle_check(
        session_id="session:test",
        turn_id="turn_final",
        state=state,
        evidence_collector=Collector(),
    )

    assert "finalized_result_kernel_trace" in captured["stages"]
    assert "idle_check_kernel_trace" in captured["stages"]
    assert state.proto_self_context["last_exec_result"]["status"] == "success"
