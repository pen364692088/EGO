from openemotion.initiative_realization import REQUIRED_WRITEBACK_GATE
from openemotion.proto_self_v2.kernel import process_update_packet
from openemotion.proto_self_v2.schemas import UpdateEventV2, UpdatePacketV2
from openemotion.proto_self_v2.state import ProtoSelfStateV2


def _packet(*, event_id: str, runtime_summary: dict | None = None) -> UpdatePacketV2:
    return UpdatePacketV2(
        event_id=event_id,
        timestamp="2026-04-05T14:00:00",
        event=UpdateEventV2(
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="close a commitment loop",
            raw_text="先把这次承诺按约执行再汇报结果。",
        ),
        conversation_summary={"session_id": "session:test", "turn_id": "turn_001"},
        task_summary={"pending_tasks": 1, "blocked_tasks": 0},
        runtime_summary={"runtime": "runtime_v2", "state_scope": "agent_global", **(runtime_summary or {})},
        safety_context={"risk_level": "low"},
    )


def _owner_projection() -> dict:
    return {
        "schema_version": "mvp21-owner-v1",
        "owner_revision": 6,
        "last_revision_id": "realization_rev_000006",
        "dominant_mode": "review",
        "selected_lane": "review",
        "realization_pressure": 0.18,
        "fulfillment_readiness": 0.42,
        "hold_bias": 0.72,
        "failure_recovery_bias": 0.67,
        "continuity_confidence": 0.49,
        "active_commitments_count": 2,
        "ready_commitments_count": 1,
        "has_realization_candidate": True,
        "has_controlled_delivery_candidate": True,
        "legacy_signal": "should_not_pass",
    }


def _host_context() -> dict:
    return {
        "source": "runtime_v2",
        "host_lane_hint": "host_reality_review",
        "host_lane_hints": ["host_reality_review", "host_continuity_queue"],
        "readiness_basis": "delivery_continuity_gap",
        "delivery_readiness": 0.84,
        "idle_seconds": 1800.0,
        "recent_delivery_status": "sent",
        "recent_delivery_success": True,
        "promotion_budget": "controlled_axis",
        "pending_realization_refs": ["realization:commitment:01"],
        "readiness_basis": "delivery_continuity_gap",
    }


def _resource_runtime() -> dict:
    return {
        "resource_budget_hint": {"reserve_level": "medium"},
        "recent_delivery_outcome": {"status": "sent", "success": True},
        "idle_window": {"idle_seconds": 1200.0},
        "maintenance_context": {"continuity_gap": 0.34},
        "host_lane_hint": "host_reality_review",
        "host_lane_hints": ["host_reality_review", "host_continuity_queue"],
    }


def _selfhood_context(*, selected_priority: str = "review") -> dict:
    return {
        "schema_version": "mvp19-owner-v1",
        "owner_revision": 3,
        "last_revision_id": "integration_rev_000003",
        "policy_mode": "stability_first",
        "selected_priority": selected_priority,
        "highest_conflict_severity": "low",
        "integration_confidence": 0.58,
        "dominant_pressure_axis": "initiative_realization",
    }


def test_runtime_initiative_realization_context_is_reflected_in_trace_summary():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_realization_ctx_001",
        runtime_summary={
            "initiative_realization_context": _owner_projection(),
            "host_proactive_context": _host_context(),
            "selfhood_integration_context": _selfhood_context(),
            **_resource_runtime(),
        },
    )

    output = process_update_packet(state, packet)

    summary = output.trace_payload["initiative_realization_context"]
    assert summary["present"] is True
    assert summary["contract_version"] == "mvp21.initiative_realization_contract.v1"
    assert summary["projection_field"] == "runtime_summary.initiative_realization_context"
    assert summary["host_hint_field"] == "runtime_summary.host_proactive_context"
    assert summary["owner_revision"] == 6
    assert summary["last_revision_id"] == "realization_rev_000006"
    assert summary["selected_lane"] == "review"
    assert summary["host_lane_hint"] == "host_reality_review"
    assert output.trace_payload["retrieval_summary"]["initiative_realization_context_present"] is True


def test_runtime_initiative_realization_emits_proposal_only_writeback():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_realization_ctx_002",
        runtime_summary={
            "initiative_realization_context": _owner_projection(),
            "host_proactive_context": _host_context(),
            "selfhood_integration_context": _selfhood_context(selected_priority="review"),
            **_resource_runtime(),
        },
    )

    output = process_update_packet(state, packet)

    assert output.initiative_realization_delta
    assert output.initiative_realization_delta["proposal_candidate_count"] >= 1
    assert output.commitment_fulfillment_candidates
    assert isinstance(output.host_lane_hints, list)
    assert output.host_lane_hints
    assert output.controlled_delivery_candidate is not None
    assert output.controlled_delivery_candidate["required_gate"] == REQUIRED_WRITEBACK_GATE
    assert output.controlled_delivery_candidate["proposal_discipline"] == "proposal_only"
    assert output.controlled_delivery_candidate["behavioral_authority"] == "none"
    assert output.initiative_realization_writeback_candidate is not None
    assert output.initiative_realization_writeback_candidate["required_gate"] == REQUIRED_WRITEBACK_GATE
    assert output.initiative_realization_writeback_candidate["proposal_only"] is True
    assert output.initiative_realization_writeback_candidate["proposal_discipline"] == "proposal_only"
    assert output.initiative_realization_writeback_candidate["behavioral_authority"] == "none"
    assert "transport_directive" not in output.controlled_delivery_candidate.get("requested_effects", [])
    assert output.trace_payload["delivery_readiness_snapshot"]["contract_version"] == "mvp21.initiative_realization_contract.v1"


def test_initiative_realization_context_filters_untrusted_fields():
    state = ProtoSelfStateV2.empty()
    host_context = {
        **_host_context(),
        "intervention_result": {"legacy": True},
        "initiative_realization_arbiter": "legacy_should_not_pass",
    }
    packet = _packet(
        event_id="evt_realization_ctx_003",
        runtime_summary={
            "initiative_realization_context": {**_owner_projection(), "extra_owner_secret": {"x": 1}},
            "host_proactive_context": host_context,
            "maintenance_context": {"legacy": "value"},
            **_resource_runtime(),
        },
    )

    output = process_update_packet(state, packet)

    assert "extra_owner_secret" not in output.trace_payload["initiative_realization_context"]
    assert "intervention_result" not in output.trace_payload["initiative_realization_context"]
    assert "initiative_realization_arbiter" not in output.trace_payload["initiative_realization_context"]
    assert output.initiative_realization_audit_entries


def test_initiative_realization_without_surface_data_is_noop():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_realization_ctx_004",
        runtime_summary={
            "maintenance_context": {"continuity_gap": 0.01},
            "resource_budget_hint": {"reserve_level": "high"},
            "idle_window": {"idle_seconds": 10.0},
            "recent_delivery_outcome": {"status": "sent", "success": True},
        },
    )

    output = process_update_packet(state, packet)

    assert output.initiative_realization_context == {}
    assert output.initiative_realization_delta == {}
    assert output.commitment_fulfillment_candidates == []
    assert output.controlled_delivery_candidate is None
    assert output.initiative_realization_writeback_candidate is None
    assert output.trace_payload["retrieval_summary"]["initiative_realization_context_present"] is False
