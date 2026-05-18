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

from run_mvp20_controlled_observation import run_controlled_observation  # noqa: E402
from openemotion.initiative_self import (  # noqa: E402
    CommitmentContinuityStatus,
    HostProactiveCandidateStatus,
    InitiativePriority,
    InitiativeProposalStatus,
    InitiativeSelfOwner,
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
        "ingress_text": "先把 initiative proposal 保持在 gate 里。",
        "runtime_status": "completed_verified",
        "runtime_reply_text": "先走受治理 initiative writeback。",
        "delivery_event_id": "delivery_001",
        "delivery_created_at": now,
        "delivery_text": "先走受治理 initiative writeback。",
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
    runtime = SimpleNamespace(proto_self_runtime=SimpleNamespace(initiative_self_store=None))

    monkeypatch.setattr(
        "run_mvp20_controlled_observation.init_runtime",
        lambda: runtime,
    )

    async def _fake_session(
        *,
        messages,
        session_id,
        runtime,
        resource_budget_hint,
        maintenance_context,
        initiative_context,
    ):
        store = runtime.proto_self_runtime.initiative_self_store
        owner = InitiativeSelfOwner(store=store)
        owner.set_initiative_state(
            dominant_mode=InitiativePriority.REVIEW,
            initiative_pressure=0.78,
            commitment_carryover_bias=0.82,
            recent_delivery_sensitivity=0.41,
            rationale_summary="test observation bounded initiative continuity",
            source_refs=["trace:mvp20:test_observation"],
        )
        owner.set_initiative_priority_state(
            selected_priority=InitiativePriority.CARRY_FORWARD,
            hold_weight=0.21,
            review_weight=0.54,
            prepare_weight=0.33,
            carry_forward_weight=0.88,
            schedule_weight=0.14,
            priority_reason="bounded carry-forward remains active under host review",
            upstream_pressure_sources=["wp14:selfhood_integration", "wp12:social_commitment_continuity"],
            source_refs=["trace:mvp20:test_observation"],
        )
        owner.set_commitment_continuity_state(
            status=CommitmentContinuityStatus.ACTIVE,
            active_commitments_count=2,
            carried_commitment_refs=["commitment:followup:bounded", "commitment:repair_review:bounded"],
            blocked_commitment_refs=[],
            continuity_confidence=0.79,
            carryover_summary="bounded followup continuity remains active",
            source_refs=["trace:mvp20:test_observation"],
        )
        proposal = owner.propose_initiative(
            proposal_label="carry_forward_commitment_under_review",
            priority_mode=InitiativePriority.CARRY_FORWARD,
            proposed_effects={"initiative_policy_hints": {"initiative_bias": "carry_forward"}},
            justification="test observation proposal",
            source_refs=["trace:mvp20:test_observation"],
        )
        owner.set_initiative_proposal_status(status=InitiativeProposalStatus.HELD)
        host_candidate = owner.set_host_proactive_candidate(
            candidate_label="governed_host_proactive_followup",
            continuity_basis="commitment:followup:bounded",
            source_refs=["trace:mvp20:test_observation"],
        )
        owner.set_host_proactive_candidate_status(status=HostProactiveCandidateStatus.HELD)
        owner.record_initiative_event(
            event_type="initiative_writeback",
            reference_id=proposal.proposal_id,
            gate_verdict="allow_writeback",
            details={"host_candidate_id": host_candidate.candidate_id},
        )
        record = owner.persist(
            update_source="proto_self_v2",
            trace_reference="trace:mvp20:test_observation",
        )
        fake_state = SimpleNamespace(
            proto_self_context={
                "initiative_self_delta": {
                    "proposal_candidate_count": 1,
                    "selected_priority": "carry_forward",
                    "commitment_mode": "carry_forward",
                    "host_proactive_mode": "candidate",
                    "surface_reasons": [
                        "initiative_pressure",
                        "commitment_carryover",
                        "active_commitments",
                        "idle_window",
                    ],
                },
                "initiative_proposal_candidates": [
                    {
                        "proposal_id": proposal.proposal_id,
                        "proposal_label": "carry_forward_commitment_under_review",
                        "priority_mode": "carry_forward",
                        "required_gate": "initiative_writeback_gate",
                        "effect_scope": "proposal_only",
                        "behavioral_authority": "none",
                        "requested_effects": ["governed_initiative_review"],
                    }
                ],
                "commitment_execution_snapshot": {
                    "selected_priority": "carry_forward",
                    "active_commitments_count": 2,
                    "blocked_commitments_count": 0,
                    "continuity_confidence": 0.79,
                    "commitment_mode": "carry_forward",
                    "reserve_level": "medium",
                    "recent_delivery_status": "sent",
                    "idle_seconds": 1800.0,
                    "integrated_priority": "grow",
                },
                "initiative_policy_hints": {
                    "initiative_bias": "carry_forward",
                    "continuity_mode": "stable",
                    "commitment_mode": "carry_forward",
                    "host_proactive_mode": "candidate",
                    "reserve_bias": "bounded",
                    "delivery_bias": "normal",
                },
                "host_proactive_candidate": {
                    "candidate_id": host_candidate.candidate_id,
                    "candidate_label": "governed_host_proactive_followup",
                    "continuity_basis": "commitment:followup:bounded",
                    "host_lane_hint": "host_proactive_outbox",
                    "required_gate": "initiative_writeback_gate",
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "none",
                    "requested_effects": ["governed_host_proactive_review"],
                    "promotion_level": "controlled_axis",
                },
                "initiative_writeback_candidate": {
                    "source": "proto_self_v2",
                    "contract_version": "mvp20.initiative_contract.v1",
                    "required_gate": "initiative_writeback_gate",
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "none",
                    "promotion_level": "controlled_axis",
                    "selected_priority": "carry_forward",
                    "surface_reasons": [
                        "initiative_pressure",
                        "commitment_carryover",
                        "active_commitments",
                        "idle_window",
                    ],
                    "owner_revision": record.model_version,
                },
                "initiative_context": dict(initiative_context),
                "initiative_writeback": {
                    "decision": {
                        "gate_verdict": "allow_writeback",
                        "changed_fields": [
                            "initiative_state",
                            "initiative_priority_state",
                            "commitment_continuity_state",
                            "initiative_proposal_candidate",
                            "host_proactive_candidate",
                            "initiative_ledger",
                        ],
                        "proposal_count": 1,
                        "host_proactive_candidate_present": True,
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
        "run_mvp20_controlled_observation._run_runtime_initiative_observation_session",
        _fake_session,
    )

    payload = await run_controlled_observation(
        messages=["先把 initiative proposal 保持在 gate 里。"],
        session_id="session:mvp20:test",
        output_json=tmp_path / "current.json",
        artifacts_dir=tmp_path / "artifacts",
    )

    assert payload["status"] == "pass"
    assert payload["verification_level"] == "V4"
    assert payload["evidence_level"] == "E4"
    assert payload["initiative_writeback_gate"] == "allow_writeback"
    assert payload["initiative_proposal_present"] is True
    assert payload["proposal_only_discipline_consistent"] is True
    assert payload["behavioral_authority_none"] is True
    assert payload["bounded_influence_present"] is True
    assert payload["selected_priority"] == "carry_forward"
    assert payload["host_proactive_mode"] == "candidate"
    assert payload["latest_revision"]["revision_id"].startswith("initiative_rev_")
    assert payload["replay_valid"] is True
    assert (tmp_path / "current.json").exists()
    assert (tmp_path / "current.md").exists()
