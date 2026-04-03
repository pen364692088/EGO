import json

from openemotion.self_model import Goal, GoalStatus, Priority, SelfModelStore, create_default_self_model


IDENTITY = "openemotion"


def test_self_model_store_saves_loads_and_persists_revisions(tmp_path):
    store = SelfModelStore(base_dir=tmp_path)

    initial = create_default_self_model(IDENTITY)
    first_revision = store.save(
        initial,
        update_source="owner_bootstrap",
        trace_reference="trace:init",
    )

    reloaded_store = SelfModelStore(base_dir=tmp_path)
    reloaded_initial = reloaded_store.load(IDENTITY)

    assert reloaded_initial is not None
    assert reloaded_initial.to_dict() == first_revision.state_snapshot
    assert store.state_file(IDENTITY).exists()
    assert store.revision_log_file(IDENTITY).exists()

    updated = create_default_self_model(IDENTITY)
    updated.active_goals = [
        Goal(
            goal_id="goal_persistence",
            description="Keep the formal owner state persistent",
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

    reloaded_updated = SelfModelStore(base_dir=tmp_path).load(IDENTITY)
    ledger_lines = store.revision_log_file(IDENTITY).read_text(encoding="utf-8").strip().splitlines()
    backup_payload = json.loads(store.backup_file(IDENTITY).read_text(encoding="utf-8"))

    assert reloaded_updated is not None
    assert reloaded_updated.to_dict() == second_revision.state_snapshot
    assert backup_payload["identity_handle"] == IDENTITY
    assert len(ledger_lines) == 2

    latest_revision = json.loads(ledger_lines[-1])
    assert latest_revision["revision_id"] == "rev_000002"
    assert latest_revision["state_hash"] == second_revision.state_hash
    assert latest_revision["previous_state_hash"] == first_revision.state_hash
    assert reloaded_updated.modification_audit_trail[-1]["trigger"] == "owner_update"
