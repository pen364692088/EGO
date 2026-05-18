from openemotion.proto_self import ProtoSelfState
from openemotion.proto_self_v2.state import ProtoSelfStateV2
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


def test_process_update_packet_preserves_v1_identity_delta_shape_in_v2_output():
    state = ProtoSelfState.empty()
    packet = UpdatePacketV2(
        event_id="evt_v2_identity_001",
        timestamp="2026-03-28T00:00:00",
        event=UpdateEventV2(
            actor="system",
            source="runtime",
            event_type="tool_result",
            user_intent="identity_check",
        ),
        conversation_summary={"session_id": "session:test", "turn_id": "turn_identity_001"},
        task_summary={"pending_tasks": 0, "blocked_tasks": 0},
        runtime_summary={"runtime": "runtime_v2", "state_scope": "agent_global"},
        safety_context={"risk_level": 0.9, "boundary_touched": True},
        prediction_snapshot_prev={"expected_success": False},
    )

    output = process_update_packet(state, packet)

    assert output.identity_delta == output.trace_payload["identity_delta"]
    assert set(output.identity_delta.keys()) == {
        "core_roles_add",
        "core_commitments_add",
        "core_boundaries_add",
        "stable_preferences_patch",
        "identity_confidence_delta",
    }


def test_proto_self_v2_state_round_trip_keeps_v1_identity_shape():
    state_v2 = ProtoSelfStateV2.empty()
    state_v2.identity.core_roles = ["assistant"]
    state_v2.identity.core_commitments = ["do_not_fabricate"]
    state_v2.identity.core_boundaries = ["no_unverified_completion_claims"]
    state_v2.identity.stable_preferences = {"clarity": 0.8}
    state_v2.identity.identity_confidence = 0.61

    restored = ProtoSelfStateV2.from_dict(state_v2.to_dict())
    restored_v1 = restored.to_v1()

    assert restored.identity.to_dict() == state_v2.identity.to_dict()
    assert restored_v1.identity.to_dict() == state_v2.identity.to_dict()
