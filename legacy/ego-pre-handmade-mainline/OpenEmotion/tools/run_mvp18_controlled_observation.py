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

from openemotion.embodied_self import (  # noqa: E402
    BoundaryPressureMode,
    EmbodiedProposalStatus,
    EmbodiedSelfOwner,
    EmbodiedSelfStore,
    EnvironmentCouplingStatus,
)
from runtime_mainline_observation_common import append_observation_records, build_runtime_observation_record  # noqa: E402
from telegram_mainline_common import init_runtime  # noqa: E402

from app.telegram_runtime_bridge import TelegramRuntimeBridge  # noqa: E402


ARTIFACTS_ROOT = OPENEMOTION_ROOT / "artifacts" / "mvp18"

DEFAULT_OWNER_BOOTSTRAP = {
    "resource_slack": 0.33,
    "perceived_load": 0.72,
    "action_readiness": 0.39,
    "last_action_source": "runtime_harness",
    "coupling_id": "delivery:telegram:repair_turn",
    "coupling_strength": 0.77,
    "controllability_estimate": 0.44,
    "recent_outcome_summary": "delivery failure raised embodied stabilization pressure",
    "coupling_status": "degraded",
    "resource_pressure_id": "resource:runtime",
    "pressure_level": 0.81,
    "slack_level": 0.19,
    "recovery_bias": 0.88,
    "boundary_id": "self_world",
    "boundary_pressure_level": 0.67,
    "boundary_mode": "guarded",
    "boundary_reason": "controlled_observation_guard",
    "action_ref": "delivery:telegram:repair_turn",
    "outcome_type": "failure",
    "consequence_summary": "recent bounded failure increased consequence pressure",
    "impact_score": 0.74,
    "consequence_controllability_estimate": 0.51,
    "distinction_summary": "bounded_self_world_boundary_under_resource_pressure",
    "guard_bias": 0.64,
    "repair_bias": 0.79,
    "proposal_target_ref": "embodied_stabilization",
    "issue_summary": "resource/boundary pressure needs governed stabilization review",
    "proposed_adjustment": {"resource_bias": "conserve", "boundary_mode": "guarded"},
    "justification": "controlled observation bootstrap proposal",
    "source_refs": ["mvp18:controlled_bootstrap"],
}

DEFAULT_ENVIRONMENT_CONTEXT = {
    "source": "runtime_v2",
    "action_ref": "delivery:telegram:repair_turn",
    "coupling_event": "delivery_feedback",
    "outcome_type": "failure",
    "outcome_summary": "delivery failure raised bounded embodied stabilization pressure",
    "resource_pressure_hint": 0.84,
    "slack_hint": 0.17,
    "boundary_signal": "guarded",
    "boundary_pressure_hint": 0.73,
    "stabilization_needed": True,
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
        "先把 resource/slack pressure 的调整留在 proposal-only writeback。",
        "action consequence 只做受治理回写，不要直接扩成环境动作权限。",
        "self/world boundary pressure 先走 embodied_writeback_gate。",
    ]


def _seed_owner_state(
    *,
    store: EmbodiedSelfStore,
    owner_bootstrap: Optional[Dict[str, Any]] = None,
) -> None:
    bootstrap = dict(DEFAULT_OWNER_BOOTSTRAP)
    bootstrap.update(dict(owner_bootstrap or {}))
    source_refs = list(bootstrap.get("source_refs") or DEFAULT_OWNER_BOOTSTRAP["source_refs"])
    owner = EmbodiedSelfOwner(store=store)
    owner.set_embodied_state(
        resource_slack=float(bootstrap.get("resource_slack") or DEFAULT_OWNER_BOOTSTRAP["resource_slack"]),
        perceived_load=float(bootstrap.get("perceived_load") or DEFAULT_OWNER_BOOTSTRAP["perceived_load"]),
        action_readiness=float(bootstrap.get("action_readiness") or DEFAULT_OWNER_BOOTSTRAP["action_readiness"]),
        last_action_source=str(
            bootstrap.get("last_action_source") or DEFAULT_OWNER_BOOTSTRAP["last_action_source"]
        ),
        source_refs=source_refs,
    )
    owner.upsert_environment_coupling(
        coupling_id=str(bootstrap.get("coupling_id") or DEFAULT_OWNER_BOOTSTRAP["coupling_id"]),
        coupling_strength=float(
            bootstrap.get("coupling_strength") or DEFAULT_OWNER_BOOTSTRAP["coupling_strength"]
        ),
        controllability_estimate=float(
            bootstrap.get("controllability_estimate")
            or DEFAULT_OWNER_BOOTSTRAP["controllability_estimate"]
        ),
        recent_outcome_summary=str(
            bootstrap.get("recent_outcome_summary")
            or DEFAULT_OWNER_BOOTSTRAP["recent_outcome_summary"]
        ),
        status=EnvironmentCouplingStatus(
            str(bootstrap.get("coupling_status") or DEFAULT_OWNER_BOOTSTRAP["coupling_status"])
        ),
        source_refs=source_refs,
    )
    owner.set_resource_pressure(
        pressure_id=str(
            bootstrap.get("resource_pressure_id") or DEFAULT_OWNER_BOOTSTRAP["resource_pressure_id"]
        ),
        pressure_level=float(
            bootstrap.get("pressure_level") or DEFAULT_OWNER_BOOTSTRAP["pressure_level"]
        ),
        slack_level=float(bootstrap.get("slack_level") or DEFAULT_OWNER_BOOTSTRAP["slack_level"]),
        recovery_bias=float(
            bootstrap.get("recovery_bias") or DEFAULT_OWNER_BOOTSTRAP["recovery_bias"]
        ),
        source_refs=source_refs,
    )
    owner.set_boundary_pressure(
        boundary_id=str(bootstrap.get("boundary_id") or DEFAULT_OWNER_BOOTSTRAP["boundary_id"]),
        pressure_level=float(
            bootstrap.get("boundary_pressure_level")
            or DEFAULT_OWNER_BOOTSTRAP["boundary_pressure_level"]
        ),
        mode=BoundaryPressureMode(
            str(bootstrap.get("boundary_mode") or DEFAULT_OWNER_BOOTSTRAP["boundary_mode"])
        ),
        reason=str(bootstrap.get("boundary_reason") or DEFAULT_OWNER_BOOTSTRAP["boundary_reason"]),
        source_refs=source_refs,
    )
    owner.record_action_consequence(
        action_ref=str(bootstrap.get("action_ref") or DEFAULT_OWNER_BOOTSTRAP["action_ref"]),
        outcome_type=str(bootstrap.get("outcome_type") or DEFAULT_OWNER_BOOTSTRAP["outcome_type"]),
        consequence_summary=str(
            bootstrap.get("consequence_summary") or DEFAULT_OWNER_BOOTSTRAP["consequence_summary"]
        ),
        impact_score=float(bootstrap.get("impact_score") or DEFAULT_OWNER_BOOTSTRAP["impact_score"]),
        controllability_estimate=float(
            bootstrap.get("consequence_controllability_estimate")
            or DEFAULT_OWNER_BOOTSTRAP["consequence_controllability_estimate"]
        ),
        source_refs=source_refs,
    )
    owner.set_self_world_boundary_semantics(
        distinction_summary=str(
            bootstrap.get("distinction_summary") or DEFAULT_OWNER_BOOTSTRAP["distinction_summary"]
        ),
        guard_bias=float(bootstrap.get("guard_bias") or DEFAULT_OWNER_BOOTSTRAP["guard_bias"]),
        repair_bias=float(bootstrap.get("repair_bias") or DEFAULT_OWNER_BOOTSTRAP["repair_bias"]),
        source_refs=source_refs,
    )
    proposal = owner.propose_stabilization(
        target_ref=str(
            bootstrap.get("proposal_target_ref") or DEFAULT_OWNER_BOOTSTRAP["proposal_target_ref"]
        ),
        issue_summary=str(bootstrap.get("issue_summary") or DEFAULT_OWNER_BOOTSTRAP["issue_summary"]),
        proposed_adjustment=dict(
            bootstrap.get("proposed_adjustment") or DEFAULT_OWNER_BOOTSTRAP["proposed_adjustment"]
        ),
        justification=str(
            bootstrap.get("justification") or DEFAULT_OWNER_BOOTSTRAP["justification"]
        ),
        source_refs=source_refs,
    )
    owner.set_proposal_status(proposal.proposal_id, status=EmbodiedProposalStatus.HELD)
    owner.persist(
        update_source="owner_bootstrap",
        trace_reference="mvp18:controlled_bootstrap",
    )


async def _run_runtime_embodied_observation_session(
    *,
    messages: List[str],
    session_id: str,
    runtime: Any,
    resource_budget_hint: Dict[str, Any],
    maintenance_context: Dict[str, Any],
    environment_context: Dict[str, Any],
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
        state.ingress_context["environment_context"] = dict(environment_context)
        state.ingress_context["risk_level"] = "high"

        ingress_created_at = datetime.now(timezone.utc).isoformat()
        ingress_event_id = (
            f"mvp18_ingress_{index:03d}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
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
                    f"mvp18_delivery_{index:03d}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
                ),
                delivery_created_at=delivery_created_at,
            )
        )

    return runtime, runtime.get_state(session_id), records


def _render_markdown(payload: Dict[str, Any]) -> str:
    writeback = dict(payload.get("embodied_writeback") or {})
    decision = dict(writeback.get("decision") or {})
    record = dict(writeback.get("record") or {})
    lines = [
        "# MVP18 Controlled Observation Report",
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
        f"- embodied_writeback_gate: `{decision.get('gate_verdict')}`",
        f"- changed_fields: `{decision.get('changed_fields')}`",
        f"- proposal_count: `{decision.get('proposal_count')}`",
        f"- consequence_candidate_count: `{decision.get('consequence_candidate_count')}`",
        f"- revision_id: `{record.get('revision_id')}`",
        f"- trace_reference: `{record.get('trace_reference')}`",
        "",
        "## Embodied Observation",
        "",
        f"- embodied_proposal_present: `{payload.get('embodied_proposal_present')}`",
        f"- proposal_only_discipline_consistent: `{payload.get('proposal_only_discipline_consistent')}`",
        f"- behavioral_authority_none: `{payload.get('behavioral_authority_none')}`",
        f"- bounded_influence_present: `{payload.get('bounded_influence_present')}`",
        f"- resource_bias: `{payload.get('resource_bias')}`",
        f"- stabilization_bias: `{payload.get('stabilization_bias')}`",
        f"- boundary_mode: `{payload.get('boundary_mode')}`",
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
    environment_context: Optional[Dict[str, Any]] = None,
    owner_bootstrap: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    artifacts_dir = artifacts_dir or (ARTIFACTS_ROOT / f"controlled_mainline_{stamp}")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    runtime = init_runtime()
    if runtime.proto_self_runtime is None:
        raise RuntimeError("Proto-Self runtime is not enabled; cannot run MVP18 controlled observation")

    store = EmbodiedSelfStore(base_dir=artifacts_dir / "formal_embodied_self")
    if store.load() is None:
        _seed_owner_state(store=store, owner_bootstrap=owner_bootstrap)
    runtime.proto_self_runtime.embodied_self_store = store

    runtime, state, records = await _run_runtime_embodied_observation_session(
        messages=messages,
        session_id=session_id,
        runtime=runtime,
        resource_budget_hint=resource_budget_hint
        or {
            "reserve_level": "low",
            "active_task": True,
            "waiting_for_user_input": False,
        },
        maintenance_context=maintenance_context
        or {
            "replay_inconsistency": False,
            "maintenance_debt_increment": 0.0,
            "continuity_signal": 0.28,
            "embodied_reason": "controlled_observation",
        },
        environment_context=environment_context or dict(DEFAULT_ENVIRONMENT_CONTEXT),
    )
    observation_log = artifacts_dir / "runtime_harness_observation.jsonl"
    append_observation_records(observation_log, records)

    proto_self_context = dict(state.proto_self_context or {})
    writeback = dict(proto_self_context.get("embodied_writeback") or {})
    decision = dict(writeback.get("decision") or {})
    revision_log = store.load_revision_log()
    latest_revision = revision_log[-1].model_dump(mode="json") if revision_log else None
    replay = store.replay()

    consequence_update_candidates = list(proto_self_context.get("consequence_update_candidates") or [])
    repair_candidates = list(proto_self_context.get("repair_or_stabilize_proposal_candidates") or [])
    writeback_candidate = dict(proto_self_context.get("embodied_writeback_candidate") or {})
    resource_boundary_snapshot = dict(proto_self_context.get("resource_boundary_snapshot") or {})
    embodied_policy_hints = dict(proto_self_context.get("embodied_policy_hints") or {})

    embodied_proposal_present = bool(
        consequence_update_candidates or repair_candidates or writeback_candidate
    )
    proposal_only_discipline_consistent = embodied_proposal_present and all(
        str(candidate.get("proposal_discipline") or "") == "proposal_only"
        and str(candidate.get("effect_scope") or "") in {"", "proposal_only"}
        for candidate in [*consequence_update_candidates, *repair_candidates]
    ) and str(writeback_candidate.get("proposal_discipline") or "") == "proposal_only"
    behavioral_authority_none = str(writeback_candidate.get("behavioral_authority") or "") == "none" and all(
        str(candidate.get("behavioral_authority") or "") in {"", "none"}
        for candidate in [*consequence_update_candidates, *repair_candidates]
    )
    bounded_influence_present = bool(proto_self_context.get("embodied_self_delta")) and bool(
        resource_boundary_snapshot
    ) and bool(embodied_policy_hints)

    accepted = (
        decision.get("gate_verdict") == "allow_writeback"
        and bool(latest_revision)
        and replay is not None
        and embodied_proposal_present
        and proposal_only_discipline_consistent
        and behavioral_authority_none
        and bounded_influence_present
    )

    payload = {
        "schema_version": "mvp18.controlled_observation.v1",
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
        "embodied_self_delta": proto_self_context.get("embodied_self_delta") or {},
        "embodied_self_delta_fields": sorted((proto_self_context.get("embodied_self_delta") or {}).keys()),
        "consequence_update_candidates": consequence_update_candidates,
        "resource_boundary_snapshot": resource_boundary_snapshot,
        "embodied_policy_hints": embodied_policy_hints,
        "repair_or_stabilize_proposal_candidates": repair_candidates,
        "embodied_writeback_candidate": writeback_candidate,
        "environment_context": proto_self_context.get("environment_context") or {},
        "embodied_writeback": writeback,
        "embodied_writeback_gate": decision.get("gate_verdict"),
        "embodied_proposal_present": embodied_proposal_present,
        "proposal_only_discipline_consistent": proposal_only_discipline_consistent,
        "behavioral_authority_none": behavioral_authority_none,
        "bounded_influence_present": bounded_influence_present,
        "resource_bias": embodied_policy_hints.get("resource_bias"),
        "stabilization_bias": embodied_policy_hints.get("stabilization_bias"),
        "boundary_mode": embodied_policy_hints.get("boundary_mode"),
        "latest_revision": latest_revision,
        "revision_count": len(revision_log),
        "replay_valid": replay is not None,
        "owner_snapshot": store.load_snapshot() or {},
        "status": "pass" if accepted else "hold",
        "verification_level": "V4" if accepted else "V3",
        "evidence_level": "E4" if accepted else "E3",
        "boundary": (
            "This report proves a controlled runtime-mainline embodied proposal-only writeback path. "
            "It does not prove live autonomy, direct reply authority, or broader transport maturity."
        ),
        "external_risk_note": (
            "Provider 429/401 remains an external budget-layer risk; it is not counted as a WP13 blocker "
            "unless it regresses formal owner embodied writeback."
        ),
    }

    report_json = artifacts_dir / "mvp18_controlled_observation_report.json"
    report_md = artifacts_dir / "mvp18_controlled_observation_report.md"
    report_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    report_md.write_text(_render_markdown(payload), encoding="utf-8")

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        output_json.with_suffix(".md").write_text(_render_markdown(payload), encoding="utf-8")
    return payload


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run the first controlled MVP18 embodied observation.")
    parser.add_argument("--message", action="append", default=[], help="Add one scripted user message")
    parser.add_argument("--messages-file", default=None, help="JSON list or newline-delimited text file")
    parser.add_argument(
        "--session-id",
        default=f"session:mvp18:controlled:{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    )
    parser.add_argument(
        "--output-json",
        default=str(ARTIFACTS_ROOT / "mvp18_controlled_observation_current.json"),
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
