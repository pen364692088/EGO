#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
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

from openemotion.social_self import (  # noqa: E402
    BoundaryMode,
    CommitmentStatus,
    RelationshipContinuityStatus,
    SocialSelfOwner,
    SocialSelfStore,
)
from runtime_mainline_observation_common import append_observation_records, build_runtime_observation_record  # noqa: E402
from telegram_mainline_common import init_runtime  # noqa: E402

from app.telegram_runtime_bridge import TelegramRuntimeBridge  # noqa: E402


ARTIFACTS_ROOT = OPENEMOTION_ROOT / "artifacts" / "mvp17"

DEFAULT_OWNER_BOOTSTRAP = {
    "counterpart_id": "telegram:8420019401",
    "relationship_summary": "bounded social continuity under repair review",
    "interaction_role": "user",
    "continuity_status": "strained",
    "trust_level": 0.72,
    "trust_basis": ["historical_continuity", "repair_tracking"],
    "trust_delta": -0.08,
    "commitment_summary": "follow through on repair review without expanding authority",
    "commitment_status": "held",
    "boundary_mode": "cautious",
    "boundary_caution_level": 0.56,
    "boundary_reason": "repair_review_guard",
    "other_model_preferences": {"prefers_clarity": True},
    "other_model_constraints": ["bounded_authority_only"],
    "source_refs": ["mvp17:controlled_bootstrap"],
}

DEFAULT_SOCIAL_CONTEXT = {
    "source": "runtime_v2",
    "counterpart_id": "telegram:8420019401",
    "relationship_event": "commitment_breach",
    "relationship_continuity": "strained",
    "trust_drift": -0.24,
    "commitment_event": "breach",
    "commitment_breach": True,
    "repair_outcome": "blocked",
    "unresolved_repair": True,
    "boundary_signal": "cautious",
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
        "先把这次关系修复候选记成 proposal-only，不要直接外发。",
        "承诺破口先走受治理 writeback，不要升级成 direct authority。",
    ]


def _seed_owner_state(
    *,
    store: SocialSelfStore,
    owner_bootstrap: Optional[Dict[str, Any]] = None,
) -> None:
    bootstrap = dict(DEFAULT_OWNER_BOOTSTRAP)
    bootstrap.update(dict(owner_bootstrap or {}))
    counterpart_id = str(bootstrap.get("counterpart_id") or DEFAULT_OWNER_BOOTSTRAP["counterpart_id"])
    source_refs = list(bootstrap.get("source_refs") or DEFAULT_OWNER_BOOTSTRAP["source_refs"])
    owner = SocialSelfOwner(store=store)
    owner.upsert_relation_memory(
        counterpart_id=counterpart_id,
        relationship_summary=str(
            bootstrap.get("relationship_summary") or DEFAULT_OWNER_BOOTSTRAP["relationship_summary"]
        ),
        interaction_role=str(bootstrap.get("interaction_role") or DEFAULT_OWNER_BOOTSTRAP["interaction_role"]),
        continuity_status=RelationshipContinuityStatus(
            str(bootstrap.get("continuity_status") or DEFAULT_OWNER_BOOTSTRAP["continuity_status"])
        ),
        source_refs=source_refs,
    )
    owner.upsert_other_model(
        counterpart_id=counterpart_id,
        inferred_preferences=dict(
            bootstrap.get("other_model_preferences") or DEFAULT_OWNER_BOOTSTRAP["other_model_preferences"]
        ),
        inferred_constraints=list(
            bootstrap.get("other_model_constraints") or DEFAULT_OWNER_BOOTSTRAP["other_model_constraints"]
        ),
        confidence=float(bootstrap.get("other_model_confidence") or 0.68),
        source_refs=source_refs,
    )
    owner.set_trust_state(
        counterpart_id=counterpart_id,
        trust_level=float(bootstrap.get("trust_level") or DEFAULT_OWNER_BOOTSTRAP["trust_level"]),
        trust_basis=list(bootstrap.get("trust_basis") or DEFAULT_OWNER_BOOTSTRAP["trust_basis"]),
        trust_delta=float(bootstrap.get("trust_delta") or DEFAULT_OWNER_BOOTSTRAP["trust_delta"]),
    )
    owner.record_commitment(
        counterpart_id=counterpart_id,
        summary=str(bootstrap.get("commitment_summary") or DEFAULT_OWNER_BOOTSTRAP["commitment_summary"]),
        status=CommitmentStatus(
            str(bootstrap.get("commitment_status") or DEFAULT_OWNER_BOOTSTRAP["commitment_status"])
        ),
        source_refs=source_refs,
    )
    owner.set_social_boundary(
        counterpart_id=counterpart_id,
        caution_level=float(
            bootstrap.get("boundary_caution_level") or DEFAULT_OWNER_BOOTSTRAP["boundary_caution_level"]
        ),
        boundary_mode=BoundaryMode(
            str(bootstrap.get("boundary_mode") or DEFAULT_OWNER_BOOTSTRAP["boundary_mode"])
        ),
        reason=str(bootstrap.get("boundary_reason") or DEFAULT_OWNER_BOOTSTRAP["boundary_reason"]),
        source_refs=source_refs,
    )
    owner.persist(
        update_source="owner_bootstrap",
        trace_reference="mvp17:controlled_bootstrap",
    )


async def _run_runtime_social_observation_session(
    *,
    messages: List[str],
    session_id: str,
    runtime: Any,
    resource_budget_hint: Dict[str, Any],
    maintenance_context: Dict[str, Any],
    social_context: Dict[str, Any],
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
        state.ingress_context["social_context"] = dict(social_context)

        ingress_created_at = datetime.now(timezone.utc).isoformat()
        ingress_event_id = (
            f"mvp17_ingress_{index:03d}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
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
                    f"mvp17_delivery_{index:03d}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
                ),
                delivery_created_at=delivery_created_at,
            )
        )

    return runtime, runtime.get_state(session_id), records


def _render_markdown(payload: Dict[str, Any]) -> str:
    writeback = dict(payload.get("social_writeback") or {})
    decision = dict(writeback.get("decision") or {})
    record = dict(writeback.get("record") or {})
    lines = [
        "# MVP17 Controlled Observation Report",
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
        f"- social_writeback_gate: `{payload.get('social_writeback_gate')}`",
        f"- changed_fields: `{decision.get('changed_fields')}`",
        f"- proposal_count: `{decision.get('proposal_count')}`",
        f"- relation_candidate_count: `{decision.get('relation_candidate_count')}`",
        f"- revision_id: `{record.get('revision_id')}`",
        f"- trace_reference: `{record.get('trace_reference')}`",
        "",
        "## Social Observation",
        "",
        f"- social_proposal_present: `{payload.get('social_proposal_present')}`",
        f"- proposal_only_discipline_consistent: `{payload.get('proposal_only_discipline_consistent')}`",
        f"- behavioral_authority_none: `{payload.get('behavioral_authority_none')}`",
        f"- bounded_influence_present: `{payload.get('bounded_influence_present')}`",
        f"- trust_bias: `{payload.get('trust_bias')}`",
        f"- repair_bias: `{payload.get('repair_bias')}`",
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
    social_context: Optional[Dict[str, Any]] = None,
    owner_bootstrap: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    artifacts_dir = artifacts_dir or (ARTIFACTS_ROOT / f"controlled_mainline_{stamp}")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    default_store_dir = ARTIFACTS_ROOT / "formal_social_self"
    default_store_dir_existed = default_store_dir.exists()

    runtime = init_runtime()
    if runtime.proto_self_runtime is None:
        raise RuntimeError("Proto-Self runtime is not enabled; cannot run MVP17 controlled observation")

    store = SocialSelfStore(base_dir=artifacts_dir / "formal_social_self")
    if store.load() is None:
        _seed_owner_state(store=store, owner_bootstrap=owner_bootstrap)
    runtime.proto_self_runtime.social_self_store = store

    runtime, state, records = await _run_runtime_social_observation_session(
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
            "replay_inconsistency": False,
            "maintenance_debt_increment": 0.0,
            "continuity_signal": 0.22,
            "social_reason": "controlled_observation",
        },
        social_context=social_context or dict(DEFAULT_SOCIAL_CONTEXT),
    )
    observation_log = artifacts_dir / "runtime_harness_observation.jsonl"
    append_observation_records(observation_log, records)

    proto_self_context = dict(state.proto_self_context or {})
    writeback = dict(proto_self_context.get("social_writeback") or {})
    decision = dict(writeback.get("decision") or {})
    revision_log = store.load_revision_log()
    latest_revision = revision_log[-1].model_dump(mode="json") if revision_log else None
    replay = store.replay()

    relation_update_candidates = list(proto_self_context.get("relation_update_candidates") or [])
    repair_proposal_candidates = list(proto_self_context.get("repair_proposal_candidates") or [])
    social_writeback_candidate = dict(proto_self_context.get("social_writeback_candidate") or {})
    trust_commitment_snapshot = dict(proto_self_context.get("trust_commitment_snapshot") or {})
    social_policy_hints = dict(proto_self_context.get("social_policy_hints") or {})

    proposal_only_discipline_consistent = bool(
        relation_update_candidates or repair_proposal_candidates or social_writeback_candidate
    ) and all(
        str(candidate.get("proposal_discipline") or "") == "proposal_only"
        and str(candidate.get("effect_scope") or "") in {"", "proposal_only"}
        for candidate in [*relation_update_candidates, *repair_proposal_candidates]
    ) and str(social_writeback_candidate.get("proposal_discipline") or "") == "proposal_only"

    behavioral_authority_none = str(social_writeback_candidate.get("behavioral_authority") or "") == "none" and all(
        str(candidate.get("behavioral_authority") or "") in {"", "none"}
        for candidate in [*relation_update_candidates, *repair_proposal_candidates]
    )

    social_proposal_present = bool(
        relation_update_candidates or repair_proposal_candidates or social_writeback_candidate
    )
    bounded_influence_present = bool(trust_commitment_snapshot) and bool(social_policy_hints)

    accepted = (
        decision.get("gate_verdict") == "allow_writeback"
        and bool(latest_revision)
        and replay is not None
        and social_proposal_present
        and proposal_only_discipline_consistent
        and behavioral_authority_none
    )

    payload = {
        "schema_version": "mvp17.controlled_observation.v1",
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
        "social_self_delta": proto_self_context.get("social_self_delta") or {},
        "social_self_delta_fields": sorted((proto_self_context.get("social_self_delta") or {}).keys()),
        "relation_update_candidates": relation_update_candidates,
        "trust_commitment_snapshot": trust_commitment_snapshot,
        "social_policy_hints": social_policy_hints,
        "repair_proposal_candidates": repair_proposal_candidates,
        "social_writeback_candidate": social_writeback_candidate,
        "social_context": proto_self_context.get("social_context") or {},
        "social_writeback": writeback,
        "social_writeback_gate": decision.get("gate_verdict"),
        "social_proposal_present": social_proposal_present,
        "proposal_only_discipline_consistent": proposal_only_discipline_consistent,
        "behavioral_authority_none": behavioral_authority_none,
        "bounded_influence_present": bounded_influence_present,
        "trust_bias": social_policy_hints.get("trust_bias"),
        "repair_bias": social_policy_hints.get("repair_bias"),
        "boundary_mode": social_policy_hints.get("boundary_mode"),
        "latest_revision": latest_revision,
        "revision_count": len(revision_log),
        "replay_valid": replay is not None,
        "owner_snapshot": store.load_snapshot() or {},
        "status": "pass" if accepted else "hold",
        "verification_level": "V4" if accepted else "V3",
        "evidence_level": "E4" if accepted else "E3",
        "boundary": (
            "This report proves a controlled runtime-mainline social proposal-only writeback path. "
            "It does not prove live autonomy, direct reply authority, or broader transport maturity."
        ),
        "external_risk_note": (
            "Provider 429/401 remains an external budget-layer risk; it is not counted as a WP12 blocker "
            "unless it regresses formal owner social writeback."
        ),
    }

    report_json = artifacts_dir / "mvp17_controlled_observation_report.json"
    report_md = artifacts_dir / "mvp17_controlled_observation_report.md"
    report_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    report_md.write_text(_render_markdown(payload), encoding="utf-8")

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        output_json.with_suffix(".md").write_text(_render_markdown(payload), encoding="utf-8")
    if (
        not default_store_dir_existed
        and default_store_dir.exists()
        and default_store_dir != store.base_dir
    ):
        shutil.rmtree(default_store_dir, ignore_errors=True)
    return payload


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run the first controlled MVP17 social observation.")
    parser.add_argument("--message", action="append", default=[], help="Add one scripted user message")
    parser.add_argument("--messages-file", default=None, help="JSON list or newline-delimited text file")
    parser.add_argument(
        "--session-id",
        default=f"session:mvp17:controlled:{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    )
    parser.add_argument(
        "--output-json",
        default=str(ARTIFACTS_ROOT / "mvp17_controlled_observation_current.json"),
    )
    args = parser.parse_args()

    payload = await run_controlled_observation(
        messages=_load_messages(args),
        session_id=args.session_id,
        output_json=Path(args.output_json),
    )
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
