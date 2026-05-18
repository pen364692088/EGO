#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
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

from aggregate_mvp17_observations import aggregate_reports, render_markdown
from mvp17_scenario_bank import SCENARIO_BANK_DIR, load_scenario_bank
from run_mvp17_controlled_observation import ARTIFACTS_ROOT, run_controlled_observation


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


async def run_controlled_observation_batch(
    *,
    bank_dir: str | Path = SCENARIO_BANK_DIR,
    scenario_ids: Optional[Sequence[str]] = None,
    output_json: Optional[Path],
    artifacts_root: Path = ARTIFACTS_ROOT,
) -> Dict[str, Any]:
    scenarios = load_scenario_bank(bank_dir, scenario_ids=scenario_ids)
    if not scenarios:
        raise RuntimeError("no valid MVP17 observation scenarios found")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    batch_dir = artifacts_root / f"controlled_batch_{stamp}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    reports: List[Dict[str, Any]] = []
    for index, scenario in enumerate(scenarios, start=1):
        scenario_dir = batch_dir / scenario["scenario_id"]
        payload = await run_controlled_observation(
            messages=list(scenario["messages"]),
            session_id=f"session:mvp17:batch:{index:03d}:{scenario['scenario_id']}",
            output_json=None,
            artifacts_dir=scenario_dir,
            scenario_manifest=scenario,
            resource_budget_hint=dict(scenario.get("resource_budget_hint") or {}),
            maintenance_context=dict(scenario.get("maintenance_context") or {}),
            social_context=dict(scenario.get("social_context") or {}),
            owner_bootstrap=dict(scenario.get("owner_bootstrap") or {}),
        )
        writeback = dict(payload.get("social_writeback") or {})
        decision = dict(writeback.get("decision") or {})
        reports.append(
            {
                "scenario_id": scenario["scenario_id"],
                "dialogue_frame_target": scenario["dialogue_frame_target"],
                "source_class": scenario["source_class"],
                "source_ref": scenario["source_ref"],
                "accepted": payload.get("status") == "pass",
                "replay_valid": bool(payload.get("replay_valid")),
                "social_proposal_present": bool(payload.get("social_proposal_present")),
                "proposal_only_discipline_consistent": bool(
                    payload.get("proposal_only_discipline_consistent")
                ),
                "behavioral_authority_none": bool(payload.get("behavioral_authority_none")),
                "bounded_influence_present": bool(payload.get("bounded_influence_present")),
                "gate_verdict": decision.get("gate_verdict"),
                "counterpart_ids": [
                    str((payload.get("trust_commitment_snapshot") or {}).get("counterpart_id") or "").strip()
                ],
                "surface_reasons": list((payload.get("social_self_delta") or {}).get("surface_reasons") or []),
                "report_json": str(scenario_dir / "mvp17_controlled_observation_report.json"),
                "report_md": str(scenario_dir / "mvp17_controlled_observation_report.md"),
            }
        )

    payload = aggregate_reports(
        reports=reports,
        git_commit_short=_git_commit_short(),
        bank_dir=str(Path(bank_dir)),
    )

    report_json = batch_dir / "mvp17_controlled_observation_batch_report.json"
    report_md = batch_dir / "mvp17_controlled_observation_batch_report.md"
    report_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    report_md.write_text(render_markdown(payload), encoding="utf-8")

    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        output_json.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    return payload


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run a controlled MVP17 observation batch from the scenario bank.")
    parser.add_argument("--bank-dir", default=str(SCENARIO_BANK_DIR))
    parser.add_argument("--scenario-id", action="append", default=[], help="Run only selected scenario_id values")
    parser.add_argument(
        "--output-json",
        default=str(ARTIFACTS_ROOT / "mvp17_controlled_observation_batch_current.json"),
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
