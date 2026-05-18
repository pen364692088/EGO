from openemotion.reflective_self import (
    ReflectiveSelfOwner,
    ReflectiveSelfState,
    ReflectiveSelfStore,
    ReflectionTargetType,
    replay_state_from_revisions,
    reset_reflective_self_owner,
    validate_reflective_state,
)


def test_reflection_queue_lifecycle_is_replayable(tmp_path):
    reset_reflective_self_owner()
    owner = ReflectiveSelfOwner(store=ReflectiveSelfStore(tmp_path))
    item = owner.enqueue_reflection(
        target_type=ReflectionTargetType.DECISION,
        target_reference="decision:target",
        trigger_source="test",
        priority=0.9,
    )
    owner.start_reflection(item.reflection_id)
    first_record = owner.persist(update_source="after_start", trace_reference="test:after_start")
    owner.complete_reflection(item.reflection_id, resolution_note="captured for replay")
    second_record = owner.persist(update_source="after_complete", trace_reference="test:after_complete")

    revisions = owner.store.load_revision_log()
    replayed = replay_state_from_revisions(revisions)

    assert first_record.revision_id == "reflective_rev_000001"
    assert second_record.revision_id == "reflective_rev_000002"
    assert replayed is not None
    assert replayed.last_revision_id == "reflective_rev_000002"
    assert item.reflection_id not in replayed.reflection_queue
    assert any(entry.entry_type == "reflection_completed" for entry in replayed.reflection_history.entries)


def test_counterfactuals_must_keep_uncertainty_explicit():
    reset_reflective_self_owner()
    owner = ReflectiveSelfOwner()
    record = owner.record_counterfactual(
        baseline_reference="decision:1",
        alternative_path="ask_for_more_evidence",
        expected_difference={"risk_delta": -0.2},
        uncertainty_level=0.4,
    )

    assert record.truth_status == "counterfactual_uncertain"
    assert validate_reflective_state(owner.get_state()).accepted

    owner.get_state().counterfactual_records[record.counterfactual_id].truth_status = "established_truth"
    verdict = validate_reflective_state(owner.get_state())

    assert not verdict.accepted
    assert f"invalid_counterfactual_truth_status:{record.counterfactual_id}" in verdict.violations


def test_proposals_remain_proposal_only_after_gate_review():
    reset_reflective_self_owner()
    owner = ReflectiveSelfOwner()
    proposal = owner.propose_revision(
        target_layer="policy_hint",
        proposed_change={"bias": "increase_verification"},
        justification="contradiction detected",
        required_gate="reflection_writeback_gate",
    )
    reviewed = owner.set_proposal_gate_status(
        proposal.proposal_id,
        status="approved_for_review",
        gate_verdict="allow_writeback",
        gate_reference="gate:test",
        reason="still proposal only",
    )

    assert reviewed.effect_scope == "proposal_only"
    assert reviewed.status == "approved_for_review"
    assert reviewed.gate_metadata["gate_verdict"] == "allow_writeback"
    assert validate_reflective_state(owner.get_state()).accepted


def test_governance_blocks_applied_proposal_state():
    state = ReflectiveSelfState()
    state.revision_proposals["proposal_1"] = {
        "proposal_id": "proposal_1",
        "target_layer": "policy_hint",
        "proposed_change": {"bias": "none"},
        "justification": "test",
        "required_gate": "reflection_writeback_gate",
        "status": "applied",
    }

    verdict = validate_reflective_state(state)

    assert not verdict.accepted
    assert "proposal_bypassed_governance:proposal_1" in verdict.violations
