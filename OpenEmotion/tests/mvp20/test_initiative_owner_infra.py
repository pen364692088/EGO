from openemotion.initiative_self import (
    CommitmentContinuityStatus,
    FORMAL_OWNER_SCHEMA_VERSION,
    FORBIDDEN_REQUESTED_EFFECTS,
    HostProactiveCandidateStatus,
    InitiativePriority,
    InitiativeProposalStatus,
    InitiativeSelfOwner,
    InitiativeSelfState,
    InitiativeSelfStore,
    PHASE1_ALLOWED_PROOF_LEVERS,
    PHASE1_AUTHORITATIVE_FIELDS,
    PHASE1_LEGACY_REFERENCE_ONLY_FIELDS,
    RUNTIME_LOCAL_PROJECTION_FIELD,
    RUNTIME_LOCAL_PROJECTION_SEMANTICS,
    replay_state_from_revisions,
    reset_initiative_self_owner,
    validate_initiative_state,
)


def test_initiative_owner_payload_matches_authoritative_fields():
    payload = InitiativeSelfState().model_dump(mode="json")

    assert tuple(payload.keys()) == PHASE1_AUTHORITATIVE_FIELDS
    assert payload["schema_version"] == FORMAL_OWNER_SCHEMA_VERSION


def test_runtime_projection_is_bounded():
    state = InitiativeSelfState()
    projection = state.to_runtime_projection()

    assert set(projection.keys()) == {
        "schema_version",
        "owner_revision",
        "last_revision_id",
        "dominant_mode",
        "initiative_pressure",
        "commitment_carryover_bias",
        "recent_delivery_sensitivity",
        "selected_priority",
        "active_commitments_count",
        "blocked_commitments_count",
        "continuity_confidence",
        "has_initiative_proposal_candidate",
        "has_host_proactive_candidate",
    }
    assert "initiative_ledger" not in projection
    assert "initiative_proposal_candidate" not in projection
    assert "host_proactive_candidate" not in projection
    assert RUNTIME_LOCAL_PROJECTION_FIELD == "proto_self_v2.state.initiative_self"
    assert "runtime-local bounded projection" in RUNTIME_LOCAL_PROJECTION_SEMANTICS


def test_governance_rejects_behavioral_authority_and_forbidden_effects():
    state = InitiativeSelfState()
    state.initiative_proposal_candidate = {
        "proposal_id": "initiative_1",
        "proposal_label": "send_now",
        "priority_mode": "schedule",
        "proposed_effects": {"host_proactive_candidate": {"mode": "send"}},
        "justification": "invalid direct execution",
        "required_gate": "initiative_writeback_gate",
        "effect_scope": "proposal_only",
        "behavioral_authority": "reply",
        "requested_effects": [FORBIDDEN_REQUESTED_EFFECTS[0]],
        "status": "proposed",
    }
    state.host_proactive_candidate = {
        "candidate_id": "host_candidate_1",
        "candidate_label": "push_outbound_now",
        "continuity_basis": "invalid direct proactive execution",
        "host_lane_hint": "host_proactive_outbox",
        "required_gate": "initiative_writeback_gate",
        "effect_scope": "proposal_only",
        "behavioral_authority": "transport",
        "requested_effects": [FORBIDDEN_REQUESTED_EFFECTS[4]],
        "status": "proposed",
    }

    verdict = validate_initiative_state(state)

    assert not verdict.accepted
    assert "invalid_behavioral_authority:initiative_1:reply" in verdict.violations
    assert f"forbidden_initiative_effect:initiative_1:{FORBIDDEN_REQUESTED_EFFECTS[0]}" in verdict.violations
    assert "invalid_host_candidate_authority:host_candidate_1:transport" in verdict.violations
    assert (
        f"forbidden_host_candidate_effect:host_candidate_1:{FORBIDDEN_REQUESTED_EFFECTS[4]}"
        in verdict.violations
    )


def test_store_roundtrip_and_replay(tmp_path):
    reset_initiative_self_owner()
    owner = InitiativeSelfOwner(store=InitiativeSelfStore(tmp_path))
    owner.set_initiative_state(
        dominant_mode=InitiativePriority.REVIEW,
        initiative_pressure=0.68,
        commitment_carryover_bias=0.74,
        recent_delivery_sensitivity=0.57,
        rationale_summary="hold direct action and preserve bounded initiative continuity",
        source_refs=["trace:initiative_state"],
    )
    owner.set_initiative_priority_state(
        selected_priority=InitiativePriority.CARRY_FORWARD,
        hold_weight=0.61,
        review_weight=0.72,
        prepare_weight=0.54,
        carry_forward_weight=0.81,
        schedule_weight=0.32,
        priority_reason="commitment continuity outranks scheduling under current pressure",
        upstream_pressure_sources=[
            "wp14:integrated_review_bias",
            "wp12:commitment_repair_context",
            "wp13:resource_boundary_snapshot",
        ],
        source_refs=["trace:priority"],
    )
    initiative = owner.propose_initiative(
        proposal_label="carry_forward_commitment_under_review",
        priority_mode=InitiativePriority.CARRY_FORWARD,
        proposed_effects={"initiative_policy_hints": ["hold", "review", "carry_forward"]},
        justification="initiative remains bounded and host-governed while commitments carry over",
        source_refs=["trace:proposal"],
    )
    owner.set_initiative_proposal_status(status=InitiativeProposalStatus.APPROVED_FOR_REVIEW)
    host_candidate = owner.set_host_proactive_candidate(
        candidate_label="host_review_candidate_after_idle_window",
        continuity_basis="bounded candidate derived from commitment continuity",
        source_refs=["trace:host_candidate"],
    )
    owner.set_host_proactive_candidate_status(status=HostProactiveCandidateStatus.HELD)
    owner.set_commitment_continuity_state(
        status=CommitmentContinuityStatus.ACTIVE,
        active_commitments_count=2,
        carried_commitment_refs=["commitment:review_chain", "commitment:bounded_followup"],
        blocked_commitment_refs=["commitment:send_now"],
        continuity_confidence=0.71,
        carryover_summary="carry forward bounded initiative while transport stays host-governed",
        source_refs=["trace:continuity"],
    )
    owner.record_initiative_event(
        event_type="initiative_snapshot_created",
        reference_id=initiative.proposal_id,
        gate_verdict="allow_review",
        details={"host_candidate_id": host_candidate.candidate_id},
    )

    record = owner.persist(update_source="test_roundtrip", trace_reference="test:initiative")
    loaded = owner.store.load()
    revisions = owner.store.load_revision_log()
    replayed = replay_state_from_revisions(revisions)

    assert record.revision_id == "initiative_rev_000001"
    assert loaded is not None
    assert loaded.last_revision_id == record.revision_id
    assert loaded.initiative_proposal_candidate is not None
    assert loaded.host_proactive_candidate is not None
    assert replayed is not None
    assert replayed.last_revision_id == record.revision_id
    assert replayed.owner_revision == 1
    assert replayed.identity_handle == "openemotion"
    assert replayed.initiative_ledger


def test_owner_records_summary_and_health():
    reset_initiative_self_owner()
    owner = InitiativeSelfOwner()
    owner.set_initiative_state(
        dominant_mode=InitiativePriority.REVIEW,
        initiative_pressure=0.63,
        commitment_carryover_bias=0.78,
        recent_delivery_sensitivity=0.42,
        rationale_summary="review-first initiative posture",
    )
    owner.set_initiative_priority_state(
        selected_priority=InitiativePriority.HOLD,
        hold_weight=0.74,
        review_weight=0.69,
        prepare_weight=0.36,
        carry_forward_weight=0.57,
        schedule_weight=0.22,
        priority_reason="hold and review dominate until commitments are reconciled",
    )
    owner.set_commitment_continuity_state(
        status=CommitmentContinuityStatus.ACTIVE,
        active_commitments_count=1,
        carried_commitment_refs=["commitment:authority_boundary"],
        blocked_commitment_refs=[],
        continuity_confidence=0.77,
        carryover_summary="keep authority boundary commitment active",
    )
    owner.propose_initiative(
        proposal_label="review_before_followup",
        priority_mode=InitiativePriority.REVIEW,
        proposed_effects={"initiative_policy_hints": ["review"]},
        justification="bounded initiative remains under host review",
    )
    owner.set_host_proactive_candidate(
        candidate_label="candidate_after_idle_window",
        continuity_basis="carried commitment with no active-task conflict",
    )

    summary = owner.get_summary()
    health = owner.check_health()

    assert summary["active_commitments_count"] == 1
    assert summary["has_initiative_proposal_candidate"] is True
    assert summary["has_host_proactive_candidate"] is True
    assert health["healthy"] is True
    assert "summary" in health
    assert "issues" in health


def test_legacy_reference_only_fields_are_excluded_from_owner_payload_and_proof_surface():
    payload = InitiativeSelfState().model_dump(mode="json")

    for field in PHASE1_LEGACY_REFERENCE_ONLY_FIELDS:
        assert field not in payload
        assert field not in PHASE1_ALLOWED_PROOF_LEVERS
