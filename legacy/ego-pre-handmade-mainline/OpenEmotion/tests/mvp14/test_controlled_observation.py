from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[3]
TOOLS_ROOT = ROOT / "OpenEmotion" / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from run_mvp14_controlled_observation import run_controlled_observation  # noqa: E402
from openemotion.endogenous_drives import EndogenousDriveOwner  # noqa: E402
from openemotion.endogenous_drives.reducers import seed_default_state  # noqa: E402


def _fake_record(session_id: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": "observation_record.v1",
        "observation_source": "direct_real",
        "transport_source": "runtime_harness",
        "source": "runtime_harness",
        "session_id": session_id,
        "turn_id": "turn_001",
        "ingress_event_id": "ingress_001",
        "ingress_created_at": now,
        "ingress_text": "先补维护债。",
        "runtime_status": "completed_verified",
        "runtime_reply_text": "先把状态收稳。",
        "delivery_event_id": "delivery_001",
        "delivery_created_at": now,
        "delivery_text": "先把状态收稳。",
        "reply_authority": "response_contract.output_check",
        "reply_origin": "model_chat",
        "delivery_kind": "chat",
        "delivery_authority_source": "response_contract.output_check",
        "output_check_reason": "ok",
        "intent_gate_status": "allow",
        "intent_gate_reason": "ok",
    }


@pytest.mark.asyncio
async def test_run_controlled_observation_writes_pass_report(tmp_path, monkeypatch):
    runtime = SimpleNamespace(proto_self_runtime=SimpleNamespace(endogenous_drive_store=None))

    monkeypatch.setattr(
        "run_mvp14_controlled_observation.init_runtime",
        lambda: runtime,
    )

    async def _fake_session(*, messages, session_id, runtime, resource_budget_hint, maintenance_context):
        store = runtime.proto_self_runtime.endogenous_drive_store
        owner = EndogenousDriveOwner(initial_state=store.load() or seed_default_state(), store=store)
        owner.add_maintenance_debt(
            category="replay_verification",
            amount=0.25,
            priority=0.9,
            source="test_observation",
        )
        record = owner.persist(
            update_source="proto_self_v2",
            trace_reference="trace:mvp14:test_observation",
        )
        fake_state = SimpleNamespace(
            proto_self_context={
                "endogenous_drive_delta": {
                    "maintenance_debts": [
                        {
                            "category": "replay_verification",
                            "amount": 0.25,
                            "priority": 0.9,
                            "source": "maintenance_context",
                        }
                    ]
                },
                "endogenous_drive_writeback": {
                    "decision": {
                        "gate_verdict": "allow_writeback",
                        "changed_fields": ["maintenance_debt", "priority_snapshot"],
                    },
                    "record": {
                        "revision_id": record.revision_id,
                        "model_version": record.model_version,
                        "trace_reference": record.trace_reference,
                        "state_hash": record.state_hash,
                    },
                    "trace_reference": "trace:update_packet",
                },
                "drive_state_snapshot": {
                    "schema_version": "mvp14-owner-v1",
                    "owner_revision": record.model_version,
                },
                "priority_snapshot": {
                    "dominant_drive": "repair",
                    "bias_terms": {"repair": 0.4},
                },
                "candidate_bias_terms": {"repair": 0.4},
                "self_maintenance_candidate": {
                    "category": "self_maintenance",
                    "dominant_issue": "maintenance_debt",
                    "priority": 0.85,
                },
            }
        )
        return runtime, fake_state, [_fake_record(session_id)]

    monkeypatch.setattr(
        "run_mvp14_controlled_observation._run_runtime_drive_observation_session",
        _fake_session,
    )

    payload = await run_controlled_observation(
        messages=["先补维护债。"],
        session_id="session:mvp14:test",
        output_json=tmp_path / "current.json",
        artifacts_dir=tmp_path / "artifacts",
    )

    assert payload["status"] == "pass"
    assert payload["verification_level"] == "V4"
    assert payload["evidence_level"] == "E4"
    assert payload["maintenance_candidate_present"] is True
    assert payload["latest_revision"]["revision_id"].startswith("drive_rev_")
    assert payload["replay_valid"] is True
    assert (tmp_path / "current.json").exists()
    assert (tmp_path / "current.md").exists()
