from openemotion.reflective_self import (
    FORMAL_OWNER_SCHEMA_VERSION,
    FORBIDDEN_REQUESTED_EFFECTS,
    PHASE1_ALLOWED_PROOF_LEVERS,
    PHASE1_AUTHORITATIVE_FIELDS,
    PHASE1_LEGACY_REFERENCE_ONLY_FIELDS,
    RUNTIME_LOCAL_PROJECTION_FIELD,
    RUNTIME_LOCAL_PROJECTION_SEMANTICS,
    ReflectiveSelfOwner,
    ReflectiveSelfState,
    ReflectiveSelfStore,
    ReflectionTargetType,
    replay_state_from_revisions,
    reset_reflective_self_owner,
    validate_reflective_state,
)


def test_reflective_owner_payload_matches_authoritative_fields():
    payload = ReflectiveSelfState().model_dump(mode="json")

    assert tuple(payload.keys()) == PHASE1_AUTHORITATIVE_FIELDS
    assert payload["schema_version"] == FORMAL_OWNER_SCHEMA_VERSION


def test_runtime_projection_is_bounded():
    state = ReflectiveSelfState()
    state.reflection_targets["t1"] = {
        "target_id": "t1",
        "target_type": "decision",
        "reference": "decision:target",
        "salience": 0.9,
        "reason": "mismatch",
    }
    state.diagnosis_records["d1"] = {
        "diagnosis_id": "d1",
        "analyzed_target": "decision:target",
        "detected_pattern": "repeated mismatch",
        "confidence": 0.8,
    }

    projection = state.to_runtime_projection()

    assert projection["owner_revision"] == 0
    assert projection["top_target_ids"] == ["t1"]
    assert "diagnosis_records" not in projection
    assert "counterfactual_records" not in projection
    assert RUNTIME_LOCAL_PROJECTION_FIELD == "proto_self_v2.state.reflective_self"
    assert "runtime-local bounded projection" in RUNTIME_LOCAL_PROJECTION_SEMANTICS


def test_governance_rejects_forbidden_authority_effects():
    state = ReflectiveSelfState()
    state.reflection_queue["reflection_1"] = {
        "reflection_id": "reflection_1",
        "target_type": "decision",
        "target_reference": "decision:1",
        "priority": 0.8,
        "trigger_source": "test",
        "requested_effects": [FORBIDDEN_REQUESTED_EFFECTS[0]],
    }

    verdict = validate_reflective_state(state)

    assert not verdict.accepted
    assert "forbidden_queue_effect:reflection_1:final_reply_text" in verdict.violations


def test_store_roundtrip_and_replay(tmp_path):
    reset_reflective_self_owner()
    owner = ReflectiveSelfOwner(store=ReflectiveSelfStore(tmp_path))
    owner.upsert_target(
        target_id="decision_root",
        target_type=ReflectionTargetType.DECISION,
        reference="decision:root",
        reason="needs review",
        salience=0.8,
    )
    owner.record_diagnosis(
        analyzed_target="decision:root",
        detected_pattern="oscillation",
        confidence=0.7,
        supporting_evidence=["trace:1"],
    )
    owner.propose_revision(
        target_layer="policy_hint",
        proposed_change={"adjustment": "defer_until_verified"},
        justification="stabilize contradictory plan selection",
        required_gate="reflection_writeback_gate",
    )

    record = owner.persist(update_source="test_roundtrip", trace_reference="test:reflective")
    loaded = owner.store.load()
    revisions = owner.store.load_revision_log()
    replayed = replay_state_from_revisions(revisions)

    assert record.revision_id == "reflective_rev_000001"
    assert loaded is not None
    assert loaded.last_revision_id == record.revision_id
    assert replayed is not None
    assert replayed.last_revision_id == record.revision_id
    assert "decision_root" in replayed.reflection_targets


def test_owner_records_history_and_health_summary():
    reset_reflective_self_owner()
    owner = ReflectiveSelfOwner()
    owner.enqueue_reflection(
        target_type=ReflectionTargetType.STATE,
        target_reference="self_model:consistency",
        trigger_source="runtime_summary",
        priority=0.6,
    )
    diagnosis = owner.record_diagnosis(
        analyzed_target="self_model:consistency",
        detected_pattern="consistency gap",
        confidence=0.75,
    )
    owner.add_unresolved_item(
        summary="Need follow-up on consistency gap",
        linked_record_id=diagnosis.diagnosis_id,
        severity=0.7,
    )

    summary = owner.get_summary()
    health = owner.check_health()

    assert summary["pending_reflections"] == 1
    assert summary["unresolved_items"] == 1
    assert len(owner.get_state().reflection_history.entries) >= 3
    assert "summary" in health
    assert "issues" in health


def test_legacy_reference_only_fields_are_excluded_from_owner_payload_and_proof_surface():
    payload = ReflectiveSelfState().model_dump(mode="json")

    for field in PHASE1_LEGACY_REFERENCE_ONLY_FIELDS:
        assert field not in payload
        assert field not in PHASE1_ALLOWED_PROOF_LEVERS
