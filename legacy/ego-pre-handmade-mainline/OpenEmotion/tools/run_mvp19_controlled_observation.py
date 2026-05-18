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

from openemotion.selfhood_integration import (  # noqa: E402
    SelfhoodIntegrationOwner,
    SelfhoodIntegrationStore,
)
from runtime_mainline_observation_common import append_observation_records, build_runtime_observation_record  # noqa: E402
from telegram_mainline_common import init_runtime  # noqa: E402

from app.telegram_runtime_bridge import TelegramRuntimeBridge  # noqa: E402


ARTIFACTS_ROOT = OPENEMOTION_ROOT / "artifacts" / "mvp19"

DEFAULT_OWNER_BOOTSTRAP = {
    "posture": "review",
    "dominant_pressure_axis": "embodied_self",
    "stability_bias": 0.73,
    "integration_confidence": 0.61,
    "active_axis_count": 5,
    "rationale_summary": "bounded cross-axis review before broader action",
    "priority_reason": "self-model uncertainty and embodied pressure outweigh growth expansion",
    "highest_conflict_severity": "medium",
    "conflict_count": 2,
    "unresolved_conflict_refs": [
        "conflict:self_model_vs_growth",
        "conflict:boundary_vs_repair",
    ],
    "blocked_axes": ["developmental_self"],
    "stabilize_weight": 0.76,
    "conserve_weight": 0.74,
    "guard_weight": 0.71,
    "review_weight": 0.82,
    "repair_weight": 0.47,
    "grow_weight": 0.18,
    "reflective_modifier": 0.16,
    "upstream_pressure_sources": [
        "self_model_low_confidence",
        "maintenance_pressure_high",
        "social_repair_breach",
        "embodied_boundary_pressure",
    ],
    "selected_priority": "review",
    "stabilize_explore_preferred": "stabilize",
    "repair_progress_preferred": "repair",
    "social_boundary_preferred": "boundary",
    "source_refs": ["mvp19:controlled_bootstrap"],
}

DEFAULT_DEVELOPMENTAL_CONTEXT = {
    "source": "runtime_v2",
    "continuity_gap": 0.42,
    "growth_pressure_hint": 0.78,
    "stagnation_signal_hint": 0.21,
    "identity_guard": "strict",
    "replay_debt": 0.0,
    "promotion_budget": "controlled_axis",
    "drift_markers": ["growth_pressure_pending"],
}

DEFAULT_SOCIAL_CONTEXT = {
    "source": "runtime_v2",
    "counterpart_id": "telegram:8420019401",
    "relationship_event": "commitment_breach",
    "relationship_continuity": "strained",
    "trust_drift": -0.24,
    "commitment_event": "breach",
    "commitment_breach": True,
    "repair_outcome": "pending",
    "unresolved_repair": True,
    "boundary_signal": "cautious",
    "promotion_budget": "review_only",
}

DEFAULT_ENVIRONMENT_CONTEXT = {
    "source": "runtime_v2",
    "action_ref": "delivery:telegram:turn_001",
    "coupling_event": "delivery_feedback",
    "outcome_type": "failure",
    "outcome_summary": "delivery timeout elevated resource and boundary pressure",
    "resource_pressure_hint": 0.83,
    "slack_hint": 0.16,
    "boundary_signal": "guarded",
    "boundary_pressure_hint": 0.72,
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
        "先把跨轴整合保持在 proposal-only writeback，不要直接升级成外发权限。",
        "如果 self-model 信心低、资源和边界压力高，就先走 stability-first review。",
    ]


def _seed_owner_state(
    *,
    store: SelfhoodIntegrationStore,
    owner_bootstrap: Optional[Dict[str, Any]] = None,
) -> None:
    bootstrap = dict(DEFAULT_OWNER_BOOTSTRAP)
    bootstrap.update(dict(owner_bootstrap or {}))
    source_refs = list(bootstrap.get("source_refs") or DEFAULT_OWNER_BOOTSTRAP["source_refs"])
    owner = SelfhoodIntegrationOwner(store=store)
    owner.set_integration_state(
        posture=str(bootstrap.get("posture") or DEFAULT_OWNER_BOOTSTRAP["posture"]),
        dominant_pressure_axis=str(
            bootstrap.get("dominant_pressure_axis")
            or DEFAULT_OWNER_BOOTSTRAP["dominant_pressure_axis"]
        ),
        stability_bias=float(
            bootstrap.get("stability_bias") or DEFAULT_OWNER_BOOTSTRAP["stability_bias"]
        ),
        integration_confidence=float(
            bootstrap.get("integration_confidence")
            or DEFAULT_OWNER_BOOTSTRAP["integration_confidence"]
        ),
        active_axis_count=int(
            bootstrap.get("active_axis_count") or DEFAULT_OWNER_BOOTSTRAP["active_axis_count"]
        ),
        rationale_summary=str(
            bootstrap.get("rationale_summary") or DEFAULT_OWNER_BOOTSTRAP["rationale_summary"]
        ),
        source_refs=source_refs,
    )
    owner.set_cross_axis_priority_state(
        selected_priority=str(
            bootstrap.get("selected_priority") or DEFAULT_OWNER_BOOTSTRAP["selected_priority"]
        ),
        stabilize_weight=float(
            bootstrap.get("stabilize_weight") or DEFAULT_OWNER_BOOTSTRAP["stabilize_weight"]
        ),
        conserve_weight=float(
            bootstrap.get("conserve_weight") or DEFAULT_OWNER_BOOTSTRAP["conserve_weight"]
        ),
        guard_weight=float(
            bootstrap.get("guard_weight") or DEFAULT_OWNER_BOOTSTRAP["guard_weight"]
        ),
        review_weight=float(
            bootstrap.get("review_weight") or DEFAULT_OWNER_BOOTSTRAP["review_weight"]
        ),
        repair_weight=float(
            bootstrap.get("repair_weight") or DEFAULT_OWNER_BOOTSTRAP["repair_weight"]
        ),
        grow_weight=float(bootstrap.get("grow_weight") or DEFAULT_OWNER_BOOTSTRAP["grow_weight"]),
        reflective_modifier=float(
            bootstrap.get("reflective_modifier") or DEFAULT_OWNER_BOOTSTRAP["reflective_modifier"]
        ),
        priority_reason=str(
            bootstrap.get("priority_reason") or DEFAULT_OWNER_BOOTSTRAP["priority_reason"]
        ),
        upstream_pressure_sources=list(
            bootstrap.get("upstream_pressure_sources")
            or DEFAULT_OWNER_BOOTSTRAP["upstream_pressure_sources"]
        ),
        source_refs=source_refs,
    )
    owner.set_proposal_conflict_state(
        highest_severity=str(
            bootstrap.get("highest_conflict_severity")
            or DEFAULT_OWNER_BOOTSTRAP["highest_conflict_severity"]
        ),
        conflict_count=int(
            bootstrap.get("conflict_count") or DEFAULT_OWNER_BOOTSTRAP["conflict_count"]
        ),
        unresolved_conflict_refs=list(
            bootstrap.get("unresolved_conflict_refs")
            or DEFAULT_OWNER_BOOTSTRAP["unresolved_conflict_refs"]
        ),
        blocked_axes=list(
            bootstrap.get("blocked_axes") or DEFAULT_OWNER_BOOTSTRAP["blocked_axes"]
        ),
        resolution_posture=str(
            bootstrap.get("selected_priority") or DEFAULT_OWNER_BOOTSTRAP["selected_priority"]
        ),
        source_refs=source_refs,
    )
    owner.set_stabilize_explore_balance(
        stabilize_weight=float(
            bootstrap.get("stabilize_weight") or DEFAULT_OWNER_BOOTSTRAP["stabilize_weight"]
        ),
        explore_weight=1.0
        - float(bootstrap.get("stabilize_weight") or DEFAULT_OWNER_BOOTSTRAP["stabilize_weight"]),
        preferred_pole=str(
            bootstrap.get("stabilize_explore_preferred")
            or DEFAULT_OWNER_BOOTSTRAP["stabilize_explore_preferred"]
        ),
        rationale="stability-first arbitration keeps exploration bounded under pressure",
        source_refs=source_refs,
    )
    owner.set_repair_progress_balance(
        repair_weight=float(
            bootstrap.get("repair_weight") or DEFAULT_OWNER_BOOTSTRAP["repair_weight"]
        ),
        progress_weight=1.0
        - float(bootstrap.get("repair_weight") or DEFAULT_OWNER_BOOTSTRAP["repair_weight"]),
        preferred_pole=str(
            bootstrap.get("repair_progress_preferred")
            or DEFAULT_OWNER_BOOTSTRAP["repair_progress_preferred"]
        ),
        rationale="repair stays bounded and cannot outrank stronger stability guards",
        source_refs=source_refs,
    )
    owner.set_social_boundary_balance(
        social_weight=float(
            bootstrap.get("repair_weight") or DEFAULT_OWNER_BOOTSTRAP["repair_weight"]
        ),
        boundary_weight=float(
            bootstrap.get("guard_weight") or DEFAULT_OWNER_BOOTSTRAP["guard_weight"]
        ),
        preferred_pole=str(
            bootstrap.get("social_boundary_preferred")
            or DEFAULT_OWNER_BOOTSTRAP["social_boundary_preferred"]
        ),
        rationale="boundary pressure can outweigh social repair under guarded arbitration",
        source_refs=source_refs,
    )
    proposal = owner.propose_integrated_tendency(
        tendency_label="review_first_integration",
        priority_mode=str(
            bootstrap.get("selected_priority") or DEFAULT_OWNER_BOOTSTRAP["selected_priority"]
        ),
        proposed_effects={
            "integrated_policy_hints": {
                "selected_priority": str(
                    bootstrap.get("selected_priority") or DEFAULT_OWNER_BOOTSTRAP["selected_priority"]
                )
            }
        },
        justification="bootstrap bounded cross-axis integration proposal",
        source_refs=source_refs,
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
        recommendation="guard boundary and conserve resources before broader action",
        priority_weight=0.79,
        guardrail_summary="advisory_only_no_upstream_owner_mutation",
        source_refs=["embodied_pressure_high"],
    )
    owner.record_integration_event(
        event_type="bootstrap_proposal",
        reference_id=proposal.proposal_id,
        gate_verdict="allow_writeback",
        details={"source": "controlled_bootstrap"},
    )
    owner.persist(
        update_source="owner_bootstrap",
        trace_reference="mvp19:controlled_bootstrap",
    )


async def _run_runtime_selfhood_observation_session(
    *,
    messages: List[str],
    session_id: str,
    runtime: Any,
    resource_budget_hint: Dict[str, Any],
    maintenance_context: Dict[str, Any],
    developmental_context: Dict[str, Any],
    social_context: Dict[str, Any],
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
        state.ingress_context["developmental_context"] = dict(developmental_context)
        state.ingress_context["social_context"] = dict(social_context)
        state.ingress_context["environment_context"] = dict(environment_context)
        state.ingress_context["risk_level"] = "high"

        ingress_created_at = datetime.now(timezone.utc).isoformat()
        ingress_event_id = (
            f"mvp19_ingress_{index:03d}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
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
                    f"mvp19_delivery_{index:03d}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
                ),
                delivery_created_at=delivery_created_at,
            )
        )

    return runtime, runtime.get_state(session_id), records


def _render_markdown(payload: Dict[str, Any]) -> str:
    writeback = dict(payload.get("selfhood_integration_writeback") or {})
    decision = dict(writeback.get("decision") or {})
    record = dict(writeback.get("record") or {})
    lines = [
        "# MVP19 Controlled Observation Report",
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
        f"- self_integration_writeback_gate: `{payload.get('self_integration_writeback_gate')}`",
        f"- changed_fields: `{decision.get('changed_fields')}`",
        f"- active_axis_count: `{decision.get('active_axis_count')}`",
        f"- axis_hint_count: `{payload.get('axis_hint_count')}`",
        f"- integration_audit_entry_count: `{payload.get('integration_audit_entry_count')}`",
        f"- revision_id: `{record.get('revision_id')}`",
        f"- trace_reference: `{record.get('trace_reference')}`",
        "",
        "## Selfhood Observation",
        "",
        f"- self_integration_proposal_present: `{payload.get('self_integration_proposal_present')}`",
        f"- proposal_only_discipline_consistent: `{payload.get('proposal_only_discipline_consistent')}`",
        f"- behavioral_authority_none: `{payload.get('behavioral_authority_none')}`",
        f"- bounded_influence_present: `{payload.get('bounded_influence_present')}`",
        f"- selected_priority: `{payload.get('selected_priority')}`",
        f"- dominant_pressure_axis: `{payload.get('dominant_pressure_axis')}`",
        f"- highest_conflict_severity: `{payload.get('highest_conflict_severity')}`",
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
    developmental_context: Optional[Dict[str, Any]] = None,
    social_context: Optional[Dict[str, Any]] = None,
    environment_context: Optional[Dict[str, Any]] = None,
    owner_bootstrap: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    artifacts_dir = artifacts_dir or (ARTIFACTS_ROOT / f"controlled_mainline_{stamp}")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    runtime = init_runtime()
    if runtime.proto_self_runtime is None:
        raise RuntimeError("Proto-Self runtime is not enabled; cannot run MVP19 controlled observation")

    store = SelfhoodIntegrationStore(base_dir=artifacts_dir / "formal_selfhood_integration")
    if store.load() is None:
        _seed_owner_state(store=store, owner_bootstrap=owner_bootstrap)
    runtime.proto_self_runtime.selfhood_integration_store = store

    runtime, state, records = await _run_runtime_selfhood_observation_session(
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
            "replay_inconsistency": True,
            "maintenance_debt_increment": 0.2,
            "debt_priority": 0.78,
            "continuity_signal": 0.58,
            "operator_note": "controlled_observation",
        },
        developmental_context=developmental_context or dict(DEFAULT_DEVELOPMENTAL_CONTEXT),
        social_context=social_context or dict(DEFAULT_SOCIAL_CONTEXT),
        environment_context=environment_context or dict(DEFAULT_ENVIRONMENT_CONTEXT),
    )
    observation_log = artifacts_dir / "runtime_harness_observation.jsonl"
    append_observation_records(observation_log, records)

    proto_self_context = dict(state.proto_self_context or {})
    writeback = dict(proto_self_context.get("selfhood_integration_writeback") or {})
    decision = dict(writeback.get("decision") or {})
    revision_log = store.load_revision_log()
    latest_revision = revision_log[-1].model_dump(mode="json") if revision_log else None
    replay = store.replay()

    delta = dict(proto_self_context.get("self_integration_delta") or {})
    priority_snapshot = dict(proto_self_context.get("cross_axis_priority_snapshot") or {})
    conflict_snapshot = dict(proto_self_context.get("proposal_conflict_snapshot") or {})
    policy_hints = dict(proto_self_context.get("integrated_policy_hints") or {})
    integrated_tendency = dict(proto_self_context.get("integrated_tendency_proposal") or {})
    axis_hints = dict(proto_self_context.get("axis_arbitration_hints") or {})
    audit_entries = list(proto_self_context.get("integration_audit_entries") or [])
    writeback_candidate = dict(proto_self_context.get("self_integration_writeback_candidate") or {})

    self_integration_proposal_present = bool(
        delta or priority_snapshot or conflict_snapshot or integrated_tendency or writeback_candidate
    )
    proposal_only_discipline_consistent = self_integration_proposal_present and (
        str(writeback_candidate.get("proposal_discipline") or "") == "proposal_only"
        and str(integrated_tendency.get("proposal_discipline") or "") == "proposal_only"
    )
    behavioral_authority_none = (
        str(writeback_candidate.get("behavioral_authority") or "") == "none"
        and str(integrated_tendency.get("behavioral_authority") or "") == "none"
        and all(bool(hint.get("advisory_only", True)) for hint in axis_hints.values())
    )
    bounded_influence_present = bool(delta) and bool(priority_snapshot) and bool(policy_hints)

    accepted = (
        decision.get("gate_verdict") == "allow_writeback"
        and bool(latest_revision)
        and replay is not None
        and self_integration_proposal_present
        and proposal_only_discipline_consistent
        and behavioral_authority_none
        and bounded_influence_present
    )

    payload = {
        "schema_version": "mvp19.controlled_observation.v1",
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
        "self_integration_delta": delta,
        "cross_axis_priority_snapshot": priority_snapshot,
        "proposal_conflict_snapshot": conflict_snapshot,
        "integrated_policy_hints": policy_hints,
        "integrated_tendency_proposal": integrated_tendency,
        "axis_arbitration_hints": axis_hints,
        "axis_hint_count": len(axis_hints),
        "integration_audit_entries": audit_entries,
        "integration_audit_entry_count": len(audit_entries),
        "self_integration_writeback_candidate": writeback_candidate,
        "selfhood_integration_context": proto_self_context.get("selfhood_integration_context") or {},
        "selfhood_integration_writeback": writeback,
        "self_integration_writeback_gate": decision.get("gate_verdict"),
        "self_integration_proposal_present": self_integration_proposal_present,
        "proposal_only_discipline_consistent": proposal_only_discipline_consistent,
        "behavioral_authority_none": behavioral_authority_none,
        "bounded_influence_present": bounded_influence_present,
        "selected_priority": priority_snapshot.get("selected_priority")
        or delta.get("selected_priority"),
        "dominant_pressure_axis": priority_snapshot.get("dominant_pressure_axis")
        or policy_hints.get("dominant_pressure_axis")
        or delta.get("dominant_pressure_axis"),
        "highest_conflict_severity": conflict_snapshot.get("highest_severity")
        or policy_hints.get("conflict_severity"),
        "latest_revision": latest_revision,
        "revision_count": len(revision_log),
        "replay_valid": replay is not None,
        "owner_snapshot": store.load_snapshot() or {},
        "status": "pass" if accepted else "hold",
        "verification_level": "V4" if accepted else "V3",
        "evidence_level": "E4" if accepted else "E3",
        "boundary": (
            "This report proves a controlled runtime-mainline selfhood integration proposal-only "
            "writeback path. It does not prove live autonomy, direct reply authority, or broader "
            "transport maturity."
        ),
        "external_risk_note": (
            "Provider 429/401 remains an external budget-layer risk; it is not counted as a WP14 "
            "blocker unless it regresses formal owner selfhood integration writeback."
        ),
    }

    report_json = artifacts_dir / "mvp19_controlled_observation_report.json"
    report_md = artifacts_dir / "mvp19_controlled_observation_report.md"
    report_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    report_md.write_text(_render_markdown(payload), encoding="utf-8")

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        output_json.with_suffix(".md").write_text(_render_markdown(payload), encoding="utf-8")
    return payload


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run the first controlled MVP19 selfhood observation.")
    parser.add_argument("--message", action="append", default=[], help="Add one scripted user message")
    parser.add_argument("--messages-file", default=None, help="JSON list or newline-delimited text file")
    parser.add_argument(
        "--session-id",
        default=f"session:mvp19:controlled:{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    )
    parser.add_argument(
        "--output-json",
        default=str(ARTIFACTS_ROOT / "mvp19_controlled_observation_current.json"),
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
