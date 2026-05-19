from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


LEGACY_FILE_CLASSIFICATIONS: dict[str, dict[str, str]] = {
    "CONTINUITY_OBSERVATION_LEDGER.md": {
        "category": "acceptance_reports",
        "reason": "Human-readable continuity observation ledger for acceptance-facing review.",
    },
    "DASHBOARD_LIVE_SESSION_EXPORT_CURRENT.json": {
        "category": "single_entry_live_windows",
        "reason": "Fresh dashboard_chat live-window export for one sampled entrypoint.",
    },
    "DASHBOARD_LIVE_SESSION_EXPORT_CURRENT.md": {
        "category": "single_entry_live_windows",
        "reason": "Markdown companion for the live dashboard entrypoint export.",
    },
    "DATA_SCHEMA.md": {
        "category": "acceptance_reports",
        "reason": "Schema reference for dashboard_v1 artifact interpretation.",
    },
    "GAP_SUMMARY.md": {
        "category": "acceptance_reports",
        "reason": "Human-readable summary of known capture gaps and validation caveats.",
    },
    "LIVE_CHAT_SUBJECTIVE_VARIABILITY_CURRENT.json": {
        "category": "current_audits",
        "reason": "Current variability audit artifact; useful but not the Stage 1 owner slice.",
    },
    "LIVE_CHAT_SUBJECTIVE_VARIABILITY_CURRENT.md": {
        "category": "current_audits",
        "reason": "Markdown companion for the current subjective variability audit.",
    },
    "LIVE_CHAT_VARIABILITY_CURRENT.json": {
        "category": "current_audits",
        "reason": "Current live chat variability audit artifact.",
    },
    "LIVE_CHAT_VARIABILITY_CURRENT.md": {
        "category": "current_audits",
        "reason": "Markdown companion for the current live chat variability audit.",
    },
    "PLASTICITY_REFLECTION_EVIDENCE.md": {
        "category": "historical/reference",
        "reason": "Historical/reference evidence note; not a current default audit surface.",
    },
    "PROVIDER_RUNTIME_OPENEMOTION_E2E_GATE_CURRENT.json": {
        "category": "current_audits",
        "reason": "Current real-channel provider/runtime/OpenEmotion gate report.",
    },
    "PROVIDER_RUNTIME_OPENEMOTION_E2E_GATE_CURRENT.md": {
        "category": "current_audits",
        "reason": "Markdown companion for the current E2E gate report.",
    },
    "README.md": {
        "category": "acceptance_reports",
        "reason": "Directory-level guidance for dashboard_v1 usage and claim ceiling.",
    },
    "REAL_MAINLINE_CAPTURE_STATUS.md": {
        "category": "acceptance_reports",
        "reason": "Acceptance-facing capture status note for the real mainline lane.",
    },
    "SUBJECT_MAINLINE_AUDIT_CURRENT.json": {
        "category": "current_audits",
        "reason": "Current Stage 1 subject-mainline audit authority artifact.",
    },
    "SUBJECT_MAINLINE_AUDIT_CURRENT.md": {
        "category": "current_audits",
        "reason": "Markdown companion for the current Stage 1 subject-mainline audit.",
    },
    "UNIFIED_HOST_CONTRACT_PARITY_CURRENT.json": {
        "category": "current_audits",
        "reason": "Current unified host contract parity audit artifact.",
    },
    "UNIFIED_HOST_CONTRACT_PARITY_CURRENT.md": {
        "category": "current_audits",
        "reason": "Markdown companion for the current unified host contract parity audit.",
    },
    "UNIFIED_INGRESS_REPLY_SAMPLE_PREFLIGHT_CURRENT.json": {
        "category": "bounded_preflight",
        "reason": "Bounded local readiness probe that must stay outside live baseline counts.",
    },
    "UNIFIED_INGRESS_REPLY_SAMPLE_PREFLIGHT_CURRENT.md": {
        "category": "bounded_preflight",
        "reason": "Markdown companion for the bounded reply-sample preflight artifact.",
    },
    "agency_rollup.json": {
        "category": "baseline_indexes",
        "reason": "Machine-readable rollup derived from agency runs.",
    },
    "agency_runs.jsonl": {
        "category": "baseline_indexes",
        "reason": "Baseline index rows for agency run observations.",
    },
    "build_meta.json": {
        "category": "baseline_indexes",
        "reason": "Index-generation metadata for dashboard_v1.",
    },
    "continuity_observation.jsonl": {
        "category": "baseline_indexes",
        "reason": "Baseline observation index for continuity data.",
    },
    "failures.jsonl": {
        "category": "baseline_indexes",
        "reason": "Baseline failure rows for dashboard_v1.",
    },
    "failures_rollup.json": {
        "category": "baseline_indexes",
        "reason": "Machine-readable failure rollup for dashboard_v1.",
    },
    "gap_summary.json": {
        "category": "baseline_indexes",
        "reason": "Machine-readable gap summary for dashboard_v1.",
    },
    "growth_rollup.json": {
        "category": "baseline_indexes",
        "reason": "Machine-readable growth rollup for dashboard_v1.",
    },
    "growth_signals.jsonl": {
        "category": "baseline_indexes",
        "reason": "Baseline index rows for growth-signal observations.",
    },
    "runs.jsonl": {
        "category": "baseline_indexes",
        "reason": "Primary baseline run index for dashboard_v1.",
    },
    "runs_rollup.json": {
        "category": "baseline_indexes",
        "reason": "Machine-readable run rollup for dashboard_v1.",
    },
}

GENERATED_CLEANUP_ARTIFACTS = (
    "ARTIFACT_MANIFEST_CURRENT.json",
    "ARTIFACT_MANIFEST_CURRENT.md",
    "DASHBOARD_STAGE1_LIVE_RUN_CURRENT.json",
    "DASHBOARD_STAGE1_LIVE_RUN_CURRENT.md",
    "STAGE1_ENTRYPOINT_COMPARATIVE_AUDIT_CURRENT.json",
    "STAGE1_ENTRYPOINT_COMPARATIVE_AUDIT_CURRENT.md",
)

COMPARATIVE_COUNT_FIELDS = (
    "ordinary_chat_turn_count",
    "execute_task_turn_count",
    "subject_gate_ok_count",
    "oe_available_count",
    "mainline_candidate_count",
    "host_only_count",
    "degraded_count",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trim_text(value: Any, *, limit: int = 240) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text if len(text) <= limit else f"{text[:limit]}..."


def build_dashboard_artifact_manifest(root: Path) -> dict[str, Any]:
    category_rows: dict[str, list[dict[str, str]]] = {
        "baseline_indexes": [],
        "current_audits": [],
        "bounded_preflight": [],
        "single_entry_live_windows": [],
        "acceptance_reports": [],
        "historical/reference": [],
    }
    files = sorted(path.name for path in root.iterdir() if path.is_file() and path.name not in GENERATED_CLEANUP_ARTIFACTS)
    unclassified: list[str] = []
    for name in files:
        item = LEGACY_FILE_CLASSIFICATIONS.get(name)
        if item is None:
            unclassified.append(name)
            continue
        category_rows[item["category"]].append(
            {
                "name": name,
                "path": f"artifacts/telegram_real_mainline_v1/dashboard_v1/{name}",
                "reason": item["reason"],
            }
        )

    missing_from_inventory = sorted(set(LEGACY_FILE_CLASSIFICATIONS) - set(files))
    return {
        "schema_version": "dashboard_v1_artifact_manifest.v1",
        "generated_at": _utc_now_iso(),
        "report_kind": "dashboard_v1_legacy_inventory_manifest",
        "inventory_scope": "legacy_top_level_inventory",
        "legacy_file_count": len(files),
        "generated_cleanup_artifacts": [
            f"artifacts/telegram_real_mainline_v1/dashboard_v1/{name}" for name in GENERATED_CLEANUP_ARTIFACTS
        ],
        "category_counts": {key: len(value) for key, value in category_rows.items()},
        "categories": category_rows,
        "unclassified_files": unclassified,
        "missing_from_inventory": missing_from_inventory,
    }


def render_dashboard_artifact_manifest_markdown(manifest: Mapping[str, Any]) -> str:
    lines = [
        "# Dashboard v1 Artifact Manifest",
        "",
        f"- generated_at: `{manifest.get('generated_at')}`",
        f"- report_kind: `{manifest.get('report_kind')}`",
        f"- inventory_scope: `{manifest.get('inventory_scope')}`",
        f"- legacy_file_count: `{manifest.get('legacy_file_count')}`",
        "",
        "## Generated Cleanup Artifacts",
        "",
    ]
    for path in list(manifest.get("generated_cleanup_artifacts") or []):
        lines.append(f"- `{path}`")
    lines.extend(["", "## Categories", ""])
    for category, rows in dict(manifest.get("categories") or {}).items():
        lines.append(f"### `{category}`")
        lines.append("")
        for row in rows:
            lines.append(f"- `{row['name']}`: {row['reason']}")
        if not rows:
            lines.append("- none")
        lines.append("")
    if manifest.get("unclassified_files"):
        lines.extend(["## Unclassified", ""])
        for name in manifest["unclassified_files"]:
            lines.append(f"- `{name}`")
        lines.append("")
    if manifest.get("missing_from_inventory"):
        lines.extend(["## Missing From Inventory", ""])
        for name in manifest["missing_from_inventory"]:
            lines.append(f"- `{name}`")
        lines.append("")
    lines.extend(
        [
            "## Contract",
            "",
            "- This manifest classifies the pre-cleanup top-level dashboard_v1 inventory into stable buckets before any broader directory reshuffle.",
            "- It does not itself move files or promote any artifact above its original claim ceiling.",
        ]
    )
    return "\n".join(lines) + "\n"


def _normalize_live_window_row(item: Mapping[str, Any]) -> dict[str, Any]:
    report = dict(item.get("report") or {})
    summary = dict(report.get("summary") or {})
    entrypoint_contract = dict(report.get("entrypoint_contract") or {})
    ordinary_chat_turn_count = int(summary.get("ordinary_chat_turn_count") or 0)
    mainline_candidate_count = int(summary.get("mainline_candidate_count") or 0)
    host_only_count = int(summary.get("host_only_count") or 0)
    degraded_count = int(summary.get("degraded_count") or 0)
    if ordinary_chat_turn_count <= 0:
        normalized_verdict = "mixed_live_window_observed"
    elif mainline_candidate_count > 0 and host_only_count == 0 and degraded_count == 0:
        normalized_verdict = "ordinary_chat_mainline_observed"
    else:
        normalized_verdict = "ordinary_chat_window_present__mainline_not_observed"
    row = {
        "entrypoint": entrypoint_contract.get("entrypoint") or "unknown",
        "claim_ceiling": report.get("claim_ceiling") or "unknown",
        "ordinary_chat_turn_count": ordinary_chat_turn_count,
        "execute_task_turn_count": int(summary.get("execute_task_turn_count") or 0),
        "subject_gate_ok_count": int(summary.get("subject_gate_ok_count") or 0),
        "oe_available_count": int(summary.get("oe_available_count") or 0),
        "mainline_candidate_count": mainline_candidate_count,
        "host_only_count": host_only_count,
        "degraded_count": degraded_count,
        "source_counts": dict(summary.get("source_counts") or {}),
        "source_artifact": item.get("artifact_path"),
        "report_kind": report.get("report_kind"),
        "verdict": normalized_verdict,
    }
    return row


def build_stage1_entrypoint_comparative_audit(
    *,
    preflight_report: Mapping[str, Any] | None,
    preflight_artifact: str | None,
    live_window_reports: list[Mapping[str, Any]],
    subject_mainline_audit: Mapping[str, Any] | None,
    subject_mainline_artifact: str | None,
) -> dict[str, Any]:
    live_rows = [_normalize_live_window_row(item) for item in live_window_reports]
    unique_entrypoints = sorted({row["entrypoint"] for row in live_rows if row["entrypoint"] != "unknown"})
    aggregate = {field: sum(int(row[field]) for row in live_rows) for field in COMPARATIVE_COUNT_FIELDS}
    source_counts_counter = Counter()
    for row in live_rows:
        source_counts_counter.update(dict(row.get("source_counts") or {}))

    if not live_rows:
        comparative_verdict = "no_live_window_present"
    elif len(unique_entrypoints) >= 2:
        comparative_verdict = "cross_entry_live_windows_present__stage1_verdict_pending"
    elif len(live_rows) >= 2:
        comparative_verdict = "single_entry_multi_window_present__cross_entry_pending"
    else:
        comparative_verdict = "single_entry_live_window_present__cross_entry_pending"

    preflight_summary = dict(preflight_report.get("summary") or {}) if preflight_report else {}
    subject_stage1 = dict((subject_mainline_audit or {}).get("stage1_activation_lens") or {})
    subject_entrypoint = dict((subject_mainline_audit or {}).get("entrypoint_contract") or {})

    return {
        "schema_version": "stage1_entrypoint_comparative_audit.v1",
        "generated_at": _utc_now_iso(),
        "report_kind": "stage1_evidence_ladder",
        "claim_ceiling": "comparative_audit_partial",
        "evidence_ladder": {
            "bounded_preflight": {
                "source_artifact": preflight_artifact,
                "claim_ceiling": preflight_report.get("claim_ceiling") if preflight_report else None,
                "entrypoint": dict(preflight_report.get("entrypoint_contract") or {}).get("entrypoint") if preflight_report else None,
                "summary": preflight_summary,
                "rule": (
                    "Bounded preflight is a local readiness probe only. It must stay outside live baseline counts and can never substitute for a fresh live window."
                ),
            },
            "single_entry_live_windows": {
                "count": len(live_rows),
                "entrypoints_observed": unique_entrypoints,
                "rows": live_rows,
            },
            "comparative_audit": {
                "rows": live_rows,
                "entrypoints_observed": unique_entrypoints,
                "entrypoint_count": len(unique_entrypoints),
                "live_window_aggregate": aggregate,
                "source_mix_summary": {
                    "source_kinds_observed": sorted(source_counts_counter),
                    "mixed_source_window_count": sum(
                        1 for row in live_rows if len(dict(row.get("source_counts") or {})) >= 2
                    ),
                },
                "live_window_source_counts": dict(source_counts_counter),
                "preflight_excluded_from_live_counts": True,
                "rule": (
                    "Only live-window rows contribute to comparative counts. Single-entry evidence proves only the sampled entrypoint and does not auto-promote to cross-entry or Stage 1 pass."
                ),
                "verdict": comparative_verdict,
            },
        },
        "supporting_context": {
            "subject_mainline_audit_reference": {
                "source_artifact": subject_mainline_artifact,
                "accepted_stage1_entrypoints": list(subject_entrypoint.get("accepted_stage1_entrypoints") or []),
                "telegram_mainline_candidate_unexpected_miss_total": int(
                    subject_stage1.get("mainline_candidate_unexpected_miss_total") or 0
                ),
                "note": (
                    "This reference keeps the current Telegram-oriented Stage 1 activation lens visible, but its baseline counts are not merged into the comparative live-window aggregate."
                ),
            }
            if subject_mainline_audit
            else None
        },
    }


def render_stage1_entrypoint_comparative_audit_markdown(report: Mapping[str, Any]) -> str:
    ladder = dict(report.get("evidence_ladder") or {})
    preflight = dict(ladder.get("bounded_preflight") or {})
    live_windows = dict(ladder.get("single_entry_live_windows") or {})
    comparative = dict(ladder.get("comparative_audit") or {})
    context = dict(report.get("supporting_context") or {})
    subject_ref = dict(context.get("subject_mainline_audit_reference") or {})

    lines = [
        "# Stage 1 Entrypoint Comparative Audit",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- report_kind: `{report.get('report_kind')}`",
        f"- claim_ceiling: `{report.get('claim_ceiling')}`",
        f"- comparative_verdict: `{comparative.get('verdict')}`",
        "",
        "## Evidence Ladder",
        "",
        f"- bounded_preflight_artifact: `{preflight.get('source_artifact')}`",
        f"- bounded_preflight_claim_ceiling: `{preflight.get('claim_ceiling')}`",
        f"- bounded_preflight_summary: `{json.dumps(preflight.get('summary') or {}, ensure_ascii=False)}`",
        f"- live_window_count: `{live_windows.get('count')}`",
        f"- entrypoints_observed: `{json.dumps(live_windows.get('entrypoints_observed') or [], ensure_ascii=False)}`",
        "",
        "## Live Window Rows",
        "",
    ]
    rows = list(comparative.get("rows") or [])
    for row in rows:
        lines.extend(
            [
                f"### `{row.get('entrypoint')}`",
                "",
                f"- source_artifact: `{row.get('source_artifact')}`",
                f"- claim_ceiling: `{row.get('claim_ceiling')}`",
                f"- ordinary_chat_turn_count: `{row.get('ordinary_chat_turn_count')}`",
                f"- execute_task_turn_count: `{row.get('execute_task_turn_count')}`",
                f"- subject_gate_ok_count: `{row.get('subject_gate_ok_count')}`",
                f"- oe_available_count: `{row.get('oe_available_count')}`",
                f"- mainline_candidate_count: `{row.get('mainline_candidate_count')}`",
                f"- host_only_count: `{row.get('host_only_count')}`",
                f"- degraded_count: `{row.get('degraded_count')}`",
                f"- verdict: `{row.get('verdict')}`",
                "",
            ]
        )
    if not rows:
        lines.extend(["- none", ""])
    aggregate = dict(comparative.get("live_window_aggregate") or {})
    source_mix_summary = dict(comparative.get("source_mix_summary") or {})
    lines.extend(
        [
            "## Aggregate",
            "",
            f"- aggregate: `{json.dumps(aggregate, ensure_ascii=False)}`",
            f"- source_mix_summary: `{json.dumps(source_mix_summary, ensure_ascii=False)}`",
            f"- live_window_source_counts: `{json.dumps(comparative.get('live_window_source_counts') or {}, ensure_ascii=False)}`",
            f"- rule: `{comparative.get('rule')}`",
            f"- preflight_excluded_from_live_counts: `{comparative.get('preflight_excluded_from_live_counts')}`",
            "",
        ]
    )
    if subject_ref:
        lines.extend(
            [
                "## Supporting Context",
                "",
                f"- subject_mainline_audit_reference: `{subject_ref.get('source_artifact')}`",
                f"- accepted_stage1_entrypoints: `{json.dumps(subject_ref.get('accepted_stage1_entrypoints') or [], ensure_ascii=False)}`",
                f"- telegram_mainline_candidate_unexpected_miss_total: `{subject_ref.get('telegram_mainline_candidate_unexpected_miss_total')}`",
                f"- note: `{_trim_text(subject_ref.get('note'))}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Claim Ceiling",
            "",
            "- This comparative audit preserves the evidence ladder: bounded preflight, then single-entry live windows, then comparative accounting.",
            "- It does not prove cross-entry Stage 1 pass until at least two valid entrypoints are observed under the same contract.",
            "- It does not prove Stage 2 tendency change, Stage 3 user benefit, runtime efficacy, or consciousness-like properties.",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "build_dashboard_artifact_manifest",
    "build_stage1_entrypoint_comparative_audit",
    "render_dashboard_artifact_manifest_markdown",
    "render_stage1_entrypoint_comparative_audit_markdown",
]
