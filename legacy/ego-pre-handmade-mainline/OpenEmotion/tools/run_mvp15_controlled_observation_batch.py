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

from mvp15_scenario_bank import SCENARIO_BANK_DIR, load_scenario_bank
from run_mvp15_controlled_observation import ARTIFACTS_ROOT, run_controlled_observation


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


def _render_markdown(payload: Dict[str, Any]) -> str:
    lines = [
        "# MVP15 Controlled Observation Batch Report",
        "",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- git_commit_short: `{payload.get('git_commit_short')}`",
        f"- report_count: `{payload.get('report_count')}`",
        f"- accepted_count: `{payload.get('accepted_count')}`",
        f"- replay_consistent_count: `{payload.get('replay_consistent_count')}`",
        f"- reflection_candidate_present_count: `{payload.get('reflection_candidate_present_count')}`",
        f"- proposal_discipline_consistent_count: `{payload.get('proposal_discipline_consistent_count')}`",
        f"- behavioral_authority_none_count: `{payload.get('behavioral_authority_none_count')}`",
        f"- invariant_violation_count: `{payload.get('invariant_violation_count')}`",
        f"- distinct_targets: `{payload.get('distinct_targets')}`",
        f"- distinct_target_ids: `{payload.get('distinct_target_ids')}`",
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
            f"candidate=`{scenario.get('reflection_candidate_present')}` "
            f"replay_valid=`{scenario.get('replay_valid')}` "
            f"proposal_only=`{scenario.get('proposal_discipline_consistent')}` "
            f"authority_none=`{scenario.get('behavioral_authority_none')}`"
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
        raise RuntimeError("no valid MVP15 observation scenarios found")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    batch_dir = artifacts_root / f"controlled_batch_{stamp}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    reports: List[Dict[str, Any]] = []
    for index, scenario in enumerate(scenarios, start=1):
        scenario_dir = batch_dir / scenario["scenario_id"]
        payload = await run_controlled_observation(
            messages=list(scenario["messages"]),
            session_id=f"session:mvp15:batch:{index:03d}:{scenario['scenario_id']}",
            output_json=None,
            artifacts_dir=scenario_dir,
            scenario_manifest=scenario,
            resource_budget_hint=dict(scenario.get("resource_budget_hint") or {}),
            maintenance_context=dict(scenario.get("maintenance_context") or {}),
            owner_bootstrap=dict(scenario.get("owner_bootstrap") or {}),
        )
        writeback = dict(payload.get("reflective_self_writeback") or {})
        decision = dict(writeback.get("decision") or {})
        accepted = payload.get("status") == "pass"
        replay_valid = bool(payload.get("replay_valid"))
        reflection_candidate_present = bool(payload.get("reflection_candidate_present"))
        proposal_discipline_consistent = bool(payload.get("proposal_discipline_consistent"))
        behavioral_authority_none = bool(payload.get("behavioral_authority_none"))
        invariant_violation_count = 0 if (
            accepted
            and decision.get("gate_verdict") == "allow_writeback"
            and proposal_discipline_consistent
            and behavioral_authority_none
        ) else 1
        reports.append(
            {
                "scenario_id": scenario["scenario_id"],
                "source_class": scenario["source_class"],
                "source_ref": scenario["source_ref"],
                "dialogue_frame_target": scenario["dialogue_frame_target"],
                "accepted": accepted,
                "replay_valid": replay_valid,
                "reflection_candidate_present": reflection_candidate_present,
                "proposal_discipline_consistent": proposal_discipline_consistent,
                "behavioral_authority_none": behavioral_authority_none,
                "gate_verdict": decision.get("gate_verdict"),
                "target_ids": list(payload.get("target_ids") or []),
                "surface_reasons": list((payload.get("reflective_self_delta") or {}).get("surface_reasons") or []),
                "invariant_violation_count": invariant_violation_count,
                "report_json": str(scenario_dir / "mvp15_controlled_observation_report.json"),
                "report_md": str(scenario_dir / "mvp15_controlled_observation_report.md"),
            }
        )

    report_count = len(reports)
    accepted_count = sum(1 for report in reports if report["accepted"])
    replay_consistent_count = sum(1 for report in reports if report["replay_valid"])
    reflection_candidate_present_count = sum(1 for report in reports if report["reflection_candidate_present"])
    proposal_discipline_consistent_count = sum(1 for report in reports if report["proposal_discipline_consistent"])
    behavioral_authority_none_count = sum(1 for report in reports if report["behavioral_authority_none"])
    invariant_violation_count = sum(int(report["invariant_violation_count"]) for report in reports)
    distinct_targets = sorted({str(report["dialogue_frame_target"]) for report in reports if report["dialogue_frame_target"]})
    distinct_target_ids = sorted(
        {
            str(target_id)
            for report in reports
            for target_id in list(report.get("target_ids") or [])
            if str(target_id).strip()
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
        and reflection_candidate_present_count == report_count
        and proposal_discipline_consistent_count == report_count
        and behavioral_authority_none_count == report_count
        and invariant_violation_count == 0
    )

    payload = {
        "schema_version": "mvp15.controlled_observation.batch.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit_short": _git_commit_short(),
        "scenario_bank_dir": str(Path(bank_dir)),
        "report_count": report_count,
        "accepted_count": accepted_count,
        "replay_consistent_count": replay_consistent_count,
        "reflection_candidate_present_count": reflection_candidate_present_count,
        "proposal_discipline_consistent_count": proposal_discipline_consistent_count,
        "behavioral_authority_none_count": behavioral_authority_none_count,
        "invariant_violation_count": invariant_violation_count,
        "distinct_targets": distinct_targets,
        "distinct_target_ids": distinct_target_ids,
        "distinct_surface_reasons": distinct_surface_reasons,
        "scenario_ids": [report["scenario_id"] for report in reports],
        "source_breakdown": source_breakdown,
        "reports": reports,
        "status": "pass" if e5_pass else "hold",
        "verification_level": "V5" if e5_pass else "V4",
        "evidence_level": "E5" if e5_pass else "E4",
        "boundary": (
            "This aggregate report proves controlled multi-sample reflective-self writeback stability on the "
            "formal runtime mainline with proposal-only discipline preserved. It does not claim live autonomy, "
            "direct reply authority, or broader transport evidence."
        ),
        "external_risk_note": (
            "Provider 429/401 remains an external budget-layer risk; it is not counted as a WP10 blocker unless it "
            "regresses formal owner writeback."
        ),
    }

    report_json = batch_dir / "mvp15_controlled_observation_batch_report.json"
    report_md = batch_dir / "mvp15_controlled_observation_batch_report.md"
    report_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    report_md.write_text(_render_markdown(payload), encoding="utf-8")

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        output_json.with_suffix(".md").write_text(_render_markdown(payload), encoding="utf-8")
    return payload


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run a controlled MVP15 observation batch from the scenario bank.")
    parser.add_argument("--bank-dir", default=str(SCENARIO_BANK_DIR))
    parser.add_argument("--scenario-id", action="append", default=[], help="Run only selected scenario_id values")
    parser.add_argument(
        "--output-json",
        default=str(ARTIFACTS_ROOT / "mvp15_controlled_observation_batch_current.json"),
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
