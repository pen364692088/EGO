from openemotion.developmental_self import (
    FORMAL_OWNER_SCHEMA_VERSION,
    FORBIDDEN_REQUESTED_EFFECTS,
    PHASE1_ALLOWED_PROOF_LEVERS,
    PHASE1_AUTHORITATIVE_FIELDS,
    PHASE1_LEGACY_REFERENCE_ONLY_FIELDS,
    RUNTIME_LOCAL_PROJECTION_FIELD,
    RUNTIME_LOCAL_PROJECTION_SEMANTICS,
    ContinuityMarkerType,
    DevelopmentalSelfOwner,
    DevelopmentalSelfState,
    DevelopmentalSelfStore,
    PromotionLevel,
    replay_state_from_revisions,
    reset_developmental_self_owner,
    validate_developmental_state,
)


def test_developmental_owner_payload_matches_authoritative_fields():
    payload = DevelopmentalSelfState().model_dump(mode="json")

    assert tuple(payload.keys()) == PHASE1_AUTHORITATIVE_FIELDS
    assert payload["schema_version"] == FORMAL_OWNER_SCHEMA_VERSION


def test_runtime_projection_is_bounded():
    state = DevelopmentalSelfState()
    projection = state.to_runtime_projection()

    assert set(projection.keys()) == {
        "schema_version",
        "owner_revision",
        "last_revision_id",
        "continuity_score",
        "growth_pressure",
        "stagnation_signal",
        "identity_preservation_confidence",
        "developmental_risk_index",
        "trajectory_summary",
        "promotion_queue_size",
        "recent_proposal_count",
    }
    assert "proposal_history" not in projection
    assert "governance_ledger" not in projection
    assert "continuity_markers" not in projection
    assert RUNTIME_LOCAL_PROJECTION_FIELD == "proto_self_v2.state.developmental_self"
    assert "runtime-local bounded projection" in RUNTIME_LOCAL_PROJECTION_SEMANTICS


def test_governance_rejects_behavioral_authority_and_forbidden_effects():
    state = DevelopmentalSelfState()
    state.proposal_history["proposal_1"] = {
        "proposal_id": "proposal_1",
        "proposal_kind": "trajectory_adjustment",
        "summary": "over-broad direct rewrite",
        "proposed_adjustment": {"continuity": "override"},
        "justification": "invalid for owner contract",
        "behavioral_authority": "reply",
        "requested_effects": [FORBIDDEN_REQUESTED_EFFECTS[0]],
    }

    verdict = validate_developmental_state(state)

    assert not verdict.accepted
    assert "invalid_behavioral_authority:proposal_1:reply" in verdict.violations
    assert f"forbidden_proposal_effect:proposal_1:{FORBIDDEN_REQUESTED_EFFECTS[0]}" in verdict.violations


def test_store_roundtrip_and_replay(tmp_path):
    reset_developmental_self_owner()
    owner = DevelopmentalSelfOwner(store=DevelopmentalSelfStore(tmp_path))
    owner.set_identity_anchor(
        anchor_summary="self-model anchored continuity",
        invariant_refs=["self_model:identity"],
        confidence=0.92,
    )
    owner.set_trajectory_summary(
        current_arc="governed_growth",
        current_phase="observation",
        recent_shift="promotion queue opened",
        continuity_note="bounded continuity retained",
        source_refs=["trace:trajectory"],
    )
    owner.set_continuity_metrics(
        continuity_score=0.83,
        growth_pressure=0.61,
        stagnation_signal=0.22,
        identity_preservation_confidence=0.95,
    )
    proposal = owner.add_proposal(
        proposal_kind="continuity_gap",
        summary="stabilize developmental pressure",
        proposed_adjustment={"priority_hint": "continue_review"},
        justification="maintain identity-preserving continuity",
        source_refs=["trace:proposal"],
        promotion_level=PromotionLevel.REVIEW_ONLY,
    )
    owner.queue_promotion(
        source_proposal_id=proposal.proposal_id,
        summary="review continuity adjustment",
        promotion_level=PromotionLevel.REVIEW_ONLY,
    )
    owner.add_continuity_marker(
        marker_type=ContinuityMarkerType.IDENTITY_ANCHOR,
        reference="self_model:identity",
        continuity_weight=0.9,
        note="stable anchor retained",
    )

    record = owner.persist(update_source="test_roundtrip", trace_reference="test:developmental")
    loaded = owner.store.load()
    revisions = owner.store.load_revision_log()
    replayed = replay_state_from_revisions(revisions)

    assert record.revision_id == "developmental_rev_000001"
    assert loaded is not None
    assert loaded.last_revision_id == record.revision_id
    assert replayed is not None
    assert replayed.last_revision_id == record.revision_id
    assert replayed.owner_revision == 1
    assert replayed.identity_handle == "openemotion"
    assert replayed.governance_ledger


def test_owner_records_continuity_summary_and_health():
    reset_developmental_self_owner()
    owner = DevelopmentalSelfOwner()
    owner.set_continuity_metrics(
        continuity_score=0.78,
        growth_pressure=0.66,
        stagnation_signal=0.18,
        identity_preservation_confidence=0.88,
    )
    owner.set_trajectory_summary(
        current_arc="identity_preserving_adaptation",
        current_phase="candidate_review",
        continuity_note="risk remains bounded",
    )
    proposal = owner.add_proposal(
        proposal_kind="stagnation_reduction",
        summary="reduce stagnation through guarded adaptation",
        proposed_adjustment={"maintenance_priority": 0.4},
        justification="keep continuity while lowering stagnation",
    )
    owner.queue_promotion(source_proposal_id=proposal.proposal_id, summary="review guarded adaptation")
    owner.add_continuity_marker(
        marker_type=ContinuityMarkerType.GROWTH_SIGNAL,
        reference="drive:completion_pressure",
        continuity_weight=0.7,
        note="growth pressure present",
    )

    summary = owner.get_summary()
    health = owner.check_health()

    assert summary["proposal_count"] == 1
    assert summary["promotion_queue_size"] == 1
    assert summary["continuity_marker_count"] == 1
    assert "summary" in health
    assert "issues" in health


def test_legacy_reference_only_fields_are_excluded_from_owner_payload_and_proof_surface():
    payload = DevelopmentalSelfState().model_dump(mode="json")

    for field in PHASE1_LEGACY_REFERENCE_ONLY_FIELDS:
        assert field not in payload
        assert field not in PHASE1_ALLOWED_PROOF_LEVERS
