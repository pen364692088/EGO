from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List


MIN_E5_SAMPLE_COUNT = 3


def render_markdown(payload: Dict[str, Any]) -> str:
    lines = [
        "# MVP17 Controlled Observation Batch Report",
        "",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- git_commit_short: `{payload.get('git_commit_short')}`",
        f"- report_count: `{payload.get('report_count')}`",
        f"- accepted_count: `{payload.get('accepted_count')}`",
        f"- replay_consistent_count: `{payload.get('replay_consistent_count')}`",
        f"- social_proposal_present_count: `{payload.get('social_proposal_present_count')}`",
        f"- proposal_only_discipline_count: `{payload.get('proposal_only_discipline_count')}`",
        f"- behavioral_authority_none_count: `{payload.get('behavioral_authority_none_count')}`",
        f"- bounded_influence_present_count: `{payload.get('bounded_influence_present_count')}`",
        f"- distinct_targets: `{payload.get('distinct_targets')}`",
        f"- distinct_counterpart_ids: `{payload.get('distinct_counterpart_ids')}`",
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
            f"proposal=`{scenario.get('social_proposal_present')}` "
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
    social_proposal_present_count = sum(1 for report in reports if report["social_proposal_present"])
    proposal_only_discipline_count = sum(
        1 for report in reports if report["proposal_only_discipline_consistent"]
    )
    behavioral_authority_none_count = sum(1 for report in reports if report["behavioral_authority_none"])
    bounded_influence_present_count = sum(1 for report in reports if report["bounded_influence_present"])
    distinct_targets = sorted(
        {str(report["dialogue_frame_target"]) for report in reports if report["dialogue_frame_target"]}
    )
    distinct_counterpart_ids = sorted(
        {
            str(counterpart_id)
            for report in reports
            for counterpart_id in list(report.get("counterpart_ids") or [])
            if str(counterpart_id).strip()
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
        and social_proposal_present_count == report_count
        and proposal_only_discipline_count == report_count
        and behavioral_authority_none_count == report_count
        and bounded_influence_present_count == report_count
    )
    return {
        "schema_version": "mvp17.controlled_observation.batch.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit_short": git_commit_short,
        "scenario_bank_dir": str(bank_dir),
        "report_count": report_count,
        "accepted_count": accepted_count,
        "replay_consistent_count": replay_consistent_count,
        "social_proposal_present_count": social_proposal_present_count,
        "proposal_only_discipline_count": proposal_only_discipline_count,
        "behavioral_authority_none_count": behavioral_authority_none_count,
        "bounded_influence_present_count": bounded_influence_present_count,
        "distinct_targets": distinct_targets,
        "distinct_counterpart_ids": distinct_counterpart_ids,
        "distinct_surface_reasons": distinct_surface_reasons,
        "scenario_ids": [report["scenario_id"] for report in reports],
        "source_breakdown": source_breakdown,
        "reports": reports,
        "status": "pass" if e5_pass else "hold",
        "verification_level": "V5" if e5_pass else "V4",
        "evidence_level": "E5" if e5_pass else "E4",
        "boundary": (
            "This aggregate report proves controlled multi-sample social proposal-only writeback stability on the "
            "formal runtime mainline. It does not claim live autonomy, direct reply authority, or broader "
            "transport evidence."
        ),
        "external_risk_note": (
            "Provider 429/401 remains an external budget-layer risk; it is not counted as a WP12 blocker unless it "
            "regresses formal owner social writeback."
        ),
    }
