import json

from openemotion.self_model import (
    Goal,
    GoalStatus,
    Priority,
    SelfModelReplay,
    SelfModelStore,
    create_default_self_model,
)


IDENTITY = "openemotion"


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
    latest_snapshot = json.loads(store.revision_log_file(IDENTITY).read_text(encoding="utf-8").strip().splitlines()[-1])[
        "after_snapshot"
    ]
    assert result.state.to_dict() == latest_snapshot
    assert result.state.active_goals[0].goal_id == "goal_replay"
    assert result.state.limitations[0].workaround == "use formal owner replay"


def test_self_model_replay_validates_revision_chain(tmp_path):
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

    replay = SelfModelReplay(SelfModelStore(base_dir=tmp_path), identity_handle=IDENTITY)
    revisions = replay.load_revisions()

    assert replay.validate_chain(revisions) is True
