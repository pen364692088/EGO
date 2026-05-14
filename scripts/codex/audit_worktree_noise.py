#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

CATEGORIES = (
    "formal_runtime_dirty",
    "authority_dirty",
    "formal_evidence_dirty",
    "operational_exhaust",
    "generated_or_mirror",
    "untracked_unknown",
    "cleanup_candidate",
)

RECOMMENDED_NEXT_OWNER = {
    "formal_runtime_dirty": "mainline_runtime_review",
    "authority_dirty": "mainline_runtime_review",
    "formal_evidence_dirty": "evidence_admission",
    "operational_exhaust": "operational_exhaust_policy",
    "generated_or_mirror": "evidence_admission",
    "untracked_unknown": "unknown_manual_triage",
    "cleanup_candidate": "no_action",
}

AUTHORITY_PATHS = {
    "docs/PROGRAM_STATE_UNIFIED.yaml",
    "EgoCore/docs/PROGRAM_STATE_UNIFIED.yaml",
    "OpenEmotion/docs/PROGRAM_STATE_UNIFIED.yaml",
}

FORMAL_EVIDENCE_PREFIXES = (
    "artifacts/evidence_ledger/",
    "artifacts/reports/",
    "artifacts/capability_registry/",
    "artifacts/telegram_real_mainline_v1/",
    "EgoCore/artifacts/test_runs/",
)

FORMAL_RUNTIME_PREFIXES = (
    "EgoCore/app/",
    "EgoCore/config/",
    "EgoCore/modules/",
    "EgoCore/scripts/",
    "EgoCore/tests/",
    "EgoCore/tools/",
    "OpenEmotion/openemotion/",
    "OpenEmotion/tests/",
    "OpenEmotion/scripts/",
    "OpenEmotion/data/",
    "ego_desktop_lab/",
)

OPERATIONAL_EXHAUST_PREFIXES = (
    "temp/",
    "logs/",
    "EgoCore/logs/",
    "OpenEmotion/logs/",
    "EgoCore/.venv_run/",
    "OpenEmotion/.venv/",
    "OpenEmotion/venv/",
    ".pytest_cache/",
    ".venv-env-restore/",
    ".ssh/",
)

OPERATIONAL_EXHAUST_SUFFIXES = (
    ".jsonl",
    ".log",
    ".pyc",
    ".pyo",
)

GENERATED_OR_MIRROR_PREFIXES = (
    "docs/STATUS.md",
    "docs/OVERALL_PROGRESS.md",
    "docs/CURRENT_PROJECT_LOGIC_FLOW.md",
    "EgoCore/docs/generated/",
    "artifacts/proto_self_mirror/",
    "EgoCore/artifacts/proto_self_mirror/",
    "OpenEmotion/artifacts/",
)

CLEANUP_CANDIDATE_PREFIXES = (
    "docs/codex/tasks/repo-mainline-clarity-v1/",
    "scripts/codex/audit_worktree_noise.py",
    "scripts/codex/verify_mainline_clarity.py",
)


@dataclass(frozen=True)
class WorktreeItem:
    path: str
    xy: str
    change_type: str
    category: str
    cleanup_scope: bool
    recommended_next_owner: str
    reason: str
    old_path: str | None = None


def _matches(path: str, prefix: str) -> bool:
    return path == prefix.rstrip("/") or path.startswith(prefix)


def _matches_any(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(_matches(path, prefix) for prefix in prefixes)


def _change_type(xy: str) -> str:
    if xy == "??":
        return "untracked"
    if "D" in xy:
        return "deleted"
    if "R" in xy:
        return "renamed"
    if "A" in xy:
        return "added"
    if "M" in xy:
        return "modified"
    return "changed"


def _classify(path: str, xy: str) -> tuple[str, str]:
    if path in AUTHORITY_PATHS:
        return "authority_dirty", "authority_dirty_do_not_stage_in_cleanup"
    if _matches_any(path, FORMAL_EVIDENCE_PREFIXES):
        return "formal_evidence_dirty", "formal_evidence_do_not_stage_in_cleanup"
    if _matches_any(path, CLEANUP_CANDIDATE_PREFIXES):
        return "cleanup_candidate", "current repo-mainline-clarity cleanup surface"
    if _matches_any(path, OPERATIONAL_EXHAUST_PREFIXES):
        return "operational_exhaust", "runtime/session/cache/log exhaust"
    if "__pycache__/" in path or path.endswith(OPERATIONAL_EXHAUST_SUFFIXES):
        return "operational_exhaust", "cache/log/jsonl exhaust"
    if _matches_any(path, GENERATED_OR_MIRROR_PREFIXES):
        return "generated_or_mirror", "generated status or mirrored observation surface"
    if _matches_any(path, FORMAL_RUNTIME_PREFIXES):
        return "formal_runtime_dirty", "formal runtime code or tests outside cleanup scope"
    if xy == "??":
        return "untracked_unknown", "untracked path outside admitted cleanup scope"
    return "untracked_unknown", "dirty path outside admitted cleanup scope"


def _git_status_porcelain_z() -> list[WorktreeItem]:
    proc = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z"],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="replace"))

    chunks = [chunk for chunk in proc.stdout.decode("utf-8", errors="replace").split("\0") if chunk]
    items: list[WorktreeItem] = []
    index = 0
    while index < len(chunks):
        chunk = chunks[index]
        index += 1
        if len(chunk) < 4:
            continue
        xy = chunk[:2]
        path = chunk[3:]
        old_path: str | None = None
        if "R" in xy or "C" in xy:
            if index < len(chunks):
                old_path = chunks[index]
                index += 1
        category, reason = _classify(path, xy)
        items.append(
            WorktreeItem(
                path=path,
                xy=xy,
                change_type=_change_type(xy),
                category=category,
                cleanup_scope=category == "cleanup_candidate",
                recommended_next_owner=RECOMMENDED_NEXT_OWNER[category],
                reason=reason,
                old_path=old_path,
            )
        )
    return sorted(items, key=lambda item: item.path)


def build_audit_payload() -> dict[str, object]:
    items = _git_status_porcelain_z()
    categories: dict[str, list[dict[str, object]]] = {category: [] for category in CATEGORIES}
    for item in items:
        categories[item.category].append(asdict(item))

    counts = {category: len(categories[category]) for category in CATEGORIES}
    category_summaries = {
        category: {
            "count": counts[category],
            "recommended_next_owner": RECOMMENDED_NEXT_OWNER[category],
            "top_20_paths": [item["path"] for item in categories[category][:20]],
        }
        for category in CATEGORIES
    }
    cleanup_scope_paths = [item.path for item in items if item.cleanup_scope]
    blocked_cleanup_paths = sorted(
        path
        for path in (
            "docs/PROGRAM_STATE_UNIFIED.yaml",
            "artifacts/evidence_ledger/index.yaml",
        )
        if any(item.path == path for item in items)
    )

    return {
        "status": "pass",
        "total_dirty_paths": len(items),
        "counts": counts,
        "category_summaries": category_summaries,
        "categories": categories,
        "cleanup_scope_paths": cleanup_scope_paths,
        "blocked_cleanup_paths": blocked_cleanup_paths,
        "return_gate": (
            "Phase 2B is readability-only; do not stage runtime/state/evidence/exhaust paths. "
            "Return to subject_system_v1_governed_proactivity fresh live recheck unless a later "
            "explicit cleanup slice admits a smaller path class."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify dirty worktree paths for cleanup triage")
    parser.add_argument("--json", action="store_true", help="Print JSON audit payload")
    parser.parse_args()
    print(json.dumps(build_audit_payload(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
