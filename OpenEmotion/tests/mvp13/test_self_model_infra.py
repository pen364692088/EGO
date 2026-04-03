import json

from openemotion.self_model import (
    Goal,
    GoalStatus,
    Priority,
    REQUIRED_REVISION_FIELDS,
    SelfModelReplay,
    SelfModelReplayError,
    SelfModelStore,
    create_default_self_model,
)


IDENTITY = "openemotion"


def test_self_model_store_saves_and_loads_across_instances(tmp_path):
    store = SelfModelStore(base_dir=tmp_path)
    baseline = create_default_self_model(IDENTITY)

    revision = store.save(
        baseline,
        update_source="owner_bootstrap",
        trace_reference="trace:init",
    )

    reloaded_store = SelfModelStore(base_dir=tmp_path)
    reloaded = reloaded_store.load(IDENTITY)

    assert reloaded is not None
    assert reloaded.to_dict() == revision.state_snapshot
    assert reloaded_store.state_file(IDENTITY).exists()
    assert reloaded_store.revision_log_file(IDENTITY).exists()


def test_self_model_store_persists_revision_log_and_backup(tmp_path):
    store = SelfModelStore(base_dir=tmp_path)
    first = create_default_self_model(IDENTITY)
    first_revision = store.save(
        first,
        update_source="owner_bootstrap",
        trace_reference="trace:baseline",
    )

    updated = create_default_self_model(IDENTITY)
    updated.active_goals = [
        Goal(
            goal_id="goal_owner_store",
            description="Keep formal owner state persistent",
            status=GoalStatus.IN_PROGRESS.value,
            priority=Priority.HIGH.value,
            progress=0.5,
        )
    ]
    updated.confidence_by_domain["reasoning"] = 0.99
    second_revision = store.save(
        updated,
        update_source="owner_update",
        trace_reference="trace:update",
    )

    ledger_lines = store.revision_log_file(IDENTITY).read_text(encoding="utf-8").strip().splitlines()
    latest_revision = json.loads(ledger_lines[-1])
    backup_payload = json.loads(store.backup_file(IDENTITY).read_text(encoding="utf-8"))
    reloaded = SelfModelStore(base_dir=tmp_path).load(IDENTITY)

    assert reloaded is not None
    assert reloaded.to_dict() == second_revision.state_snapshot
    assert len(ledger_lines) == 2
    assert latest_revision["revision_id"] == "rev_000002"
    assert latest_revision["state_hash"] == second_revision.state_hash
    assert latest_revision["previous_state_hash"] == first_revision.state_hash
    assert backup_payload["identity_handle"] == IDENTITY
    assert reloaded.modification_audit_trail[-1]["trigger"] == "owner_update"


def test_revision_log_contains_required_replay_contract_fields(tmp_path):
    store = SelfModelStore(base_dir=tmp_path)
    store.save(
        create_default_self_model(IDENTITY),
        update_source="owner_contract_check",
        trace_reference="trace:contract",
        confidence_class="stable",
        gate_verdict="allow_writeback",
    )

    revision = json.loads(store.revision_log_file(IDENTITY).read_text(encoding="utf-8").strip())

    for field in REQUIRED_REVISION_FIELDS:
        assert field in revision


def test_self_model_replay_reconstructs_latest_state_from_ledger(tmp_path):
    store = SelfModelStore(base_dir=tmp_path)
    baseline = create_default_self_model(IDENTITY)
    store.save(
        baseline,
        update_source="owner_bootstrap",
        trace_reference="trace:baseline",
    )

    evolved = create_default_self_model(IDENTITY)
    evolved.active_goals = [
        Goal(
            goal_id="goal_replay",
            description="Replay must reconstruct the latest formal owner state",
            status=GoalStatus.ACCEPTED.value,
            priority=Priority.MEDIUM.value,
            progress=1.0,
        )
    ]
    evolved.limitations[0].workaround = "use formal owner replay"
    store.save(
        evolved,
        update_source="owner_update",
        trace_reference="trace:evolved",
    )

    store.state_file(IDENTITY).unlink()

    replay = SelfModelReplay(SelfModelStore(base_dir=tmp_path), identity_handle=IDENTITY)
    result = replay.replay()

    assert result.valid_chain is True
    assert result.revision_count == 2
    assert result.state is not None
    assert result.state.active_goals[0].goal_id == "goal_replay"
    assert result.state.limitations[0].workaround == "use formal owner replay"


def test_self_model_replay_raises_on_before_snapshot_mismatch(tmp_path):
    store = SelfModelStore(base_dir=tmp_path)
    store.save(
        create_default_self_model(IDENTITY),
        update_source="owner_bootstrap",
        trace_reference="trace:first",
    )
    store.save(
        create_default_self_model(IDENTITY),
        update_source="owner_update",
        trace_reference="trace:second",
    )

    wrong_base = create_default_self_model("other_identity").to_dict()

    try:
        store.replay(IDENTITY, base_snapshot=wrong_base)
    except SelfModelReplayError as exc:
        assert "replay divergence" in str(exc)
    else:
        raise AssertionError("expected replay mismatch to raise SelfModelReplayError")
