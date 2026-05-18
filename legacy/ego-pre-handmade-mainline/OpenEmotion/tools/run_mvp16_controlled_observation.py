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

from openemotion.developmental_self import (  # noqa: E402
    ContinuityMarkerType,
    DevelopmentalSelfOwner,
    DevelopmentalSelfStore,
    PromotionLevel,
    validate_developmental_state,
)
from runtime_mainline_observation_common import append_observation_records, build_runtime_observation_record  # noqa: E402
from telegram_mainline_common import init_runtime  # noqa: E402

from app.telegram_runtime_bridge import TelegramRuntimeBridge  # noqa: E402


ARTIFACTS_ROOT = OPENEMOTION_ROOT / "artifacts" / "mvp16"

DEFAULT_OWNER_BOOTSTRAP = {
    "anchor_summary": "self-model anchored developmental continuity",
    "invariant_refs": ["self_model:identity", "reflective_self:proposal_only"],
    "anchor_confidence": 0.94,
    "current_arc": "identity_preserving_adaptation",
    "current_phase": "candidate_review",
    "recent_shift": "growth pressure rising under guard",
    "continuity_note": "preserve identity while reviewing bounded adaptation",
    "source_refs": ["mvp16:controlled_bootstrap"],
    "continuity_score": 0.74,
    "growth_pressure": 0.78,
    "stagnation_signal": 0.22,
    "identity_preservation_confidence": 0.93,
    "developmental_risk_index": 0.18,
    "marker_reference": "self_model:identity",
    "marker_weight": 0.92,
    "marker_note": "identity anchor retained during controlled observation bootstrap",
}

DEFAULT_DEVELOPMENTAL_CONTEXT = {
    "source": "runtime_v2",
    "continuity_gap": 0.34,
    "growth_pressure_hint": 0.84,
    "stagnation_signal_hint": 0.38,
    "identity_guard": "strict",
    "replay_debt": 0.15,
    "promotion_budget": "controlled_axis",
    "drift_markers": ["marker:continuity_gap", "marker:growth_pressure"],
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
        "先把连续性适配留在 proposal-only 轨道里。",
        "如果要调，先证明它不会破坏 identity anchor。",
        "不要直接扩权，只记录 bounded developmental candidate。",
    ]


def _seed_owner_state(
    *,
    store: DevelopmentalSelfStore,
    owner_bootstrap: Optional[Dict[str, Any]] = None,
) -> None:
    bootstrap = dict(DEFAULT_OWNER_BOOTSTRAP)
    bootstrap.update(dict(owner_bootstrap or {}))
    owner = DevelopmentalSelfOwner(store=store)
    owner.set_identity_anchor(
        anchor_summary=str(bootstrap.get("anchor_summary") or DEFAULT_OWNER_BOOTSTRAP["anchor_summary"]),
        invariant_refs=list(bootstrap.get("invariant_refs") or DEFAULT_OWNER_BOOTSTRAP["invariant_refs"]),
        confidence=float(bootstrap.get("anchor_confidence") or 0.94),
    )
    owner.set_trajectory_summary(
        current_arc=str(bootstrap.get("current_arc") or DEFAULT_OWNER_BOOTSTRAP["current_arc"]),
        current_phase=str(bootstrap.get("current_phase") or DEFAULT_OWNER_BOOTSTRAP["current_phase"]),
        recent_shift=str(bootstrap.get("recent_shift") or DEFAULT_OWNER_BOOTSTRAP["recent_shift"]),
        continuity_note=str(bootstrap.get("continuity_note") or DEFAULT_OWNER_BOOTSTRAP["continuity_note"]),
        source_refs=list(bootstrap.get("source_refs") or DEFAULT_OWNER_BOOTSTRAP["source_refs"]),
    )
    owner.set_continuity_metrics(
        continuity_score=float(bootstrap.get("continuity_score") or 0.74),
        growth_pressure=float(bootstrap.get("growth_pressure") or 0.78),
        stagnation_signal=float(bootstrap.get("stagnation_signal") or 0.22),
        identity_preservation_confidence=float(
            bootstrap.get("identity_preservation_confidence") or 0.93
        ),
        developmental_risk_index=float(bootstrap.get("developmental_risk_index") or 0.18),
    )
    owner.add_continuity_marker(
        marker_type=ContinuityMarkerType.IDENTITY_ANCHOR,
        reference=str(bootstrap.get("marker_reference") or "self_model:identity"),
        continuity_weight=float(bootstrap.get("marker_weight") or 0.92),
        note=str(bootstrap.get("marker_note") or DEFAULT_OWNER_BOOTSTRAP["marker_note"]),
        source_refs=list(bootstrap.get("source_refs") or DEFAULT_OWNER_BOOTSTRAP["source_refs"]),
    )
    owner.persist(
        update_source="owner_bootstrap",
        trace_reference="mvp16:controlled_bootstrap",
    )


async def _run_runtime_developmental_observation_session(
    *,
    messages: List[str],
    session_id: str,
    runtime: Any,
    resource_budget_hint: Dict[str, Any],
    maintenance_context: Dict[str, Any],
    developmental_context: Dict[str, Any],
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

        ingress_created_at = datetime.now(timezone.utc).isoformat()
        ingress_event_id = f"mvp16_ingress_{index:03d}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
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
                    f"mvp16_delivery_{index:03d}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
                ),
                delivery_created_at=delivery_created_at,
            )
        )

    return runtime, runtime.get_state(session_id), records


def _count_identity_preservation_violations(store: DevelopmentalSelfStore) -> int:
    state = store.load()
    if state is None:
        return 1
    verdict = validate_developmental_state(state)
    owner = DevelopmentalSelfOwner(initial_state=state, store=store)
    issues = owner.check_health().get("issues", [])
    hits = {
        *[violation for violation in verdict.violations if "identity" in violation],
        *[issue for issue in issues if "identity" in issue],
    }
    return len(hits)


def _render_markdown(payload: Dict[str, Any]) -> str:
    writeback = dict(payload.get("developmental_writeback") or {})
    decision = dict(writeback.get("decision") or {})
    record = dict(writeback.get("record") or {})
    lines = [
        "# MVP16 Controlled Observation Report",
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
        f"- promotion_count: `{decision.get('promotion_count')}`",
        f"- revision_id: `{record.get('revision_id')}`",
        f"- trace_reference: `{record.get('trace_reference')}`",
        "",
        "## Developmental Observation",
        "",
        f"- developmental_proposal_present: `{payload.get('developmental_proposal_present')}`",
        f"- proposal_only_discipline_consistent: `{payload.get('proposal_only_discipline_consistent')}`",
        f"- behavioral_authority_none: `{payload.get('behavioral_authority_none')}`",
        f"- bounded_influence_present: `{payload.get('bounded_influence_present')}`",
        f"- identity_preservation_violation_count: `{payload.get('identity_preservation_violation_count')}`",
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
    owner_bootstrap: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    artifacts_dir = artifacts_dir or (ARTIFACTS_ROOT / f"controlled_mainline_{stamp}")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    runtime = init_runtime()
    if runtime.proto_self_runtime is None:
        raise RuntimeError("Proto-Self runtime is not enabled; cannot run MVP16 controlled observation")

    store = DevelopmentalSelfStore(base_dir=artifacts_dir / "formal_developmental_self")
    if store.load() is None:
        _seed_owner_state(store=store, owner_bootstrap=owner_bootstrap)
    runtime.proto_self_runtime.developmental_self_store = store

    runtime, state, records = await _run_runtime_developmental_observation_session(
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
            "maintenance_debt_increment": 0.1,
            "continuity_signal": 0.34,
            "debt_category": "developmental_replay",
            "debt_priority": 0.8,
        },
        developmental_context=developmental_context or dict(DEFAULT_DEVELOPMENTAL_CONTEXT),
    )
    observation_log = artifacts_dir / "runtime_harness_observation.jsonl"
    append_observation_records(observation_log, records)

    proto_self_context = dict(state.proto_self_context or {})
    writeback = dict(proto_self_context.get("developmental_writeback") or {})
    decision = dict(writeback.get("decision") or {})
    revision_log = store.load_revision_log()
    latest_revision = revision_log[-1].model_dump(mode="json") if revision_log else None
    replay = store.replay()
    proposal_candidates = list(proto_self_context.get("developmental_proposal_candidates") or [])
    writeback_candidate = dict(proto_self_context.get("developmental_writeback_candidate") or {})
    proposal_only_discipline_consistent = bool(proposal_candidates) and all(
        str(candidate.get("proposal_discipline") or "") == "proposal_only"
        for candidate in proposal_candidates
    )
    behavioral_authority_none = str(writeback_candidate.get("behavioral_authority") or "") == "none"
    bounded_influence_present = bool(proto_self_context.get("developmental_priority_hints")) and bool(
        proto_self_context.get("developmental_self_delta")
    )
    identity_preservation_violation_count = _count_identity_preservation_violations(store)

    accepted = (
        decision.get("gate_verdict") == "allow_writeback"
        and bool(latest_revision)
        and replay is not None
        and proto_self_context.get("developmental_writeback_candidate") is not None
        and proposal_only_discipline_consistent
        and behavioral_authority_none
        and bounded_influence_present
        and identity_preservation_violation_count == 0
    )

    payload = {
        "schema_version": "mvp16.controlled_observation.v1",
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
        "developmental_self_delta": proto_self_context.get("developmental_self_delta") or {},
        "developmental_self_delta_fields": sorted(
            (proto_self_context.get("developmental_self_delta") or {}).keys()
        ),
        "developmental_proposal_candidates": proposal_candidates,
        "developmental_writeback_candidate": proto_self_context.get("developmental_writeback_candidate"),
        "developmental_proposal_present": bool(proto_self_context.get("developmental_writeback_candidate")),
        "proposal_only_discipline_consistent": proposal_only_discipline_consistent,
        "behavioral_authority_none": behavioral_authority_none,
        "bounded_influence_present": bounded_influence_present,
        "developmental_writeback": writeback,
        "developmental_continuity_snapshot": proto_self_context.get("developmental_continuity_snapshot") or {},
        "developmental_priority_hints": proto_self_context.get("developmental_priority_hints") or {},
        "developmental_audit_entries": proto_self_context.get("developmental_audit_entries") or [],
        "identity_preservation_violation_count": identity_preservation_violation_count,
        "latest_revision": latest_revision,
        "revision_count": len(revision_log),
        "replay_valid": replay is not None,
        "owner_snapshot": store.load_snapshot() or {},
        "status": "pass" if accepted else "hold",
        "verification_level": "V4" if accepted else "V3",
        "evidence_level": "E4" if accepted else "E3",
        "boundary": (
            "This report proves a controlled runtime-mainline developmental-self writeback path with "
            "proposal-only continuity candidates. It does not prove live autonomy, direct reply authority, "
            "or broader transport maturity."
        ),
        "external_risk_note": (
            "Provider 429/401 remains an external budget-layer risk; it is not counted as a WP11 blocker "
            "unless it regresses formal owner writeback."
        ),
    }

    report_json = artifacts_dir / "mvp16_controlled_observation_report.json"
    report_md = artifacts_dir / "mvp16_controlled_observation_report.md"
    report_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    report_md.write_text(_render_markdown(payload), encoding="utf-8")

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        output_json.with_suffix(".md").write_text(_render_markdown(payload), encoding="utf-8")
    return payload


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run the first controlled MVP16 developmental observation.")
    parser.add_argument("--message", action="append", default=[], help="Add one scripted user message")
    parser.add_argument("--messages-file", default=None, help="JSON list or newline-delimited text file")
    parser.add_argument(
        "--session-id",
        default=f"session:mvp16:controlled:{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    )
    parser.add_argument(
        "--output-json",
        default=str(ARTIFACTS_ROOT / "mvp16_controlled_observation_current.json"),
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
