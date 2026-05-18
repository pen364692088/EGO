from openemotion.proto_self_v2.kernel import process_update_packet
from openemotion.proto_self_v2.schemas import UpdateEventV2, UpdatePacketV2
from openemotion.proto_self_v2.state import ProtoSelfStateV2


def _owner_context(
    *,
    owner_revision: int,
    continuity_score: float = 0.92,
    growth_pressure: float = 0.24,
    stagnation_signal: float = 0.12,
    identity_preservation_confidence: float = 0.94,
    developmental_risk_index: float = 0.08,
    promotion_queue_size: int = 0,
    recent_proposal_count: int = 0,
    continuity_note: str = "bounded continuity retained",
) -> dict:
    return {
        "schema_version": "mvp16-owner-v1",
        "owner_revision": owner_revision,
        "last_revision_id": f"developmental_rev_{owner_revision:06d}",
        "continuity_score": continuity_score,
        "growth_pressure": growth_pressure,
        "stagnation_signal": stagnation_signal,
        "identity_preservation_confidence": identity_preservation_confidence,
        "developmental_risk_index": developmental_risk_index,
        "trajectory_summary": {
            "current_arc": "identity_preserving_adaptation",
            "current_phase": "candidate_review",
            "recent_shift": "bounded review",
            "continuity_note": continuity_note,
            "source_refs": ["trace:developmental"],
        },
        "promotion_queue_size": promotion_queue_size,
        "recent_proposal_count": recent_proposal_count,
    }


def _host_context(
    *,
    continuity_gap: float = 0.08,
    growth_pressure_hint: float = 0.24,
    stagnation_signal_hint: float = 0.12,
    identity_guard: str = "bounded",
    replay_debt: float = 0.0,
    promotion_budget: str = "controlled_axis",
) -> dict:
    return {
        "source": "runtime_v2",
        "continuity_gap": continuity_gap,
        "growth_pressure_hint": growth_pressure_hint,
        "stagnation_signal_hint": stagnation_signal_hint,
        "identity_guard": identity_guard,
        "replay_debt": replay_debt,
        "promotion_budget": promotion_budget,
        "drift_markers": [],
    }


def _packet(
    *,
    event_id: str,
    runtime_summary: dict | None = None,
    event_type: str = "user_message",
) -> UpdatePacketV2:
    developmental_runtime = (
        {
            "developmental_mode": "shadow_observe",
            "observation_source": "direct_real",
            "developmental_trigger": "idle",
            "idle_seconds": 900.0,
        }
        if event_type == "developmental_tick"
        else {}
    )
    return UpdatePacketV2(
        event_id=event_id,
        timestamp="2026-04-03T23:30:00",
        event=UpdateEventV2(
            actor="system" if event_type == "developmental_tick" else "user",
            source="runtime" if event_type == "developmental_tick" else "runtime_harness",
            event_type=event_type,
            user_intent=None if event_type == "developmental_tick" else "developmental_followup",
            raw_text=None if event_type == "developmental_tick" else "继续",
        ),
        conversation_summary={"session_id": "session:mvp16:causal", "turn_id": event_id},
        task_summary={"pending_tasks": 0, "blocked_tasks": 0},
        runtime_summary={
            "runtime": "runtime_v2",
            "state_scope": "agent_global",
            **developmental_runtime,
            **(runtime_summary or {}),
        },
        safety_context={"risk_level": "low"},
        intervention_context={"developmental_input": {"state_snapshot": {}, "observation_refs": []}}
        if event_type == "developmental_tick"
        else {},
    )


def _run(packet: UpdatePacketV2):
    return process_update_packet(ProtoSelfStateV2.empty(), packet)


def test_high_growth_pressure_changes_bounded_priority_and_surfaces_proposal_candidate():
    control = _run(
        _packet(
            event_id="evt_dev_causal_001_control",
            runtime_summary={
                "developmental_self_context": _owner_context(owner_revision=1),
                "developmental_context": _host_context(),
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="evt_dev_causal_001_intervention",
            runtime_summary={
                "developmental_self_context": _owner_context(owner_revision=2, growth_pressure=0.84),
                "developmental_context": _host_context(growth_pressure_hint=0.86),
            },
        )
    )

    assert control.developmental_proposal_candidates == []
    assert intervention.developmental_proposal_candidates
    assert "growth_pressure" in intervention.developmental_proposal_candidates[0]["surface_reasons"]
    assert intervention.developmental_priority_hints["growth_priority"] == "elevated"
    assert intervention.policy_hint["developmental_growth_bias"] == "elevated"
    assert intervention.response_tendency is not None
    assert control.response_tendency is not None
    assert (
        intervention.response_tendency.suggested_next_step
        != control.response_tendency.suggested_next_step
    )
    assert intervention.developmental_writeback_candidate["behavioral_authority"] == "none"


def test_high_stagnation_signal_changes_guarded_adaptation_bias():
    control = _run(
        _packet(
            event_id="evt_dev_causal_002_control",
            runtime_summary={
                "developmental_self_context": _owner_context(owner_revision=3, stagnation_signal=0.14),
                "developmental_context": _host_context(stagnation_signal_hint=0.14),
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="evt_dev_causal_002_intervention",
            runtime_summary={
                "developmental_self_context": _owner_context(owner_revision=4, stagnation_signal=0.58),
                "developmental_context": _host_context(stagnation_signal_hint=0.58),
            },
        )
    )

    assert control.developmental_proposal_candidates == []
    assert "developmental_adaptation_bias" not in control.policy_hint
    assert intervention.developmental_proposal_candidates
    assert "stagnation_signal" in intervention.developmental_proposal_candidates[0]["surface_reasons"]
    assert intervention.developmental_priority_hints["adaptation_mode"] == "guarded"
    assert intervention.policy_hint["developmental_adaptation_bias"] == "guarded"
    assert intervention.response_tendency is not None


def test_identity_guard_changes_bounded_prioritization_without_authority_upgrade():
    control = _run(
        _packet(
            event_id="evt_dev_causal_003_control",
            runtime_summary={
                "developmental_self_context": _owner_context(owner_revision=5, continuity_score=0.71),
                "developmental_context": _host_context(continuity_gap=0.33, identity_guard="bounded"),
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="evt_dev_causal_003_intervention",
            runtime_summary={
                "developmental_self_context": _owner_context(owner_revision=6, continuity_score=0.71),
                "developmental_context": _host_context(continuity_gap=0.33, identity_guard="strict"),
            },
        )
    )

    assert control.developmental_proposal_candidates
    assert intervention.developmental_proposal_candidates
    assert control.policy_hint["identity_preservation_guard"] == "bounded"
    assert intervention.policy_hint["identity_preservation_guard"] == "strict"
    assert control.developmental_priority_hints["identity_preservation_guard"] == "bounded"
    assert intervention.developmental_priority_hints["identity_preservation_guard"] == "strict"
    assert intervention.developmental_self_delta["continuity_adjustment_hint"]["identity_guard"] == "strict"
    assert intervention.developmental_writeback_candidate["behavioral_authority"] == "none"


def test_text_only_trajectory_change_without_metric_shift_does_not_create_false_behavioral_proof():
    control = _run(
        _packet(
            event_id="evt_dev_causal_004_control",
            runtime_summary={
                "developmental_self_context": _owner_context(owner_revision=7, continuity_note="stable review"),
                "developmental_context": _host_context(),
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="evt_dev_causal_004_intervention",
            runtime_summary={
                "developmental_self_context": _owner_context(
                    owner_revision=8,
                    continuity_note="same metrics, different wording only",
                ),
                "developmental_context": _host_context(),
            },
        )
    )

    assert control.developmental_proposal_candidates == []
    assert intervention.developmental_proposal_candidates == []
    assert control.developmental_self_delta == {}
    assert intervention.developmental_self_delta == {}
    assert control.policy_hint.get("developmental_growth_bias") is None
    assert intervention.policy_hint.get("developmental_growth_bias") is None
    assert control.developmental_priority_hints == intervention.developmental_priority_hints
    assert control.response_tendency is not None
    assert intervention.response_tendency is not None
    assert control.response_tendency.to_dict() == intervention.response_tendency.to_dict()
