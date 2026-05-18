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

from run_mvp17_controlled_observation import run_controlled_observation  # noqa: E402
from openemotion.social_self import (  # noqa: E402
    BoundaryMode,
    CommitmentStatus,
    RelationshipContinuityStatus,
    SocialSelfOwner,
)


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
        "ingress_text": "先把关系修复候选留成 proposal-only。",
        "runtime_status": "completed_verified",
        "runtime_reply_text": "先走受治理 social writeback。",
        "delivery_event_id": "delivery_001",
        "delivery_created_at": now,
        "delivery_text": "先走受治理 social writeback。",
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
    runtime = SimpleNamespace(proto_self_runtime=SimpleNamespace(social_self_store=None))

    monkeypatch.setattr(
        "run_mvp17_controlled_observation.init_runtime",
        lambda: runtime,
    )

    async def _fake_session(
        *,
        messages,
        session_id,
        runtime,
        resource_budget_hint,
        maintenance_context,
        social_context,
    ):
        store = runtime.proto_self_runtime.social_self_store
        owner = SocialSelfOwner(store=store)
        owner.upsert_relation_memory(
            counterpart_id="telegram:8420019401",
            relationship_summary="bounded repair review",
            continuity_status=RelationshipContinuityStatus.STRAINED,
            source_refs=["trace:mvp17:test_observation"],
        )
        owner.set_trust_state(
            counterpart_id="telegram:8420019401",
            trust_level=0.68,
            trust_basis=["trust_drift", "commitment_breach"],
            trust_delta=-0.24,
        )
        owner.record_commitment(
            counterpart_id="telegram:8420019401",
            summary="repair the strained social continuity",
            status=CommitmentStatus.BREACHED,
            source_refs=["trace:mvp17:test_observation"],
        )
        owner.set_social_boundary(
            counterpart_id="telegram:8420019401",
            caution_level=0.72,
            boundary_mode=BoundaryMode.CAUTIOUS,
            reason="repair_review_guard",
            source_refs=["trace:mvp17:test_observation"],
        )
        proposal = owner.propose_repair(
            counterpart_id="telegram:8420019401",
            issue_summary="commitment breach requires bounded repair",
            proposed_adjustment={"repair_bias": "elevated"},
            justification="test observation proposal",
            source_refs=["trace:mvp17:test_observation"],
        )
        owner.set_repair_status(proposal.proposal_id, status=proposal.status.HELD)
        record = owner.persist(
            update_source="proto_self_v2",
            trace_reference="trace:mvp17:test_observation",
        )
        fake_state = SimpleNamespace(
            proto_self_context={
                "social_self_delta": {
                    "proposal_candidate_count": 1,
                    "counterpart_id": "telegram:8420019401",
                    "relationship_continuity": "strained",
                    "surface_reasons": ["trust_drift", "commitment_breach", "unresolved_repair"],
                },
                "relation_update_candidates": [
                    {
                        "candidate_id": "relation_update:telegram:8420019401:2",
                        "counterpart_id": "telegram:8420019401",
                        "relationship_event": "commitment_breach",
                        "relationship_continuity": "strained",
                        "required_gate": "social_writeback_gate",
                        "proposal_discipline": "proposal_only",
                        "behavioral_authority": "none",
                        "promotion_level": "controlled_axis",
                    }
                ],
                "trust_commitment_snapshot": {
                    "counterpart_id": "telegram:8420019401",
                    "trust_signal_max": 0.68,
                    "open_commitment_count": 0,
                    "breached_commitment_count": 1,
                    "pending_repair_count": 1,
                    "boundary_caution_max": 0.72,
                    "relationship_continuity": "strained",
                    "trust_drift": -0.24,
                },
                "social_policy_hints": {
                    "relationship_continuity": "strained",
                    "trust_bias": "guarded",
                    "commitment_guard": "strict",
                    "repair_bias": "elevated",
                    "boundary_mode": "cautious",
                    "counterpart_id": "telegram:8420019401",
                },
                "repair_proposal_candidates": [
                    {
                        "candidate_id": "repair_candidate:telegram:8420019401:3",
                        "counterpart_id": "telegram:8420019401",
                        "reason": "social_repair",
                        "surface_reasons": ["trust_drift", "commitment_breach", "unresolved_repair"],
                        "required_gate": "social_writeback_gate",
                        "proposal_discipline": "proposal_only",
                        "behavioral_authority": "none",
                        "promotion_level": "controlled_axis",
                    }
                ],
                "social_writeback_candidate": {
                    "source": "proto_self_v2",
                    "contract_version": "mvp17.social_contract.v1",
                    "counterpart_id": "telegram:8420019401",
                    "required_gate": "social_writeback_gate",
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "none",
                    "promotion_level": "controlled_axis",
                    "surface_reasons": ["trust_drift", "commitment_breach", "unresolved_repair"],
                    "owner_revision": record.model_version,
                },
                "social_context": dict(social_context),
                "social_writeback": {
                    "decision": {
                        "gate_verdict": "allow_writeback",
                        "changed_fields": [
                            "relation_memory",
                            "trust_state",
                            "commitment_state",
                            "repair_state",
                            "social_boundary_state",
                            "governance_ledger",
                        ],
                        "proposal_count": 1,
                        "relation_candidate_count": 1,
                    },
                    "record": {
                        "revision_id": record.revision_id,
                        "model_version": record.model_version,
                        "trace_reference": record.trace_reference,
                        "state_hash": record.state_hash,
                    },
                    "trace_reference": "trace:update_packet",
                },
            }
        )
        return runtime, fake_state, [_fake_record(session_id)]

    monkeypatch.setattr(
        "run_mvp17_controlled_observation._run_runtime_social_observation_session",
        _fake_session,
    )

    payload = await run_controlled_observation(
        messages=["先把关系修复候选留成 proposal-only。"],
        session_id="session:mvp17:test",
        output_json=tmp_path / "current.json",
        artifacts_dir=tmp_path / "artifacts",
    )

    assert payload["status"] == "pass"
    assert payload["verification_level"] == "V4"
    assert payload["evidence_level"] == "E4"
    assert payload["social_writeback_gate"] == "allow_writeback"
    assert payload["social_proposal_present"] is True
    assert payload["proposal_only_discipline_consistent"] is True
    assert payload["behavioral_authority_none"] is True
    assert payload["bounded_influence_present"] is True
    assert payload["latest_revision"]["revision_id"].startswith("social_rev_")
    assert payload["replay_valid"] is True
    assert (tmp_path / "current.json").exists()
    assert (tmp_path / "current.md").exists()
