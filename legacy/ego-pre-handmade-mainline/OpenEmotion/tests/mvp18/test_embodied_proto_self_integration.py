from openemotion.proto_self_v2.kernel import process_update_packet
from openemotion.proto_self_v2.schemas import UpdateEventV2, UpdatePacketV2
from openemotion.proto_self_v2.state import ProtoSelfStateV2


def _packet(*, event_id: str, runtime_summary: dict | None = None) -> UpdatePacketV2:
    return UpdatePacketV2(
        event_id=event_id,
        timestamp="2026-04-04T02:00:00",
        event=UpdateEventV2(
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="embodied followup",
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
        timestamp="2026-04-04T02:30:00",
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


def _owner_context() -> dict:
    return {
        "schema_version": "mvp18-owner-v1",
        "owner_revision": 5,
        "last_revision_id": "embodied_rev_000005",
        "resource_slack": 0.28,
        "perceived_load": 0.74,
        "active_coupling_count": 2,
        "max_resource_pressure": 0.81,
        "min_resource_slack": 0.22,
        "max_boundary_pressure": 0.63,
        "recent_consequence_count": 2,
        "stabilization_proposal_count": 1,
        "self_world_guard_bias": 0.59,
        "emotiond.consequence.runner": {"should": "not_pass"},
    }


def _host_context() -> dict:
    return {
        "source": "runtime_v2",
        "action_ref": "delivery:telegram:turn_001",
        "coupling_event": "delivery_feedback",
        "outcome_type": "failure",
        "outcome_summary": "delivery timeout caused a missed followup",
        "resource_pressure_hint": 0.76,
        "slack_hint": 0.18,
        "boundary_signal": "guarded",
        "boundary_pressure_hint": 0.68,
        "stabilization_needed": True,
        "promotion_budget": "controlled_axis",
        "intervention_result": {"legacy": True},
    }


def test_runtime_embodied_context_is_reflected_in_trace_summary():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_embodied_ctx_001",
        runtime_summary={
            "embodied_self_context": _owner_context(),
            "environment_context": _host_context(),
        },
    )

    output = process_update_packet(state, packet)

    summary = output.trace_payload["constraint_summary"]["embodied_self_context"]
    assert summary["present"] is True
    assert summary["contract_version"] == "mvp18.embodied_contract.v1"
    assert summary["owner_revision"] == 5
    assert summary["active_coupling_count"] == 2
    assert summary["max_resource_pressure"] == 0.81
    assert summary["action_ref"] == "delivery:telegram:turn_001"
    assert output.confidence_meta["embodied_self_context_present"] is True
    assert output.confidence_meta["embodied_self_owner_revision"] == 5
    assert output.trace_payload["retrieval_summary"]["embodied_self_context_present"] is True
    assert output.trace_payload["retrieval_summary"]["environment_context_present"] is True


def test_runtime_embodied_context_emits_proposal_disciplined_hooks():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_embodied_ctx_002",
        runtime_summary={
            "embodied_self_context": _owner_context(),
            "environment_context": _host_context(),
        },
    )

    output = process_update_packet(state, packet)

    assert output.embodied_writeback_candidate is not None
    assert output.embodied_writeback_candidate["proposal_discipline"] == "proposal_only"
    assert output.embodied_writeback_candidate["behavioral_authority"] == "none"
    assert output.embodied_writeback_candidate["required_gate"] == "embodied_writeback_gate"
    assert output.consequence_update_candidates[0]["promotion_level"] == "controlled_axis"
    assert output.repair_or_stabilize_proposal_candidates[0]["proposal_discipline"] == "proposal_only"
    assert output.embodied_policy_hints["resource_bias"] == "conserve"
    assert output.policy_hint["embodied_boundary_bias"] == "cautious"
    assert output.trace_payload["environment_context"]["host_hint_field"] == "runtime_summary.environment_context"


def test_runtime_embodied_context_does_not_promote_second_truth_source_fields():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_embodied_ctx_003",
        runtime_summary={
            "embodied_self_context": _owner_context(),
            "environment_context": _host_context(),
        },
    )

    output = process_update_packet(state, packet)

    assert "emotiond.consequence.runner" not in output.trace_payload["constraint_summary"]["embodied_self_context"]
    assert "intervention_result" not in output.trace_payload["environment_context"]
    assert output.embodied_self_delta["proposal_candidate_count"] == 1


def test_legacy_environment_surfaces_do_not_create_formal_embodied_outputs():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_embodied_ctx_004",
        runtime_summary={"intervention_result": {"legacy": True}},
    )

    output = process_update_packet(state, packet)

    assert output.embodied_self_delta == {}
    assert output.repair_or_stabilize_proposal_candidates == []
    assert output.embodied_writeback_candidate is None
    assert output.trace_payload["constraint_summary"]["embodied_self_context"]["present"] is False


def test_developmental_embodied_context_keeps_outputs_proposal_only():
    state = ProtoSelfStateV2.empty()
    packet = _developmental_packet(
        event_id="evt_embodied_ctx_dev_001",
        runtime_summary={
            "embodied_self_context": _owner_context(),
            "environment_context": _host_context(),
        },
    )

    output = process_update_packet(state, packet)

    assert output.embodied_writeback_candidate is not None
    assert output.embodied_writeback_candidate["proposal_discipline"] == "proposal_only"
    assert output.embodied_writeback_candidate["behavioral_authority"] == "none"
    assert output.resource_boundary_snapshot["boundary_signal"] == "guarded"
    assert output.trace_payload["environment_context"]["action_ref"] == "delivery:telegram:turn_001"
    assert output.confidence_meta["embodied_self_context_present"] is True
