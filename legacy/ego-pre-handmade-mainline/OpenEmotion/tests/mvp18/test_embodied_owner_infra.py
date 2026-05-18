from openemotion.embodied_self import (
    BoundaryPressureMode,
    EmbodiedProposalStatus,
    EmbodiedSelfOwner,
    EmbodiedSelfState,
    EmbodiedSelfStore,
    FORMAL_OWNER_SCHEMA_VERSION,
    FORBIDDEN_REQUESTED_EFFECTS,
    PHASE1_ALLOWED_PROOF_LEVERS,
    PHASE1_AUTHORITATIVE_FIELDS,
    PHASE1_LEGACY_REFERENCE_ONLY_FIELDS,
    RUNTIME_LOCAL_PROJECTION_FIELD,
    RUNTIME_LOCAL_PROJECTION_SEMANTICS,
    replay_state_from_revisions,
    reset_embodied_self_owner,
    validate_embodied_state,
)


def test_embodied_owner_payload_matches_authoritative_fields():
    payload = EmbodiedSelfState().model_dump(mode="json")

    assert tuple(payload.keys()) == PHASE1_AUTHORITATIVE_FIELDS
    assert payload["schema_version"] == FORMAL_OWNER_SCHEMA_VERSION


def test_runtime_projection_is_bounded():
    state = EmbodiedSelfState()
    projection = state.to_runtime_projection()

    assert set(projection.keys()) == {
        "schema_version",
        "owner_revision",
        "last_revision_id",
        "resource_slack",
        "perceived_load",
        "active_coupling_count",
        "max_resource_pressure",
        "min_resource_slack",
        "max_boundary_pressure",
        "recent_consequence_count",
        "stabilization_proposal_count",
        "self_world_guard_bias",
    }
    assert "environment_coupling_state" not in projection
    assert "resource_pressure_state" not in projection
    assert "boundary_pressure_state" not in projection
    assert "action_consequence_memory" not in projection
    assert RUNTIME_LOCAL_PROJECTION_FIELD == "proto_self_v2.state.embodied_self"
    assert "runtime-local bounded projection" in RUNTIME_LOCAL_PROJECTION_SEMANTICS


def test_governance_rejects_behavioral_authority_and_forbidden_effects():
    state = EmbodiedSelfState()
    state.proposal_history["proposal_1"] = {
        "proposal_id": "proposal_1",
        "target_ref": "environment:self_world",
        "issue_summary": "attempt direct environment control",
        "proposed_adjustment": {"repair_bias": 0.2},
        "justification": "invalid for owner contract",
        "required_gate": "embodied_writeback_gate",
        "behavioral_authority": "tool",
        "requested_effects": [FORBIDDEN_REQUESTED_EFFECTS[0]],
        "status": "proposed",
    }

    verdict = validate_embodied_state(state)

    assert not verdict.accepted
    assert "invalid_behavioral_authority:proposal_1:tool" in verdict.violations
    assert f"forbidden_embodied_effect:proposal_1:{FORBIDDEN_REQUESTED_EFFECTS[0]}" in verdict.violations


def test_store_roundtrip_and_replay(tmp_path):
    reset_embodied_self_owner()
    owner = EmbodiedSelfOwner(store=EmbodiedSelfStore(tmp_path))
    owner.set_embodied_state(
        resource_slack=0.42,
        perceived_load=0.73,
        action_readiness=0.38,
        source_refs=["trace:embodied"],
    )
    owner.upsert_environment_coupling(
        coupling_id="runtime:chat_loop",
        coupling_strength=0.64,
        controllability_estimate=0.51,
        recent_outcome_summary="bounded action consequence retained",
        source_refs=["trace:coupling"],
    )
    owner.set_resource_pressure(
        pressure_id="resource:slack",
        pressure_level=0.68,
        slack_level=0.32,
        recovery_bias=0.41,
        source_refs=["trace:resource"],
    )
    owner.set_boundary_pressure(
        boundary_id="self_world",
        pressure_level=0.57,
        mode=BoundaryPressureMode.GUARDED,
        reason="preserve self/world separation under load",
        source_refs=["trace:boundary"],
    )
    owner.record_action_consequence(
        action_ref="runtime:delivery_attempt",
        outcome_type="delivery_failure",
        consequence_summary="resource pressure increased after failed attempt",
        impact_score=0.61,
        controllability_estimate=0.48,
        source_refs=["trace:consequence"],
    )
    proposal = owner.propose_stabilization(
        target_ref="resource:slack",
        issue_summary="stabilize resource pressure after failed action",
        proposed_adjustment={"embodied_policy_hint": "repair_or_stabilize"},
        justification="keep embodied loop bounded and recoverable",
        source_refs=["trace:proposal"],
    )
    owner.set_proposal_status(proposal.proposal_id, status=EmbodiedProposalStatus.APPROVED_FOR_REVIEW)
    owner.set_self_world_boundary_semantics(
        distinction_summary="bounded self world separation under governed environment coupling",
        guard_bias=0.66,
        repair_bias=0.53,
        source_refs=["trace:self_world"],
    )

    record = owner.persist(update_source="test_roundtrip", trace_reference="test:embodied")
    loaded = owner.store.load()
    revisions = owner.store.load_revision_log()
    replayed = replay_state_from_revisions(revisions)

    assert record.revision_id == "embodied_rev_000001"
    assert loaded is not None
    assert loaded.last_revision_id == record.revision_id
    assert replayed is not None
    assert replayed.last_revision_id == record.revision_id
    assert replayed.owner_revision == 1
    assert replayed.identity_handle == "openemotion"
    assert replayed.governance_ledger


def test_owner_records_summary_and_health():
    reset_embodied_self_owner()
    owner = EmbodiedSelfOwner()
    owner.set_embodied_state(
        resource_slack=0.35,
        perceived_load=0.76,
        action_readiness=0.29,
    )
    owner.upsert_environment_coupling(
        coupling_id="runtime:chat_loop",
        coupling_strength=0.71,
        controllability_estimate=0.49,
        recent_outcome_summary="delivery outcomes remain bounded",
    )
    owner.set_resource_pressure(
        pressure_id="resource:slack",
        pressure_level=0.84,
        slack_level=0.16,
        recovery_bias=0.55,
    )
    owner.set_boundary_pressure(
        boundary_id="self_world",
        pressure_level=0.82,
        mode=BoundaryPressureMode.REPAIR_ONLY,
        reason="high boundary pressure requires repair-only posture",
    )
    owner.record_action_consequence(
        action_ref="runtime:delivery_attempt",
        outcome_type="delivery_timeout",
        consequence_summary="timeout elevated embodied pressure",
        impact_score=0.73,
    )
    owner.propose_stabilization(
        target_ref="boundary:self_world",
        issue_summary="stabilize self/world boundary after timeout",
        proposed_adjustment={"repair_or_stabilize": True},
        justification="reduce boundary pressure under bounded repair",
    )

    summary = owner.get_summary()
    health = owner.check_health()

    assert summary["coupling_count"] == 1
    assert summary["resource_pressure_count"] == 1
    assert summary["boundary_pressure_count"] == 1
    assert summary["consequence_count"] == 1
    assert summary["stabilization_proposal_count"] == 1
    assert "summary" in health
    assert "issues" in health
    assert "resource_pressure_elevated" in health["issues"]
    assert "boundary_pressure_elevated" in health["issues"]


def test_legacy_reference_only_fields_are_excluded_from_owner_payload_and_proof_surface():
    payload = EmbodiedSelfState().model_dump(mode="json")

    for field in PHASE1_LEGACY_REFERENCE_ONLY_FIELDS:
        assert field not in payload
        assert field not in PHASE1_ALLOWED_PROOF_LEVERS
