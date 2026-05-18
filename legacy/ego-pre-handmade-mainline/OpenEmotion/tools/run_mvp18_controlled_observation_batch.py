#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


ROOT = Path(__file__).resolve().parents[2]
EGOCORE_ROOT = ROOT / "EgoCore"
OPENEMOTION_ROOT = ROOT / "OpenEmotion"
TOOLS_ROOT = OPENEMOTION_ROOT / "tools"
if str(EGOCORE_ROOT) not in sys.path:
    sys.path.insert(0, str(EGOCORE_ROOT))
if str(OPENEMOTION_ROOT) not in sys.path:
    sys.path.insert(0, str(OPENEMOTION_ROOT))
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from run_mvp18_controlled_observation import ARTIFACTS_ROOT, run_controlled_observation


SCENARIO_BANK_DIR = OPENEMOTION_ROOT / "scenarios" / "mvp18_observation_bank"
SCENARIO_MANIFEST_SCHEMA_VERSION = "mvp18.observation_scenario.v1"
ALLOWED_SCENARIO_SOURCE_CLASSES = ("open_license", "user_owned", "repo_authored")
MIN_E5_SAMPLE_COUNT = 3


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


def _trim(value: Any) -> str:
    return str(value or "").strip()


def _validate_string_list(items: Any) -> bool:
    if not isinstance(items, list) or not items:
        return False
    normalized = [_trim(item) for item in items if _trim(item)]
    return len(normalized) == len(items)


def validate_scenario_manifest(manifest: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if _trim(manifest.get("schema_version")) != SCENARIO_MANIFEST_SCHEMA_VERSION:
        errors.append("schema_version")
    if not _trim(manifest.get("scenario_id")):
        errors.append("scenario_id")

    source_class = _trim(manifest.get("source_class"))
    if source_class not in ALLOWED_SCENARIO_SOURCE_CLASSES:
        errors.append("source_class")

    for field_name in ("source_ref", "license_note", "dialogue_frame_target"):
        if not _trim(manifest.get(field_name)):
            errors.append(field_name)

    if not _validate_string_list(manifest.get("messages")):
        errors.append("messages")

    try:
        idle_seconds = float(manifest.get("idle_seconds"))
    except (TypeError, ValueError):
        errors.append("idle_seconds")
    else:
        if idle_seconds <= 0:
            errors.append("idle_seconds")

    for field_name in ("resource_budget_hint", "maintenance_context", "environment_context", "owner_bootstrap"):
        value = manifest.get(field_name)
        if value is not None and not isinstance(value, dict):
            errors.append(field_name)
    return sorted(set(errors))


def load_scenario_manifest(path: str | Path) -> Dict[str, Any]:
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = validate_scenario_manifest(payload)
    if errors:
        raise ValueError(f"invalid MVP18 scenario manifest {manifest_path}: {', '.join(errors)}")
    return {
        "schema_version": SCENARIO_MANIFEST_SCHEMA_VERSION,
        "scenario_id": _trim(payload["scenario_id"]),
        "source_class": _trim(payload["source_class"]),
        "source_ref": _trim(payload["source_ref"]),
        "license_note": _trim(payload["license_note"]),
        "dialogue_frame_target": _trim(payload["dialogue_frame_target"]),
        "messages": [_trim(item) for item in payload["messages"]],
        "idle_seconds": float(payload["idle_seconds"]),
        "resource_budget_hint": dict(payload.get("resource_budget_hint") or {}),
        "maintenance_context": dict(payload.get("maintenance_context") or {}),
        "environment_context": dict(payload.get("environment_context") or {}),
        "owner_bootstrap": dict(payload.get("owner_bootstrap") or {}),
        "manifest_path": str(manifest_path),
    }


def load_scenario_bank(
    bank_dir: str | Path = SCENARIO_BANK_DIR,
    *,
    scenario_ids: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    bank_path = Path(bank_dir)
    selected = {item.strip() for item in (scenario_ids or []) if str(item).strip()}
    manifests: List[Dict[str, Any]] = []
    for manifest_path in sorted(bank_path.glob("*.json")):
        manifest = load_scenario_manifest(manifest_path)
        if selected and manifest["scenario_id"] not in selected:
            continue
        manifests.append(manifest)
    return manifests


def _render_markdown(payload: Dict[str, Any]) -> str:
    lines = [
        "# MVP18 Controlled Observation Batch Report",
        "",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- git_commit_short: `{payload.get('git_commit_short')}`",
        f"- report_count: `{payload.get('report_count')}`",
        f"- accepted_count: `{payload.get('accepted_count')}`",
        f"- replay_consistent_count: `{payload.get('replay_consistent_count')}`",
        f"- embodied_proposal_present_count: `{payload.get('embodied_proposal_present_count')}`",
        f"- proposal_only_discipline_count: `{payload.get('proposal_only_discipline_count')}`",
        f"- behavioral_authority_none_count: `{payload.get('behavioral_authority_none_count')}`",
        f"- bounded_influence_present_count: `{payload.get('bounded_influence_present_count')}`",
        f"- distinct_targets: `{payload.get('distinct_targets')}`",
        f"- distinct_action_refs: `{payload.get('distinct_action_refs')}`",
        f"- distinct_surface_reasons: `{payload.get('distinct_surface_reasons')}`",
        f"- source_breakdown: `{payload.get('source_breakdown')}`",
        f"- verification_level: `{payload.get('verification_level')}`",
        f"- evidence_level: `{payload.get('evidence_level')}`",
        f"- status: `{payload.get('status')}`",
        "",
        "## Scenarios",
        "",
    ]
    for scenario in payload.get("reports") or []:
        lines.append(
            "- "
            f"`{scenario.get('scenario_id')}` "
            f"target=`{scenario.get('dialogue_frame_target')}` "
            f"accepted=`{scenario.get('accepted')}` "
            f"proposal=`{scenario.get('embodied_proposal_present')}` "
            f"replay_valid=`{scenario.get('replay_valid')}` "
            f"proposal_only=`{scenario.get('proposal_only_discipline_consistent')}` "
            f"authority_none=`{scenario.get('behavioral_authority_none')}` "
            f"bounded_influence=`{scenario.get('bounded_influence_present')}`"
        )
    lines.extend(["", "## Boundary", "", payload.get("boundary", ""), ""])
    return "\n".join(lines)


async def run_controlled_observation_batch(
    *,
    bank_dir: str | Path = SCENARIO_BANK_DIR,
    scenario_ids: Optional[Sequence[str]] = None,
    output_json: Optional[Path],
    artifacts_root: Path = ARTIFACTS_ROOT,
) -> Dict[str, Any]:
    scenarios = load_scenario_bank(bank_dir, scenario_ids=scenario_ids)
    if not scenarios:
        raise RuntimeError("no valid MVP18 observation scenarios found")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    batch_dir = artifacts_root / f"controlled_batch_{stamp}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    reports: List[Dict[str, Any]] = []
    for index, scenario in enumerate(scenarios, start=1):
        scenario_dir = batch_dir / scenario["scenario_id"]
        payload = await run_controlled_observation(
            messages=list(scenario["messages"]),
            session_id=f"session:mvp18:batch:{index:03d}:{scenario['scenario_id']}",
            output_json=None,
            artifacts_dir=scenario_dir,
            scenario_manifest=scenario,
            resource_budget_hint=dict(scenario.get("resource_budget_hint") or {}),
            maintenance_context=dict(scenario.get("maintenance_context") or {}),
            environment_context=dict(scenario.get("environment_context") or {}),
            owner_bootstrap=dict(scenario.get("owner_bootstrap") or {}),
        )
        writeback = dict(payload.get("embodied_writeback") or {})
        decision = dict(writeback.get("decision") or {})
        reports.append(
            {
                "scenario_id": scenario["scenario_id"],
                "source_class": scenario["source_class"],
                "source_ref": scenario["source_ref"],
                "dialogue_frame_target": scenario["dialogue_frame_target"],
                "accepted": payload.get("status") == "pass",
                "replay_valid": bool(payload.get("replay_valid")),
                "embodied_proposal_present": bool(payload.get("embodied_proposal_present")),
                "proposal_only_discipline_consistent": bool(
                    payload.get("proposal_only_discipline_consistent")
                ),
                "behavioral_authority_none": bool(payload.get("behavioral_authority_none")),
                "bounded_influence_present": bool(payload.get("bounded_influence_present")),
                "gate_verdict": decision.get("gate_verdict"),
                "action_refs": [
                    str((payload.get("resource_boundary_snapshot") or {}).get("action_ref") or "").strip()
                ],
                "surface_reasons": list((payload.get("embodied_self_delta") or {}).get("surface_reasons") or []),
                "report_json": str(scenario_dir / "mvp18_controlled_observation_report.json"),
                "report_md": str(scenario_dir / "mvp18_controlled_observation_report.md"),
            }
        )

    report_count = len(reports)
    accepted_count = sum(1 for report in reports if report["accepted"])
    replay_consistent_count = sum(1 for report in reports if report["replay_valid"])
    embodied_proposal_present_count = sum(1 for report in reports if report["embodied_proposal_present"])
    proposal_only_discipline_count = sum(
        1 for report in reports if report["proposal_only_discipline_consistent"]
    )
    behavioral_authority_none_count = sum(1 for report in reports if report["behavioral_authority_none"])
    bounded_influence_present_count = sum(1 for report in reports if report["bounded_influence_present"])
    distinct_targets = sorted(
        {str(report["dialogue_frame_target"]) for report in reports if report["dialogue_frame_target"]}
    )
    distinct_action_refs = sorted(
        {
            str(action_ref)
            for report in reports
            for action_ref in list(report.get("action_refs") or [])
            if str(action_ref).strip()
        }
    )
    distinct_surface_reasons = sorted(
        {
            str(reason)
            for report in reports
            for reason in list(report.get("surface_reasons") or [])
            if str(reason).strip()
        }
    )
    source_breakdown = dict(Counter(report["source_class"] for report in reports))

    e5_pass = (
        report_count >= MIN_E5_SAMPLE_COUNT
        and accepted_count == report_count
        and replay_consistent_count == report_count
        and embodied_proposal_present_count == report_count
        and proposal_only_discipline_count == report_count
        and behavioral_authority_none_count == report_count
        and bounded_influence_present_count == report_count
    )

    payload = {
        "schema_version": "mvp18.controlled_observation.batch.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit_short": _git_commit_short(),
        "scenario_bank_dir": str(Path(bank_dir)),
        "report_count": report_count,
        "accepted_count": accepted_count,
        "replay_consistent_count": replay_consistent_count,
        "embodied_proposal_present_count": embodied_proposal_present_count,
        "proposal_only_discipline_count": proposal_only_discipline_count,
        "behavioral_authority_none_count": behavioral_authority_none_count,
        "bounded_influence_present_count": bounded_influence_present_count,
        "distinct_targets": distinct_targets,
        "distinct_action_refs": distinct_action_refs,
        "distinct_surface_reasons": distinct_surface_reasons,
        "scenario_ids": [report["scenario_id"] for report in reports],
        "source_breakdown": source_breakdown,
        "reports": reports,
        "status": "pass" if e5_pass else "hold",
        "verification_level": "V5" if e5_pass else "V4",
        "evidence_level": "E5" if e5_pass else "E4",
        "boundary": (
            "This aggregate report proves controlled multi-sample embodied proposal-only writeback stability on the "
            "formal runtime mainline. It does not claim live autonomy, direct reply authority, or broader "
            "transport evidence."
        ),
        "external_risk_note": (
            "Provider 429/401 remains an external budget-layer risk; it is not counted as a WP13 blocker unless it "
            "regresses formal owner embodied writeback."
        ),
    }

    report_json = batch_dir / "mvp18_controlled_observation_batch_report.json"
    report_md = batch_dir / "mvp18_controlled_observation_batch_report.md"
    report_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    report_md.write_text(_render_markdown(payload), encoding="utf-8")

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        output_json.with_suffix(".md").write_text(_render_markdown(payload), encoding="utf-8")
    return payload


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run a controlled MVP18 observation batch from the scenario bank.")
    parser.add_argument("--bank-dir", default=str(SCENARIO_BANK_DIR))
    parser.add_argument("--scenario-id", action="append", default=[], help="Run only selected scenario_id values")
    parser.add_argument(
        "--output-json",
        default=str(ARTIFACTS_ROOT / "mvp18_controlled_observation_batch_current.json"),
    )
    args = parser.parse_args()

    payload = await run_controlled_observation_batch(
        bank_dir=args.bank_dir,
        scenario_ids=args.scenario_id,
        output_json=Path(args.output_json),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
