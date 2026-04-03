from openemotion.proto_self_v2.kernel import process_update_packet
from openemotion.proto_self_v2.schemas import UpdateEventV2, UpdatePacketV2
from openemotion.proto_self_v2.state import ProtoSelfStateV2


def _packet(*, event_id: str, runtime_summary: dict | None = None) -> UpdatePacketV2:
    return UpdatePacketV2(
        event_id=event_id,
        timestamp="2026-04-03T08:00:00",
        event=UpdateEventV2(
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="continue discussion",
            raw_text="继续",
        ),
        conversation_summary={"session_id": "session:test", "turn_id": "turn_001"},
        task_summary={"pending_tasks": 0, "blocked_tasks": 0},
        runtime_summary={"runtime": "runtime_v2", "state_scope": "agent_global", **(runtime_summary or {})},
        safety_context={"risk_level": "low"},
    )


def _developmental_packet(*, event_id: str, runtime_summary: dict | None = None) -> UpdatePacketV2:
    return UpdatePacketV2(
        event_id=event_id,
        timestamp="2026-04-03T08:30:00",
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
        intervention_context={"developmental_input": {"state_snapshot": {}, "observation_refs": []}},
    )


def test_runtime_endogenous_drive_context_is_reflected_in_trace_summary():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_drive_ctx_001",
        runtime_summary={
            "endogenous_drive_context": {
                "schema_version": "mvp14-owner-v1",
                "owner_revision": 4,
                "last_revision_id": "drive_rev_000004",
                "active_drives": [
                    {
                        "drive_id": "verification",
                        "drive_type": "verification",
                        "intensity": 0.9,
                        "persistence": 0.8,
                        "candidate_bias": 0.0,
                        "pressure": 0.72,
                    },
                    {
                        "drive_id": "completion",
                        "drive_type": "completion",
                        "intensity": 0.7,
                        "persistence": 0.7,
                        "candidate_bias": 0.0,
                        "pressure": 0.49,
                    },
                ],
                "homeostatic_signals": [],
                "maintenance_debt": [],
                "priority_snapshot": {
                    "dominant_drive": "verification",
                    "bias_terms": {"verification": 0.72, "completion": 0.49},
                },
                "summary": {"total_maintenance_debt": 0.0},
                "self_maintenance_candidate": None,
            },
            "resource_budget_hint": {"reserve_level": "normal"},
            "maintenance_context": {},
            "recent_delivery_outcome": {"success": True, "status": "sent"},
        },
    )

    output = process_update_packet(state, packet)

    summary = output.trace_payload["constraint_summary"]["endogenous_drive_context"]
    assert summary["present"] is True
    assert summary["owner_revision"] == 4
    assert summary["active_drive_count"] == 2
    assert output.candidate_bias_terms["verification"] == 0.72
    assert output.policy_hint["risk_bias"] == "high"
    assert output.policy_hint["closure_bias"] is True
    assert output.confidence_meta["endogenous_drive_context_present"] is True


def test_runtime_endogenous_drive_context_does_not_promote_second_truth_source_fields():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_drive_ctx_002",
        runtime_summary={
            "endogenous_drive_context": {
                "schema_version": "mvp14-owner-v1",
                "owner_revision": 2,
                "last_revision_id": "drive_rev_000002",
                "active_drives": [
                    {
                        "drive_id": "repair",
                        "drive_type": "repair",
                        "intensity": 0.6,
                        "persistence": 0.6,
                        "candidate_bias": 0.0,
                        "pressure": 0.36,
                    }
                ],
                "homeostatic_signals": [],
                "maintenance_debt": [{"debt_id": "repair_001", "category": "repair", "amount": 0.4, "priority": 0.8, "source": "x"}],
                "priority_snapshot": {"dominant_drive": "repair", "bias_terms": {"repair": 0.36}},
                "summary": {"total_maintenance_debt": 0.4},
                "self_maintenance_candidate": {"category": "self_maintenance", "priority": 0.8},
            },
            "resource_budget_hint": {"reserve_level": "low"},
            "maintenance_context": {},
            "recent_delivery_outcome": {"success": True, "status": "sent"},
        },
    )

    output = process_update_packet(state, packet)
    persisted_projection = state.to_dict()["drives"]

    assert "owner_revision" not in persisted_projection
    assert "priority_snapshot" not in persisted_projection
    assert output.self_maintenance_candidate is not None
    assert output.trace_payload["drive_context"]["projection_field"] == "runtime_summary.endogenous_drive_context"


def test_developmental_endogenous_drive_context_emits_maintenance_delta():
    state = ProtoSelfStateV2.empty()
    packet = _developmental_packet(
        event_id="evt_drive_ctx_dev_001",
        runtime_summary={
            "endogenous_drive_context": {
                "schema_version": "mvp14-owner-v1",
                "owner_revision": 5,
                "last_revision_id": "drive_rev_000005",
                "active_drives": [
                    {
                        "drive_id": "repair",
                        "drive_type": "repair",
                        "intensity": 0.8,
                        "persistence": 0.9,
                        "candidate_bias": 0.0,
                        "pressure": 0.72,
                    }
                ],
                "homeostatic_signals": [],
                "maintenance_debt": [{"debt_id": "replay_001", "category": "replay_verification", "amount": 0.5, "priority": 0.9, "source": "internal"}],
                "priority_snapshot": {"dominant_drive": "repair", "bias_terms": {"repair": 0.72}},
                "summary": {"total_maintenance_debt": 0.5},
                "self_maintenance_candidate": {"category": "self_maintenance", "priority": 0.9},
            },
            "resource_budget_hint": {"reserve_level": "low"},
            "maintenance_context": {"replay_inconsistency": True, "maintenance_debt_increment": 0.2, "continuity_signal": 0.3},
            "recent_delivery_outcome": {"success": False, "status": "failed"},
        },
    )

    output = process_update_packet(state, packet)

    assert output.self_maintenance_candidate is not None
    assert "maintenance_debts" in output.endogenous_drive_delta
    assert "drive_adjustments" in output.endogenous_drive_delta
    assert output.response_tendency is not None
    assert output.response_tendency.preferred_mode == "repair"
    assert output.trace_payload["drive_context"]["maintenance_candidate_present"] is True
