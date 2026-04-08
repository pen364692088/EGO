#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TASK_ROOT = ROOT / "docs" / "codex" / "tasks" / "repo-authority-cleanup"
CANONICAL_DOCS_INDEX = TASK_ROOT / "CANONICAL_DOCS_INDEX.md"
ARTIFACT_LOG_INVENTORY = TASK_ROOT / "ARTIFACT_LOG_INVENTORY.md"
DOCS_CANONICAL = ROOT / "docs" / "canonical" / "README.md"
DOCS_ARCHIVE = ROOT / "docs" / "archive" / "README.md"
ARTIFACTS_CURRENT = ROOT / "artifacts" / "current" / "README.md"
ARTIFACTS_ARCHIVE = ROOT / "artifacts" / "archive" / "README.md"


REQUIRED_SNIPPETS = {
    CANONICAL_DOCS_INDEX: [
        "| `README.md` | repo-level public authority summary |",
        "| `docs/CURRENT_PROJECT_LOGIC_FLOW.md` | current formal logic/call chain summary |",
        "| `docs/PROTO_SELF_SINGLE_AUTHORITY_DECISION.md` | prescriptive authority decision layer |",
        "| `docs/codex/tasks/repo-authority-cleanup/CANONICAL_DOCS_INDEX.md` | cleanup execution ledger |",
        "| `docs/canonical/README.md` | canonical boundary marker |",
        "| `docs/archive/README.md` | archive boundary marker |",
    ],
    ARTIFACT_LOG_INVENTORY: [
        "| `artifacts/telegram_real_mainline_v1/*` | current Telegram mainline evidence |",
        "| `artifacts/acceptance_chains/*` | current generated acceptance outputs |",
        "| `OpenEmotion/artifacts/mvp12/*CURRENT*`, `mvp13/*CURRENT*`, `mvp14/*CURRENT*`, `mvp15/*CURRENT*`, `mvp16/*CURRENT*` | current owner-axis evidence |",
        "| `artifacts/current/README.md` | current artifact boundary marker |",
        "| `artifacts/archive/README.md` | archive artifact boundary marker |",
    ],
    DOCS_CANONICAL: [
        "Physical canonical migration is not complete yet.",
        "Use `docs/codex/tasks/repo-authority-cleanup/CANONICAL_DOCS_INDEX.md` as the current canonical index.",
    ],
    DOCS_ARCHIVE: [
        "Archive relocation is admission-controlled.",
        "Do not move files here until caller and gate references are cleared.",
    ],
    ARTIFACTS_CURRENT: [
        "Current artifact boundary marker.",
        "Do not move current evidence bundles until caller migration is complete.",
    ],
    ARTIFACTS_ARCHIVE: [
        "Archive artifact boundary marker.",
        "Do not archive replay / trace / audit evidence without explicit admission proof.",
    ],
}


def main() -> int:
    errors: list[str] = []
    for path, snippets in REQUIRED_SNIPPETS.items():
        if not path.exists():
            errors.append(f"missing cleanup admission surface: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet not in text:
                errors.append(f"{path.relative_to(ROOT)} missing required cleanup admission snippet: {snippet}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("cleanup admission gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
