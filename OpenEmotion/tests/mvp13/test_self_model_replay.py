import json

from openemotion.self_model import (
    Goal,
    GoalStatus,
    Priority,
    SelfModelReplay,
    SelfModelStore,
    create_default_self_model,
)


def test_self_model_replay_reconstructs_latest_state_from_ledger(tmp_path):
    store = SelfModelStore(base_dir=tmp_path)

    baseline = create_default_self_model("openemotion")
    store.save(baseline, changed_fields=["capabilities"], reason="baseline")

    evolved = create_default_self_model("openemotion")
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
        changed_fields=["active_goals", "limitations"],
        reason="evolved_state",
    )

    store.state_file.unlink()

    replay = SelfModelReplay(SelfModelStore(base_dir=tmp_path))
    result = replay.replay()

    assert result.valid_chain is True
    assert result.revision_count == 2
    assert result.state is not None
    assert result.state.to_dict() == json.loads(store.revision_ledger_file.read_text(encoding="utf-8").strip().splitlines()[-1])["state_snapshot"]
    assert result.state.active_goals[0].goal_id == "goal_replay"
    assert result.state.limitations[0].workaround == "use formal owner replay"


def test_self_model_replay_validates_revision_chain(tmp_path):
    store = SelfModelStore(base_dir=tmp_path)
    store.save(create_default_self_model("openemotion"), changed_fields=["capabilities"], reason="baseline")
    store.save(create_default_self_model("openemotion"), changed_fields=["limitations"], reason="second")

    replay = SelfModelReplay(SelfModelStore(base_dir=tmp_path))
    revisions = replay.load_revisions()

    assert replay.validate_chain(revisions) is True

