#!/usr/bin/env python3
"""
Stable lightweight lint entry for repo control surfaces and core Python sources.
"""

from __future__ import annotations

import py_compile
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

PYTHON_DIRS = [
    ROOT / "EgoCore" / "app",
    ROOT / "OpenEmotion" / "emotiond",
    ROOT / "OpenEmotion" / "openemotion",
    ROOT / "scripts" / "codex",
]

PYTHON_FILES = [
    ROOT / "OpenEmotion" / "test_smoke.py",
    ROOT / "OpenEmotion" / "verify_typecheck.py",
    ROOT / "OpenEmotion" / "verify_typecheck_simple.py",
]

TEXT_GLOBS = [
    ROOT / "AGENTS.md",
]

TEXT_DIRS = [
    ROOT / ".agents" / "skills",
    ROOT / "docs" / "codex",
]


def iter_python_files() -> list[Path]:
    files: list[Path] = []
    for directory in PYTHON_DIRS:
        if directory.exists():
            files.extend(sorted(directory.rglob("*.py")))
    for path in PYTHON_FILES:
        if path.exists():
            files.append(path)
    return sorted({path.resolve() for path in files})


def iter_text_files() -> list[Path]:
    files = [path for path in TEXT_GLOBS if path.exists()]
    for directory in TEXT_DIRS:
        if directory.exists():
            files.extend(sorted(directory.rglob("*.md")))
    return sorted({path.resolve() for path in files})


def check_python(files: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in files:
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"python syntax failed: {path.relative_to(ROOT)} -> {exc.msg}")
    return errors


def check_text(files: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in files:
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()
        for idx, line in enumerate(lines, start=1):
            if line.rstrip(" \t") != line:
                errors.append(f"trailing whitespace: {path.relative_to(ROOT)}:{idx}")
        if content and not content.endswith("\n"):
            errors.append(f"missing trailing newline: {path.relative_to(ROOT)}")
        if path.name == "SKILL.md":
            errors.extend(check_skill_frontmatter(path, content))
    return errors


def check_skill_frontmatter(path: Path, content: str) -> list[str]:
    errors: list[str] = []
    lines = content.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return [f"missing frontmatter: {path.relative_to(ROOT)}"]
    try:
        closing = lines[1:].index("---") + 1
    except ValueError:
        return [f"unterminated frontmatter: {path.relative_to(ROOT)}"]
    frontmatter = "\n".join(lines[1:closing])
    if "name:" not in frontmatter:
        errors.append(f"frontmatter missing name: {path.relative_to(ROOT)}")
    if "description:" not in frontmatter:
        errors.append(f"frontmatter missing description: {path.relative_to(ROOT)}")
    return errors


def main() -> int:
    python_files = iter_python_files()
    text_files = iter_text_files()
    errors = check_python(python_files) + check_text(text_files)

    print("Codex repo lint")
    print("=" * 60)
    print(f"python files checked: {len(python_files)}")
    print(f"text files checked: {len(text_files)}")

    if errors:
        print("\nLint failures:")
        for entry in errors:
            print(f"- {entry}")
        return 1

    print("\nOK: no lint failures detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
