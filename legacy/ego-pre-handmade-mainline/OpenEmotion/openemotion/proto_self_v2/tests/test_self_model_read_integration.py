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


def _developmental_packet(*, event_id: str, runtime_summary: dict | None = None) -> UpdatePacketV2:
    return UpdatePacketV2(
        event_id=event_id,
        timestamp="2026-04-03T05:30:00",
        event=UpdateEventV2(
            actor="system",
            source="runtime",
            event_type="developmental_tick",
            user_intent=None,
            raw_text=None,
        ),
        conversation_summary={"session_id": "session:test", "turn_id": "turn_dev"},
        task_summary={"pending_tasks": 0, "blocked_tasks": 0},
        runtime_summary={
            "runtime": "runtime_v2",
            "state_scope": "agent_global",
            "developmental_mode": "shadow_observe",
            "observation_source": "direct_real",
            "developmental_trigger": "idle",
            "idle_seconds": 900.0,
            **(runtime_summary or {}),
        },
        safety_context={"risk_level": "low"},
        intervention_context={
            "developmental_input": {
                "state_snapshot": {
                    "recent_user_turns": [
                        "如果记忆一直在，但每次处理它的主体都重新生成，那还是同一个自我吗？",
                        "我怀疑我们把“记忆”误当成了“持续存在的证明”。",
                    ],
                    "recent_assistant_replies": [
                        "也许自我是个过程而不是实体。",
                        "记忆证明的是发生过，不一定证明同一个主体一直在。",
                    ],
                },
                "observation_refs": [
                    {"kind": "runtime_mainline_ingress", "event_id": "ingress_001", "text_preview": "记忆与持续存在"},
                    {"kind": "runtime_mainline_delivery", "event_id": "delivery_001", "text_preview": "记忆不等于主体连续"},
                ],
                "unresolved_tensions": [{"kind": "identity", "label": "记忆与主体连续", "intensity": 0.84}],
                "long_term_goals": [{"name": "cohere", "pressure": 0.6}],
            }
        },
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


def test_developmental_direct_real_frame_emits_formal_self_model_delta():
    state = ProtoSelfStateV2.empty()
    packet = _developmental_packet(
        event_id="evt_self_model_ctx_dev_001",
        runtime_summary={
            "self_model_context": {
                "schema_version": "1.0.0",
                "identity_handle": "openemotion",
                "capabilities": [{"capability_id": "cap_reasoning"}],
                "limitations": [{"limitation_id": "lim_no_gui"}],
                "active_goals": [],
                "standing_commitments": [],
                "confidence_by_domain": {"reasoning": 0.9},
                "known_unknowns": [],
                "tool_authority_boundary": {
                    "current_allowed_tools": ["read", "write", "edit", "exec"],
                    "restricted_tools": [],
                    "forbidden_tools": [],
                },
                "dependency_map": {"external_services": [], "internal_modules": []},
                "created_at": "2026-04-03T04:00:00Z",
                "last_modified_at": "2026-04-03T04:50:00Z",
                "modification_audit_trail": [],
            }
        },
    )

    output = process_update_packet(state, packet)

    assert "known_unknowns" in output.self_model_delta
    assert "confidence_by_domain" in output.self_model_delta
    assert output.self_model_delta["confidence_by_domain"]["dialogue_frame:continuity_gap"] >= 0.58
    assert output.confidence_meta["self_model_update_mode"] == "append_observation"
    assert output.trace_payload["self_model_delta"] == output.self_model_delta
    assert output.developmental_summary["self_model_delta_fields"] == ["confidence_by_domain", "known_unknowns"]


def test_developmental_synthetic_frame_does_not_emit_formal_self_model_delta():
    state = ProtoSelfStateV2.empty()
    packet = _developmental_packet(
        event_id="evt_self_model_ctx_dev_002",
        runtime_summary={
            "observation_source": "synthetic",
            "self_model_context": {
                "schema_version": "1.0.0",
                "identity_handle": "openemotion",
                "capabilities": [],
                "limitations": [],
                "active_goals": [],
                "standing_commitments": [],
                "confidence_by_domain": {},
                "known_unknowns": [],
                "tool_authority_boundary": {
                    "current_allowed_tools": ["read", "write", "edit", "exec"],
                    "restricted_tools": [],
                    "forbidden_tools": [],
                },
                "dependency_map": {"external_services": [], "internal_modules": []},
                "created_at": "2026-04-03T04:00:00Z",
                "last_modified_at": "2026-04-03T04:50:00Z",
                "modification_audit_trail": [],
            }
        },
    )

    output = process_update_packet(state, packet)

    assert output.self_model_delta == {}
    assert "self_model_update_mode" not in output.confidence_meta
