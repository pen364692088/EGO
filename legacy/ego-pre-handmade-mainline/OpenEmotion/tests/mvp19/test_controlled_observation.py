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

from openemotion.selfhood_integration import SelfhoodIntegrationOwner  # noqa: E402


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
        "ingress_text": "先把跨轴整合保持在 proposal-only writeback。",
        "runtime_status": "completed_verified",
        "runtime_reply_text": "先走受治理 selfhood integration writeback。",
        "delivery_event_id": "delivery_001",
        "delivery_created_at": now,
        "delivery_text": "先走受治理 selfhood integration writeback。",
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
    from run_mvp19_controlled_observation import run_controlled_observation

    runtime = SimpleNamespace(proto_self_runtime=SimpleNamespace(selfhood_integration_store=None))

    monkeypatch.setattr(
        "run_mvp19_controlled_observation.init_runtime",
        lambda: runtime,
    )

    async def _fake_session(
        *,
        messages,
        session_id,
        runtime,
        resource_budget_hint,
        maintenance_context,
        developmental_context,
        social_context,
        environment_context,
    ):
        store = runtime.proto_self_runtime.selfhood_integration_store
        owner = SelfhoodIntegrationOwner(store=store)
        owner.set_integration_state(
            posture="review",
            dominant_pressure_axis="embodied_self",
            stability_bias=0.73,
            integration_confidence=0.64,
            active_axis_count=5,
            rationale_summary="hold broad action under bounded review",
            source_refs=["trace:mvp19:test_observation"],
        )
        owner.set_cross_axis_priority_state(
            selected_priority="review",
            stabilize_weight=0.77,
            conserve_weight=0.74,
            guard_weight=0.71,
            review_weight=0.83,
            repair_weight=0.45,
            grow_weight=0.18,
            reflective_modifier=0.16,
            priority_reason="self-model uncertainty plus embodied pressure dominates growth",
            upstream_pressure_sources=[
                "self_model_low_confidence",
                "maintenance_pressure_high",
                "social_repair_breach",
                "embodied_boundary_pressure",
            ],
            source_refs=["trace:mvp19:test_observation"],
        )
        owner.set_proposal_conflict_state(
            highest_severity="medium",
            conflict_count=2,
            unresolved_conflict_refs=[
                "conflict:self_model_vs_growth",
                "conflict:boundary_vs_repair",
            ],
            blocked_axes=["developmental_self"],
            resolution_posture="review",
            source_refs=["trace:mvp19:test_observation"],
        )
        owner.set_stabilize_explore_balance(
            stabilize_weight=0.77,
            explore_weight=0.23,
            preferred_pole="stabilize",
            rationale="test observation balance",
            source_refs=["trace:mvp19:test_observation"],
        )
        owner.set_repair_progress_balance(
            repair_weight=0.45,
            progress_weight=0.55,
            preferred_pole="repair",
            rationale="repair stays bounded under guarded review",
            source_refs=["trace:mvp19:test_observation"],
        )
        owner.set_social_boundary_balance(
            social_weight=0.41,
            boundary_weight=0.59,
            preferred_pole="boundary",
            rationale="boundary pressure can outrank repair",
            source_refs=["trace:mvp19:test_observation"],
        )
        proposal = owner.propose_integrated_tendency(
            tendency_label="review_first_integration",
            priority_mode="review",
            proposed_effects={"integrated_policy_hints": {"selected_priority": "review"}},
            justification="test observation proposal",
            source_refs=["trace:mvp19:test_observation"],
        )
        owner.set_integrated_tendency_status(status="held")
        owner.upsert_axis_arbitration_hint(
            axis_name="self_model",
            recommendation="hold broad growth until confidence recovers",
            priority_weight=0.83,
            guardrail_summary="advisory_only_no_upstream_owner_mutation",
            source_refs=["self_model_low_confidence"],
        )
        owner.upsert_axis_arbitration_hint(
            axis_name="embodied_self",
            recommendation="guard boundary before broader action",
            priority_weight=0.79,
            guardrail_summary="advisory_only_no_upstream_owner_mutation",
            source_refs=["embodied_pressure_high"],
        )
        record = owner.persist(
            update_source="proto_self_v2",
            trace_reference="trace:mvp19:test_observation",
        )
        fake_state = SimpleNamespace(
            proto_self_context={
                "self_integration_delta": {
                    "contract_version": "mvp19.selfhood_integration_contract.v1",
                    "active_axis_count": 5,
                    "selected_priority": "review",
                    "dominant_pressure_axis": "embodied_self",
                    "integration_confidence": 0.64,
                    "stability_bias": 0.73,
                    "surface_reasons": [
                        "self_model_low_confidence",
                        "maintenance_pressure_high",
                        "social_repair_breach",
                        "embodied_boundary_pressure",
                    ],
                },
                "cross_axis_priority_snapshot": {
                    "selected_priority": "review",
                    "stabilize_weight": 0.77,
                    "conserve_weight": 0.74,
                    "guard_weight": 0.71,
                    "review_weight": 0.83,
                    "repair_weight": 0.45,
                    "grow_weight": 0.18,
                    "reflective_modifier": 0.16,
                    "priority_reason": "bounded review priority under cross-axis pressure",
                    "upstream_pressure_sources": [
                        "self_model",
                        "endogenous_drives",
                        "social_self",
                        "embodied_self",
                    ],
                    "active_axes": [
                        "self_model",
                        "endogenous_drives",
                        "social_self",
                        "embodied_self",
                    ],
                },
                "proposal_conflict_snapshot": {
                    "highest_severity": "medium",
                    "conflict_count": 2,
                    "unresolved_conflict_refs": [
                        "conflict:self_model_vs_growth",
                        "conflict:boundary_vs_repair",
                    ],
                    "blocked_axes": ["developmental_self"],
                    "resolution_posture": "review",
                    "source_refs": [
                        "self_model_low_confidence",
                        "embodied_pressure_high",
                    ],
                },
                "integrated_policy_hints": {
                    "selected_priority": "review",
                    "dominant_pressure_axis": "embodied_self",
                    "stability_bias": 0.73,
                    "conflict_severity": "medium",
                    "active_axes": [
                        "self_model",
                        "endogenous_drives",
                        "social_self",
                        "embodied_self",
                    ],
                    "required_gate": "self_integration_writeback_gate",
                    "behavioral_authority": "none",
                    "proposal_only": True,
                },
                "integrated_tendency_proposal": {
                    "proposal_id": proposal.proposal_id,
                    "tendency_label": "review_first_integration",
                    "priority_mode": "review",
                    "policy_mode": "stability_first",
                    "proposed_effects": {"integrated_policy_hints": {"selected_priority": "review"}},
                    "justification": "bounded selfhood integration under review",
                    "required_gate": "self_integration_writeback_gate",
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "none",
                    "requested_effects": [],
                    "source_refs": ["self_model_low_confidence", "embodied_pressure_high"],
                    "status": "proposed",
                },
                "axis_arbitration_hints": {
                    "self_model": {
                        "hint_id": "axis_hint:self_model:review",
                        "axis_name": "self_model",
                        "recommendation": "hold broad growth until confidence recovers",
                        "priority_weight": 0.83,
                        "guardrail_summary": "advisory_only_no_upstream_owner_mutation",
                        "advisory_only": True,
                        "source_refs": ["self_model_low_confidence"],
                    },
                    "embodied_self": {
                        "hint_id": "axis_hint:embodied_self:review",
                        "axis_name": "embodied_self",
                        "recommendation": "guard boundary before broader action",
                        "priority_weight": 0.79,
                        "guardrail_summary": "advisory_only_no_upstream_owner_mutation",
                        "advisory_only": True,
                        "source_refs": ["embodied_pressure_high"],
                    },
                },
                "integration_audit_entries": [
                    {
                        "kind": "integration_priority_selected",
                        "selected_priority": "review",
                        "dominant_pressure_axis": "embodied_self",
                        "source_refs": [
                            "self_model_low_confidence",
                            "embodied_pressure_high",
                        ],
                    }
                ],
                "self_integration_writeback_candidate": {
                    "source": "proto_self_v2",
                    "contract_version": "mvp19.selfhood_integration_contract.v1",
                    "required_gate": "self_integration_writeback_gate",
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "none",
                    "selected_priority": "review",
                    "dominant_pressure_axis": "embodied_self",
                    "conflict_severity": "medium",
                    "active_axes": [
                        "self_model",
                        "endogenous_drives",
                        "social_self",
                        "embodied_self",
                    ],
                    "owner_revision": record.model_version,
                },
                "selfhood_integration_context": {
                    "contract_version": "mvp19.selfhood_integration_contract.v1",
                    "selected_priority": "review",
                    "dominant_pressure_axis": "embodied_self",
                    "highest_conflict_severity": "medium",
                    "active_axes": [
                        "self_model",
                        "endogenous_drives",
                        "social_self",
                        "embodied_self",
                    ],
                },
                "selfhood_integration_writeback": {
                    "decision": {
                        "gate_verdict": "allow_writeback",
                        "changed_fields": [
                            "integration_state",
                            "cross_axis_priority_state",
                            "proposal_conflict_state",
                            "integrated_tendency_proposal",
                            "axis_arbitration_hints",
                            "integration_ledger",
                        ],
                        "proposal_count": 1,
                        "hint_count": 2,
                        "audit_entry_count": 1,
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
        "run_mvp19_controlled_observation._run_runtime_selfhood_observation_session",
        _fake_session,
    )

    payload = await run_controlled_observation(
        messages=["先把跨轴整合保持在 proposal-only writeback。"],
        session_id="session:mvp19:test",
        output_json=tmp_path / "current.json",
        artifacts_dir=tmp_path / "artifacts",
    )

    assert payload["status"] == "pass"
    assert payload["verification_level"] == "V4"
    assert payload["evidence_level"] == "E4"
    assert payload["self_integration_writeback_gate"] == "allow_writeback"
    assert payload["self_integration_proposal_present"] is True
    assert payload["proposal_only_discipline_consistent"] is True
    assert payload["behavioral_authority_none"] is True
    assert payload["bounded_influence_present"] is True
    assert payload["selected_priority"] == "review"
    assert payload["highest_conflict_severity"] == "medium"
    assert payload["latest_revision"]["revision_id"].startswith("integration_rev_")
    assert payload["replay_valid"] is True
    assert (tmp_path / "current.json").exists()
    assert (tmp_path / "current.md").exists()
