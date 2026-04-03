import json

from openemotion.self_model import Goal, GoalStatus, Priority, SelfModelStore, create_default_self_model


def test_self_model_store_saves_loads_and_persists_revisions(tmp_path):
    store = SelfModelStore(base_dir=tmp_path)

    initial = create_default_self_model("openemotion")
    first_revision = store.save(initial, changed_fields=["capabilities"], reason="initial_snapshot")

    reloaded_store = SelfModelStore(base_dir=tmp_path)
    reloaded_initial = reloaded_store.load()

    assert reloaded_initial is not None
    assert reloaded_initial.to_dict() == first_revision.state_snapshot
    assert store.state_file.exists()
    assert store.revision_ledger_file.exists()

    updated = create_default_self_model("openemotion")
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
        changed_fields=["active_goals", "confidence_by_domain"],
        reason="update_goal_and_confidence",
    )

    reloaded_updated = SelfModelStore(base_dir=tmp_path).load()
    ledger_lines = store.revision_ledger_file.read_text(encoding="utf-8").strip().splitlines()
    backup_payload = json.loads(store.backup_file.read_text(encoding="utf-8"))

    assert reloaded_updated is not None
    assert reloaded_updated.to_dict() == second_revision.state_snapshot
    assert backup_payload["identity_handle"] == "openemotion"
    assert len(ledger_lines) == 2

    latest_revision = json.loads(ledger_lines[-1])
    assert latest_revision["revision_id"] == "rev_000002"
    assert latest_revision["state_hash"] == second_revision.state_hash
    assert latest_revision["previous_state_hash"] == first_revision.state_hash
    assert reloaded_updated.modification_audit_trail[-1]["reason"] == "update_goal_and_confidence"
