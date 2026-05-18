from openemotion.proto_self_v2.kernel import process_update_packet
from openemotion.proto_self_v2.schemas import UpdateEventV2, UpdatePacketV2
from openemotion.proto_self_v2.state import ProtoSelfStateV2


def _packet(*, event_id: str, runtime_summary: dict | None = None) -> UpdatePacketV2:
    return UpdatePacketV2(
        event_id=event_id,
        timestamp="2026-04-03T11:00:00",
        event=UpdateEventV2(
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="reflective discussion",
            raw_text="继续分析这个判断",
        ),
        conversation_summary={"session_id": "session:test", "turn_id": "turn_001"},
        task_summary={"pending_tasks": 0, "blocked_tasks": 0},
        runtime_summary={"runtime": "runtime_v2", "state_scope": "agent_global", **(runtime_summary or {})},
        safety_context={"risk_level": "low"},
    )


def _developmental_packet(*, event_id: str, runtime_summary: dict | None = None) -> UpdatePacketV2:
    return UpdatePacketV2(
        event_id=event_id,
        timestamp="2026-04-03T11:30:00",
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


def test_runtime_reflective_context_is_reflected_in_trace_summary():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_reflect_ctx_001",
        runtime_summary={
            "reflective_self_context": {
                "schema_version": "mvp15-owner-v1",
                "owner_revision": 3,
                "last_revision_id": "reflective_rev_000003",
                "reflection_pressure": 0.62,
                "pending_reflections": 2,
                "unresolved_items": 1,
                "proposal_candidates": 1,
                "top_target_ids": ["decision:target", "trajectory:drift"],
                "emotiond.reflection_engine": {"should": "not_pass"},
            }
        },
    )

    output = process_update_packet(state, packet)

    summary = output.trace_payload["constraint_summary"]["reflective_self_context"]
    assert summary["present"] is True
    assert summary["owner_revision"] == 3
    assert summary["proposal_candidates"] == 1
    assert summary["top_target_ids"] == ["decision:target", "trajectory:drift"]
    assert output.confidence_meta["reflective_self_context_present"] is True
    assert output.confidence_meta["reflective_self_owner_revision"] == 3
    assert output.trace_payload["retrieval_summary"]["reflective_self_context_present"] is True


def test_runtime_reflective_context_emits_proposal_disciplined_hooks():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_reflect_ctx_002",
        runtime_summary={
            "reflective_self_context": {
                "schema_version": "mvp15-owner-v1",
                "owner_revision": 5,
                "last_revision_id": "reflective_rev_000005",
                "reflection_pressure": 0.71,
                "pending_reflections": 1,
                "unresolved_items": 2,
                "proposal_candidates": 1,
                "top_target_ids": ["decision:target"],
            }
        },
    )

    output = process_update_packet(state, packet)

    assert output.reflection_writeback_candidate is not None
    assert output.reflection_writeback_candidate["proposal_discipline"] == "proposal_only"
    assert output.reflection_writeback_candidate["behavioral_authority"] == "none"
    assert output.revision_proposal_candidates[0]["required_gate"] == "reflection_writeback_gate"
    assert output.policy_hint["reflection_bias"] == "elevated"
    assert output.trace_payload["reflection_context"]["projection_field"] == "runtime_summary.reflective_self_context"


def test_runtime_reflective_context_does_not_promote_second_truth_source_fields():
    state = ProtoSelfStateV2.empty()
    packet = _packet(
        event_id="evt_reflect_ctx_003",
        runtime_summary={
            "reflective_self_context": {
                "schema_version": "mvp15-owner-v1",
                "owner_revision": 1,
                "last_revision_id": "reflective_rev_000001",
                "reflection_pressure": 0.25,
                "pending_reflections": 0,
                "unresolved_items": 0,
                "proposal_candidates": 0,
                "top_target_ids": [],
                "emotiond.self_counterfactual": {"legacy": True},
            }
        },
    )

    output = process_update_packet(state, packet)

    assert "emotiond.self_counterfactual" not in output.trace_payload["constraint_summary"]["reflective_self_context"]
    assert output.reflective_self_delta == {}
    assert output.revision_proposal_candidates == []


def test_developmental_reflective_context_keeps_outputs_proposal_only():
    state = ProtoSelfStateV2.empty()
    packet = _developmental_packet(
        event_id="evt_reflect_ctx_dev_001",
        runtime_summary={
            "reflective_self_context": {
                "schema_version": "mvp15-owner-v1",
                "owner_revision": 7,
                "last_revision_id": "reflective_rev_000007",
                "reflection_pressure": 0.58,
                "pending_reflections": 1,
                "unresolved_items": 1,
                "proposal_candidates": 1,
                "top_target_ids": ["trajectory:drift"],
            }
        },
    )

    output = process_update_packet(state, packet)

    assert output.reflection_writeback_candidate is not None
    assert output.reflection_writeback_candidate["proposal_discipline"] == "proposal_only"
    assert output.trace_payload["reflection_context"]["owner_revision"] == 7
    assert output.confidence_meta["reflective_self_context_present"] is True
