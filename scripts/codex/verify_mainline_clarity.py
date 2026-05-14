#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from route_convergence_common import (
    HYGIENE_RULES,
    REPO_SURFACE_MAP_PATH,
    build_route_entries,
    load_program_state,
    render_repo_surface_map,
)


ROOT = Path(__file__).resolve().parents[2]
README_PATH = ROOT / "README.md"
QUICKSTART_PATH = ROOT / "docs" / "MAINLINE_QUICKSTART.md"
WORKTREE_TRIAGE_PATH = ROOT / "docs" / "codex" / "tasks" / "repo-mainline-clarity-v1" / "WORKTREE_TRIAGE.md"
RETURN_GATE_REVIEW_PATH = ROOT / "docs" / "codex" / "tasks" / "repo-mainline-clarity-v1" / "RETURN_GATE_REVIEW.md"
AUDIT_WORKTREE_NOISE_PATH = ROOT / "scripts" / "codex" / "audit_worktree_noise.py"


REQUIRED_README_REFS = (
    "docs/MAINLINE_QUICKSTART.md",
    "docs/PROGRAM_STATE_UNIFIED.yaml",
    "docs/codex/tasks/TASK_LANE_INDEX.md",
    "docs/REPO_HYGIENE_POLICY.md",
)

REQUIRED_QUICKSTART_REFS = (
    "subject_system_v1_governed_proactivity",
    "EgoCore",
    "OpenEmotion",
    "ego_desktop_lab",
    "reference harness",
    "not a second runtime",
    "docs/PROGRAM_STATE_UNIFIED.yaml",
    "docs/codex/tasks/TASK_LANE_INDEX.md",
)

REQUIRED_TRIAGE_REFS = (
    "authority_dirty",
    "formal_runtime_dirty",
    "operational_exhaust",
    "No runtime behavior changes",
    "Return gate",
    "subject_system_v1_governed_proactivity",
)

REQUIRED_RETURN_GATE_REFS = (
    "subject_system_v1_governed_proactivity",
    "fresh live recheck",
    "mainline_runtime_review",
    "evidence_admission",
    "operational_exhaust_policy",
    "unknown_manual_triage",
    "No runtime behavior changes",
)

CLEANUP_STAGE_PREFIXES = (
    "docs/codex/tasks/repo-mainline-clarity-v1/",
    "scripts/codex/audit_worktree_noise.py",
    "scripts/codex/verify_mainline_clarity.py",
)

FORBIDDEN_CLEANUP_STAGE_PATHS = (
    "docs/PROGRAM_STATE_UNIFIED.yaml",
    "EgoCore/docs/PROGRAM_STATE_UNIFIED.yaml",
    "OpenEmotion/docs/PROGRAM_STATE_UNIFIED.yaml",
    "artifacts/evidence_ledger/index.yaml",
)

FORBIDDEN_CLEANUP_STAGE_PREFIXES = (
    "EgoCore/",
    "OpenEmotion/",
    "artifacts/evidence_ledger/",
    "artifacts/reports/",
    "artifacts/telegram_real_mainline_v1/",
    "temp/",
    "logs/",
    ".pytest_cache/",
)

FORBIDDEN_ALWAYS_STAGE_PREFIXES = (
    "temp/",
    "logs/",
    ".pytest_cache/",
)

FORBIDDEN_CLEANUP_STAGE_SUFFIXES = (
    ".jsonl",
    ".log",
    ".pyc",
    ".pyo",
)


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


def _matches_prefix(path: str, prefix: str) -> bool:
    return path == prefix.rstrip("/") or path.startswith(prefix)


def _check_staged_operational_exhaust(errors: list[str]) -> None:
    staged_paths = _git_lines(["diff", "--cached", "--name-only"])
    cleanup_stage_active = any(
        any(_matches_prefix(path, prefix) for prefix in CLEANUP_STAGE_PREFIXES)
        for path in staged_paths
    )
    blocked: list[str] = []
    for path in staged_paths:
        if cleanup_stage_active and path in FORBIDDEN_CLEANUP_STAGE_PATHS:
            blocked.append(f"{path} (authority_or_formal_evidence_do_not_stage_in_cleanup)")
            continue
        if cleanup_stage_active:
            if path.startswith(FORBIDDEN_CLEANUP_STAGE_PREFIXES) or path.endswith(FORBIDDEN_CLEANUP_STAGE_SUFFIXES):
                blocked.append(f"{path} (not_allowed_in_repo_mainline_clarity_cleanup_stage)")
                continue
            if not any(_matches_prefix(path, prefix) for prefix in CLEANUP_STAGE_PREFIXES):
                blocked.append(f"{path} (not_allowed_in_repo_mainline_clarity_cleanup_stage)")
                continue
        elif path.startswith(FORBIDDEN_ALWAYS_STAGE_PREFIXES):
            blocked.append(f"{path} (operational_exhaust)")
            continue
        for rule in HYGIENE_RULES:
            if _matches_prefix(path, rule.path_prefix):
                blocked.append(f"{path} ({rule.class_name})")
                break
        if "__pycache__/" in path or path.endswith((".pyc", ".pyo")):
            blocked.append(f"{path} (python_cache_exhaust)")
    if blocked:
        errors.append("staged operational exhaust is not allowed: " + ", ".join(sorted(blocked)[:20]))


def _check_text_contains(path: Path, required: tuple[str, ...], errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing required mainline clarity file: {path.relative_to(ROOT)}")
        return
    text = path.read_text(encoding="utf-8")
    for item in required:
        if item not in text:
            errors.append(f"{path.relative_to(ROOT)} missing `{item}`")


def _check_worktree_audit(errors: list[str]) -> None:
    if not AUDIT_WORKTREE_NOISE_PATH.exists():
        errors.append("missing scripts/codex/audit_worktree_noise.py")
        return

    proc = subprocess.run(
        ["python3", "scripts/codex/audit_worktree_noise.py", "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        errors.append(f"audit_worktree_noise.py failed: {proc.stderr.strip()}")
        return
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        errors.append(f"audit_worktree_noise.py emitted invalid JSON: {exc}")
        return

    required_categories = {
        "formal_runtime_dirty",
        "authority_dirty",
        "formal_evidence_dirty",
        "operational_exhaust",
        "generated_or_mirror",
        "untracked_unknown",
        "cleanup_candidate",
    }
    categories = payload.get("categories")
    if not isinstance(categories, dict):
        errors.append("audit_worktree_noise.py payload missing categories")
        return
    missing = sorted(required_categories - set(categories))
    if missing:
        errors.append(f"audit_worktree_noise.py missing categories: {', '.join(missing)}")

    category_summaries = payload.get("category_summaries")
    if not isinstance(category_summaries, dict):
        errors.append("audit_worktree_noise.py payload missing category_summaries")
    else:
        for category in required_categories:
            summary = category_summaries.get(category)
            if not isinstance(summary, dict):
                errors.append(f"audit_worktree_noise.py category_summaries missing {category}")
                continue
            if "recommended_next_owner" not in summary:
                errors.append(f"audit_worktree_noise.py {category} summary missing recommended_next_owner")
            top_paths = summary.get("top_20_paths")
            if not isinstance(top_paths, list):
                errors.append(f"audit_worktree_noise.py {category} summary missing top_20_paths")
            elif len(top_paths) > 20:
                errors.append(f"audit_worktree_noise.py {category} top_20_paths has more than 20 entries")

    by_path: dict[str, str] = {}
    for category, items in categories.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("path"), str):
                by_path[item["path"]] = category

    expected_if_dirty = {
        "docs/PROGRAM_STATE_UNIFIED.yaml": "authority_dirty",
        "artifacts/evidence_ledger/index.yaml": "formal_evidence_dirty",
    }
    for path, expected_category in expected_if_dirty.items():
        actual = by_path.get(path)
        if actual is not None and actual != expected_category:
            errors.append(f"{path} classified as {actual}, expected {expected_category}")


def main() -> int:
    errors: list[str] = []
    state = load_program_state()
    entries = build_route_entries(state)
    active = [entry for entry in entries if entry.lane == "active_default"]
    if len(active) != 1:
        errors.append(f"expected exactly one active_default lane, found {len(active)}")
    elif active[0].key != "subject-system-v1-governed-proactivity":
        errors.append("active_default lane must stay `subject-system-v1-governed-proactivity`")

    _check_text_contains(README_PATH, REQUIRED_README_REFS, errors)
    _check_text_contains(QUICKSTART_PATH, REQUIRED_QUICKSTART_REFS, errors)
    _check_text_contains(WORKTREE_TRIAGE_PATH, REQUIRED_TRIAGE_REFS, errors)
    _check_text_contains(RETURN_GATE_REVIEW_PATH, REQUIRED_RETURN_GATE_REFS, errors)
    _check_worktree_audit(errors)

    if not REPO_SURFACE_MAP_PATH.exists():
        errors.append("missing generated docs/REPO_SURFACE_MAP.md")
    else:
        expected = render_repo_surface_map()
        actual = REPO_SURFACE_MAP_PATH.read_text(encoding="utf-8")
        if actual != expected:
            errors.append("generated file drift detected: docs/REPO_SURFACE_MAP.md")

    _check_staged_operational_exhaust(errors)

    if errors:
        print(json.dumps({"status": "fail", "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    print(
        json.dumps(
            {
                "status": "pass",
                "active_default": active[0].key if active else None,
                "quickstart": str(QUICKSTART_PATH.relative_to(ROOT)),
                "surface_map": str(REPO_SURFACE_MAP_PATH.relative_to(ROOT)),
                "staged_exhaust_blocked": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
