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
ARTIFACTS_ROOT = ROOT / "OpenEmotion" / "artifacts" / "mvp16"


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
    continuity_score: float = 0.92,
    growth_pressure: float = 0.24,
    stagnation_signal: float = 0.12,
    identity_preservation_confidence: float = 0.94,
    developmental_risk_index: float = 0.08,
    promotion_queue_size: int = 0,
    recent_proposal_count: int = 0,
    continuity_note: str = "bounded continuity retained",
) -> dict:
    return {
        "schema_version": "mvp16-owner-v1",
        "owner_revision": owner_revision,
        "last_revision_id": f"developmental_rev_{owner_revision:06d}",
        "continuity_score": continuity_score,
        "growth_pressure": growth_pressure,
        "stagnation_signal": stagnation_signal,
        "identity_preservation_confidence": identity_preservation_confidence,
        "developmental_risk_index": developmental_risk_index,
        "trajectory_summary": {
            "current_arc": "identity_preserving_adaptation",
            "current_phase": "candidate_review",
            "recent_shift": "bounded review",
            "continuity_note": continuity_note,
            "source_refs": ["trace:developmental"],
        },
        "promotion_queue_size": promotion_queue_size,
        "recent_proposal_count": recent_proposal_count,
    }


def _host_context(
    *,
    continuity_gap: float = 0.08,
    growth_pressure_hint: float = 0.24,
    stagnation_signal_hint: float = 0.12,
    identity_guard: str = "bounded",
    replay_debt: float = 0.0,
    promotion_budget: str = "controlled_axis",
) -> dict:
    return {
        "source": "runtime_v2",
        "continuity_gap": continuity_gap,
        "growth_pressure_hint": growth_pressure_hint,
        "stagnation_signal_hint": stagnation_signal_hint,
        "identity_guard": identity_guard,
        "replay_debt": replay_debt,
        "promotion_budget": promotion_budget,
        "drift_markers": [],
    }


def _packet(*, event_id: str, runtime_summary: dict | None = None) -> UpdatePacketV2:
    return UpdatePacketV2(
        event_id=event_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        event=UpdateEventV2(
            actor="user",
            source="runtime_harness",
            event_type="user_message",
            user_intent="developmental_followup",
            raw_text="继续",
        ),
        conversation_summary={"session_id": "session:mvp16:causal", "turn_id": event_id},
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
                "developmental_self_context": _owner_context(owner_revision=1),
                "developmental_context": _host_context(),
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="pair1_intervention",
            runtime_summary={
                "developmental_self_context": _owner_context(owner_revision=2, growth_pressure=0.84),
                "developmental_context": _host_context(growth_pressure_hint=0.86),
            },
        )
    )
    pairs.append(
        {
            "pair_id": "high_growth_pressure",
            "passed": control.developmental_proposal_candidates == []
            and intervention.developmental_proposal_candidates != []
            and intervention.policy_hint.get("developmental_growth_bias") == "elevated"
            and control.response_tendency is not None
            and intervention.response_tendency is not None
            and intervention.response_tendency.suggested_next_step
            != control.response_tendency.suggested_next_step,
            "metric": {
                "control_growth_priority": control.developmental_priority_hints.get("growth_priority"),
                "intervention_growth_priority": intervention.developmental_priority_hints.get("growth_priority"),
                "control_next_step": control.response_tendency.suggested_next_step if control.response_tendency else None,
                "intervention_next_step": (
                    intervention.response_tendency.suggested_next_step if intervention.response_tendency else None
                ),
                "intervention_surface_reasons": intervention.developmental_proposal_candidates[0].get(
                    "surface_reasons", []
                )
                if intervention.developmental_proposal_candidates
                else [],
            },
        }
    )

    control = _run(
        _packet(
            event_id="pair2_control",
            runtime_summary={
                "developmental_self_context": _owner_context(owner_revision=3, stagnation_signal=0.14),
                "developmental_context": _host_context(stagnation_signal_hint=0.14),
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="pair2_intervention",
            runtime_summary={
                "developmental_self_context": _owner_context(owner_revision=4, stagnation_signal=0.58),
                "developmental_context": _host_context(stagnation_signal_hint=0.58),
            },
        )
    )
    pairs.append(
        {
            "pair_id": "high_stagnation_signal",
            "passed": control.developmental_proposal_candidates == []
            and intervention.developmental_proposal_candidates != []
            and intervention.policy_hint.get("developmental_adaptation_bias") == "guarded",
            "metric": {
                "control_adaptation_mode": control.developmental_priority_hints.get("adaptation_mode"),
                "intervention_adaptation_mode": intervention.developmental_priority_hints.get("adaptation_mode"),
                "intervention_surface_reasons": intervention.developmental_proposal_candidates[0].get(
                    "surface_reasons", []
                )
                if intervention.developmental_proposal_candidates
                else [],
            },
        }
    )

    control = _run(
        _packet(
            event_id="pair3_control",
            runtime_summary={
                "developmental_self_context": _owner_context(owner_revision=5, continuity_score=0.71),
                "developmental_context": _host_context(continuity_gap=0.33, identity_guard="bounded"),
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="pair3_intervention",
            runtime_summary={
                "developmental_self_context": _owner_context(owner_revision=6, continuity_score=0.71),
                "developmental_context": _host_context(continuity_gap=0.33, identity_guard="strict"),
            },
        )
    )
    pairs.append(
        {
            "pair_id": "identity_guard_prioritization",
            "passed": bool(control.developmental_proposal_candidates)
            and bool(intervention.developmental_proposal_candidates)
            and control.policy_hint.get("identity_preservation_guard") == "bounded"
            and intervention.policy_hint.get("identity_preservation_guard") == "strict"
            and intervention.developmental_writeback_candidate.get("behavioral_authority") == "none",
            "metric": {
                "control_identity_guard": control.developmental_priority_hints.get("identity_preservation_guard"),
                "intervention_identity_guard": intervention.developmental_priority_hints.get(
                    "identity_preservation_guard"
                ),
            },
        }
    )

    control = _run(
        _packet(
            event_id="pair4_control",
            runtime_summary={
                "developmental_self_context": _owner_context(owner_revision=7, continuity_note="stable review"),
                "developmental_context": _host_context(),
            },
        )
    )
    intervention = _run(
        _packet(
            event_id="pair4_intervention",
            runtime_summary={
                "developmental_self_context": _owner_context(
                    owner_revision=8,
                    continuity_note="same metrics, different wording only",
                ),
                "developmental_context": _host_context(),
            },
        )
    )
    pairs.append(
        {
            "pair_id": "text_only_change_has_no_effect",
            "passed": control.developmental_proposal_candidates == intervention.developmental_proposal_candidates == []
            and control.developmental_self_delta == intervention.developmental_self_delta == {}
            and control.response_tendency is not None
            and intervention.response_tendency is not None
            and control.response_tendency.to_dict() == intervention.response_tendency.to_dict(),
            "metric": {
                "control_priority_hints": control.developmental_priority_hints,
                "intervention_priority_hints": intervention.developmental_priority_hints,
                "control_next_step": control.response_tendency.suggested_next_step if control.response_tendency else None,
                "intervention_next_step": (
                    intervention.response_tendency.suggested_next_step if intervention.response_tendency else None
                ),
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
        "status": "pass" if passed_count >= 4 else "hold",
        "verification_level": "V3" if passed_count >= 4 else "V2",
        "evidence_level": "E3" if passed_count >= 4 else "E2",
        "pair_count": len(pairs),
        "passed_count": passed_count,
        "pairs": pairs,
    }
    json_path = ARTIFACTS_ROOT / "mvp16_causal_validation_current.json"
    md_path = ARTIFACTS_ROOT / "mvp16_causal_validation_current.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# MVP16 Causal Validation",
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
