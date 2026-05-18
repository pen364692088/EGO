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

from openemotion.endogenous_drives import EndogenousDriveOwner, EndogenousDriveStore
from openemotion.endogenous_drives.reducers import seed_default_state
from openemotion.endogenous_drives.schemas import DriveType
from runtime_mainline_observation_common import append_observation_records, build_runtime_observation_record
from telegram_mainline_common import init_runtime

from app.telegram_runtime_bridge import TelegramRuntimeBridge


ARTIFACTS_ROOT = OPENEMOTION_ROOT / "artifacts" / "mvp14"


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
    return value[: limit - 1].rstrip() + "…"


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
        "先别扩范围，先补 replay 和 continuity 的维护债。",
        "如果一致性没有补回来，后面的外发都不该升级。",
        "先把当前状态收稳。",
    ]


def _seed_owner_state(
    *,
    store: EndogenousDriveStore,
    drive_overrides: Optional[Dict[str, Any]] = None,
    maintenance_debts: Optional[List[Dict[str, Any]]] = None,
    homeostatic_updates: Optional[List[Dict[str, Any]]] = None,
) -> None:
    owner = EndogenousDriveOwner(initial_state=seed_default_state(), store=store)
    for drive_key, target in dict(drive_overrides or {}).items():
        drive_type = DriveType(str(drive_key))
        current = owner.state.active_drives[drive_type.value].intensity
        owner.update_drive(
            drive_type,
            float(target) - float(current),
            cause="scenario_bootstrap",
        )
    for debt in list(maintenance_debts or []):
        owner.add_maintenance_debt(
            category=str(debt.get("category") or "scenario_debt"),
            amount=float(debt.get("amount") or 0.0),
            priority=float(debt.get("priority") or 0.5),
            source=str(debt.get("source") or "scenario_bootstrap"),
        )
    for signal in list(homeostatic_updates or []):
        signal_id = str(signal.get("signal_id") or "").strip()
        if signal_id:
            owner.update_homeostatic_signal(signal_id, float(signal.get("observed_value") or 0.0))
    owner.persist(
        update_source="owner_bootstrap",
        trace_reference="mvp14:controlled_bootstrap",
    )


async def _run_runtime_drive_observation_session(
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
        ingress_event_id = f"mvp14_ingress_{index:03d}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
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
                    f"mvp14_delivery_{index:03d}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
                ),
                delivery_created_at=delivery_created_at,
            )
        )

    return runtime, runtime.get_state(session_id), records


def _render_markdown(payload: Dict[str, Any]) -> str:
    writeback = dict(payload.get("endogenous_drive_writeback") or {})
    decision = dict(writeback.get("decision") or {})
    record = dict(writeback.get("record") or {})
    lines = [
        "# MVP14 Controlled Observation Report",
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
        f"- revision_id: `{record.get('revision_id')}`",
        f"- trace_reference: `{record.get('trace_reference')}`",
        "",
        "## Drive Observation",
        "",
        f"- maintenance_candidate_present: `{payload.get('maintenance_candidate_present')}`",
        f"- dominant_drive: `{payload.get('dominant_drive')}`",
        f"- delta_fields: `{payload.get('endogenous_drive_delta_fields')}`",
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
    drive_overrides: Optional[Dict[str, Any]] = None,
    maintenance_debts: Optional[List[Dict[str, Any]]] = None,
    homeostatic_updates: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    artifacts_dir = artifacts_dir or (ARTIFACTS_ROOT / f"controlled_mainline_{stamp}")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    runtime = init_runtime()
    if runtime.proto_self_runtime is None:
        raise RuntimeError("Proto-Self runtime is not enabled; cannot run MVP14 controlled observation")

    store = EndogenousDriveStore(base_dir=artifacts_dir / "formal_endogenous_drives")
    if store.load() is None:
        _seed_owner_state(
            store=store,
            drive_overrides=drive_overrides,
            maintenance_debts=maintenance_debts,
            homeostatic_updates=homeostatic_updates,
        )
    runtime.proto_self_runtime.endogenous_drive_store = store

    runtime, state, records = await _run_runtime_drive_observation_session(
        messages=messages,
        session_id=session_id,
        runtime=runtime,
        resource_budget_hint=resource_budget_hint
        or {
            "reserve_level": "low",
            "active_task": False,
            "waiting_for_user_input": False,
        },
        maintenance_context=maintenance_context
        or {
            "replay_inconsistency": True,
            "maintenance_debt_increment": 0.25,
            "continuity_signal": 0.35,
            "debt_category": "replay_verification",
            "debt_priority": 0.9,
        },
    )
    observation_log = artifacts_dir / "runtime_harness_observation.jsonl"
    append_observation_records(observation_log, records)

    proto_self_context = dict(state.proto_self_context or {})
    writeback = dict(proto_self_context.get("endogenous_drive_writeback") or {})
    decision = dict(writeback.get("decision") or {})
    revision_log = store.load_revision_log()
    latest_revision = revision_log[-1].model_dump(mode="json") if revision_log else None
    replay = store.replay()
    accepted = (
        decision.get("gate_verdict") == "allow_writeback"
        and bool(latest_revision)
        and replay is not None
        and proto_self_context.get("self_maintenance_candidate") is not None
    )

    payload = {
        "schema_version": "mvp14.controlled_observation.v1",
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
        "endogenous_drive_delta": proto_self_context.get("endogenous_drive_delta") or {},
        "endogenous_drive_delta_fields": sorted((proto_self_context.get("endogenous_drive_delta") or {}).keys()),
        "endogenous_drive_writeback": writeback,
        "drive_state_snapshot": proto_self_context.get("drive_state_snapshot") or {},
        "priority_snapshot": proto_self_context.get("priority_snapshot") or {},
        "candidate_bias_terms": proto_self_context.get("candidate_bias_terms") or {},
        "self_maintenance_candidate": proto_self_context.get("self_maintenance_candidate"),
        "maintenance_candidate_present": bool(proto_self_context.get("self_maintenance_candidate")),
        "dominant_drive": (proto_self_context.get("priority_snapshot") or {}).get("dominant_drive"),
        "latest_revision": latest_revision,
        "revision_count": len(revision_log),
        "replay_valid": replay is not None,
        "owner_snapshot": store.load_snapshot() or {},
        "status": "pass" if accepted else "hold",
        "verification_level": "V4" if accepted else "V3",
        "evidence_level": "E4" if accepted else "E3",
        "boundary": (
            "This report proves a controlled runtime-mainline endogenous-drive writeback path with a governed "
            "self-maintenance candidate. It does not prove live autonomy, direct reply authority, or broader "
            "transport maturity."
        ),
        "external_risk_note": (
            "Provider 429/401 remains an external budget-layer risk; it is not counted as a WP9 blocker unless it "
            "regresses formal owner writeback."
        ),
    }

    report_json = artifacts_dir / "mvp14_controlled_observation_report.json"
    report_md = artifacts_dir / "mvp14_controlled_observation_report.md"
    report_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    report_md.write_text(_render_markdown(payload), encoding="utf-8")

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        output_json.with_suffix(".md").write_text(_render_markdown(payload), encoding="utf-8")
    return payload


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run the first controlled MVP14 endogenous-drive observation.")
    parser.add_argument("--message", action="append", default=[], help="Add one scripted user message")
    parser.add_argument("--messages-file", default=None, help="JSON list or newline-delimited text file")
    parser.add_argument(
        "--session-id",
        default=f"session:mvp14:controlled:{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    )
    parser.add_argument(
        "--output-json",
        default=str(ARTIFACTS_ROOT / "mvp14_controlled_observation_current.json"),
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
