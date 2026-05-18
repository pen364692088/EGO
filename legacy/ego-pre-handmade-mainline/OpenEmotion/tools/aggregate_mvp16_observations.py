from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List


MIN_E5_SAMPLE_COUNT = 3


def render_markdown(payload: Dict[str, Any]) -> str:
    lines = [
        "# MVP16 Controlled Observation Batch Report",
        "",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- git_commit_short: `{payload.get('git_commit_short')}`",
        f"- report_count: `{payload.get('report_count')}`",
        f"- accepted_count: `{payload.get('accepted_count')}`",
        f"- replay_consistent_count: `{payload.get('replay_consistent_count')}`",
        f"- developmental_proposal_present_count: `{payload.get('developmental_proposal_present_count')}`",
        f"- proposal_only_discipline_count: `{payload.get('proposal_only_discipline_count')}`",
        f"- behavioral_authority_none_count: `{payload.get('behavioral_authority_none_count')}`",
        f"- bounded_influence_present_count: `{payload.get('bounded_influence_present_count')}`",
        f"- identity_preservation_violation_count: `{payload.get('identity_preservation_violation_count')}`",
        f"- distinct_targets: `{payload.get('distinct_targets')}`",
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
            f"proposal=`{scenario.get('developmental_proposal_present')}` "
            f"replay_valid=`{scenario.get('replay_valid')}` "
            f"proposal_only=`{scenario.get('proposal_only_discipline_consistent')}` "
            f"authority_none=`{scenario.get('behavioral_authority_none')}` "
            f"bounded_influence=`{scenario.get('bounded_influence_present')}`"
        )
    lines.extend(["", "## Boundary", "", payload.get("boundary", ""), ""])
    return "\n".join(lines)


def aggregate_reports(*, reports: List[Dict[str, Any]], git_commit_short: str, bank_dir: str) -> Dict[str, Any]:
    report_count = len(reports)
    accepted_count = sum(1 for report in reports if report["accepted"])
    replay_consistent_count = sum(1 for report in reports if report["replay_valid"])
    developmental_proposal_present_count = sum(
        1 for report in reports if report["developmental_proposal_present"]
    )
    proposal_only_discipline_count = sum(
        1 for report in reports if report["proposal_only_discipline_consistent"]
    )
    behavioral_authority_none_count = sum(1 for report in reports if report["behavioral_authority_none"])
    bounded_influence_present_count = sum(1 for report in reports if report["bounded_influence_present"])
    identity_preservation_violation_count = sum(
        int(report["identity_preservation_violation_count"]) for report in reports
    )
    distinct_targets = sorted(
        {str(report["dialogue_frame_target"]) for report in reports if report["dialogue_frame_target"]}
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
        and developmental_proposal_present_count == report_count
        and proposal_only_discipline_count == report_count
        and behavioral_authority_none_count == report_count
        and bounded_influence_present_count == report_count
        and identity_preservation_violation_count == 0
    )
    return {
        "schema_version": "mvp16.controlled_observation.batch.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit_short": git_commit_short,
        "scenario_bank_dir": str(bank_dir),
        "report_count": report_count,
        "accepted_count": accepted_count,
        "replay_consistent_count": replay_consistent_count,
        "developmental_proposal_present_count": developmental_proposal_present_count,
        "proposal_only_discipline_count": proposal_only_discipline_count,
        "behavioral_authority_none_count": behavioral_authority_none_count,
        "bounded_influence_present_count": bounded_influence_present_count,
        "identity_preservation_violation_count": identity_preservation_violation_count,
        "distinct_targets": distinct_targets,
        "distinct_surface_reasons": distinct_surface_reasons,
        "scenario_ids": [report["scenario_id"] for report in reports],
        "source_breakdown": source_breakdown,
        "reports": reports,
        "status": "pass" if e5_pass else "hold",
        "verification_level": "V5" if e5_pass else "V4",
        "evidence_level": "E5" if e5_pass else "E4",
        "boundary": (
            "This aggregate report proves controlled multi-sample developmental-self writeback stability on the "
            "formal runtime mainline with proposal-only continuity candidates. It does not claim live autonomy, "
            "direct reply authority, or broader transport evidence."
        ),
        "external_risk_note": (
            "Provider 429/401 remains an external budget-layer risk; it is not counted as a WP11 blocker unless it "
            "regresses formal owner writeback."
        ),
    }
