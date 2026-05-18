from openemotion.proto_self_v2.kernel import process_update_packet
from openemotion.proto_self_v2.schemas import UpdateEventV2, UpdatePacketV2
from openemotion.proto_self_v2.state import ProtoSelfStateV2


def _packet(*, event_id: str, runtime_summary: dict | None = None) -> UpdatePacketV2:
    return UpdatePacketV2(
        event_id=event_id,
        timestamp="2026-04-03T22:00:00",
        event=UpdateEventV2(
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="developmental followup",
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
        timestamp="2026-04-03T22:30:00",
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
        "schema_version": "mvp16-owner-v1",
        "owner_revision": 4,
        "last_revision_id": "developmental_rev_000004",
        "continuity_score": 0.62,
        "growth_pressure": 0.74,
        "stagnation_signal": 0.41,
        "identity_preservation_confidence": 0.88,
        "developmental_risk_index": 0.44,
        "trajectory_summary": {
            "current_arc": "identity_preserving_adaptation",
            "current_phase": "candidate_review",
            "recent_shift": "growth pressure up",
            "continuity_note": "review before promotion",
            "source_refs": ["trace:trajectory"],
        },
        "promotion_queue_size": 1,
        "recent_proposal_count": 2,
        "emotiond.developmental.manager": {"should": "not_pass"},
    }


def _host_context() -> dict:
    return {
        "source": "runtime_v2",
        "continuity_gap": 0.31,
        "growth_pressure_hint": 0.78,
        "stagnation_signal_hint": 0.42,
        "identity_guard": "strict",
        "replay_debt": 0.2,
        "promotion_budget": "controlled_axis",
        "drift_markers": ["marker:trajectory_gap"],
    }


def test_runtime_developmental_context_is_reflected_in_trace_summary():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_dev_ctx_001",
        runtime_summary={
            "developmental_self_context": _owner_context(),
            "developmental_context": _host_context(),
        },
    )

    output = process_update_packet(state, packet)

    summary = output.trace_payload["constraint_summary"]["developmental_self_context"]
    assert summary["present"] is True
    assert summary["owner_revision"] == 4
    assert summary["promotion_queue_size"] == 1
    assert summary["recent_proposal_count"] == 2
    assert summary["continuity_gap"] == 0.31
    assert output.confidence_meta["developmental_self_context_present"] is True
    assert output.confidence_meta["developmental_self_owner_revision"] == 4
    assert output.trace_payload["retrieval_summary"]["developmental_self_context_present"] is True


def test_runtime_developmental_context_emits_proposal_disciplined_hooks():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_dev_ctx_002",
        runtime_summary={
            "developmental_self_context": _owner_context(),
            "developmental_context": _host_context(),
        },
    )

    output = process_update_packet(state, packet)

    assert output.developmental_writeback_candidate is not None
    assert output.developmental_writeback_candidate["proposal_discipline"] == "proposal_only"
    assert output.developmental_writeback_candidate["behavioral_authority"] == "none"
    assert output.developmental_writeback_candidate["required_gate"] == "developmental_writeback_gate"
    assert output.developmental_proposal_candidates[0]["promotion_level"] == "controlled_axis"
    assert output.policy_hint["developmental_continuity_bias"] == "elevated"
    assert output.policy_hint["identity_preservation_guard"] == "strict"
    assert output.trace_payload["developmental_context"]["host_hint_field"] == "runtime_summary.developmental_context"


def test_runtime_developmental_context_does_not_promote_second_truth_source_fields():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_dev_ctx_003",
        runtime_summary={
            "developmental_self_context": _owner_context(),
            "developmental_context": _host_context(),
        },
    )

    output = process_update_packet(state, packet)
    persisted_projection = state.to_dict()["developmental_shadow"]

    assert "emotiond.developmental.manager" not in output.trace_payload["constraint_summary"]["developmental_self_context"]
    assert output.developmental_self_delta["proposal_candidate_count"] == 1
    assert "owner_revision" not in persisted_projection
    assert "promotion_queue_size" not in persisted_projection


def test_developmental_tick_emits_bounded_developmental_outputs():
    state = ProtoSelfStateV2.empty()
    packet = _developmental_packet(
        event_id="evt_dev_ctx_dev_001",
        runtime_summary={
            "developmental_self_context": _owner_context(),
            "developmental_context": _host_context(),
        },
    )

    output = process_update_packet(state, packet)

    assert output.developmental_proposal_candidates
    assert output.developmental_continuity_snapshot["continuity_gap"] == 0.31
    assert output.developmental_priority_hints["identity_preservation_guard"] == "strict"
    assert output.developmental_audit_entries
    assert output.response_tendency is not None
    assert output.trace_payload["developmental_writeback_candidate"]["proposal_discipline"] == "proposal_only"
