#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[2]
EGOCORE_ROOT = ROOT / "EgoCore"
OPENEMOTION_ROOT = ROOT / "OpenEmotion"
SCRIPTS_ROOT = ROOT / "scripts"
if str(EGOCORE_ROOT) not in sys.path:
    sys.path.insert(0, str(EGOCORE_ROOT))
if str(OPENEMOTION_ROOT) not in sys.path:
    sys.path.insert(0, str(OPENEMOTION_ROOT))
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from openemotion.initiative_self import (  # noqa: E402
    CommitmentContinuityStatus,
    HostProactiveCandidateStatus,
    InitiativePriority,
    InitiativeProposalStatus,
    InitiativeSelfOwner,
    InitiativeSelfStore,
)
from runtime_mainline_observation_common import (  # noqa: E402
    append_observation_records,
    build_runtime_observation_record,
)
from telegram_mainline_common import init_runtime  # noqa: E402

from app.telegram_runtime_bridge import TelegramRuntimeBridge  # noqa: E402


ARTIFACTS_ROOT = OPENEMOTION_ROOT / "artifacts" / "mvp20"

DEFAULT_OWNER_BOOTSTRAP = {
    "dominant_mode": "review",
    "initiative_pressure": 0.76,
    "commitment_carryover_bias": 0.84,
    "recent_delivery_sensitivity": 0.42,
    "rationale_summary": "bounded initiative continuity stays host-governed and proposal-only",
    "selected_priority": "carry_forward",
    "hold_weight": 0.24,
    "review_weight": 0.58,
    "prepare_weight": 0.37,
    "carry_forward_weight": 0.88,
    "schedule_weight": 0.16,
    "priority_reason": "carry forward an existing bounded commitment under current runtime review",
    "active_commitments_count": 2,
    "carried_commitment_refs": [
        "commitment:followup:bounded",
        "commitment:repair_review:bounded",
    ],
    "blocked_commitment_refs": [],
    "continuity_confidence": 0.78,
    "carryover_summary": "bounded followup remains active but still requires host gate review",
    "proposal_label": "carry_forward_commitment_under_review",
    "proposed_effects": {
        "initiative_policy_hints": {
            "initiative_bias": "carry_forward",
            "host_proactive_mode": "candidate",
        }
    },
    "proposal_justification": "controlled observation bootstrap proposal",
    "host_candidate_label": "governed_host_proactive_followup",
    "host_continuity_basis": "commitment:followup:bounded",
    "source_refs": ["mvp20:controlled_bootstrap"],
}

DEFAULT_INITIATIVE_CONTEXT = {
    "source": "runtime_v2",
    "initiative_trigger": "commitment_followup",
    "continuity_ref": "commitment:followup:bounded",
    "pending_commitment_refs": [
        "commitment:followup:bounded",
        "commitment:repair_review:bounded",
    ],
    "blocked_commitment_refs": [],
    "reserve_level": "medium",
    "recent_delivery_status": "sent",
    "delivery_failure": False,
    "idle_seconds": 1800.0,
    "host_lane_hint": "host_proactive_outbox",
    "promotion_budget": "controlled_axis",
}


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


def _trim_text(text: Any, *, limit: int = 72) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _load_messages(args: argparse.Namespace) -> List[str]:
    messages: List[str] = list(args.message or [])
    if args.messages_file:
        content = Path(args.messages_file).read_text(encoding="utf-8")
        if args.messages_file.endswith(".json"):
            payload = json.loads(content)
            if not isinstance(payload, list):
                raise ValueError("messages-file JSON must be a list of strings")
            messages.extend(str(item).strip() for item in payload if str(item).strip())
        else:
            messages.extend(line.strip() for line in content.splitlines() if line.strip())
    if messages:
        return messages
    return [
        "先把已有承诺以 proposal-only 的方式延续，不要直接升级成外发。",
        "host proactive candidate 只能进入 gated review，不能直接发出去。",
    ]


def _seed_owner_state(
    *,
    store: InitiativeSelfStore,
    owner_bootstrap: Optional[Dict[str, Any]] = None,
) -> None:
    bootstrap = dict(DEFAULT_OWNER_BOOTSTRAP)
    bootstrap.update(dict(owner_bootstrap or {}))
    source_refs = list(bootstrap.get("source_refs") or DEFAULT_OWNER_BOOTSTRAP["source_refs"])
    owner = InitiativeSelfOwner(store=store)
    owner.set_initiative_state(
        dominant_mode=InitiativePriority(str(bootstrap.get("dominant_mode") or "review")),
        initiative_pressure=float(bootstrap.get("initiative_pressure") or 0.0),
        commitment_carryover_bias=float(bootstrap.get("commitment_carryover_bias") or 0.0),
        recent_delivery_sensitivity=float(bootstrap.get("recent_delivery_sensitivity") or 0.0),
        rationale_summary=str(
            bootstrap.get("rationale_summary") or DEFAULT_OWNER_BOOTSTRAP["rationale_summary"]
        ),
        source_refs=source_refs,
    )
    owner.set_initiative_priority_state(
        selected_priority=InitiativePriority(str(bootstrap.get("selected_priority") or "review")),
        hold_weight=float(bootstrap.get("hold_weight") or 0.0),
        review_weight=float(bootstrap.get("review_weight") or 0.0),
        prepare_weight=float(bootstrap.get("prepare_weight") or 0.0),
        carry_forward_weight=float(bootstrap.get("carry_forward_weight") or 0.0),
        schedule_weight=float(bootstrap.get("schedule_weight") or 0.0),
        priority_reason=str(
            bootstrap.get("priority_reason") or DEFAULT_OWNER_BOOTSTRAP["priority_reason"]
        ),
        upstream_pressure_sources=[
            "wp14:selfhood_integration",
            "wp12:social_commitment_continuity",
        ],
        source_refs=source_refs,
    )
    owner.set_commitment_continuity_state(
        status=CommitmentContinuityStatus.ACTIVE,
        active_commitments_count=int(
            bootstrap.get("active_commitments_count")
            or DEFAULT_OWNER_BOOTSTRAP["active_commitments_count"]
        ),
        carried_commitment_refs=list(
            bootstrap.get("carried_commitment_refs")
            or DEFAULT_OWNER_BOOTSTRAP["carried_commitment_refs"]
        ),
        blocked_commitment_refs=list(
            bootstrap.get("blocked_commitment_refs")
            or DEFAULT_OWNER_BOOTSTRAP["blocked_commitment_refs"]
        ),
        continuity_confidence=float(
            bootstrap.get("continuity_confidence")
            or DEFAULT_OWNER_BOOTSTRAP["continuity_confidence"]
        ),
        carryover_summary=str(
            bootstrap.get("carryover_summary") or DEFAULT_OWNER_BOOTSTRAP["carryover_summary"]
        ),
        source_refs=source_refs,
    )
    proposal = owner.propose_initiative(
        proposal_label=str(
            bootstrap.get("proposal_label") or DEFAULT_OWNER_BOOTSTRAP["proposal_label"]
        ),
        priority_mode=InitiativePriority(str(bootstrap.get("selected_priority") or "review")),
        proposed_effects=dict(
            bootstrap.get("proposed_effects") or DEFAULT_OWNER_BOOTSTRAP["proposed_effects"]
        ),
        justification=str(
            bootstrap.get("proposal_justification")
            or DEFAULT_OWNER_BOOTSTRAP["proposal_justification"]
        ),
        source_refs=source_refs,
    )
    owner.set_initiative_proposal_status(status=InitiativeProposalStatus.HELD)
    host_candidate = owner.set_host_proactive_candidate(
        candidate_label=str(
            bootstrap.get("host_candidate_label")
            or DEFAULT_OWNER_BOOTSTRAP["host_candidate_label"]
        ),
        continuity_basis=str(
            bootstrap.get("host_continuity_basis")
            or DEFAULT_OWNER_BOOTSTRAP["host_continuity_basis"]
        ),
        source_refs=source_refs,
    )
    owner.set_host_proactive_candidate_status(status=HostProactiveCandidateStatus.HELD)
    owner.record_initiative_event(
        event_type="initiative_bootstrap",
        reference_id=proposal.proposal_id,
        gate_verdict="allow_writeback",
        details={"host_candidate_id": host_candidate.candidate_id},
    )
    owner.persist(
        update_source="owner_bootstrap",
        trace_reference="mvp20:controlled_bootstrap",
    )


async def _run_runtime_initiative_observation_session(
    *,
    messages: List[str],
    session_id: str,
    runtime: Any,
    resource_budget_hint: Dict[str, Any],
    maintenance_context: Dict[str, Any],
    initiative_context: Dict[str, Any],
) -> Tuple[Any, Any, List[Dict[str, Any]]]:
    ingress_bridge = TelegramRuntimeBridge()
    records: List[Dict[str, Any]] = []

    for index, text in enumerate(messages, start=1):
        state = runtime.get_state(session_id)
        decision = await ingress_bridge.inspect_ingress_semantic(text, state, llm_client=None)
        state.ingress_context = ingress_bridge.build_ingress_context(decision, state)
        state.ingress_context["observation_source"] = "direct_real"
        state.ingress_context["traffic_source"] = "real"
        state.ingress_context["resource_budget_hint"] = dict(resource_budget_hint)
        state.ingress_context["maintenance_context"] = dict(maintenance_context)
        state.ingress_context["initiative_context"] = dict(initiative_context)

        ingress_created_at = datetime.now(timezone.utc).isoformat()
        ingress_event_id = (
            f"mvp20_ingress_{index:03d}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
        )
        result = await runtime.run_turn_typed(
            session_id=session_id,
            user_input=text,
            source="runtime_harness",
        )
        delivery_created_at = datetime.now(timezone.utc).isoformat()
        turn_id = (
            str(getattr(getattr(result, "reply", None), "turn_id", "") or "")
            or str(getattr(state, "active_turn_id", "") or "")
            or f"turn_{index:03d}"
        )
        records.append(
            build_runtime_observation_record(
                session_id=session_id,
                turn_id=turn_id,
                user_input=text,
                result=result,
                state=state,
                transport_source="runtime_harness",
                source="runtime_harness",
                ingress_event_id=ingress_event_id,
                ingress_created_at=ingress_created_at,
                delivery_event_id=(
                    f"mvp20_delivery_{index:03d}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
                ),
                delivery_created_at=delivery_created_at,
            )
        )

    return runtime, runtime.get_state(session_id), records


def _render_markdown(payload: Dict[str, Any]) -> str:
    writeback = dict(payload.get("initiative_writeback") or {})
    decision = dict(writeback.get("decision") or {})
    record = dict(writeback.get("record") or {})
    lines = [
        "# MVP20 Controlled Observation Report",
        "",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- git_commit_short: `{payload.get('git_commit_short')}`",
        f"- session_id: `{payload.get('session_id')}`",
        f"- observation_count: `{payload.get('observation_count')}`",
        f"- verification_level: `{payload.get('verification_level')}`",
        f"- evidence_level: `{payload.get('evidence_level')}`",
        f"- status: `{payload.get('status')}`",
        "",
        "## Writeback",
        "",
        f"- initiative_writeback_gate: `{decision.get('gate_verdict')}`",
        f"- changed_fields: `{decision.get('changed_fields')}`",
        f"- proposal_count: `{decision.get('proposal_count')}`",
        f"- host_proactive_candidate_present: `{decision.get('host_proactive_candidate_present')}`",
        f"- revision_id: `{record.get('revision_id')}`",
        f"- trace_reference: `{record.get('trace_reference')}`",
        "",
        "## Initiative Observation",
        "",
        f"- initiative_proposal_present: `{payload.get('initiative_proposal_present')}`",
        f"- proposal_only_discipline_consistent: `{payload.get('proposal_only_discipline_consistent')}`",
        f"- behavioral_authority_none: `{payload.get('behavioral_authority_none')}`",
        f"- bounded_influence_present: `{payload.get('bounded_influence_present')}`",
        f"- selected_priority: `{payload.get('selected_priority')}`",
        f"- commitment_mode: `{payload.get('commitment_mode')}`",
        f"- host_proactive_mode: `{payload.get('host_proactive_mode')}`",
        f"- replay_valid: `{payload.get('replay_valid')}`",
        f"- revision_count: `{payload.get('revision_count')}`",
        "",
        "## Boundary",
        "",
        payload.get("boundary", ""),
        "",
    ]
    return "\n".join(lines)


async def run_controlled_observation(
    *,
    messages: List[str],
    session_id: str,
    output_json: Optional[Path],
    artifacts_dir: Optional[Path] = None,
    scenario_manifest: Optional[Dict[str, Any]] = None,
    resource_budget_hint: Optional[Dict[str, Any]] = None,
    maintenance_context: Optional[Dict[str, Any]] = None,
    initiative_context: Optional[Dict[str, Any]] = None,
    owner_bootstrap: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    artifacts_dir = artifacts_dir or (ARTIFACTS_ROOT / f"controlled_mainline_{stamp}")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    runtime = init_runtime()
    if runtime.proto_self_runtime is None:
        raise RuntimeError("Proto-Self runtime is not enabled; cannot run MVP20 controlled observation")

    store = InitiativeSelfStore(base_dir=artifacts_dir / "formal_initiative_self")
    if store.load() is None:
        _seed_owner_state(store=store, owner_bootstrap=owner_bootstrap)
    runtime.proto_self_runtime.initiative_self_store = store

    runtime, state, records = await _run_runtime_initiative_observation_session(
        messages=messages,
        session_id=session_id,
        runtime=runtime,
        resource_budget_hint=resource_budget_hint
        or {
            "reserve_level": "medium",
            "active_task": True,
            "waiting_for_user_input": False,
        },
        maintenance_context=maintenance_context
        or {
            "replay_inconsistency": False,
            "maintenance_debt_increment": 0.0,
            "continuity_signal": 0.72,
            "initiative_reason": "controlled_observation",
        },
        initiative_context=initiative_context or dict(DEFAULT_INITIATIVE_CONTEXT),
    )
    observation_log = artifacts_dir / "runtime_harness_observation.jsonl"
    append_observation_records(observation_log, records)

    proto_self_context = dict(state.proto_self_context or {})
    writeback = dict(proto_self_context.get("initiative_writeback") or {})
    decision = dict(writeback.get("decision") or {})
    revision_log = store.load_revision_log()
    latest_revision = revision_log[-1].model_dump(mode="json") if revision_log else None
    replay = store.replay()

    initiative_delta = dict(proto_self_context.get("initiative_self_delta") or {})
    proposal_candidates = list(proto_self_context.get("initiative_proposal_candidates") or [])
    commitment_snapshot = dict(proto_self_context.get("commitment_execution_snapshot") or {})
    initiative_policy_hints = dict(proto_self_context.get("initiative_policy_hints") or {})
    host_proactive_candidate = dict(proto_self_context.get("host_proactive_candidate") or {})
    writeback_candidate = dict(proto_self_context.get("initiative_writeback_candidate") or {})

    initiative_proposal_present = bool(
        initiative_delta or proposal_candidates or host_proactive_candidate or writeback_candidate
    )
    proposal_only_discipline_consistent = initiative_proposal_present and all(
        str(candidate.get("proposal_discipline") or candidate.get("effect_scope") or "proposal_only")
        in {"proposal_only"}
        and str(candidate.get("behavioral_authority") or "none") == "none"
        for candidate in proposal_candidates
    ) and (
        not host_proactive_candidate
        or (
            str(host_proactive_candidate.get("proposal_discipline") or "") == "proposal_only"
            and str(host_proactive_candidate.get("behavioral_authority") or "") == "none"
        )
    ) and (
        not writeback_candidate
        or (
            str(writeback_candidate.get("proposal_discipline") or "") == "proposal_only"
            and str(writeback_candidate.get("behavioral_authority") or "") == "none"
        )
    )
    behavioral_authority_none = (
        str(writeback_candidate.get("behavioral_authority") or "") == "none"
        and all(str(candidate.get("behavioral_authority") or "none") == "none" for candidate in proposal_candidates)
        and (
            not host_proactive_candidate
            or str(host_proactive_candidate.get("behavioral_authority") or "") == "none"
        )
    )
    bounded_influence_present = bool(initiative_delta) and bool(commitment_snapshot) and bool(
        initiative_policy_hints
    )

    accepted = (
        decision.get("gate_verdict") == "allow_writeback"
        and bool(latest_revision)
        and replay is not None
        and initiative_proposal_present
        and proposal_only_discipline_consistent
        and behavioral_authority_none
        and bounded_influence_present
    )

    payload = {
        "schema_version": "mvp20.controlled_observation.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit_short": _git_commit_short(),
        "session_id": session_id,
        "observation_count": len(records),
        "observation_log": str(observation_log),
        "scenario_manifest": dict(scenario_manifest or {}) or None,
        "observation_refs": [
            {
                "kind": "runtime_mainline_delivery",
                "event_id": record.get("delivery_event_id"),
                "created_at": record.get("delivery_created_at"),
                "text_preview": _trim_text(record.get("delivery_text"), limit=72),
            }
            for record in records[-4:]
        ],
        "initiative_self_delta": initiative_delta,
        "initiative_self_delta_fields": sorted(initiative_delta.keys()),
        "initiative_proposal_candidates": proposal_candidates,
        "commitment_execution_snapshot": commitment_snapshot,
        "initiative_policy_hints": initiative_policy_hints,
        "host_proactive_candidate": host_proactive_candidate or None,
        "initiative_writeback_candidate": writeback_candidate or None,
        "initiative_context": proto_self_context.get("initiative_context") or {},
        "initiative_writeback": writeback,
        "initiative_writeback_gate": decision.get("gate_verdict"),
        "initiative_proposal_present": initiative_proposal_present,
        "proposal_only_discipline_consistent": proposal_only_discipline_consistent,
        "behavioral_authority_none": behavioral_authority_none,
        "bounded_influence_present": bounded_influence_present,
        "selected_priority": initiative_policy_hints.get("initiative_bias"),
        "commitment_mode": initiative_policy_hints.get("commitment_mode"),
        "host_proactive_mode": initiative_policy_hints.get("host_proactive_mode"),
        "latest_revision": latest_revision,
        "revision_count": len(revision_log),
        "replay_valid": replay is not None,
        "owner_snapshot": store.load_snapshot() or {},
        "status": "pass" if accepted else "hold",
        "verification_level": "V4" if accepted else "V3",
        "evidence_level": "E4" if accepted else "E3",
        "boundary": (
            "This report proves a controlled runtime-mainline initiative proposal-only writeback path. "
            "It does not prove live autonomy, direct reply authority, tool authority, or broader transport maturity."
        ),
        "external_risk_note": (
            "Provider 429/401 remains an external budget-layer risk; it is not counted as a WP15 blocker "
            "unless it regresses formal owner initiative writeback."
        ),
    }

    report_json = artifacts_dir / "mvp20_controlled_observation_report.json"
    report_md = artifacts_dir / "mvp20_controlled_observation_report.md"
    report_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    report_md.write_text(_render_markdown(payload), encoding="utf-8")

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        output_json.with_suffix(".md").write_text(_render_markdown(payload), encoding="utf-8")
    return payload


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run the first controlled MVP20 initiative observation.")
    parser.add_argument("--message", action="append", default=[], help="Add one scripted user message")
    parser.add_argument("--messages-file", default=None, help="JSON list or newline-delimited text file")
    parser.add_argument(
        "--session-id",
        default=f"session:mvp20:controlled:{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    )
    parser.add_argument(
        "--output-json",
        default=str(ARTIFACTS_ROOT / "mvp20_controlled_observation_current.json"),
    )
    args = parser.parse_args()

    payload = await run_controlled_observation(
        messages=_load_messages(args),
        session_id=args.session_id,
        output_json=Path(args.output_json),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
