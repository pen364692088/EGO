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
ARTIFACTS_ROOT = ROOT / "OpenEmotion" / "artifacts" / "mvp15"


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


def _packet(*, event_id: str, runtime_summary: dict | None = None, event_type: str = "user_message") -> UpdatePacketV2:
    return UpdatePacketV2(
        event_id=event_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        event=UpdateEventV2(
            actor="system" if event_type == "developmental_tick" else "user",
            source="runtime" if event_type == "developmental_tick" else "runtime_harness",
            event_type=event_type,
            user_intent=None if event_type == "developmental_tick" else "reflect",
            raw_text=None if event_type == "developmental_tick" else "继续",
        ),
        conversation_summary={"session_id": "session:mvp15:causal", "turn_id": event_id},
        task_summary={"pending_tasks": 0, "blocked_tasks": 0},
        runtime_summary={
            "runtime": "runtime_v2",
            "state_scope": "agent_global",
            **(
                {
                    "developmental_mode": "shadow_observe",
                    "observation_source": "direct_real",
                    "developmental_trigger": "idle",
                    "idle_seconds": 900.0,
                }
                if event_type == "developmental_tick"
                else {}
            ),
            **(runtime_summary or {}),
        },
        safety_context={"risk_level": "low"},
        intervention_context={"developmental_input": {"state_snapshot": {}, "observation_refs": []}}
        if event_type == "developmental_tick"
        else {},
    )


def _run(packet: UpdatePacketV2):
    return process_update_packet(ProtoSelfStateV2.empty(), packet)


def _pair_results() -> List[Dict[str, Any]]:
    pairs: List[Dict[str, Any]] = []

    control = _run(_packet(event_id="pair1_control", runtime_summary={"reflective_self_context": {"schema_version": "mvp15-owner-v1", "owner_revision": 1}}))
    intervention = _run(
        _packet(
            event_id="pair1_intervention",
            runtime_summary={
                "reflective_self_context": {
                    "schema_version": "mvp15-owner-v1",
                    "owner_revision": 2,
                    "reflection_pressure": 0.82,
                    "pending_reflections": 2,
                    "proposal_candidates": 1,
                    "top_target_ids": ["decision:target"],
                }
            },
        )
    )
    pairs.append(
        {
            "pair_id": "high_reflection_pressure",
            "passed": control.reflection_writeback_candidate is None
            and intervention.reflection_writeback_candidate is not None
            and intervention.revision_proposal_candidates[0]["proposal_discipline"] == "proposal_only",
            "metric": {
                "control_revision_candidates": len(control.revision_proposal_candidates),
                "intervention_revision_candidates": len(intervention.revision_proposal_candidates),
            },
        }
    )

    control = _run(
        _packet(
            event_id="pair2_control",
            runtime_summary={
                "reflective_self_context": {
                    "schema_version": "mvp15-owner-v1",
                    "owner_revision": 3,
                    "reflection_pressure": 0.36,
                    "pending_reflections": 1,
                    "unresolved_items": 0,
                    "proposal_candidates": 1,
                    "top_target_ids": ["trajectory:drift"],
                }
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="pair2_intervention",
            runtime_summary={
                "reflective_self_context": {
                    "schema_version": "mvp15-owner-v1",
                    "owner_revision": 4,
                    "reflection_pressure": 0.36,
                    "pending_reflections": 1,
                    "unresolved_items": 2,
                    "proposal_candidates": 1,
                    "top_target_ids": ["trajectory:drift"],
                }
            },
        )
    )
    pairs.append(
        {
            "pair_id": "unresolved_items_bias",
            "passed": "uncertainty_bias" not in control.policy_hint
            and intervention.policy_hint.get("uncertainty_bias") == "elevated"
            and intervention.reflection_writeback_candidate["behavioral_authority"] == "none",
            "metric": {
                "control_uncertainty_bias": control.policy_hint.get("uncertainty_bias"),
                "intervention_uncertainty_bias": intervention.policy_hint.get("uncertainty_bias"),
            },
        }
    )

    control = _run(
        _packet(
            event_id="pair3_control",
            event_type="developmental_tick",
            runtime_summary={
                "reflective_self_context": {
                    "schema_version": "mvp15-owner-v1",
                    "owner_revision": 5,
                    "reflection_pressure": 0.1,
                    "pending_reflections": 0,
                    "unresolved_items": 0,
                    "proposal_candidates": 0,
                    "top_target_ids": [],
                },
                "maintenance_context": {},
                "recent_delivery_outcome": {"success": True, "status": "sent"},
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="pair3_intervention",
            event_type="developmental_tick",
            runtime_summary={
                "reflective_self_context": {
                    "schema_version": "mvp15-owner-v1",
                    "owner_revision": 6,
                    "reflection_pressure": 0.1,
                    "pending_reflections": 0,
                    "unresolved_items": 0,
                    "proposal_candidates": 0,
                    "top_target_ids": [],
                },
                "maintenance_context": {"replay_inconsistency": True},
                "recent_delivery_outcome": {"success": False, "status": "failed"},
            },
        )
    )
    pairs.append(
        {
            "pair_id": "replay_inconsistency_surface",
            "passed": control.reflective_self_delta == {}
            and intervention.reflective_self_delta.get("revision_proposals")
            and intervention.reflection_writeback_candidate["behavioral_authority"] == "none",
            "metric": {
                "control_delta_fields": sorted(control.reflective_self_delta.keys()),
                "intervention_delta_fields": sorted(intervention.reflective_self_delta.keys()),
                "surface_reasons": intervention.reflective_self_delta.get("surface_reasons", []),
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
    json_path = ARTIFACTS_ROOT / "mvp15_causal_validation_current.json"
    md_path = ARTIFACTS_ROOT / "mvp15_causal_validation_current.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# MVP15 Causal Validation",
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
