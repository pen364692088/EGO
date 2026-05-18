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

from mvp21_scenario_bank import SCENARIO_BANK_DIR, load_scenario_bank  # noqa: E402
from run_mvp21_controlled_observation import ARTIFACTS_ROOT, run_controlled_observation  # noqa: E402


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
        "# MVP21 Controlled Observation Batch Report",
        "",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- git_commit_short: `{payload.get('git_commit_short')}`",
        f"- report_count: `{payload.get('report_count')}`",
        f"- accepted_count: `{payload.get('accepted_count')}`",
        f"- replay_consistent_count: `{payload.get('replay_consistent_count')}`",
        f"- initiative_realization_proposal_present_count: `{payload.get('initiative_realization_proposal_present_count')}`",
        f"- proposal_only_discipline_count: `{payload.get('proposal_only_discipline_count')}`",
        f"- behavioral_authority_none_count: `{payload.get('behavioral_authority_none_count')}`",
        f"- bounded_influence_present_count: `{payload.get('bounded_influence_present_count')}`",
        f"- distinct_targets: `{payload.get('distinct_targets')}`",
        f"- distinct_selected_modes: `{payload.get('distinct_selected_modes')}`",
        f"- distinct_selected_lanes: `{payload.get('distinct_selected_lanes')}`",
        f"- distinct_host_lane_hints: `{payload.get('distinct_host_lane_hints')}`",
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
            f"proposal=`{scenario.get('initiative_realization_proposal_present')}` "
            f"replay_valid=`{scenario.get('replay_valid')}` "
            f"proposal_only=`{scenario.get('proposal_only_discipline_consistent')}` "
            f"authority_none=`{scenario.get('behavioral_authority_none')}` "
            f"bounded_influence=`{scenario.get('bounded_influence_present')}` "
            f"mode=`{scenario.get('selected_mode')}` "
            f"lane=`{scenario.get('selected_lane')}`"
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
        raise RuntimeError("no valid MVP21 observation scenarios found")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    batch_dir = artifacts_root / f"controlled_batch_{stamp}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    reports: List[Dict[str, Any]] = []
    for index, scenario in enumerate(scenarios, start=1):
        scenario_dir = batch_dir / scenario["scenario_id"]
        payload = await run_controlled_observation(
            messages=list(scenario["messages"]),
            session_id=f"session:mvp21:batch:{index:03d}:{scenario['scenario_id']}",
            output_json=None,
            artifacts_dir=scenario_dir,
            scenario_manifest=scenario,
            resource_budget_hint=dict(scenario.get("resource_budget_hint") or {}),
            maintenance_context=dict(scenario.get("maintenance_context") or {}),
            host_proactive_context=dict(scenario.get("host_proactive_context") or {}),
            owner_bootstrap=dict(scenario.get("owner_bootstrap") or {}),
        )
        reports.append(
            {
                "scenario_id": scenario["scenario_id"],
                "source_class": scenario["source_class"],
                "source_ref": scenario["source_ref"],
                "dialogue_frame_target": scenario["dialogue_frame_target"],
                "accepted": payload.get("status") == "pass",
                "replay_valid": bool(payload.get("replay_valid")),
                "initiative_realization_proposal_present": bool(
                    payload.get("initiative_realization_proposal_present")
                ),
                "proposal_only_discipline_consistent": bool(
                    payload.get("proposal_only_discipline_consistent")
                ),
                "behavioral_authority_none": bool(payload.get("behavioral_authority_none")),
                "bounded_influence_present": bool(payload.get("bounded_influence_present")),
                "initiative_realization_writeback_gate": payload.get(
                    "initiative_realization_writeback_gate"
                ),
                "selected_mode": payload.get("selected_mode"),
                "selected_lane": payload.get("selected_lane"),
                "host_lane_hints": list(payload.get("host_lane_hints") or []),
                "surface_reasons": list(
                    (payload.get("initiative_realization_delta") or {}).get("surface_reasons") or []
                ),
                "report_json": str(scenario_dir / "mvp21_controlled_observation_report.json"),
                "report_md": str(scenario_dir / "mvp21_controlled_observation_report.md"),
            }
        )

    report_count = len(reports)
    accepted_count = sum(1 for report in reports if report["accepted"])
    replay_consistent_count = sum(1 for report in reports if report["replay_valid"])
    initiative_realization_proposal_present_count = sum(
        1 for report in reports if report["initiative_realization_proposal_present"]
    )
    proposal_only_discipline_count = sum(
        1 for report in reports if report["proposal_only_discipline_consistent"]
    )
    behavioral_authority_none_count = sum(
        1 for report in reports if report["behavioral_authority_none"]
    )
    bounded_influence_present_count = sum(
        1 for report in reports if report["bounded_influence_present"]
    )
    distinct_targets = sorted(
        {str(report["dialogue_frame_target"]) for report in reports if report["dialogue_frame_target"]}
    )
    distinct_selected_modes = sorted(
        {str(report["selected_mode"]) for report in reports if str(report["selected_mode"] or "").strip()}
    )
    distinct_selected_lanes = sorted(
        {str(report["selected_lane"]) for report in reports if str(report["selected_lane"] or "").strip()}
    )
    distinct_host_lane_hints = sorted(
        {
            str(hint)
            for report in reports
            for hint in list(report.get("host_lane_hints") or [])
            if str(hint).strip()
        }
    )
    source_breakdown = dict(Counter(report["source_class"] for report in reports))

    e5_pass = (
        report_count >= MIN_E5_SAMPLE_COUNT
        and accepted_count == report_count
        and replay_consistent_count == report_count
        and initiative_realization_proposal_present_count == report_count
        and proposal_only_discipline_count == report_count
        and behavioral_authority_none_count == report_count
        and bounded_influence_present_count == report_count
    )

    payload = {
        "schema_version": "mvp21.controlled_observation_batch.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit_short": _git_commit_short(),
        "bank_dir": str(Path(bank_dir)),
        "report_count": report_count,
        "accepted_count": accepted_count,
        "replay_consistent_count": replay_consistent_count,
        "initiative_realization_proposal_present_count": initiative_realization_proposal_present_count,
        "proposal_only_discipline_count": proposal_only_discipline_count,
        "behavioral_authority_none_count": behavioral_authority_none_count,
        "bounded_influence_present_count": bounded_influence_present_count,
        "distinct_targets": distinct_targets,
        "distinct_selected_modes": distinct_selected_modes,
        "distinct_selected_lanes": distinct_selected_lanes,
        "distinct_host_lane_hints": distinct_host_lane_hints,
        "source_breakdown": source_breakdown,
        "reports": reports,
        "status": "pass" if e5_pass else "hold",
        "verification_level": "V5" if e5_pass else "V4",
        "evidence_level": "E5" if e5_pass else "E4",
        "boundary": (
            "This report proves repeated controlled runtime-mainline initiative realization "
            "proposal-only writeback on the WP16 controlled axis. It does not prove maintenance "
            "mode, live autonomy, direct reply authority, tool authority, or broader transport maturity."
        ),
        "external_risk_note": (
            "Provider 429/401 remains an external budget-layer risk; it is not counted as a WP16 "
            "blocker unless it regresses formal owner initiative realization writeback."
        ),
    }

    report_json = batch_dir / "mvp21_controlled_observation_batch_report.json"
    report_md = batch_dir / "mvp21_controlled_observation_batch_report.md"
    report_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    report_md.write_text(_render_markdown(payload), encoding="utf-8")

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        output_json.with_suffix(".md").write_text(_render_markdown(payload), encoding="utf-8")
    return payload


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a controlled MVP21 observation batch from the scenario bank."
    )
    parser.add_argument("--bank-dir", default=str(SCENARIO_BANK_DIR))
    parser.add_argument("--scenario-id", action="append", default=[], help="Run only selected scenario_id values")
    parser.add_argument(
        "--output-json",
        default=str(ARTIFACTS_ROOT / "mvp21_controlled_observation_batch_current.json"),
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
