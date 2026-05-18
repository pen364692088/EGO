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
ARTIFACTS_ROOT = ROOT / "OpenEmotion" / "artifacts" / "mvp18"


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
    resource_slack: float = 0.78,
    perceived_load: float = 0.24,
    active_coupling_count: int = 1,
    max_resource_pressure: float = 0.22,
    min_resource_slack: float = 0.74,
    max_boundary_pressure: float = 0.16,
    recent_consequence_count: int = 0,
    stabilization_proposal_count: int = 0,
    self_world_guard_bias: float = 0.18,
) -> dict:
    return {
        "schema_version": "mvp18-owner-v1",
        "owner_revision": owner_revision,
        "last_revision_id": f"embodied_rev_{owner_revision:06d}",
        "resource_slack": resource_slack,
        "perceived_load": perceived_load,
        "active_coupling_count": active_coupling_count,
        "max_resource_pressure": max_resource_pressure,
        "min_resource_slack": min_resource_slack,
        "max_boundary_pressure": max_boundary_pressure,
        "recent_consequence_count": recent_consequence_count,
        "stabilization_proposal_count": stabilization_proposal_count,
        "self_world_guard_bias": self_world_guard_bias,
    }


def _host_context(
    *,
    action_ref: str = "env:act:001",
    coupling_event: str = "steady_observe",
    outcome_type: str = "observed",
    outcome_summary: str = "stable loop",
    resource_pressure_hint: float = 0.2,
    slack_hint: float = 0.76,
    boundary_signal: str = "open",
    boundary_pressure_hint: float = 0.12,
    stabilization_needed: bool = False,
    promotion_budget: str = "review_only",
) -> dict:
    return {
        "source": "runtime_v2",
        "action_ref": action_ref,
        "coupling_event": coupling_event,
        "outcome_type": outcome_type,
        "outcome_summary": outcome_summary,
        "resource_pressure_hint": resource_pressure_hint,
        "slack_hint": slack_hint,
        "boundary_signal": boundary_signal,
        "boundary_pressure_hint": boundary_pressure_hint,
        "stabilization_needed": stabilization_needed,
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
            user_intent="embodied_followup",
            raw_text="continue",
        ),
        conversation_summary={"session_id": "session:mvp18:causal", "turn_id": event_id},
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
                "embodied_self_context": _owner_context(owner_revision=1),
                "environment_context": _host_context(),
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="pair1_intervention",
            runtime_summary={
                "embodied_self_context": _owner_context(
                    owner_revision=2,
                    resource_slack=0.24,
                    perceived_load=0.72,
                    max_resource_pressure=0.82,
                    min_resource_slack=0.2,
                ),
                "environment_context": _host_context(),
            },
        )
    )
    pairs.append(
        {
            "pair_id": "high_resource_pressure_changes_weighting",
            "passed": control.repair_or_stabilize_proposal_candidates == []
            and control.policy_hint.get("embodied_resource_bias") is None
            and intervention.embodied_writeback_candidate is not None
            and intervention.policy_hint.get("embodied_resource_bias") == "conserve"
            and "resource_pressure"
            in intervention.repair_or_stabilize_proposal_candidates[0].get("surface_reasons", [])
            and "resource_slack_low"
            in intervention.repair_or_stabilize_proposal_candidates[0].get("surface_reasons", []),
            "metric": {
                "control_resource_bias": control.policy_hint.get("embodied_resource_bias"),
                "intervention_resource_bias": intervention.policy_hint.get("embodied_resource_bias"),
                "intervention_surface_reasons": intervention.repair_or_stabilize_proposal_candidates[0].get(
                    "surface_reasons", []
                )
                if intervention.repair_or_stabilize_proposal_candidates
                else [],
            },
        }
    )

    control = _run(
        _packet(
            event_id="pair2_control",
            runtime_summary={
                "embodied_self_context": _owner_context(owner_revision=3),
                "environment_context": _host_context(),
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="pair2_intervention",
            runtime_summary={
                "embodied_self_context": _owner_context(owner_revision=4, recent_consequence_count=2),
                "environment_context": _host_context(),
            },
        )
    )
    pairs.append(
        {
            "pair_id": "consequence_memory_changes_weighting",
            "passed": control.consequence_update_candidates == []
            and control.embodied_writeback_candidate is None
            and intervention.consequence_update_candidates != []
            and intervention.embodied_self_delta.get("surface_reasons") == ["recent_consequence"]
            and intervention.policy_hint.get("embodied_stabilization_bias") == "normal"
            and intervention.embodied_writeback_candidate is not None,
            "metric": {
                "control_consequence_candidates": len(control.consequence_update_candidates),
                "intervention_consequence_candidates": len(intervention.consequence_update_candidates),
                "control_stabilization_bias": control.policy_hint.get("embodied_stabilization_bias"),
                "intervention_stabilization_bias": intervention.policy_hint.get(
                    "embodied_stabilization_bias"
                ),
            },
        }
    )

    control = _run(
        _packet(
            event_id="pair3_control",
            runtime_summary={
                "embodied_self_context": _owner_context(owner_revision=5),
                "environment_context": _host_context(boundary_signal="open"),
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="pair3_intervention",
            runtime_summary={
                "embodied_self_context": _owner_context(
                    owner_revision=6,
                    max_boundary_pressure=0.84,
                    self_world_guard_bias=0.81,
                ),
                "environment_context": _host_context(
                    boundary_signal="guarded",
                    boundary_pressure_hint=0.82,
                ),
            },
        )
    )
    pairs.append(
        {
            "pair_id": "boundary_guard_changes_weighting",
            "passed": control.repair_or_stabilize_proposal_candidates == []
            and control.policy_hint.get("embodied_boundary_bias") is None
            and intervention.repair_or_stabilize_proposal_candidates != []
            and intervention.embodied_policy_hints.get("boundary_mode") == "guarded"
            and intervention.policy_hint.get("embodied_boundary_bias") == "cautious"
            and intervention.embodied_writeback_candidate is not None,
            "metric": {
                "control_boundary_mode": control.embodied_policy_hints.get("boundary_mode"),
                "intervention_boundary_mode": intervention.embodied_policy_hints.get("boundary_mode"),
                "control_boundary_bias": control.policy_hint.get("embodied_boundary_bias"),
                "intervention_boundary_bias": intervention.policy_hint.get("embodied_boundary_bias"),
            },
        }
    )

    control = _run(
        _packet(
            event_id="pair4_control",
            runtime_summary={
                "embodied_self_context": _owner_context(owner_revision=7),
                "environment_context": _host_context(outcome_summary="stable loop"),
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="pair4_intervention",
            runtime_summary={
                "embodied_self_context": _owner_context(owner_revision=8),
                "environment_context": _host_context(
                    outcome_summary="same metrics, reworded outcome",
                ),
            },
        )
    )
    pairs.append(
        {
            "pair_id": "text_only_change_has_no_effect",
            "passed": control.embodied_self_delta == intervention.embodied_self_delta == {}
            and control.consequence_update_candidates == intervention.consequence_update_candidates == []
            and control.repair_or_stabilize_proposal_candidates
            == intervention.repair_or_stabilize_proposal_candidates
            == []
            and control.embodied_policy_hints == intervention.embodied_policy_hints
            and control.response_tendency is not None
            and intervention.response_tendency is not None
            and control.response_tendency.to_dict() == intervention.response_tendency.to_dict(),
            "metric": {
                "control_embodied_policy_hints": control.embodied_policy_hints,
                "intervention_embodied_policy_hints": intervention.embodied_policy_hints,
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
    json_path = ARTIFACTS_ROOT / "mvp18_causal_validation_current.json"
    md_path = ARTIFACTS_ROOT / "mvp18_causal_validation_current.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# MVP18 Causal Validation",
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
