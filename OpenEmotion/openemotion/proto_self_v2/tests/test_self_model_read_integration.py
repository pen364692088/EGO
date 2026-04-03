from openemotion.proto_self_v2.kernel import process_update_packet
from openemotion.proto_self_v2.schemas import UpdateEventV2, UpdatePacketV2
from openemotion.proto_self_v2.state import ProtoSelfStateV2


def _packet(*, event_id: str, runtime_summary: dict | None = None) -> UpdatePacketV2:
    return UpdatePacketV2(
        event_id=event_id,
        timestamp="2026-04-02T23:40:00",
        event=UpdateEventV2(
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="discuss self model",
            raw_text="我们继续讨论这个问题",
        ),
        conversation_summary={"session_id": "session:test", "turn_id": "turn_001"},
        task_summary={"pending_tasks": 0, "blocked_tasks": 0},
        runtime_summary={"runtime": "runtime_v2", "state_scope": "agent_global", **(runtime_summary or {})},
        safety_context={"risk_level": "low"},
    )


def test_runtime_self_model_context_is_reflected_in_trace_summary():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_self_model_ctx_001",
        runtime_summary={
            "self_model_context": {
                "schema_version": "1.0.0",
                "identity_handle": "openemotion",
                "capabilities": [{"capability_id": "cap_reasoning"}],
                "limitations": [{"limitation_id": "lim_no_gui"}],
                "active_goals": [{"goal_id": "goal_mvp13"}],
                "standing_commitments": [{"commitment_id": "stay_governed"}],
                "confidence_by_domain": {"reasoning": 0.9, "action:reply": 0.4},
                "known_unknowns": [{"unknown_id": "u1"}],
                "last_modified_at": "2026-04-02T23:00:00Z",
                "behavioral_tendencies": [{"should": "not_pass"}],
            }
        },
    )

    output = process_update_packet(state, packet)

    summary = output.trace_payload["constraint_summary"]["self_model_context"]
    assert summary["present"] is True
    assert summary["identity_handle"] == "openemotion"
    assert summary["schema_version"] == "1.0.0"
    assert summary["capability_count"] == 1
    assert summary["limitation_count"] == 1
    assert summary["active_goals_count"] == 1
    assert summary["standing_commitments_count"] == 1
    assert summary["confidence_domains_count"] == 2
    assert summary["known_unknowns_count"] == 1
    assert "behavioral_tendencies" not in summary["authoritative_fields"]
    assert output.confidence_meta["self_model_context_present"] is True
    assert output.confidence_meta["self_model_context_identity_handle"] == "openemotion"
    assert output.trace_payload["retrieval_summary"]["self_model_context_present"] is True


def test_runtime_self_model_context_does_not_promote_second_truth_source_fields():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_self_model_ctx_002",
        runtime_summary={
            "self_model_context": {
                "identity_handle": "openemotion",
                "standing_commitments": [{"commitment_id": "stay_governed"}],
                "active_goals": [{"goal_id": "goal_mvp13"}],
                "confidence_by_domain": {"action:reply": 0.4},
                "active_tensions": [{"legacy": True}],
            }
        },
    )

    output = process_update_packet(state, packet)
    persisted_projection = state.to_dict()["self_model"]

    assert "standing_commitments" not in output.self_model_delta
    assert "active_goals" not in output.self_model_delta
    assert "confidence_by_domain" not in output.self_model_delta
    assert "active_tensions" not in output.trace_payload["constraint_summary"]["self_model_context"]["authoritative_fields"]
    assert "standing_commitments" not in persisted_projection
    assert "active_goals" not in persisted_projection
