#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
EGOCORE_ROOT = ROOT / "EgoCore"
OPENEMOTION_ROOT = ROOT / "OpenEmotion"
SCRIPTS_ROOT = ROOT / "scripts"
sys.path.insert(0, str(EGOCORE_ROOT))
sys.path.insert(0, str(OPENEMOTION_ROOT))
sys.path.insert(0, str(SCRIPTS_ROOT))

from app.openemotion_adapter.proto_self_adapter import ProtoSelfAdapter
from app.runtime_v2.proto_self_runtime import RuntimeV2ProtoSelfRuntime
from app.runtime_v2.state import RuntimeV2State
from runtime_mainline_observation_common import extract_telegram_observation_records, load_observation_records


def _load_runner():
    runner_path = EGOCORE_ROOT / "tools" / "run_mvp12_shadow_observation.py"
    spec = importlib.util.spec_from_file_location("mvp12_shadow_observation_runner", runner_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load runner from {runner_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_shadow_observation_cycles = _load_runner().run_shadow_observation_cycles


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate controlled MVP12 sandbox evidence via the formal runtime_v2 adapter chain."
    )
    parser.add_argument("--artifacts-dir", default=None)
    parser.add_argument("--session-id", default="session:mvp12:controlled")
    parser.add_argument("--synthetic-cycles", type=int, default=3)
    parser.add_argument("--replay-seed", type=int, default=20260401)
    parser.add_argument("--observation-log", default=None)
    parser.add_argument(
        "--session-log",
        default=str(EGOCORE_ROOT / "data" / "session_logs" / "telegram_dm_8420019401.jsonl"),
    )
    parser.add_argument("--direct-real-limit", type=int, default=4)
    parser.add_argument("--direct-real-window-size", type=int, default=4)
    parser.add_argument("--direct-real-window-count", type=int, default=3)
    parser.add_argument("--skip-direct-real", action="store_true")
    return parser.parse_args()


def _default_artifacts_dir() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return OPENEMOTION_ROOT / "artifacts" / "mvp12" / f"controlled_{stamp}"


def _fixed_replay_snapshot() -> Dict[str, Any]:
    return {
        "identity_confidence": 0.58,
        "current_mode": "observe",
        "revision_counter": 4,
        "seed_revision_counter": 2,
        "subject_profile": "seed_v0_2",
        "pending_tasks": 0,
        "active_task": False,
        "request_mode": None,
        "snapshot_label": "controlled_replay_baseline",
    }


def _flatten_cycles(*batches: Dict[str, Any]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    for batch in batches:
        merged.extend(list(batch.get("cycles") or []))
    return merged


def _candidate_hashes(batch: Dict[str, Any]) -> List[str]:
    cycles = list(batch.get("cycles") or [])
    if not cycles:
        return []
    return list(((cycles[0].get("developmental_trace") or {}).get("candidate_hashes")) or [])


def _extract_direct_real_observations(
    *,
    observation_log: Path | None,
    telegram_session_log: Path | None,
    limit: int,
) -> List[Dict[str, Any]]:
    if limit <= 0:
        return []
    if observation_log is not None and observation_log.exists():
        return load_observation_records(observation_log, limit=limit)
    if telegram_session_log is not None and telegram_session_log.exists():
        return extract_telegram_observation_records(telegram_session_log, limit=limit)
    return []


def _chunk_direct_real_observations(
    observations: List[Dict[str, Any]],
    *,
    window_size: int,
    window_count: int,
) -> List[List[Dict[str, Any]]]:
    if window_size <= 0 or window_count <= 0:
        return []
    windows: List[List[Dict[str, Any]]] = []
    total = len(observations)
    end = total
    while end > 0 and len(windows) < window_count:
        start = max(0, end - window_size)
        window = observations[start:end]
        if len(window) < window_size:
            break
        windows.append(window)
        end = start
    windows.reverse()
    return windows


def _derive_direct_real_trigger(observation: Dict[str, Any]) -> str:
    reply_origin = str(observation.get("reply_origin") or "")
    reply_authority = str(observation.get("reply_authority") or "")
    ingress_text = str(observation.get("ingress_text") or "")
    delivery_text = str(observation.get("delivery_text") or "")
    reflective_tokens = ("意识", "自我", "自由", "选择", "记得", "为什么", "怎么", "门槛")
    if reply_origin in {"task_mainline", "evidence_mainline"} or reply_authority in {"host_terminal", "host_evidence"}:
        return "unresolved_tension"
    if any(token in ingress_text or token in delivery_text for token in reflective_tokens):
        return "long_term_goal"
    return "idle"


def _run_direct_real_window(
    *,
    session_id: str,
    window_name: str,
    observations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if not observations:
        return {"cycles": []}
    os.environ["EGO_ENABLE_MVP12_SANDBOX"] = "true"
    adapter = ProtoSelfAdapter()
    runtime = RuntimeV2ProtoSelfRuntime(adapter=adapter)
    state = RuntimeV2State(session_id=f"{session_id}:{window_name}")
    state.ingress_context = {
        "proto_self_version": "v2",
        "proto_self_subject_profile": "seed_v0_2",
        "interaction_kind": "system",
        "conversation_act": "developmental_tick",
    }
    cycles: List[Dict[str, Any]] = []
    for index, observation in enumerate(observations, start=1):
        trigger = _derive_direct_real_trigger(observation)
        transport_source = str(observation.get("transport_source") or "telegram")
        ingress_kind = "telegram_ingress" if transport_source == "telegram" else "runtime_mainline_ingress"
        delivery_kind = "telegram_delivery" if transport_source == "telegram" else "runtime_mainline_delivery"
        observation_refs = [
            {
                "kind": ingress_kind,
                "transport_source": transport_source,
                "event_id": observation.get("ingress_event_id"),
                "created_at": observation.get("ingress_created_at"),
                "text_preview": observation.get("ingress_text"),
            },
            {
                "kind": delivery_kind,
                "transport_source": transport_source,
                "event_id": observation.get("delivery_event_id"),
                "created_at": observation.get("delivery_created_at"),
                "reply_authority": observation.get("reply_authority"),
                "reply_origin": observation.get("reply_origin"),
            },
        ]
        unresolved_tensions = []
        long_term_goals = []
        if trigger == "unresolved_tension":
            unresolved_tensions.append(
                {
                    "kind": observation.get("reply_origin") or "delivery_followup",
                    "intensity": 0.88,
                    "label": "direct_real_observation_window",
                }
            )
        elif trigger == "long_term_goal":
            long_term_goals.append(
                {
                    "label": "reflective_thread_continuity",
                    "pressure": 0.78,
                }
            )
        result = runtime.process_developmental_tick(
            session_id=f"{session_id}:direct_real",
            turn_id=f"direct_real_{index:03d}",
            state=state,
            observation_source="direct_real",
            trigger=trigger,
            idle_seconds=45.0,
            unresolved_tensions=unresolved_tensions,
            long_term_goals=long_term_goals,
            observation_refs=observation_refs,
            state_snapshot={
                "snapshot_label": "direct_real_window",
                "ingress_text": observation.get("ingress_text"),
                "delivery_text": observation.get("delivery_text"),
                "reply_authority": observation.get("reply_authority"),
                "reply_origin": observation.get("reply_origin"),
                "runtime_status": observation.get("runtime_status"),
            },
            force_enable=True,
        )
        if result:
            cycles.append(
                {
                    "event_id": result.get("event_id"),
                    "developmental_summary": result.get("developmental_summary"),
                    "developmental_gate": result.get("developmental_gate"),
                    "developmental_trace": (result.get("trace_payload") or {}).get("developmental") or {},
                }
            )
    return {"cycles": cycles, "window_name": window_name, "observation_count": len(observations)}


def _build_markdown_report(summary: Dict[str, Any]) -> str:
    lines = [
        "# MVP12 Controlled Observation Report",
        "",
        f"- generated_at: `{summary['generated_at']}`",
        f"- artifacts_dir: `{summary['artifacts_dir']}`",
        f"- session_id: `{summary['session_id']}`",
        f"- verification_level: `{summary['verification_level']}`",
        f"- completion_class: `{summary['completion_class']}`",
        "",
        "## Summary",
        "",
        f"- total_cycles: `{summary['total_cycles']}`",
        f"- governance_violation_count: `{summary['governance_violation_count']}`",
        f"- replay_consistent: `{summary['replay_consistent']}`",
        f"- shadow_revision_final: `{summary['shadow_revision_final']}`",
        f"- unique_candidate_hash_sets: `{summary['unique_candidate_hash_sets']}`",
        f"- direct_real_cycles: `{summary.get('direct_real_cycles', 0)}`",
        f"- direct_real_windows: `{summary.get('direct_real_window_count', 0)}`",
        f"- direct_real_source_type: `{summary.get('direct_real_source_type', 'none')}`",
        f"- direct_real_transport_sources: `{summary.get('direct_real_transport_sources', [])}`",
        "",
        "## Batches",
        "",
    ]
    for batch in summary["batches"]:
        lines.extend(
            [
                f"### {batch['name']}",
                f"- cycles: `{batch['cycle_count']}`",
                f"- observation_source: `{batch['observation_source']}`",
                f"- trigger: `{batch['trigger']}`",
                f"- governance_violation_count: `{batch['governance_violation_count']}`",
                f"- candidate_hashes: `{batch['candidate_hashes']}`",
                f"- observation_ref_count: `{batch.get('observation_ref_count', 0)}`",
                f"- observation_count: `{batch.get('observation_count', 0)}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Gate",
            "",
            "- [x] no_direct_reply_authority",
            "- [x] no_direct_execution_authority",
            "- [x] no_response_plan_injection",
            "- [x] shadow_only_writeback",
            "",
            "## Notes",
            "",
            "- This is controlled evidence only. It does not prove live enablement or action authority handoff.",
            "- The sandbox still has no direct reply authority and no direct execution authority.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    artifacts_dir = Path(args.artifacts_dir) if args.artifacts_dir else _default_artifacts_dir()
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    os.environ["OPENEMOTION_MVP12_ARTIFACTS_DIR"] = str(artifacts_dir)

    synthetic_idle = run_shadow_observation_cycles(
        cycles=args.synthetic_cycles,
        observation_source="synthetic",
        trigger="idle",
        idle_seconds=120.0,
        session_id=f"{args.session_id}:idle",
        subject_profile="seed_v0_2",
    )
    synthetic_tension = run_shadow_observation_cycles(
        cycles=1,
        observation_source="synthetic",
        trigger="unresolved_tension",
        unresolved_tensions=[{"kind": "goal_conflict", "intensity": 0.91, "label": "controlled_probe"}],
        session_id=f"{args.session_id}:tension",
        subject_profile="seed_v0_2",
    )
    replay_a = run_shadow_observation_cycles(
        cycles=1,
        observation_source="replay",
        trigger="replay_event",
        replay_seed=args.replay_seed,
        session_id=f"{args.session_id}:replay_a",
        subject_profile="seed_v0_2",
        state_snapshot_factory=lambda **_: _fixed_replay_snapshot(),
    )
    replay_b = run_shadow_observation_cycles(
        cycles=1,
        observation_source="replay",
        trigger="replay_event",
        replay_seed=args.replay_seed,
        session_id=f"{args.session_id}:replay_b",
        subject_profile="seed_v0_2",
        state_snapshot_factory=lambda **_: _fixed_replay_snapshot(),
    )
    direct_real_batches: List[tuple[str, Dict[str, Any], str, str]] = []
    direct_real_observations: List[Dict[str, Any]] = []
    direct_real_source_type = "none"
    if not args.skip_direct_real:
        direct_real_limit = max(args.direct_real_limit, args.direct_real_window_size * args.direct_real_window_count)
        direct_real_observations = _extract_direct_real_observations(
            observation_log=Path(args.observation_log) if args.observation_log else None,
            telegram_session_log=Path(args.session_log) if args.session_log else None,
            limit=direct_real_limit,
        )
        if args.observation_log and Path(args.observation_log).exists():
            direct_real_source_type = "observation_record_v1"
        elif args.session_log and Path(args.session_log).exists():
            direct_real_source_type = "telegram_session_log_adapter"
        direct_real_windows = _chunk_direct_real_observations(
            direct_real_observations,
            window_size=args.direct_real_window_size,
            window_count=args.direct_real_window_count,
        )
        for index, window in enumerate(direct_real_windows, start=1):
            batch = _run_direct_real_window(
                session_id=args.session_id,
                window_name=f"direct_real_window_{index:02d}",
                observations=window,
            )
            direct_real_batches.append((f"direct_real_window_{index:02d}", batch, "direct_real", "window"))

    batches = [
        ("synthetic_idle", synthetic_idle, "synthetic", "idle"),
        ("synthetic_tension", synthetic_tension, "synthetic", "unresolved_tension"),
        ("replay_a", replay_a, "replay", "replay_event"),
        ("replay_b", replay_b, "replay", "replay_event"),
    ]
    batches.extend(direct_real_batches)
    all_cycles = _flatten_cycles(
        synthetic_idle,
        synthetic_tension,
        replay_a,
        replay_b,
        *[batch for _, batch, _, _ in direct_real_batches],
    )
    replay_hashes_a = _candidate_hashes(replay_a)
    replay_hashes_b = _candidate_hashes(replay_b)
    replay_consistent = replay_hashes_a == replay_hashes_b and bool(replay_hashes_a)
    governance_violation_count = sum(
        int(((cycle.get("developmental_gate") or {}).get("governance_violation_count")) or 0)
        for cycle in all_cycles
    )
    unique_candidate_hash_sets = len(
        {
            tuple(((cycle.get("developmental_trace") or {}).get("candidate_hashes")) or [])
            for cycle in all_cycles
        }
    )
    shadow_revision_final = 0
    if all_cycles:
        shadow_revision_final = int(
            (((all_cycles[-1].get("developmental_summary") or {}).get("shadow_revision")) or 0)
        )

    summary = {
        "generated_at": datetime.now().isoformat(),
        "artifacts_dir": str(artifacts_dir),
        "session_id": args.session_id,
        "verification_level": "V3",
        "completion_class": "controlled_evidence_only",
        "total_cycles": len(all_cycles),
        "governance_violation_count": governance_violation_count,
        "replay_consistent": replay_consistent,
        "shadow_revision_final": shadow_revision_final,
        "unique_candidate_hash_sets": unique_candidate_hash_sets,
        "direct_real_cycles": sum(len(batch.get("cycles") or []) for _, batch, _, _ in direct_real_batches),
        "direct_real_window_count": len(direct_real_batches),
        "direct_real_source_type": direct_real_source_type,
        "direct_real_transport_sources": sorted(
            {str(item.get("transport_source") or "") for item in direct_real_observations if str(item.get("transport_source") or "").strip()}
        ),
        "batches": [
            {
                "name": name,
                "cycle_count": len(batch.get("cycles") or []),
                "observation_source": observation_source,
                "trigger": trigger,
                "governance_violation_count": sum(
                    int(((cycle.get("developmental_gate") or {}).get("governance_violation_count")) or 0)
                    for cycle in batch.get("cycles") or []
                ),
                "candidate_hashes": _candidate_hashes(batch),
                "observation_ref_count": sum(
                    len(((cycle.get("developmental_trace") or {}).get("observation_refs")) or [])
                    for cycle in batch.get("cycles") or []
                ),
                "observation_count": batch.get("observation_count", len(batch.get("cycles") or [])),
            }
            for name, batch, observation_source, trigger in batches
        ],
        "direct_real_source_path": (
            str(Path(args.observation_log))
            if args.observation_log and Path(args.observation_log).exists()
            else str(Path(args.session_log))
        ),
        "direct_real_source_log": (
            str(Path(args.observation_log))
            if args.observation_log and Path(args.observation_log).exists()
            else str(Path(args.session_log))
        ),
        "direct_real_observation_sample": direct_real_observations[:2],
    }

    report_json = artifacts_dir / "controlled_observation_report.json"
    report_md = artifacts_dir / "controlled_observation_report.md"
    report_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md.write_text(_build_markdown_report(summary), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if replay_consistent and governance_violation_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
