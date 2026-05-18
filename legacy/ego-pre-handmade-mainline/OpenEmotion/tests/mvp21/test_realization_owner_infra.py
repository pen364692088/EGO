from openemotion.initiative_realization import (
    CommitmentFulfillmentStatus,
    ControlledDeliveryCandidateStatus,
    FORMAL_OWNER_SCHEMA_VERSION,
    FORBIDDEN_REQUESTED_EFFECTS,
    InitiativeRealizationOwner,
    InitiativeRealizationState,
    InitiativeRealizationStore,
    PHASE1_ALLOWED_PROOF_LEVERS,
    PHASE1_AUTHORITATIVE_FIELDS,
    PHASE1_LEGACY_REFERENCE_ONLY_FIELDS,
    RUNTIME_LOCAL_PROJECTION_FIELD,
    RUNTIME_LOCAL_PROJECTION_SEMANTICS,
    RealizationMode,
    RealizationProposalStatus,
    replay_state_from_revisions,
    reset_initiative_realization_owner,
    validate_realization_state,
)


def test_realization_owner_payload_matches_authoritative_fields():
    payload = InitiativeRealizationState().model_dump(mode="json")

    assert tuple(payload.keys()) == PHASE1_AUTHORITATIVE_FIELDS
    assert payload["schema_version"] == FORMAL_OWNER_SCHEMA_VERSION


def test_runtime_projection_is_bounded():
    state = InitiativeRealizationState()
    projection = state.to_runtime_projection()

    assert set(projection.keys()) == {
        "schema_version",
        "owner_revision",
        "last_revision_id",
        "dominant_mode",
        "realization_pressure",
        "fulfillment_readiness",
        "hold_bias",
        "failure_recovery_bias",
        "selected_lane",
        "active_commitments_count",
        "ready_commitments_count",
        "continuity_confidence",
        "has_realization_candidate",
        "has_controlled_delivery_candidate",
    }
    assert "realization_ledger" not in projection
    assert "initiative_realization_candidate" not in projection
    assert "controlled_delivery_candidate" not in projection
    assert RUNTIME_LOCAL_PROJECTION_FIELD == "proto_self_v2.state.initiative_realization"
    assert "runtime-local bounded projection" in RUNTIME_LOCAL_PROJECTION_SEMANTICS


def test_governance_rejects_behavioral_authority_and_forbidden_effects():
    state = InitiativeRealizationState()
    state.initiative_realization_candidate = {
        "candidate_id": "realization_1",
        "candidate_label": "deliver_now",
        "selected_mode": "fulfill",
        "proposed_effects": {"controlled_delivery_candidate": {"mode": "send"}},
        "justification": "invalid direct execution",
        "required_gate": "initiative_realization_writeback_gate",
        "effect_scope": "proposal_only",
        "behavioral_authority": "reply",
        "requested_effects": [FORBIDDEN_REQUESTED_EFFECTS[0]],
        "status": "proposed",
    }
    state.controlled_delivery_candidate = {
        "candidate_id": "delivery_candidate_1",
        "candidate_label": "push_outbound_now",
        "readiness_basis": "invalid direct delivery execution",
        "delivery_readiness": 0.91,
        "host_lane_hint": "host_proactive_outbox",
        "required_gate": "initiative_realization_writeback_gate",
        "effect_scope": "proposal_only",
        "behavioral_authority": "transport",
        "requested_effects": [FORBIDDEN_REQUESTED_EFFECTS[4]],
        "status": "proposed",
    }

    verdict = validate_realization_state(state)

    assert not verdict.accepted
    assert "invalid_behavioral_authority:realization_1:reply" in verdict.violations
    assert f"forbidden_realization_effect:realization_1:{FORBIDDEN_REQUESTED_EFFECTS[0]}" in verdict.violations
    assert "invalid_delivery_candidate_authority:delivery_candidate_1:transport" in verdict.violations
    assert (
        f"forbidden_delivery_candidate_effect:delivery_candidate_1:{FORBIDDEN_REQUESTED_EFFECTS[4]}"
        in verdict.violations
    )


def test_store_roundtrip_and_replay(tmp_path):
    reset_initiative_realization_owner()
    owner = InitiativeRealizationOwner(store=InitiativeRealizationStore(tmp_path))
    owner.set_realization_state(
        dominant_mode=RealizationMode.REVIEW,
        realization_pressure=0.68,
        fulfillment_readiness=0.74,
        hold_bias=0.57,
        failure_recovery_bias=0.61,
        rationale_summary="hold direct delivery and preserve bounded realization continuity",
        source_refs=["trace:realization_state"],
    )
    owner.set_delivery_readiness_state(
        selected_lane=RealizationMode.PREPARE,
        hold_weight=0.61,
        review_weight=0.72,
        prepare_weight=0.81,
        mediate_weight=0.54,
        fulfill_weight=0.32,
        lane_reason="prepare controlled delivery after review and readiness checks",
        host_lane_hints=[
            "host_review_queue",
            "host_proactive_outbox",
        ],
        source_refs=["trace:readiness"],
    )
    realization = owner.propose_realization(
        candidate_label="prepare_controlled_delivery_after_review",
        selected_mode=RealizationMode.PREPARE,
        proposed_effects={"host_lane_hints": ["hold", "review", "prepare"]},
        justification="initiative realization remains bounded and host-governed while readiness is established",
        source_refs=["trace:proposal"],
    )
    owner.set_initiative_realization_candidate_status(
        status=RealizationProposalStatus.APPROVED_FOR_REVIEW
    )
    delivery = owner.set_controlled_delivery_candidate(
        candidate_label="host_lane_candidate_after_idle_window",
        readiness_basis="bounded candidate derived from readiness and review posture",
        delivery_readiness=0.71,
        source_refs=["trace:delivery_candidate"],
    )
    owner.set_controlled_delivery_candidate_status(
        status=ControlledDeliveryCandidateStatus.HELD
    )
    owner.set_commitment_fulfillment_state(
        status=CommitmentFulfillmentStatus.READY,
        active_commitments_count=2,
        ready_commitments_count=1,
        realized_commitment_refs=["commitment:bounded_review_chain"],
        blocked_commitment_refs=["commitment:send_now"],
        continuity_confidence=0.71,
        fulfillment_summary="keep realization host-governed while readiness remains bounded",
        source_refs=["trace:fulfillment"],
    )
    owner.record_realization_event(
        event_type="realization_snapshot_created",
        reference_id=realization.candidate_id,
        gate_verdict="allow_review",
        details={"delivery_candidate_id": delivery.candidate_id},
    )

    record = owner.persist(update_source="test_roundtrip", trace_reference="test:realization")
    loaded = owner.store.load()
    revisions = owner.store.load_revision_log()
    replayed = replay_state_from_revisions(revisions)

    assert record.revision_id == "realization_rev_000001"
    assert loaded is not None
    assert loaded.last_revision_id == record.revision_id
    assert loaded.initiative_realization_candidate is not None
    assert loaded.controlled_delivery_candidate is not None
    assert replayed is not None
    assert replayed.last_revision_id == record.revision_id
    assert replayed.owner_revision == 1
    assert replayed.identity_handle == "openemotion"
    assert replayed.realization_ledger


def test_owner_records_summary_and_health():
    reset_initiative_realization_owner()
    owner = InitiativeRealizationOwner()
    owner.set_realization_state(
        dominant_mode=RealizationMode.REVIEW,
        realization_pressure=0.63,
        fulfillment_readiness=0.58,
        hold_bias=0.78,
        failure_recovery_bias=0.42,
        rationale_summary="review-first realization posture",
    )
    owner.set_delivery_readiness_state(
        selected_lane=RealizationMode.HOLD,
        hold_weight=0.74,
        review_weight=0.69,
        prepare_weight=0.36,
        mediate_weight=0.57,
        fulfill_weight=0.22,
        lane_reason="hold and review dominate until delivery readiness is reconciled",
        host_lane_hints=["host_review_queue"],
    )
    owner.set_commitment_fulfillment_state(
        status=CommitmentFulfillmentStatus.ACTIVE,
        active_commitments_count=1,
        ready_commitments_count=1,
        realized_commitment_refs=["commitment:authority_boundary"],
        blocked_commitment_refs=[],
        continuity_confidence=0.77,
        fulfillment_summary="keep authority boundary commitment active",
    )
    owner.propose_realization(
        candidate_label="review_before_delivery",
        selected_mode=RealizationMode.REVIEW,
        proposed_effects={"integrated_policy_hints": ["review"]},
        justification="bounded realization remains under host review",
    )
    owner.set_controlled_delivery_candidate(
        candidate_label="candidate_after_idle_window",
        readiness_basis="carried commitment with no active-task conflict",
        delivery_readiness=0.66,
    )

    summary = owner.get_summary()
    health = owner.check_health()

    assert summary["active_commitments_count"] == 1
    assert summary["ready_commitments_count"] == 1
    assert summary["has_realization_candidate"] is True
    assert summary["has_controlled_delivery_candidate"] is True
    assert health["healthy"] is True
    assert "summary" in health
    assert "issues" in health


def test_legacy_reference_only_fields_are_excluded_from_owner_payload_and_proof_surface():
    payload = InitiativeRealizationState().model_dump(mode="json")

    for field in PHASE1_LEGACY_REFERENCE_ONLY_FIELDS:
        assert field not in payload
        assert field not in PHASE1_ALLOWED_PROOF_LEVERS
