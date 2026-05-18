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

from run_mvp16_controlled_observation import run_controlled_observation  # noqa: E402
from openemotion.developmental_self import (  # noqa: E402
    ContinuityMarkerType,
    DevelopmentalSelfOwner,
    PromotionLevel,
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
        "ingress_text": "先把连续性候选留下来。",
        "runtime_status": "completed_verified",
        "runtime_reply_text": "先保持 bounded proposal-only。",
        "delivery_event_id": "delivery_001",
        "delivery_created_at": now,
        "delivery_text": "先保持 bounded proposal-only。",
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
    runtime = SimpleNamespace(proto_self_runtime=SimpleNamespace(developmental_self_store=None))

    monkeypatch.setattr(
        "run_mvp16_controlled_observation.init_runtime",
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
    ):
        store = runtime.proto_self_runtime.developmental_self_store
        owner = DevelopmentalSelfOwner(store=store)
        owner.set_identity_anchor(
            anchor_summary="self-model anchored continuity",
            invariant_refs=["self_model:identity"],
            confidence=0.95,
        )
        owner.set_trajectory_summary(
            current_arc="identity_preserving_adaptation",
            current_phase="candidate_review",
            continuity_note="bounded continuity retained",
            source_refs=["trace:mvp16:test_observation"],
        )
        owner.set_continuity_metrics(
            continuity_score=0.73,
            growth_pressure=0.82,
            stagnation_signal=0.38,
            identity_preservation_confidence=0.94,
            developmental_risk_index=0.2,
        )
        proposal = owner.add_proposal(
            proposal_kind="developmental_continuity",
            summary="review identity-preserving adaptation",
            proposed_adjustment={"continuity_gap": 0.34},
            justification="test observation proposal",
            source_refs=["trace:mvp16:test_observation"],
            promotion_level=PromotionLevel.CONTROLLED_AXIS,
        )
        owner.queue_promotion(
            source_proposal_id=proposal.proposal_id,
            summary="review developmental proposal",
            promotion_level=PromotionLevel.CONTROLLED_AXIS,
        )
        owner.add_continuity_marker(
            marker_type=ContinuityMarkerType.IDENTITY_ANCHOR,
            reference="self_model:identity",
            continuity_weight=0.92,
            note="anchor retained",
            source_refs=["trace:mvp16:test_observation"],
        )
        record = owner.persist(
            update_source="proto_self_v2",
            trace_reference="trace:mvp16:test_observation",
        )
        fake_state = SimpleNamespace(
            proto_self_context={
                "developmental_self_delta": {
                    "proposal_candidate_count": 1,
                    "surface_reasons": ["continuity_gap", "growth_pressure"],
                },
                "developmental_proposal_candidates": [
                    {
                        "candidate_id": "developmental_candidate:1:2",
                        "reason": "developmental_continuity",
                        "required_gate": "developmental_writeback_gate",
                        "proposal_discipline": "proposal_only",
                        "behavioral_authority": "none",
                        "promotion_level": "controlled_axis",
                    }
                ],
                "developmental_continuity_snapshot": {
                    "owner_revision": record.model_version,
                    "continuity_gap": 0.34,
                },
                "developmental_priority_hints": {
                    "growth_priority": "elevated",
                    "continuity_priority": "elevated",
                    "identity_preservation_guard": "strict",
                },
                "developmental_audit_entries": [
                    {"kind": "developmental_signal", "reason": "continuity_gap"}
                ],
                "developmental_writeback_candidate": {
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "none",
                    "required_gate": "developmental_writeback_gate",
                    "promotion_level": "controlled_axis",
                },
                "developmental_writeback": {
                    "decision": {
                        "gate_verdict": "allow_writeback",
                        "changed_fields": [
                            "continuity_metrics",
                            "proposal_history",
                            "promotion_queue",
                            "governance_ledger",
                        ],
                        "proposal_count": 1,
                        "promotion_count": 1,
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
        "run_mvp16_controlled_observation._run_runtime_developmental_observation_session",
        _fake_session,
    )

    payload = await run_controlled_observation(
        messages=["先把连续性候选留下来。"],
        session_id="session:mvp16:test",
        output_json=tmp_path / "current.json",
        artifacts_dir=tmp_path / "artifacts",
    )

    assert payload["status"] == "pass"
    assert payload["verification_level"] == "V4"
    assert payload["evidence_level"] == "E4"
    assert payload["developmental_proposal_present"] is True
    assert payload["proposal_only_discipline_consistent"] is True
    assert payload["behavioral_authority_none"] is True
    assert payload["bounded_influence_present"] is True
    assert payload["identity_preservation_violation_count"] == 0
    assert payload["latest_revision"]["revision_id"].startswith("developmental_rev_")
    assert payload["replay_valid"] is True
    assert (tmp_path / "current.json").exists()
    assert (tmp_path / "current.md").exists()
