from openemotion.proto_self_v2.kernel import process_update_packet
from openemotion.proto_self_v2.schemas import UpdateEventV2, UpdatePacketV2
from openemotion.proto_self_v2.state import ProtoSelfStateV2


def _packet(*, event_id: str, runtime_summary: dict | None = None) -> UpdatePacketV2:
    return UpdatePacketV2(
        event_id=event_id,
        timestamp="2026-04-04T00:00:00",
        event=UpdateEventV2(
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="social continuity",
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
        timestamp="2026-04-04T00:30:00",
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
        "schema_version": "mvp17-owner-v1",
        "owner_revision": 4,
        "last_revision_id": "social_rev_000004",
        "active_relations_count": 3,
        "trust_signal_max": 0.71,
        "open_commitment_count": 1,
        "breached_commitment_count": 1,
        "pending_repair_count": 1,
        "boundary_caution_max": 0.63,
        "recent_counterpart_ids": ["telegram:8420019401", "telegram:secondary"],
        "emotiond.state.bond_trust": {"should": "not_pass"},
    }


def _host_context() -> dict:
    return {
        "source": "runtime_v2",
        "counterpart_id": "telegram:8420019401",
        "relationship_event": "commitment_breach",
        "relationship_continuity": "strained",
        "trust_drift": -0.22,
        "commitment_event": "breach",
        "commitment_breach": True,
        "repair_outcome": "pending",
        "unresolved_repair": True,
        "boundary_signal": "cautious",
        "promotion_budget": "review_only",
        "relationship_context": {"legacy": True},
    }


def test_runtime_social_context_is_reflected_in_trace_summary():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_social_ctx_001",
        runtime_summary={
            "social_self_context": _owner_context(),
            "social_context": _host_context(),
        },
    )

    output = process_update_packet(state, packet)

    summary = output.trace_payload["constraint_summary"]["social_self_context"]
    assert summary["present"] is True
    assert summary["contract_version"] == "mvp17.social_contract.v1"
    assert summary["owner_revision"] == 4
    assert summary["active_relations_count"] == 3
    assert summary["pending_repair_count"] == 1
    assert summary["counterpart_id"] == "telegram:8420019401"
    assert output.confidence_meta["social_self_context_present"] is True
    assert output.confidence_meta["social_self_owner_revision"] == 4
    assert output.trace_payload["retrieval_summary"]["social_self_context_present"] is True


def test_runtime_social_context_emits_proposal_disciplined_hooks():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_social_ctx_002",
        runtime_summary={
            "social_self_context": _owner_context(),
            "social_context": _host_context(),
        },
    )

    output = process_update_packet(state, packet)

    assert output.social_writeback_candidate is not None
    assert output.social_writeback_candidate["proposal_discipline"] == "proposal_only"
    assert output.social_writeback_candidate["behavioral_authority"] == "none"
    assert output.social_writeback_candidate["required_gate"] == "social_writeback_gate"
    assert output.relation_update_candidates[0]["proposal_discipline"] == "proposal_only"
    assert output.repair_proposal_candidates[0]["required_gate"] == "social_writeback_gate"
    assert output.social_policy_hints["repair_bias"] == "elevated"
    assert output.policy_hint["social_boundary_bias"] == "cautious"
    assert output.trace_payload["social_context"]["host_hint_field"] == "runtime_summary.social_context"


def test_runtime_social_context_does_not_promote_second_truth_source_fields():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_social_ctx_003",
        runtime_summary={
            "social_self_context": _owner_context(),
            "social_context": _host_context(),
        },
    )

    output = process_update_packet(state, packet)

    assert "emotiond.state.bond_trust" not in output.trace_payload["constraint_summary"]["social_self_context"]
    assert "relationship_context" not in output.trace_payload["social_context"]
    assert output.social_self_delta["proposal_candidate_count"] == 1


def test_legacy_social_surfaces_do_not_create_formal_social_outputs():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_social_ctx_004",
        runtime_summary={"relationship_context": {"legacy": True}},
    )

    output = process_update_packet(state, packet)

    assert output.social_self_delta == {}
    assert output.repair_proposal_candidates == []
    assert output.social_writeback_candidate is None
    assert output.trace_payload["constraint_summary"]["social_self_context"]["present"] is False


def test_developmental_social_context_keeps_outputs_proposal_only():
    state = ProtoSelfStateV2.empty()
    packet = _developmental_packet(
        event_id="evt_social_ctx_dev_001",
        runtime_summary={
            "social_self_context": _owner_context(),
            "social_context": _host_context(),
        },
    )

    output = process_update_packet(state, packet)

    assert output.social_writeback_candidate is not None
    assert output.social_writeback_candidate["proposal_discipline"] == "proposal_only"
    assert output.social_writeback_candidate["behavioral_authority"] == "none"
    assert output.social_policy_hints["commitment_guard"] == "strict"
    assert output.trace_payload["social_context"]["counterpart_id"] == "telegram:8420019401"
    assert output.confidence_meta["social_self_context_present"] is True
