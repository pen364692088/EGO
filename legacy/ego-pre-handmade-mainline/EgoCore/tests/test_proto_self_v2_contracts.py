from __future__ import annotations

from datetime import datetime

from app.openemotion_adapter.proto_self_adapter import ProtoSelfAdapter, normalize_to_proto_self_input
from app.openemotion_adapter.proto_self_contract_validator import validate_proto_self_v2_payload
from openemotion.proto_self_v2.schemas import UpdatePacketV2
from openemotion.proto_self_v2.seed_schemas import SEED_SUBJECT_PROFILE


def test_normalize_to_proto_self_input_builds_v2_packet():
    packet = normalize_to_proto_self_input(
        {
            "schema_version": "proto_self.v2",
            "event_id": "evt_v2_001",
            "timestamp": datetime.now().isoformat(),
            "event": {
                "actor": "user",
                "source": "telegram",
                "event_type": "user_message",
                "user_intent": "read file",
                "raw_text": "read file app.py",
            },
            "conversation_summary": {"session_id": "session:test", "turn_id": "turn_001"},
            "task_summary": {"pending_tasks": 1, "blocked_tasks": 0},
            "runtime_summary": {"runtime": "runtime_v2", "state_scope": "agent_global"},
            "safety_context": {"risk": "high"},
        }
    )

    assert isinstance(packet, UpdatePacketV2)
    assert packet.safety_context == {"risk_level": "high"}


def test_adapter_handle_event_supports_v2_contract(tmp_path):
    adapter = ProtoSelfAdapter(mirror_dir=tmp_path / "mirror")
    payload = {
        "schema_version": "proto_self.v2",
        "event_id": "evt_v2_002",
        "timestamp": datetime.now().isoformat(),
        "event": {
            "actor": "user",
            "source": "telegram",
            "event_type": "user_message",
            "user_intent": "read file",
            "raw_text": "read file app.py",
        },
        "conversation_summary": {"session_id": "session:test", "thread_id": "session:test", "turn_id": "turn_001"},
        "task_summary": {"pending_tasks": 1, "blocked_tasks": 0},
        "runtime_summary": {"runtime": "runtime_v2", "state_scope": "agent_global"},
        "safety_context": {"risk_level": "medium"},
        "prediction_snapshot_prev": {"expected_success": True},
    }

    result = adapter.handle_event(payload)

    assert result["schema_version"] == "proto_self.output.v2"
    assert result["event_id"] == "evt_v2_002"
    assert result["trace_payload"]["schema_version"] == "proto_self.trace.v2"
    assert result["trace_payload"]["update_packet_hash"]


def test_adapter_handle_event_accepts_runtime_self_model_context(tmp_path):
    adapter = ProtoSelfAdapter(mirror_dir=tmp_path / "mirror")
    payload = {
        "schema_version": "proto_self.v2",
        "event_id": "evt_v2_ctx_001",
        "timestamp": datetime.now().isoformat(),
        "event": {
            "actor": "user",
            "source": "telegram",
            "event_type": "user_message",
            "user_intent": "continue discussion",
            "raw_text": "继续",
        },
        "conversation_summary": {"session_id": "session:test", "thread_id": "session:test", "turn_id": "turn_001"},
        "task_summary": {"pending_tasks": 0, "blocked_tasks": 0},
        "runtime_summary": {
            "runtime": "runtime_v2",
            "state_scope": "agent_global",
            "self_model_context": {
                "schema_version": "1.0.0",
                "identity_handle": "openemotion",
                "capabilities": [{"capability_id": "cap_reasoning"}],
                "limitations": [{"limitation_id": "lim_no_gui"}],
                "active_goals": [{"goal_id": "goal_owner"}],
                "standing_commitments": [{"commitment_id": "stay_governed", "binding_level": "hard"}],
                "confidence_by_domain": {"reasoning": 0.9},
                "known_unknowns": [],
                "created_at": "2026-04-02T00:00:00Z",
                "last_modified_at": "2026-04-02T00:00:00Z",
                "modification_audit_trail": [],
            },
        },
        "safety_context": {"risk_level": "low"},
    }

    result = adapter.handle_event(payload)

    assert result["schema_version"] == "proto_self.output.v2"
    assert result["trace_payload"]["constraint_summary"]["self_model_context"]["identity_handle"] == "openemotion"


def test_adapter_handle_event_accepts_runtime_endogenous_drive_context(tmp_path):
    adapter = ProtoSelfAdapter(mirror_dir=tmp_path / "mirror")
    payload = {
        "schema_version": "proto_self.v2",
        "event_id": "evt_v2_drive_ctx_001",
        "timestamp": datetime.now().isoformat(),
        "event": {
            "actor": "user",
            "source": "telegram",
            "event_type": "user_message",
            "user_intent": "continue discussion",
            "raw_text": "继续",
        },
        "conversation_summary": {"session_id": "session:test", "thread_id": "session:test", "turn_id": "turn_001"},
        "task_summary": {"pending_tasks": 0, "blocked_tasks": 0},
        "runtime_summary": {
            "runtime": "runtime_v2",
            "state_scope": "agent_global",
            "endogenous_drive_context": {
                "schema_version": "mvp14-owner-v1",
                "owner_revision": 3,
                "last_revision_id": "drive_rev_000003",
                "active_drives": [
                    {
                        "drive_id": "verification",
                        "drive_type": "verification",
                        "intensity": 0.9,
                        "persistence": 0.8,
                        "candidate_bias": 0.0,
                        "pressure": 0.72,
                    },
                    {
                        "drive_id": "completion",
                        "drive_type": "completion",
                        "intensity": 0.7,
                        "persistence": 0.7,
                        "candidate_bias": 0.0,
                        "pressure": 0.49,
                    },
                ],
                "homeostatic_signals": [],
                "maintenance_debt": [],
                "priority_snapshot": {
                    "dominant_drive": "verification",
                    "bias_terms": {"verification": 0.72, "completion": 0.49},
                },
                "summary": {"total_maintenance_debt": 0.0},
                "self_maintenance_candidate": None,
            },
            "resource_budget_hint": {"reserve_level": "normal"},
            "maintenance_context": {},
            "recent_delivery_outcome": {"success": True, "status": "sent"},
        },
        "safety_context": {"risk_level": "low"},
    }

    result = adapter.handle_event(payload)

    assert result["schema_version"] == "proto_self.output.v2"
    assert result["trace_payload"]["constraint_summary"]["endogenous_drive_context"]["owner_revision"] == 3
    assert result["trace_payload"]["retrieval_summary"]["endogenous_drive_context_present"] is True
    assert result["candidate_bias_terms"]["verification"] == 0.72
    assert result["policy_hint"]["risk_bias"] == "high"


def test_adapter_handle_event_supports_seed_profile_contract(tmp_path):
    adapter = ProtoSelfAdapter(mirror_dir=tmp_path / "mirror")
    payload = {
        "schema_version": "proto_self.v2",
        "event_id": "evt_seed_001",
        "timestamp": datetime.now().isoformat(),
        "event": {
            "actor": "system",
            "source": "runtime",
            "event_type": "idle_check",
            "user_intent": None,
            "raw_text": None,
        },
        "subject_profile": SEED_SUBJECT_PROFILE,
        "seed_event": {
            "schema_version": "proto_self_seed.v0.2",
            "event_type": "idle_check",
            "source": "runtime",
            "payload": {"resolved_target_path": "app.py"},
            "runtime_summary": {
                "request_mode": "write",
                "resolved_target_path": "app.py",
                "active_task": False,
            },
            "safety_context": {"risk_level": "low", "blocked": False},
        },
        "conversation_summary": {"session_id": "session:test", "thread_id": "session:test", "turn_id": "turn_001"},
        "task_summary": {"pending_tasks": 1, "blocked_tasks": 0},
        "runtime_summary": {"runtime": "runtime_v2", "state_scope": "agent_global", "request_mode": "write"},
        "safety_context": {"risk_level": "low"},
        "prediction_snapshot_prev": {},
    }

    result = adapter.handle_event(payload)

    assert result["schema_version"] == "proto_self.output.v2"
    assert result["subject_profile"] == SEED_SUBJECT_PROFILE
    assert result["candidate_actions"]
    assert result["trace_payload"]["subject_profile"] == SEED_SUBJECT_PROFILE
    assert result["trace_payload"]["candidate_actions"]


def test_validate_proto_self_v2_payload_rejects_missing_event():
    payload = {
        "schema_version": "proto_self.v2",
        "event_id": "evt_v2_bad",
        "timestamp": datetime.now().isoformat(),
        "runtime_summary": {"runtime": "runtime_v2"},
        "task_summary": {},
        "conversation_summary": {},
        "safety_context": {"risk_level": "low"},
    }

    try:
        validate_proto_self_v2_payload(payload)
    except ValueError as exc:
        assert "event" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing required event")


def test_validate_proto_self_v2_payload_rejects_seed_profile_without_seed_event():
    payload = {
        "schema_version": "proto_self.v2",
        "event_id": "evt_v2_seed_bad",
        "timestamp": datetime.now().isoformat(),
        "event": {
            "actor": "user",
            "source": "telegram",
            "event_type": "user_message",
        },
        "subject_profile": SEED_SUBJECT_PROFILE,
        "runtime_summary": {"runtime": "runtime_v2"},
        "task_summary": {},
        "conversation_summary": {},
        "safety_context": {"risk_level": "low"},
    }

    try:
        validate_proto_self_v2_payload(payload)
    except ValueError as exc:
        assert "seed_event" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing seed_event")


def test_validate_proto_self_v2_payload_allows_developmental_seed_without_seed_event():
    payload = {
        "schema_version": "proto_self.v2",
        "event_id": "evt_v2_dev_seed",
        "timestamp": datetime.now().isoformat(),
        "event": {
            "actor": "system",
            "source": "runtime",
            "event_type": "developmental_tick",
        },
        "subject_profile": SEED_SUBJECT_PROFILE,
        "runtime_summary": {
            "runtime": "runtime_v2",
            "developmental_mode": "shadow_observe",
            "observation_source": "synthetic",
        },
        "task_summary": {},
        "conversation_summary": {},
        "safety_context": {"risk_level": "low"},
        "intervention_context": {"developmental_input": {}},
    }

    validate_proto_self_v2_payload(payload)
