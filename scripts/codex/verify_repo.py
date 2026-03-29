#!/usr/bin/env python3
"""
Detect and run repo validation commands for the Codex long-run harness.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Check:
    category: str
    name: str
    command: Sequence[str]
    cwd: Path
    source: str
    run_in_fast: bool
    run_in_full: bool
    env_overrides: dict[str, str] | None = None
    report_only: bool = False
    precondition_reason: str | None = None


@dataclass
class Result:
    category: str
    name: str
    command: str
    source: str
    status: str
    note: str
    returncode: int | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run repo validation checks for Codex long-run tasks")
    parser.add_argument("--mode", choices=["fast", "full"], required=True, help="Validation depth")
    parser.add_argument("--dry-run", action="store_true", help="Print detected commands without executing them")
    return parser.parse_args()


def has_make_target(path: Path, target: str) -> bool:
    if not path.exists():
        return False
    needle = f"{target}:"
    return needle in path.read_text(encoding="utf-8", errors="ignore")


def health_endpoint_available() -> bool:
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen("http://127.0.0.1:18080/health", timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def python_command(path: str | Path) -> list[str]:
    return [str(path)]


def candidate_openemotion_python() -> list[tuple[list[str], str]]:
    candidates: list[tuple[list[str], str]] = []
    env_python = os.environ.get("OPENEMOTION_PYTHON")
    if env_python:
        candidates.append((python_command(env_python), f"OPENEMOTION_PYTHON={env_python}"))

    path_candidates = [
        (ROOT / "OpenEmotion" / ".venv" / "bin" / "python", "OpenEmotion/.venv/bin/python"),
        (ROOT / "OpenEmotion" / "venv" / "bin" / "python", "OpenEmotion/venv/bin/python"),
        (ROOT / "OpenEmotion" / ".venv" / "Scripts" / "python.exe", "OpenEmotion/.venv/Scripts/python.exe"),
        (ROOT / "OpenEmotion" / "venv" / "Scripts" / "python.exe", "OpenEmotion/venv/Scripts/python.exe"),
    ]
    for path, label in path_candidates:
        if path.exists():
            candidates.append((python_command(path), label))

    candidates.append((python_command(sys.executable), f"current interpreter ({sys.executable})"))

    deduped: list[tuple[list[str], str]] = []
    seen: set[str] = set()
    for command, label in candidates:
        key = command[0]
        if key not in seen:
            seen.add(key)
            deduped.append((command, label))
    return deduped


def python_missing_modules(command: Sequence[str], modules: Sequence[str]) -> list[str]:
    probe = [*command, "-c", "import " + ", ".join(modules)]
    proc = subprocess.run(probe, cwd=ROOT / "OpenEmotion", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if proc.returncode == 0:
        return []
    missing: list[str] = []
    for module in modules:
        single = [*command, "-c", f"import {module}"]
        proc = subprocess.run(single, cwd=ROOT / "OpenEmotion", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if proc.returncode != 0:
            missing.append(module)
    return missing


def resolved_openemotion_python() -> tuple[list[str], str]:
    return candidate_openemotion_python()[0]


def repo_local_pythonpath(entries: Sequence[Path]) -> str:
    parts = [str(path) for path in entries]
    existing = os.environ.get("PYTHONPATH")
    if existing:
        parts.append(existing)
    return os.pathsep.join(parts)


def detect_checks() -> List[Check]:
    checks: List[Check] = []

    ego_pyproject = ROOT / "EgoCore" / "pyproject.toml"
    ego_tests = ROOT / "EgoCore" / "tests"
    ego_regression = ROOT / "EgoCore" / "tools" / "run_telegram_mainline_regression.sh"
    open_pyproject = ROOT / "OpenEmotion" / "pyproject.toml"
    open_makefile = ROOT / "OpenEmotion" / "Makefile"
    open_smoke = ROOT / "OpenEmotion" / "test_smoke.py"
    open_typecheck_simple = ROOT / "OpenEmotion" / "verify_typecheck_simple.py"
    open_typecheck = ROOT / "OpenEmotion" / "verify_typecheck.py"
    open_testbot = ROOT / "OpenEmotion" / "scripts" / "run_testbot_scenarios.py"
    repo_lint = ROOT / "scripts" / "codex" / "lint_repo.py"
    open_python_cmd, open_python_label = resolved_openemotion_python()
    open_runtime_missing = python_missing_modules(open_python_cmd, ["fastapi", "pydantic", "pytest", "requests"])
    open_smoke_missing = python_missing_modules(open_python_cmd, ["fastapi", "requests"])
    ego_pytest_env = {
        "PYTHONPATH": repo_local_pythonpath(
            [
                ROOT / "EgoCore",
                ROOT / "EgoCore" / "modules",
                ROOT / "OpenEmotion",
            ]
        )
    }

    if ego_pyproject.exists():
        checks.append(
            Check(
                category="build",
                name="EgoCore editable install",
                command=["python3", "-m", "pip", "install", "-e", ".[dev]"],
                cwd=ROOT / "EgoCore",
                source="EgoCore/pyproject.toml",
                run_in_fast=False,
                run_in_full=False,
                report_only=True,
                precondition_reason="setup/bootstrap command, not verification-grade",
            )
        )

    if has_make_target(open_makefile, "venv"):
        checks.append(
            Check(
                category="build",
                name="OpenEmotion venv bootstrap",
                command=["make", "venv"],
                cwd=ROOT / "OpenEmotion",
                source="OpenEmotion/Makefile",
                run_in_fast=False,
                run_in_full=False,
                report_only=True,
                precondition_reason="setup/bootstrap command, not verification-grade",
            )
        )

    if ego_pyproject.exists() and ego_tests.exists():
        checks.append(
            Check(
                category="test",
                name="EgoCore pytest suite",
                command=["python3", "-m", "pytest", "tests/", "-v", "-s"],
                cwd=ROOT / "EgoCore",
                source="EgoCore/pyproject.toml + EgoCore/tests/ via repo-local PYTHONPATH",
                run_in_fast=False,
                run_in_full=True,
                env_overrides=ego_pytest_env,
                precondition_reason="full-only heavy test suite",
            )
        )

    if has_make_target(open_makefile, "test"):
        test_command: Sequence[str] = [*open_python_cmd, "-m", "pytest", "tests/", "-q"]
        source = f"OpenEmotion/pyproject.toml + OpenEmotion/tests/ via {open_python_label}"
        open_test_reason = "full-only heavy test suite"
        if open_runtime_missing:
            open_test_reason = (
                f"{open_python_label} missing modules: {', '.join(open_runtime_missing)}"
            )
        checks.append(
            Check(
                category="test",
                name="OpenEmotion test suite",
                command=test_command,
                cwd=ROOT / "OpenEmotion",
                source=source,
                run_in_fast=False,
                run_in_full=not open_runtime_missing,
                precondition_reason=open_test_reason,
            )
        )

    if repo_lint.exists():
        checks.append(
            Check(
                category="lint",
                name="Codex repo lint",
                command=["python3", "scripts/codex/lint_repo.py"],
                cwd=ROOT,
                source="scripts/codex/lint_repo.py",
                run_in_fast=True,
                run_in_full=True,
            )
        )

    if open_typecheck_simple.exists():
        simple_reason = None
        if open_runtime_missing:
            simple_reason = f"{open_python_label} missing modules: {', '.join(open_runtime_missing)}"
        checks.append(
            Check(
                category="typecheck",
                name="OpenEmotion simple typecheck",
                command=[*open_python_cmd, "verify_typecheck_simple.py"],
                cwd=ROOT / "OpenEmotion",
                source=f"OpenEmotion/verify_typecheck_simple.py via {open_python_label}",
                run_in_fast=simple_reason is None,
                run_in_full=False,
                precondition_reason=simple_reason,
            )
        )

    if open_typecheck.exists():
        checks.append(
            Check(
                category="typecheck",
                name="OpenEmotion full typecheck",
                command=[*open_python_cmd, "verify_typecheck.py"],
                cwd=ROOT / "OpenEmotion",
                source=f"OpenEmotion/verify_typecheck.py via {open_python_label}",
                run_in_fast=False,
                run_in_full=True,
            )
        )

    smoke_reason = None
    if not open_smoke.exists():
        smoke_reason = "missing OpenEmotion/test_smoke.py"
    elif open_smoke_missing:
        smoke_reason = f"{open_python_label} missing modules: {', '.join(open_smoke_missing)}"
    checks.append(
        Check(
            category="e2e/smoke",
            name="OpenEmotion smoke",
            command=[*open_python_cmd, "test_smoke.py"],
            cwd=ROOT / "OpenEmotion",
            source=f"OpenEmotion/test_smoke.py via {open_python_label}",
            run_in_fast=smoke_reason is None,
            run_in_full=False,
            precondition_reason=smoke_reason,
        )
    )

    if ego_regression.exists():
        checks.append(
            Check(
                category="e2e/smoke",
                name="EgoCore Telegram mainline regression",
                command=["bash", "./tools/run_telegram_mainline_regression.sh"],
                cwd=ROOT / "EgoCore",
                source="EgoCore/tools/run_telegram_mainline_regression.sh",
                run_in_fast=False,
                run_in_full=True,
            )
        )

    testbot_reason = None
    if not open_testbot.exists():
        testbot_reason = "missing OpenEmotion/scripts/run_testbot_scenarios.py"
    elif not health_endpoint_available():
        testbot_reason = "emotiond health endpoint unavailable at 127.0.0.1:18080"
    checks.append(
        Check(
            category="e2e/smoke",
            name="OpenEmotion testbot PR subset",
            command=[
                *open_python_cmd,
                "scripts/run_testbot_scenarios.py",
                "--subset",
                "pr",
                "--output",
                "artifacts/testbot/pr_summary.json",
            ],
            cwd=ROOT / "OpenEmotion",
            source=f"OpenEmotion/scripts/run_testbot_scenarios.py via {open_python_label}",
            run_in_fast=False,
            run_in_full=testbot_reason is None,
            precondition_reason=testbot_reason,
        )
    )

    return checks


def should_run(check: Check, mode: str) -> tuple[bool, str | None]:
    if check.report_only:
        return False, check.precondition_reason
    if check.precondition_reason and not (check.run_in_fast or check.run_in_full):
        return False, check.precondition_reason
    if mode == "fast" and check.run_in_fast:
        return True, None
    if mode == "full" and check.run_in_full:
        return True, None
    if mode == "fast":
        return False, check.precondition_reason or "full-only heavy test suite"
    return False, check.precondition_reason or "not enabled for this mode"


def run_check(check: Check, *, dry_run: bool) -> Result:
    command_str = " ".join(check.command) if check.command else "(none)"
    should_execute, reason = should_run(check, MODE)
    if not should_execute:
        return Result(
            category=check.category,
            name=check.name,
            command=command_str,
            source=check.source,
            status="skipped",
            note=reason or "not selected",
        )
    if dry_run:
        return Result(
            category=check.category,
            name=check.name,
            command=command_str,
            source=check.source,
            status="skipped",
            note="dry-run",
        )

    env = os.environ.copy()
    if check.env_overrides:
        env.update(check.env_overrides)
    proc = subprocess.run(
        list(check.command),
        cwd=check.cwd,
        env=env,
        text=True,
    )
    if proc.returncode == 0:
        return Result(
            category=check.category,
            name=check.name,
            command=command_str,
            source=check.source,
            status="success",
            note="ok",
            returncode=0,
        )
    return Result(
        category=check.category,
        name=check.name,
        command=command_str,
        source=check.source,
        status="failed",
        note=f"exit={proc.returncode}",
        returncode=proc.returncode,
    )


def print_summary(results: Iterable[Result]) -> None:
    print(f"Codex verify summary (mode={MODE})")
    print("=" * 96)
    print(f"{'category':<12} {'status':<8} {'name':<34} {'source':<28} note")
    print("-" * 96)
    for result in results:
        print(
            f"{result.category:<12} {result.status:<8} {result.name[:34]:<34} "
            f"{result.source[:28]:<28} {result.note}"
        )
        print(f"  command: {result.command}")


MODE = "fast"


def main() -> int:
    global MODE
    args = parse_args()
    MODE = args.mode
    checks = detect_checks()
    results = [run_check(check, dry_run=args.dry_run) for check in checks]
    print_summary(results)
    return 1 if any(result.status == "failed" for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
