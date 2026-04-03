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

from openemotion.reflective_self import ReflectiveSelfOwner, ReflectiveSelfStore, ReflectionTargetType
from runtime_mainline_observation_common import append_observation_records, build_runtime_observation_record
from telegram_mainline_common import init_runtime

from app.telegram_runtime_bridge import TelegramRuntimeBridge


ARTIFACTS_ROOT = OPENEMOTION_ROOT / "artifacts" / "mvp15"

DEFAULT_OWNER_BOOTSTRAP = {
    "target_id": "decision:target",
    "target_type": "decision",
    "target_reference": "decision:target",
    "target_reason": "controlled_observation_bootstrap",
    "target_salience": 0.85,
    "target_evidence_refs": ["mvp15:controlled_bootstrap"],
    "reflection_trigger_source": "controlled_observation_bootstrap",
    "reflection_priority": 0.75,
    "reflection_evidence_refs": ["mvp15:controlled_bootstrap"],
    "unresolved_summary": "previous decision needs bounded reflective follow-up",
    "unresolved_severity": 0.7,
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
    return value[: limit - 1].rstrip() + "..."


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
        "先别把外发权放开，先把这次反思记录成正式候选。",
        "如果前一个判断是错的，先列清楚可能的修订方向。",
        "保持 proposal-only，不要直接改写行为权。",
    ]


def _resolve_target_type(raw: Any) -> ReflectionTargetType:
    try:
        return ReflectionTargetType(str(raw or "").strip() or ReflectionTargetType.DECISION.value)
    except ValueError:
        return ReflectionTargetType.STATE


def _seed_owner_state(
    *,
    store: ReflectiveSelfStore,
    owner_bootstrap: Optional[Dict[str, Any]] = None,
) -> None:
    bootstrap = dict(DEFAULT_OWNER_BOOTSTRAP)
    bootstrap.update(dict(owner_bootstrap or {}))
    owner = ReflectiveSelfOwner(store=store)
    target_id = str(bootstrap.get("target_id") or "decision:target")
    target_reference = str(bootstrap.get("target_reference") or target_id)
    target_type = _resolve_target_type(bootstrap.get("target_type"))
    owner.upsert_target(
        target_id=target_id,
        target_type=target_type,
        reference=target_reference,
        reason=str(bootstrap.get("target_reason") or "controlled_observation_bootstrap"),
        salience=float(bootstrap.get("target_salience") or 0.85),
        evidence_refs=list(bootstrap.get("target_evidence_refs") or ["mvp15:controlled_bootstrap"]),
    )
    for extra_target in list(bootstrap.get("extra_targets") or []):
        if not isinstance(extra_target, dict):
            continue
        extra_target_id = str(extra_target.get("target_id") or "").strip()
        if not extra_target_id:
            continue
        owner.upsert_target(
            target_id=extra_target_id,
            target_type=_resolve_target_type(extra_target.get("target_type")),
            reference=str(extra_target.get("target_reference") or extra_target_id),
            reason=str(extra_target.get("target_reason") or "controlled_observation_bootstrap"),
            salience=float(extra_target.get("target_salience") or 0.5),
            evidence_refs=list(extra_target.get("target_evidence_refs") or []),
        )
    owner.enqueue_reflection(
        target_type=target_type,
        target_reference=target_reference,
        trigger_source=str(bootstrap.get("reflection_trigger_source") or "controlled_observation_bootstrap"),
        priority=float(bootstrap.get("reflection_priority") or 0.75),
        evidence_refs=list(bootstrap.get("reflection_evidence_refs") or ["mvp15:controlled_bootstrap"]),
    )
    owner.add_unresolved_item(
        summary=str(
            bootstrap.get("unresolved_summary") or "previous decision needs bounded reflective follow-up"
        ),
        linked_record_id=(
            str(bootstrap.get("unresolved_linked_record_id")).strip()
            if bootstrap.get("unresolved_linked_record_id")
            else None
        ),
        severity=float(bootstrap.get("unresolved_severity") or 0.7),
    )
    owner.persist(
        update_source="owner_bootstrap",
        trace_reference="mvp15:controlled_bootstrap",
    )


async def _run_runtime_reflective_observation_session(
    *,
    messages: List[str],
    session_id: str,
    runtime: Any,
    resource_budget_hint: Dict[str, Any],
    maintenance_context: Dict[str, Any],
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

        ingress_created_at = datetime.now(timezone.utc).isoformat()
        ingress_event_id = f"mvp15_ingress_{index:03d}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
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
                    f"mvp15_delivery_{index:03d}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
                ),
                delivery_created_at=delivery_created_at,
            )
        )

    return runtime, runtime.get_state(session_id), records


def _render_markdown(payload: Dict[str, Any]) -> str:
    writeback = dict(payload.get("reflective_self_writeback") or {})
    decision = dict(writeback.get("decision") or {})
    record = dict(writeback.get("record") or {})
    lines = [
        "# MVP15 Controlled Observation Report",
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
        f"- gate_verdict: `{decision.get('gate_verdict')}`",
        f"- changed_fields: `{decision.get('changed_fields')}`",
        f"- proposal_count: `{decision.get('proposal_count')}`",
        f"- revision_id: `{record.get('revision_id')}`",
        f"- trace_reference: `{record.get('trace_reference')}`",
        "",
        "## Reflection Observation",
        "",
        f"- reflection_candidate_present: `{payload.get('reflection_candidate_present')}`",
        f"- proposal_discipline_consistent: `{payload.get('proposal_discipline_consistent')}`",
        f"- behavioral_authority_none: `{payload.get('behavioral_authority_none')}`",
        f"- delta_fields: `{payload.get('reflective_self_delta_fields')}`",
        f"- latest_target_ids: `{payload.get('target_ids')}`",
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
    owner_bootstrap: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    artifacts_dir = artifacts_dir or (ARTIFACTS_ROOT / f"controlled_mainline_{stamp}")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    runtime = init_runtime()
    if runtime.proto_self_runtime is None:
        raise RuntimeError("Proto-Self runtime is not enabled; cannot run MVP15 controlled observation")

    store = ReflectiveSelfStore(base_dir=artifacts_dir / "formal_reflective_self")
    if store.load() is None:
        _seed_owner_state(store=store, owner_bootstrap=owner_bootstrap)
    runtime.proto_self_runtime.reflective_self_store = store

    runtime, state, records = await _run_runtime_reflective_observation_session(
        messages=messages,
        session_id=session_id,
        runtime=runtime,
        resource_budget_hint=resource_budget_hint
        or {
            "reserve_level": "normal",
            "active_task": False,
            "waiting_for_user_input": False,
        },
        maintenance_context=maintenance_context
        or {
            "replay_inconsistency": True,
            "continuity_signal": 0.4,
            "maintenance_debt_increment": 0.15,
            "reflection_reason": "controlled_observation",
        },
    )
    observation_log = artifacts_dir / "runtime_harness_observation.jsonl"
    append_observation_records(observation_log, records)

    proto_self_context = dict(state.proto_self_context or {})
    writeback = dict(proto_self_context.get("reflective_self_writeback") or {})
    decision = dict(writeback.get("decision") or {})
    revision_log = store.load_revision_log()
    latest_revision = revision_log[-1].model_dump(mode="json") if revision_log else None
    replay = store.replay()
    revision_proposal_candidates = list(proto_self_context.get("revision_proposal_candidates") or [])
    reflection_writeback_candidate = dict(proto_self_context.get("reflection_writeback_candidate") or {})
    proposal_discipline_consistent = bool(revision_proposal_candidates) and all(
        str(candidate.get("proposal_discipline") or "") == "proposal_only"
        and str(candidate.get("effect_scope") or "") in {"", "proposal_only"}
        for candidate in revision_proposal_candidates
    )
    behavioral_authority_none = str(reflection_writeback_candidate.get("behavioral_authority") or "") == "none"

    accepted = (
        decision.get("gate_verdict") == "allow_writeback"
        and bool(latest_revision)
        and replay is not None
        and proto_self_context.get("reflection_writeback_candidate") is not None
        and proposal_discipline_consistent
        and behavioral_authority_none
    )

    payload = {
        "schema_version": "mvp15.controlled_observation.v1",
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
        "reflective_self_delta": proto_self_context.get("reflective_self_delta") or {},
        "reflective_self_delta_fields": sorted((proto_self_context.get("reflective_self_delta") or {}).keys()),
        "revision_proposal_candidates": revision_proposal_candidates,
        "reflection_writeback_candidate": proto_self_context.get("reflection_writeback_candidate"),
        "reflection_candidate_present": bool(proto_self_context.get("reflection_writeback_candidate")),
        "proposal_discipline_consistent": proposal_discipline_consistent,
        "behavioral_authority_none": behavioral_authority_none,
        "reflective_self_writeback": writeback,
        "confidence_adjustment_hints": proto_self_context.get("confidence_adjustment_hints") or {},
        "maintenance_priority_hints": proto_self_context.get("maintenance_priority_hints") or {},
        "target_ids": list((proto_self_context.get("reflective_self_delta") or {}).get("target_ids") or []),
        "latest_revision": latest_revision,
        "revision_count": len(revision_log),
        "replay_valid": replay is not None,
        "owner_snapshot": store.load_snapshot() or {},
        "status": "pass" if accepted else "hold",
        "verification_level": "V4" if accepted else "V3",
        "evidence_level": "E4" if accepted else "E3",
        "boundary": (
            "This report proves a controlled runtime-mainline reflective-self writeback path with proposal-only "
            "diagnosis/revision candidates. It does not prove live autonomy, direct reply authority, or broader "
            "transport maturity."
        ),
        "external_risk_note": (
            "Provider 429/401 remains an external budget-layer risk; it is not counted as a WP10 blocker unless it "
            "regresses formal owner writeback."
        ),
    }

    report_json = artifacts_dir / "mvp15_controlled_observation_report.json"
    report_md = artifacts_dir / "mvp15_controlled_observation_report.md"
    report_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    report_md.write_text(_render_markdown(payload), encoding="utf-8")

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        output_json.with_suffix(".md").write_text(_render_markdown(payload), encoding="utf-8")
    return payload


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run the first controlled MVP15 reflective-self observation.")
    parser.add_argument("--message", action="append", default=[], help="Add one scripted user message")
    parser.add_argument("--messages-file", default=None, help="JSON list or newline-delimited text file")
    parser.add_argument(
        "--session-id",
        default=f"session:mvp15:controlled:{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    )
    parser.add_argument(
        "--output-json",
        default=str(ARTIFACTS_ROOT / "mvp15_controlled_observation_current.json"),
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
