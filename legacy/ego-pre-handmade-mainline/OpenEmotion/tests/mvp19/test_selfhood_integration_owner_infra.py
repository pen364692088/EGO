from openemotion.selfhood_integration import (
    ArbitrationPriority,
    ConflictSeverity,
    FORMAL_OWNER_SCHEMA_VERSION,
    FORBIDDEN_REQUESTED_EFFECTS,
    IntegratedProposalStatus,
    PHASE1_ALLOWED_PROOF_LEVERS,
    PHASE1_AUTHORITATIVE_FIELDS,
    PHASE1_LEGACY_REFERENCE_ONLY_FIELDS,
    RUNTIME_LOCAL_PROJECTION_FIELD,
    RUNTIME_LOCAL_PROJECTION_SEMANTICS,
    SelfhoodIntegrationOwner,
    SelfhoodIntegrationState,
    SelfhoodIntegrationStore,
    replay_state_from_revisions,
    reset_selfhood_integration_owner,
    validate_selfhood_integration_state,
)


def test_selfhood_integration_payload_matches_authoritative_fields():
    payload = SelfhoodIntegrationState().model_dump(mode="json")

    assert tuple(payload.keys()) == PHASE1_AUTHORITATIVE_FIELDS
    assert payload["schema_version"] == FORMAL_OWNER_SCHEMA_VERSION


def test_runtime_projection_is_bounded():
    state = SelfhoodIntegrationState()
    projection = state.to_runtime_projection()

    assert set(projection.keys()) == {
        "schema_version",
        "owner_revision",
        "last_revision_id",
        "policy_mode",
        "integration_posture",
        "integration_confidence",
        "selected_priority",
        "dominant_pressure_axis",
        "highest_conflict_severity",
        "stabilize_weight",
        "explore_weight",
        "repair_weight",
        "progress_weight",
        "social_weight",
        "boundary_weight",
        "active_hint_axes",
        "tendency_status",
    }
    assert "integration_state" not in projection
    assert "cross_axis_priority_state" not in projection
    assert "proposal_conflict_state" not in projection
    assert "axis_arbitration_hints" not in projection
    assert "integration_ledger" not in projection
    assert RUNTIME_LOCAL_PROJECTION_FIELD == "proto_self_v2.state.selfhood_integration"
    assert "runtime-local bounded projection" in RUNTIME_LOCAL_PROJECTION_SEMANTICS


def test_governance_rejects_behavioral_authority_and_forbidden_effects():
    state = SelfhoodIntegrationState()
    state.integrated_tendency_proposal = {
        "proposal_id": "integrated_1",
        "tendency_label": "attempt_direct_reply",
        "priority_mode": "repair",
        "policy_mode": "stability_first",
        "proposed_effects": {"reply_text": "not allowed"},
        "justification": "invalid for owner contract",
        "required_gate": "self_integration_writeback_gate",
        "behavioral_authority": "reply",
        "requested_effects": [FORBIDDEN_REQUESTED_EFFECTS[0]],
        "status": "proposed",
    }

    verdict = validate_selfhood_integration_state(state)

    assert not verdict.accepted
    assert "invalid_behavioral_authority:integrated_1:reply" in verdict.violations
    assert (
        f"forbidden_integrated_effect:integrated_1:{FORBIDDEN_REQUESTED_EFFECTS[0]}"
        in verdict.violations
    )


def test_store_roundtrip_and_replay(tmp_path):
    reset_selfhood_integration_owner()
    owner = SelfhoodIntegrationOwner(store=SelfhoodIntegrationStore(tmp_path))
    owner.set_integration_state(
        posture=ArbitrationPriority.STABILIZE,
        dominant_pressure_axis="embodied_self",
        stability_bias=0.79,
        integration_confidence=0.68,
        active_axis_count=6,
        rationale_summary="resource pressure and low confidence require bounded stabilization",
        source_refs=["trace:integration"],
    )
    owner.set_cross_axis_priority_state(
        selected_priority=ArbitrationPriority.CONSERVE,
        stabilize_weight=0.82,
        conserve_weight=0.78,
        guard_weight=0.74,
        review_weight=0.66,
        repair_weight=0.48,
        grow_weight=0.22,
        reflective_modifier=0.19,
        priority_reason="embodied pressure outranks repair and growth in phase1",
        upstream_pressure_sources=[
            "wp8:self_model_low_confidence",
            "wp9:maintenance_pressure_high",
            "wp13:resource_boundary_pressure_high",
        ],
        source_refs=["trace:priority"],
    )
    owner.set_proposal_conflict_state(
        highest_severity=ConflictSeverity.MEDIUM,
        conflict_count=2,
        unresolved_conflict_refs=["conflict:self_model_vs_growth", "conflict:social_vs_boundary"],
        blocked_axes=["developmental_self"],
        resolution_posture=ArbitrationPriority.REVIEW,
        source_refs=["trace:conflict"],
    )
    owner.set_stabilize_explore_balance(
        stabilize_weight=0.8,
        explore_weight=0.2,
        preferred_pole="stabilize",
        rationale="low confidence keeps exploration deferred",
        source_refs=["trace:balance:stabilize"],
    )
    owner.set_repair_progress_balance(
        repair_weight=0.64,
        progress_weight=0.36,
        preferred_pole="repair",
        rationale="repair remains ahead of forward progress under conflict",
        source_refs=["trace:balance:repair"],
    )
    owner.set_social_boundary_balance(
        social_weight=0.41,
        boundary_weight=0.59,
        preferred_pole="boundary",
        rationale="boundary protection stays ahead of social expansion",
        source_refs=["trace:balance:social"],
    )
    proposal = owner.propose_integrated_tendency(
        tendency_label="stabilize_and_review_before_growth",
        priority_mode=ArbitrationPriority.REVIEW,
        proposed_effects={
            "integrated_policy_hints": ["conserve", "guard", "review"],
            "self_integration_delta": {"stability_bias": 0.79},
        },
        justification="phase1 stability-first arbitration keeps upstream proposals bounded",
        source_refs=["trace:proposal"],
    )
    owner.set_integrated_tendency_status(status=IntegratedProposalStatus.APPROVED_FOR_REVIEW)
    owner.upsert_axis_arbitration_hint(
        axis_name="self_model",
        recommendation="hold growth until confidence recovers",
        priority_weight=0.76,
        guardrail_summary="do not rewrite upstream self_model owner state",
        source_refs=["trace:hint:self_model"],
    )
    owner.upsert_axis_arbitration_hint(
        axis_name="embodied_self",
        recommendation="conserve resources and raise guard bias",
        priority_weight=0.83,
        guardrail_summary="treat embodied pressure as advisory, not direct action authority",
        source_refs=["trace:hint:embodied"],
    )
    owner.record_integration_event(
        event_type="integration_snapshot_created",
        reference_id=proposal.proposal_id,
        gate_verdict="allow_review",
        details={"selected_priority": "conserve"},
    )

    record = owner.persist(update_source="test_roundtrip", trace_reference="test:selfhood")
    loaded = owner.store.load()
    revisions = owner.store.load_revision_log()
    replayed = replay_state_from_revisions(revisions)

    assert record.revision_id == "integration_rev_000001"
    assert loaded is not None
    assert loaded.last_revision_id == record.revision_id
    assert loaded.integrated_tendency_proposal is not None
    assert replayed is not None
    assert replayed.last_revision_id == record.revision_id
    assert replayed.owner_revision == 1
    assert replayed.identity_handle == "openemotion"
    assert replayed.integration_ledger


def test_owner_records_summary_and_health():
    reset_selfhood_integration_owner()
    owner = SelfhoodIntegrationOwner()
    owner.set_integration_state(
        posture=ArbitrationPriority.REPAIR,
        dominant_pressure_axis="social_self",
        stability_bias=0.41,
        integration_confidence=0.52,
        active_axis_count=5,
        rationale_summary="repair pressure outruns growth under current conflict",
    )
    owner.set_cross_axis_priority_state(
        selected_priority=ArbitrationPriority.REPAIR,
        stabilize_weight=0.44,
        conserve_weight=0.41,
        guard_weight=0.45,
        review_weight=0.52,
        repair_weight=0.72,
        grow_weight=0.28,
        reflective_modifier=0.22,
        priority_reason="repair bias elevated by social commitment risk",
    )
    owner.set_proposal_conflict_state(
        highest_severity=ConflictSeverity.HIGH,
        conflict_count=3,
        unresolved_conflict_refs=["conflict:repair_vs_boundary"],
        blocked_axes=["developmental_self", "social_self"],
        resolution_posture=ArbitrationPriority.REVIEW,
    )
    owner.set_stabilize_explore_balance(
        stabilize_weight=0.48,
        explore_weight=0.52,
        preferred_pole="explore",
        rationale="deliberately imbalanced test state",
    )
    owner.set_repair_progress_balance(
        repair_weight=0.71,
        progress_weight=0.29,
        preferred_pole="repair",
        rationale="repair remains dominant",
    )
    owner.set_social_boundary_balance(
        social_weight=0.47,
        boundary_weight=0.53,
        preferred_pole="boundary",
        rationale="boundary still slightly ahead",
    )
    owner.propose_integrated_tendency(
        tendency_label="repair_then_review",
        priority_mode=ArbitrationPriority.REPAIR,
        proposed_effects={"integrated_policy_hints": ["repair", "review"]},
        justification="repair pressure is dominant in this synthetic health check",
    )
    owner.upsert_axis_arbitration_hint(
        axis_name="social_self",
        recommendation="repair commitments before broader social progress",
        priority_weight=0.8,
        guardrail_summary="no direct mutation of social_self owner state",
    )

    summary = owner.get_summary()
    health = owner.check_health()

    assert summary["hint_count"] == 1
    assert summary["conflict_count"] == 3
    assert summary["has_integrated_tendency_proposal"] is True
    assert "summary" in health
    assert "issues" in health
    assert "high_conflict_pressure" in health["issues"]
    assert "stability_first_bias_missing" in health["issues"]


def test_legacy_reference_only_fields_are_excluded_from_owner_payload_and_proof_surface():
    payload = SelfhoodIntegrationState().model_dump(mode="json")

    for field in PHASE1_LEGACY_REFERENCE_ONLY_FIELDS:
        assert field not in payload
        assert field not in PHASE1_ALLOWED_PROOF_LEVERS
