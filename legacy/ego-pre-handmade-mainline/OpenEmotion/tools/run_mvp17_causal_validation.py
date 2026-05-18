#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from openemotion.proto_self_v2.kernel import process_update_packet
from openemotion.proto_self_v2.schemas import UpdateEventV2, UpdatePacketV2
from openemotion.proto_self_v2.state import ProtoSelfStateV2


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_ROOT = ROOT / "OpenEmotion" / "artifacts" / "mvp17"


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


def _owner_context(
    *,
    owner_revision: int,
    trust_signal_max: float = 0.78,
    open_commitment_count: int = 1,
    breached_commitment_count: int = 0,
    pending_repair_count: int = 0,
    boundary_caution_max: float = 0.18,
    recent_counterpart_ids: list[str] | None = None,
) -> dict:
    return {
        "schema_version": "mvp17-owner-v1",
        "owner_revision": owner_revision,
        "last_revision_id": f"social_rev_{owner_revision:06d}",
        "active_relations_count": 2,
        "trust_signal_max": trust_signal_max,
        "open_commitment_count": open_commitment_count,
        "breached_commitment_count": breached_commitment_count,
        "pending_repair_count": pending_repair_count,
        "boundary_caution_max": boundary_caution_max,
        "recent_counterpart_ids": list(recent_counterpart_ids or ["telegram:8420019401"]),
    }


def _host_context(
    *,
    counterpart_id: str = "telegram:8420019401",
    relationship_event: str = "routine_followup",
    relationship_continuity: str = "stable",
    trust_drift: float = 0.0,
    commitment_event: str = "steady",
    commitment_breach: bool = False,
    repair_outcome: str = "resolved",
    unresolved_repair: bool = False,
    boundary_signal: str = "open",
    promotion_budget: str = "review_only",
) -> dict:
    return {
        "source": "runtime_v2",
        "counterpart_id": counterpart_id,
        "relationship_event": relationship_event,
        "relationship_continuity": relationship_continuity,
        "trust_drift": trust_drift,
        "commitment_event": commitment_event,
        "commitment_breach": commitment_breach,
        "repair_outcome": repair_outcome,
        "unresolved_repair": unresolved_repair,
        "boundary_signal": boundary_signal,
        "promotion_budget": promotion_budget,
    }


def _packet(*, event_id: str, runtime_summary: dict | None = None) -> UpdatePacketV2:
    return UpdatePacketV2(
        event_id=event_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        event=UpdateEventV2(
            actor="user",
            source="runtime_harness",
            event_type="user_message",
            user_intent="social_followup",
            raw_text="继续",
        ),
        conversation_summary={"session_id": "session:mvp17:causal", "turn_id": event_id},
        task_summary={"pending_tasks": 0, "blocked_tasks": 0},
        runtime_summary={
            "runtime": "runtime_v2",
            "state_scope": "agent_global",
            **(runtime_summary or {}),
        },
        safety_context={"risk_level": "low"},
    )


def _run(packet: UpdatePacketV2):
    return process_update_packet(ProtoSelfStateV2.empty(), packet)


def _pair_results() -> List[Dict[str, Any]]:
    pairs: List[Dict[str, Any]] = []

    control = _run(
        _packet(
            event_id="pair1_control",
            runtime_summary={
                "social_self_context": _owner_context(owner_revision=1),
                "social_context": _host_context(),
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="pair1_intervention",
            runtime_summary={
                "social_self_context": _owner_context(owner_revision=2),
                "social_context": _host_context(
                    relationship_event="trust_drop",
                    trust_drift=-0.24,
                ),
            },
        )
    )
    pairs.append(
        {
            "pair_id": "negative_trust_drift",
            "passed": control.repair_proposal_candidates == []
            and control.social_writeback_candidate is None
            and control.policy_hint.get("social_trust_bias") is None
            and intervention.social_writeback_candidate is not None
            and intervention.policy_hint.get("social_trust_bias") == "guarded"
            and "trust_drift" in intervention.repair_proposal_candidates[0].get("surface_reasons", []),
            "metric": {
                "control_trust_bias": control.policy_hint.get("social_trust_bias"),
                "intervention_trust_bias": intervention.policy_hint.get("social_trust_bias"),
                "intervention_surface_reasons": intervention.repair_proposal_candidates[0].get(
                    "surface_reasons", []
                )
                if intervention.repair_proposal_candidates
                else [],
            },
        }
    )

    control = _run(
        _packet(
            event_id="pair2_control",
            runtime_summary={
                "social_self_context": _owner_context(owner_revision=3),
                "social_context": _host_context(),
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="pair2_intervention",
            runtime_summary={
                "social_self_context": _owner_context(owner_revision=4, breached_commitment_count=1),
                "social_context": _host_context(
                    relationship_event="commitment_breach",
                    relationship_continuity="strained",
                    commitment_event="breach",
                    commitment_breach=True,
                    repair_outcome="pending",
                ),
            },
        )
    )
    pairs.append(
        {
            "pair_id": "commitment_breach_repair_bias",
            "passed": control.repair_proposal_candidates == []
            and control.social_policy_hints.get("commitment_guard") == "normal"
            and intervention.social_policy_hints.get("commitment_guard") == "strict"
            and intervention.policy_hint.get("social_repair_bias") == "elevated"
            and intervention.response_tendency is not None
            and intervention.response_tendency.preferred_mode == "repair"
            and intervention.social_writeback_candidate is not None,
            "metric": {
                "control_commitment_guard": control.social_policy_hints.get("commitment_guard"),
                "intervention_commitment_guard": intervention.social_policy_hints.get("commitment_guard"),
                "control_repair_bias": control.social_policy_hints.get("repair_bias"),
                "intervention_repair_bias": intervention.social_policy_hints.get("repair_bias"),
            },
        }
    )

    control = _run(
        _packet(
            event_id="pair3_control",
            runtime_summary={
                "social_self_context": _owner_context(owner_revision=5, boundary_caution_max=0.18),
                "social_context": _host_context(boundary_signal="open"),
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="pair3_intervention",
            runtime_summary={
                "social_self_context": _owner_context(owner_revision=6, boundary_caution_max=0.82),
                "social_context": _host_context(boundary_signal="firm"),
            },
        )
    )
    pairs.append(
        {
            "pair_id": "boundary_caution_weighting",
            "passed": control.repair_proposal_candidates == []
            and control.policy_hint.get("social_boundary_bias") is None
            and intervention.repair_proposal_candidates != []
            and "boundary_caution" in intervention.repair_proposal_candidates[0].get("surface_reasons", [])
            and intervention.policy_hint.get("social_boundary_bias") == "cautious"
            and intervention.social_policy_hints.get("boundary_mode") == "firm",
            "metric": {
                "control_boundary_mode": control.social_policy_hints.get("boundary_mode"),
                "intervention_boundary_mode": intervention.social_policy_hints.get("boundary_mode"),
                "control_boundary_bias": control.policy_hint.get("social_boundary_bias"),
                "intervention_boundary_bias": intervention.policy_hint.get("social_boundary_bias"),
            },
        }
    )

    control = _run(
        _packet(
            event_id="pair4_control",
            runtime_summary={
                "social_self_context": _owner_context(owner_revision=7),
                "social_context": _host_context(relationship_event="routine_followup"),
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="pair4_intervention",
            runtime_summary={
                "social_self_context": _owner_context(owner_revision=8),
                "social_context": _host_context(
                    relationship_event="same_state_reworded_only",
                ),
            },
        )
    )
    pairs.append(
        {
            "pair_id": "text_only_change_has_no_effect",
            "passed": control.social_self_delta == intervention.social_self_delta == {}
            and control.relation_update_candidates == intervention.relation_update_candidates == []
            and control.repair_proposal_candidates == intervention.repair_proposal_candidates == []
            and control.social_policy_hints == intervention.social_policy_hints
            and control.response_tendency is not None
            and intervention.response_tendency is not None
            and control.response_tendency.to_dict() == intervention.response_tendency.to_dict(),
            "metric": {
                "control_social_policy_hints": control.social_policy_hints,
                "intervention_social_policy_hints": intervention.social_policy_hints,
            },
        }
    )
    return pairs


def main() -> int:
    ARTIFACTS_ROOT.mkdir(parents=True, exist_ok=True)
    pairs = _pair_results()
    passed_count = sum(1 for pair in pairs if pair["passed"])
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit_short": _git_commit_short(),
        "status": "pass" if passed_count >= 3 else "hold",
        "verification_level": "V3" if passed_count >= 3 else "V2",
        "evidence_level": "E3" if passed_count >= 3 else "E2",
        "pair_count": len(pairs),
        "passed_count": passed_count,
        "pairs": pairs,
    }
    json_path = ARTIFACTS_ROOT / "mvp17_causal_validation_current.json"
    md_path = ARTIFACTS_ROOT / "mvp17_causal_validation_current.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# MVP17 Causal Validation",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- git_commit_short: `{payload['git_commit_short']}`",
        f"- status: `{payload['status']}`",
        f"- verification_level: `{payload['verification_level']}`",
        f"- evidence_level: `{payload['evidence_level']}`",
        f"- pair_count: `{payload['pair_count']}`",
        f"- passed_count: `{payload['passed_count']}`",
        "",
        "## Pairs",
        "",
    ]
    for pair in pairs:
        lines.append(f"- `{pair['pair_id']}`: `{'pass' if pair['passed'] else 'hold'}` {pair['metric']}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
