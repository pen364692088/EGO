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

from run_mvp15_controlled_observation import run_controlled_observation  # noqa: E402
from openemotion.reflective_self import ReflectiveSelfOwner  # noqa: E402


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
        "ingress_text": "先把这次反思留成候选。",
        "runtime_status": "completed_verified",
        "runtime_reply_text": "先保持 proposal-only。",
        "delivery_event_id": "delivery_001",
        "delivery_created_at": now,
        "delivery_text": "先保持 proposal-only。",
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
    runtime = SimpleNamespace(proto_self_runtime=SimpleNamespace(reflective_self_store=None))

    monkeypatch.setattr(
        "run_mvp15_controlled_observation.init_runtime",
        lambda: runtime,
    )

    async def _fake_session(*, messages, session_id, runtime, resource_budget_hint, maintenance_context):
        store = runtime.proto_self_runtime.reflective_self_store
        owner = ReflectiveSelfOwner(store=store)
        owner.upsert_target(
            target_id="decision:target",
            target_type="decision",
            reference="decision:target",
            reason="test_observation",
            salience=0.8,
        )
        proposal = owner.propose_revision(
            target_layer="decision:target",
            proposed_change={"candidate_id": "reflection_candidate:decision:target"},
            justification="test observation proposal",
            required_gate="reflection_writeback_gate",
        )
        owner.set_proposal_gate_status(
            proposal.proposal_id,
            status="held",
            gate_verdict="allow_writeback",
            gate_reference="trace:mvp15:test_observation",
            reason="proposal_only_candidate_recorded",
        )
        record = owner.persist(
            update_source="proto_self_v2",
            trace_reference="trace:mvp15:test_observation",
        )
        fake_state = SimpleNamespace(
            proto_self_context={
                "reflective_self_delta": {
                    "revision_proposals": [{"candidate_id": "reflection_candidate:decision:target"}],
                    "target_ids": ["decision:target"],
                    "surface_reasons": ["reflection_pressure"],
                },
                "revision_proposal_candidates": [
                    {
                        "candidate_id": "reflection_candidate:decision:target",
                        "target_id": "decision:target",
                        "required_gate": "reflection_writeback_gate",
                        "proposal_discipline": "proposal_only",
                    }
                ],
                "reflection_writeback_candidate": {
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "none",
                    "required_gate": "reflection_writeback_gate",
                    "target_ids": ["decision:target"],
                },
                "reflective_self_writeback": {
                    "decision": {
                        "gate_verdict": "allow_writeback",
                        "changed_fields": ["reflection_targets", "revision_proposals"],
                        "proposal_count": 1,
                    },
                    "record": {
                        "revision_id": record.revision_id,
                        "model_version": record.model_version,
                        "trace_reference": record.trace_reference,
                        "state_hash": record.state_hash,
                    },
                    "trace_reference": "trace:update_packet",
                },
                "confidence_adjustment_hints": {"certainty_bound": "bounded"},
                "maintenance_priority_hints": {"reflection_followup_priority": "elevated"},
            }
        )
        return runtime, fake_state, [_fake_record(session_id)]

    monkeypatch.setattr(
        "run_mvp15_controlled_observation._run_runtime_reflective_observation_session",
        _fake_session,
    )

    payload = await run_controlled_observation(
        messages=["先把这次反思留成候选。"],
        session_id="session:mvp15:test",
        output_json=tmp_path / "current.json",
        artifacts_dir=tmp_path / "artifacts",
    )

    assert payload["status"] == "pass"
    assert payload["verification_level"] == "V4"
    assert payload["evidence_level"] == "E4"
    assert payload["reflection_candidate_present"] is True
    assert payload["latest_revision"]["revision_id"].startswith("reflective_rev_")
    assert payload["replay_valid"] is True
    assert (tmp_path / "current.json").exists()
    assert (tmp_path / "current.md").exists()
