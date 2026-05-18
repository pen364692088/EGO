from openemotion.social_self import (
    BoundaryMode,
    CommitmentStatus,
    FORMAL_OWNER_SCHEMA_VERSION,
    FORBIDDEN_REQUESTED_EFFECTS,
    PHASE1_ALLOWED_PROOF_LEVERS,
    PHASE1_AUTHORITATIVE_FIELDS,
    PHASE1_LEGACY_REFERENCE_ONLY_FIELDS,
    RUNTIME_LOCAL_PROJECTION_FIELD,
    RUNTIME_LOCAL_PROJECTION_SEMANTICS,
    RepairProposalStatus,
    SocialSelfOwner,
    SocialSelfState,
    SocialSelfStore,
    replay_state_from_revisions,
    reset_social_self_owner,
    validate_social_state,
)


def test_social_owner_payload_matches_authoritative_fields():
    payload = SocialSelfState().model_dump(mode="json")

    assert tuple(payload.keys()) == PHASE1_AUTHORITATIVE_FIELDS
    assert payload["schema_version"] == FORMAL_OWNER_SCHEMA_VERSION


def test_runtime_projection_is_bounded():
    state = SocialSelfState()
    projection = state.to_runtime_projection()

    assert set(projection.keys()) == {
        "schema_version",
        "owner_revision",
        "last_revision_id",
        "active_relations_count",
        "trust_signal_max",
        "open_commitment_count",
        "breached_commitment_count",
        "pending_repair_count",
        "boundary_caution_max",
        "recent_counterpart_ids",
    }
    assert "trust_state" not in projection
    assert "commitment_state" not in projection
    assert "repair_state" not in projection
    assert "other_model_state" not in projection
    assert RUNTIME_LOCAL_PROJECTION_FIELD == "proto_self_v2.state.social_self"
    assert "runtime-local bounded projection" in RUNTIME_LOCAL_PROJECTION_SEMANTICS


def test_governance_rejects_behavioral_authority_and_forbidden_effects():
    state = SocialSelfState()
    state.repair_state["repair_1"] = {
        "proposal_id": "repair_1",
        "counterpart_id": "telegram:user",
        "issue_summary": "attempt direct outreach",
        "proposed_adjustment": {"tone": "warmer"},
        "justification": "invalid for owner contract",
        "required_gate": "social_writeback_gate",
        "behavioral_authority": "reply",
        "requested_effects": [FORBIDDEN_REQUESTED_EFFECTS[0]],
        "status": "proposed",
    }

    verdict = validate_social_state(state)

    assert not verdict.accepted
    assert "invalid_behavioral_authority:repair_1:reply" in verdict.violations
    assert f"forbidden_repair_effect:repair_1:{FORBIDDEN_REQUESTED_EFFECTS[0]}" in verdict.violations


def test_store_roundtrip_and_replay(tmp_path):
    reset_social_self_owner()
    owner = SocialSelfOwner(store=SocialSelfStore(tmp_path))
    owner.upsert_relation_memory(
        counterpart_id="telegram:8420019401",
        relationship_summary="long-running collaborator relationship",
        source_refs=["trace:relation"],
    )
    owner.upsert_other_model(
        counterpart_id="telegram:8420019401",
        inferred_preferences={"pace": "direct", "tone": "calm"},
        inferred_constraints=["avoid_overclaim"],
        confidence=0.74,
        source_refs=["trace:other_model"],
    )
    owner.set_trust_state(
        counterpart_id="telegram:8420019401",
        trust_level=0.67,
        trust_basis=["consistent follow-through"],
        trust_delta=0.12,
    )
    owner.record_commitment(
        counterpart_id="telegram:8420019401",
        summary="keep claims bounded and auditable",
        status=CommitmentStatus.OPEN,
        due_hint="current_phase",
        source_refs=["trace:commitment"],
    )
    proposal = owner.propose_repair(
        counterpart_id="telegram:8420019401",
        issue_summary="repair trust after an over-strong claim",
        proposed_adjustment={"social_policy_hint": "clarify_and_repair"},
        justification="preserve relationship continuity under bounded repair",
        source_refs=["trace:repair"],
    )
    owner.set_repair_status(proposal.proposal_id, status=RepairProposalStatus.APPROVED_FOR_REVIEW)
    owner.set_social_boundary(
        counterpart_id="telegram:8420019401",
        caution_level=0.58,
        boundary_mode=BoundaryMode.CAUTIOUS,
        reason="keep certainty bounded",
        source_refs=["trace:boundary"],
    )

    record = owner.persist(update_source="test_roundtrip", trace_reference="test:social")
    loaded = owner.store.load()
    revisions = owner.store.load_revision_log()
    replayed = replay_state_from_revisions(revisions)

    assert record.revision_id == "social_rev_000001"
    assert loaded is not None
    assert loaded.last_revision_id == record.revision_id
    assert replayed is not None
    assert replayed.last_revision_id == record.revision_id
    assert replayed.owner_revision == 1
    assert replayed.identity_handle == "openemotion"
    assert replayed.governance_ledger


def test_owner_records_social_summary_and_health():
    reset_social_self_owner()
    owner = SocialSelfOwner()
    owner.upsert_relation_memory(
        counterpart_id="telegram:8420019401",
        relationship_summary="stable collaborative relation",
    )
    owner.set_trust_state(
        counterpart_id="telegram:8420019401",
        trust_level=0.71,
        trust_basis=["consistent review quality"],
    )
    owner.record_commitment(
        counterpart_id="telegram:8420019401",
        summary="keep authority boundaries explicit",
        status=CommitmentStatus.BREACHED,
    )
    owner.propose_repair(
        counterpart_id="telegram:8420019401",
        issue_summary="repair after commitment breach",
        proposed_adjustment={"repair_bias": 0.4},
        justification="restore bounded trust after breach",
    )
    owner.set_social_boundary(
        counterpart_id="telegram:8420019401",
        caution_level=0.63,
        boundary_mode=BoundaryMode.FIRM,
        reason="prevent repeat overclaim",
    )

    summary = owner.get_summary()
    health = owner.check_health()

    assert summary["relation_count"] == 1
    assert summary["trust_count"] == 1
    assert summary["commitment_count"] == 1
    assert summary["pending_repair_count"] == 1
    assert "summary" in health
    assert "issues" in health
    assert "breached_commitment_present" in health["issues"]


def test_legacy_reference_only_fields_are_excluded_from_owner_payload_and_proof_surface():
    payload = SocialSelfState().model_dump(mode="json")

    for field in PHASE1_LEGACY_REFERENCE_ONLY_FIELDS:
        assert field not in payload
        assert field not in PHASE1_ALLOWED_PROOF_LEVERS
