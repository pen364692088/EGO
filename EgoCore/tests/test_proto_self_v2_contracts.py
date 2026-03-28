from __future__ import annotations

from datetime import datetime

from app.openemotion_adapter.proto_self_adapter import ProtoSelfAdapter, normalize_to_proto_self_input
from app.openemotion_adapter.proto_self_contract_validator import validate_proto_self_v2_payload
from openemotion.proto_self_v2.schemas import UpdatePacketV2


def test_normalize_to_proto_self_input_builds_v2_packet():
    packet = normalize_to_proto_self_input(
        {
            "schema_version": "proto_self.v2",
            "event_id": "evt_v2_001",
            "timestamp": datetime.now().isoformat(),
            "event": {
                "actor": "user",
                "source": "telegram",
                "event_type": "user_message",
                "user_intent": "read file",
                "raw_text": "read file app.py",
            },
            "conversation_summary": {"session_id": "session:test", "turn_id": "turn_001"},
            "task_summary": {"pending_tasks": 1, "blocked_tasks": 0},
            "runtime_summary": {"runtime": "runtime_v2", "state_scope": "agent_global"},
            "safety_context": {"risk": "high"},
        }
    )

    assert isinstance(packet, UpdatePacketV2)
    assert packet.safety_context == {"risk_level": "high"}


def test_adapter_handle_event_supports_v2_contract(tmp_path):
    adapter = ProtoSelfAdapter(mirror_dir=tmp_path / "mirror")
    payload = {
        "schema_version": "proto_self.v2",
        "event_id": "evt_v2_002",
        "timestamp": datetime.now().isoformat(),
        "event": {
            "actor": "user",
            "source": "telegram",
            "event_type": "user_message",
            "user_intent": "read file",
            "raw_text": "read file app.py",
        },
        "conversation_summary": {"session_id": "session:test", "thread_id": "session:test", "turn_id": "turn_001"},
        "task_summary": {"pending_tasks": 1, "blocked_tasks": 0},
        "runtime_summary": {"runtime": "runtime_v2", "state_scope": "agent_global"},
        "safety_context": {"risk_level": "medium"},
        "prediction_snapshot_prev": {"expected_success": True},
    }

    result = adapter.handle_event(payload)

    assert result["schema_version"] == "proto_self.output.v2"
    assert result["event_id"] == "evt_v2_002"
    assert result["trace_payload"]["schema_version"] == "proto_self.trace.v2"
    assert result["trace_payload"]["update_packet_hash"]


def test_validate_proto_self_v2_payload_rejects_missing_event():
    payload = {
        "schema_version": "proto_self.v2",
        "event_id": "evt_v2_bad",
        "timestamp": datetime.now().isoformat(),
        "runtime_summary": {"runtime": "runtime_v2"},
        "task_summary": {},
        "conversation_summary": {},
        "safety_context": {"risk_level": "low"},
    }

    try:
        validate_proto_self_v2_payload(payload)
    except ValueError as exc:
        assert "event" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing required event")
