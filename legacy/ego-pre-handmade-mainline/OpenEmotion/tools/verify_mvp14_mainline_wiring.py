#!/usr/bin/env python3
"""
Static verifier for MVP14 drive/mainline wiring.

Purpose:
- avoid manual grep when checking whether core/workspace still directly depend
  on legacy drive/homeostasis paths
- provide a machine-readable checkpoint before and after Step05B
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def inspect_wiring() -> dict:
    core_text = _read("OpenEmotion/emotiond/core.py")
    workspace_text = _read("OpenEmotion/emotiond/workspace.py")

    core_direct_legacy_drive_dependency = "emotiond.drive_homeostasis" in core_text
    core_uses_drive_adapter = "from emotiond.drive_adapter import get_drive_adapter" in core_text
    core_uses_adapter_snapshot = ".build_legacy_state(" in core_text

    workspace_direct_legacy_homeostasis_import = "from emotiond.homeostasis import" in workspace_text
    workspace_adds_homeostasis_candidates = "add_homeostasis_candidates" in workspace_text

    core_converged = core_uses_drive_adapter and core_uses_adapter_snapshot and not core_direct_legacy_drive_dependency
    workspace_still_legacy = workspace_direct_legacy_homeostasis_import and workspace_adds_homeostasis_candidates

    if core_converged and not workspace_still_legacy:
        status = "full_convergence"
    elif core_converged:
        status = "decision_mainline_converged_workspace_still_legacy"
    else:
        status = "legacy_mainline_detected"

    return {
        "schema_version": "mvp14.mainline_wiring_check.v1",
        "root": str(ROOT),
        "core": {
            "direct_legacy_drive_dependency": core_direct_legacy_drive_dependency,
            "uses_drive_adapter": core_uses_drive_adapter,
            "uses_adapter_snapshot_builder": core_uses_adapter_snapshot,
            "converged": core_converged,
        },
        "workspace": {
            "direct_legacy_homeostasis_import": workspace_direct_legacy_homeostasis_import,
            "adds_homeostasis_candidates": workspace_adds_homeostasis_candidates,
            "legacy_path_present": workspace_still_legacy,
        },
        "status": status,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Print JSON only.")
    parser.add_argument(
        "--require-core-converged",
        action="store_true",
        help="Exit non-zero unless core.py no longer directly imports drive_homeostasis and uses drive_adapter snapshots.",
    )
    parser.add_argument(
        "--require-workspace-converged",
        action="store_true",
        help="Exit non-zero unless workspace.py also no longer directly depends on legacy homeostasis path.",
    )
    args = parser.parse_args()

    report = inspect_wiring()

    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        print(f"status: {report['status']}")
        print(f"core.converged: {report['core']['converged']}")
        print(f"workspace.legacy_path_present: {report['workspace']['legacy_path_present']}")

    if args.require_core_converged and not report["core"]["converged"]:
        return 1
    if args.require_workspace_converged and report["workspace"]["legacy_path_present"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
