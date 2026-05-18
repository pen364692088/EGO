from openemotion.proto_self_v2.kernel import process_update_packet
from openemotion.proto_self_v2.schemas import UpdateEventV2, UpdatePacketV2
from openemotion.proto_self_v2.state import ProtoSelfStateV2


def _owner_context(
    *,
    owner_revision: int,
    trust_signal_max: float = 0.78,
    open_commitment_count: int = 1,
    breached_commitment_count: int = 0,
    pending_repair_count: int = 0,
    boundary_caution_max: float = 0.18,
    recent_counterpart_ids: list[str] | None = None,
) -> dict:
    return {
        "schema_version": "mvp17-owner-v1",
        "owner_revision": owner_revision,
        "last_revision_id": f"social_rev_{owner_revision:06d}",
        "active_relations_count": 2,
        "trust_signal_max": trust_signal_max,
        "open_commitment_count": open_commitment_count,
        "breached_commitment_count": breached_commitment_count,
        "pending_repair_count": pending_repair_count,
        "boundary_caution_max": boundary_caution_max,
        "recent_counterpart_ids": list(recent_counterpart_ids or ["telegram:8420019401"]),
    }


def _host_context(
    *,
    counterpart_id: str = "telegram:8420019401",
    relationship_event: str = "routine_followup",
    relationship_continuity: str = "stable",
    trust_drift: float = 0.0,
    commitment_event: str = "steady",
    commitment_breach: bool = False,
    repair_outcome: str = "resolved",
    unresolved_repair: bool = False,
    boundary_signal: str = "open",
    promotion_budget: str = "review_only",
) -> dict:
    return {
        "source": "runtime_v2",
        "counterpart_id": counterpart_id,
        "relationship_event": relationship_event,
        "relationship_continuity": relationship_continuity,
        "trust_drift": trust_drift,
        "commitment_event": commitment_event,
        "commitment_breach": commitment_breach,
        "repair_outcome": repair_outcome,
        "unresolved_repair": unresolved_repair,
        "boundary_signal": boundary_signal,
        "promotion_budget": promotion_budget,
    }


def _packet(*, event_id: str, runtime_summary: dict | None = None) -> UpdatePacketV2:
    return UpdatePacketV2(
        event_id=event_id,
        timestamp="2026-04-04T06:00:00",
        event=UpdateEventV2(
            actor="user",
            source="runtime_harness",
            event_type="user_message",
            user_intent="social_followup",
            raw_text="继续",
        ),
        conversation_summary={"session_id": "session:mvp17:causal", "turn_id": event_id},
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


def test_negative_trust_drift_changes_guarded_social_bias():
    control = _run(
        _packet(
            event_id="evt_social_causal_001_control",
            runtime_summary={
                "social_self_context": _owner_context(owner_revision=1),
                "social_context": _host_context(),
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="evt_social_causal_001_intervention",
            runtime_summary={
                "social_self_context": _owner_context(owner_revision=2),
                "social_context": _host_context(
                    relationship_event="trust_drop",
                    trust_drift=-0.24,
                ),
            },
        )
    )

    assert control.repair_proposal_candidates == []
    assert control.social_writeback_candidate is None
    assert "social_trust_bias" not in control.policy_hint
    assert intervention.repair_proposal_candidates
    assert intervention.social_writeback_candidate is not None
    assert "trust_drift" in intervention.repair_proposal_candidates[0]["surface_reasons"]
    assert intervention.social_policy_hints["trust_bias"] == "guarded"
    assert intervention.policy_hint["social_trust_bias"] == "guarded"
    assert intervention.social_writeback_candidate["behavioral_authority"] == "none"


def test_commitment_breach_changes_repair_bias_and_commitment_guard():
    control = _run(
        _packet(
            event_id="evt_social_causal_002_control",
            runtime_summary={
                "social_self_context": _owner_context(owner_revision=3),
                "social_context": _host_context(),
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="evt_social_causal_002_intervention",
            runtime_summary={
                "social_self_context": _owner_context(owner_revision=4, breached_commitment_count=1),
                "social_context": _host_context(
                    relationship_event="commitment_breach",
                    relationship_continuity="strained",
                    commitment_event="breach",
                    commitment_breach=True,
                    repair_outcome="pending",
                ),
            },
        )
    )

    assert control.repair_proposal_candidates == []
    assert control.social_policy_hints["commitment_guard"] == "normal"
    assert control.social_policy_hints["repair_bias"] == "normal"
    assert intervention.repair_proposal_candidates
    assert intervention.social_policy_hints["commitment_guard"] == "strict"
    assert intervention.social_policy_hints["repair_bias"] == "elevated"
    assert intervention.policy_hint["social_commitment_guard"] == "strict"
    assert intervention.policy_hint["social_repair_bias"] == "elevated"
    assert intervention.response_tendency is not None
    assert intervention.response_tendency.preferred_mode == "repair"
    assert intervention.social_writeback_candidate["behavioral_authority"] == "none"


def test_boundary_caution_changes_bounded_boundary_weighting():
    control = _run(
        _packet(
            event_id="evt_social_causal_003_control",
            runtime_summary={
                "social_self_context": _owner_context(owner_revision=5, boundary_caution_max=0.18),
                "social_context": _host_context(boundary_signal="open"),
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="evt_social_causal_003_intervention",
            runtime_summary={
                "social_self_context": _owner_context(owner_revision=6, boundary_caution_max=0.82),
                "social_context": _host_context(boundary_signal="firm"),
            },
        )
    )

    assert control.repair_proposal_candidates == []
    assert "social_boundary_bias" not in control.policy_hint
    assert intervention.repair_proposal_candidates
    assert "boundary_caution" in intervention.repair_proposal_candidates[0]["surface_reasons"]
    assert intervention.social_policy_hints["boundary_mode"] == "firm"
    assert intervention.policy_hint["social_boundary_bias"] == "cautious"
    assert intervention.response_tendency is not None
    assert intervention.response_tendency.preferred_tone == "cautious"
    assert intervention.social_writeback_candidate["behavioral_authority"] == "none"


def test_text_only_social_event_change_without_metric_shift_has_no_behavioral_effect():
    control = _run(
        _packet(
            event_id="evt_social_causal_004_control",
            runtime_summary={
                "social_self_context": _owner_context(owner_revision=7),
                "social_context": _host_context(relationship_event="routine_followup"),
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="evt_social_causal_004_intervention",
            runtime_summary={
                "social_self_context": _owner_context(owner_revision=8),
                "social_context": _host_context(
                    relationship_event="same_state_reworded_only",
                ),
            },
        )
    )

    assert control.social_self_delta == {}
    assert intervention.social_self_delta == {}
    assert control.relation_update_candidates == []
    assert intervention.relation_update_candidates == []
    assert control.repair_proposal_candidates == []
    assert intervention.repair_proposal_candidates == []
    assert control.social_policy_hints == intervention.social_policy_hints
    assert control.policy_hint.get("social_trust_bias") is None
    assert intervention.policy_hint.get("social_trust_bias") is None
    assert control.response_tendency is not None
    assert intervention.response_tendency is not None
    assert control.response_tendency.to_dict() == intervention.response_tendency.to_dict()
