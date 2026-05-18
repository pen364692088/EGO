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

from openemotion.initiative_realization import (  # noqa: E402
    CommitmentFulfillmentStatus,
    ControlledDeliveryCandidateStatus,
    InitiativeRealizationOwner,
    InitiativeRealizationStore,
    RealizationMode,
    RealizationProposalStatus,
)
from runtime_mainline_observation_common import (  # noqa: E402
    append_observation_records,
    build_runtime_observation_record,
)
from telegram_mainline_common import init_runtime  # noqa: E402

from app.telegram_runtime_bridge import TelegramRuntimeBridge  # noqa: E402


ARTIFACTS_ROOT = OPENEMOTION_ROOT / "artifacts" / "mvp21"

DEFAULT_OWNER_BOOTSTRAP = {
    "dominant_mode": "review",
    "realization_pressure": 0.21,
    "fulfillment_readiness": 0.31,
    "hold_bias": 0.73,
    "failure_recovery_bias": 0.69,
    "rationale_summary": "bounded initiative realization stays host-governed and proposal-only",
    "selected_lane": "review",
    "hold_weight": 0.76,
    "review_weight": 0.88,
    "prepare_weight": 0.32,
    "mediate_weight": 0.41,
    "fulfill_weight": 0.24,
    "lane_reason": "review under current runtime mainline before any host delivery execution",
    "host_lane_hints": ["host_reality_review", "host_continuity_queue"],
    "fulfillment_status": "active",
    "active_commitments_count": 2,
    "ready_commitments_count": 1,
    "realized_commitment_refs": ["realization:followup:bounded"],
    "blocked_commitment_refs": [],
    "continuity_confidence": 0.74,
    "fulfillment_summary": "bounded commitments remain eligible only through controlled host-lane review",
    "candidate_label": "realization_review_candidate_under_host_gate",
    "candidate_mode": "review",
    "proposed_effects": {
        "initiative_realization_policy_hints": {
            "realization_bias": "review_first",
            "host_lane_mode": "review",
        }
    },
    "candidate_justification": "controlled observation bootstrap realization candidate",
    "controlled_delivery_label": "governed_controlled_delivery_review_candidate",
    "readiness_basis": "realization_continuity_review",
    "delivery_readiness": 0.67,
    "host_lane_hint": "host_reality_review",
    "source_refs": ["mvp21:controlled_bootstrap"],
}

DEFAULT_HOST_PROACTIVE_CONTEXT = {
    "source": "runtime_v2",
    "host_lane_hint": "host_reality_review",
    "host_lane_hints": ["host_reality_review", "host_continuity_queue"],
    "readiness_basis": "realization_continuity_review",
    "delivery_readiness": 0.67,
    "recent_delivery_status": "sent",
    "recent_delivery_success": True,
    "promotion_budget": "controlled_axis",
    "pending_realization_refs": [
        "realization:followup:bounded",
        "realization:repair_review:bounded",
    ],
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
        "先把这次 realization proposal 留在 gate 内审查，不要直接进入外发或 transport。",
        "controlled delivery candidate 只能进入 host review，不能直接交付。",
    ]


def _seed_owner_state(
    *,
    store: InitiativeRealizationStore,
    owner_bootstrap: Optional[Dict[str, Any]] = None,
) -> None:
    bootstrap = dict(DEFAULT_OWNER_BOOTSTRAP)
    bootstrap.update(dict(owner_bootstrap or {}))
    source_refs = list(bootstrap.get("source_refs") or DEFAULT_OWNER_BOOTSTRAP["source_refs"])

    owner = InitiativeRealizationOwner(store=store)
    owner.set_realization_state(
        dominant_mode=RealizationMode(str(bootstrap.get("dominant_mode") or "review")),
        realization_pressure=float(bootstrap.get("realization_pressure") or 0.0),
        fulfillment_readiness=float(bootstrap.get("fulfillment_readiness") or 0.0),
        hold_bias=float(bootstrap.get("hold_bias") or 0.0),
        failure_recovery_bias=float(bootstrap.get("failure_recovery_bias") or 0.0),
        rationale_summary=str(
            bootstrap.get("rationale_summary") or DEFAULT_OWNER_BOOTSTRAP["rationale_summary"]
        ),
        source_refs=source_refs,
    )
    owner.set_delivery_readiness_state(
        selected_lane=RealizationMode(str(bootstrap.get("selected_lane") or "review")),
        hold_weight=float(bootstrap.get("hold_weight") or 0.0),
        review_weight=float(bootstrap.get("review_weight") or 0.0),
        prepare_weight=float(bootstrap.get("prepare_weight") or 0.0),
        mediate_weight=float(bootstrap.get("mediate_weight") or 0.0),
        fulfill_weight=float(bootstrap.get("fulfill_weight") or 0.0),
        lane_reason=str(bootstrap.get("lane_reason") or DEFAULT_OWNER_BOOTSTRAP["lane_reason"]),
        host_lane_hints=list(
            bootstrap.get("host_lane_hints") or DEFAULT_OWNER_BOOTSTRAP["host_lane_hints"]
        ),
        source_refs=source_refs,
    )
    owner.set_commitment_fulfillment_state(
        status=CommitmentFulfillmentStatus(
            str(bootstrap.get("fulfillment_status") or "active")
        ),
        active_commitments_count=int(
            bootstrap.get("active_commitments_count")
            or DEFAULT_OWNER_BOOTSTRAP["active_commitments_count"]
        ),
        ready_commitments_count=int(
            bootstrap.get("ready_commitments_count")
            or DEFAULT_OWNER_BOOTSTRAP["ready_commitments_count"]
        ),
        realized_commitment_refs=list(
            bootstrap.get("realized_commitment_refs")
            or DEFAULT_OWNER_BOOTSTRAP["realized_commitment_refs"]
        ),
        blocked_commitment_refs=list(
            bootstrap.get("blocked_commitment_refs")
            or DEFAULT_OWNER_BOOTSTRAP["blocked_commitment_refs"]
        ),
        continuity_confidence=float(
            bootstrap.get("continuity_confidence")
            or DEFAULT_OWNER_BOOTSTRAP["continuity_confidence"]
        ),
        fulfillment_summary=str(
            bootstrap.get("fulfillment_summary")
            or DEFAULT_OWNER_BOOTSTRAP["fulfillment_summary"]
        ),
        source_refs=source_refs,
    )
    candidate = owner.propose_realization(
        candidate_label=str(
            bootstrap.get("candidate_label") or DEFAULT_OWNER_BOOTSTRAP["candidate_label"]
        ),
        selected_mode=RealizationMode(str(bootstrap.get("candidate_mode") or "review")),
        proposed_effects=dict(
            bootstrap.get("proposed_effects") or DEFAULT_OWNER_BOOTSTRAP["proposed_effects"]
        ),
        justification=str(
            bootstrap.get("candidate_justification")
            or DEFAULT_OWNER_BOOTSTRAP["candidate_justification"]
        ),
        source_refs=source_refs,
    )
    owner.set_initiative_realization_candidate_status(status=RealizationProposalStatus.HELD)
    delivery_candidate = owner.set_controlled_delivery_candidate(
        candidate_label=str(
            bootstrap.get("controlled_delivery_label")
            or DEFAULT_OWNER_BOOTSTRAP["controlled_delivery_label"]
        ),
        readiness_basis=str(
            bootstrap.get("readiness_basis") or DEFAULT_OWNER_BOOTSTRAP["readiness_basis"]
        ),
        delivery_readiness=float(
            bootstrap.get("delivery_readiness") or DEFAULT_OWNER_BOOTSTRAP["delivery_readiness"]
        ),
        host_lane_hint=str(
            bootstrap.get("host_lane_hint") or DEFAULT_OWNER_BOOTSTRAP["host_lane_hint"]
        ),
        source_refs=source_refs,
        requested_effects=["review_realization_lane"],
    )
    owner.set_controlled_delivery_candidate_status(
        status=ControlledDeliveryCandidateStatus.HELD
    )
    owner.record_realization_event(
        event_type="initiative_realization_bootstrap",
        reference_id=candidate.candidate_id,
        gate_verdict="allow_writeback",
        details={"delivery_candidate_id": delivery_candidate.candidate_id},
    )
    owner.persist(
        update_source="owner_bootstrap",
        trace_reference="mvp21:controlled_bootstrap",
    )


async def _run_runtime_initiative_realization_observation_session(
    *,
    messages: List[str],
    session_id: str,
    runtime: Any,
    resource_budget_hint: Dict[str, Any],
    maintenance_context: Dict[str, Any],
    host_proactive_context: Dict[str, Any],
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
        state.ingress_context["host_proactive_context"] = dict(host_proactive_context)

        ingress_created_at = datetime.now(timezone.utc).isoformat()
        ingress_event_id = (
            f"mvp21_ingress_{index:03d}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
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
                    f"mvp21_delivery_{index:03d}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
                ),
                delivery_created_at=delivery_created_at,
            )
        )

    return runtime, runtime.get_state(session_id), records


def _render_markdown(payload: Dict[str, Any]) -> str:
    writeback = dict(payload.get("initiative_realization_writeback") or {})
    decision = dict(writeback.get("decision") or {})
    record = dict(writeback.get("record") or {})
    lines = [
        "# MVP21 Controlled Observation Report",
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
        f"- initiative_realization_writeback_gate: `{decision.get('gate_verdict')}`",
        f"- changed_fields: `{decision.get('changed_fields')}`",
        f"- proposal_count: `{decision.get('proposal_count')}`",
        f"- controlled_delivery_candidate_present: `{decision.get('controlled_delivery_candidate_present')}`",
        f"- revision_id: `{record.get('revision_id')}`",
        f"- trace_reference: `{record.get('trace_reference')}`",
        "",
        "## Realization Observation",
        "",
        f"- initiative_realization_proposal_present: `{payload.get('initiative_realization_proposal_present')}`",
        f"- proposal_only_discipline_consistent: `{payload.get('proposal_only_discipline_consistent')}`",
        f"- behavioral_authority_none: `{payload.get('behavioral_authority_none')}`",
        f"- bounded_influence_present: `{payload.get('bounded_influence_present')}`",
        f"- selected_mode: `{payload.get('selected_mode')}`",
        f"- selected_lane: `{payload.get('selected_lane')}`",
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
    host_proactive_context: Optional[Dict[str, Any]] = None,
    owner_bootstrap: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    artifacts_dir = artifacts_dir or (ARTIFACTS_ROOT / f"controlled_mainline_{stamp}")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    runtime = init_runtime()
    if runtime.proto_self_runtime is None:
        raise RuntimeError("Proto-Self runtime is not enabled; cannot run MVP21 controlled observation")

    store = InitiativeRealizationStore(base_dir=artifacts_dir / "formal_initiative_realization")
    if store.load() is None:
        _seed_owner_state(store=store, owner_bootstrap=owner_bootstrap)
    runtime.proto_self_runtime.initiative_realization_store = store

    runtime, state, records = await _run_runtime_initiative_realization_observation_session(
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
            "continuity_signal": 0.76,
            "initiative_realization_reason": "controlled_observation",
        },
        host_proactive_context=host_proactive_context or dict(DEFAULT_HOST_PROACTIVE_CONTEXT),
    )
    observation_log = artifacts_dir / "runtime_harness_observation.jsonl"
    append_observation_records(observation_log, records)

    proto_self_context = dict(state.proto_self_context or {})
    writeback = dict(proto_self_context.get("initiative_realization_writeback") or {})
    decision = dict(writeback.get("decision") or {})
    revision_log = store.load_revision_log()
    latest_revision = revision_log[-1].model_dump(mode="json") if revision_log else None
    replay = store.replay()

    realization_delta = dict(proto_self_context.get("initiative_realization_delta") or {})
    fulfillment_candidates = list(
        proto_self_context.get("commitment_fulfillment_candidates") or []
    )
    readiness_snapshot = dict(proto_self_context.get("delivery_readiness_snapshot") or {})
    host_lane_hints = list(proto_self_context.get("host_lane_hints") or [])
    controlled_delivery_candidate = dict(
        proto_self_context.get("controlled_delivery_candidate") or {}
    )
    writeback_candidate = dict(
        proto_self_context.get("initiative_realization_writeback_candidate") or {}
    )

    proposal_present = bool(
        realization_delta
        or fulfillment_candidates
        or controlled_delivery_candidate
        or writeback_candidate
    )
    proposal_only_discipline_consistent = proposal_present and all(
        str(candidate.get("proposal_discipline") or candidate.get("effect_scope") or "proposal_only")
        in {"proposal_only"}
        and str(candidate.get("behavioral_authority") or "none") == "none"
        for candidate in fulfillment_candidates
    ) and (
        not controlled_delivery_candidate
        or (
            str(
                controlled_delivery_candidate.get("proposal_discipline")
                or controlled_delivery_candidate.get("effect_scope")
                or "proposal_only"
            )
            == "proposal_only"
            and str(controlled_delivery_candidate.get("behavioral_authority") or "none")
            == "none"
        )
    ) and (
        not writeback_candidate
        or (
            str(
                writeback_candidate.get("proposal_discipline")
                or writeback_candidate.get("effect_scope")
                or "proposal_only"
            )
            == "proposal_only"
            and str(writeback_candidate.get("behavioral_authority") or "none") == "none"
        )
    )
    behavioral_authority_none = (
        all(
            str(candidate.get("behavioral_authority") or "none") == "none"
            for candidate in fulfillment_candidates
        )
        and (
            not controlled_delivery_candidate
            or str(controlled_delivery_candidate.get("behavioral_authority") or "none")
            == "none"
        )
        and (
            not writeback_candidate
            or str(writeback_candidate.get("behavioral_authority") or "none") == "none"
        )
    )
    bounded_influence_present = bool(realization_delta) and bool(readiness_snapshot) and bool(
        host_lane_hints
    )

    accepted = (
        decision.get("gate_verdict") == "allow_writeback"
        and bool(latest_revision)
        and replay is not None
        and proposal_present
        and proposal_only_discipline_consistent
        and behavioral_authority_none
        and bounded_influence_present
    )

    payload = {
        "schema_version": "mvp21.controlled_observation.v1",
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
        "initiative_realization_delta": realization_delta,
        "initiative_realization_delta_fields": sorted(realization_delta.keys()),
        "commitment_fulfillment_candidates": fulfillment_candidates,
        "delivery_readiness_snapshot": readiness_snapshot,
        "host_lane_hints": host_lane_hints,
        "controlled_delivery_candidate": controlled_delivery_candidate or None,
        "initiative_realization_writeback_candidate": writeback_candidate or None,
        "initiative_realization_context": proto_self_context.get("initiative_realization_context")
        or {},
        "host_proactive_context": proto_self_context.get("host_proactive_context") or {},
        "initiative_realization_writeback": writeback,
        "initiative_realization_writeback_gate": decision.get("gate_verdict"),
        "initiative_realization_proposal_present": proposal_present,
        "proposal_only_discipline_consistent": proposal_only_discipline_consistent,
        "behavioral_authority_none": behavioral_authority_none,
        "bounded_influence_present": bounded_influence_present,
        "selected_mode": realization_delta.get("selected_mode"),
        "selected_lane": readiness_snapshot.get("selected_lane"),
        "latest_revision": latest_revision,
        "revision_count": len(revision_log),
        "replay_valid": replay is not None,
        "owner_snapshot": store.load_snapshot() or {},
        "status": "pass" if accepted else "hold",
        "verification_level": "V4" if accepted else "V3",
        "evidence_level": "E4" if accepted else "E3",
        "boundary": (
            "This report proves a controlled runtime-mainline initiative realization proposal-only "
            "writeback path. It does not prove live autonomy, direct reply authority, tool authority, "
            "or broader transport maturity."
        ),
        "external_risk_note": (
            "Provider 429/401 remains an external budget-layer risk; it is not counted as a WP16 blocker "
            "unless it regresses formal owner initiative realization writeback."
        ),
    }

    report_json = artifacts_dir / "mvp21_controlled_observation_report.json"
    report_md = artifacts_dir / "mvp21_controlled_observation_report.md"
    report_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    report_md.write_text(_render_markdown(payload), encoding="utf-8")

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        output_json.with_suffix(".md").write_text(_render_markdown(payload), encoding="utf-8")
    return payload


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the first controlled MVP21 initiative realization observation."
    )
    parser.add_argument("--message", action="append", default=[], help="Add one scripted user message")
    parser.add_argument("--messages-file", default=None, help="JSON list or newline-delimited text file")
    parser.add_argument(
        "--session-id",
        default=f"session:mvp21:controlled:{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    )
    parser.add_argument(
        "--output-json",
        default=str(ARTIFACTS_ROOT / "mvp21_controlled_observation_current.json"),
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
