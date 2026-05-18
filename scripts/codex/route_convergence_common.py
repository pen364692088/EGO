#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from program_state_common import ROOT, load_yaml


PROGRAM_STATE_PATH = ROOT / "docs" / "PROGRAM_STATE_UNIFIED.yaml"
TASKS_ROOT = ROOT / "docs" / "codex" / "tasks"
TASK_LANE_INDEX_PATH = TASKS_ROOT / "TASK_LANE_INDEX.md"
REPO_HYGIENE_POLICY_PATH = ROOT / "docs" / "REPO_HYGIENE_POLICY.md"
REPO_SURFACE_MAP_PATH = ROOT / "docs" / "REPO_SURFACE_MAP.md"

LANE_ORDER = [
    "active_default",
    "supporting_active",
    "parked",
    "closed_evidence",
    "reference_only",
]
LANE_TITLES = {
    "active_default": "Active Default",
    "supporting_active": "Supporting Active",
    "parked": "Parked",
    "closed_evidence": "Closed Evidence",
    "reference_only": "Reference Only",
}


@dataclass(frozen=True)
class RouteEntry:
    key: str
    label: str
    lane: str
    kind: str
    paths: tuple[str, ...]
    why: str
    workstream_id: str | None = None


@dataclass(frozen=True)
class HygieneRule:
    path_prefix: str
    class_name: str
    tracked_policy: str
    ignore_snippets: tuple[str, ...]
    next_action: str
    note: str


TASK_OVERRIDES: dict[str, dict[str, Any]] = {
    "ego-operator-human-operator-trial-v2": {
        "lane": "active_default",
        "label": "EgoOperator Human Operator Trial v2",
        "why": "Current EgoOperator human-observation gate; records whether the operator-first runtime is actually usable in continuous Chinese operator work.",
        "workstream_id": "ego_operator_first_transition",
    },
    "ego-operator-rename-docs-safety-v1": {
        "lane": "closed_evidence",
        "label": "EgoOperator Rename + Docs Safety v1",
        "why": "Previous EgoOperator naming and reader-safety transition record; superseded by the human operator trial v2 task as the active observation owner.",
        "workstream_id": "ego_operator_first_transition",
    },
    "ego-mainline-demotion-v1": {
        "lane": "closed_evidence",
        "label": "Ego Mainline Demotion v1",
        "why": "Previous operator-first transition record; superseded by the EgoOperator rename/docs-safety task while preserving legacy demotion evidence.",
        "workstream_id": "ego_operator_first_transition",
    },
    "subject-system-v1-governed-proactivity": {
        "lane": "closed_evidence",
        "label": "Subject System v1 Governed Proactivity",
        "why": "Legacy pre-EgoOperator governed-proactivity evidence; preserved for reference and fallback, not the active default route.",
        "workstream_id": "subject_system_v1_governed_proactivity",
    },
    "active-inference-mainline-activation": {
        "lane": "closed_evidence",
        "label": "Active-Inference Mainline Activation",
        "why": "Frozen dashboard-only bounded predecessor tranche; preserve as closed evidence, not the active default route.",
        "workstream_id": "active_inference_mainline_activation",
    },
    "repo-cleanup-route-convergence": {
        "lane": "supporting_active",
        "label": "Repo Cleanup Route Convergence",
        "why": "Supporting cleanup lane for route index, hygiene gate, and Stage 1 evidence convergence; must not replace the active default track.",
        "workstream_id": "repo_cleanup_route_convergence",
    },
    "repo-mainline-clarity-v1": {
        "lane": "supporting_active",
        "label": "Repo Mainline Clarity v1",
        "why": "Supporting repo-view slice for mainline onboarding, surface-map clarity, and staged operational-exhaust hygiene; must not replace the active default track.",
    },
    "provider-runtime-openemotion-e2e-gate": {
        "lane": "supporting_active",
        "label": "Provider/Runtime/OpenEmotion E2E Gate",
        "why": "Real-channel supporting gate for the current mainline; supports Stage 1 truth but is not a competing route.",
        "workstream_id": "provider_runtime_openemotion_e2e_gate",
    },
    "telegram-subject-mainline-audit": {
        "lane": "supporting_active",
        "label": "Telegram Subject Mainline Audit",
        "why": "Supporting audit slice for Stage 1 subject-ingress accounting and live evidence discipline.",
        "workstream_id": "live_subject_ingress_observation",
    },
    "unified-host-contract-correctness": {
        "lane": "supporting_active",
        "label": "Unified Host Contract Correctness",
        "why": "Frozen predecessor tranche that still supports Stage 1 equivalent-entry reasoning.",
        "workstream_id": "unified_host_contract_correctness",
    },
    "repo-authority-cleanup": {
        "lane": "closed_evidence",
        "label": "Repo Authority Cleanup",
        "why": "Repo/integration boundary cleanup is closed out and no longer competes for current execution ownership.",
        "workstream_id": "repo_authority_cleanup",
    },
    "ai-self-awareness-minimal-framework": {
        "lane": "closed_evidence",
        "label": "AI Self-Awareness Minimal Framework",
        "why": "Selection closeout and MVS demotion authority live here; this is closed research evidence, not the current runtime owner.",
        "workstream_id": "ai_self_awareness_research",
    },
}

RUNTIME_PROXIMAL_PREFIX = "runtime-proximal-"
REFERENCE_ONLY_PREFIXES = (
    "codex-harness-hardening",
    "e4-shadow-h1-formal-mainline-sampling",
    "egocore-pytest-suite-stabilization",
    "h1-canonical-promotion-prep",
    "h1-canonical-shadow-patch",
    "h1-preflight-same-surface-unblock",
    "identify-public-causal-driver-for-mvs-trial-2",
    "interface-layer-consolidation",
    "live-chat-subjective-variability",
    "llm-in-loop-whole-chain-sampling",
    "mandatory-subject-ingress-all-turns",
    "mvs-h1-external-eval-corpus",
    "mvs-h1-external-raw-extraction-replay",
    "mvs-h1-external-replay-execution",
    "openemotion-candidate-hash-stabilization",
    "openemotion-daemon-lifecycle-stabilization",
    "openemotion-env-health-stabilization",
    "openemotion-live-integration-fixture-stabilization",
    "openemotion-mvp10-replay-determinism-stabilization",
    "openemotion-mvp11-replay-tempfile-stabilization",
    "openemotion-outcome-capture-stabilization",
    "openemotion-readme-contract-stabilization",
    "openemotion-test-collection-stabilization",
    "openemotion-v6k2-whitelist-alert-stabilization",
    "proto-self-seed-host-evidence-stabilization",
    "proto-self-seed-real-rollout",
    "simulated-shadow-h1-mainline-sampling",
    "wp12-maintenance-institutionalization",
)

EXTRA_ROUTE_ENTRIES = (
    RouteEntry(
        key="wp17-mvp22-authority",
        label="WP17 / MVP22 Authority Refs",
        lane="parked",
        kind="authority_refs",
        paths=(
            "Tasks/MVP22_task_plan.md",
            "Tasks/active/mvp22_long_horizon_self_continuity/STATUS.md",
        ),
        why="Authority-frozen bounded continuity lane; preserved but parked behind the active default track.",
        workstream_id="wp17_bounded_continuity_lane",
    ),
    RouteEntry(
        key="mvs-aligned-compact-closed-evidence",
        label="MVS-Aligned Compact Closed Evidence",
        lane="closed_evidence",
        kind="authority_refs",
        paths=(
            "docs/codex/tasks/ai-self-awareness-minimal-framework/SELECTION_CLOSEOUT.md",
            "docs/codex/tasks/ai-self-awareness-minimal-framework/MVS_ALIGNED_COMPACT_PROTOTYPE_DESIGN.md",
        ),
        why="Closed evidence only; selection closeout keeps it out of the default implementation track.",
    ),
)

HYGIENE_RULES = (
    HygieneRule(
        path_prefix="legacy/ego-pre-handmade-mainline/OpenEmotion/artifacts/mvp12/cycle_traces/",
        class_name="operational_exhaust_archive",
        tracked_policy="grandfathered legacy tracked inventory; ignore new raw cycle traces",
        ignore_snippets=("legacy/ego-pre-handmade-mainline/OpenEmotion/artifacts/mvp12/cycle_traces/",),
        next_action="Keep acceptance-facing CURRENT reports elsewhere; future lane may de-track legacy trace jsons in one archival pass.",
        note="This path is high-volume operational exhaust, not a primary authority surface.",
    ),
    HygieneRule(
        path_prefix="legacy/ego-pre-handmade-mainline/EgoCore/artifacts/proto_self_store/",
        class_name="session_store_exhaust",
        tracked_policy="grandfathered seed snapshots allowed; ignore new session-store churn",
        ignore_snippets=("legacy/ego-pre-handmade-mainline/EgoCore/artifacts/proto_self_store/",),
        next_action="Keep only deliberate seed/session examples tracked; move live store growth out of the repo surface.",
        note="Session-store churn should not flood the worktree or compete with acceptance artifacts.",
    ),
    HygieneRule(
        path_prefix="legacy/ego-pre-handmade-mainline/EgoCore/logs/",
        class_name="runtime_log_exhaust",
        tracked_policy="grandfathered archive logs remain for reference; ignore new runtime logs",
        ignore_snippets=("legacy/ego-pre-handmade-mainline/EgoCore/logs/",),
        next_action="Future cleanup may de-track archived logs after explicit archival review; new log churn stays ignored.",
        note="Runtime log output is operational exhaust unless a task explicitly promotes a CURRENT artifact elsewhere.",
    ),
    HygieneRule(
        path_prefix="legacy/ego-pre-handmade-mainline/EgoCore/data/session_logs/",
        class_name="session_log_exhaust",
        tracked_policy="ignore new session logs; no tracked baseline is expected here",
        ignore_snippets=("legacy/ego-pre-handmade-mainline/EgoCore/data/session_logs/",),
        next_action="Keep session-log capture out of tracked state unless a task explicitly exports a bounded CURRENT artifact.",
        note="This path should not carry repo-facing acceptance state.",
    ),
    HygieneRule(
        path_prefix="artifacts/dashboard_runtime_logs/",
        class_name="dashboard_runtime_exhaust",
        tracked_policy="ignore runtime-server logs and polling exhaust",
        ignore_snippets=("artifacts/dashboard_runtime_logs/",),
        next_action="Promote only explicit CURRENT reports into acceptance-facing artifact roots.",
        note="Dashboard runtime logs are operational exhaust, not current evidence by default.",
    ),
    HygieneRule(
        path_prefix="artifacts/launcher_meta/",
        class_name="launcher_meta_exhaust",
        tracked_policy="ignore launcher metadata and temp orchestration byproducts",
        ignore_snippets=("artifacts/launcher_meta/",),
        next_action="Keep launcher metadata out of the tracked repo unless a bounded task explicitly promotes it.",
        note="Launcher/process metadata is environment exhaust, not a stable authority source.",
    ),
    HygieneRule(
        path_prefix="temp/",
        class_name="runtime_temp_exhaust",
        tracked_policy="ignore local temp outputs and runtime JSONL by default",
        ignore_snippets=("temp/",),
        next_action="Promote only explicit lab reports or accepted evidence artifacts outside temp.",
        note="Root temp output is local operational exhaust and must not become an authority surface.",
    ),
    HygieneRule(
        path_prefix=".pytest_cache/",
        class_name="test_cache_exhaust",
        tracked_policy="ignore pytest cache output",
        ignore_snippets=(".pytest_cache/",),
        next_action="Never commit pytest cache directories.",
        note="Pytest cache is a local acceleration artifact, not evidence.",
    ),
    HygieneRule(
        path_prefix="logs/",
        class_name="runtime_log_exhaust",
        tracked_policy="ignore root runtime logs by default",
        ignore_snippets=("logs/",),
        next_action="Promote only bounded CURRENT reports outside raw logs.",
        note="Root log output is operational exhaust unless explicitly curated.",
    ),
    HygieneRule(
        path_prefix="legacy/ego-pre-handmade-mainline/EgoCore/temp/",
        class_name="egocore_temp_exhaust",
        tracked_policy="ignore EgoCore local temp outputs",
        ignore_snippets=("legacy/ego-pre-handmade-mainline/EgoCore/temp/", "legacy/ego-pre-handmade-mainline/EgoCore/tmp/"),
        next_action="Keep local EgoCore temp output out of tracked state.",
        note="EgoCore temp directories are runtime byproducts unless a task explicitly promotes a report.",
    ),
    HygieneRule(
        path_prefix="legacy/ego-pre-handmade-mainline/OpenEmotion/logs/",
        class_name="openemotion_log_exhaust",
        tracked_policy="ignore OpenEmotion raw runtime logs",
        ignore_snippets=("legacy/ego-pre-handmade-mainline/OpenEmotion/logs/",),
        next_action="Promote only bounded CURRENT reports outside raw logs.",
        note="OpenEmotion logs are operational exhaust unless curated into an accepted artifact.",
    ),
)

SURFACE_MAP_ROWS = (
    {
        "surface": "operator_runtime",
        "paths": ("EgoOperator/",),
        "role": "Current default operator-first runtime candidate: natural language understanding, approvals, memory, trace, and human trial gates.",
        "authority": "Default implementation surface for new operator experience work; claims remain local/candidate unless human-observable gates pass.",
    },
    {
        "surface": "legacy_reference",
        "paths": (
            "legacy/ego-pre-handmade-mainline/EgoCore/",
            "legacy/ego-pre-handmade-mainline/OpenEmotion/",
            "legacy/ego-pre-handmade-mainline/ego_desktop_lab/",
        ),
        "role": "Pre-EgoOperator runtime, subject kernel, and lab harness retained as reference/fallback/algorithm sources.",
        "authority": "Not the default implementation lane; do not re-promote without a new Stage Card and evidence gate.",
    },
    {
        "surface": "governance",
        "paths": (
            "docs/PROGRAM_STATE_UNIFIED.yaml",
            "docs/codex/tasks/TASK_LANE_INDEX.md",
            "docs/REPO_HYGIENE_POLICY.md",
            "docs/MAINLINE_QUICKSTART.md",
        ),
        "role": "Human and agent route map for current mainline, lane ownership, and cleanup boundaries.",
        "authority": "PROGRAM_STATE_UNIFIED is source of truth; generated views are route maps only.",
    },
    {
        "surface": "evidence",
        "paths": ("artifacts/evidence_ledger/", "accepted CURRENT reports"),
        "role": "Accepted evidence and replayable proof surfaces.",
        "authority": "Evidence supports claims but does not become runtime owner.",
    },
    {
        "surface": "archive_reference",
        "paths": ("docs/archive/", "artifacts/archive/", "closed-evidence task dirs"),
        "role": "Historical, diagnostic, or closed proof material.",
        "authority": "Findable reference only; not current implementation authority.",
    },
    {
        "surface": "operational_exhaust",
        "paths": ("temp/", "logs/", "runtime JSONL", "cache", "session stores"),
        "role": "Local runtime byproducts and machine-specific output.",
        "authority": "Ignored or explicitly marked operational exhaust; never a default claim source.",
    },
)


def load_program_state() -> dict[str, Any]:
    return load_yaml(PROGRAM_STATE_PATH)


def _git_lines(args: list[str]) -> list[str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def tracked_count(path_prefix: str) -> int:
    return len(_git_lines(["ls-files", path_prefix]))


def list_task_dirs() -> list[str]:
    return sorted(path.name for path in TASKS_ROOT.iterdir() if path.is_dir())


def _default_route_for_slug(slug: str) -> tuple[str, str]:
    if slug.startswith(RUNTIME_PROXIMAL_PREFIX):
        return (
            "closed_evidence",
            "Runtime-proximal runner/planning slices are now frozen bounded evidence, not active route contenders.",
        )
    if slug in REFERENCE_ONLY_PREFIXES:
        return (
            "reference_only",
            "Historical stabilization, sampling, or exploratory task; retained as reference/supporting history only.",
        )
    return (
        "reference_only",
        "No current authority promotes this task as an active or parked route; keep it as reference-only by default.",
    )


def build_route_entries(program_state: dict[str, Any] | None = None) -> list[RouteEntry]:
    state = program_state or load_program_state()
    workstream_statuses = {item.get("id"): item.get("status") for item in state.get("workstreams") or []}
    entries: list[RouteEntry] = []
    for slug in list_task_dirs():
        override = TASK_OVERRIDES.get(slug)
        if override:
            lane = str(override["lane"])
            label = str(override["label"])
            why = str(override["why"])
            workstream_id = override.get("workstream_id")
        else:
            lane, why = _default_route_for_slug(slug)
            label = slug.replace("-", " ").title()
            workstream_id = None
        if workstream_id and workstream_id in workstream_statuses:
            why = f"{why} Current workstream status: `{workstream_statuses[workstream_id]}`."
        entries.append(
            RouteEntry(
                key=slug,
                label=label,
                lane=lane,
                kind="codex_task",
                paths=(f"docs/codex/tasks/{slug}/",),
                why=why,
                workstream_id=workstream_id,
            )
        )
    entries.extend(EXTRA_ROUTE_ENTRIES)
    return sorted(entries, key=lambda item: (LANE_ORDER.index(item.lane), item.label.lower(), item.key))


def _render_path_list(paths: tuple[str, ...]) -> str:
    return "<br>".join(f"`{path}`" for path in paths)


def render_task_lane_index(program_state: dict[str, Any] | None = None) -> str:
    state = program_state or load_program_state()
    entries = build_route_entries(state)
    lane_counts = {lane: sum(1 for entry in entries if entry.lane == lane) for lane in LANE_ORDER}

    lines = [
        "# Task Lane Index",
        "",
        "> AUTO-GENERATED FILE. Do not edit by hand.",
        "> Derived from `docs/PROGRAM_STATE_UNIFIED.yaml` plus repo-tracked lane rules in `scripts/codex/route_convergence_common.py`.",
        "> This file is a route map, not a second authority source.",
        "> If this file disagrees with `docs/PROGRAM_STATE_UNIFIED.yaml`, trust `docs/PROGRAM_STATE_UNIFIED.yaml` and regenerate route-convergence views.",
        "",
        "## Lane Rules",
        "",
        "- Exactly one lane may be `active_default`.",
        "- `supporting_active` may help the current default track, but may not replace the execution owner.",
        "- `parked` lanes keep authority/task-package readiness without competing for default execution priority.",
        "- `closed_evidence` records completed/frozen proof surfaces that no longer compete as current implementation tracks.",
        "- `reference_only` is the default fallback for historical, diagnostic, or exploratory directories that are not current route owners.",
        "",
        "## Lane Counts",
        "",
        "| lane | count |",
        "|---|---:|",
    ]
    for lane in LANE_ORDER:
        lines.append(f"| `{lane}` | {lane_counts[lane]} |")

    for lane in LANE_ORDER:
        rows = [entry for entry in entries if entry.lane == lane]
        lines.extend(
            [
                "",
                f"## {LANE_TITLES[lane]}",
                "",
                "| entry | kind | workstream | paths | why |",
                "|---|---|---|---|---|",
            ]
        )
        for entry in rows:
            workstream = f"`{entry.workstream_id}`" if entry.workstream_id else "n/a"
            lines.append(
                f"| {entry.label} | `{entry.kind}` | {workstream} | {_render_path_list(entry.paths)} | {entry.why} |"
            )
    return "\n".join(lines) + "\n"


def build_hygiene_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rule in HYGIENE_RULES:
        rows.append(
            {
                "path_prefix": rule.path_prefix,
                "class_name": rule.class_name,
                "tracked_policy": rule.tracked_policy,
                "tracked_count": tracked_count(rule.path_prefix),
                "ignore_snippets": list(rule.ignore_snippets),
                "next_action": rule.next_action,
                "note": rule.note,
            }
        )
    return rows


def render_repo_hygiene_policy() -> str:
    rows = build_hygiene_rows()
    lines = [
        "# Repo Hygiene Policy",
        "",
        "> AUTO-GENERATED FILE. Do not edit by hand.",
        "> Generated by `python3 scripts/codex/generate_route_convergence_views.py`.",
        "> This policy is descriptive governance for worktree hygiene. The authority source for route selection remains `docs/PROGRAM_STATE_UNIFIED.yaml`.",
        "> If this file drifts from current authority, regenerate route-convergence views and trust `docs/PROGRAM_STATE_UNIFIED.yaml` for route ownership.",
        "",
        "## First-Round Rule",
        "",
        "- Keep acceptance-facing `CURRENT` / aggregate reports tracked when they are explicitly promoted.",
        "- Treat raw traces, session stores, runtime logs, dashboard polling byproducts, and launcher metadata as operational exhaust by default.",
        "- This first-round gate grandfathers explicit legacy tracked inventory, but blocks new tracked or unignored exhaust under the path prefixes below.",
        "",
        "## Policy Table",
        "",
        "| path prefix | class | tracked policy | current tracked count | ignore snippets | next action |",
        "|---|---|---|---:|---|---|",
    ]
    for row in rows:
        snippets = "<br>".join(f"`{item}`" for item in row["ignore_snippets"])
        lines.append(
            f"| `{row['path_prefix']}` | `{row['class_name']}` | {row['tracked_policy']} | {row['tracked_count']} | {snippets} | {row['next_action']} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
        ]
    )
    for row in rows:
        lines.append(f"- `{row['path_prefix']}`: {row['note']}")
    return "\n".join(lines) + "\n"


def render_repo_surface_map() -> str:
    lines = [
        "# Repo Surface Map",
        "",
        "> AUTO-GENERATED FILE. Do not edit by hand.",
        "> Generated by `python3 scripts/codex/generate_route_convergence_views.py`.",
        "> This map is a derived onboarding view, not a second authority source.",
        "> If this file disagrees with `docs/PROGRAM_STATE_UNIFIED.yaml`, trust `docs/PROGRAM_STATE_UNIFIED.yaml`.",
        "",
        "## Surface Table",
        "",
        "| surface | paths | role | authority boundary |",
        "|---|---|---|---|",
    ]
    for row in SURFACE_MAP_ROWS:
        paths = "<br>".join(f"`{path}`" for path in row["paths"])
        lines.append(f"| `{row['surface']}` | {paths} | {row['role']} | {row['authority']} |")
    lines.extend(
        [
            "",
            "## Rules",
            "",
            "- `EgoOperator/` is the default operator-first implementation surface.",
            "- `legacy/ego-pre-handmade-mainline/ego_desktop_lab/` is a reference harness, not a second runtime authority.",
            "- Legacy Shell / Telegram paths are reference/fallback only unless a future task explicitly restores them.",
            "- Closed evidence and archive/reference surfaces remain findable but do not compete with the active default lane.",
            "- Operational exhaust must stay ignored unless an explicit task promotes a bounded CURRENT report.",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "HYGIENE_RULES",
    "PROGRAM_STATE_PATH",
    "REPO_HYGIENE_POLICY_PATH",
    "REPO_SURFACE_MAP_PATH",
    "SURFACE_MAP_ROWS",
    "TASK_LANE_INDEX_PATH",
    "build_hygiene_rows",
    "build_route_entries",
    "list_task_dirs",
    "load_program_state",
    "render_repo_hygiene_policy",
    "render_repo_surface_map",
    "render_task_lane_index",
]
