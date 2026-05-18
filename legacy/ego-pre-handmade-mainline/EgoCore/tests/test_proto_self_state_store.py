from __future__ import annotations

import json
from pathlib import Path

from app.openemotion_adapter.proto_self_state_store import ProtoSelfStateStore
from openemotion.proto_self import ProtoSelfState
from openemotion.proto_self_v2.state import ProtoSelfStateV2
from openemotion.proto_self_v2.seed_state import ProtoSelfSeedState


def _make_state(*, revision: int, focus: str) -> ProtoSelfState:
    state = ProtoSelfState.empty()
    state.revision_counter = revision
    state.self_model.current_focus = focus
    return state


def test_state_store_loads_legacy_state_and_writes_new_layout(tmp_path: Path) -> None:
    legacy_dir = tmp_path / "legacy_mirror"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    legacy_state = _make_state(revision=3, focus="legacy_focus")
    (legacy_dir / "state.json").write_text(
        json.dumps(legacy_state.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    store = ProtoSelfStateStore(
        root_dir=tmp_path / "proto_self_store",
        legacy_mirror_dir=legacy_dir,
    )

    loaded = store.load_agent_global_state()
    assert loaded.revision_counter == 3
    assert loaded.self_model.current_focus == "legacy_focus"

    store.save_agent_global_state(loaded, context={"source": "migration_test"})
    assert store.agent_global_state_path.exists()
    persisted = json.loads(store.agent_global_state_path.read_text(encoding="utf-8"))
    assert persisted["revision_counter"] == 3
    assert json.loads((legacy_dir / "state.json").read_text(encoding="utf-8"))["revision_counter"] == 3


def test_record_session_reset_preserves_agent_global_state(tmp_path: Path) -> None:
    store = ProtoSelfStateStore(
        root_dir=tmp_path / "proto_self_store",
        legacy_mirror_dir=tmp_path / "legacy_mirror",
    )
    agent_state = _make_state(revision=5, focus="global_focus")
    store.save_agent_global_state(agent_state, context={"source": "unit_test"})
    before = store.agent_global_state_path.read_text(encoding="utf-8")

    store.record_event_binding(
        session_id="telegram:dm:123",
        thread_id="telegram:dm:123",
        source="telegram",
        event_id="evt_1",
        turn_id="turn_1",
        event_type="user_message",
        context={"state_scope": "agent_global"},
    )
    store.record_session_reset(
        session_id="telegram:dm:123",
        thread_id="telegram:dm:123",
        source="runtime_v2",
        command="/new",
        generation_id=2,
    )

    after = store.agent_global_state_path.read_text(encoding="utf-8")
    assert before == after

    session_manifest = json.loads(
        (store.root_dir / "sessions" / "telegram_dm_123" / "session.json").read_text(encoding="utf-8")
    )
    assert session_manifest["reset_count"] == 1
    assert session_manifest["generation_id"] == 2
    assert session_manifest["last_reset"]["command"] == "/new"
    assert session_manifest["last_reset"]["preserves_agent_global"] is True


def test_experiment_state_is_isolated_from_agent_global(tmp_path: Path) -> None:
    store = ProtoSelfStateStore(
        root_dir=tmp_path / "proto_self_store",
        legacy_mirror_dir=tmp_path / "legacy_mirror",
    )
    global_state = _make_state(revision=7, focus="live_global")
    store.save_agent_global_state(global_state, context={"source": "live"})

    store.fork_experiment("replay_case_001", source_trace="logs/proto_self_trace.jsonl")
    experiment_state = store.load_experiment_state("replay_case_001")
    assert experiment_state.revision_counter == 7
    assert experiment_state.self_model.current_focus == "live_global"

    experiment_state.revision_counter = 99
    experiment_state.self_model.current_focus = "replay_only"
    store.save_experiment_state("replay_case_001", experiment_state)

    reloaded_global = store.load_agent_global_state()
    reloaded_experiment = store.load_experiment_state("replay_case_001")
    assert reloaded_global.revision_counter == 7
    assert reloaded_global.self_model.current_focus == "live_global"
    assert reloaded_experiment.revision_counter == 99
    assert reloaded_experiment.self_model.current_focus == "replay_only"


def test_state_store_round_trips_v2_seed_state_and_preserves_v1_mirror(tmp_path: Path) -> None:
    store = ProtoSelfStateStore(
        root_dir=tmp_path / "proto_self_store",
        legacy_mirror_dir=tmp_path / "legacy_mirror",
    )
    state_v2 = ProtoSelfStateV2.empty()
    state_v2.revision_counter = 11
    state_v2.self_model.current_focus = "seed_focus"
    state_v2.seed_state = ProtoSelfSeedState.empty()
    state_v2.seed_state.focus_goal.current_focus = "inspect_target"
    state_v2.seed_state.focus_goal.pending_commitment = "finish_seed_contract"
    state_v2.seed_state.revision_counter = 4

    store.save_agent_global_state_v2(state_v2, context={"source": "seed_test"})
    loaded = store.load_agent_global_state_v2()

    assert loaded.revision_counter == 11
    assert loaded.seed_state is not None
    assert loaded.seed_state.focus_goal.pending_commitment == "finish_seed_contract"
    assert store.agent_global_state_v2_path.exists()

    legacy_payload = json.loads(store.legacy_state_path.read_text(encoding="utf-8"))
    assert legacy_payload["revision_counter"] == 11
    assert "seed_state" not in legacy_payload
