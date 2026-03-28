from openemotion.proto_self import ProtoSelfState
from openemotion.proto_self_v2.kernel import process_update_packet
from openemotion.proto_self_v2.schemas import UpdateEventV2, UpdatePacketV2


def test_process_update_packet_emits_v2_output_and_trace():
    state = ProtoSelfState.empty()
    packet = UpdatePacketV2(
        event_id="evt_v2_001",
        timestamp="2026-03-28T00:00:00",
        event=UpdateEventV2(
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="inspect file",
            raw_text="请帮我看看 main.py",
        ),
        conversation_summary={"session_id": "session:test", "turn_id": "turn_001"},
        task_summary={"pending_tasks": 1, "blocked_tasks": 0},
        runtime_summary={"runtime": "runtime_v2", "state_scope": "agent_global"},
        safety_context={"risk_level": "medium"},
        prediction_snapshot_prev={"expected_success": True},
    )

    output = process_update_packet(state, packet)

    assert output.schema_version == "proto_self.output.v2"
    assert output.trace_payload["schema_version"] == "proto_self.trace.v2"
    assert output.trace_payload["event_id"] == "evt_v2_001"
    assert output.trace_payload["update_packet_hash"]
    assert "retrieval_summary" in output.trace_payload
    assert "constraint_summary" in output.trace_payload
