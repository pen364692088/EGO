from openemotion.proto_self_v2.kernel import process_update_packet
from openemotion.proto_self_v2.schemas import UpdateEventV2, UpdatePacketV2
from openemotion.proto_self_v2.state import ProtoSelfStateV2


def _packet(*, event_id: str, runtime_summary: dict | None = None) -> UpdatePacketV2:
    return UpdatePacketV2(
        event_id=event_id,
        timestamp="2026-04-04T18:00:00",
        event=UpdateEventV2(
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="follow through on an existing commitment",
            raw_text="继续推进，不要丢掉之前说好的事。",
        ),
        conversation_summary={"session_id": "session:test", "turn_id": "turn_001"},
        task_summary={"pending_tasks": 1, "blocked_tasks": 0},
        runtime_summary={"runtime": "runtime_v2", "state_scope": "agent_global", **(runtime_summary or {})},
        safety_context={"risk_level": "low"},
    )


def _initiative_owner_projection() -> dict:
    return {
        "schema_version": "mvp20-owner-v1",
        "owner_revision": 4,
        "last_revision_id": "initiative_rev_000004",
        "dominant_mode": "carry_forward",
        "initiative_pressure": 0.78,
        "commitment_carryover_bias": 0.82,
        "recent_delivery_sensitivity": 0.64,
        "selected_priority": "carry_forward",
        "active_commitments_count": 2,
        "blocked_commitments_count": 0,
        "continuity_confidence": 0.73,
        "has_initiative_proposal_candidate": True,
        "has_host_proactive_candidate": False,
        "direct_owner_state": {"must_not": "leak"},
    }


def _initiative_context(*, reserve_level: str = "medium", delivery_status: str = "sent") -> dict:
    return {
        "source": "runtime_v2",
        "initiative_trigger": "commitment_followup",
        "continuity_ref": "commitment:followup:001",
        "pending_commitment_refs": ["commitment:followup:001"],
        "blocked_commitment_refs": [],
        "reserve_level": reserve_level,
        "recent_delivery_status": delivery_status,
        "delivery_failure": delivery_status in {"failed", "blocked"},
        "idle_seconds": 1200.0,
        "host_lane_hint": "host_proactive_outbox",
        "promotion_budget": "controlled_axis",
        "legacy_owner": "wp7_should_not_pass",
    }


def _selfhood_integration_context(*, selected_priority: str = "review", conflict: str = "medium") -> dict:
    return {
        "schema_version": "mvp19-owner-v1",
        "owner_revision": 2,
        "last_revision_id": "integration_rev_000002",
        "policy_mode": "stability_first",
        "integration_posture": selected_priority,
        "integration_confidence": 0.66,
        "selected_priority": selected_priority,
        "dominant_pressure_axis": "social_self",
        "highest_conflict_severity": conflict,
        "stabilize_weight": 0.61,
        "explore_weight": 0.39,
        "repair_weight": 0.58,
        "progress_weight": 0.42,
        "social_weight": 0.53,
        "boundary_weight": 0.47,
        "active_hint_axes": ["social_self", "initiative_self"],
        "tendency_status": "proposed",
    }


def test_process_update_packet_exposes_initiative_proto_self_outputs():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_initiative_001",
        runtime_summary={
            "initiative_self_context": _initiative_owner_projection(),
            "initiative_context": _initiative_context(),
            "selfhood_integration_context": _selfhood_integration_context(selected_priority="review"),
            "resource_budget_hint": {"reserve_level": "medium"},
            "recent_delivery_outcome": {"status": "sent", "success": True},
            "idle_window": {"idle_seconds": 1200.0},
        },
    )

    output = process_update_packet(state, packet)

    assert output.initiative_self_delta["selected_priority"] == "review"
    assert output.initiative_proposal_candidates
    assert output.commitment_execution_snapshot["active_commitments_count"] == 2
    assert output.initiative_policy_hints["host_proactive_mode"] == "held"
    assert output.initiative_writeback_candidate["required_gate"] == "initiative_writeback_gate"
    assert output.initiative_writeback_candidate["behavioral_authority"] == "none"
    assert output.trace_payload["initiative_context"]["contract_version"] == "mvp20.initiative_contract.v1"
    assert output.trace_payload["initiative_context"]["projection_field"] == "runtime_summary.initiative_self_context"
    assert output.trace_payload["initiative_context"]["host_hint_field"] == "runtime_summary.initiative_context"
    assert output.trace_payload["initiative_context"]["runtime_local_projection_field"] == (
        "proto_self_v2.state.initiative_self"
    )
    assert output.trace_payload["initiative_context"]["present"] is True
    assert "direct_owner_state" not in output.trace_payload["initiative_context"]
    assert output.confidence_meta["initiative_self_context_present"] is True


def test_initiative_contract_can_surface_bounded_host_proactive_candidate_without_execution():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_initiative_002",
        runtime_summary={
            "initiative_self_context": _initiative_owner_projection(),
            "initiative_context": _initiative_context(reserve_level="medium", delivery_status="sent"),
            "selfhood_integration_context": _selfhood_integration_context(selected_priority="grow", conflict="low"),
            "resource_budget_hint": {"reserve_level": "medium"},
            "recent_delivery_outcome": {"status": "sent", "success": True},
            "idle_window": {"idle_seconds": 2400.0},
        },
    )

    output = process_update_packet(state, packet)

    candidate = output.host_proactive_candidate
    assert candidate is not None
    assert candidate["required_gate"] == "initiative_writeback_gate"
    assert candidate["proposal_discipline"] == "proposal_only"
    assert candidate["behavioral_authority"] == "none"
    assert "transport_directive" not in candidate.get("requested_effects", [])
    assert output.response_tendency is not None
    assert output.response_tendency.preferred_mode == "respond"


def test_initiative_contract_does_not_consume_legacy_host_proactive_semantic_owner():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_initiative_003",
        runtime_summary={
            "initiative_self_context": _initiative_owner_projection(),
            "initiative_context": {
                **_initiative_context(reserve_level="low", delivery_status="blocked"),
                "initiative_arbiter": "legacy_should_not_pass",
                "pending_proactive_followup": {"id": "legacy_followup"},
                "controlled_proactive_delivery_lane": "legacy_lane",
            },
            "selfhood_integration_context": _selfhood_integration_context(selected_priority="review"),
            "resource_budget_hint": {"reserve_level": "low"},
            "recent_delivery_outcome": {"status": "blocked", "success": False},
            "idle_window": {"idle_seconds": 300.0},
        },
    )

    output = process_update_packet(state, packet)

    assert output.initiative_policy_hints["initiative_bias"] == "hold"
    assert output.trace_payload["initiative_context"]["reserve_level"] == "low"
    assert "initiative_arbiter" not in output.trace_payload["initiative_context"]
    assert "pending_proactive_followup" not in output.trace_payload["initiative_context"]
    assert "controlled_proactive_delivery_lane" not in output.trace_payload["initiative_context"]
