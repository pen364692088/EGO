"""
MVP16: Open Developmental Self tests.

Coverage focuses on admission-grade developmental projection:
- schema and persistence basics
- anti-false-positive protection
- controlled real-sample backfill
- trajectory index / replay audit artifact generation
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from emotiond.developmental import (
    DevelopmentalEpisode,
    DevelopmentalManager,
    DevelopmentalState,
    DevelopmentalWritebackEvent,
    GrowthMetric,
    TransitionRecord,
    get_developmental_manager,
    reset_developmental_manager,
)


REAL_OUTPUT_SCHEMA_VERSION = "proto_self.output.v2"
REAL_TRACE_SCHEMA_VERSION = "proto_self.trace.v2"


def _write_sample(
    sample_root: Path,
    sample_name: str,
    *,
    text: str,
    timestamp: str,
    session_id: str,
    source_type: str = "real_channel",
    output_schema_version: str = REAL_OUTPUT_SCHEMA_VERSION,
    trace_schema_version: str = REAL_TRACE_SCHEMA_VERSION,
    delivery_kind: str = "reply",
    outbox_success: bool = True,
) -> Path:
    sample_dir = sample_root / sample_name
    sample_dir.mkdir(parents=True, exist_ok=True)

    raw_update = {
        "update_id": abs(hash(sample_name)) % 100000,
        "message": {
            "message_id": abs(hash(f"{sample_name}:message")) % 100000,
            "date": timestamp,
            "chat": {"id": 8420019401, "type": "private"},
            "from": {"id": 8420019401, "is_bot": False, "username": "moonlight"},
            "text": text,
        },
    }
    normalized_event = {
        "schema_version": "proto_self.v2",
        "event_id": f"evt_{sample_name}",
        "event": {"raw_text": text},
        "conversation_context": {
            "session_id": session_id,
            "thread_id": session_id,
            "turn_id": f"turn_{sample_name}",
        },
        "conversation_summary": {
            "session_id": session_id,
            "thread_id": session_id,
            "turn_id": f"turn_{sample_name}",
        },
    }
    openemotion_result = {
        "schema_version": output_schema_version,
        "event_id": f"evt_{sample_name}",
    }
    openemotion_trace = {
        "schema_version": trace_schema_version,
        "event_id": f"evt_{sample_name}",
    }
    response_plan = {
        "status": "command_result",
        "delivery_kind": delivery_kind,
        "reply_length": len(text),
    }
    outbox_record = {
        "chat_id": 8420019401,
        "message_id": abs(hash(f"{sample_name}:reply")) % 100000,
        "date": timestamp,
        "text_length": len(text),
        "success": outbox_success,
    }

    sample_json = {
        "sample_id": sample_name,
        "timestamp": timestamp,
        "source_type": source_type,
        "channel": "telegram",
        "raw_update": raw_update,
        "normalized_event": normalized_event,
        "openemotion_result": openemotion_result,
        "openemotion_trace": openemotion_trace,
        "response_plan": response_plan,
        "outbox_record": outbox_record,
    }
    ledger_json = {
        "sample_id": sample_name,
        "timestamp": timestamp,
        "source_type": source_type,
        "channel": "telegram",
        "ids": {
            "session_id": session_id,
            "thread_id": session_id,
            "turn_id": f"turn_{sample_name}",
        },
        "inputs": {
            "raw_update": raw_update,
            "normalized_event": normalized_event,
        },
        "openemotion": {
            "result": openemotion_result,
            "trace_payload": openemotion_trace,
        },
        "host": {
            "response_plan": response_plan,
            "outbox_record": outbox_record,
        },
    }
    replay_json = {
        "replay_id": f"replay_{sample_name}",
        "sample_id": sample_name,
        "timestamp": timestamp,
    }

    (sample_dir / "sample.json").write_text(json.dumps(sample_json, indent=2, ensure_ascii=False), encoding="utf-8")
    (sample_dir / "ledger.json").write_text(json.dumps(ledger_json, indent=2, ensure_ascii=False), encoding="utf-8")
    (sample_dir / "replay.json").write_text(json.dumps(replay_json, indent=2, ensure_ascii=False), encoding="utf-8")
    return sample_dir


def _build_admission_grade_sample_set(sample_root: Path) -> None:
    _write_sample(
        sample_root,
        "sample_20260328_191541_743c02b0",
        text="/new",
        timestamp="2026-03-28T19:15:41+00:00",
        session_id="telegram:dm:8420019401",
    )
    _write_sample(
        sample_root,
        "sample_20260328_191554_f778b476",
        text="你好啊",
        timestamp="2026-03-28T19:15:54+00:00",
        session_id="telegram:dm:8420019401",
    )
    _write_sample(
        sample_root,
        "sample_20260328_192536_a18d7479",
        text="你叫什么名字?",
        timestamp="2026-03-28T19:25:36+00:00",
        session_id="telegram:dm:8420019401",
    )
    _write_sample(
        sample_root,
        "sample_20260329_091500_eeee1111",
        text="/new",
        timestamp="2026-03-29T09:15:00+00:00",
        session_id="telegram:dm:8420019401",
    )
    _write_sample(
        sample_root,
        "sample_20260329_091510_ffff2222",
        text="今天心情如何?",
        timestamp="2026-03-29T09:15:10+00:00",
        session_id="telegram:dm:8420019401:reset-2",
    )


class TestDevelopmentalSchema:
    def test_episode_defaults(self):
        episode = DevelopmentalEpisode(
            episode_id="test",
            episode_type="growth",
            phase="MVP16",
        )
        assert episode.description == ""
        assert episode.achievements == []
        assert episode.real_mainline is False

    def test_transition_record_defaults(self):
        transition = TransitionRecord(
            transition_id="test",
            from_phase="MVP15",
            to_phase="MVP16",
        )
        assert transition.approved is False
        assert transition.transition_kind == "phase_change"

    def test_growth_metric(self):
        metric = GrowthMetric(metric_name="test", value=0.8)
        assert metric.value == 0.8
        assert metric.trend == "stable"

    def test_state_serialization(self):
        state = DevelopmentalState()
        state.trajectory.episodes.append(
            DevelopmentalEpisode(
                episode_id="test_ep",
                episode_type="milestone",
                phase="MVP16",
                sample_ref="a/sample.json",
                ledger_ref="a/ledger.json",
                replay_ref="a/replay.json",
            )
        )
        restored = DevelopmentalState(**json.loads(state.model_dump_json()))
        assert len(restored.trajectory.episodes) == 1
        assert restored.trajectory.episodes[0].episode_id == "test_ep"


class TestDevelopmentalManagerPersistence:
    @pytest.fixture(autouse=True)
    def cleanup(self):
        reset_developmental_manager()
        yield
        reset_developmental_manager()

    def test_persistence_save_and_load(self, tmp_path):
        state_path = tmp_path / "test_state.json"

        manager = DevelopmentalManager(state_path=state_path)
        manager.record_episode("test_episode", "MVP16", "Test description")
        manager.update_metric("test_metric", 0.75)

        reset_developmental_manager()
        manager2 = DevelopmentalManager(state_path=state_path)

        assert len(manager2.state.trajectory.episodes) == 1
        assert manager2.state.trajectory.episodes[0].description == "Test description"
        assert manager2.state.metrics["test_metric"].value == 0.75

    def test_reset_with_clear_persistence(self, tmp_path):
        state_path = tmp_path / "to_delete.json"
        manager = DevelopmentalManager(state_path=state_path)
        manager.record_episode("ep1", "MVP16")

        reset_developmental_manager(clear_persistence=True, state_path=manager._state_path)
        assert not state_path.exists()

    def test_reset_without_clear_persistence(self, tmp_path):
        state_path = tmp_path / "to_keep.json"
        manager = DevelopmentalManager(state_path=state_path)
        manager.record_episode("ep1", "MVP16")

        reset_developmental_manager(clear_persistence=False, state_path=state_path)
        assert state_path.exists()


class TestAdmissionGradeProtection:
    @pytest.fixture(autouse=True)
    def cleanup(self):
        reset_developmental_manager()
        yield
        reset_developmental_manager()

    def test_has_real_data_false_after_init(self, tmp_path):
        manager = DevelopmentalManager(state_path=tmp_path / "empty.json")
        assert manager.has_real_data() is False

    def test_manual_episode_transition_and_metric_do_not_flip_has_real_data(self, tmp_path):
        manager = DevelopmentalManager(state_path=tmp_path / "manual_only.json")

        manager.record_episode("milestone", "MVP16")
        manager.record_transition("MVP15", "MVP16")
        manager.update_metric("continuity_score", 0.85)

        summary = manager.get_summary()
        assert manager.has_real_data() is False
        assert summary["has_real_data"] is False
        assert summary["real_episode_count"] == 0
        assert summary["trajectory_refs_present"] is False
        assert summary["admission_inputs_present"] is False

    def test_record_real_mainline_episode_requires_admission_grade_contract(self, tmp_path):
        manager = DevelopmentalManager(state_path=tmp_path / "contract_guard.json")

        with pytest.raises(ValueError):
            manager.record_real_mainline_episode(
                DevelopmentalWritebackEvent(
                    source_type="test_only",
                    session_id="telegram:dm:1",
                    sample_ref="sample.json",
                    ledger_ref="ledger.json",
                    user_turn_kind="natural_language",
                    final_action="reply",
                    outcome_summary="bad source",
                    proto_self_output_schema_version=REAL_OUTPUT_SCHEMA_VERSION,
                    proto_self_trace_schema_version=REAL_TRACE_SCHEMA_VERSION,
                    governance_snapshot={"outbox_success": True},
                    invariant_snapshot={"identity_preserved": True},
                    timestamp=1.0,
                )
            )

        with pytest.raises(ValueError):
            manager.record_real_mainline_episode(
                DevelopmentalWritebackEvent(
                    source_type="real_channel",
                    session_id="telegram:dm:1",
                    sample_ref="sample.json",
                    ledger_ref="ledger.json",
                    user_turn_kind="command",
                    final_action="reply",
                    outcome_summary="bad turn kind",
                    proto_self_output_schema_version=REAL_OUTPUT_SCHEMA_VERSION,
                    proto_self_trace_schema_version=REAL_TRACE_SCHEMA_VERSION,
                    governance_snapshot={"outbox_success": True},
                    invariant_snapshot={"identity_preserved": True},
                    timestamp=1.0,
                )
            )


class TestRealTrajectoryProjection:
    @pytest.fixture(autouse=True)
    def cleanup(self):
        reset_developmental_manager()
        yield
        reset_developmental_manager()

    def test_sync_real_projection_imports_only_eligible_real_mainline_samples_and_writes_artifacts(self, tmp_path):
        state_path = tmp_path / "developmental_state.json"
        sample_root = tmp_path / "real_telegram"
        observation_dir = tmp_path / "observation"
        _build_admission_grade_sample_set(sample_root)

        manager = DevelopmentalManager(state_path=state_path)
        summary = manager.sync_real_projection_from_sample_artifacts(
            sample_artifacts_dir=sample_root,
            observation_dir=observation_dir,
        )

        assert summary["sync_status"] == "synced"
        assert summary["has_real_data"] is True
        assert summary["real_episode_count"] == 3
        assert summary["real_session_count"] == 2
        assert summary["real_day_count"] == 2
        assert summary["session_reset_transition_count"] == 1
        assert summary["calendar_rollover_transition_count"] == 1
        assert summary["trajectory_refs_present"] is True
        assert summary["replay_refs_present"] is True
        assert summary["admission_inputs_present"] is True
        assert summary["eligible_samples_found"] == 3
        assert summary["imported_real_episode_count"] == 3

        real_episodes = manager.get_real_mainline_episodes()
        assert len(real_episodes) == 3
        assert all(ep.real_mainline for ep in real_episodes)
        assert all(ep.sample_ref and ep.ledger_ref and ep.replay_ref for ep in real_episodes)

        index_path = observation_dir / "real_trajectory_index.json"
        audit_path = observation_dir / "real_trajectory_replay_audit.json"
        assert index_path.exists()
        assert audit_path.exists()

        index_payload = json.loads(index_path.read_text(encoding="utf-8"))
        audit_payload = json.loads(audit_path.read_text(encoding="utf-8"))

        assert index_payload["summary"]["admission_inputs_present"] is True
        assert len(index_payload["episodes"]) == 3
        assert index_payload["transitions"][0]["transition_kind"] == "session_reset"
        assert index_payload["transitions"][1]["transition_kind"] == "calendar_rollover"
        assert audit_payload["identity_preserved"] is True
        assert audit_payload["governance_preserved"] is True
        assert audit_payload["source_refs_intact"] is True

    def test_command_turns_and_wrong_schema_samples_do_not_count(self, tmp_path):
        state_path = tmp_path / "filtered_state.json"
        sample_root = tmp_path / "real_telegram"

        _write_sample(
            sample_root,
            "sample_20260328_200001_aaaa0001",
            text="/help",
            timestamp="2026-03-28T20:00:01+00:00",
            session_id="telegram:dm:8420019401",
        )
        _write_sample(
            sample_root,
            "sample_20260328_200011_bbbb0002",
            text="这条样本 trace 版本不对",
            timestamp="2026-03-28T20:00:11+00:00",
            session_id="telegram:dm:8420019401",
            trace_schema_version="proto_self.trace.v1",
        )

        manager = DevelopmentalManager(state_path=state_path)
        summary = manager.sync_real_projection_from_sample_artifacts(sample_artifacts_dir=sample_root)

        assert summary["has_real_data"] is False
        assert summary["real_episode_count"] == 0
        assert summary["eligible_samples_found"] == 0
        assert summary["imported_real_episode_count"] == 0
        assert manager.get_real_mainline_episodes() == []


class TestResetBehavior:
    @pytest.fixture(autouse=True)
    def cleanup(self):
        reset_developmental_manager()
        yield
        reset_developmental_manager()

    def test_reset_clears_singleton_instance(self, tmp_path):
        state_path = tmp_path / "reset_test.json"
        manager = DevelopmentalManager(state_path=state_path)
        manager.record_episode("ep1", "MVP16")

        reset_developmental_manager()
        assert DevelopmentalManager._instance is None
        assert get_developmental_manager(state_path=state_path) is not None

    def test_reset_without_clear_keeps_persisted_data(self, tmp_path):
        state_path = tmp_path / "keep_data.json"
        manager = DevelopmentalManager(state_path=state_path)
        manager.record_episode("ep1", "MVP16", "Saved episode")

        reset_developmental_manager(clear_persistence=False, state_path=state_path)

        manager2 = DevelopmentalManager(state_path=state_path)
        assert len(manager2.state.trajectory.episodes) == 1
        assert manager2.state.trajectory.episodes[0].description == "Saved episode"


class TestIncrementalObservation:
    @pytest.fixture(autouse=True)
    def cleanup(self):
        reset_developmental_manager()
        yield
        reset_developmental_manager()

    def test_episode_increment(self, tmp_path):
        manager = DevelopmentalManager(state_path=tmp_path / "incremental.json")
        manager.record_episode("milestone", "MVP16", "Episode 1")
        manager.record_episode("milestone", "MVP16", "Episode 2")
        manager.record_episode("milestone", "MVP16", "Episode 3")

        assert len(manager.state.trajectory.episodes) == 3

    def test_transition_increment(self, tmp_path):
        manager = DevelopmentalManager(state_path=tmp_path / "trans_incremental.json")
        manager.record_transition("MVP14", "MVP15")
        manager.record_transition("MVP15", "MVP16")

        assert len(manager.state.trajectory.transitions) == 2
        assert manager.state.trajectory.current_phase == "MVP16"

    def test_metric_history_tracking(self, tmp_path):
        manager = DevelopmentalManager(state_path=tmp_path / "metric_history.json")
        manager.update_metric("continuity_score", 0.7)
        manager.update_metric("continuity_score", 0.8)
        manager.update_metric("continuity_score", 0.9)

        metric = manager.state.metrics["continuity_score"]
        assert len(metric.history) >= 2
        assert metric.value == 0.9
        assert metric.trend == "improving"


class TestExitCriteria:
    @pytest.fixture(autouse=True)
    def cleanup(self):
        reset_developmental_manager()
        yield
        reset_developmental_manager()

    def test_governed_growth_transition(self, tmp_path):
        manager = DevelopmentalManager(state_path=tmp_path / "governed.json")
        transition = manager.record_transition("MVP15", "MVP16", approved=True, approver="governor")
        assert transition.approved is True

    def test_identity_preservation_default(self, tmp_path):
        manager = DevelopmentalManager(state_path=tmp_path / "identity.json")
        manager.record_episode("test", "MVP16")
        assert manager.check_identity_preservation() is True

    def test_continuity_score_bounds(self, tmp_path):
        manager = DevelopmentalManager(state_path=tmp_path / "score.json")
        manager.update_metric("continuity_score", 0.85)
        score = manager.get_continuity_score()
        assert 0.0 <= score <= 1.0


class TestSingletonBehavior:
    @pytest.fixture(autouse=True)
    def cleanup(self):
        reset_developmental_manager()
        yield
        reset_developmental_manager()

    def test_singleton_returns_same_instance(self, tmp_path):
        path = tmp_path / "singleton.json"
        assert get_developmental_manager(state_path=path) is get_developmental_manager(state_path=path)

    def test_singleton_with_different_paths_after_reset(self, tmp_path):
        path1 = tmp_path / "path1.json"
        path2 = tmp_path / "path2.json"

        m1 = get_developmental_manager(state_path=path1)
        m1.record_episode("ep1", "MVP16")

        reset_developmental_manager()
        m2 = get_developmental_manager(state_path=path2)

        assert m1 is not m2
        assert len(m2.state.trajectory.episodes) == 0
