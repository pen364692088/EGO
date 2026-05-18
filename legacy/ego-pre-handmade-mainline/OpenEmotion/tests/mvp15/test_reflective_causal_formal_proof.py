from openemotion.proto_self_v2.kernel import process_update_packet
from openemotion.proto_self_v2.schemas import UpdateEventV2, UpdatePacketV2
from openemotion.proto_self_v2.state import ProtoSelfStateV2


def _packet(*, event_id: str, runtime_summary: dict | None = None, event_type: str = "user_message") -> UpdatePacketV2:
    return UpdatePacketV2(
        event_id=event_id,
        timestamp="2026-04-03T12:00:00",
        event=UpdateEventV2(
            actor="system" if event_type == "developmental_tick" else "user",
            source="runtime" if event_type == "developmental_tick" else "telegram",
            event_type=event_type,
            user_intent=None if event_type == "developmental_tick" else "reflect",
            raw_text=None if event_type == "developmental_tick" else "继续",
        ),
        conversation_summary={"session_id": "session:test", "turn_id": f"turn:{event_id}"},
        task_summary={"pending_tasks": 0, "blocked_tasks": 0},
        runtime_summary={
            "runtime": "runtime_v2",
            "state_scope": "agent_global",
            **(
                {
                    "developmental_mode": "shadow_observe",
                    "observation_source": "direct_real",
                    "developmental_trigger": "idle",
                    "idle_seconds": 900.0,
                }
                if event_type == "developmental_tick"
                else {}
            ),
            **(runtime_summary or {}),
        },
        safety_context={"risk_level": "low"},
        intervention_context={"developmental_input": {"state_snapshot": {}, "observation_refs": []}}
        if event_type == "developmental_tick"
        else {},
    )


def _run(packet: UpdatePacketV2):
    return process_update_packet(ProtoSelfStateV2.empty(), packet)


def test_high_reflection_pressure_changes_revision_proposal_hooks():
    control = _run(
        _packet(
            event_id="evt_reflect_causal_001_control",
            runtime_summary={"reflective_self_context": {"schema_version": "mvp15-owner-v1", "owner_revision": 1}},
        )
    )
    intervention = _run(
        _packet(
            event_id="evt_reflect_causal_001_intervention",
            runtime_summary={
                "reflective_self_context": {
                    "schema_version": "mvp15-owner-v1",
                    "owner_revision": 2,
                    "reflection_pressure": 0.82,
                    "pending_reflections": 2,
                    "proposal_candidates": 1,
                    "top_target_ids": ["decision:target"],
                }
            },
        )
    )

    assert control.reflection_writeback_candidate is None
    assert intervention.reflection_writeback_candidate is not None
    assert intervention.revision_proposal_candidates[0]["proposal_discipline"] == "proposal_only"
    assert intervention.policy_hint["reflection_bias"] == "elevated"


def test_unresolved_items_change_uncertainty_bias_without_direct_authority():
    control = _run(
        _packet(
            event_id="evt_reflect_causal_002_control",
            runtime_summary={
                "reflective_self_context": {
                    "schema_version": "mvp15-owner-v1",
                    "owner_revision": 3,
                    "reflection_pressure": 0.36,
                    "pending_reflections": 1,
                    "unresolved_items": 0,
                    "proposal_candidates": 1,
                    "top_target_ids": ["trajectory:drift"],
                }
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="evt_reflect_causal_002_intervention",
            runtime_summary={
                "reflective_self_context": {
                    "schema_version": "mvp15-owner-v1",
                    "owner_revision": 4,
                    "reflection_pressure": 0.36,
                    "pending_reflections": 1,
                    "unresolved_items": 2,
                    "proposal_candidates": 1,
                    "top_target_ids": ["trajectory:drift"],
                }
            },
        )
    )

    assert "uncertainty_bias" not in control.policy_hint
    assert intervention.policy_hint["uncertainty_bias"] == "elevated"
    assert intervention.reflection_writeback_candidate["behavioral_authority"] == "none"


def test_replay_inconsistency_triggers_proposal_only_reflective_delta_on_developmental_path():
    control = _run(
        _packet(
            event_id="evt_reflect_causal_003_control",
            event_type="developmental_tick",
            runtime_summary={
                "reflective_self_context": {
                    "schema_version": "mvp15-owner-v1",
                    "owner_revision": 5,
                    "reflection_pressure": 0.1,
                    "pending_reflections": 0,
                    "unresolved_items": 0,
                    "proposal_candidates": 0,
                    "top_target_ids": [],
                },
                "maintenance_context": {},
                "recent_delivery_outcome": {"success": True, "status": "sent"},
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="evt_reflect_causal_003_intervention",
            event_type="developmental_tick",
            runtime_summary={
                "reflective_self_context": {
                    "schema_version": "mvp15-owner-v1",
                    "owner_revision": 6,
                    "reflection_pressure": 0.1,
                    "pending_reflections": 0,
                    "unresolved_items": 0,
                    "proposal_candidates": 0,
                    "top_target_ids": [],
                },
                "maintenance_context": {"replay_inconsistency": True},
                "recent_delivery_outcome": {"success": False, "status": "failed"},
            },
        )
    )

    assert control.reflective_self_delta == {}
    assert intervention.reflective_self_delta["revision_proposals"][0]["effect_scope"] == "proposal_only"
    assert intervention.reflection_writeback_candidate["behavioral_authority"] == "none"
    assert intervention.confidence_adjustment_hints["certainty_bound"] == "bounded"
