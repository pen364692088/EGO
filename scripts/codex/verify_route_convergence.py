#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys

from route_convergence_common import (
    HYGIENE_RULES,
    REPO_HYGIENE_POLICY_PATH,
    REPO_SURFACE_MAP_PATH,
    TASK_LANE_INDEX_PATH,
    build_route_entries,
    load_program_state,
    render_repo_hygiene_policy,
    render_repo_surface_map,
    render_task_lane_index,
)


def _git_lines(args: list[str]) -> list[str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=REPO_HYGIENE_POLICY_PATH.parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _is_legacy_migration_addition(path: str, deleted_paths: set[str]) -> bool:
    prefix = "legacy/ego-pre-handmade-mainline/"
    if not path.startswith(prefix):
        return False
    return path[len(prefix) :] in deleted_paths


def _check_generated_file(path, expected: str, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing generated file: {path}")
        return
    actual = path.read_text(encoding="utf-8")
    if actual != expected:
        errors.append(f"generated file drift detected: {path}")


def main() -> int:
    errors: list[str] = []
    program_state = load_program_state()
    entries = build_route_entries(program_state)
    expected_lane_index = render_task_lane_index(program_state)
    expected_hygiene_policy = render_repo_hygiene_policy()
    expected_surface_map = render_repo_surface_map()

    _check_generated_file(TASK_LANE_INDEX_PATH, expected_lane_index, errors)
    _check_generated_file(REPO_HYGIENE_POLICY_PATH, expected_hygiene_policy, errors)
    _check_generated_file(REPO_SURFACE_MAP_PATH, expected_surface_map, errors)

    active_default_entries = [entry for entry in entries if entry.lane == "active_default"]
    if len(active_default_entries) != 1:
        errors.append(f"expected exactly one active_default entry, found {len(active_default_entries)}")
    elif active_default_entries[0].key != "ego-operator-human-operator-trial-v2":
        errors.append("active_default entry must be `ego-operator-human-operator-trial-v2` during EgoOperator human-observation gate")

    workstreams = {item.get("id"): item for item in program_state.get("workstreams") or []}
    active_ws = workstreams.get("ego_operator_first_transition") or {}
    if not active_ws:
        errors.append("ego_operator_first_transition workstream missing from docs/PROGRAM_STATE_UNIFIED.yaml")
    elif not str(active_ws.get("status") or "").strip():
        errors.append("ego_operator_first_transition workstream must carry a non-empty current status")
    supporting_ws = workstreams.get("repo_cleanup_route_convergence") or {}
    if supporting_ws.get("status") != "supporting_active":
        errors.append("repo_cleanup_route_convergence workstream must exist and stay `supporting_active`")

    gitignore_text = (REPO_HYGIENE_POLICY_PATH.parents[1] / ".gitignore").read_text(encoding="utf-8")
    deleted_paths = set(_git_lines(["diff", "--name-only", "--no-renames", "--diff-filter=D", "HEAD"]))

    for rule in HYGIENE_RULES:
        for snippet in rule.ignore_snippets:
            if snippet not in gitignore_text:
                errors.append(f".gitignore missing route-hygiene snippet `{snippet}`")

        untracked = _git_lines(["ls-files", "--others", "--exclude-standard", "--", rule.path_prefix])
        if untracked:
            errors.append(
                f"unignored operational exhaust present under {rule.path_prefix}: {', '.join(untracked[:5])}"
            )

        added = set(_git_lines(["diff", "--name-only", "--diff-filter=A", "HEAD", "--", rule.path_prefix]))
        added.update(_git_lines(["diff", "--cached", "--name-only", "--diff-filter=A", "--", rule.path_prefix]))
        added = {path for path in added if not _is_legacy_migration_addition(path, deleted_paths)}
        if added:
            errors.append(
                f"new tracked operational exhaust detected under {rule.path_prefix}: {', '.join(sorted(added)[:5])}"
            )

    if errors:
        print(json.dumps({"status": "fail", "errors": errors}, ensure_ascii=False, indent=2))
        return 1

    print(
        json.dumps(
            {
                "status": "pass",
                "active_default": active_default_entries[0].key if active_default_entries else None,
                "supporting_active_count": sum(1 for entry in entries if entry.lane == "supporting_active"),
                "route_index": str(TASK_LANE_INDEX_PATH.relative_to(REPO_HYGIENE_POLICY_PATH.parents[1])),
                "hygiene_policy": str(REPO_HYGIENE_POLICY_PATH.relative_to(REPO_HYGIENE_POLICY_PATH.parents[1])),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
