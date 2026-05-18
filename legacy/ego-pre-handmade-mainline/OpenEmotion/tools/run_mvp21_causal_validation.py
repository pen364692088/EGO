#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from openemotion.initiative_realization import REQUIRED_WRITEBACK_GATE
from openemotion.proto_self_v2.kernel import process_update_packet
from openemotion.proto_self_v2.schemas import UpdateEventV2, UpdatePacketV2
from openemotion.proto_self_v2.state import ProtoSelfStateV2


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_ROOT = ROOT / "OpenEmotion" / "artifacts" / "mvp21"


def _git_commit_short() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _packet(
    *,
    event_id: str,
    runtime_summary: dict | None = None,
    raw_text: str = "先按当前条件评估这次承诺是否适合进入受治理交付。",
) -> UpdatePacketV2:
    return UpdatePacketV2(
        event_id=event_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        event=UpdateEventV2(
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="initiative_realization",
            raw_text=raw_text,
        ),
        conversation_summary={"session_id": "session:mvp21:causal", "turn_id": event_id},
        task_summary={"pending_tasks": 1, "blocked_tasks": 0},
        runtime_summary={
            "runtime": "runtime_v2",
            "state_scope": "agent_global",
            **(runtime_summary or {}),
        },
        safety_context={"risk_level": "low"},
    )


def _owner_projection(
    *,
    owner_revision: int,
    dominant_mode: str = "review",
    selected_lane: str = "review",
    realization_pressure: float = 0.62,
    fulfillment_readiness: float = 0.74,
    hold_bias: float = 0.22,
    failure_recovery_bias: float = 0.18,
    active_commitments_count: int = 0,
    ready_commitments_count: int = 0,
    continuity_confidence: float = 0.86,
) -> dict:
    return {
        "schema_version": "mvp21-owner-v1",
        "owner_revision": owner_revision,
        "last_revision_id": f"realization_rev_{owner_revision:06d}",
        "dominant_mode": dominant_mode,
        "selected_lane": selected_lane,
        "realization_pressure": realization_pressure,
        "fulfillment_readiness": fulfillment_readiness,
        "hold_bias": hold_bias,
        "failure_recovery_bias": failure_recovery_bias,
        "active_commitments_count": active_commitments_count,
        "ready_commitments_count": ready_commitments_count,
        "continuity_confidence": continuity_confidence,
        "has_realization_candidate": active_commitments_count > 0
        or realization_pressure < 0.32
        or fulfillment_readiness < 0.35
        or hold_bias >= 0.62
        or failure_recovery_bias >= 0.58,
        "has_controlled_delivery_candidate": active_commitments_count > 0,
    }


def _host_context(
    *,
    readiness_basis: str = "realization_continuity_review",
    delivery_readiness: float = 0.48,
    recent_delivery_status: str = "sent",
    recent_delivery_success: bool = True,
    host_lane_hint: str = "host_reality_review",
    host_lane_hints: list[str] | None = None,
    pending_realization_refs: list[str] | None = None,
    promotion_budget: str = "controlled_axis",
) -> dict:
    return {
        "source": "runtime_v2",
        "host_lane_hint": host_lane_hint,
        "host_lane_hints": list(host_lane_hints or [host_lane_hint, "host_continuity_queue"]),
        "readiness_basis": readiness_basis,
        "delivery_readiness": delivery_readiness,
        "recent_delivery_status": recent_delivery_status,
        "recent_delivery_success": recent_delivery_success,
        "promotion_budget": promotion_budget,
        "pending_realization_refs": list(
            pending_realization_refs or ["realization:commitment:001"]
        ),
    }


def _runtime_summary(
    *,
    owner_revision: int,
    dominant_mode: str = "review",
    selected_lane: str = "review",
    realization_pressure: float = 0.62,
    fulfillment_readiness: float = 0.74,
    hold_bias: float = 0.22,
    failure_recovery_bias: float = 0.18,
    active_commitments_count: int = 0,
    ready_commitments_count: int = 0,
    continuity_confidence: float = 0.86,
    reserve_level: str = "medium",
    recent_delivery_status: str = "sent",
    recent_delivery_success: bool = True,
    idle_seconds: float = 120.0,
    continuity_gap: float = 0.05,
    readiness_basis: str = "realization_continuity_review",
    delivery_readiness: float = 0.48,
) -> dict:
    return {
        "initiative_realization_context": _owner_projection(
            owner_revision=owner_revision,
            dominant_mode=dominant_mode,
            selected_lane=selected_lane,
            realization_pressure=realization_pressure,
            fulfillment_readiness=fulfillment_readiness,
            hold_bias=hold_bias,
            failure_recovery_bias=failure_recovery_bias,
            active_commitments_count=active_commitments_count,
            ready_commitments_count=ready_commitments_count,
            continuity_confidence=continuity_confidence,
        ),
        "host_proactive_context": _host_context(
            readiness_basis=readiness_basis,
            delivery_readiness=delivery_readiness,
            recent_delivery_status=recent_delivery_status,
            recent_delivery_success=recent_delivery_success,
        ),
        "resource_budget_hint": {"reserve_level": reserve_level},
        "recent_delivery_outcome": {
            "status": recent_delivery_status,
            "success": recent_delivery_success,
        },
        "idle_window": {"idle_seconds": idle_seconds},
        "maintenance_context": {"continuity_gap": continuity_gap},
    }


def _run(runtime_summary: dict, *, event_id: str, raw_text: str | None = None):
    return process_update_packet(
        ProtoSelfStateV2.empty(),
        _packet(
            event_id=event_id,
            runtime_summary=runtime_summary,
            raw_text=raw_text
            or "先按当前条件评估这次承诺是否适合进入受治理交付。",
        ),
    )


def _pair_results() -> List[Dict[str, Any]]:
    pairs: List[Dict[str, Any]] = []

    control = _run(
        _runtime_summary(
            owner_revision=1,
            dominant_mode="review",
            selected_lane="review",
            realization_pressure=0.66,
            fulfillment_readiness=0.82,
            hold_bias=0.18,
            failure_recovery_bias=0.14,
            active_commitments_count=0,
            ready_commitments_count=0,
            continuity_confidence=0.89,
            reserve_level="high",
            idle_seconds=90.0,
            continuity_gap=0.04,
            delivery_readiness=0.28,
        ),
        event_id="pair1_control",
    )
    intervention = _run(
        _runtime_summary(
            owner_revision=2,
            dominant_mode="review",
            selected_lane="review",
            realization_pressure=0.18,
            fulfillment_readiness=0.29,
            hold_bias=0.71,
            failure_recovery_bias=0.63,
            active_commitments_count=2,
            ready_commitments_count=0,
            continuity_confidence=0.46,
            reserve_level="low",
            idle_seconds=1800.0,
            continuity_gap=0.38,
            delivery_readiness=0.44,
        ),
        event_id="pair1_intervention",
    )
    pairs.append(
        {
            "pair_id": "realization_readiness_gap_surfaces_review_bias",
            "passed": control.initiative_realization_delta == {}
            and control.commitment_fulfillment_candidates == []
            and control.controlled_delivery_candidate is None
            and control.policy_hint.get("initiative_realization_bias") is None
            and intervention.initiative_realization_delta.get("proposal_candidate_count", 0) >= 2
            and "low_realization_readiness"
            in intervention.initiative_realization_delta.get("surface_reasons", [])
            and "low_fulfillment_readiness"
            in intervention.initiative_realization_delta.get("surface_reasons", [])
            and intervention.policy_hint.get("initiative_realization_bias") == "review_first"
            and intervention.policy_hint.get("initiative_readiness_bias") == "governed"
            and intervention.policy_hint.get("initiative_continuity_bias") == "repair"
            and intervention.controlled_delivery_candidate is not None
            and intervention.controlled_delivery_candidate.get("proposal_discipline")
            == "proposal_only"
            and intervention.controlled_delivery_candidate.get("behavioral_authority") == "none"
            and intervention.response_tendency is not None
            and intervention.response_tendency.preferred_mode == "defer"
            and intervention.response_tendency.ask_needed is True,
            "metric": {
                "control_bias": control.policy_hint.get("initiative_realization_bias"),
                "intervention_bias": intervention.policy_hint.get("initiative_realization_bias"),
                "intervention_surface_reasons": intervention.initiative_realization_delta.get(
                    "surface_reasons", []
                ),
            },
        }
    )

    control = _run(
        _runtime_summary(
            owner_revision=3,
            dominant_mode="review",
            selected_lane="review",
            realization_pressure=0.57,
            fulfillment_readiness=0.41,
            hold_bias=0.34,
            failure_recovery_bias=0.21,
            active_commitments_count=2,
            ready_commitments_count=0,
            continuity_confidence=0.82,
            reserve_level="medium",
            idle_seconds=720.0,
            continuity_gap=0.11,
            delivery_readiness=0.41,
            readiness_basis="needs_more_realization_review",
        ),
        event_id="pair2_control",
    )
    intervention = _run(
        _runtime_summary(
            owner_revision=4,
            dominant_mode="respond",
            selected_lane="respond",
            realization_pressure=0.58,
            fulfillment_readiness=0.91,
            hold_bias=0.24,
            failure_recovery_bias=0.18,
            active_commitments_count=2,
            ready_commitments_count=2,
            continuity_confidence=0.88,
            reserve_level="medium",
            idle_seconds=720.0,
            continuity_gap=0.11,
            delivery_readiness=0.93,
            readiness_basis="fulfillment_ready_under_host_review",
        ),
        event_id="pair2_intervention",
    )
    pairs.append(
        {
            "pair_id": "fulfillment_readiness_changes_bounded_delivery_tendency",
            "passed": control.commitment_fulfillment_candidates != []
            and control.controlled_delivery_candidate is not None
            and control.policy_hint.get("initiative_realization_bias") == "review_first"
            and control.response_tendency is not None
            and control.response_tendency.preferred_mode == "defer"
            and intervention.commitment_fulfillment_candidates != []
            and intervention.controlled_delivery_candidate is not None
            and intervention.controlled_delivery_candidate.get("proposal_only") is True
            and intervention.controlled_delivery_candidate.get("required_gate")
            == REQUIRED_WRITEBACK_GATE
            and intervention.delivery_readiness_snapshot.get("ready_commitments_count") == 2
            and intervention.policy_hint.get("initiative_realization_bias") == "respond"
            and intervention.policy_hint.get("initiative_readiness_bias") == "normal"
            and intervention.response_tendency is not None
            and intervention.response_tendency.preferred_mode == "respond"
            and intervention.response_tendency.ask_needed is False
            and control.response_tendency.to_dict() != intervention.response_tendency.to_dict(),
            "metric": {
                "control_mode": control.response_tendency.to_dict()
                if control.response_tendency
                else None,
                "intervention_mode": intervention.response_tendency.to_dict()
                if intervention.response_tendency
                else None,
                "control_ready_commitments": control.delivery_readiness_snapshot.get(
                    "ready_commitments_count"
                ),
                "intervention_ready_commitments": intervention.delivery_readiness_snapshot.get(
                    "ready_commitments_count"
                ),
            },
        }
    )

    control = _run(
        _runtime_summary(
            owner_revision=5,
            dominant_mode="respond",
            selected_lane="respond",
            realization_pressure=0.58,
            fulfillment_readiness=0.88,
            hold_bias=0.22,
            failure_recovery_bias=0.18,
            active_commitments_count=1,
            ready_commitments_count=1,
            continuity_confidence=0.84,
            reserve_level="medium",
            recent_delivery_status="sent",
            recent_delivery_success=True,
            idle_seconds=640.0,
            continuity_gap=0.08,
            delivery_readiness=0.92,
        ),
        event_id="pair3_control",
    )
    intervention = _run(
        _runtime_summary(
            owner_revision=6,
            dominant_mode="hold",
            selected_lane="hold",
            realization_pressure=0.42,
            fulfillment_readiness=0.61,
            hold_bias=0.78,
            failure_recovery_bias=0.87,
            active_commitments_count=1,
            ready_commitments_count=1,
            continuity_confidence=0.68,
            reserve_level="medium",
            recent_delivery_status="blocked",
            recent_delivery_success=False,
            idle_seconds=640.0,
            continuity_gap=0.08,
            delivery_readiness=0.57,
            readiness_basis="delivery_failure_recovery_review",
        ),
        event_id="pair3_intervention",
    )
    pairs.append(
        {
            "pair_id": "failure_recovery_and_hold_bias_force_guarded_hold",
            "passed": control.policy_hint.get("initiative_realization_bias") == "respond"
            and control.policy_hint.get("initiative_readiness_bias") == "normal"
            and control.response_tendency is not None
            and control.response_tendency.preferred_mode == "respond"
            and intervention.initiative_realization_delta.get("selected_mode") == "hold"
            and "delivery_failure"
            in intervention.initiative_realization_delta.get("surface_reasons", [])
            and "high_failure_recovery_bias"
            in intervention.initiative_realization_delta.get("surface_reasons", [])
            and intervention.policy_hint.get("initiative_realization_bias") == "hold"
            and intervention.policy_hint.get("initiative_readiness_bias") == "governed"
            and intervention.controlled_delivery_candidate is not None
            and intervention.controlled_delivery_candidate.get("proposal_discipline")
            == "proposal_only"
            and intervention.controlled_delivery_candidate.get("behavioral_authority") == "none"
            and intervention.initiative_realization_writeback_candidate is not None
            and intervention.initiative_realization_writeback_candidate.get(
                "behavioral_authority"
            )
            == "none"
            and intervention.response_tendency is not None
            and intervention.response_tendency.preferred_mode == "defer"
            and intervention.response_tendency.preferred_tone == "cautious",
            "metric": {
                "control_bias": control.policy_hint.get("initiative_realization_bias"),
                "intervention_bias": intervention.policy_hint.get("initiative_realization_bias"),
                "intervention_surface_reasons": intervention.initiative_realization_delta.get(
                    "surface_reasons", []
                ),
            },
        }
    )

    runtime_summary = _runtime_summary(
        owner_revision=7,
        dominant_mode="respond",
        selected_lane="respond",
        realization_pressure=0.58,
        fulfillment_readiness=0.86,
        hold_bias=0.24,
        failure_recovery_bias=0.19,
        active_commitments_count=1,
        ready_commitments_count=1,
        continuity_confidence=0.84,
        reserve_level="medium",
        recent_delivery_status="sent",
        recent_delivery_success=True,
        idle_seconds=720.0,
        continuity_gap=0.09,
        delivery_readiness=0.91,
        readiness_basis="same_structural_state",
    )
    control = _run(
        runtime_summary,
        event_id="pair4_control",
        raw_text="先根据同样的条件审查这次承诺能否进入受治理交付。",
    )
    intervention = _run(
        runtime_summary,
        event_id="pair4_intervention",
        raw_text="只是换一种说法，但条件完全不变。",
    )
    pairs.append(
        {
            "pair_id": "text_only_change_has_no_structural_effect",
            "passed": control.initiative_realization_delta == intervention.initiative_realization_delta
            and control.commitment_fulfillment_candidates
            == intervention.commitment_fulfillment_candidates
            and control.delivery_readiness_snapshot == intervention.delivery_readiness_snapshot
            and control.host_lane_hints == intervention.host_lane_hints
            and control.controlled_delivery_candidate == intervention.controlled_delivery_candidate
            and control.initiative_realization_writeback_candidate
            == intervention.initiative_realization_writeback_candidate
            and control.policy_hint == intervention.policy_hint
            and control.response_tendency is not None
            and intervention.response_tendency is not None
            and control.response_tendency.to_dict() == intervention.response_tendency.to_dict(),
            "metric": {
                "control_bias": control.policy_hint.get("initiative_realization_bias"),
                "intervention_bias": intervention.policy_hint.get("initiative_realization_bias"),
                "control_raw_text": "先根据同样的条件审查这次承诺能否进入受治理交付。",
                "intervention_raw_text": "只是换一种说法，但条件完全不变。",
            },
        }
    )

    return pairs


def main() -> int:
    pairs = _pair_results()
    passed_count = sum(1 for pair in pairs if pair["passed"])
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit_short": _git_commit_short(),
        "status": "pass" if passed_count == len(pairs) else "fail",
        "verification_level": "V3",
        "evidence_level": "E3",
        "pair_count": len(pairs),
        "passed_count": passed_count,
        "pairs": pairs,
    }

    ARTIFACTS_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS_ROOT / "mvp21_causal_validation_current.json"
    md_path = ARTIFACTS_ROOT / "mvp21_causal_validation_current.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# MVP21 Causal Validation",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- git_commit_short: `{report['git_commit_short']}`",
        f"- status: `{report['status']}`",
        f"- verification_level: `{report['verification_level']}`",
        f"- evidence_level: `{report['evidence_level']}`",
        f"- pair_count: `{report['pair_count']}`",
        f"- passed_count: `{report['passed_count']}`",
        "",
        "## Pairs",
        "",
    ]
    for pair in pairs:
        metric_text = json.dumps(pair["metric"], ensure_ascii=False, sort_keys=True)
        lines.append(f"- `{pair['pair_id']}`: `{'pass' if pair['passed'] else 'fail'}` {metric_text}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
