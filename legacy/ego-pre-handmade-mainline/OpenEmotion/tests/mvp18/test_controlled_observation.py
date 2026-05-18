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

from run_mvp18_controlled_observation import run_controlled_observation  # noqa: E402
from openemotion.embodied_self import (  # noqa: E402
    BoundaryPressureMode,
    EmbodiedProposalStatus,
    EmbodiedSelfOwner,
    EnvironmentCouplingStatus,
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
        "ingress_text": "先把 embodied proposal 保持在 gate 里。",
        "runtime_status": "completed_verified",
        "runtime_reply_text": "先走受治理 embodied writeback。",
        "delivery_event_id": "delivery_001",
        "delivery_created_at": now,
        "delivery_text": "先走受治理 embodied writeback。",
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
    runtime = SimpleNamespace(proto_self_runtime=SimpleNamespace(embodied_self_store=None))

    monkeypatch.setattr(
        "run_mvp18_controlled_observation.init_runtime",
        lambda: runtime,
    )

    async def _fake_session(
        *,
        messages,
        session_id,
        runtime,
        resource_budget_hint,
        maintenance_context,
        environment_context,
    ):
        store = runtime.proto_self_runtime.embodied_self_store
        owner = EmbodiedSelfOwner(store=store)
        owner.set_embodied_state(
            resource_slack=0.24,
            perceived_load=0.78,
            action_readiness=0.36,
            source_refs=["trace:mvp18:test_observation"],
        )
        owner.upsert_environment_coupling(
            coupling_id="delivery:telegram:repair_turn",
            coupling_strength=0.76,
            controllability_estimate=0.45,
            recent_outcome_summary="delivery failure raised stabilization pressure",
            status=EnvironmentCouplingStatus.DEGRADED,
            source_refs=["trace:mvp18:test_observation"],
        )
        owner.set_resource_pressure(
            pressure_id="resource:runtime",
            pressure_level=0.81,
            slack_level=0.18,
            recovery_bias=0.87,
            source_refs=["trace:mvp18:test_observation"],
        )
        owner.set_boundary_pressure(
            boundary_id="self_world",
            pressure_level=0.69,
            mode=BoundaryPressureMode.GUARDED,
            reason="test_observation_guard",
            source_refs=["trace:mvp18:test_observation"],
        )
        owner.record_action_consequence(
            action_ref="delivery:telegram:repair_turn",
            outcome_type="failure",
            consequence_summary="recent bounded failure increased consequence pressure",
            impact_score=0.75,
            controllability_estimate=0.52,
            source_refs=["trace:mvp18:test_observation"],
        )
        owner.set_self_world_boundary_semantics(
            distinction_summary="bounded_self_world_boundary_under_test_pressure",
            guard_bias=0.65,
            repair_bias=0.78,
            source_refs=["trace:mvp18:test_observation"],
        )
        proposal = owner.propose_stabilization(
            target_ref="embodied_stabilization",
            issue_summary="resource/boundary pressure needs governed stabilization review",
            proposed_adjustment={"resource_bias": "conserve", "boundary_mode": "guarded"},
            justification="test observation proposal",
            source_refs=["trace:mvp18:test_observation"],
        )
        owner.set_proposal_status(proposal.proposal_id, status=EmbodiedProposalStatus.HELD)
        record = owner.persist(
            update_source="proto_self_v2",
            trace_reference="trace:mvp18:test_observation",
        )
        fake_state = SimpleNamespace(
            proto_self_context={
                "embodied_self_delta": {
                    "proposal_candidate_count": 1,
                    "action_ref": "delivery:telegram:repair_turn",
                    "surface_reasons": ["resource_pressure", "boundary_pressure", "recent_consequence"],
                    "boundary_signal": "guarded",
                },
                "consequence_update_candidates": [
                    {
                        "candidate_id": "consequence_update:delivery:telegram:repair_turn:2",
                        "action_ref": "delivery:telegram:repair_turn",
                        "outcome_type": "failure",
                        "required_gate": "embodied_writeback_gate",
                        "proposal_discipline": "proposal_only",
                        "behavioral_authority": "none",
                        "promotion_level": "controlled_axis",
                    }
                ],
                "resource_boundary_snapshot": {
                    "owner_revision": record.model_version,
                    "last_revision_id": record.revision_id,
                    "resource_slack": 0.24,
                    "perceived_load": 0.78,
                    "active_coupling_count": 1,
                    "max_resource_pressure": 0.81,
                    "min_resource_slack": 0.18,
                    "max_boundary_pressure": 0.69,
                    "recent_consequence_count": 1,
                    "stabilization_proposal_count": 1,
                    "self_world_guard_bias": 0.65,
                    "action_ref": "delivery:telegram:repair_turn",
                    "outcome_type": "failure",
                    "coupling_event": "delivery_feedback",
                    "boundary_signal": "guarded",
                },
                "embodied_policy_hints": {
                    "resource_bias": "conserve",
                    "boundary_mode": "guarded",
                    "stabilization_bias": "elevated",
                    "consequence_mode": "repair",
                    "self_world_guard": "tight",
                    "action_ref": "delivery:telegram:repair_turn",
                },
                "repair_or_stabilize_proposal_candidates": [
                    {
                        "candidate_id": "embodied_stabilize:delivery:telegram:repair_turn:3",
                        "reason": "repair_or_stabilize",
                        "surface_reasons": ["resource_pressure", "boundary_pressure", "recent_consequence"],
                        "required_gate": "embodied_writeback_gate",
                        "proposal_discipline": "proposal_only",
                        "behavioral_authority": "none",
                        "promotion_level": "controlled_axis",
                    }
                ],
                "embodied_writeback_candidate": {
                    "source": "proto_self_v2",
                    "contract_version": "mvp18.embodied_contract.v1",
                    "action_ref": "delivery:telegram:repair_turn",
                    "required_gate": "embodied_writeback_gate",
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "none",
                    "promotion_level": "controlled_axis",
                    "surface_reasons": ["resource_pressure", "boundary_pressure", "recent_consequence"],
                    "owner_revision": record.model_version,
                },
                "environment_context": dict(environment_context),
                "embodied_writeback": {
                    "decision": {
                        "gate_verdict": "allow_writeback",
                        "changed_fields": [
                            "embodied_state",
                            "environment_coupling_state",
                            "resource_pressure_state",
                            "boundary_pressure_state",
                            "action_consequence_memory",
                            "self_world_boundary_semantics",
                            "proposal_history",
                            "governance_ledger",
                        ],
                        "proposal_count": 1,
                        "consequence_candidate_count": 1,
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
        "run_mvp18_controlled_observation._run_runtime_embodied_observation_session",
        _fake_session,
    )

    payload = await run_controlled_observation(
        messages=["先把 embodied proposal 保持在 gate 里。"],
        session_id="session:mvp18:test",
        output_json=tmp_path / "current.json",
        artifacts_dir=tmp_path / "artifacts",
    )

    assert payload["status"] == "pass"
    assert payload["verification_level"] == "V4"
    assert payload["evidence_level"] == "E4"
    assert payload["embodied_writeback_gate"] == "allow_writeback"
    assert payload["embodied_proposal_present"] is True
    assert payload["proposal_only_discipline_consistent"] is True
    assert payload["behavioral_authority_none"] is True
    assert payload["bounded_influence_present"] is True
    assert payload["latest_revision"]["revision_id"].startswith("embodied_rev_")
    assert payload["replay_valid"] is True
    assert (tmp_path / "current.json").exists()
    assert (tmp_path / "current.md").exists()
