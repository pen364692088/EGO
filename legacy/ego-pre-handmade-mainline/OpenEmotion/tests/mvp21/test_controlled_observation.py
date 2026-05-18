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

from run_mvp21_controlled_observation import run_controlled_observation  # noqa: E402
from openemotion.initiative_realization import (  # noqa: E402
    CommitmentFulfillmentStatus,
    ControlledDeliveryCandidateStatus,
    InitiativeRealizationOwner,
    InitiativeRealizationStore,
    RealizationMode,
    RealizationProposalStatus,
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
        "ingress_text": "先把 realization proposal 保持在 gate 里。",
        "runtime_status": "completed_verified",
        "runtime_reply_text": "先走受治理 realization writeback。",
        "delivery_event_id": "delivery_001",
        "delivery_created_at": now,
        "delivery_text": "先走受治理 realization writeback。",
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
    runtime = SimpleNamespace(proto_self_runtime=SimpleNamespace(initiative_realization_store=None))

    monkeypatch.setattr(
        "run_mvp21_controlled_observation.init_runtime",
        lambda: runtime,
    )

    async def _fake_session(
        *,
        messages,
        session_id,
        runtime,
        resource_budget_hint,
        maintenance_context,
        host_proactive_context,
    ):
        store = runtime.proto_self_runtime.initiative_realization_store
        owner = InitiativeRealizationOwner(store=store)
        owner.set_realization_state(
            dominant_mode=RealizationMode.REVIEW,
            realization_pressure=0.22,
            fulfillment_readiness=0.31,
            hold_bias=0.74,
            failure_recovery_bias=0.66,
            rationale_summary="test observation bounded initiative realization",
            source_refs=["trace:mvp21:test_observation"],
        )
        owner.set_delivery_readiness_state(
            selected_lane=RealizationMode.REVIEW,
            hold_weight=0.72,
            review_weight=0.85,
            prepare_weight=0.28,
            mediate_weight=0.36,
            fulfill_weight=0.22,
            lane_reason="bounded realization remains under host review",
            host_lane_hints=["host_reality_review", "host_continuity_queue"],
            source_refs=["trace:mvp21:test_observation"],
        )
        owner.set_commitment_fulfillment_state(
            status=CommitmentFulfillmentStatus.ACTIVE,
            active_commitments_count=2,
            ready_commitments_count=1,
            realized_commitment_refs=["realization:followup:bounded"],
            blocked_commitment_refs=[],
            continuity_confidence=0.77,
            fulfillment_summary="bounded realization remains active under host review",
            source_refs=["trace:mvp21:test_observation"],
        )
        proposal = owner.propose_realization(
            candidate_label="realization_review_candidate_under_host_gate",
            selected_mode=RealizationMode.REVIEW,
            proposed_effects={
                "initiative_realization_policy_hints": {"realization_bias": "review_first"}
            },
            justification="test observation proposal",
            source_refs=["trace:mvp21:test_observation"],
        )
        owner.set_initiative_realization_candidate_status(status=RealizationProposalStatus.HELD)
        delivery_candidate = owner.set_controlled_delivery_candidate(
            candidate_label="governed_controlled_delivery_review_candidate",
            readiness_basis="realization_continuity_review",
            delivery_readiness=0.68,
            host_lane_hint="host_reality_review",
            source_refs=["trace:mvp21:test_observation"],
            requested_effects=["review_realization_lane"],
        )
        owner.set_controlled_delivery_candidate_status(
            status=ControlledDeliveryCandidateStatus.HELD
        )
        owner.record_realization_event(
            event_type="initiative_realization_writeback",
            reference_id=proposal.candidate_id,
            gate_verdict="allow_writeback",
            details={"delivery_candidate_id": delivery_candidate.candidate_id},
        )
        record = owner.persist(
            update_source="proto_self_v2",
            trace_reference="trace:mvp21:test_observation",
        )
        fake_state = SimpleNamespace(
            proto_self_context={
                "initiative_realization_delta": {
                    "proposal_candidate_count": 2,
                    "selected_mode": "review",
                    "surface_reasons": [
                        "low_realization_readiness",
                        "low_fulfillment_readiness",
                        "high_hold_bias",
                        "high_active_commitments",
                    ],
                    "lane": "review",
                    "proposal_only": True,
                },
                "commitment_fulfillment_candidates": [
                    {
                        "candidate_id": proposal.candidate_id,
                        "target_mode": "review",
                        "required_gate": "initiative_realization_writeback_gate",
                        "proposal_only": True,
                        "proposal_discipline": "proposal_only",
                        "behavioral_authority": "none",
                        "promotion_level": "controlled_axis",
                    }
                ],
                "delivery_readiness_snapshot": {
                    "contract_version": "mvp21.initiative_realization_contract.v1",
                    "selected_lane": "review",
                    "ready_commitments_count": 1,
                    "active_commitments_count": 2,
                    "delivery_failure": False,
                },
                "host_lane_hints": ["host_reality_review", "host_continuity_queue"],
                "controlled_delivery_candidate": {
                    "candidate_id": delivery_candidate.candidate_id,
                    "candidate_label": "governed_controlled_delivery_review_candidate",
                    "readiness_basis": "realization_continuity_review",
                    "delivery_readiness": 0.68,
                    "host_lane_hint": "host_reality_review",
                    "required_gate": "initiative_realization_writeback_gate",
                    "proposal_only": True,
                    "proposal_discipline": "proposal_only",
                    "effect_scope": "proposal_only",
                    "behavioral_authority": "none",
                    "requested_effects": ["review_realization_lane"],
                    "promotion_level": "controlled_axis",
                },
                "initiative_realization_writeback_candidate": {
                    "source": "proto_self_v2",
                    "contract_version": "mvp21.initiative_realization_contract.v1",
                    "required_gate": "initiative_realization_writeback_gate",
                    "proposal_only": True,
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "none",
                    "promotion_level": "controlled_axis",
                    "surface_reasons": [
                        "low_realization_readiness",
                        "low_fulfillment_readiness",
                        "high_hold_bias",
                        "high_active_commitments",
                    ],
                    "owner_revision": record.model_version,
                },
                "initiative_realization_context": {
                    "contract_version": "mvp21.initiative_realization_contract.v1",
                    "present": True,
                    "selected_lane": "review",
                },
                "host_proactive_context": dict(host_proactive_context),
                "initiative_realization_writeback": {
                    "decision": {
                        "gate_verdict": "allow_writeback",
                        "changed_fields": [
                            "realization_state",
                            "delivery_readiness_state",
                            "commitment_fulfillment_state",
                            "initiative_realization_candidate",
                            "controlled_delivery_candidate",
                            "realization_ledger",
                        ],
                        "proposal_count": 1,
                        "controlled_delivery_candidate_present": True,
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
        "run_mvp21_controlled_observation._run_runtime_initiative_realization_observation_session",
        _fake_session,
    )

    payload = await run_controlled_observation(
        messages=["先把 realization proposal 保持在 gate 里。"],
        session_id="session:mvp21:test",
        output_json=tmp_path / "current.json",
        artifacts_dir=tmp_path / "artifacts",
    )

    assert payload["status"] == "pass"
    assert payload["verification_level"] == "V4"
    assert payload["evidence_level"] == "E4"
    assert payload["initiative_realization_writeback_gate"] == "allow_writeback"
    assert payload["initiative_realization_proposal_present"] is True
    assert payload["proposal_only_discipline_consistent"] is True
    assert payload["behavioral_authority_none"] is True
    assert payload["bounded_influence_present"] is True
    assert payload["selected_mode"] == "review"
    assert payload["selected_lane"] == "review"
    assert payload["latest_revision"]["revision_id"].startswith("realization_rev_")
    assert payload["replay_valid"] is True
    assert (tmp_path / "current.json").exists()
    assert (tmp_path / "current.md").exists()
