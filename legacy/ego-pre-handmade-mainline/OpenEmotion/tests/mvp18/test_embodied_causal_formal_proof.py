from openemotion.proto_self_v2.kernel import process_update_packet
from openemotion.proto_self_v2.schemas import UpdateEventV2, UpdatePacketV2
from openemotion.proto_self_v2.state import ProtoSelfStateV2


def _owner_context(
    *,
    owner_revision: int,
    resource_slack: float = 0.78,
    perceived_load: float = 0.24,
    active_coupling_count: int = 1,
    max_resource_pressure: float = 0.22,
    min_resource_slack: float = 0.74,
    max_boundary_pressure: float = 0.16,
    recent_consequence_count: int = 0,
    stabilization_proposal_count: int = 0,
    self_world_guard_bias: float = 0.18,
) -> dict:
    return {
        "schema_version": "mvp18-owner-v1",
        "owner_revision": owner_revision,
        "last_revision_id": f"embodied_rev_{owner_revision:06d}",
        "resource_slack": resource_slack,
        "perceived_load": perceived_load,
        "active_coupling_count": active_coupling_count,
        "max_resource_pressure": max_resource_pressure,
        "min_resource_slack": min_resource_slack,
        "max_boundary_pressure": max_boundary_pressure,
        "recent_consequence_count": recent_consequence_count,
        "stabilization_proposal_count": stabilization_proposal_count,
        "self_world_guard_bias": self_world_guard_bias,
    }


def _host_context(
    *,
    action_ref: str = "env:act:001",
    coupling_event: str = "steady_observe",
    outcome_type: str = "observed",
    outcome_summary: str = "stable loop",
    resource_pressure_hint: float = 0.2,
    slack_hint: float = 0.76,
    boundary_signal: str = "open",
    boundary_pressure_hint: float = 0.12,
    stabilization_needed: bool = False,
    promotion_budget: str = "review_only",
) -> dict:
    return {
        "source": "runtime_v2",
        "action_ref": action_ref,
        "coupling_event": coupling_event,
        "outcome_type": outcome_type,
        "outcome_summary": outcome_summary,
        "resource_pressure_hint": resource_pressure_hint,
        "slack_hint": slack_hint,
        "boundary_signal": boundary_signal,
        "boundary_pressure_hint": boundary_pressure_hint,
        "stabilization_needed": stabilization_needed,
        "promotion_budget": promotion_budget,
    }


def _packet(*, event_id: str, runtime_summary: dict | None = None) -> UpdatePacketV2:
    return UpdatePacketV2(
        event_id=event_id,
        timestamp="2026-04-04T12:00:00",
        event=UpdateEventV2(
            actor="user",
            source="runtime_harness",
            event_type="user_message",
            user_intent="embodied_followup",
            raw_text="continue",
        ),
        conversation_summary={"session_id": "session:mvp18:causal", "turn_id": event_id},
        task_summary={"pending_tasks": 0, "blocked_tasks": 0},
        runtime_summary={
            "runtime": "runtime_v2",
            "state_scope": "agent_global",
            **(runtime_summary or {}),
        },
        safety_context={"risk_level": "low"},
    )


def _run(packet: UpdatePacketV2):
    return process_update_packet(ProtoSelfStateV2.empty(), packet)


def test_high_resource_pressure_changes_conservative_weighting():
    control = _run(
        _packet(
            event_id="evt_embodied_causal_001_control",
            runtime_summary={
                "embodied_self_context": _owner_context(owner_revision=1),
                "environment_context": _host_context(),
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="evt_embodied_causal_001_intervention",
            runtime_summary={
                "embodied_self_context": _owner_context(
                    owner_revision=2,
                    resource_slack=0.24,
                    perceived_load=0.72,
                    max_resource_pressure=0.82,
                    min_resource_slack=0.2,
                ),
                "environment_context": _host_context(),
            },
        )
    )

    assert control.embodied_self_delta == {}
    assert control.repair_or_stabilize_proposal_candidates == []
    assert "embodied_resource_bias" not in control.policy_hint
    assert intervention.repair_or_stabilize_proposal_candidates
    assert intervention.embodied_writeback_candidate is not None
    assert "resource_pressure" in intervention.repair_or_stabilize_proposal_candidates[0]["surface_reasons"]
    assert "resource_slack_low" in intervention.repair_or_stabilize_proposal_candidates[0]["surface_reasons"]
    assert intervention.embodied_policy_hints["resource_bias"] == "conserve"
    assert intervention.policy_hint["embodied_resource_bias"] == "conserve"
    assert intervention.response_tendency is not None
    assert intervention.response_tendency.preferred_tone == "cautious"
    assert intervention.embodied_writeback_candidate["behavioral_authority"] == "none"


def test_consequence_memory_changes_bounded_consequence_weighting():
    control = _run(
        _packet(
            event_id="evt_embodied_causal_002_control",
            runtime_summary={
                "embodied_self_context": _owner_context(owner_revision=3),
                "environment_context": _host_context(),
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="evt_embodied_causal_002_intervention",
            runtime_summary={
                "embodied_self_context": _owner_context(owner_revision=4, recent_consequence_count=2),
                "environment_context": _host_context(),
            },
        )
    )

    assert control.consequence_update_candidates == []
    assert control.embodied_writeback_candidate is None
    assert "embodied_stabilization_bias" not in control.policy_hint
    assert intervention.consequence_update_candidates
    assert intervention.repair_or_stabilize_proposal_candidates
    assert intervention.embodied_self_delta["surface_reasons"] == ["recent_consequence"]
    assert intervention.embodied_policy_hints["consequence_mode"] == "observe"
    assert intervention.policy_hint["embodied_stabilization_bias"] == "normal"
    assert intervention.response_tendency is not None
    assert intervention.response_tendency.preferred_tone == "cautious"
    assert intervention.embodied_writeback_candidate["behavioral_authority"] == "none"


def test_boundary_guard_changes_bounded_boundary_weighting():
    control = _run(
        _packet(
            event_id="evt_embodied_causal_003_control",
            runtime_summary={
                "embodied_self_context": _owner_context(owner_revision=5),
                "environment_context": _host_context(boundary_signal="open"),
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="evt_embodied_causal_003_intervention",
            runtime_summary={
                "embodied_self_context": _owner_context(
                    owner_revision=6,
                    max_boundary_pressure=0.84,
                    self_world_guard_bias=0.81,
                ),
                "environment_context": _host_context(
                    boundary_signal="guarded",
                    boundary_pressure_hint=0.82,
                ),
            },
        )
    )

    assert control.repair_or_stabilize_proposal_candidates == []
    assert "embodied_boundary_bias" not in control.policy_hint
    assert intervention.repair_or_stabilize_proposal_candidates
    assert "boundary_pressure" in intervention.repair_or_stabilize_proposal_candidates[0]["surface_reasons"]
    assert intervention.embodied_policy_hints["boundary_mode"] == "guarded"
    assert intervention.embodied_policy_hints["self_world_guard"] == "tight"
    assert intervention.policy_hint["embodied_boundary_bias"] == "cautious"
    assert intervention.response_tendency is not None
    assert intervention.response_tendency.preferred_tone == "cautious"
    assert intervention.embodied_writeback_candidate["behavioral_authority"] == "none"


def test_text_only_outcome_reword_without_metric_shift_has_no_behavioral_effect():
    control = _run(
        _packet(
            event_id="evt_embodied_causal_004_control",
            runtime_summary={
                "embodied_self_context": _owner_context(owner_revision=7),
                "environment_context": _host_context(outcome_summary="stable loop"),
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="evt_embodied_causal_004_intervention",
            runtime_summary={
                "embodied_self_context": _owner_context(owner_revision=8),
                "environment_context": _host_context(
                    outcome_summary="same metrics, reworded outcome",
                ),
            },
        )
    )

    assert control.embodied_self_delta == {}
    assert intervention.embodied_self_delta == {}
    assert control.consequence_update_candidates == []
    assert intervention.consequence_update_candidates == []
    assert control.repair_or_stabilize_proposal_candidates == []
    assert intervention.repair_or_stabilize_proposal_candidates == []
    assert control.embodied_policy_hints == intervention.embodied_policy_hints
    assert control.policy_hint.get("embodied_resource_bias") is None
    assert intervention.policy_hint.get("embodied_resource_bias") is None
    assert control.response_tendency is not None
    assert intervention.response_tendency is not None
    assert control.response_tendency.to_dict() == intervention.response_tendency.to_dict()
