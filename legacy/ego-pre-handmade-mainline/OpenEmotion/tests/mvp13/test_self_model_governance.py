from openemotion.self_model import (
    ALLOW_WRITEBACK,
    HOLD_FOR_REVIEW,
    REJECT,
    ROLLBACK_TO_LAST_STABLE,
    Goal,
    GoalStatus,
    Priority,
    SelfModelStore,
    SelfModelUpdateRequest,
    apply_governed_writeback,
    check_identity_invariants,
    create_default_self_model,
    evaluate_update_request,
)


IDENTITY = "openemotion"


def test_identity_invariants_reject_identity_handle_change():
    baseline = create_default_self_model(IDENTITY)
    proposed = create_default_self_model("other_identity")
    proposed.created_at = baseline.created_at

    violations = check_identity_invariants(
        baseline,
        proposed,
        request=SelfModelUpdateRequest(
            delta={"identity_handle": "other_identity"},
            update_mode="rollback_revision",
            update_source="governance_revision",
            trace_reference="trace:identity",
            confidence_class="critical",
            supporting_evidence=["explicit governance revision"],
        ),
    )

    assert any(item.field_path == "identity_handle" for item in violations)


def test_update_gate_rejects_tool_authority_expansion_without_governance_revision():
    baseline = create_default_self_model(IDENTITY)
    request = SelfModelUpdateRequest(
        delta={
            "tool_authority_boundary": {
                "current_allowed_tools": ["read", "write", "edit", "exec", "network"],
                "restricted_tools": [],
                "forbidden_tools": [],
            }
        },
        update_mode="promote_to_stable_trait",
        update_source="proto_self_v2",
        trace_reference="trace:tool-boundary",
        confidence_class="high",
        supporting_evidence=["candidate:stable-pattern"],
    )

    decision = evaluate_update_request(baseline, request=request)

    assert decision.gate_verdict == REJECT
    assert any(item.field_path == "tool_authority_boundary" for item in decision.invariant_violations)


def test_drift_policy_holds_low_confidence_standing_commitment_rewrite():
    baseline = create_default_self_model(IDENTITY)
    baseline.standing_commitments = []
    request = SelfModelUpdateRequest(
        delta={
            "standing_commitments": [
                {
                    "commitment_id": "commitment_review",
                    "source": "runtime_learned",
                    "description": "Maintain a persistent explanatory style",
                    "binding_level": "soft",
                    "active": True,
                }
            ]
        },
        update_mode="revise_tendency",
        update_source="proto_self_v2",
        trace_reference="trace:commitment",
        confidence_class="medium",
        supporting_evidence=["cycle:001"],
    )

    decision = evaluate_update_request(baseline, request=request)

    assert decision.gate_verdict == HOLD_FOR_REVIEW
    assert decision.drift_assessment.stable_default_changes == ["standing_commitments"]


def test_drift_policy_rolls_back_on_revision_oscillation(tmp_path):
    store = SelfModelStore(base_dir=tmp_path)
    baseline = create_default_self_model(IDENTITY)
    revision_1 = store.save(
        baseline,
        update_source="owner_bootstrap",
        trace_reference="trace:r1",
        confidence_class="high",
    )

    updated = create_default_self_model(IDENTITY)
    updated.confidence_by_domain["reasoning"] = 0.2
    revision_2 = store.save(
        updated,
        update_source="owner_update",
        trace_reference="trace:r2",
        confidence_class="high",
    )

    request = SelfModelUpdateRequest(
        delta={"confidence_by_domain": {"reasoning": 0.95}},
        update_mode="append_observation",
        update_source="proto_self_v2",
        trace_reference="trace:r3",
        confidence_class="high",
        supporting_evidence=["cycle:stable-pattern"],
    )

    decision = evaluate_update_request(
        updated,
        request=request,
        revisions=[revision_1, revision_2],
    )

    assert decision.gate_verdict == ROLLBACK_TO_LAST_STABLE
    assert decision.drift_assessment.revision_oscillation_rate == 1.0


def test_governed_writeback_emits_revision_for_allowed_delta(tmp_path):
    store = SelfModelStore(base_dir=tmp_path)
    baseline = create_default_self_model(IDENTITY)
    store.save(
        baseline,
        update_source="owner_bootstrap",
        trace_reference="trace:init",
        confidence_class="high",
    )

    request = SelfModelUpdateRequest(
        delta={
            "active_goals": [
                Goal(
                    goal_id="goal_mvp13_owner",
                    description="Persist the formal owner self-model",
                    status=GoalStatus.IN_PROGRESS.value,
                    priority=Priority.HIGH.value,
                    progress=0.6,
                ).to_dict()
            ],
            "confidence_by_domain": {"reasoning": 0.92},
        },
        update_mode="append_observation",
        update_source="proto_self_v2",
        trace_reference="trace:allow",
        confidence_class="high",
        supporting_evidence=["cycle:stable-pattern", "trace:allow"],
    )

    result = apply_governed_writeback(
        store=store,
        current_model=baseline,
        request=request,
        revisions=store.load_revision_log(IDENTITY),
    )

    saved = store.load(IDENTITY)

    assert result.decision.gate_verdict == ALLOW_WRITEBACK
    assert result.stable_snapshot_mutated is True
    assert result.revision is not None
    assert saved is not None
    assert saved.active_goals[0].goal_id == "goal_mvp13_owner"
    assert saved.modification_audit_trail[-1]["gate_verdict"] == ALLOW_WRITEBACK


def test_governed_writeback_rejects_legacy_field_without_mutating_store(tmp_path):
    store = SelfModelStore(base_dir=tmp_path)
    baseline = create_default_self_model(IDENTITY)
    store.save(
        baseline,
        update_source="owner_bootstrap",
        trace_reference="trace:init",
        confidence_class="high",
    )

    request = SelfModelUpdateRequest(
        delta={"active_tensions": [{"tension_id": "legacy_only"}]},
        update_mode="append_observation",
        update_source="proto_self_v2",
        trace_reference="trace:legacy",
        confidence_class="high",
        supporting_evidence=["cycle:legacy"],
    )

    result = apply_governed_writeback(
        store=store,
        current_model=baseline,
        request=request,
        revisions=store.load_revision_log(IDENTITY),
    )

    saved = store.load(IDENTITY)

    assert result.decision.gate_verdict == REJECT
    assert result.stable_snapshot_mutated is False
    assert result.revision is None
    assert saved is not None
    assert "active_tensions" not in saved.to_dict()
